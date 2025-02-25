# Use the official miniconda3 base imgage
FROM continuumio/miniconda3:23.10.0-1

# Define the version of SimNIBS to be used; should be 4.0.0 or 4.0.1 or 4.1.0
ARG SIMNIBS_VERSION="4.0.1"

# Set the working directory to /app
WORKDIR /app

# Copy the environment file for the specified SimNIBS version
COPY Docker_Sim/environments/environment_linux_${SIMNIBS_VERSION}.yml .

# Install required system dependencies (OpenGL, GLFW, X11, etc.)
RUN apt-get update && apt-get install -y \
    mesa-utils \
    libgl1-mesa-glx \
    libgl1-mesa-dev \
    libglfw3 \
    libglfw3-dev \
    libxcursor1 \
    libxft-dev \
    libxinerama-dev \
    libxrandr-dev \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

# Create a Conda environment using the provided environment_{version}.yml file
RUN conda env create -f environment_linux_${SIMNIBS_VERSION}.yml \
    && conda clean --all --yes \
    && rm -rf /opt/conda/pkgs/*

# Use the Conda environment "simnibs_env" for all subsequent commands
SHELL [ "conda", "run", "-n", "simnibs_env", "/bin/bash", "-c" ]

# Automatically activate the simnibs_env environment in future shells
RUN echo "conda activate simnibs_env" >> ~/.bashrc

# Set the environment variables to ensure the correct Conda environment is used
ENV PATH=/opt/conda/envs/simnibs_env/bin:$PATH
ENV CONDA_DEFAULT_ENV=simnibs_env

# Install SimNIBS Python package from the specified version's release
RUN pip install --no-cache-dir -f https://github.com/simnibs/simnibs/releases/download/v${SIMNIBS_VERSION}/simnibs-${SIMNIBS_VERSION}-cp39-cp39-linux_x86_64.whl simnibs \
    && rm -rf ~/.cache/pip

# Set application-specific environment variables
ENV PYTHONPATH=/app
ENV ELECTRODE_POSITION_X=0
ENV ELECTRODE_POSITION_Y=0
ENV ELECTRODE_POSITION_Z=0
ENV VOLUME_PATH=/data
ENV ELECTRODE_NAME="NO_NAME"
ENV ENSEMBLE_NAME="DEFAULT"
ENV MESH_NAME="NO_NAME"

# Run the main application using the specified Conda environment
CMD ["conda", "run", "--no-capture-output", "-n", "simnibs_env", "python", "/app/Docker_Sim/sim_controller.py"]

# Building this file:
# docker build --no-cache -t simnibs_simulation:dev

# Usage instructions for running a container with volume and environment variables
# docker run -v /path/to/local/code:/app -v /path/to/simulation/result/data:/data
#   -e ELECTRODE_POSITION_X=X
#   -e ELECTRODE_POSITION_Y=Y
#   -e ELECTRODE_POSITION_Z=Z
#   -e ELECTRODE_NAME="electrode name"
#   -e ENSEMBLE_NAME="ensemble name"
#   image_name:tag
