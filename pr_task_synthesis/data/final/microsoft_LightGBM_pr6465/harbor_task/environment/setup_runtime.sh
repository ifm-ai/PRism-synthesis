#!/bin/bash
set -e -u -o pipefail

# setup_runtime.sh - Build-time runtime creation for LightGBM Python package
# This script creates the conda environment and installs base dependencies

echo "=== LightGBM Environment Setup ==="

# Configuration
CONDA_DIR="/opt/conda"
ENV_NAME="lightgbm-env"
WORKSPACE="${WORKSPACE:-/workspace}"

# Install miniforge if conda is not available
if [ ! -f "${CONDA_DIR}/bin/conda" ]; then
    echo "Installing Miniforge..."
    ARCH=$(uname -m)
    curl -sL -o /tmp/miniforge.sh \
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${ARCH}.sh"
    bash /tmp/miniforge.sh -f -b -p "${CONDA_DIR}"
    rm /tmp/miniforge.sh
else
    echo "Conda already installed at ${CONDA_DIR}"
fi

# Initialize conda
source "${CONDA_DIR}/etc/profile.d/conda.sh"

# Create conda environment with Python and core dependencies
echo "Creating conda environment: ${ENV_NAME}"
conda create -q -y -n "${ENV_NAME}" \
    python=3.11 \
    numpy \
    scipy \
    scikit-learn \
    pandas \
    pytest \
    cmake \
    ninja \
    setuptools \
    wheel \
    pip

# Activate the environment
conda activate "${ENV_NAME}"

# Install additional build dependencies via pip
echo "Installing additional Python dependencies..."
pip install --upgrade pip

# Install LightGBM Python package dependencies from pyproject.toml
pip install dataclasses scipy numpy scikit-learn pandas dask pyarrow matplotlib pytest joblib cloudpickle psutil

# Build and install LightGBM from source in the workspace
echo "Building LightGBM from source..."
cd "${WORKSPACE}"

# Initialize and update git submodules (required for external libraries)
echo "Initializing git submodules..."
git submodule update --init --recursive 2>/dev/null || true

# Create build directory and configure with CMake
cmake -B build -S . -DUSE_OPENMP=ON

# Build the C++ library
cmake --build build --target _lightgbm -j4

# Build and install the Python package using the precompiled library
cd "${WORKSPACE}"
./build-python.sh install --precompile --no-isolation

# Force uninstall any PyPI version and install from local sdist
echo "Ensuring local version is installed..."
cd "${WORKSPACE}/dist"
pip uninstall -y lightgbm 2>/dev/null || true
pip install --no-cache-dir lightgbm-*.tar.gz

echo "=== Setup Complete ==="
echo "Environment: ${ENV_NAME}"
echo "Activate with: source ${CONDA_DIR}/etc/profile.d/conda.sh && conda activate ${ENV_NAME}"
