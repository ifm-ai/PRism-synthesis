#!/bin/bash
# Setup runtime for gudhi project with TensorFlow layers
# This script creates the Python environment and installs dependencies

set -e

echo "=== Setting up gudhi runtime environment ==="

# Install system packages (CMake and build essentials for C++ extensions)
echo "Installing system packages..."
apt-get update -qq
apt-get install -y -qq cmake build-essential pkg-config python3-venv git curl

# Create a virtual environment for the project
VENV_PATH="/opt/benchmark/gudhi_env"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating Python virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Upgrade pip
pip install --upgrade pip --quiet

# Install core dependencies for gudhi build
echo "Installing Python dependencies..."
pip install --quiet \
    numpy>=1.15.0 \
    cython>=0.27 \
    pybind11 \
    setuptools>=24.2.0 \
    wheel \
    build

# Install TensorFlow (CPU version for container compatibility)
echo "Installing TensorFlow..."
pip install --quiet tensorflow

# Install test dependencies
echo "Installing test dependencies..."
pip install --quiet pytest scikit-learn

# Verify installations
echo "Verifying installations..."
python -c "import tensorflow as tf; print(f'TensorFlow version: {tf.__version__}')"
python -c "import numpy; print(f'NumPy version: {numpy.__version__}')"
python -c "import pytest; print(f'pytest version: {pytest.__version__}')"

echo "=== Runtime setup complete ==="
