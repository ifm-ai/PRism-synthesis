#!/bin/bash
# Runtime setup script for TileDB-SOMA Python environment
# This script sets up the Python environment and installs dependencies

set -euo pipefail

echo "=== TileDB-SOMA Runtime Setup ==="

# Install system packages (cmake required for building native extensions)
echo "Installing system packages..."
apt-get update -qq
apt-get install -y -qq cmake libssl-dev pkg-config python3-venv patch python3-dev g++

# Verify cmake installation
echo "Verifying cmake installation..."
cmake --version

# Create Python virtual environment for the benchmark
VENV_PATH="/opt/benchmark/venv"
echo "Creating Python virtual environment at ${VENV_PATH}..."
python3 -m venv "${VENV_PATH}"

# Activate the virtual environment
echo "Activating virtual environment..."
source "${VENV_PATH}/bin/activate"

# Upgrade pip and install build tools (use older setuptools for pkg_resources)
echo "Upgrading pip and installing build tools..."
pip install --upgrade pip
pip install 'setuptools<70' wheel

# Change to the Python API directory
cd /workspace/apis/python

# Create a RELEASE-VERSION file since git tags may not be available
# This is needed for the version.py script to work
echo "1.0.0" > RELEASE-VERSION

# Install build dependencies first (pybind11)
echo "Installing build dependencies..."
pip install 'pybind11[global]>=2.10.0'

# Install the TileDB-SOMA package in editable mode
# This will build the native extensions including libtiledbsoma
# Note: CXXFLAGS set to suppress dangling-reference warning (g++ 14 compatibility issue with spdlog/fmt)
# Only use the flag if the compiler supports it (g++ 13+)
echo "Installing TileDB-SOMA package in editable mode..."
if g++ -Wdangling-reference -E - < /dev/null 2>/dev/null; then
    export CXXFLAGS="-Wno-error=dangling-reference"
    echo "Using CXXFLAGS=$CXXFLAGS (g++ 13+ detected)"
else
    echo "g++ does not support -Wdangling-reference (g++ 12 or older), proceeding without CXXFLAGS"
fi
pip install -e .

# Install dev/test dependencies with compatible versions
echo "Installing test dependencies..."
pip install pytest sparse 'typeguard<3.0' 'anndata<0.11'

# Verify installation
echo "Verifying installation..."
python -c "import tiledbsoma; print(f'tiledbsoma version: {tiledbsoma.__version__}')"
python -c "import pyarrow; import pandas; import numpy; print('Core dependencies OK')"

echo "=== Runtime Setup Complete ==="
