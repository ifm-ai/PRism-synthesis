#!/bin/bash
# Setup runtime environment for AutoGPTQ benchmark
# This script creates a Python virtual environment and installs dependencies
# Note: CUDA extensions require GPU - this setup installs CPU-only PyTorch for basic testing

set -e

echo "=== AutoGPTQ Runtime Setup ==="

# Create directories
mkdir -p /opt/benchmark
WORKSPACE_DIR="${WORKSPACE:-/workspace}"

# Install system dependencies if not already present
echo "Checking system dependencies..."
if ! command -v pip3 &> /dev/null; then
    echo "Installing python3-pip..."
    apt-get update -qq && apt-get install -y -qq python3-pip
fi

# Create Python virtual environment
echo "Creating Python virtual environment..."
python3 -m venv /opt/benchmark/venv
source /opt/benchmark/venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install compatible PyTorch version (2.4+ for transformers 5.x compatibility)
echo "Installing PyTorch (CPU-only for testing)..."
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu

# Install core dependencies with compatible versions
# Using peft 0.7.x which is compatible with the codebase
echo "Installing core dependencies..."
pip install \
    "transformers>=4.31.0,<5.0.0" \
    "accelerate>=0.26.0" \
    "safetensors" \
    "datasets" \
    "peft>=0.5.0,<0.9.0" \
    "tqdm" \
    "numpy<2.0.0" \
    "sentencepiece" \
    "rouge" \
    "gekko"

# Install test dependencies
echo "Installing test dependencies..."
pip install pytest parameterized

# Install AutoGPTQ from source WITHOUT CUDA extensions
# Set BUILD_CUDA_EXT=0 to skip CUDA extension compilation
echo "Installing AutoGPTQ from source (CPU-only mode)..."
cd "$WORKSPACE_DIR"
BUILD_CUDA_EXT=0 DISABLE_QIGEN=1 pip install -e .

# Verify installation
echo "Verifying installation..."
python -c "import auto_gptq; print('auto_gptq version:', auto_gptq.__version__)"

# Deactivate venv - activation will be done by downstream scripts
deactivate

echo "=== Runtime setup complete ==="
echo "Activation command: source /opt/benchmark/venv/bin/activate"
