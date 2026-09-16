#!/bin/bash
# *******************************************************************************
# setup_runtime.sh - Build-time runtime creation for MLCommons RNNT environment
# *******************************************************************************
# This script creates the Python virtual environment and installs dependencies
# for the MLCommons inference RNNT speech recognition benchmark.
#
# It should be called by repo_setup.sh after /workspace is materialized.
# *******************************************************************************

set -euo pipefail

echo "=== Setting up MLCommons RNNT Python runtime environment ==="

# Configuration
VENV_PATH="/opt/benchmark/mlcommons-venv"
WORKSPACE="${WORKSPACE:-/workspace}"

# Ensure we're using Python 3 (prefer 3.10 if available)
PYTHON_CMD="python3"
if command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
fi

echo "Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Get the Python version for venv package installation
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

# Install system packages (git and curl should already be present in base image)
echo "=== Installing system packages ==="
# Note: sox and libsox-fmt-all are optional - pip can install sox bindings without system sox
apt-get update -qq 2>/dev/null || apt-get update || true
apt-get install -y -qq \
    "python${PYTHON_VERSION}-venv" \
    "python${PYTHON_VERSION}-dev" \
    python3-pip \
    protobuf-compiler \
    libprotoc-dev \
    libbz2-dev \
    libcgal-dev \
    libffi-dev \
    libfreetype6-dev \
    libhdf5-dev \
    libjpeg-dev \
    liblzma-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libpng-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    2>/dev/null || apt-get install -y \
        "python${PYTHON_VERSION}-venv" \
        "python${PYTHON_VERSION}-dev" \
        python3-pip \
        protobuf-compiler \
        libprotoc-dev \
        libbz2-dev \
        libcgal-dev \
        libffi-dev \
        libfreetype6-dev \
        libhdf5-dev \
        libjpeg-dev \
        liblzma-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libpng-dev \
        libreadline-dev \
        libsqlite3-dev \
        libssl-dev \
        libxml2-dev \
        libxslt-dev \
        zlib1g-dev \
        || echo "Note: Some system packages may not be available, continuing with pip installation"

# Create virtual environment
echo "=== Creating virtual environment at $VENV_PATH ==="
rm -rf "$VENV_PATH" 2>/dev/null || true
mkdir -p "$(dirname "$VENV_PATH")"
$PYTHON_CMD -m venv "$VENV_PATH"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Upgrade pip and install build tools
echo "=== Upgrading pip and installing build tools ==="
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir "setuptools>=41.0.0" six mock wheel cython

# Install SciPy prerequisites
echo "=== Installing SciPy prerequisites ==="
pip install --no-cache-dir pybind11[global]==2.6.2 pyangbind pythran

# Install core ML dependencies (versions from Dockerfile)
echo "=== Installing NumPy and SciPy ==="
pip install --no-cache-dir numpy==1.25.2 scipy==1.10.1

# Install essential ML packages
echo "=== Installing essential ML packages ==="
pip install --no-cache-dir hypothesis pyyaml pytest matplotlib

# Install vision and data packages
# Note: pillow 6.1 is from the original Dockerfile but is incompatible with Python 3.11
# We use a newer version that's compatible
echo "=== Installing vision and data packages ==="
pip install --no-cache-dir 'pillow>=9.0' lmdb ck==1.55.5 absl-py pycocotools typing_extensions

# Install transformers and pandas
echo "=== Installing transformers and pandas ==="
pip install --no-cache-dir transformers==4.32.1 pandas

# Install OpenCV
echo "=== Installing OpenCV ==="
pip install --no-cache-dir scikit-build
pip uninstall -y enum34 2>/dev/null || true
pip install --no-cache-dir opencv-python-headless==4.8.0.74

# Install librosa (the key dependency for this fix)
echo "=== Installing librosa and audio dependencies ==="
pip install --no-cache-dir 'librosa==0.10.0'

# Install additional RNNT dependencies
echo "=== Installing RNNT-specific dependencies ==="
pip install --no-cache-dir requests tqdm boto3 iopath unidecode inflect toml
pip install --no-cache-dir future onnx==1.15.0

# Install sox Python bindings (system sox optional)
echo "=== Installing sox Python bindings ==="
pip install --no-cache-dir sox || echo "Note: sox pip package not available, skipping"

# Install PyTorch (CPU version for testing - the actual AArch64 build would use custom wheels)
echo "=== Installing PyTorch ==="
# For the benchmark environment, we install a standard PyTorch that works on x86_64
# The actual AArch64 Docker build compiles PyTorch from source with ARM optimizations
pip install --no-cache-dir torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0

# Install the workspace as an editable package if it has setup.py
if [ -f "$WORKSPACE/setup.py" ]; then
    echo "=== Installing workspace as editable package ==="
    cd "$WORKSPACE"
    pip install -e . || true
fi

# Verify installation
echo "=== Verifying installation ==="
python -c "import librosa; print(f'librosa version: {librosa.__version__}')"
python -c "import torch; print(f'PyTorch version: {torch.__version__}')"
python -c "import numpy; print(f'NumPy version: {numpy.__version__}')"
python -c "import scipy; print(f'SciPy version: {scipy.__version__}')"

echo "=== Runtime setup complete ==="
echo "Virtual environment: $VENV_PATH"
echo "To activate: source $VENV_PATH/bin/activate"
