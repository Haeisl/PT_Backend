import json
from pathlib import Path
from typing import Any

def load_json(file_path: Path) -> dict:
    """
    Load JSON content from a given file path.

    Parameters
    ----------
    file_path : Path
        A Path object from which to load JSON data.

    Returns
    -------
    dict
        A dictionary containing the parsed JSON data.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    json.JSONDecodeError
        If the file contains invalid JSON.
    OSError
        For any underlying I/O error.
    """
    print(f"Loading: {file_path}")
    try:
        data = json.loads(file_path.read_text())
        print(f"Successfully read JSON data from: {file_path}")
        return data
    except FileNotFoundError as e:
        print(f"File not found: {file_path}\nError: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in file: {file_path}\nError: {e}")
        raise
    except OSError as e:
        print(f"I/O error({e.errno}): {e.strerror}")
        raise

def save_json(data: Any, file_path: Path) -> None:
    """
    Save data in JSON format at the specified file path.

    Parameters
    ----------
    data : Any
        A Python object (e.g., dict or list) to be serialized as JSON.
    file_path : Path
        A Path object where the JSON file should be saved.

    Returns
    -------
    None

    Raises
    ------
    TypeError
        If `data` is not JSON-serializable.
    OSError
        For any underlying I/O error.
    """
    try:
        file_path.write_text(json.dumps(data))
        print(f"Successfully saved JSON to: {file_path}")
    except TypeError as e:
        print(f"Data provided is not JSON serializable: {e}")
        raise
    except OSError as e:
        print(f"I/O error({e.errno}): {e.strerror}")
        raise