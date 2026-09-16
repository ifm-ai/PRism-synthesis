#!/bin/bash
# Setup runtime environment for TileDB-Vector-Search
# This script creates the Python virtual environment and installs dependencies

set -e

echo "=== Setting up TileDB-Vector-Search runtime environment ==="

# Install python3-venv and python3-dev packages (required for venv module and building extensions)
echo "Installing python3-venv and python3-dev..."
apt-get update && apt-get install -y python3.11-venv python3.11-dev

# Create virtual environment
VENV_PATH="/opt/benchmark/venv"
echo "Creating virtual environment at $VENV_PATH..."
python3 -m venv "$VENV_PATH"

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Upgrade pip and install build tools
echo "Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel

# Install system dependencies for building (if not already present)
echo "Ensuring build dependencies are installed..."
apt-get update && apt-get install -y libopenblas-dev build-essential cmake 2>/dev/null || true

# Install the pre-built tiledb-vector-search package from PyPI
# This includes the C++ extensions already built
echo "Installing tiledb-vector-search package with dependencies..."
pip install "tiledb-vector-search>=0.10.0" "numpy<2.0.0" scikit-learn tiledb-cloud

# Install test dependencies
echo "Installing test dependencies..."
pip install "pytest<8.0.0" pytest-xdist nbmake

# The source code in /workspace will be used for the fix
# The pre-built package provides the runtime, but tests will use the /workspace source

# Verify installation
echo "Verifying installation..."
python -c "import tiledb.vector_search; print('tiledb.vector_search module loaded successfully')"
python -c "import numpy; print(f'numpy version: {numpy.__version__}')"
python -c "import sklearn; print(f'scikit-learn version: {sklearn.__version__}')"

echo "=== Runtime environment setup complete ==="
echo "To activate the environment, run: source $VENV_PATH/bin/activate"
