Epilepsy Planning Tool - Backend
================================
**Important:** Before following the instructions step by step, please read through the entire README.

---

## Overview:
This backend handles the pre-processing of the patient's head mesh, execution of ensembles of simulations
and post-processing of the simulation results. All relevant parameters should be set in the Tool's frontend or the ```config.ini``` file in the project's directory.

---

## Prerequisites:
- **Python**: Required for running the backend scripts.
- **Conda (Miniconda)**: Required for installing SimNIBS Python packages.
    - **Installation**: Download and install Miniconda from [here](https://docs.anaconda.com/miniconda/)
- **Docker**: Docker needs to be installed and running. Instructions for installing Docker can be found [here](https://docs.docker.com/get-docker/).
- All commands assume the terminal is opened in the project's root directory (`PlanningTool_Backend`)

---

## Setting up the Docker image:
The SimNIBS simulations used in this project run inside Docker containers.
You can either build the image yourself, using the Dockerfile in the project's directory or pull an existing, functioning image from Docker Hub.

#### Pulling the image from Docker Hub
To pull a working image from Docker Hub, start Docker and pull the image from Docker Hub using:
```sh
docker pull haeisl/simnibs_simulation:latest
```

#### Building the image using the Dockerfile
To build a Docker image for this backend, run:
```bash
docker build --no-cache --build-arg SIMNIBS_VERSION=4.0.1 -t simnibs_simulation:latest .
```
- `--no-cache`: Skip Docker's cache to ensure all layers are rebuilt. Use this only if changes were made to the Dockerfile.

- `--build-arg SIMNIBS_VERSION=<version>`: Set the SimNIBS version (options are 4.0.0, 4.0.1, 4.1.0). The default version is `4.0.1`, which has been tested extensively.

- `-t`: Tag the Docker image. Here, it tags the image as `simnibs_simulation:latest`.

#### Allocating System Resources for Docker with ```.wslconfig```
To ensure efficient performance when running the SimNIBS simulations in Docker, you can allocate more system resources by configuring a ```.wslconfig``` file . This file allows you to specify memory, CPU, and swap space limits for WSL 2, which directly impacts the performance of Docker containers running inside it. You can either read for yourself [here](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) or follow along the next few exemplary steps.

1. **Locate or Create the File**
    The ```.wslconfig``` file should be placed in your user profile directory:
    ```makefile
    C:\Users\YourUsername\.wslconfig
    ```
2. **Modify Resource Allocation**
    Add or update the following lines in ```.wslconfig```:
    ```ini
    [wsl2]
    memory=20GB
    processors=14
    swap=16GB
    ```
    - ```memory=20GB```: Allocates **20GB** of RAM to WSL2, ensuring enough resources for Docker. More is better, but leave enough for your main OS.
    - ```processors=14```: Allocates **14 CPU cores** to improve container processing speed.
    - ```swap=16GB```: Sets up a **16GB swap file**, allowing memory overflow to be stored on disk.

    >**Note:** You obviously have to change these numbers according to your own system. These are just the numbers I use on my PC, your optimal settings may vary.
3. **Restart WSL**
    After saving the ```.wslconfig``` file, restart WSL for the changes to take effect:
    ```sh
    wsl --shutdown
    ```
    When you restart Docker, it will now have access to the allocated resources.

---

## Setting Up the Environment
It is **highly recommended** to set up a conda environment to avoid dependency conflicts.\
Setting up and activating a conda environment can be done like:
```bash
conda create -n planningtoolenv python=3.9.12
conda activate planningtoolenv
conda env update -f environment.yml
```
This will set up a conda environment with most of the dependencies for running the backend.\
The only thing missing is SimNIBS, which needs to be installed via a wheel file.
To install SimNIBS v4.0.1, run the following on Windows machines:
```bash
pip install --no-cache-dir -f https://github.com/simnibs/simnibs/releases/download/v4.0.1/simnibs-4.0.1-cp39-cp39-win_amd64.whl simnibs
```
For Linux or MacOS systems replace the link with:

**Linux:** `https://github.com/simnibs/simnibs/releases/download/v4.0.1/simnibs-4.0.1-cp39-cp39-linux_x86_64.whl`
**MacOS:** `https://github.com/simnibs/simnibs/releases/download/v4.0.1/simnibs-4.0.1-cp39-cp39-macosx_10_11_x86_64.whl`

>**Note:** If you are using Windows, conda environments might not activate correctly in PowerShell. Using the Command Prompt (`cmd.exe`) has proven to be more reliable.

---
## Running the Backend:
Before following the next few steps to start the customized SimNIBS simulations, take a look at the ```config.ini``` file in this directory. In this config file you can:
1. Set up the maximum number of Docker containers to run at a time.
2. Specify the Docker image name to be used for the simulation, if you are deviating from the default.
3. Link to the path where you would like to save the simulation results.
4. Enter the mesh name, if the mesh name and patient ID do not match.

### Step 1: Generate default JSON data from the `.msh` File
Both back- and frontend rely on pre-processed JSON data from the original .msh file. This default data needs to be generated once for each patient. The backend can generate this data, using:
```
python start_backend.py -D /path/to/msh/ -F mesh.msh -I patient_id
```
- `--directory` or `-D`: Specifies the directory containing the mesh file. Replace `/path/to/msh/` with the actual path to your mesh directory.

- `--filename` or `-F`: Specifies the filename of the mesh file to be processed. Replace `mesh.msh` with your actual mesh file name.

- `--patientid` or `-I`: Specifies the patient ID, which should be unique for each patient. Use the same ID if running the same patient's head mesh again.

### Step 2: Start the REST Server
The backend requires a running REST server to communicate with the frontend. To start the server, run:
```
python start_backend.py -S -a 0.0.0.0 -p 5000
```
- `--startserver` or `-S`: Starts the local RESTful server for communicating with the backend.

- `--address` or `-a`: Specifies the IP address to bind the server to. The default is `0.0.0.0`, which listens on all available network interfaces.

- `--port` or `-p`: Specifies the server port. The default port is `5000`.

> **Note:** You can combine the options from **Step 1** and **Step 2** to both process the `.msh` file and start the server in one command. For example:
> ```
>python start_backend.py -D /path/to/msh/ -F mesh.msh -I patient_id -S -a 0.0.0.0 -p 5000
>```


### Step 3: Load Head Mesh and Configure Simulations
With a running server, you can load the head mesh into the frontend using the patient ID. Once the configuration is done via the frontend interface, the backend is ready for simulations.

### Step 4: Running Simulations
After configuring and sending the ensemble data to the backend from the frontend, run the simulation using:
```bash
python run_docker_simulations.py --PatientID Ernie --ConfigID config123 --ROIID roi123
```
- `PatientID`: Specifies the patient ID set during pre-processing.
- `ConfigID`: Specifies the configuration ID for the ensemble, as set in the frontend.
- `ROIID`: Specifies the region of interest (ROI) ID, set in the frontend.

---
## Clean-Up
For particularly lazy people like myself, I have created a script ```remove_post_processing_results.py``` to remove all post-processing results (JSON data) that were generated after all the Docker containers have finished running.
Run this script like:
```sh
python remove_post_processing_results.py
```
This will extract all post-processing results from the ```data_dir``` specified in the ```config.ini``` and lets you specify which data to delete. Supplying the script with the optional ```--dry-run``` flag will not remove any data, rather it will list which files would have been deleted.

---
### Additional Tips & Insights for future developers
There should be extensive documentation about this backend on [readthedocs]() or [GitHubPages]()
TODO: add links

If you need to send a request to the REST server, be it for testing purposes or otherwise, but do not want to do it through the front end (e.g. re-running a previously failed or aborted simulation) you can send one using:
```sh
(Windows)
Invoke-RestMethod -Uri "http://localhost:5000/run_simulations/Ernie/Config0/ROI0" -Method Post

(Linux)
curl -X POST http://localhost:5000/run_simulations/Ernie/Config0/ROI0
```
You can replace the `/run_simulations` part with any other endpoint, same goes for the Patient, Config and ROI IDs.

If you only need to re-run post-processing for an ensemble of simulations, go into `run_docker_simulations.py` and comment line 385: `run_simulations(electrodes, max_containers, image_name, mesh_name, code_path, config_id_json, patient_id_json)`, this will lead to the backend only generating the post-processing JSON files.
This obviously requires that the corresponding simulations have finished in some form.

If you aim to improve the simulation success rate, everything relevant should be inside `Docker_Sim/`, especially in the `functions.py` module, most meshing operations are found here.

If you aim to improve the accuracy of the colormap in the frontend, the answer probably lies inside the `process_simulation/` directory.

glhf

<!--
Old readme
# **SETUP:**
PyCharm recommended.

1. Open "SimNIBS installation via Windows 10 Command Prompt.pdf"
2. Follow only the steps 1, 2, 5 and 6! (Only the Versions which are inside the yml are important)
3. Install all necessary packages with pip. (Use requirements_backend.txt)
4. Build Dockerfile for simulation (Use Docker_Sim Folder)

# **Pipeline:**
1. Create Default Data for Patient with process_original_mesh.py (Define Patient ID)
2. Start application.py
3. Use Frontend to create the configuration data and send it to backend
4. Modify ochester.ps1 to specify how many simulations should run parallel (be careful with the number of threads, it can slow down the system e.g. 4 to 5 simulations require about 32 GB RAM)
5. Start the simulation with the created configuration data (e.g. ./ochester.ps1 -input_file "electrode_positions_En0_4.json") -->
