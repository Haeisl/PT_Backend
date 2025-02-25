"""
This module processes simulation data for different configurations and patients.
It includes functions to convert simulation data to JSON format, create 3D data files,
and manage the storage and compression of these files.

Functions
---------
    - convert_data_to_json : Convert simulation data to JSON format for a given configuration, electrode, and patient.
    - create_one_json_data_file : Create a single JSON data file from multiple simulation outputs for a given configuration and patient.

Dependencies
------------
    - json : For reading and writing JSON files.
    - os : For file and directory operations.
    - shutil : For high-level file operations.
    - zlib : For compressing data.
    - numpy : For numerical operations and statistics.
    - database_params : Custom module for database parameters and paths.
    - process_simulations.process_helper_functions : Custom module for creating tag-based dictionaries.
"""

import json
import shutil
import zlib

import numpy as np

import utils
from process_simulations.process_helper_functions import create_tag_based_dictionary


def convert_data_to_json(_mesh, _config_id: str, _current_electrode: str, _patient_id: str):
    """
    Convert simulation data to JSON format for a given configuration, electrode, and patient.

    Parameters
    ----------
    _mesh : object
        Mesh object containing simulation data.
    _config_id : str
        Configuration ID.
    _current_electrode : str
        Current electrode ID.
    _patient_id : str
        Patient ID.

    Returns
    -------
    tuple
        Median, mean, and 95th percentile of the combined magnitudes.
    """
    print("============================= " + _current_electrode + " =============================")

    print("Tags...")
    all_tags = _mesh.elm.tag1

    print("Simulation data...")
    all_magnE_dict, mtags = create_tag_based_dictionary(all_tags, _mesh.elmdata[1].value)

    all_E_dict, vtags = create_tag_based_dictionary(all_tags, _mesh.elmdata[0].value)

    save_path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / _current_electrode
    save_path.mkdir(parents=True, exist_ok=True)

    # Save magnitude data to JSON files
    for key, value in all_magnE_dict.items():
        utils.save_json({key: value}, save_path / f"{_config_id}_{key}_magnE_dict.json")

    # Save vector field data to JSON files
    for key, value in all_E_dict.items():
        utils.save_json({key: value}, save_path / f"{_config_id}_{key}_E_dict.json")

    # Combine values for specific volume tags
    volume_tags = {"1", "2", "3", "6", "8", "9", "10"}
    combined_values = []
    for key in all_magnE_dict:
        if key in volume_tags:
            combined_values.extend(all_magnE_dict[key])

    # Calculate and return the median, mean, and 95th percentile of the combined values
    return np.median(combined_values), np.mean(combined_values), np.percentile(combined_values, 95)


def create_one_json_data_file(_config_id: str, _patient_id: str, _successful_indices):
    """
    Create a single JSON data file from multiple simulation outputs for a given configuration and patient.

    Parameters
    ----------
    _config_id : str
        Configuration ID.
    _patient_id : str
        Patient ID.
    _successful_indices : list
        List of successful simulation indices.

    Returns
    -------
    None
    """

    Electrodes = {}

    path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id

    # Define tags to be processed
    tags = ["1001", "1002", "1003", "1006", "1008", "1009", "1010", "1", "2", "3", "6", "8", "9", "10"]  # 1005 , 5 , 7

    for i in _successful_indices:
        Magnitude = {}
        Vectorfield = {}

        for tag in tags:
            file_path_magn = path / f"Electrode_{i}" / f"{_config_id}_{tag}_magnE_dict.json"
            file_path_vfield = path / f"Electrode_{i}" / f"{_config_id}_{tag}_E_dict.json"

            magn_data = utils.load_json(file_path_magn)
            vfield_data = utils.load_json(file_path_vfield)

            if magn_data is None or vfield_data is None:
                return

            Magnitude.update(magn_data)
            Vectorfield.update(vfield_data)

        Electrodes[f"Electrode_{i}"] = {
            "Magnitude": Magnitude,
            "Vectorfield": Vectorfield
        }

    print("Combining...")
    merged_data = {
        "Electrodes": Electrodes,
        "Metadata": {}
    }

    print("Creating JSON...")
    utils.save_json(merged_data, path / f"{_config_id}_data.json")

    # Compress JSON data with zlib
    print("Compressing JSON...")
    compressed_data = zlib.compress(json.dumps(merged_data).encode())
    compressed_file = path / f"{_config_id}_compressed_data.zlib"
    compressed_file.write_bytes(compressed_data)

    # Delete individual files
    print("Deleting...")
    for i in _successful_indices:
        electrode_folder = path / f"Electrode_{i}"
        if electrode_folder.exists():
            shutil.rmtree(electrode_folder)
