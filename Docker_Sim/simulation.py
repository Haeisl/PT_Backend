import glob
import logging
import os
import time

import functions as f
import numpy as np
from param import (
    currents,
    d_centerAct,
    d_outerAct,
    fields,
    fnamehead,
    h_electrode,
    n_electrodes,
    names,
)
from simnibs import mesh_tools, sim_struct

logger = logging.getLogger("planningtool")
start_time = time.time()
current_path = os.path.abspath(os.getcwd())


def run_simulation(pathfem_modif):
    """
    Assemble the head model from multiple mesh files, place electrodes, and run a tDCS simulation.

    This function:
        1. Loads partial meshes (skin, skull, isolation, electrodes) from files in `pathfem_modif`.
        2. Joins and connects them into a single Msh object.
        3. Retags certain parts to match simulation requirements for SimNIBS.
        4. Creates a SimNIBS SESSION object, sets up electrodes, and calls the solver.
        5. Cleans up intermediate files, leaving only key outputs.

    Parameters
    ----------
    pathfem_modif : pathlib.Path
        A path object indicating where the mesh files and output should be read/written.

    Returns
    -------
    None
        The function writes simulation outputs to files in `pathfem_modif`.
    """
    logger.info("Assembling head model:")

    mesh_without_skin_and_skull = mesh_tools.read_msh(str(pathfem_modif / "mesh_without_skull_and_skin.msh"))

    skull_ref_with_elec_and_isolation = mesh_tools.read_msh(str(pathfem_modif / "skull_ref_with_elec_and_isolation.msh"))

    skull = skull_ref_with_elec_and_isolation.crop_mesh([5, 1005])
    f.retag(skull, 5, 7)
    f.retag(skull, 1005, 1007)

    # subtracted skin
    skin = mesh_tools.read_msh(str(pathfem_modif / "mesh_skin_with_hole_fixed_for_everything.msh"))
    skin.elm.tag2 = skin.elm.tag1

    elec = skull_ref_with_elec_and_isolation.crop_mesh(
        [501, 502, 503, 504, 505, 1501, 1502, 1503, 1504, 1505, 2101, 2102, 2103, 2104, 2105])

    # subtracted isolation
    isolation = mesh_tools.read_msh(str(pathfem_modif / "isolation_with_hole_fixed_for_electrodes_and_skull.msh"))
    isolation.elm.tag2 = isolation.elm.tag1
    isolation.reconstruct_unique_surface()

    mesh_stacked = f.join_and_connect(mesh_without_skin_and_skull, skull)
    mesh_stacked = f.join_and_connect(mesh_stacked, isolation)
    mesh_stacked = f.join_and_connect(mesh_stacked, elec)
    mesh_stacked = f.join_and_connect(mesh_stacked, skin)
    logger.info("Done!")

    # Checking shared nodes
    logger.info("Checking shared nodes:")
    tag_pairs = [
        (5, 7, "skin_skull"),
        (5, 3, "skin_csf"),
        (5, 6, "skin_eyes"),
        (5, 506, "skin_iso"),
        (506, 7, "iso_skull"),
        (506, 501, "iso_elec1"),
        (506, 502, "iso_elec2"),
        (506, 503, "iso_elec3"),
        (506, 504, "iso_elec4"),
        (506, 505, "iso_elec5"),
        (501, 7, "skull_elec1"),
        (502, 7, "skull_elec2"),
        (503, 7, "skull_elec3"),
        (504, 7, "skull_elec4"),
        (505, 7, "skull_elec5"),
    ]

    # Loop through each pair and log the results
    for tag1, tag2, label in tag_pairs:
        shared_nodes = mesh_stacked.find_shared_nodes([tag1, tag2])
        count_shared_nodes = len(shared_nodes) if shared_nodes is not None else 0
        logger.info(f"shared_nodes_{label} = {count_shared_nodes}")

    # Starting simulation
    logger.info("Starting simulation")
    S = sim_struct.SESSION()
    S.pathfem = str(pathfem_modif)
    S.fields = fields

    tdcslist = S.add_tdcslist()
    tdcslist.currents = np.array(currents)

    elec_names = names

    # pre-defined for one electrodes position just to test!!!
    elec_centres = [[-58.90757978, -7.15420753, 60.45319494],
                    [-59.01373406078079, 15.216413733068805, 58.689740352466536],
                    [-55.40858409952824, -29.881348421700686, 60.11295351094711],
                    [-43.33297514258787, -5.621862902615938, 77.28400176854188],
                    [-66.49744938552507, -8.660316015302419, 38.48076093271303]]

    # elec_centres = [[x * 10 for x in sublist] for sublist in elec_centres]

    for i in range(n_electrodes):
        elec = tdcslist.add_electrode()
        elec.name = elec_names[i]
        elec.channelnr = i + 1
        elec.definition = 'plane'
        elec.centre = elec_centres[i]
        elec.shape = 'ellipse'
        if i == 0:
            elec.dimensions = [d_centerAct, d_centerAct]
            elec.thickness = [h_electrode]
        else:
            elec.dimensions = [d_outerAct, d_outerAct]
            elec.thickness = [h_electrode]

            # pre-defined!!!!
    elec_surfaces = [2101, 2102, 2103, 2104, 2105]

    S.poslists[0].currents = S.poslists[0].currents[:n_electrodes]
    S.poslists[0].electrode = S.poslists[0].electrode[:n_electrodes]
    elec_surfaces = elec_surfaces[:n_electrodes]

    mesh_core_elec2 = mesh_stacked

    # skull as skin , skin as skull, isolation as Electrode Rubber
    f.retag(mesh_core_elec2, 1005, 1004)  # skin to empty tag
    f.retag(mesh_core_elec2, 5, 4)  # skin to empty tag
    f.retag(mesh_core_elec2, 1007, 1005)  # skull to skin
    f.retag(mesh_core_elec2, 7, 5)  # skull to skin
    f.retag(mesh_core_elec2, 1004, 1007)  # skin to skull
    f.retag(mesh_core_elec2, 4, 7)  # skin to skull
    f.retag(mesh_core_elec2, 1506, 1004)  # isolation to ElecRubber
    f.retag(mesh_core_elec2, 506, 100)  # isolation to ElecRubber

    # export edited mesh and load
    mesh_core_elec2.write(str(pathfem_modif / fnamehead))

    S.fnamehead = fnamehead

    f.run_simulation(S, elec_surfaces)

    # Remove Unnecessary files :

    fileList = glob.glob(str(pathfem_modif) + "/*.*")

    # Iterate over the list of filepaths & remove each file.
    for filePath in fileList:
        if "TDCS_1" not in filePath and "edited_mesh.msh" not in filePath:
            try:
                os.remove(filePath)
            except Exception as e:
                logger.info(f"Error while deleting file {filePath}, Error: {str(e)}")

    logger.info("--- %s seconds ---" % (time.time() - start_time))


def simulate():
    """
    Top-level function to create electrodes, isolation, and run a tDCS simulation.

    This function:
        1. Calls create_elec_and_iso() from the `functions` module to prepare meshes and isolation geometry, returning the path to the modified directory.
        2. Calls run_simulation() to assemble the final mesh, place electrodes, and run the tDCS simulation.
        3. Writes an info file summarizing the simulation parameters via write_info().

    Returns
    -------
    None
        Results are written to files in the path returned by create_elec_and_iso().
    """
    pathfem_modif = f.create_elec_and_iso()
    run_simulation(pathfem_modif)
    f.write_info(pathfem_modif)

    logger.info("--- %s seconds in total ---" % (time.time() - start_time))
