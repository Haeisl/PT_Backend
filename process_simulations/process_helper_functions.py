"""
This module provides helper functions for processing simulation data.
It includes functions to create tag-based dictionaries, validate tags,
generate lookup tables for tags, and check for numpy ndarrays in data structures.

Functions
---------
    - is_valid_tag : Check if a tag is valid based on predefined criteria.
    - create_tag_based_dictionary : Create a dictionary based on tags and their corresponding data.
    - create_tag_look_up_table : Create a lookup table for tags with their descriptions.
    - create_tag_look_up_table_default : Create a default lookup table for tags with their descriptions.
    - custom_switch : Return the description for a given tag.
    - custom_switch_default : Return the default description for a given tag.
    - check_for_ndarrays : Recursively check for numpy ndarrays in a data structure.

Dependencies
------------
    - numpy : For numerical operations and handling numpy ndarrays.
"""

import numpy as np


def is_valid_tag(str_tag: str) -> bool:
    """
    Check if a tag is valid based on predefined criteria.

    Parameters
    ----------
    str_tag : str
        Tag as a string.

    Returns
    -------
    bool
        True if the tag is valid, False otherwise.
    """
    return str_tag not in ["1004", "4", "100", "1005", "7", "5"] and not str_tag.startswith(("50", "150", "210"))


def create_tag_based_dictionary(tags: list, tag_data: list) -> tuple:
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
    tuple
        Dictionary of tags and their data, and list of used tags.
    """
    meshes_dict = {}
    used_tags = set()

    print("Building Dictionary... ")
    for tag, data in zip(tags, tag_data):
        str_tag = str(tag)
        if is_valid_tag(str_tag):
            # If data is a numpy ndarray, convert it to a list
            if isinstance(data, np.ndarray):
                data = data.tolist()
            meshes_dict.setdefault(str_tag, []).append(data)

    for key, value in meshes_dict.items():
        meshes_dict[key] = value[::-1]
        used_tags.add(int(key))

    used_tags = sorted(list(used_tags))

    return meshes_dict, list(map(str, used_tags))


def create_tag_look_up_table(tags: list) -> list:
    """
    Create a lookup table for tags with their descriptions.

    Parameters
    ----------
    tags : list
        List of tags.

    Returns
    -------
    list
        List of descriptions corresponding to the tags.
    """
    descriptions = []
    for tag in tags:
        descriptions.append(custom_switch(str(tag)))
    return descriptions


def create_tag_look_up_table_default(tags: list) -> list:
    """
    Create a default lookup table for tags with their descriptions.

    Parameters
    ----------
    tags : list
        List of tags.

    Returns
    -------
    list
        List of default descriptions corresponding to the tags.
    """
    descriptions = []
    for tag in tags:
        descriptions.append(custom_switch_default(str(tag)))
    return descriptions


def custom_switch(x: str) -> str:
    """
    Return the description for a given tag.

    Parameters
    ----------
    x : str
        Tag as a string.

    Returns
    -------
    str
        Description of the tag.
    """
    return {
        "1": "WM",
        "2": "GM",
        "3": "CSF",
        "4": "Electrode Isolation",
        "5": "Compact Bone",
        "6": "Eyeballs",
        "7": "Skin",
        "8": "Spongy Bone",
        "9": "Blood",
        "10": "Muscle",
        "501": "Electrode 1501",
        "502": "Electrode 1502",
        "503": "Electrode 1503",
        "504": "Electrode 1504",
        "505": "Electrode 1505",
        "100": "Electrode Rubber",
        "1001": "WM",
        "1002": "GM",
        "1003": "CSF",
        "1004": "Electrode Isolation",
        "1005": "Compact Bone",
        "1006": "Eyeballs",
        "1008": "Spongy Bone",
        "1009": "Blood",
        "1010": "Muscle",
        "1501": "Electrode 1501",
        "1502": "Electrode 1502",
        "1503": "Electrode 1503",
        "1504": "Electrode 1504",
        "1505": "Electrode 1505",
        "2101": "Electrode 2101",
        "2102": "Electrode 2102",
        "2103": "Electrode 2103",
        "2104": "Electrode 2104",
        "2105": "Electrode 2105",
    }.get(x, f"{x} NOT FOUND")


def custom_switch_default(x: str) -> str:
    """
    Return the default description for a given tag.

    Parameters
    ----------
    x : str
        Tag as a string.

    Returns
    -------
    str
        Default description of the tag.
    """
    return {
        "1001": "WM",
        "1002": "GM",
        "1003": "CSF",
        "1005": "Skin",
        "1006": "Eyeballs",
        "1007": "Compact Bone",
        "1008": "Spongy Bone",
        "1009": "Blood",
        "1010": "Muscle",
    }.get(x, f"{x} NOT FOUND")
