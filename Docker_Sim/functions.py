import copy
import gc
import logging
import math
import pathlib
import time

import gmsh
import meshlib.mrmeshpy as mrmeshpy
import numpy as np
import param
from electrodes import electrode_placement, small_standard_positions
from param import cond as c
from param import (
    d_rect,
    h_electrode,
    h_silicon,
    isolation_shape,
    n_electrodes,
    onamehead,
    pathfem,
    pos_centre,
)
from scipy.spatial import ConvexHull, KDTree, cKDTree
from scipy.spatial.distance import cdist
from simnibs import mesh_tools, sim_struct
from simnibs.mesh_tools import mesh_io
from simnibs.mesh_tools.mesh_io import Elements, Msh
from simnibs.simulation import fem
from svg_to_nodes import svg_to_nodes

logger = logging.getLogger("planningtool")


def remove_from_mesh(mesh, tag):
    """
    Remove volume(s) with the specified tag(s) from a mesh.

    This function calls mesh.remove_from_mesh(tag) internally and verifies
    that no elements with the old tag remain.

    Parameters
    ----------
    mesh : Msh
        The Msh object from which to remove elements.
    tag : int or list of int
        An integer or list of integers representing the volume tags to be removed.

    Returns
    -------
    Msh
        The updated Msh object with the specified volume(s) removed.
    """
    mesh_core = mesh.remove_from_mesh(tag)
    assert len(mesh_core.elm.nodes_with_tag(tag)) == 0, \
        "volume %i has not been removed completely!" % (tag)
    return mesh_core


def remove_skin(mesh):
    """
    Remove skin volume and surface from the mesh.

    Internally calls remove_from_mesh with tags [5, 1005], which typically correspond
    to skin volumes/surfaces in this setup.

    Parameters
    ----------
    mesh : Msh
        The Msh object from which to remove skin.

    Returns
    -------
    Msh
        The updated Msh object with skin removed.
    """
    return remove_from_mesh(mesh, [5, 1005])


def retag(mesh, otag, ntag):
    """
    Change element tags from old tag (otag) to new tag (ntag).

    This function modifies mesh.elm.tag1 and mesh.elm.tag2 in-place to switch
    elements from otag to ntag, then checks consistency.

    Parameters
    ----------
    mesh : Msh
        The Msh object whose elements will be retagged.
    otag : int
        The old tag to be replaced.
    ntag : int
        The new tag that replaces the old tag.

    Returns
    -------
    None
        Modifies mesh in place.
    """
    n_nodes_otag = len(mesh.elm.nodes_with_tag(otag))
    mesh.elm.tag1 = np.where(mesh.elm.tag1 == otag, ntag, mesh.elm.tag1)
    mesh.elm.tag2 = np.where(mesh.elm.tag2 == otag, ntag, mesh.elm.tag2)
    n_nodes_ntag = len(mesh.elm.nodes_with_tag(ntag))
    assert n_nodes_otag == n_nodes_ntag, "error in retagging!"
    assert len(mesh.elm.nodes_with_tag(otag)) == 0, "retag left nodes with the old tag!"


def compact_bone_to_skin(mesh):
    """
    Reassign compact bone tags to skin tags.

    This function calls retag to replace the compact bone tags (1007, 7)
    with the skin tags (1005, 5).

    Parameters
    ----------
    mesh : Msh
        The Msh object to modify.

    Returns
    -------
    None
        Modifies mesh in place.
    """
    retag(mesh, 1007, 1005)
    retag(mesh, 7, 5)


def compact_bone_back(mesh):
    """
    Reassign skin tags back to compact bone.

    This reverses the assignments done in compact_bone_to_skin by replacing
    skin tags (1005, 5) with bone tags (1007, 7).

    Parameters
    ----------
    mesh : Msh
        The Msh object to modify.

    Returns
    -------
    None
        Modifies mesh in place.
    """
    retag(mesh, 1005, 1007)
    retag(mesh, 5, 7)


def mesh_get_outer_surface(mesh, ntag) -> Msh:
    """
    Extract the outer surface from a mesh as a new Msh.

    This function identifies all outside faces (triangles on the outer surface)
    and creates a new Msh object containing only those faces, assigning them a
    specified tag (ntag).

    Parameters
    ----------
    mesh : Msh
        The original mesh.
    ntag : int
        The tag to assign to the new surface elements.

    Returns
    -------
    Msh
        A new Msh object containing only the outer surface triangles.
    """
    faces = mesh.elm.get_outside_faces()
    bound = Msh(mesh.nodes, Elements(triangles=faces))
    bound.elm.tag1 = np.full(bound.elm.tag1.shape, ntag)
    bound.elm.tag2 = np.full(bound.elm.tag2.shape, ntag)
    return bound


def msh2_to_simnibs(name):
    """
    Convert a .msh file to a SimNIBS-compatible format (removes carriage returns).

    This function reads an existing .msh file in binary mode, strips carriage returns,
    writes out a new file named '[original]_simnibs.msh', and then reads it via
    mesh_tools.read_msh.

    Parameters
    ----------
    name : str
        The path to the original .msh file.

    Returns
    -------
    Msh
        A Msh object read from the newly created '_simnibs.msh' file.
    """
    all_dots = [i for i in range(len(name)) if name.startswith('.', i)]
    extension_pos = all_dots[-1]

    with open(name, 'rb') as f1, open(name[0:extension_pos] + '_simnibs.msh', 'wb') as f2:
        lines = f1.readlines()
        for line in lines:
            line = line.decode()
            f2.write(bytes(line.replace('\r', ''), 'utf-8'))

    return mesh_tools.read_msh(name[0:extension_pos] + '_simnibs.msh')


def refine(mesh, path: pathlib.Path, refined_name):
    """
    Refine the mesh using gmsh and return the refined mesh.

    This function:
        - Writes the original mesh to 'mesh_before_refining.msh'.
        - Uses gmsh to refine the mesh.
        - Cleans up carriage returns in the intermediate file.
        - Saves the final refined mesh under 'refined_name'.
        - Removes intermediate .msh files except for the one containing 'skull' in its name.

    Parameters
    ----------
    mesh : Msh
        The mesh to refine.
    path : pathlib.Path
        A pathlib.Path where intermediate and final files will be stored.
    refined_name : str
        A string name for the final refined mesh file.

    Returns
    -------
    Msh
        The refined Msh object read from the final file.
    """
    logger.info('Skull global refining:')

    mesh.write(str(path / 'mesh_before_refining.msh'))

    logger.info(f"{str(path)} mesh_after_refining_pre.msh")

    gmsh.initialize()
    gmsh.open(str(path / "mesh_before_refining.msh"))
    gmsh.model.mesh.refine()
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
    gmsh.write(str(path / "mesh_after_refining_pre.msh"))
    gmsh.finalize()

    buffer_size = 1024 * 1024  # 1 MB chunks
    with open(path / "mesh_after_refining_pre.msh", "rb") as f1, \
         open(path / "mesh_after_refining_gmsh.msh", "wb") as f2:
        while chunk := f1.read(buffer_size):
            chunk = chunk.replace(b'\r', b'')
            f2.write(chunk)

    logger.info("Done!")
    logger.info("Refined mesh saving:")

    refined_skull = mesh_tools.read_msh(str(path / "mesh_after_refining_gmsh.msh"))

    # Additional checks and cleanup
    logger.info("Checking for degenerate elements and disconnected nodes...")
    refined_skull = remove_disconnected_nodes(refined_skull)

    refined_skull.write(str(path / refined_name))

    for file_path in path.glob("*.msh"):
        if "skull" not in file_path.name:
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error while deleting file: {file_path}, Error: {str(e)}")

    logger.info("Done!")
    return mesh_tools.read_msh(str(path / refined_name))

def join_and_connect(mesh1: Msh, mesh2: Msh) -> Msh:
    """
    Join two meshes and merge shared nodes.

    This function searches for coincident nodes between mesh1 and mesh2 using
    a KD-Tree. Shared nodes are merged, while non-shared nodes are appended
    to the first mesh.

    Parameters
    ----------
    mesh1 : Msh
        The primary Msh object to which the second is joined.
    mesh2 : Msh
        The secondary Msh object to be joined.

    Returns
    -------
    Msh
        A new Msh object containing both meshes, with shared nodes merged.
    """
    kdtree = cKDTree(mesh1.nodes[:])  # type: ignore
    distance, idx = kdtree.query(mesh2.nodes[:])  # type: ignore

    shared_nodes = np.isclose(distance, 0)
    new_m2_node_numbers = np.zeros(mesh2.nodes.nr, dtype=int)
    new_m2_node_numbers[shared_nodes] = idx[shared_nodes] + 1
    new_m2_node_numbers[~shared_nodes] = np.arange(np.sum(~shared_nodes)) + mesh1.nodes.nr + 1

    # Update element connectivity
    new_m2_nnl = new_m2_node_numbers[mesh2.elm.node_number_list - 1]
    new_m2_nnl[mesh2.elm.elm_type == 2, 3] = -1

    # Create joined mesh
    joined = copy.deepcopy(mesh1)
    joined.nodes.node_coord = np.append(
        mesh1.nodes.node_coord, mesh2.nodes[~shared_nodes], axis=0
    )
    joined.elm.node_number_list = np.append(
        mesh1.elm.node_number_list, new_m2_nnl, axis=0
    )
    joined.elm.elm_type = np.append(mesh1.elm.elm_type, mesh2.elm.elm_type)
    joined.elm.tag1 = np.append(mesh1.elm.tag1, mesh2.elm.tag1)
    joined.elm.tag2 = np.append(mesh1.elm.tag2, mesh2.elm.tag2)

    # Check for disconnected components
    joined = remove_disconnected_nodes(joined)

    return joined

def run_simulation(S, electrode_surfaces):
    """
    Run a tDCS simulation using a custom Neumann-based solver.

    This function:
        - Adjusts electrode conductivities in the session (S).
        - Prepares the mesh for simulation.
        - Calls a custom Neumann solver ('custom_tdcs_neumann') to calculate potential.
        - Calculates resulting fields and writes outputs to disk.

    Parameters
    ----------
    S : SimNIBS SESSION
        A SimNIBS SESSION object with all electrode/mesh data set up.
    electrode_surfaces : list
        A list of surfaces used for the electrodes.

    Returns
    -------
    None
        Results are written to files and appended to the session object.
    """
    logger.info("simulation is running ...")
    tdcslist = S.poslists[0]

    # cond[100-1] = electrode rubber (added automatically)
    tdcslist.cond[500 - 1].name = "Central_electrode"
    tdcslist.cond[500 - 1].value = c["Electrode"]
    tdcslist.cond[100 - 1].value = c["ElecRubber"]
    for i in range(1, n_electrodes):
        tdcslist.cond[500 + i - 1].value = tdcslist.cond[500 - 1].value
        tdcslist.cond[500 + i - 1].name = "Peripheral_electrode%d" % (i)
        tdcslist.cond[100 + i - 1].value = tdcslist.cond[100 - 1].value
        tdcslist.cond[100 + i - 1].name = tdcslist.cond[100 - 1].name + str(i)

    tdcslist.cond[1 - 1].value = c["WM"]  # WM
    tdcslist.cond[2 - 1].value = c["GM"]  # GM
    tdcslist.cond[3 - 1].value = c["CSF"]  # CSF
    tdcslist.cond[7 - 1].value = c["Skin"]  # Skull (was swapped with skin)

    tdcslist.cond[6 - 1].value = c["Eyeballs"]  # eyeballs
    tdcslist.cond[5 - 1].value = c["CompactBone"]  # Skin  (was swapped with skull)
    tdcslist.cond[8 - 1].value = c["SpongyBone"]  # spongy bone
    tdcslist.cond[9 - 1].value = c["Blood"]
    tdcslist.cond[10 - 1].value = c["Muscle"]  # muscle

    filename = onamehead.split(".")[0] + "_TDCS_1"
    fn_simu = S.pathfem + '/' + filename
    tdcslist._prepare()
    mesh_elec = mesh_tools.read_msh(S.pathfem + '/' + S.fnamehead)

    cond = tdcslist.cond2elmdata(mesh_elec)

    start_time = time.perf_counter()

    logger.info('Start TDCS_neumann')

    def custom_tdcs_neumann(mesh, cond, currents, electrode_surface_tags):
        """
        Solve a tDCS electric potential using Neumann boundary conditions on electrodes.

        Parameters
        ----------
        mesh : Msh
            The Msh object containing the geometry.
        cond : ElementData
            An ElementData field with conductivity information.
        currents : list
            A list of currents corresponding to each electrode.
        electrode_surface_tags : list
            A list of surface tags where the boundary conditions apply.

        Returns
        -------
        NodeData
            A NodeData object named 'v' with the resulting electric potential.
        """
        assert len(electrode_surface_tags) == len(currents),\
            'Please define one current per electrode'
        assert np.isclose(np.sum(currents), 0.), 'Sum of currents must be zero'
        S = fem.TDCSFEMNeumann(mesh, cond, electrode_surface_tags[0], solver_options='pardiso')
        b = S.assemble_rhs(electrode_surface_tags[1:], currents[1:])
        v = S.solve(b)
        del S, b
        gc.collect()
        return mesh_io.NodeData(v, name='v', mesh=mesh)

    v = custom_tdcs_neumann(mesh_elec, cond, tdcslist.currents, np.unique(electrode_surfaces))
    # v = fem.tdcs_neumann(mesh_elec, cond, tdcslist.currents, np.unique(electrode_surfaces))

    logger.info(f"It took {time.perf_counter() - start_time: 0.2f} second(s) to complete.")

    # field calculation
    m = fem.calc_fields(v, tdcslist.postprocess, cond=cond)

    final_name = fn_simu + "_scalar.msh"
    m.write(final_name)
    tdcslist.fnamefem = final_name
    v = m.view(
        visible_tags=sim_struct._surf_preferences(m),
        visible_fields=sim_struct._field_preferences(tdcslist.postprocess))

    el_geo_fn = fn_simu + '_el_currents.geo'
    tdcslist._electrode_current_geo(m, el_geo_fn)
    v.add_merge(filename + "_el_currents.geo")
    v.add_view(ColormapNumber=10, ColormapAlpha=.5, Visible=1)
    v.write_opt(final_name)


def write_info(pathfem_modif):
    """
    Write simulation and positioning parameters to a .infofile.

    This function uses a global 'param' object (not shown in this snippet)
    to retrieve various simulation parameters and writes them to
    'param.infofile'.

    Parameters
    ----------
    pathfem_modif : pathlib.Path
        A path object where param.infofile is stored.

    Returns
    -------
    None
        Outputs text to a file.
    """
    infofile = open(str(pathfem_modif / "param.infofile"), 'w+')
    infofile.write('== Filenames:\n')
    infofile.write('onamehead = ' + param.onamehead + '\n')
    infofile.write('fnamehead = ' + param.fnamehead + '\n')
    infofile.write('pathfem = ' + param.pathfem + '\n')
    infofile.write('infofile = ' + param.infofile + '\n')
    infofile.write('\n\n')

    infofile.write('== Simulation Parameters:\n')
    infofile.write('n_electrodes = ' + str(param.n_electrodes) + '\n')
    infofile.write('currents = ' + str(param.currents) + '\n')
    infofile.write('names = ' + str(param.names) + '\n')
    infofile.write('theta = ' + str(param.theta) + '\n')
    infofile.write('fields = ' + param.fields + '\n')
    infofile.write('cond = ' + str(param.cond) + '\n')
    infofile.write('\n\n')

    infofile.write('== Positioning Parameters:\n')
    infofile.write('d_intElec = ' + str(param.d_intElec) + '\n')
    infofile.write('d_centerCompl = ' + str(param.d_centerCompl) + '\n')
    infofile.write('d_outerCompl = ' + str(param.d_outerCompl) + '\n')
    infofile.write('d_outerAct = ' + str(param.d_outerAct) + '\n')
    infofile.write('d_border = ' + str(param.d_border) + '\n')
    infofile.write('h_silicon = ' + str(param.h_silicon) + '\n')
    infofile.write('h_electrode = ' + str(param.h_electrode) + '\n')
    infofile.write('pos_centre = ' + str(param.pos_centre) + '\n')
    infofile.write('orientation = ' + str(param.orientation) + '\n')
    infofile.write('\n\n')

    infofile.close()


def distance(point1, point2):
    """
    Calculate the Euclidean distance between two 3D points.

    Parameters
    ----------
    point1 : tuple or list
        A tuple/list with (x, y, z) coordinates.
    point2 : tuple or list
        A tuple/list with (x, y, z) coordinates.

    Returns
    -------
    float
        The Euclidean distance between the two points.
    """
    x1, y1, z1 = point1
    x2, y2, z2 = point2
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def find_diagonals(nodes_coord):
    """
    Find two diagonal segments based on convex hull points.

    This function:
        - Computes the convex hull of the given node coordinates.
        - Finds two pairs of points that are the farthest apart.

    Parameters
    ----------
    nodes_coord : numpy.ndarray
        A NumPy array of shape (N, 3) representing node coordinates in 3D space.

    Returns
    -------
    list
        A list of two pairs of points (each pair is a list of two 3D coordinates),
        representing the longest diagonals found among the hull points.
    """
    diagonals = [[], []]

    hull = ConvexHull(nodes_coord)

    # Extract the points forming the hull
    hullpoints = nodes_coord[hull.vertices, :]

    for i in range(2):
        hdist = cdist(hullpoints, hullpoints, metric='euclidean')

        # Get the farthest apart points
        bestpair = np.unravel_index(hdist.argmax(), hdist.shape)

        # Print them
        logger.info(f"{[hullpoints[bestpair[0]], hullpoints[bestpair[1]]]}")

        diagonals[i] = [hullpoints[bestpair[0]], hullpoints[bestpair[1]]]

        hullpoints = np.delete(hullpoints, (bestpair[0]), axis=0)

    return (diagonals)


def find_corners(mesh):
    """
    Locate corners (diagonal endpoints) of an electrode placed on a mesh.

    This function:
        - Sets up a temporary SimNIBS session and places a rectangular electrode on the given mesh.
        - Extracts the electrode surface nodes, then identifies diagonal points via 'find_diagonals'.
        - Returns the diagonal corners and a modified mesh with the electrodes removed.

    Parameters
    ----------
    mesh : Msh
        A Msh object representing the main head mesh.

    Returns
    -------
    tuple
        A tuple containing:
        - The list of diagonals (pairs of far-apart points) from the electrode surface.
        - The mesh after removing the electrode volumes (tags [501, 502, 1501, 1502, 2101, 2102]).
    """
    start_time = time.time()

    # Initalize a session
    s = sim_struct.SESSION()
    # Name of head mesh
    s.fnamehead = onamehead
    # Output folder
    s.pathfem = 'rect_example_outputs/'

    xdir_centre, ydir_centre, zdir_centre = small_standard_positions(mesh)

    #  electrode placement for rect example

    # Initialize a tDCS simulation
    tdcslist = s.add_tdcslist()

    # Set currents
    tdcslist.currents = [-1e-3, 1e-3]

    # Initialize the cathode
    cathode = tdcslist.add_electrode()
    # Connect electrode to first channel (-1e-3 mA, cathode)
    cathode.channelnr = 1

    # Electrode dimension
    cathode.dimensions = [d_rect, d_rect]  # from new isolation design

    # Rectangular shape
    cathode.shape = 'rect'

    # 5mm thickness
    cathode.thickness = [h_electrode]

    # Electrode Position
    cathode.centre = pos_centre

    # Electrode direction
    cathode.pos_ydir = ydir_centre

    #  Add isolation

    isolation = tdcslist.add_electrode()
    # Assign it to the second channel
    isolation.channelnr = 2

    # Calculate set of vertices of EASEE isolation shape
    vertices = svg_to_nodes(isolation_shape, 0)

    # Isolation shape
    isolation.shape = 'custom'

    # Isolation vertices
    isolation.vertices = vertices

    # Isolation thickness
    isolation.thickness = [h_silicon]

    # Isolation position
    isolation.centre = pos_centre

    # Isolation pos_ydir
    isolation.pos_ydir = ydir_centre

    tdcslist.mesh = mesh
    mesh_core_elec, elec_surfaces = tdcslist._place_electrodes()

    mesh_rect_elec_surf = mesh_core_elec.crop_mesh([elec_surfaces[0]]) # type: ignore

    nodes_coord = mesh_rect_elec_surf.nodes.node_coord
    logger.info("--- %s seconds ---" % (time.time() - start_time))

    logger.info('--- Diagonals calculation ---')

    start_time = time.time()
    diagonals = find_diagonals(nodes_coord)

    logger.info("--- %s seconds ---" % (time.time() - start_time))

    return diagonals, remove_from_mesh(mesh_core_elec, [501, 502, 1501, 1502, 2101, 2102])


def remove_electrodes_volume_from_skin(electrodes_volume_mesh, skin_surf_vol_mesh):
    """
    Remove the volume occupied by electrodes from the skin volume mesh.

    This function:
        - Finds tetrahedra in the skin mesh that contain electrode nodes.
        - Deletes those tetrahedra to leave a "hole" where the electrodes are.

    Parameters
    ----------
    electrodes_volume_mesh : Msh
        A Msh object representing the electrode volumes.
    skin_surf_vol_mesh : Msh
        A Msh object representing the skin volume + surface.

    Returns
    -------
    Msh
        A new Msh object for the skin mesh with the electrode volumes removed.
    """
    b = skin_surf_vol_mesh.find_tetrahedron_with_points(electrodes_volume_mesh.nodes.node_coord)
    points_in_skin = b[0]
    points_in_skin1 = points_in_skin[points_in_skin != -1]
    points_in_skin2 = points_in_skin1 - 1

    mesh_skin1 = copy.deepcopy(skin_surf_vol_mesh)

    mesh_skin1.elm.node_number_list = np.delete(mesh_skin1.elm.node_number_list, points_in_skin2, axis=0)
    mesh_skin1.elm.elm_type = mesh_skin1.elm.elm_type[0:mesh_skin1.elm.node_number_list.shape[0]]
    mesh_skin1.elm.tag1 = mesh_skin1.elm.tag1[0:mesh_skin1.elm.node_number_list.shape[0]]
    mesh_skin1.elm.tag2 = mesh_skin1.elm.tag1

    mesh_skin1 = remove_disconnected_nodes(mesh_skin1)

    return mesh_skin1


def remove_disconnected_nodes(mesh):
    """
    Remove any nodes that are not connected to any elements in a mesh.

    This function:

    - Identifies nodes with zero adjacency.
    - Deletes them from the mesh and updates the element node numbering accordingly.

    Parameters
    ----------
    mesh : Msh
        A Msh object to be processed.

    Returns
    -------
    Msh
        The updated Msh object with disconnected nodes removed.
    """
    # Find and delete disconnected nodes
    sparse_matrix = mesh.elm.node_elm_adjacency()
    sparse_nodes_mean = sparse_matrix.mean(axis=1)
    disconnected_nodes_idx = np.where(sparse_nodes_mean == 0)[0][1:]  # indices of disconnected nodes

    # Remove disconnected nodes
    mesh.nodes.node_coord = np.delete(mesh.nodes.node_coord, disconnected_nodes_idx - 1, axis=0)

    # Fix element-node connection
    node_number_list_flatten = mesh.elm.node_number_list.flatten()
    node_number_list_flatten_copy = copy.deepcopy(node_number_list_flatten)

    for i in range(len(disconnected_nodes_idx)):
        node_number_list_flatten_copy[node_number_list_flatten > disconnected_nodes_idx[i]] -= 1

    node_number_list = np.reshape(node_number_list_flatten_copy, (len(node_number_list_flatten) // 4, 4))
    mesh.elm.node_number_list = node_number_list

    return mesh


def find_and_fix_nodes_for_change_new(mesh_skin_with_holes, electrodes_ref):
    """
    Align skin mesh nodes to match electrode coordinates within a tolerance.

    This function:

    - Creates a KDTree from the electrode node coordinates.
    - Finds skin mesh nodes within a certain tolerance to those electrode coordinates.
    - Replaces those skin node coordinates with the electrode coordinates, ensuring
      alignment between skin and electrode meshes.

    Parameters
    ----------
    mesh_skin_with_holes : Msh
        A Msh object for the skin mesh (with holes).
    electrodes_ref : Msh
        A Msh object whose node coordinates are used as the reference.

    Returns
    -------
    Msh
        The modified skin mesh with nodes aligned to electrode coordinates.
    """
    logger.info('Start')
    tolerance = 0.1

    elec_nodes = electrodes_ref.nodes.node_coord
    nodes_for_change_dict = dict()
    elec_nodes_rounded = np.round(elec_nodes, 4)
    skin_nodes_rounded = np.round(mesh_skin_with_holes.nodes.node_coord, 4)

    array1 = skin_nodes_rounded
    array2 = elec_nodes_rounded

    tree = KDTree(array2)
    distances, indices = tree.query(array1, distance_upper_bound=tolerance)

    indices1 = np.copy(indices)
    indices1[distances == np.inf] = -1

    nodes_for_change_dict = {}
    for i, idx in enumerate(indices1):
        if idx != -1:
            nodes_for_change_dict[idx] = i

    for key, value in nodes_for_change_dict.items():
        # change values of nodes
        mesh_skin_with_holes.nodes.node_coord[value] = electrodes_ref.nodes.node_coord[key]

    logger.info('Finish')

    return (mesh_skin_with_holes)


def volumes_subtraction(vol1_name: pathlib.Path, vol2_name: pathlib.Path, output_name: pathlib.Path):
    """
    Subtract one volumetric mesh from another, fix common geometry issues, and save the result.

    This function:
        - Loads two volumetric meshes from the paths given by 'vol1_name' and 'vol2_name'.
        - Performs a difference operation (A minus B) using mrmeshpy's Boolean tools.
        - Searches for (and logs) degenerate faces and self-intersections in the resulting mesh.
        - Attempts to fix self-intersections if any are found.
        - Saves the final mesh to 'output_name'.

    Parameters
    ----------
    vol1_name : pathlib.Path
        Path to the first volume/mesh (A).
    vol2_name : pathlib.Path
        Path to the second volume/mesh (B) to subtract from the first.
    output_name : pathlib.Path
        Path where the resulting mesh after subtraction is saved.

    Returns
    -------
    None
        The function writes the result to a file.
    """
    logger.info('Mesh loading:')
    try:
        meshA = mrmeshpy.loadMesh(mrmeshpy.Path(vol1_name))
        meshB = mrmeshpy.loadMesh(mrmeshpy.Path(vol2_name))
    except ValueError as e:
        logger.error(e)

    logger.info('Done!')
    logger.info('Subtraction:')

    diff = mrmeshpy.boolean(meshA, meshB, mrmeshpy.BooleanOperation.DifferenceAB)
    logger.info('Done!')

    diff_mesh = diff.mesh

    # Mesh geometry fix

    logger.info("Mesh geometry fix:")

    # Degenerate faces fix
    logger.info("Degenerate faces fix:")

    degenerate_faces_number = mrmeshpy.findDegenerateFaces(mrmeshpy.MeshPart(diff_mesh),
                                                           1.000e+04).count()  # criticalAspectRatio = 1.000e+04 as in the Web MeshInspector
    logger.info(f"Number of degenerate faces = {str(degenerate_faces_number)}")

    # if degenerate_faces_number > 0:
    #     decimate_settings = mrmeshpy.DecimateSettings()     # at the moment default settings seems to be OK

    #     # decimate_strategy = mrmeshpy.DecimateStrategy(0)    # 0 = MinimizeError, 1 = ShortestEdgeFirst
    #     # decimate_settings = mrmeshpy.DecimateSettings()
    #     # decimate_settings.maxDeletedFaces = 100
    #     # decimate_settings.maxDeletedVertices = 300
    #     # decimate_settings.maxEdgeLen = 5
    #     # decimate_settings.maxError = 0.1
    #     # decimate_settings.maxTriangleAspectRatio = 1.0e+4
    #     # decimate_settings.optimizeVertexPos = False
    #     # decimate_settings.packMesh = False
    #     # # decimate_settings.region = diff_mesh
    #     # decimate_settings.stabilizer = 0
    #     # decimate_settings.strategy = decimate_strategy
    #     # decimate_settings.touchBdVerts = False

    #     mrmeshpy.decimateMesh(diff_mesh, settings = decimate_settings)
    #     logger.info("Done!")


    # Self-intersecting faces fix
    logger.info("Self-intersecting faces fix:")

    self_intersecting_faces = mrmeshpy.findSelfCollidingTrianglesBS(mrmeshpy.MeshPart(diff_mesh))
    self_intersecting_faces_number = self_intersecting_faces.count()
    logger.info(f"Number of self-intersecting faces = {str(self_intersecting_faces_number)}")

    if self_intersecting_faces_number > 0:
        logger.info("Attempting to fix self-intersections")
        mrmeshpy.fixSelfIntersections(diff_mesh, voxelSize = 1.0)
    logger.info("Done!")


    # mrmeshpy.fixSelfIntersections(mesh: meshlib.mrmeshpy.Mesh, voxelSize: float)
    # mrmeshpy.relax(self_intersecting_faces)
    # a = mrmeshpy.MeshRelaxParams()
    # a.region = self_intersecting_faces

    mrmeshpy.saveMesh(diff_mesh, mrmeshpy.Path(output_name))


def create_elec_and_iso():
    """
    Create electrodes and isolation geometry, refine the skull mesh, and perform volume subtractions.

    This function performs a multi-step mesh manipulation pipeline to:
        1. Create a new output directory for the simulation.
        2. Locate and read the original head mesh.
        3. Separate the mesh into skin, skull, and the remaining tissues, applying tag changes if needed.
        4. Optionally refine the skull mesh if a refined version doesn't already exist.
        5. Calculate electrode positions using 'find_corners()', then place the electrodes with 'electrode_placement()'.
        6. Compute normals for electrodes and extrude both the electrode surfaces and isolation surfaces in Gmsh.
        7. Subtract volumes to remove isolation from the skin and electrodes from the isolation, and re-create volumes in Gmsh.
        8. Fix node positions to ensure consistent geometry between adjacent surfaces.
        9. Cleanup (delete) intermediate or unnecessary files.

    Returns
    -------
    pathlib.Path
        A pathlib.Path object corresponding to the newly created output directory
        that contains the final meshes.
    """
    start_time = time.time()

    # Simplified path creation
    i = 0
    while True:
        pathfem_modif = pathlib.Path(pathfem[:-2] + str(i))
        if pathfem_modif.exists():
            i += 1
            continue
        else:
            pathfem_modif.mkdir(exist_ok=True, parents=True)
            break

    # manipulate head model if declared in param.py
    meshname = onamehead
    original_mesh_path = None

    volume_dir = pathlib.Path(param.volume_path)
    for path in volume_dir.rglob(meshname):
        if path.is_file():
            original_mesh_path = path
            logger.info(f"Found {meshname} in {path}!")

    if original_mesh_path is None:
        logger.error(f"Unable to locate {meshname} file in data directory {volume_dir}.")
        raise FileNotFoundError(f"Unable to locate {meshname} file in {volume_dir}.")

    mesh = mesh_tools.read_msh(original_mesh_path)

    # mesh = mesh_tools.read_msh(requirements_path + meshname)

    # Extract skin surface and skull core
    mesh_skin_surf = mesh.crop_mesh([5, 1005])
    logger.info("Extracted skin surface")

    mesh_core = mesh.crop_mesh([7, 1007])
    logger.info("Extracted skull surface")

    mesh_without_skull_and_skin = mesh.remove_from_mesh([5, 1005, 7, 1007])
    mesh_without_skull_and_skin.write(str(pathfem_modif / "mesh_without_skull_and_skin.msh"))

    # Retag the mesh to adjest the element labels
    retag(mesh_core, 1007, 1005)
    retag(mesh_core, 7, 5)

    # Check if we already refined and saved skull using simnibs (decrease read time)
    mesh_file_path = pathfem_modif.parent / f"skull_surf_refined_{meshname}"

    if mesh_file_path.exists():
        mesh_core = mesh_tools.read_msh(mesh_file_path)
    else:
        mesh_core = refine(mesh_core, pathfem_modif.parent, f"skull_surf_refined_{meshname}")

    logger.info(f"Mesh preparation took {time.time() - start_time:.2f} seconds")

    # Electrode placement
    logger.info("Calculating peripheral electrodes centers...")
    diagonals, mesh_core = find_corners(mesh_core)
    peripheral_coord = np.array(
        [diagonals[0][0], diagonals[0][1], diagonals[1][0], diagonals[1][1]]).tolist()

    logger.info(f"Peripheral coordinates: {peripheral_coord}")
    S, mesh_core_elec, elec_surfaces = electrode_placement(mesh_core, pathfem_modif, peripheral_coord)

    mesh_core_elec.write(str(pathfem_modif / "skull_ref_with_elec_and_isolation.msh"))

    # Calculate normals for electrodes
    closest_normals = []
    for i in range(n_electrodes):
        try:
            mesh_elec_n = mesh_core_elec.crop_mesh([501 + i, 1501 + i, 2102 + i])
            mesh_elec_outsurf_n = mesh_get_outer_surface(mesh_elec_n, 1003)

            closest_point_n = mesh_elec_outsurf_n.nodes.find_closest_node(
                pos_centre if i == 0 else peripheral_coord[i - 1], return_index=True
            )

            all_nodes_normals_n = mesh_elec_outsurf_n.nodes_normals(mesh_elec_outsurf_n.elm.elm_number)
            closest_normal_n = all_nodes_normals_n.value[closest_point_n[-1]]
            closest_normal_n = np.expand_dims(closest_normal_n if closest_normal_n[0] >= 0 else -closest_normal_n, axis=0)
            closest_normals.append(closest_normal_n)
        except Exception as e:
            logger.error(f"Failed to calculate normal for electrode {i}: {e}")
            break

    closest_normals = np.vstack(closest_normals)
    logger.info(f"Calculated closest normals: {closest_normals}")

    # isolation and electrodes extrusion by gmsh

    logger.info("Isolation extrusion by gmsh")

    # isolation extrusion
    isolation_top_surf = mesh_core_elec.crop_mesh([1506])
    isolation_top_surf.write(str(pathfem_modif / "mesh_isolation_1506.msh"))

    gmsh.initialize()

    gmsh.open(str(pathfem_modif / "mesh_isolation_1506.msh"))

    extrusion_vect = closest_normals[0]
    vector_len = math.sqrt(closest_normals[0][0] ** 2 + closest_normals[0][1] ** 2 + closest_normals[0][2] ** 2)

    total_extrusion_vec_length = h_silicon + 1

    extrusion_vect = closest_normals[0] * (total_extrusion_vec_length / vector_len)

    gmsh.model.geo.extrude([(2, 1506)], extrusion_vect[0], extrusion_vect[1], extrusion_vect[2],
                           [int(5 * total_extrusion_vec_length)])

    gmsh.model.geo.synchronize()

    gmsh.model.addPhysicalGroup(3, [1], 506)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(pathfem_modif / "isolation_gmsh_extruded_with_surf.msh2"))


    isolation = msh2_to_simnibs(str(pathfem_modif / "isolation_gmsh_extruded_with_surf.msh2"))
    isolation.elm.tag2 = isolation.elm.tag1
    isolation_volume = isolation.crop_mesh([506])
    isolation_volume.write(str(pathfem_modif / "isolation_gmsh_extruded_vol.msh"))
    isolation_extruded_outsurf = mesh_get_outer_surface(isolation_volume, 1004)
    isolation_extruded_outsurf.write(str(pathfem_modif / "isolation_extruded_outsurf.msh"))

    gmsh.open(str(pathfem_modif / "isolation_extruded_outsurf.msh"))
    # gmsh.option.setNumber("Mesh.Binary", 0) # ASCII STL format (use 1 for binary STL)

    # Save the mesh as STL
    gmsh.write(str(pathfem_modif / "isolation_extruded_outsurf.stl"))

    logger.info("Done!")

    # electrodes extrusion
    logger.info("Electrodes extrusion by gmsh")

    for i in range(n_electrodes):

        logger.info(f"Electrode {i + 1} extrusion by gmsh")

        electrode_top_surf = mesh_core_elec.crop_mesh([1501 + i])
        electrode_top_surf.write(str(pathfem_modif / f"mesh_electrode_150{i+1}.msh"))

        gmsh.open(str(pathfem_modif / f"mesh_electrode_150{i+1}.msh"))

        extrusion_vect = closest_normals[i]
        vector_len = math.sqrt(closest_normals[i][0] ** 2 + closest_normals[i][1] ** 2 + closest_normals[i][2] ** 2)

        total_extrusion_vec_length = h_silicon + 1
        extrusion_vect = closest_normals[i] * (total_extrusion_vec_length / vector_len)

        gmsh.model.geo.extrude([(2, 1501 + i)], extrusion_vect[0], extrusion_vect[1], extrusion_vect[2],
                               [int(5 * total_extrusion_vec_length)])

        gmsh.model.geo.synchronize()

        gmsh.model.addPhysicalGroup(3, [1], 501 + i)
        gmsh.model.mesh.generate(3)
        gmsh.write(str(pathfem_modif / f"electrode_{str(1501 + i)}_Gmsh_extruded_with_surf.msh2"))

        electrode = msh2_to_simnibs(str(pathfem_modif / f"electrode_{str(1501 + i)}_Gmsh_extruded_with_surf.msh2"))
        electrode.elm.tag2 = electrode.elm.tag1
        electrode_volume = electrode.crop_mesh([501 + i])
        electrode_volume.write(str(pathfem_modif / f"electrode_{str(1501 + i)}_Gmsh_extruded_vol.msh2"))
        electrode_outsurf = mesh_get_outer_surface(electrode_volume, 1501 + i)
        electrode_outsurf.elm.tag2 = electrode_outsurf.elm.tag1
        electrode_outsurf.write(str(pathfem_modif / f"electrode_{str(1501 + i)}_Gmsh_extruded_outsurf.msh"))

        if i == 0:
            electrodes = electrode_outsurf
        else:
            electrodes = join_and_connect(electrodes, electrode_outsurf)

        logger.info('Done!')

    electrodes.write(str(pathfem_modif / "electrodes_Gmsh_extruded_outsurf.msh"))

    gmsh.open(str(pathfem_modif / "electrodes_Gmsh_extruded_outsurf.msh"))
    # gmsh.option.setNumber("Mesh.Binary", 0) # 0 for ASCII STL, 1 for binary STL

    # Save the mesh in STL format
    gmsh.write(str(pathfem_modif / "electrodes_Gmsh_extruded_outsurf.stl"))

    logger.info("Done!")

    # volumes subtraction

    logger.info("Volumes subtraction")

    logger.info("Skin-isolation subtraction")

    # skin outsrf creation
    skin = mesh_skin_surf.crop_mesh([5])
    skin_outsrf = mesh_get_outer_surface(skin, 1004)
    skin_outsrf.write(str(pathfem_modif / "skin_outsrf.msh"))

    gmsh.open(str(pathfem_modif / "skin_outsrf.msh"))
    # gmsh.option.setNumber("Mesh.Binary", 0) # 0 for ASCII STL, 1 for binary STL

    # Save the mesh in STL format
    gmsh.write(str(pathfem_modif / "skin_outsrf.stl"))

    # skin-isolation subtraction

    # gmsh extruded isolation
    volumes_subtraction(
        pathfem_modif / "skin_outsrf.stl",
        pathfem_modif / "isolation_extruded_outsurf.stl",
        pathfem_modif / "skin_without_Gmsh_isolation.stl"
    )

    # skin volume creation
    gmsh.open(str(pathfem_modif / "skin_without_Gmsh_isolation.stl"))

    gmsh.model.mesh.setSize(gmsh.model.getEntities(0), 5)
    gmsh.model.geo.addSurfaceLoop([1], 1005)
    gmsh.model.geo.addVolume([1005], 1)
    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(3)
    gmsh.model.addPhysicalGroup(2, [1], 1005)
    gmsh.model.addPhysicalGroup(3, [1], 5)
    gmsh.write(str(pathfem_modif / "skin_without_isolation_vol_surf.msh2"))

    skin = msh2_to_simnibs(str(pathfem_modif / "skin_without_isolation_vol_surf.msh2"))
    skin.elm.tag2 = skin.elm.tag1
    skin_volume = skin.crop_mesh([5])
    skin_volume.write(str(pathfem_modif / "skin_without_isolation_vol.msh"))
    logger.info('Done!')

    logger.info("Isolation-electrodes subtraction")

    # isolation outsrf creation
    isolation = mesh_core_elec.crop_mesh([506])
    isolation_outsrf = mesh_get_outer_surface(isolation, 1004)
    isolation_outsrf.write(str(pathfem_modif / "isolation_outsrf.msh"))

    gmsh.open(str(pathfem_modif / "isolation_outsrf.msh"))
    # gmsh.option.setNumber("Mesh.Binary", 0) # 0 for ASCII STL, 1 for binary STL

    # Save the mesh in STL format
    gmsh.write(str(pathfem_modif / "isolation_outsrf.stl"))

    # isolation-electrodes subtraction

    # gmsh extruded electrodes
    volumes_subtraction(
        pathfem_modif / "isolation_outsrf.stl",
        pathfem_modif / "electrodes_Gmsh_extruded_outsurf.stl",
        pathfem_modif / "isolation_without_electrodes.stl"
    )

    # isolation volume creation

    gmsh.open(str(pathfem_modif / "isolation_without_electrodes.stl"))
    gmsh.model.mesh.setSize(gmsh.model.getEntities(0), 5)
    gmsh.model.geo.addSurfaceLoop([1], 1506)
    gmsh.model.geo.addVolume([1506], 1)
    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(3)
    gmsh.model.addPhysicalGroup(2, [1], 1506)
    gmsh.model.addPhysicalGroup(3, [1], 506)
    gmsh.write(str(pathfem_modif / "isolation_without_electrodes_vol_surf.msh2"))

    isolation = msh2_to_simnibs(str(pathfem_modif / "isolation_without_electrodes_vol_surf.msh2"))
    isolation.elm.tag2 = isolation.elm.tag1
    isolation_volume = isolation.crop_mesh([506])
    isolation_volume.write(str(pathfem_modif / "isolation_without_electrodes_vol.msh"))

    logger.info('Done!')
    gmsh.finalize()

    # meshes fix

    logger.info("Meshes fix")

    # iso fix with electrodes and skull
    logger.info("Isolation fix with skull and electrodes")
    iso = mesh_tools.read_msh(str(pathfem_modif / "isolation_without_electrodes_vol.msh"))
    skull_and_elec = copy.deepcopy(mesh_core_elec)
    skull_and_elec = skull_and_elec.remove_from_mesh([506, 1506, 2106])
    new_iso = find_and_fix_nodes_for_change_new(iso, skull_and_elec)
    new_iso.write(str(pathfem_modif / "isolation_with_hole_fixed_for_electrodes_and_skull.msh"))
    logger.info("Done!")

    # skin fix with all tissues
    logger.info("Skin fix with all tissues, isolation and electrodes")
    skin = mesh_tools.read_msh(str(pathfem_modif / "skin_without_isolation_vol.msh"))
    mesh_without_skin_and_skull = mesh_tools.read_msh(str(pathfem_modif / "mesh_without_skull_and_skin.msh"))
    skull = mesh_core_elec.crop_mesh([5, 1005])
    retag(skull, 5, 7)
    retag(skull, 1005, 1007)
    skull.write(str(pathfem_modif / "skull_from_simulation.msh"))
    isolation = mesh_tools.read_msh(str(pathfem_modif / "isolation_with_hole_fixed_for_electrodes_and_skull.msh"))
    elec = mesh_core_elec.crop_mesh(
        [501, 502, 503, 504, 505, 1501, 1502, 1503, 1504, 1505, 2101, 2102, 2103, 2104, 2105])
    everything_except_skin = join_and_connect(mesh_without_skin_and_skull, skull)
    everything_except_skin = join_and_connect(everything_except_skin, isolation)
    everything_except_skin = join_and_connect(everything_except_skin, elec)

    new_skin = find_and_fix_nodes_for_change_new(skin, everything_except_skin)
    new_skin.write(str(pathfem_modif / "mesh_skin_with_hole_fixed_for_everything.msh"))

    logger.info("Done!")

    # List of files to keep
    files_to_keep = {
        "mesh_without_skull_and_skin.msh",
        "skull_ref_with_elec_and_isolation.msh",
        "mesh_skin_with_hole_fixed_for_everything.msh",
        "isolation_with_hole_fixed_for_electrodes_and_skull.msh",
    }
    file_list = list(pathfem_modif.glob("*.*"))
    # Iterate over all files in the directory and remove the ones not in files_to_keep
    for file_path in file_list:
        if file_path.name not in files_to_keep:
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error while deleting file: {file_path}, Error: {str(e)}")

    logger.info("================================================================================")
    logger.info("DELETING FILES:")
    logger.info(f"{[file.as_posix() for file in file_list]}")
    logger.info("================================================================================")

    logger.info(f"Preparation took {time.time() - start_time} seconds")

    return pathfem_modif
