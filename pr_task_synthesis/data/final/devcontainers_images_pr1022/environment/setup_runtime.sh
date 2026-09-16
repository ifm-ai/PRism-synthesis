#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for Anaconda devcontainer environment
# This script creates a conda environment and installs dependencies for Pillow verification

set -e

echo "=== Setting up Anaconda Python runtime environment ==="

# Install Miniconda if not present (lighter than full Anaconda for our needs)
if [ ! -d "/opt/conda" ]; then
    echo "Installing Miniconda..."
    curl -fsSL -o /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash /tmp/miniconda.sh -b -p /opt/conda
    rm -f /tmp/miniconda.sh
fi

# Set up conda initialization
export PATH="/opt/conda/bin:$PATH"

# Initialize conda for bash
/opt/conda/bin/conda init bash 2>/dev/null || true

# Source conda for this session
source /opt/conda/etc/profile.d/conda.sh

# Create a clean environment for the benchmark
echo "Creating benchmark conda environment..."
conda create -n benchmark -y python=3.11 2>/dev/null || conda create -n benchmark python=3.11 -y

# Activate the environment
conda activate benchmark

# Install Pillow 10.2.0 (the buggy version - matches the buggy repository state)
echo "Installing Pillow 10.2.0 and dependencies..."
pip install --upgrade pip
pip install "Pillow==10.2.0"

# Verify installation
echo "Verifying Pillow installation..."
python -c "from PIL import Image; print(f'Pillow version: {Image.__version__ if hasattr(Image, \"__version__\") else \"OK\"}')"

# Install pytest for test running
pip install pytest

# Clean up conda cache
conda clean -afy 2>/dev/null || true

echo "=== Runtime setup complete ==="
echo "To activate: source /opt/conda/etc/profile.d/conda.sh && conda activate benchmark"
