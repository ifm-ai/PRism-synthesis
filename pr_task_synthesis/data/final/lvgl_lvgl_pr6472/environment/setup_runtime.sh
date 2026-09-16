#!/bin/bash
# LVGL Build Environment Setup Script
# This script prepares the build environment for LVGL (Light and Versatile Graphics Library)
# It should be run during image build to create the primary runtime environment

set -e

echo "=== LVGL Build Environment Setup ==="

# Install system packages required for LVGL development and testing
echo "Installing system packages..."
apt-get update
apt-get install -y \
    cmake \
    ninja-build \
    gcc \
    g++ \
    pkg-config \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    ruby-dev \
    git \
    curl \
    python3 \
    python3-pip

# Install Python dependencies for test scripts
echo "Installing Python dependencies..."
pip3 install --break-system-packages pypng lz4 || true

# Verify installations
echo "Verifying toolchain..."
cmake --version
ninja --version
gcc --version
python3 --version
ruby --version

echo "=== LVGL Build Environment Setup Complete ==="
