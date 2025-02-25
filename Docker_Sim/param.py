# !!!Parameters to change by user !!!
import os

# ----------------------------------------------------------------------
# File and Path Configurations
# ----------------------------------------------------------------------

# Original mesh name (must be inside the main folder containing simulation.py)
# onamehead = "ernie_my.msh"
onamehead = os.environ["MESH_NAME"] + ".msh"

# Environment variables for paths
code_path = os.environ["PYTHONPATH"]
volume_path = os.environ["VOLUME_PATH"]
ensemble_name = os.environ["ENSEMBLE_NAME"]
electrode_name = os.environ["ELECTRODE_NAME"]

# # Path to requirements folder (derived from volume_path)
# requirements_path = f"{volume_path}/requirements/"

# Edited headmodel filename (head model with implanted electrodes and isolation, without simulation results)
fnamehead = "edited_mesh.msh"

# Simulation output directory path (must end with a "/")
# Format: folder_contains_main.py/results/original_mesh_name/Simulation №/
pathfem = f"{volume_path}/{ensemble_name}/{electrode_name}/results/{onamehead[:-4]}/Simulation_n/"

# Info file will be saved in pathfem
infofile = "data.info"

# Filename of isolation model (must be inside the main folder containing simulation.py)
isolation_shape = f"{code_path}/Docker_Sim/isolation_design_ver_1.svg"

# ----------------------------------------------------------------------
# Electrode Specifications
# ----------------------------------------------------------------------

# Number of electrodes
n_electrodes = 5

# Currents for the electrodes
# The current on the central electrode should equal the negative total of the peripheral electrodes
currents = [0.001, -0.00025, -0.00025, -0.00025, -0.00025]

# Names of the electrodes
names = ["center", "lateral_1", "lateral_2", "lateral_3", "lateral_4"]

# Center position of the central electrode (from environment variables)
pos_centre = [
    float(os.environ.get("ELECTRODE_POSITION_X", "")), # "0" for documentation builds, "" for running
    float(os.environ.get("ELECTRODE_POSITION_Y", "")),
    float(os.environ.get("ELECTRODE_POSITION_Z", ""))
]

# Orientation for pad (standard values: [0, 0, 100])
orientation = [0, 0, 100]

# Rotation angle (theta) for the pad and electrodes (clockwise rotation)
theta = 45

# Fields to be simulated (choose from v, e, E, j, J)
fields = "veE"

# ----------------------------------------------------------------------
# Material and Geometric Properties
# ----------------------------------------------------------------------

# Silicon pad height [mm]
h_silicon = 1

# Electrode height [mm]
h_electrode = 0.120

# Conductivities [S/m] for different tissues and materials
cond = {
    "WM": 0.3746,                   # Whole brain weighted average
    "GM": 0.3746,                   # Whole brain weighted average
    "CSF": 1.71,                    # Cerebrospinal fluid weighted average
    "CompactBone": 0.0046,          # Skull compact bone weighted average
    "SpongyBone": 0.0497,           # Skull spongy bone weighted average
    "Skin": 0.4137,                 # Skin weighted average
    "Eyeballs": 0.5,                # Eyeball conductivity
    "Blood": 0.5737,                # Blood conductivity
    "Muscle": 0.3243,               # Muscle conductivity
    "ElecRubber": 0.000001,         # Electrode rubber isolation (cannot be zero)
    "Electrode": 9.5 * (10 ** 6)    # Platinum electrode conductivity
}

# ----------------------------------------------------------------------
# Electrode Design (Do not modify unless necessary)
# ----------------------------------------------------------------------

# Orientation angle (phi) between the lateral electrodes and the central one [degrees]
phi = 45

# Distance between the central and lateral electrode centers [mm] (from .svg isolation model)
d_intElec = 23

# Distance of complete central electrode [mm]
d_centerCompl = 20

# Active size of the central electrode (diameter along x and y axis) [mm]
d_centerAct = 15

# Complete lateral electrode size [mm] (same as central electrode complete size)
d_outerCompl = 13

# Active lateral electrode size [mm] (same as central electrode active size)
d_outerAct = 10

# Silicon pad extension beyond electrode border [mm]
d_border = 6  # For new electrode design (EASEE)

# Side length of the square inscribed in the circle (from center of central to peripheral electrode) [mm]
d_rect = 32.5