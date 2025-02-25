"""
Entry point for processing mesh files and optionally starting a Flask-based server.

This script uses command-line arguments to:
    - Convert a mesh file to JSON for a given patient.
    - Start the web server if requested.

Examples
--------
::

    $ python main.py -S -D /path/to/meshdir -F meshfile.msh -I Patient123 -a 0.0.0.0 -p 8080

Notes
-----
Dependencies:
    - argparse for command-line interface
    - waitress for serving the Flask app
    - simnibs.mesh_tools for reading .msh files
    - process_simulations for the JSON conversion logic
"""


import argparse
from pathlib import Path
import sys

from simnibs import mesh_tools
from waitress import serve

import server
from process_simulations.process_original_mesh import convert_mesh_to_json


def process(directory: str, filename: str, patient_id: str) -> None:
    """
    Convert a .msh file into JSON format for a given patient.

    This function reads a SimNIBS .msh file from the specified directory and filename,
    and invokes a conversion utility to create a JSON representation of the mesh data.

    Parameters
    ----------
    directory : str
        The directory containing the .msh file.
    filename : str
        The name of the .msh file (e.g. 'ernie_my.msh').
    patient_id : str
        A string ID representing the patient or subject.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    """
    full_path = Path(directory) / filename

    if not full_path.exists():
        print(f"Passed file path: {full_path} does not exist.")
        raise FileNotFoundError

    mesh_raw = mesh_tools.read_msh(full_path)
    convert_mesh_to_json(mesh_raw, patient_id)


def main() -> None:
    """
    Parse command-line arguments and orchestrate mesh processing or server startup.

    This function:
        - Defines command-line arguments for directory, filename, patient ID, server address, and port.
        - Processes the mesh file if the required arguments (directory, filename, patient ID) are provided.
        - Optionally starts the Flask-based server via waitress if the --startserver flag is used.

    Returns
    -------
    None
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-S", "--startserver", action="store_true",
        help="Flag to indicate whether the server should be started."
    )

    parser.add_argument(
        "-D", "--directory", type=str,
        help="The directory where the mesh file is located."
    )

    parser.add_argument(
        "-F", "--filename", type=str,
        help="The name of the mesh file. Default is 'ernie_my.msh'."
    )

    parser.add_argument(
        "-I", "--patientid", type=str,
        help="The patient ID corresponding to the mesh. Default is 'Ernie'."
    )

    parser.add_argument(
        "-a", "--address", type=str, default="127.0.0.1",
        help="The IP address to bind to."
    )

    parser.add_argument(
        "-p", "--port",type=int,default=5000,
        help="The port to bind to."
    )

    args = parser.parse_args()

    if args.directory and args.filename and args.patientid:
        try:
            process(args.directory, args.filename, args.patientid)
        except Exception:
            print(f"Unable to process {args.filename} in {str(Path(args.directory).absolute())} for {args.patientid}")
            raise
    elif any([args.directory, args.filename, args.patientid]):
        missing_args = []
        if not args.directory:
            missing_args.append("'--directory' or '-D'")
        if not args.filename:
            missing_args.append("'--filename' or '-F'")
        if not args.patientid:
            missing_args.append("'--patientid' or '-I'")

        print("Missing arguments for pre-processing:")
        print(f"{', '.join(missing_args)}")
        sys.exit(1)

    if args.startserver:
        try:
            print(f"Server starting at {args.address}:{args.port}...")
            print("The server can be terminated with CTRL + C.")
            serve(server.app, host=args.address, port=args.port)
        except Exception:
            print(f"Failed to start the server at {args.address}:{args.port}")
            raise


if __name__ == "__main__":
    main()