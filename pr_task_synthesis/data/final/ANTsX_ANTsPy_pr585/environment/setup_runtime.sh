#!/bin/bash
# setup_runtime.sh - Runtime setup script for ANTsPy benchmark environment
# This script creates the Python environment and installs base dependencies
# It is called by repo_setup.sh after /workspace is created

set -e

echo "=== ANTsPy Runtime Setup ==="

# Install system dependencies if not already present
apt-get update -qq
apt-get install -y -qq cmake libblas-dev liblapack-dev gfortran libpng-dev python3-dev git curl python3-pip python3.11-venv > /dev/null 2>&1 || true

# Create a virtual environment for the benchmark
VENV_PATH="/opt/benchmark/venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating Python virtual environment at $VENV_PATH"
    python3 -m venv "$VENV_PATH"
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Upgrade pip
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# Install Python runtime dependencies and antspyx package
# Installing pre-built antspyx wheel to avoid complex C++ build during benchmark setup
echo "Installing Python base dependencies and antspyx..."
pip install numpy pandas scipy scikit-image scikit-learn statsmodels matplotlib pyyaml webcolors Pillow nibabel > /dev/null 2>&1

# Install pytest for running tests
pip install pytest > /dev/null 2>&1

# Install antspyx from PyPI (pre-built wheel)
pip install antspyx > /dev/null 2>&1

echo "=== Runtime setup complete ==="
echo "Virtual environment: $VENV_PATH"
echo "Activation command: source $VENV_PATH/bin/activate"
