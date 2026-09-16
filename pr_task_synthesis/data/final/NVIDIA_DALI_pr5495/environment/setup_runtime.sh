#!/bin/bash
# setup_runtime.sh - Runtime creation script for NVIDIA DALI
# This script sets up the build environment for DALI including CMake and dependencies

set -e

echo "=== Setting up DALI runtime environment ==="

# Install system packages
echo "Installing system packages..."
apt-get update -qq

# Install CMake and essential build tools (including git and curl for repo cloning)
apt-get install -y -qq \
    cmake \
    build-essential \
    ninja-build \
    pkg-config \
    wget \
    git \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    python3-full \
    python3-venv \
    > /dev/null 2>&1 || apt-get install -y -qq \
    cmake \
    build-essential \
    ninja-build \
    pkg-config \
    wget \
    git \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    python3-full \
    python3-venv

# Install CMake 3.18+ if the distro version is too old
CMAKE_VERSION=$(cmake --version 2>/dev/null | head -1 | awk '{print $3}')
CMAKE_MAJOR=$(echo "$CMAKE_VERSION" | cut -d. -f1)
CMAKE_MINOR=$(echo "$CMAKE_VERSION" | cut -d. -f2)

if [ "$CMAKE_MAJOR" -lt 3 ] || { [ "$CMAKE_MAJOR" -eq 3 ] && [ "$CMAKE_MINOR" -lt 18 ]; }; then
    echo "Installing CMake 3.24..."
    wget -qO- https://apt.kitware.com/keys/kitware-archive-latest.asc | gpg --dearmor - > /usr/share/keyrings/kitware-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/kitware-archive-keyring.gpg] https://apt.kitware.com/ubuntu/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/kitware.list
    apt-get update -qq
    apt-get install -y -qq cmake > /dev/null 2>&1
fi

# Create Python virtual environment for DALI
echo "Creating Python virtual environment..."
VENV_PATH="/opt/benchmark/dali_venv"
rm -rf "$VENV_PATH"
python3 -m venv "$VENV_PATH"

# Activate and upgrade pip
source "$VENV_PATH/bin/activate"
pip install --quiet --upgrade pip setuptools wheel

# Install test dependencies and numpy for DALI
echo "Installing Python dependencies..."
pip install --quiet pytest numpy

# Deactivate venv
deactivate

# Create a directory for CUDA toolkit placeholder (for GPU-enabled builds)
# Note: Actual CUDA toolkit should be provided by the base image or host
mkdir -p /opt/cuda
mkdir -p /usr/local/cuda

# Export environment variables for CUDA
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Create environment marker file
echo "Runtime environment setup complete" > /opt/dali_runtime_ready.txt

echo "=== DALI runtime environment setup complete ==="
echo "CMake version: $(cmake --version | head -1)"
echo "Python version: $(python3 --version)"
echo "GCC version: $(g++ --version | head -1)"
echo "Virtual environment: $VENV_PATH"
