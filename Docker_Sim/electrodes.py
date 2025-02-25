

import logging
from math import cos, radians, sin
from typing import Tuple, cast

import numpy as np
import param
from simnibs import sim_struct
from simnibs.mesh_tools.mesh_io import Msh
from svg_to_nodes import svg_to_nodes

logger = logging.getLogger("planningtool")


def small_standard_positions(mesh):
    """
    Determine orientation vectors (xdir, ydir, zdir) for silicone pad placement on the skull surface.

    This function:
        - Finds the closest node on the skull mesh to a predefined `param.pos_centre`.
        - Retrieves the surface normal at that point to define the z-direction.
        - Computes xdir by taking the cross product of zdir and a user-defined orientation vector (ydir).
        - Rotates ydir around zdir based on an angle `param.theta` using Rodrigues' rotation formula.

    Parameters
    ----------
    mesh : Msh
        Mesh object from which to extract the skull region (ID 1005).

    Returns
    -------
    tuple of ndarray
        A tuple (xdir_centre, ydir_centre, zdir_centre) representing the orientation vectors for the silicone pad.
    """
    # determine xdir, ydir and zdir for silicone pad and calculate electrode positions
    # xdir, ydir and zdir are LEFT HANDED, contrary to mesh coordinates

    pos_centre = np.array(param.pos_centre)
    ydir_centre = np.array(param.orientation)

    # get closest point on skull and local normals for planning electrode placement
    # skull was retagged to skin
    mesh_skull = mesh.crop_mesh(1005)
    [pos_centre_surface, index] = mesh_skull.nodes.find_closest_node(
        pos_centre, return_index=True
    )
    ptnormals = mesh_skull.nodes_normals()
    zdir_centre = ptnormals.value[index, :]

    xdir_centre = np.cross(
        zdir_centre, ydir_centre
    )  # cross product to assert linear dependency and to rotate ydir_centre
    assert np.any(
        xdir_centre != 0
    ), "ERROR: Linear dependency while placing pad. Choose a different param.orientation vector."

    # rotate ydir_centre around zdir_centre to rotate silicone pad
    theta = param.theta
    ydir_centre = (
        ydir_centre * cos(radians(theta))
        + xdir_centre * sin(radians(theta))
        + zdir_centre * np.dot(zdir_centre, ydir_centre) * (1 - cos(radians(theta)))
    )  # rodrigues rotation

    return xdir_centre, ydir_centre, zdir_centre


def electrode_placement(mesh, pathfem_modif, peripheral_coord=[]) -> Tuple[sim_struct.SESSION, Msh, list]:
    """
    Set up electrode placement and generate a simulation session for tDCS in SimNIBS.

    This function:
        - Creates a SimNIBS session (`sim_struct.SESSION`), assigns fields and currents.
        - Defines electrode properties (dimensions, thickness, etc.) and places them on the mesh.
        - Optionally uses peripheral coordinates if provided, otherwise calculates electrode center positions using `small_standard_positions`.
        - Adds an isolation shape from an SVG file for the silicone pad.

    Parameters
    ----------
    mesh : Msh
        A mesh object representing the head model.
    pathfem_modif : str
        A file path or identifier for the FEM mesh output.
    peripheral_coord : list, optional
        A list of additional electrode center coordinates for peripheral electrodes.

    Returns
    -------
    tuple
        - SimNIBS SESSION object (`S`).
        - Modified Msh object (`mesh_elec`) with electrodes placed.
        - List of surfaces (`elec_surfaces`) corresponding to electrodes.
    """
    S = sim_struct.SESSION()
    S.pathfem = str(pathfem_modif)
    S.fields = param.fields

    tdcslist = S.add_tdcslist()
    tdcslist.currents = np.array(param.currents)

    # define electrodes (first center one and then lateral ones) and placement (by polar coordinates)
    elec_names = param.names
    if peripheral_coord != []:
        pos_centre = np.array(param.pos_centre)
        mesh_skull = mesh.crop_mesh(1005)
        [pos_centre_surface, index] = mesh_skull.nodes.find_closest_node(
            pos_centre, return_index=True
        )
        elec_centres = [pos_centre_surface] + peripheral_coord
    else:
        xdir_centre, ydir_centre, zdir_centre = small_standard_positions(mesh)

    for i in range(param.n_electrodes):
        elec = tdcslist.add_electrode()
        elec.name = elec_names[i]
        elec.channelnr = i + 1
        elec.definition = "plane"
        elec.centre = elec_centres[i]
        elec.shape = "ellipse"
        elec.thickness = [param.h_electrode]
        if i == 0:
            elec.dimensions = [param.d_centerAct, param.d_centerAct]
        else:
            elec.dimensions = [param.d_outerAct, param.d_outerAct]

    # cond[100-1] = electrode rubber (added automatically)
    tdcslist.cond[500 - 1].name = "Central_electrode"
    tdcslist.cond[500 - 1].value = param.cond["Electrode"]
    tdcslist.cond[100 - 1].value = param.cond["ElecRubber"]
    for i in range(1, param.n_electrodes):
        tdcslist.cond[500 + i - 1].value = tdcslist.cond[500 - 1].value
        tdcslist.cond[500 + i - 1].name = "Peripheral_electrode%d" % (i)
        tdcslist.cond[100 + i - 1].value = tdcslist.cond[100 - 1].value
        tdcslist.cond[100 + i - 1].name = str(tdcslist.cond[100 - 1].name) + str(i)

    # Add isolation
    s_pad = tdcslist.add_electrode()

    # Assign it to the last channel
    s_pad.channelnr = param.n_electrodes + 1
    s_pad.name = "Silicon Pad"

    # Calculate set of vertices of EASEE isolation shape
    vertices = svg_to_nodes(param.isolation_shape, 0)

    # Isolation shape
    s_pad.definition = "plane"
    s_pad.shape = "custom"

    # Isolation vertices
    s_pad.vertices = vertices

    # Isolation thickness
    s_pad.thickness = [param.h_silicon]

    # Isolation position
    s_pad.centre = pos_centre_surface

    xdir_centre, ydir_centre, zdir_centre = small_standard_positions(mesh)

    # Isolation pos_ydir
    s_pad.pos_ydir = ydir_centre

    tdcslist.mesh = mesh
    mesh_elec, elec_surfaces = cast(Tuple[Msh, list], tdcslist._place_electrodes())

    return S, mesh_elec, elec_surfaces
