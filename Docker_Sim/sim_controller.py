import json
import logging
import logging.config
import logging.handlers
import os
import sys
import warnings
from pathlib import Path

import simulation

import logging_utils

logging.config.fileConfig(Path("./logging.conf").as_posix()) # .. for documentation builds, . for running
logging.captureWarnings(True)
logger = logging.getLogger("planningtool")


def log_warning(message, category, filename, lineno, file=None, line=None):
    logger = logging.getLogger("warnings")
    logger.warning(f"{filename}: {category.__name__}: {message} [Line {lineno}]")


warnings.showwarning = log_warning


def print_environment_info() -> None:
    """
    Print environment information such as Conda environment and Python version.

    This function retrieves the current Conda environment (if any) from the
    environment variable CONDA_DEFAULT_ENV and the Python version from sys.version,
    then logs the information.

    Returns
    -------
    None
    """
    conda_env = os.environ.get("CONDA_DEFAULT_ENV", "Not in a Conda environment")
    python_version = sys.version
    logger.info(f"Conda Environment: {conda_env}\nPython version: {python_version}")


def create_sim_info_file(running: bool, success: bool) -> None:
    """
    Create or update a JSON file with simulation status information.

    This function uses environment variables (VOLUME_PATH, ENSEMBLE_NAME, ELECTRODE_NAME,
    ELECTRODE_POSITION_X/Y/Z) to construct a JSON file named 'sim_info_<electrode>.json'.
    It updates the file with details about the simulation status (running/success).

    Parameters
    ----------
    running : bool
        A boolean indicating whether the simulation is currently running.
    success : bool
        A boolean indicating whether the simulation has completed successfully.

    Returns
    -------
    None
        The JSON file is written to disk.
    """
    volume_path = os.environ.get("VOLUME_PATH", "")
    ensemble_name = os.environ.get("ENSEMBLE_NAME", "")
    electrode_name = os.environ.get("ELECTRODE_NAME", "")
    electrode_pos_x = os.environ.get("ELECTRODE_POSITION_X", "")
    electrode_pos_y = os.environ.get("ELECTRODE_POSITION_Y", "")
    electrode_pos_z = os.environ.get("ELECTRODE_POSITION_Z", "")

    file_path = Path(volume_path) / ensemble_name / f"sim_info_{electrode_name}.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = {
        "ensemble_name": ensemble_name,
        "path": volume_path,
        "running": running,
        "success": success,
        "Environment": os.environ.get("CONDA_DEFAULT_ENV", "Not in a Conda environment"),
        "Electrode": {
            "name": electrode_name,
            "X": electrode_pos_x,
            "Y": electrode_pos_y,
            "Z": electrode_pos_z,
        }
    }

    try:
        with file_path.open("w") as file:
            json.dump(content, file, indent=4)
        logger.info(f"Successfully saved JSON to: {file_path}")
    except Exception as e:
        logger.info(f"Error saving JSON to file: {file_path}, Error: {str(e)}")


def main():
    """
    Main entry point for the simulation script.

    This function:
        - Registers a custom excepthook for global exception handling.
        - Logs an initial simulation info file indicating the simulation is running.
        - Prints environment information.
        - Calls the simulation logic (simulation.simulate()).
        - Updates the simulation info file upon completion.
        - Unregisters the custom excepthook.

    Returns
    -------
    None
    """
    logging_utils.register_excepthook(logger)

    create_sim_info_file(True, False)

    print_environment_info()

    simulation.simulate()

    create_sim_info_file(False, True)

    logging_utils.unregister_excepthook()


if __name__ == "__main__":
    main()

# def run_simulation() -> None:
#     logger.info("Running simulation")
#     simulation.simulate()