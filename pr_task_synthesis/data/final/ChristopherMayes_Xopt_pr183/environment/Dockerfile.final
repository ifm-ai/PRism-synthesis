FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system packages required for Xopt (mpi4py, compilation, Miniforge download)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    libopenmpi-dev \
    openmpi-bin \
    libhdf5-dev \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download and install Miniforge
RUN wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O /tmp/miniforge.sh && \
    bash /tmp/miniforge.sh -b -p /opt/conda && \
    rm /tmp/miniforge.sh && \
    /opt/conda/bin/conda init bash

# Set up conda in PATH for subsequent build steps
ENV PATH="/opt/conda/bin:$PATH"
ENV CONDA_PREFIX="/opt/conda"

# Copy build-context scripts into the image
COPY setup_runtime.sh /opt/benchmark/setup_runtime.sh
COPY repo_setup.sh /opt/benchmark/repo_setup.sh

# Make scripts executable
RUN chmod +x /opt/benchmark/setup_runtime.sh /opt/benchmark/repo_setup.sh

# Run repo_setup.sh to materialize /workspace from git
RUN /opt/benchmark/repo_setup.sh

# Run setup_runtime.sh to create conda environment and install xopt
RUN /opt/benchmark/setup_runtime.sh

# Set working directory
WORKDIR /workspace
