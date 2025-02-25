"""
This module processes the original mesh data for different patients.
It includes functions to convert mesh data to JSON format, create tag-based dictionaries,
and manage the storage and compression of these files.

Functions
---------
    - convert_mesh_to_json : Convert mesh data to JSON format for a given patient.
    - create_tag_based_dictionary : Create a dictionary based on tags and their corresponding data.

Dependencies
------------
    - json : For reading and writing JSON files.
    - os : For file and directory operations.
    - zlib : For compressing data.
    - numpy : For numerical operations and statistics.
    - database_params : Custom module for database parameters and paths.
    - simnibs.mesh_tools : For reading mesh files.
    - process_simulations.process_helper_functions : Custom module for creating tag lookup tables.
"""
import json
import zlib

import numpy as np
from simnibs import mesh_tools

import utils
from process_simulations.process_helper_functions import (
    create_tag_look_up_table_default,
)


def convert_mesh_to_json(mesh: mesh_tools.Msh, _patient_id: str) -> None:
    """
    Convert mesh data to JSON format for a given patient.

    Parameters
    ----------
    mesh : object
        Mesh object containing simulation data.
    _patient_id : str
        Patient ID.

    Returns
    -------
    None
    """
    print("Vertices...")
    vertices = mesh.nodes.node_coord

    print("Triangles...")
    split_index = mesh.elm.triangles.size
    triangles = mesh.elm.node_number_list[:split_index, :3] - 1

    print("Tags...")
    all_tags = mesh.elm.tag1[:split_index]
    unique_tag_list = np.unique(all_tags)

    # Create a dictionary based on tags and triangles
    meshes_dict = create_tag_based_dictionary(all_tags, triangles)

    print("Descriptions...")
    # Create a lookup table for tags with their descriptions
    mesh_descriptions = create_tag_look_up_table_default(unique_tag_list)

    save_path = utils.DATABASE_PATHS["original"] / _patient_id
    save_path.mkdir(parents=True, exist_ok=True)

    print("Creating JSON Files...")
    # Save unique tag list to JSON file
    utils.save_json(unique_tag_list.tolist(), save_path / f"{_patient_id}_unique_tag_list.json")

    # Save vertices to JSON file
    utils.save_json(vertices.tolist(), save_path / f"{_patient_id}_vertices.json")

    # Save mesh dictionary to JSON file
    utils.save_json(meshes_dict, save_path / f"{_patient_id}_mesh.json")

    # Save skin mesh to JSON file
    utils.save_json(meshes_dict["1005"], save_path / f"{_patient_id}_skin_mesh.json")

    # Combine all data into a single dictionary
    merged_data = {
        "vertices": vertices.tolist(),
        "meshes": meshes_dict,
        "mesh_tags": unique_tag_list.tolist(),
        "mesh_descriptions": mesh_descriptions
    }
    # Save combined data to a single JSON file
    utils.save_json(merged_data, save_path / f"{_patient_id}_original_3d_data.json")

    #print("Checking for ndarrays...")
    #check_for_ndarrays(merged_data)

    # Compress JSON data with zlib
    print("Compressing JSON...")
    try:
        compressed_data = zlib.compress(json.dumps(merged_data).encode())
        # Save compressed data to a file
        compressed_file = save_path / f"{_patient_id}_original_compressed_3d_data.zlib"
        compressed_file.write_bytes(compressed_data)
        print(f"Successfully compressed to zlib in: {str(compressed_file)}")
    except Exception:
        raise

    print("Done!")


def create_tag_based_dictionary(tags: list, tag_data: list) -> dict:
    """
    Create a dictionary based on tags and their corresponding data.

    Parameters
    ----------
    tags : list
        List of tags.
    tag_data : list
        List of data corresponding to the tags.

    Returns
    -------
    dict
        Dictionary of tags and their data.
    """
    meshes_dict = {}

    print("Building Dictionary...")
    for tag, data in zip(tags, tag_data):
        key = str(tag)
        if key not in meshes_dict:
            meshes_dict[key] = []
        meshes_dict[key].append(data)

    # Converting NumPy arrays to lists
    for key in meshes_dict:
        meshes_dict[key] = np.flip(meshes_dict[key]).tolist()

    return meshes_dict

# # Path to the mesh file
# path = "C:\\Users\\Vince\\OneDrive\\UniHeidelberg\\SoSe23\\Praktikum_Epilepsie_2\\ernie_my.msh"
# # Read the mesh file
# mesh_raw = mesh_tools.read_msh(path.replace("\\", "/"))
# # Convert the mesh data to JSON format for the patient 'Ernie'
# convert_mesh_to_json(mesh_raw, 'Ernie')