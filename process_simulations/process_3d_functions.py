"""
This module processes 3D simulation data for different configurations and patients.
It includes functions to map geometry to vertices, create tag-based dictionaries,
and generate 3D data files in JSON format.

Functions
---------
    - map_geometry_to_vertex : Map geometry objects to their corresponding vertices, including their indices.
    - create_tag_to_new_index_mapping : Create a mapping from tags to new indices.
    - create_tag_based_dictionary_for_volumes : Create a dictionary based on volume tags.
    - create_3d_data : Create 3D data files for a given ensemble and patient.

Dependencies
------------
    - json : For reading and writing JSON files.
    - os : For file and directory operations.
    - zlib : For compressing data.
    - collections.defaultdict : For creating default dictionaries.
    - numpy : For numerical operations and statistics.
    - database_params : Custom module for database parameters and paths.
    - process_simulations.process_helper_functions : Custom module for creating tag-based dictionaries and lookup tables.
"""

import json
import zlib
from collections import defaultdict

import numpy as np
from simnibs import mesh_tools

import utils
from process_simulations.process_helper_functions import (
    create_tag_based_dictionary,
    create_tag_look_up_table,
    is_valid_tag,
)


def map_geometry_to_vertex(_geometry: list, _geometry_indices: list) -> dict:
    """
    Map geometry objects to their corresponding vertices, including their indices.

    Parameters
    ----------
    _geometry : list
        List of geometry objects.
    _geometry_indices : list
        List of geometry indices.

    Returns
    -------
    dict
        Dictionary mapping vertices to geometry objects and their indices.
    """
    vertex_to_tetra = defaultdict(list)
    for _geometry_object, _geometry_index in zip(_geometry, _geometry_indices):
        _geometry_object_tuple = tuple(
            int(vertex) for vertex in _geometry_object
        )  # Convert the cell array to a tuple once per cell
        for vertex in _geometry_object:
            vertex_str = str(vertex)
            # Include both the geometry object tuple and its index in the structure
            if vertex_str not in vertex_to_tetra:
                vertex_to_tetra[vertex_str] = [
                    (_geometry_object_tuple, int(_geometry_index))
                ]
            else:
                vertex_to_tetra[vertex_str].append(
                    (_geometry_object_tuple, int(_geometry_index))
                )
    return dict(vertex_to_tetra)


def create_tag_to_new_index_mapping(_cell_tags: list) -> tuple:
    """
    Create a mapping from tags to new indices.

    Parameters
    ----------
    _cell_tags : list
        List of cell tags.

    Returns
    -------
    tuple
        Dictionary mapping tags to new indices and dictionary of tag lengths.
    """
    tag_to_new_index = {}
    tag_length_dict = {}
    for tag in _cell_tags:
        str_tag = str(tag)
        if is_valid_tag(str_tag):
            tag_to_new_index.setdefault(str_tag, []).append(
                len(tag_to_new_index.get(str_tag, []))
            )
            tag_length_dict[str_tag] = len(tag_to_new_index[str_tag])
    return tag_to_new_index, tag_length_dict


def create_tag_based_dictionary_for_volumes(_volume_tags: list, _tetras: list) -> tuple:
    """
    Create a dictionary based on volume tags.

    Parameters
    ----------
    _volume_tags : list
        List of volume tags.
    _tetras : list
        List of tetrahedral elements.

    Returns
    -------
    tuple
        Dictionary of volume tags and list of used tags.
    """
    volume_dict = {}
    used_tags = set()

    print("Building Dictionary...")
    for tag, data in zip(_volume_tags, _tetras):
        str_tag = str(tag)
        if is_valid_tag(str_tag):
            # If data is a numpy ndarray, convert it to a list
            if isinstance(data, np.ndarray):
                data = data.tolist()
            volume_dict.setdefault(str_tag, []).append(data)

    for key, value in volume_dict.items():
        volume_dict[key] = np.unique(np.array(value).flatten()).tolist()
        used_tags.add(int(key))

    used_tags = sorted(list(used_tags))

    return volume_dict, list(map(str, used_tags))


def create_3d_data(_current_ensemble: str, _current_mesh: mesh_tools.Msh, _patient_id: str) -> int:
    """
    Create 3D data files for a given ensemble and patient.

    Parameters
    ----------
    _current_ensemble : str
        Current ensemble ID.
    _current_mesh : object
        Mesh object containing simulation data.
    _patient_id : str
        Patient ID.

    Returns
    -------
    int
        Maximum vertex index.
    """
    print("Tags... ")
    split_index = _current_mesh.elm.triangles.size
    mesh_tags = _current_mesh.elm.tag1[:split_index]
    volume_tags = _current_mesh.elm.tag1[split_index:]
    tag_indexing_dict, tag_length_dict = create_tag_to_new_index_mapping(
        _current_mesh.elm.tag1.tolist()
    )

    print("Cell Indices...")
    cell_indices_in_main_array = _current_mesh.elm.elm_number - 1
    mesh_cell_indices = cell_indices_in_main_array[:split_index]
    volume_cell_indices = cell_indices_in_main_array[split_index:]
    all_cell_index_dict, _ = create_tag_based_dictionary(
        _current_mesh.elm.tag1.tolist(), cell_indices_in_main_array.tolist()
    )

    print("Triangles... ")
    triangles = _current_mesh.elm.node_number_list[:split_index, :3] - 1
    meshes_dict, mesh_tag_list = create_tag_based_dictionary(mesh_tags, triangles)
    triangles_per_vertex = map_geometry_to_vertex(triangles, mesh_cell_indices)

    print("Tetras... ")
    tetras = _current_mesh.elm.node_number_list[split_index:] - 1
    volume_dict, volume_tag_list = create_tag_based_dictionary_for_volumes(
        volume_tags, tetras
    )
    volume_raw_dict, _ = create_tag_based_dictionary(volume_tags, tetras)
    tetras_per_vertex = map_geometry_to_vertex(tetras, volume_cell_indices)

    all_tags = mesh_tag_list + volume_tag_list

    print("Vertices... ")
    _max_index = 0

    for key, value in meshes_dict.items():
        t_max_index = np.max(np.ravel(value))
        if t_max_index > _max_index:
            _max_index = t_max_index

    for key, value in volume_dict.items():
        t_max_index = np.max(np.ravel(value))
        if t_max_index > _max_index:
            _max_index = t_max_index

    vertices = _current_mesh.nodes.node_coord[: _max_index + 1]

    print("Descriptions...")
    mesh_descriptions = create_tag_look_up_table(mesh_tag_list)
    volume_descriptions = create_tag_look_up_table(volume_tag_list)

    merged_data = {
        "vertices": vertices.tolist(),
        "meshes": meshes_dict,
        "volumes": volume_dict,
        "volumes_raw": volume_raw_dict,
        "mesh_tags": mesh_tag_list,
        "volume_tags": volume_tag_list,
        "all_tags": all_tags,
        "mesh_descriptions": mesh_descriptions,
        "volume_descriptions": volume_descriptions,
    }

    print("Creating JSON Files...")
    save_dir = utils.DATABASE_PATHS["process"] / _patient_id / _current_ensemble
    save_dir.mkdir(parents=True, exist_ok=True)

    utils.save_json(merged_data, save_dir / f"{_current_ensemble}_3d_data.json")

    print("Creating JSON Files for individual data...")
    print("tetras_per_vertex...")
    utils.save_json(tetras_per_vertex, save_dir / f"{_current_ensemble}_tetras_per_vertex.json")

    print("triangles_per_vertex...")
    utils.save_json(triangles_per_vertex, save_dir / f"{_current_ensemble}_triangles_per_vertex.json")

    print("all_cell_index_dict...")
    utils.save_json(all_cell_index_dict, save_dir / f"{_current_ensemble}_cell_index_dict.json")

    print("tag_length_dict...")
    utils.save_json(tag_length_dict, save_dir / f"{_current_ensemble}_tag_length_dict.json")

    print("Compressed JSON...")
    compressed_data = zlib.compress(json.dumps(merged_data).encode())
    compressed_file = save_dir / f"{_current_ensemble}_compressed_3d_data.zlib"
    compressed_file.write_bytes(compressed_data)

    return _max_index
