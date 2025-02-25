"""
This module processes regions of interest (ROI) within 3D simulation data.
It includes functions to check if vertices are inside a cube, filter data based on value counts,
and map data to specific ROIs.

Functions
---------
    - is_inside_cube : Check if a vertex is inside the cube defined by cube vertices.
    - get_vertices_inside_cube : Get the indices of the vertices that are inside the cube.
    - load_data_from_json : Load data from a JSON file.
    - get_tetras_per_vertex_in_roi : Get the tetrahedra per vertex that are inside the ROI.
    - get_unique_tetras_in_roi : Get unique tetrahedra in the ROI.
    - get_indices_per_tag_in_roi : Get indices per tag in the ROI.
    - filter_dict_by_value_count : Filter a dictionary by the count of values.
    - create_roi_mask : Create a mask for the region of interest (ROI).
    - extract_values : Extract values from the electrode dictionary based on ROI indices and store them in the extracted dictionary.
    - map_data_to_roi : Map simulation data to a region of interest (ROI) and create a JSON file with the mapped data.
    - build_vertex_tag_index_structure : Build a vertex tag index structure for the region of interest (ROI).

Dependencies
------------
    - json : For reading and writing JSON files.
    - os : For file and directory operations.
    - zlib : For compressing data.
    - collections.Counter : For counting occurrences of values.
    - numpy : For numerical operations and statistics.
    - database_params : Custom module for database parameters and paths.
"""

import json
import zlib
from collections import Counter

import numpy as np
from scipy.spatial import Delaunay

import utils


def is_cuboid(points):
    """Check if eight points form a rectangular cuboid."""

    return True
    # Check for uniqueness
    unique_points = np.unique(points, axis=0)
    if len(unique_points) != 8:
        print("Points are not unique.")
        return False

    return True
    # Implement more tests as needed.
    # Probably not needed, as ROI can't be anything else than a cuboid because it's defined as such in the frontend


def get_vertices_inside_cube(vertices: np.ndarray, cube_vertices: np.ndarray) -> list[int]:
    """
    Get the indices of the vertices that are inside the cube.

    Parameters
    ----------
    vertices : numpy.ndarray
        A 2D numpy array where each row represents a vertex in the mesh.
    cube_vertices : numpy.ndarray
        A 2D numpy array where each row represents a vertex of the cube.

    Returns
    -------
    list
        A list of indices of the vertices that are inside the cube.
    """
    if not is_cuboid(cube_vertices):
        raise ValueError("Cube vertices do not form a valid cuboid.")

    # Create a Delaunay triangulation of the cuboid vertices
    delaunay = Delaunay(cube_vertices)

    vertices_inside_cube = []
    for i, vertex in enumerate(vertices):
        # Find the simplex that contains the point
        simplex = delaunay.find_simplex(vertex)
        # simplex >= 0 means the point is inside the cuboid
        if simplex >= 0:
            vertices_inside_cube.append(i)  # Store the index of the vertex
    print(f"\n\n{len(vertices_inside_cube)}\n\n")
    return vertices_inside_cube


def get_tetras_per_vertex_in_roi(tetras_per_vertex: dict, vertices_in_roi: list) -> dict:
    """
    Get the tetrahedra per vertex that are inside the ROI.

    Parameters
    ----------
    tetras_per_vertex : dict
        Dictionary of tetrahedra per vertex.
    vertices_in_roi : list
        List of vertices inside the ROI.

    Returns
    -------
    dict
        Dictionary of tetrahedra per vertex inside the ROI.
    """
    unique_vertices_in_roi = {str(x) for x in vertices_in_roi}
    tetras_per_vertex_in_roi = {str(k): v for k, v in tetras_per_vertex.items() if k in unique_vertices_in_roi}
    return tetras_per_vertex_in_roi


def get_unique_tetras_in_roi(tetras_per_vertex_in_roi: dict) -> np.ndarray:
    """
    Get unique tetrahedra in the ROI.

    Parameters
    ----------
    tetras_per_vertex_in_roi : dict
        Dictionary of tetrahedra per vertex inside the ROI.

    Returns
    -------
    numpy.ndarray
        Array of unique tetrahedra in the ROI.
    """
    unique_tetras = []
    for values in tetras_per_vertex_in_roi.values():
        unique_tetras.append(values[1])
    return np.unique(unique_tetras).tolist()


def get_indices_per_tag_in_roi(_unique_tetras: np.ndarray, _cell_id_per_tag: dict) -> dict:
    """
    Get indices per tag in the ROI.

    Parameters
    ----------
    _unique_tetras : numpy.ndarray
        Array of unique tetrahedra in the ROI.
    _cell_id_per_tag : dict
        Dictionary of cell IDs per tag.

    Returns
    -------
    dict
        Dictionary of indices per tag in the ROI.
    """
    # Initialize the result dictionary
    _indices_per_tag_in_roi = {}

    # Iterate over tags and their associated indices
    for tag, indices in _cell_id_per_tag.items():  # {"2": [2, 1, 0], "1": [3], "3": [5, 4]}
        for index in indices:
            if index in _unique_tetras:
                actual_index = indices.index(index)
                _indices_per_tag_in_roi.setdefault(tag, []).append(actual_index)
    return _indices_per_tag_in_roi


def filter_dict_by_value_count(dictionary: dict, count: int) -> dict:
    """
    Filter a dictionary by the count of values.

    Parameters
    ----------
    dictionary : dict
        Dictionary to filter. Each value is expected to be a list of lists.
    count : int
        Minimum count of occurrences for each value.

    Returns
    -------
    dict
        Filtered dictionary.
    """
    all_values = []
    for _list in dictionary.values():
        for _values in _list:
            all_values.extend(_values[0])

    value_counts = Counter(all_values)
    filtered_dict = {}

    for key, _list in dictionary.items():
        # Filter based on the count condition
        for _value in _list:
            if all(value_counts.get(index, 0) >= count for index in _value[0]):
                filtered_dict[key] = _value

    return filtered_dict


def create_roi_mask(_config_id: str, _patient_id: str, _roi_id: str) -> None:
    """
    Create a mask for the region of interest (ROI).

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
    path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id
    path_roi = path / _roi_id
    path_roi.mkdir(parents=True, exist_ok=True)

    print("Loading vertices...")
    geometry_data = utils.load_json(path / f"{_config_id}_3d_data.json")
    vertices = np.array(geometry_data["vertices"])
    meshes = geometry_data["meshes"]
    volumes_raw = geometry_data["volumes_raw"]

    print("Loading roi_bounds...")
    roi_bounds_dict = utils.load_json(utils.DATABASE_PATHS["roi"] / _patient_id / f"{_roi_id}_roi_bounds.json")
    roi_bounds = np.array(roi_bounds_dict["Bounds"])

    print("Processing vertex_indices_in_roi ...")
    vertex_indices_in_roi = get_vertices_inside_cube(vertices, roi_bounds)

    print("Saving vertex_indices_in_roi ...")
    utils.save_json(vertex_indices_in_roi, path_roi / f"{_roi_id}_vertex_indices_in_roi.json")

    print("Loading tetras_per_vertex ...")
    tetra_per_vertex = utils.load_json(path / f"{_config_id}_tetras_per_vertex.json")

    print("Processing tetras_per_vertex_in_roi ...")
    tetras_per_vertex_in_roi = get_tetras_per_vertex_in_roi(tetra_per_vertex, vertex_indices_in_roi)

    print("Filtering tetras_per_vertex_in_roi ...")
    # Only where all vertices are inside the cube
    tetras_per_vertex_in_roi = filter_dict_by_value_count(tetras_per_vertex_in_roi, 4)

    print("Saving tetras_per_vertex_in_roi ...")
    utils.save_json(tetras_per_vertex_in_roi, path_roi / f"{_roi_id}_tetras_per_vertex_in_roi.json")

    print("Loading triangles_per_vertex ...")
    triangles_per_vertex = utils.load_json(path / f"{_config_id}_triangles_per_vertex.json")

    print("Processing triangles_per_vertex_in_roi ...")
    triangles_per_vertex_in_roi = get_tetras_per_vertex_in_roi(triangles_per_vertex, vertex_indices_in_roi)

    print("Filtering triangles_per_vertex_in_roi ...")
    # Only where all vertices are inside the cube
    triangles_per_vertex_in_roi = filter_dict_by_value_count(triangles_per_vertex_in_roi, 3)

    print("Saving triangles_per_vertex_in_roi ...")
    utils.save_json(triangles_per_vertex_in_roi, path_roi / f"{_roi_id}_triangles_per_vertex_in_roi.json")

    print("Processing unique_tetras_in_roi ...")
    unique_tetras_in_roi = get_unique_tetras_in_roi(tetras_per_vertex_in_roi)

    print("Saving unique_tetras_in_roi ...")
    utils.save_json(unique_tetras_in_roi, path_roi / f"{_roi_id}_unique_tetras_in_roi.json")

    print("Processing unique_triangles_in_roi ...")
    unique_triangles_in_roi = get_unique_tetras_in_roi(triangles_per_vertex_in_roi)

    print("Saving unique_triangles_in_roi ...")
    utils.save_json(unique_triangles_in_roi, path_roi / f"{_roi_id}_unique_triangles_in_roi.json")

    print("Loading cell_index_dict ...")
    cell_index_dict = utils.load_json(path / f"{_config_id}_cell_index_dict.json")

    print("Processing indices_per_tag_in_roi ...")
    indices_per_tag_in_roi = get_indices_per_tag_in_roi(unique_tetras_in_roi, cell_index_dict)
    indices_per_tag_in_roi.update(get_indices_per_tag_in_roi(unique_triangles_in_roi, cell_index_dict))

    print("Saving indices_per_tag_in_roi ...")
    utils.save_json(indices_per_tag_in_roi, path_roi / f"{_roi_id}_indices_per_tag_in_roi.json")

    print("Processing volume_vertex_tag_index_mapping ...")
    volume_vertex_tag_index_mapping = build_vertex_tag_index_structure(volumes_raw, indices_per_tag_in_roi)

    print("============================ Volume ============================")
    print(len(volume_vertex_tag_index_mapping))
    print("================================================================")

    print("Saving volume_vertex_tag_index_mapping ...")
    utils.save_json(volume_vertex_tag_index_mapping, path_roi / f"{_roi_id}_volume_vertex_tag_index_mapping.json")

    print("Processing mesh_vertex_tag_index_mapping ...")
    mesh_vertex_tag_index_mapping = build_vertex_tag_index_structure(meshes, indices_per_tag_in_roi, False)

    print("============================ Mesh ============================")
    print(len(mesh_vertex_tag_index_mapping))
    print("==============================================================")

    print("Saving mesh_vertex_tag_index_mapping ...")
    utils.save_json(mesh_vertex_tag_index_mapping, path_roi / f"{_roi_id}_mesh_vertex_tag_index_mapping.json")


def extract_values(electrode_dict: dict, roi_indices_dict: dict, extracted_dict: dict, key: str) -> None:
    """
    Extract values from the electrode dictionary based on ROI indices and store them in the extracted dictionary.

    Parameters
    ----------
    electrode_dict : dict
        Dictionary containing electrode data.
    roi_indices_dict : dict
        Dictionary containing indices of the region of interest (ROI).
    extracted_dict : dict
        Dictionary to store the extracted values.
    key : str
        Key to identify the data type (e.g., "Magnitude" or "Vectorfield").

    Returns
    -------
    None
    """
    for tag_key, tag_values in electrode_dict[key].items():
        current_indices_arr = roi_indices_dict.get(tag_key)
        if current_indices_arr is not None:  # Ensure that the key exists in the dictionary
            # Extract values based on the ROI indices
            extracted_dict[tag_key] = [tag_values[i] for i in current_indices_arr]
        else:
            extracted_dict[tag_key] = {}


def map_data_to_roi(_config_id: str, _patient_id: str, _roi_id: str) -> None:
    """
    Map simulation data to a region of interest (ROI) and create a JSON file with the mapped data.

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
    path = utils.DATABASE_PATHS["process"] / _patient_id / _config_id
    path_roi = path / _roi_id

    print("Loading data ...")
    data_file_path = path / f"{_config_id}_data.json"
    data_dict = utils.load_json(data_file_path)

    print("Loading roi_indices ...")
    roi_indices_path = path_roi / f"{_roi_id}_indices_per_tag_in_roi.json"
    roi_indices_dict = utils.load_json(roi_indices_path)

    # Create new dictionaries to store the extracted data
    merge_data_dict = {}

    print("Extracting data ...")
    for key, electrode_dict in data_dict["Electrodes"].items():
        extracted_field_dict = {}
        extracted_magn_dict = {}
        # Extract magnitude and vector field data based on ROI indices
        extract_values(electrode_dict, roi_indices_dict, extracted_magn_dict, "Magnitude")
        extract_values(electrode_dict, roi_indices_dict, extracted_field_dict, "Vectorfield")

        merge_data_dict.setdefault(key, {"Vectorfield": extracted_field_dict, "Magnitude": extracted_magn_dict})

    roi_data_dict = {}
    roi_data_dict.setdefault("Electrodes", merge_data_dict)

    print("Adding Index Mapping ...")
    roi_data_dict.setdefault("Index_Mapping", roi_indices_dict)

    print("Adding Tag Length ...")
    tag_length_dict = utils.load_json(path / f"{_config_id}_tag_length_dict.json")
    roi_data_dict.setdefault("Tag_Length", tag_length_dict)

    print("Adding Vertex Tag Index Mapping ...")
    volume_vertex_tag_index_mapping = utils.load_json(path_roi / f"{_roi_id}_volume_vertex_tag_index_mapping.json")
    roi_data_dict.setdefault("Volume_Vertex_Tag_Mapping", volume_vertex_tag_index_mapping)

    print("Adding Mesh Tag Index Mapping ...")
    mesh_vertex_tag_index_mapping = utils.load_json(path_roi / f"{_roi_id}_mesh_vertex_tag_index_mapping.json")
    roi_data_dict.setdefault("Mesh_Vertex_Tag_Mapping", mesh_vertex_tag_index_mapping)

    print("Creating JSON ...")
    utils.save_json(roi_data_dict, path_roi / f"{_roi_id}_roi_data.json")

    print("Compressing JSON ...")
    # Compress JSON data with zlib
    compressed_data = zlib.compress(json.dumps(roi_data_dict).encode())
    # Save compressed data to a file
    compressed_file = path_roi / f"{_roi_id}_compressed_roi_data.zlib"
    compressed_file.write_bytes(compressed_data)


def build_vertex_tag_index_structure(_vertex_indices_data: dict, _indices_per_tag_in_roi: dict, bIsTetra=True) -> dict:
    """
    Build a vertex tag index structure for the region of interest (ROI).

    Parameters
    ----------
    _vertex_indices_data : dict
        Dictionary containing vertex indices data.
    _indices_per_tag_in_roi : dict
        Dictionary containing indices per tag in the ROI.
    bIsTetra : bool, optional
        Flag indicating if the data is for tetrahedra (default is True).

    Returns
    -------
    dict
        Vertex tag index structure.
    """
    # Initialize the final data structure
    _vertex_tag_index_structure = {}

    # Define valid tags based on whether the data is for tetrahedra or not
    if bIsTetra:
        valid_tags = {"1", "2", "3", "6", "8", "9", "10"}
    else:
        valid_tags = {"1001", "1002", "1003", "1006", "1008", "1009", "1010"}

    # Iterate over the indices per tag in the ROI
    for tag, indices in _indices_per_tag_in_roi.items():
        # Skip tags that are not valid
        if tag not in valid_tags:
            continue

        # Retrieve cells based on the indices
        cells = [_vertex_indices_data[tag][index] for index in indices]

        # Process each cell and its corresponding index
        for cell, index in zip(cells, indices):
            for vertex_index in cell:
                if vertex_index not in _vertex_tag_index_structure.keys():
                    _vertex_tag_index_structure[vertex_index] = {}
                if tag not in _vertex_tag_index_structure[vertex_index].keys():
                    _vertex_tag_index_structure[vertex_index][tag] = []
                _vertex_tag_index_structure[vertex_index][tag].append(index)

    return _vertex_tag_index_structure
