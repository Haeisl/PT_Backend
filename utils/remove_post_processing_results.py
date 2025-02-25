"""
A utility script to clear or simulate clearing post-processing results from patient and configuration directories.

Notes
-----
This script:
    - Reads a config.ini file to locate a `process_data` directory within a database structure.
    - Identifies and displays patient IDs and associated config IDs.
    - Allows the user to selectively remove files/directories under specific patient/config IDs or remove all.
    - Supports a dry-run mode to simulate removal without actually deleting files.

Examples
--------
  python clear_directory.py --dry-run
"""


import sys
from argparse import ArgumentParser
from configparser import ConfigParser
from pathlib import Path

# Constants for user confirmation
YES_RESPONSES = {"y", "yes"}

# Constants for paths
DATABASE_SUBPATH = "database"
PROCESS_DATA_SUBPATH = "process_data"

# File paths
CONFIG_FILE = "config.ini"
CONFIG_SECTION = "Settings"
CONFIG_OPTION = "data_dir"


def parse_arguments():
    """
    Parse command-line arguments.

    Supported arguments:
      --dry-run: If specified, file removal will only be printed rather than performed.

    Returns
    -------
    argparse.Namespace
        An object with the parsed arguments (dry_run: bool).
    """
    parser = ArgumentParser(description="Clear directories based on user selection.")
    parser.add_argument("--dry-run", action="store_true", help="Print operations without performing them.")
    return parser.parse_args()


def get_process_data_directory_path() -> Path:
    """
    Get the path to the 'process_data' directory from config.ini.

    The config.ini file is expected to have a [Settings] section with a 'data_dir' option.
    The final path is data_dir/database/process_data.

    Returns
    -------
    Path
        A Path object pointing to the 'process_data' directory.

    Raises
    ------
    SystemExit
        If the config file is missing or the specified path does not exist.
    """
    if not Path(CONFIG_FILE).exists():
        print(f"Error: '{CONFIG_FILE}' file is missing.")
        sys.exit(1)

    # Read the config file
    config = ConfigParser()
    config.read(CONFIG_FILE)

    # Retrieve the path as a string
    try:
        data_dir_string = config.get(CONFIG_SECTION, CONFIG_OPTION)
    except Exception as e:
        print(f"Error reading {CONFIG_FILE}: {e}")
        sys.exit(1)

    # Convert the string to a Path object
    data_dir = Path(data_dir_string)

    # Check whether the path is valid
    if not data_dir.is_dir():
        print(f"Specified path in '{CONFIG_FILE}' ({data_dir_string}) does not exist.")
        sys.exit(1)

    # Navigate to data_dir/database/process_data
    process_data = data_dir / DATABASE_SUBPATH / PROCESS_DATA_SUBPATH

    # Check if that path exists
    if not process_data.is_dir():
        print(f"No '{PROCESS_DATA_SUBPATH}' directory found at {process_data.as_posix()}.")
        sys.exit(1)

    return process_data


def get_all_patient_ids_and_configs(process_data: Path) -> dict:
    """
    Identify available patient IDs and config IDs under the 'process_data' directory.

    This function inspects the subdirectories of `process_data`, assuming each subdirectory name
    is a patient ID, and each subdirectory under that is a config ID.

    Parameters
    ----------
    process_data : Path
        A Path object pointing to the 'process_data' directory.

    Returns
    -------
    dict
        A dict mapping patient IDs (keys) to lists of config IDs (values).
    """
    # The names of the subdirectories of 'process_data' are the patient IDs
    # The names of the subdirectories of the patient ID directories are the config IDs
    return {
        subdir.name: [sub.name for sub in subdir.iterdir() if sub.is_dir()]
        for subdir in process_data.iterdir() if subdir.is_dir()
    }


def clear_directory(path: Path, dry_run: bool = False) -> None:
    """
    Recursively remove files and directories under a given path.

    Parameters
    ----------
    path : Path
        The top-level directory to be cleared.
    dry_run : bool, optional
        If True, prints the items that would be deleted without actually deleting them.
    """
    for item in path.iterdir():
        try:
            if item.is_dir():
                # Recursively remove the directory
                clear_directory(item, dry_run=dry_run)
                if not dry_run:
                    item.rmdir() # Remove the now empty directory
            else:
                if not dry_run:
                    item.unlink() # Remove the file
            if dry_run:
                print(f"Would delete: {item}")
        except Exception as e:
            print(f"Error deleting {item}: {e}")
            sys.exit(1)


def user_clear_directory(path: Path, dry_run: bool = False) -> None:
    """
    Prompt user for confirmation before clearing a directory.

    Parameters
    ----------
    path : Path
        The directory to clear.
    dry_run : bool, optional
        If True, simulate deletion rather than actually removing files.

    Raises
    ------
    SystemExit
        If the user declines to proceed.
    """
    action = "Would remove" if dry_run else "About to remove"
    print(f"\n{action} everything in {path}.")
    final_choice = input("Proceed? Yes/No: ")
    if final_choice.lower() in YES_RESPONSES:
        print("Deleting..." if not dry_run else "Simulating deletion...")
        clear_directory(path, dry_run=dry_run)
    else:
        print("Aborting.")
        sys.exit(0)


def main() -> None:
    """
    Main entry point to prompt for and execute (or simulate) directory clearing tasks.

    **Workflow:**

        1. Parse arguments for a possible dry-run.
        2. Confirm user intent to remove post-processing results.
        3. Determine the 'process_data' directory from the config file.
        4. Enumerate patient IDs and config IDs.
        5. Prompt user for selection to remove:

            - a specific patient/config pair,
            - all configs under a patient,
            - or all data under 'process_data'.

        6. Perform or simulate the removal based on user choice.
    """
    args = parse_arguments()
    dry_run = args.dry_run

    print("You are about to irreversibly remove post-processing results.")
    cont_choice = input("Continue? Yes/No: ").strip().lower()

    if cont_choice not in YES_RESPONSES:
        print("Aborting.")
        sys.exit(0)

    process_data = get_process_data_directory_path()

    patient_id_config_dict = get_all_patient_ids_and_configs(process_data)

    # Print all Patient IDs and associated config IDs
    print("\nThese patient and config IDs have been found:")
    for i, (patient_id, config_ids) in enumerate(patient_id_config_dict.items(), start=1):
        print(f"{i}. {patient_id}:")
        for config_id in config_ids:
            print(f"  - {config_id}")

    print("\nYou can:")
    print("- Enter a pair like 'Patient123, Config123' without quotes to select a specific pair for removal")
    print("- Enter a patient ID like 'Patient123' without quotes to select all configs for the specified patient for removal")
    print("- Type 'all' to select everything")
    print("- Anything else to abort")

    removal_choice = input("\nRemove: ").strip()

    if removal_choice.lower() == "all":
        path = process_data
        user_clear_directory(path, dry_run=dry_run)
    elif "," in removal_choice:
        parts = removal_choice.split(",", 1)

        if len(parts) != 2 or not all(parts):
            print("Invalid input format. Use 'Patient123, Config123'.")
            sys.exit(1)

        patient_id = parts[0].strip()
        config_id = parts[1].strip()

        if patient_id in patient_id_config_dict and config_id in patient_id_config_dict[patient_id]:
            path = process_data / patient_id / config_id
            user_clear_directory(path, dry_run=dry_run)
        else:
            print("Invalid pair. Aborting process.")
            sys.exit(1)
    elif removal_choice in patient_id_config_dict:
        path = process_data / removal_choice
        user_clear_directory(path, dry_run=dry_run)
    else:
        print("Aborting.")
        sys.exit(0)

    print("Done!")


if __name__ == "__main__":
    main()