"""
This module provides functions to validate the success and results of simulations for a given configuration and patient.

Functions
---------
    - validate_simulations_success : Validates the success of simulations by checking the success status of each simulation.
    - validate_simulations_result : Placeholder function for validating simulation results.
    - collect_validation_results : Collects validation results and updates them with magnitude statistics.
    - collect_validation_results_for_roi : Collects validation results for a specific ROI and updates them with magnitude statistics for different tags.

Dependencies
------------
    - json : For reading and writing JSON files.
    - os : For file and directory operations.
    - numpy : For numerical operations and statistics.
    - database_params : Custom module for database parameters and paths.
"""
import numpy as np

import utils


def validate_simulations_success(_config_id: str, _patient_id: str) -> None:
    """
    Validates the success of simulations for a given configuration and patient.

    This function reads the electrode positions from a JSON file and checks the success status of each simulation.
    The results are saved to a validation results JSON file.

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

    # Path to the electrode positions file
    electrode_position_file = utils.DATABASE_PATHS["electrode"] / _patient_id / f"electrode_positions_{_config_id}.json"
    data = utils.load_json(electrode_position_file)
    electrode_count = data['Metadata']['Number']

    # Initializing validation results dictionary
    validation_results = {
        'metadata': {
            'config_id': _config_id,
            'patient_id': _patient_id,
            'electrode_count': electrode_count
        },
        "successful_simulation_indices": []
    }

    # List to store indices of successful simulations
    successful_indices = []

    # Iterate over each electrode and check the success status of the simulation
    for i in range(electrode_count):
        sim_info_file = utils.get_sim_output_path(_config_id) / f"sim_info_Electrode_{i}.json"
        if not sim_info_file.exists():
            validation_results[f"Electrode_{i}"] = {"success": "false", "valid": "null", "median_magnitude": 0.0, "mean_magnitude": 0.0, "percentile_95": 0.0}
        else:
            sim_info = utils.load_json(sim_info_file)
            if not sim_info.get("success", False):
                validation_results[f'Electrode_{i}'] = {'success': "false", 'valid': "null", 'median_magnitude': 0.0, 'mean_magnitude': 0.0, 'percentile_95': 0.0}
            else:
                validation_results[f'Electrode_{i}'] = {'success': "true", 'valid': "null", 'median_magnitude': 0.0, 'mean_magnitude': 0.0, 'percentile_95': 0.0}
                # Add the index to the list
                successful_indices.append(i)

    # Adding the list of successful indices to the validation results
    validation_results["successful_simulation_indices"] = successful_indices

    # Saving the validation results to a JSON file
    save_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id
    save_path.mkdir(parents=True, exist_ok=True)
    utils.save_json(validation_results, save_path / f"{_config_id}_validation_results.json")


def validate_simulations_result(_config_id: str, _patient_id: str):
    """
    Placeholder function for validating simulation results.

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
    print("validate_simulations_result: NOT IMPLEMENTED YET")
    # raise NotImplementedError
    pass


def collect_validation_results(_config_id: str, _patient_id: str):
    """
    Collects validation results for a given configuration and patient.

    This function reads the simulation data and updates the validation results with magnitude statistics.

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

    print(f"Collecting validation results for {_patient_id}: {_config_id}")
    data_file_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / f"{_config_id}_data.json"
    validation_file_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id

    validation_results = utils.load_json(validation_file_path / f"{_config_id}_validation_results.json")

    # Check if the data file exists
    if not data_file_path.exists():
        print(f"File {data_file_path} does not exist.")
        return

    # Load the JSON data file
    data = utils.load_json(data_file_path)

    # Iterate over all electrodes and collect magnitude values
    for electrode, electrode_data in data['Electrodes'].items():
        combined_values = []
        for tag, magnitude in electrode_data['Magnitude'].items():
            combined_values.extend(magnitude)
        median_magnitude = np.median(combined_values)
        mean_magnitude = np.mean(combined_values)
        percentile_95 = np.percentile(combined_values, 95)
        max_magnitude = np.max(combined_values)
        print(f"=== Electrode: {electrode} ===")
        print(f"Median: {median_magnitude}, Mean: {mean_magnitude}, 95th percentile: {percentile_95}")
        validation_results[electrode]['median_magnitude'] = median_magnitude
        validation_results[electrode]['mean_magnitude'] = mean_magnitude
        validation_results[electrode]['percentile_95'] = percentile_95
        validation_results[electrode]['max_magnitude'] = max_magnitude

    # Save the updated validation results to a JSON file
    utils.save_json(validation_results, validation_file_path / f"{_config_id}_validation_results.json")


def collect_validation_results_for_roi(_config_id: str, _patient_id: str, _roi_id: str):
    """
    Collects validation results for a specific ROI (Region of Interest) for a given configuration and patient.

    This function reads the simulation data and updates the validation results with magnitude statistics for different tags.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.
    _roi_id : str
        ROI ID.

    Returns
    -------
    None
    """

    print(f"Collecting validation results for {_patient_id}: {_config_id} : {_roi_id}")
    data_file_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / _roi_id / f"{_roi_id}_roi_data.json"
    validation_file_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / _roi_id

    validation_results = {}  # Initialize validation_results

    if not data_file_path.exists():
        print(f"File {data_file_path} does not exist.")
        raise FileNotFoundError

    # Load the JSON data file
    data = utils.load_json(data_file_path)

    volume_tags = {"1", "2", "3", "6", "8", "9", "10"}
    # mesh_tags = {"1001", "1002", "1003", "1006", "1008", "1009", "1010"}

    # Iterate over all electrodes and collect magnitude values
    for electrode, electrode_data in data['Electrodes'].items():
        combined_values = []
        Grey_Matter_Percentile = 0
        Grey_Matter_max = 0
        Grey_Matter_Median = 0
        Grey_Matter_Mean = 0
        spongy_bone_Percentile = 0
        spongy_bone_max = 0
        spongy_bone_Median = 0
        spongy_bone_Mean = 0
        Grey_Matter_Percentile_mesh = 0
        Grey_Matter_max_mesh = 0
        Grey_Matter_Median_mesh = 0
        Grey_Matter_Mean_mesh = 0
        for tag, magnitude in electrode_data['Magnitude'].items():
            if tag in volume_tags:
                combined_values.extend(magnitude)
                if tag == "2":
                    Grey_Matter_Percentile = np.percentile(magnitude, 95)
                    Grey_Matter_max = np.max(magnitude)
                    Grey_Matter_Median = np.median(magnitude)
                    Grey_Matter_Mean = np.mean(magnitude)
                if tag == "8":
                    spongy_bone_Percentile = np.percentile(magnitude, 95)
                    spongy_bone_max = np.max(magnitude)
                    spongy_bone_Median = np.median(magnitude)
                    spongy_bone_Mean = np.mean(magnitude)
            if tag == "1002":
                Grey_Matter_Percentile_mesh = np.percentile(magnitude, 95)
                Grey_Matter_max_mesh = np.max(magnitude)
                Grey_Matter_Median_mesh = np.median(magnitude)
                Grey_Matter_Mean_mesh = np.mean(magnitude)


        median_magnitude = np.median(combined_values)
        mean_magnitude = np.mean(combined_values)
        percentile = np.percentile(combined_values, 95)
        max_magnitude = np.max(combined_values)
        print(f"=== Electrode: {electrode} ===")
        print(f"Median: {median_magnitude}, Mean: {mean_magnitude}, percentile: {percentile}")
        # Initialize a new dictionary for this electrode
        validation_results[electrode] = {}
        validation_results[electrode]['Median_Magnitude'] = median_magnitude
        validation_results[electrode]['Mean_Magnitude'] = mean_magnitude
        validation_results[electrode]['percentile_95'] = percentile
        validation_results[electrode]['Max_Magnitude'] = max_magnitude
        validation_results[electrode]['Grey_Matter_Percentile_95_Magnitude'] = Grey_Matter_Percentile
        validation_results[electrode]['Grey_Matter_Max_Magnitude'] = Grey_Matter_max
        validation_results[electrode]['Grey_Matter_Median_Magnitude'] = Grey_Matter_Median
        validation_results[electrode]['Grey_Matter_Mean_Magnitude'] = Grey_Matter_Mean
        validation_results[electrode]['Grey_Matter_Percentile_95_Mesh_Magnitude'] = Grey_Matter_Percentile_mesh
        validation_results[electrode]['Grey_Matter_Max_Mesh_Magnitude'] = Grey_Matter_max_mesh
        validation_results[electrode]['Grey_Matter_Median_Mesh_Magnitude'] = Grey_Matter_Median_mesh
        validation_results[electrode]['Grey_Matter_Mean_Mesh_Magnitude'] = Grey_Matter_Mean_mesh
        validation_results[electrode]['Spongy_Bone_Percentile_95_Magnitude'] = spongy_bone_Percentile
        validation_results[electrode]['Spongy_Bone_Max_Magnitude'] = spongy_bone_max
        validation_results[electrode]['Spongy_Bone_Median_Magnitude'] = spongy_bone_Median
        validation_results[electrode]['Spongy_Bone_Mean_Magnitude'] = spongy_bone_Mean

    # Save the updated validation results to a JSON file
    utils.save_json(validation_results, validation_file_path / f"{_config_id}_{_roi_id}_roi_validation_results.json")
