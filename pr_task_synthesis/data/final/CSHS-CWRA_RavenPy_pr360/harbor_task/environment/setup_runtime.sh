#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for RavenPy
# This script creates the Python virtual environment and installs dependencies
# It is designed to be called once during image build

set -e

echo "=== RavenPy Runtime Setup ==="

# Create benchmark environment directory
mkdir -p /opt/benchmark

# Create Python virtual environment
echo "Creating Python virtual environment..."
python3 -m venv /opt/benchmark/venv

# Activate the virtual environment
source /opt/benchmark/venv/bin/activate

# Upgrade pip and install build tools
echo "Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel

# Install GDAL Python bindings if gdal-config is available
if command -v gdal-config &> /dev/null; then
    echo "Installing GDAL Python bindings..."
    pip install GDAL=="$(gdal-config --version)"
else
    echo "GDAL not found at system level, attempting to install GDAL package..."
    # Try to install GDAL - this may fail if libgdal-dev is not installed
    pip install GDAL || echo "Warning: GDAL installation failed. Install libgdal-dev and gdal-bin first."
fi

# Install flit build backend
echo "Installing flit..."
pip install flit

# Install raven-hydro (Raven hydrological framework)
echo "Installing raven-hydro..."
pip install "raven-hydro>=0.2.4,<1.0"

# Install the RavenPy package in editable mode with dev dependencies
echo "Installing RavenPy in editable mode with dev dependencies..."
cd /workspace
pip install -e ".[dev]"

# Verify installation
echo "Verifying installation..."
python -c "import ravenpy; print(f'RavenPy version: {ravenpy.__version__}')"
python -c "from ravenpy.config.commands import CustomOutput; print('CustomOutput import OK')"

echo "=== RavenPy Runtime Setup Complete ==="
