#!/usr/bin/env bash
# setup_runtime.sh - Runtime environment setup for Apache Arrow C++ Parquet benchmark
# This script creates a conda environment with all necessary C++ dependencies

set -e

echo "=== Apache Arrow C++ Parquet Benchmark Runtime Setup ==="

# Export conda for use in this script
export PATH="/opt/conda/bin:$PATH"
export CONDA_EXE="/opt/conda/bin/conda"

# Accept conda Terms of Service to avoid interactive prompts
# Required for recent Miniconda versions before using default anaconda channels
echo "Accepting conda Terms of Service..."
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Configure conda for non-interactive operation
conda config --set always_yes yes
conda config --set channel_priority flexible

# Create the benchmark conda environment
echo "Creating conda environment 'arrow-cpp'..."
conda create -n arrow-cpp -y \
    python=3.11 \
    cmake>=3.16 \
    ninja \
    c-compiler \
    cxx-compiler \
    pkg-config \
    make \
    || { echo "Failed to create base conda environment"; exit 1; }

# Activate the environment for package installation
source /opt/conda/etc/profile.d/conda.sh
conda activate arrow-cpp

echo "Installing C++ dependencies for Parquet..."
# Install the core C++ dependencies required for building and running Parquet benchmarks
conda install -y -c conda-forge \
    benchmark>=1.6.0 \
    boost-cpp>=1.68.0 \
    gtest>=1.10.0 \
    gflags \
    glog \
    snappy \
    lz4-c \
    zlib \
    brotli \
    thrift-cpp>=0.11.0 \
    rapidjson \
    re2 \
    zstd \
    openssl \
    || { echo "Failed to install C++ dependencies"; exit 1; }

echo "Verifying environment setup..."
# Verify key tools are available
cmake --version
ninja --version
echo "Conda environment 'arrow-cpp' is ready."

# Export environment variables for downstream use
echo "export PATH=\"/opt/conda/envs/arrow-cpp/bin:\$PATH\"" > /opt/conda/envs/arrow-cpp/bin/activate-arrow-cpp.sh
echo "export CMAKE_PREFIX_PATH=\"/opt/conda/envs/arrow-cpp:\$CMAKE_PREFIX_PATH\"" >> /opt/conda/envs/arrow-cpp/bin/activate-arrow-cpp.sh
echo "export PKG_CONFIG_PATH=\"/opt/conda/envs/arrow-cpp/lib/pkgconfig:\$PKG_CONFIG_PATH\"" >> /opt/conda/envs/arrow-cpp/bin/activate-arrow-cpp.sh

echo "=== Runtime setup complete ==="
echo "To activate: source /opt/conda/etc/profile.d/conda.sh && conda activate arrow-cpp"
