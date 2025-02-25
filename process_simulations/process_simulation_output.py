"""
This module processes simulation outputs for different configurations and patients.
It includes functions to convert simulation data to 3D data, validate simulation results,
and map simulation data to regions of interest (ROIs).

Functions
---------
    - convert_to_data_and_3d : Convert simulation output to 3D data and JSON format for a given configuration and patient.
    - convert_to_3d : Convert simulation output to 3D data for a given configuration and patient.
    - convert_to_data_for_reference : Convert reference simulation output to JSON format.
    - process_simulation_output : Process simulation output for a given configuration and patient, including validation and conversion.
    - map_simulation_to_roi : Map simulation data to a region of interest (ROI) for a given configuration, patient, and ROI.

Dependencies
------------
    - json : For reading and writing JSON files.
    - os : For file and directory operations.
    - simnibs.mesh_tools : For reading mesh files.
    - database_params : Custom module for database parameters and paths.
    - process_simulations.process_3d_functions : Custom module for creating 3D data.
    - process_simulations.process_data_functions : Custom module for converting data to JSON and creating combined JSON files.
    - process_simulations.process_roi_functions : Custom module for creating ROI masks and mapping data to ROIs.
    - process_simulations.validate_simulation_output : Custom module for validating simulation success and results.
"""

from simnibs import mesh_tools

import utils
from process_simulations.process_3d_functions import create_3d_data
from process_simulations.process_data_functions import (
    convert_data_to_json,
    create_one_json_data_file,
)
from process_simulations.process_roi_functions import create_roi_mask, map_data_to_roi
from process_simulations.validate_simulation_output import (
    collect_validation_results_for_roi,
    validate_simulations_result,
    validate_simulations_success,
)


def convert_to_data_and_3d(_config_id: str, _patient_id: str) -> None:
    """
    Convert simulation output to 3D data and JSON format for a given configuration and patient.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.

    Returns
    -------
    None
    """
    save_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id
    validation_results = utils.load_json(save_path / f"{_config_id}_validation_results.json")

    if validation_results is None:
        print(f"Error, no validation results at {(save_path / f'{_config_id}_validation_results.json').as_posix()}")
        return

    successful_indices = validation_results['successful_simulation_indices']

    data_3d_created = False

    for i in successful_indices:
        mesh_raw = mesh_tools.read_msh(utils.get_sim_mesh_path(_config_id, str(i)))

        if not data_3d_created:
            create_3d_data(_config_id, mesh_raw, _patient_id)
            data_3d_created = True
        median_magnitude, mean_magnitude, percentile_95 = convert_data_to_json(mesh_raw, _config_id,
                                                                               f"Electrode_{i}", _patient_id)
        validation_results[f'Electrode_{i}']['median_magnitude'] = median_magnitude
        validation_results[f'Electrode_{i}']['mean_magnitude'] = mean_magnitude
        validation_results[f'Electrode_{i}']['percentile_95'] = percentile_95

    create_one_json_data_file(_config_id, _patient_id, successful_indices)

    utils.save_json(validation_results, save_path / f"{_config_id}_validation_results.json")


def convert_to_3d(_config_id: str, _patient_id: str) -> None:
    """
    Convert simulation output to 3D data for a given configuration and patient.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.

    Returns
    -------
    None
    """
    path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id
    validation_results = utils.load_json(path / f"{_config_id}_validation_results.json")

    if validation_results is None:
        print(f"Error, no validation results at {(path / f'{_config_id}_validation_results.json').as_posix()}")
        return

    mesh_raw = mesh_tools.read_msh(utils.get_sim_mesh_path(_config_id, str(validation_results['successful_simulation_indices'][0])))
    create_3d_data(_config_id, mesh_raw, _patient_id)


def convert_to_data_for_reference(_config_id: str, _patient_id: str) -> None:
    """
    Convert reference simulation output to JSON format.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.

    Returns
    -------
    None
    """
    mesh_raw = mesh_tools.read_msh(utils.get_sim_mesh_path("REFERENCE", "0"))
    convert_data_to_json(mesh_raw, "REFERENCE_V000", "REFERENCE", "NO_NAME")


def process_simulation_output(_config_id: str, _patient_id: str) -> None:
    """
    Process simulation output for a given configuration and patient.
    This includes validating simulation success, converting data to 3D, and validating results.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.

    Returns
    -------
    None
    """
    print(f'=== Validate Simulations Success (1/2) for {_patient_id}: {_config_id} ===')
    validate_simulations_success(_config_id, _patient_id)

    print(f'=== Process Simulation Output for {_patient_id}: {_config_id} ===')
    convert_to_data_and_3d(_config_id, _patient_id)

    print(f'=== Validate Simulations Result (2/2) for {_patient_id}: {_config_id} ===')
    validate_simulations_result(_config_id, _patient_id)


def map_simulation_to_roi(_config_id: str, _patient_id: str, _roi_id: str):
    """
    Map simulation data to a region of interest (ROI) for a given configuration, patient, and ROI.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.
    _roi_id : str
        Region of Interest ID.

    Returns
    -------
    None
    """
    print(f'=== Create ROI Mask for {_patient_id}: {_config_id}: {_roi_id}  ===')
    create_roi_mask(_config_id, _patient_id, _roi_id)

    print(f'=== Map Data to Roi for {_patient_id}: {_config_id}: {_roi_id} ===')
    map_data_to_roi(_config_id, _patient_id, _roi_id)

    print(f'=== Collect Validation Output for {_patient_id}: {_config_id}: {_roi_id}  ===')
    collect_validation_results_for_roi(_config_id, _patient_id, _roi_id)
