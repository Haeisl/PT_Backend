"""
Orchestrate the setup and execution of SimNIBS simulations within Docker.

Notes
-----
This script:
    - Parses command-line arguments for patient/config/ROI info.
    - Validates necessary files (electrode positions, ROI data).
    - Loads simulation settings from an .ini file.
    - Spawns Docker containers to run simulations concurrently for each electrode.
    - Performs post-processing steps (mapping simulations to ROI, generating 3D data, validation).
"""


import argparse
import configparser
import json
import subprocess
import sys
import time

from process_simulations.process_simulation_output import (
    collect_validation_results_for_roi,
    convert_to_3d,
    map_simulation_to_roi,
    process_simulation_output,
)
from process_simulations.validate_simulation_output import (
    collect_validation_results
)
from utils import DATABASE_PATHS, SIMULATION_BASE, set_mesh_name, DATA_PATH


def parse_arguments():
    """
    Parse command-line arguments for patient, config, and ROI IDs.

    Returns
    -------
    argparse.Namespace
        An object containing PatientID, ConfigID, and ROIID (all required),
        or exits if any are missing.
    """
    sentinel = object()
    argument_parser = argparse.ArgumentParser(
        description="Run an ensemble of customized SimNIBS simulations using Docker."
    )

    argument_parser.add_argument(
        "--PatientID", type=str, default=sentinel,
        help="ID of the patient (typically set in the frontend)"
    )
    argument_parser.add_argument(
        "--ConfigID", type=str, default=sentinel,
        help=("Configuration ID, sometimes also called Ensemble name"
        "(typically set in the frontend)")
    )
    argument_parser.add_argument(
        "--ROIID", type=str, default=sentinel,
        help="Region of interest (ROI) ID (typically set in the frontend)"
    )
    args = argument_parser.parse_args()
    args_dict = vars(args)
    required_args = ["PatientID", "ConfigID", "ROIID"]

    for arg_name, arg_value in args_dict.items():
        if arg_value is sentinel and arg_name in required_args:
            print(f"Error: received no value for '--{arg_name}', exiting")
            sys.exit(1)

    return args


def load_config():
    """
    Load configuration settings from a local config.ini file.

    Returns
    -------
    configparser.ConfigParser
        An object with the loaded settings.
    """
    config = configparser.ConfigParser()
    config.read("config.ini")

    return config


def get_settings(config, args):
    """
    Retrieve and set the simulation settings from config.ini and command-line args.

    This function extracts values such as max_containers, image_name, and mesh_name
    from the config. If any are set to "default", it uses fallback values.

    Parameters
    ----------
    config : configparser.ConfigParser
        An instance with loaded config.ini data.
    args : argparse.Namespace
        An object containing command-line arguments.

    Returns
    -------
    tuple
        A tuple (max_containers, image_name, mesh_name).
    """
    max_containers = config["Settings"]["max_containers"]
    image_name = config["Settings"]["image_name"]
    mesh_name = config["Settings"]["mesh_name"]

    max_containers = 1 if max_containers == "default" else int(max_containers)
    image_name = "simnibs_simulation:latest" if image_name == "default" else image_name
    mesh_name = args.PatientID if mesh_name == "default" else mesh_name

    set_mesh_name(mesh_name)
    return max_containers, image_name, mesh_name


def validate_files(args):
    """
    Validate the existence of required files and directories for the simulation.

    This checks:
    - electrode_positions_<ConfigID>.json in electrode directory
    - ROI file in the roi directory
    - The SIMULATION_BASE code path

    Parameters
    ----------
    args : argparse.Namespace
        An object with PatientID, ConfigID, and ROIID.

    Returns
    -------
    tuple
        A tuple (config_file_path, roi_file_path, code_path) referring to the
        validated file paths and directories.

    Raises
    ------
    SystemExit
        Exits with code 1 if any required file/path is missing.
    """
    config_file_path = DATABASE_PATHS["electrode"] / str(args.PatientID) / f"electrode_positions_{args.ConfigID}.json"
    roi_file_path = DATABASE_PATHS["roi"] / str(args.PatientID) / f"{args.ROIID}_roi_bounds.json"
    code_path = SIMULATION_BASE
    if not config_file_path.exists():
        print(f"Error: File {config_file_path.as_posix()} does not exist. Check Patient and Config IDs.")
        sys.exit(1)

    if not code_path.exists():
        print(f"Error: Unable to find subdirectory {code_path.as_posix()}.")
        sys.exit(1)

    if not roi_file_path.exists():
        print(f"Error: File {roi_file_path.as_posix()} does not exist. Check Patient and Config IDs.")
        sys.exit(1)

    return config_file_path, roi_file_path, code_path


def load_json_content(config_file_path, roi_file_path):
    """
    Load JSON data from the electrode configuration file and ROI file.

    Parameters
    ----------
    config_file_path : Path
        A Path object to the electrode configuration file.
    roi_file_path : Path
        A Path object to the ROI file.

    Returns
    -------
    tuple
        A tuple (config_json_content, roi_json_content) as Python dictionaries.

    Raises
    ------
    SystemExit
        Exits if JSON parsing fails.
    """
    try:
        with config_file_path.open() as file:
            config_json_content = json.load(file)
    except Exception as e:
        print(f"Error: Failed to parse JSON content from {config_file_path.as_posix()}. {str(e)}")
        sys.exit(1)

    try:
        with roi_file_path.open() as file:
            roi_json_content = json.load(file)
    except Exception as e:
        print(f"Error: Failed to parse JSON content form {roi_file_path.as_posix()}. {str(e)}")

    return config_json_content, roi_json_content


def validate_args_vs_json(args, config_json_content, roi_json_content):
    """
    Compare command-line arguments against values found in JSON files.

    Issues warnings if mismatch is found between the provided IDs
    (PatientID, ConfigID, ROIID) and those loaded from the JSON contents.

    Parameters
    ----------
    args : argparse.Namespace
        An object with PatientID, ConfigID, and ROIID.
    config_json_content : dict
        A dict loaded from the electrode config JSON.
    roi_json_content : dict
        A dict loaded from the ROI JSON.

    Returns
    -------
    tuple
        A tuple (electrodes, config_id_json, patient_id_json, roi_id_json)
        extracted from the JSON files.

    Raises
    ------
    SystemExit
        Exits if electrodes are not found in the configuration JSON.
    """
    electrodes = config_json_content.get("Electrodes", {})
    metadata = config_json_content.get("Metadata", {})
    config_id_json = metadata.get("Config_ID", "")
    patient_id_json = metadata.get("Patient_ID", "")
    roi_id_json = roi_json_content.get("Metadata", {}).get("ROI_ID", "")

    if args.ROIID != roi_id_json:
        print(f"Warning: supplied ROI ID {args.ROIID} does not match ROI ID from config file {roi_id_json}")

    if args.PatientID != patient_id_json:
        print(f"Warning: supplied Patient ID {args.PatientID} does not match Patient ID from config file {patient_id_json}")

    if args.ConfigID != config_id_json:
        print(f"Warning: supplied Config ID (Ensemble name) {args.ConfigID} does not match Config ID from config file {config_id_json}")

    if not electrodes:
        print("Error: No electrodes found in the configuration file.")
        sys.exit(1)

    return electrodes, config_id_json, patient_id_json, roi_id_json


def run_simulations(electrodes, max_containers, image_name, mesh_name, code_path, config_id_json, patient_id_json):
    """
    Run Docker-based simulations for each electrode concurrently up to max_containers limit.

    For each electrode:
    1. Await available container slots if max_containers is reached.
    2. Extract the electrode position (X, Y, Z).
    3. Spin up a Docker container passing environment variables.

    Parameters
    ----------
    electrodes : dict
        A dict of electrode data from the configuration JSON.
    max_containers : int
        Maximum number of Docker containers to run concurrently.
    image_name : str
        Name (and tag) of the Docker image to run.
    mesh_name : str
        Name of the mesh used for the simulation (e.g., patient ID).
    code_path : Path
        Path to the local code directory (mounted into the container).
    config_id_json : str
        A string ID for the current configuration (from JSON).
    patient_id_json : str
        A string ID for the current patient (from JSON).

    Returns
    -------
    None

    Raises
    ------
    SystemExit
        Exits if a container fails to start.
    """
    # Keep track of running processes
    running_containers = []
    for electrode, position in electrodes.items():
        # Wait until the number of running containers is less than max_containers
        while len(running_containers) >= max_containers:
            # Check the status of running containers
            for p in running_containers[:]:
                if p.poll() is not None:  # Check if the process has finished
                    running_containers.remove(p)
            time.sleep(10)

        # Extract XYZ coordinates for the current electrode
        X = position.get("X", 0)
        Y = position.get("Y", 0)
        Z = position.get("Z", 0)

        # Start a Docker container for the simulation
        try:
            process = subprocess.Popen([
                "docker", "run",
                "-v", f"{code_path.parent}:/app",
                "-v", f"{DATA_PATH}:/data",
                "-e", f"ELECTRODE_POSITION_X={X}",
                "-e", f"ELECTRODE_POSITION_Y={Y}",
                "-e", f"ELECTRODE_POSITION_Z={Z}",
                "-e", f"ENSEMBLE_NAME={config_id_json}",
                "-e", f"ELECTRODE_NAME={electrode}",
                "-e", f"MESH_NAME={mesh_name}",
                image_name
            ])
            running_containers.append(process)
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to start Docker container. {str(e)}")
            sys.exit(1)

        time.sleep(5)

    # Wait for all remaining containers to finish
    for process in running_containers:
        process.wait()


def post_processing(config_id_json, patient_id_json, roi_id_json):
    """
    Perform post-processing tasks once all simulations are complete.

    These tasks include:
    - Aggregating simulation outputs (process_simulation_output).
    - Mapping results to the ROI (map_simulation_to_roi).
    - Converting final data to 3D (convert_to_3d).
    - Collecting validation results for this ROI and in general.

    Parameters
    ----------
    config_id_json : str
        The configuration ID from JSON metadata.
    patient_id_json : str
        The patient ID from JSON metadata.
    roi_id_json : str
        The ROI ID from JSON metadata.

    Returns
    -------
    None
    """
    process_simulation_output(config_id_json, patient_id_json)
    map_simulation_to_roi(config_id_json, patient_id_json, roi_id_json)
    convert_to_3d(config_id_json, patient_id_json)
    collect_validation_results_for_roi(config_id_json, patient_id_json, roi_id_json)
    collect_validation_results(config_id_json, patient_id_json)


def main():
    """
    Main entry point for configuring and running SimNIBS-based Docker simulations.

    Steps:
    1. Parse CLI arguments (PatientID, ConfigID, ROIID).
    2. Load config.ini for container/image settings.
    3. Validate existence of required files (electrode config, ROI data).
    4. Compare CLI args with JSON metadata, warn if mismatched.
    5. Launch Docker containers for each electrode, respecting max concurrency.
    6. Run post-processing tasks (mapping to ROI, creating 3D data, validation).

    Returns
    -------
    None

    Raises
    ------
    SystemExit
        Exits on critical errors.
    """
    args = parse_arguments()
    config = load_config()

    max_containers, image_name, mesh_name = get_settings(config, args)
    config_file_path, roi_file_path, code_path = validate_files(args)
    config_json_content, roi_json_content = load_json_content(config_file_path, roi_file_path)
    electrodes, config_id_json, patient_id_json, roi_id_json = validate_args_vs_json(args, config_json_content, roi_json_content)

    run_simulations(electrodes, max_containers, image_name, mesh_name, code_path, config_id_json, patient_id_json)
    post_processing(config_id_json, patient_id_json, roi_id_json)


if __name__ == "__main__":
    main()