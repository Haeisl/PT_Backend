"""
This module provides functions to handle various data processing tasks
related to simulations for different configurations and patients.

It offers REST endpoints for retrieving and updating 3D mesh data, electrode
positions, ROI data, and simulated results for a variety of configurations
and patient IDs.

Dependencies include:
    - json: For reading and writing JSON files.
    - os: For file and directory operations.
    - flask: For creating the web server and handling HTTP requests.
    - database_params (in ```utils```): Custom module for database parameters and paths.
    - waitress: For serving the Flask application.

Routes Provided:
    - /3d/configuration/<_patient_id> (GET): Retrieves original 3D mesh data
    - /data/elect_pos/<_patient_id>/<_config_id> (POST/GET): Manages electrode positions
    - /data/validation/<_patient_id>/<_config_id> (GET): Retrieves validation results
    - /data/roi/<_patient_id>/<_roi_id> (POST): Receives ROI data
    - /3d/configuration/skin/<_patient_id> (GET): Retrieves skin mesh data
    - /3d/simulated/<_patient_id>/<_config_id> (GET): Retrieves simulated 3D mesh data
    - /data/simulated/<_patient_id>/<_config_id>/<_roi_id> (GET): Retrieves simulated data for a specified ROI
    - /data/interpolated/<_patient_id>/<_config_id>/<_roi_id>/<_interpolation_id> (POST): Receives interpolated data
    - /reached (GET): Returns a simple status response
    - /run_simulations/<_patient_id>/<_config_id>/<_roi_id> (POST): Starts the simulations
"""

#!/usr/bin/env python
# encoding: utf-8
import json
import os
import subprocess
import time

from flask import Flask, Response, jsonify, request, send_file

import utils

app = Flask(__name__)

# File containing the patient IDs and times they were last called
LOCK_FILE = "./logs/simulation_locks.json"

# Minimum interval between simulations in seconds
SIMULATION_LOCK_TIME = 300


def load_last_execution_times():
    try:
        with open(LOCK_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_last_execution_times(data):
    with open(LOCK_FILE, 'w') as f:
        json.dump(data, f)


@app.route('/3d/configuration/<_patient_id>', methods=['GET'])
def get_default_mesh(_patient_id: str) -> tuple[Response, int, dict]:
    """
    Retrieves the original 3D mesh data for a given patient.

    Parameters
    ----------
    _patient_id : str
        The patient ID.

    Returns
    -------
    tuple
        A tuple containing:
            - A Flask Response object sending the compressed .zlib file
            - An HTTP status code (200 if successful)
            - A dictionary of headers, here indicating 'Decompressed-Size'
    """
    print(f"Loading original mesh for {_patient_id}...")
    path = utils.DATABASE_PATHS["original"] / _patient_id
    path_json = path / f"{_patient_id}_original_3d_data.json"
    path_zlib = path / f"{_patient_id}_original_compressed_3d_data.zlib"

    decompressed_size = path_json.stat().st_size

    return send_file(path_zlib, as_attachment=True), 200, {'Decompressed-Size': decompressed_size}


@app.route('/data/elect_pos/<_patient_id>/<_config_id>', methods=['POST'])
def receive_electrode_positions(_patient_id: str, _config_id: str) -> str:
    """
    Receives and saves electrode positions for a given patient and configuration.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.

    Returns
    -------
    str
        A confirmation message indicating the positions were received.
    """
    json_data = request.get_json()

    path = utils.DATABASE_PATHS["electrode"] / _patient_id
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"electrode_positions_{_config_id}.json"
    utils.save_json(json_data, file_path)

    message = f"Electrode positions for {_patient_id}: {_config_id} received!"
    print(message)
    return message


@app.route('/data/elect_pos/<_patient_id>/<_config_id>', methods=['GET'])
def get_electrode_area(_patient_id: str, _config_id: str) -> dict:
    """
    Retrieves the electrode positions for a given patient and configuration.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.

    Returns
    -------
    dict
        A dictionary containing the electrode positions.
    """
    path = utils.DATABASE_PATHS["electrode"] / _patient_id / f"electrode_positions_{_config_id}.json"
    elect_pos = utils.load_json(path)

    print(f"Sending electrode positions for {_patient_id}: {_config_id}...")
    print(path)
    return elect_pos


@app.route('/data/validation/<_patient_id>/<_config_id>', methods=['GET'])
def get_validation(_patient_id: str, _config_id: str) -> dict:
    """
    Retrieves validation results for a given patient and configuration.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.

    Returns
    -------
    dict
        A dictionary containing the validation results.
    """
    path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / f"{_config_id}_validation_results.json"
    validation_results = utils.load_json(path)

    print(f"Sending validation results for {_patient_id}: {_config_id}...")
    print(path)
    return validation_results


@app.route('/data/roi/<_patient_id>/<_roi_id>', methods=['POST'])
def receive_roi_data(_patient_id: str, _roi_id: str) -> str:
    """
    Receives and saves ROI (Region of Interest) data for a given patient and ROI ID.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _roi_id : str
        The ROI ID.

    Returns
    -------
    str
        A confirmation message indicating the ROI data was received.
    """
    json_data = request.get_json()
    print(f"New ROI Data for {_patient_id}: {_roi_id} received!")

    path = utils.DATABASE_PATHS["roi"] / _patient_id
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"{_roi_id}_roi_bounds.json"
    utils.save_json(json_data, file_path)

    return f"ROI Data for {_patient_id}: {_roi_id} received!"


@app.route('/3d/configuration/skin/<_patient_id>', methods=['GET'])
def get_skin(_patient_id: str) -> Response:
    """
    Retrieves the skin mesh data for a given patient.

    Parameters
    ----------
    _patient_id : str
        The patient ID.

    Returns
    -------
    Response
        A Flask Response object (JSON) containing vertices and triangles for the skin mesh.
    """
    print(f"Loading skin_mesh for {_patient_id}...")
    path = utils.DATABASE_PATHS["original"] / _patient_id

    vertices_path = path / f"{_patient_id}_vertices.json"
    skin_path = path / f"{_patient_id}_skin_mesh.json"
    vertices = utils.load_json(vertices_path)
    skin_mesh = utils.load_json(skin_path)

    print(f"Sending skin_mesh for {_patient_id}...")
    return jsonify({'vertices': vertices, 'triangles': skin_mesh})


@app.route('/3d/simulated/<_patient_id>/<_config_id>', methods=['GET'])
def get_mesh(_patient_id: str, _config_id: str) -> tuple[Response, int, dict]:
    """
    Retrieves the simulated 3D mesh data for a given patient and configuration.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.

    Returns
    -------
    tuple
        A tuple containing:
            - A Flask Response object sending the compressed 3D .zlib file
            - HTTP status code
            - A header dict containing the 'Decompressed-Size'
    """
    print(f"Loading mesh for patient id {_patient_id}...")
    path_json = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / f"{_config_id}_3d_data.json"
    path_zlib = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / f"{_config_id}_compressed_3d_data.zlib"

    decompressed_size = path_json.stat().st_size

    return send_file(path_zlib, as_attachment=True), 200, {'Decompressed-Size': decompressed_size}


@app.route('/data/simulated/<_patient_id>/<_config_id>/<_roi_id>', methods=['GET'])
def get_data(_patient_id: str, _config_id: str, _roi_id: str) -> tuple[Response, int, dict]:
    """
    Retrieves the simulated data for a given patient, configuration, and ROI.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.
    _roi_id : str
        The ROI ID.

    Returns
    -------
    tuple
        A tuple containing:
            - A Flask Response object sending the compressed ROI .zlib file
            - HTTP status code
            - A header dict with the 'Decompressed-Size'
    """
    print(f"Loading data for patient id {_patient_id}...")
    path_roi = utils.DATABASE_PATHS["process"] / _patient_id / _config_id / _roi_id

    path_json = path_roi / f"{_roi_id}_roi_data.json"
    path_zlib = path_roi / f"{_roi_id}_compressed_roi_data.zlib"

    print("Sending...")
    decompressed_size = path_json.stat().st_size

    return send_file(path_zlib, as_attachment=True), 200, {'Decompressed-Size': decompressed_size}


@app.route('/data/interpolated/<_patient_id>/<_config_id>/<_roi_id>/<_interpolation_id>', methods=['POST'])
def receive_interpolated_data(_patient_id: str, _config_id: str, _roi_id: str, _interpolation_id: str) -> str:
    """
    Receives and saves interpolated data for a given patient, configuration, ROI, and interpolation ID.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.
    _roi_id : str
        The ROI ID.
    _interpolation_id : str
        The interpolation ID.

    Returns
    -------
    str
        A confirmation message indicating the data was received.
    """
    json_data = request.get_json()
    print("New Interpolated Data received!")

    path = utils.DATABASE_PATHS["interpolation"] / _patient_id / _config_id / _roi_id
    path.mkdir(parents=True, exist_ok=True)

    file_path = path / f"{_interpolation_id}_interpolated_data.json"
    utils.save_json(json_data, file_path)

    print(f"Interpolated Data for {_patient_id}: {_config_id} | {_roi_id} | {_interpolation_id} received!")
    return f"Interpolated Data for {_patient_id}: {_config_id} | {_roi_id} | {_interpolation_id} received!"

@app.route('/reached', methods=['GET'])
def reached():
    """
    Simple health-check endpoint.

    Returns
    -------
    Response
        JSON response with 'status': True, and HTTP 200.
    """
    return jsonify({'status': True}), 200

@app.route('/run_simulations/<_patient_id>/<_config_id>/<_roi_id>', methods=['POST'])
def run_simulations(_patient_id: str, _config_id: str, _roi_id: str):
    """
    Route to initiate simulations for a given patient, configuration, and ROI.
    Ensures that only one simulation can be started for each patient within a specified lockout time.

    Parameters
    ----------
    _patient_id : str
        The patient ID.
    _config_id : str
        The configuration ID.
    _roi_id : str
        The ROI ID.

    Returns
    -------
    A JSON response indicating the status of the request:
        - 'success' if the simulation started successfully.
        - 'warning' if a simulation was recently started and the lockout time has not expired.
        - 'error' if there was an exception during the process.
    """
    print(f"PatientID:{_patient_id}, ConfigID:{_config_id}, ROIID:{_roi_id}")

    last_execution_times = load_last_execution_times()
    current_time = time.time()

    # Check if a simulation ran with this patient ID recently
    if _patient_id in last_execution_times:
        elapsed_time = current_time - last_execution_times[_patient_id]
        if elapsed_time < SIMULATION_LOCK_TIME:
            remaining_time = SIMULATION_LOCK_TIME - elapsed_time
            print(f"Need to wait {remaining_time} seconds before starting a new simulation for patient {_patient_id}")
            return jsonify({
                'status': 'warning',
                'message': f"Please wait {int(remaining_time)} seconds before starting a new simulation for this patient."
            }), 429 # HTTP 429 means Too Many Requests

    # Update last execution time
    last_execution_times[_patient_id] = current_time
    save_last_execution_times(last_execution_times)

    try:
        command = [
            "python", "run_docker_simulations.py",
            "--PatientID", _patient_id,
            "--ConfigID", _config_id,
            "--ROIID", _roi_id
        ]
        # Create detached process on Windows
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

        # Start subprocess in a new session and redirect its output
        with open("./logs/simulation_output.log", "w") as out, open("./logs/simulation_error.log", "w") as err:
            subprocess.Popen(command, stdout=out, stderr=err, creationflags=creation_flags, start_new_session=True)

        print(f"Successfully started simulations for patient {_patient_id}, config {_config_id}, ROI {_roi_id}!")
        return jsonify({
            'status': 'success',
            'message': 'Simulation started in background'
        }), 200

    except Exception as e:
        print(f"Unable to start simulation for patient {_patient_id}. {str(e)}")
        return jsonify({'status':'error', 'message':str(e)}), 500
