#!/bin/bash
# setup_runtime.sh - Create the conda environment and install dependencies for Xopt
# This script is meant to be run during Docker image build
# Base image: ubuntu:22.04 with Miniforge manually installed

set -e

echo "=== Setting up Xopt runtime environment ==="

# Ensure conda is available
if [ ! -d "/opt/conda" ]; then
    echo "Installing Miniforge..."
    wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O /tmp/miniforge.sh
    bash /tmp/miniforge.sh -b -p /opt/conda
    rm /tmp/miniforge.sh
fi

# Initialize conda
export PATH="/opt/conda/bin:$PATH"
export CONDA_PREFIX="/opt/conda"

# Source conda for shell functions
source /opt/conda/etc/profile.d/conda.sh

# Create the conda environment from environment.yml
cd /workspace
echo "Creating conda environment 'xopt-dev' from environment.yml..."
conda env create -f environment.yml

# Activate the environment
conda activate xopt-dev

# Install the package in editable mode (no dependencies since conda handles them)
echo "Installing xopt in editable mode..."
pip install --no-dependencies -e .

echo "=== Xopt runtime environment setup complete ==="
echo "Environment: xopt-dev"
echo "Activation: source /opt/conda/etc/profile.d/conda.sh && conda activate xopt-dev"
