#!/bin/bash
# Build-time script to create the runtime environment for pz-rail
# This script creates a venv, installs dependencies, and prepares the environment

set -e

# Create the benchmark environment directory
ENV_DIR="/opt/benchmark/venv"
WORKSPACE="${WORKSPACE:-/workspace}"

echo "Installing system dependencies (if not already installed)..."
apt-get update -qq || true
apt-get install -y -qq git curl openmpi-bin libopenmpi-dev hdf5-tools libhdf5-openmpi-dev || true

echo "Creating Python virtual environment at ${ENV_DIR}..."
python3 -m venv "${ENV_DIR}"

echo "Activating virtual environment..."
source "${ENV_DIR}/bin/activate"

echo "Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel

echo "Installing system MPI and HDF5 packages already done (openmpi-bin, libopenmpi-dev, hdf5-tools, libhdf5-openmpi-dev)"

echo "Installing mpi4py with MPI support..."
pip install mpi4py

echo "Installing h5py with HDF5 support..."
# Use the system HDF5 libraries
export HDF5_DIR=/usr/lib/x86_64-linux-gnu/hdf5/openmpi
export CC=mpicc
pip install h5py

echo "Installing jax and jaxlib..."
pip install jax jaxlib

echo "Installing base dependencies from environment.yml (via pip)..."
pip install numpy astropy healpy pandas fitsio pyarrow tables

echo "Installing pz-rail-base core dependency..."
pip install pz-rail-base

echo "Installing pz-rail in development mode..."
cd "${WORKSPACE}"
pip install -e .

echo "Installing pytest for testing..."
pip install pytest pytest-cov

echo "Deactivating virtual environment..."
deactivate

echo "Runtime environment setup complete!"
echo "To activate: source ${ENV_DIR}/bin/activate"
