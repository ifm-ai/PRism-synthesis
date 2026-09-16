#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for BigDL-LLM
# Optimized for low bandwidth network environments (500-900 kB/s)
# Uses CPU-only torch to reduce download size from >2.5GB to ~200MB

set -e

echo "=== BigDL-LLM Runtime Setup (Network-Optimized) ==="

# System package installation (git and curl are already available in the base image)
echo "Git: $(which git)"
echo "Curl: $(which curl)"

# Install python3-venv if not already available (needed for venv creation)
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "Installing python3-venv..."
    apt-get update && apt-get install -y python3.11-venv python3-pip
fi

# Create the benchmark runtime environment
VENV_PATH="/opt/benchmark/venv"
echo "Creating Python virtual environment at $VENV_PATH..."

# Remove existing venv if present (for idempotency)
rm -rf "$VENV_PATH"

# Create virtual environment
python3 -m venv "$VENV_PATH"

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Upgrade pip with retry handling
echo "Upgrading pip..."
pip install --upgrade pip --retries 5 --timeout 60

# Install requests module required by setup.py
echo "Installing requests module (required by setup.py)..."
pip install requests --retries 5 --timeout 60

# STRATEGY: Use CPU-only torch to avoid large CUDA dependencies
# torch CPU variant is ~200MB vs ~2GB+ for CUDA variants
# This is critical for network-constrained environments with 500-900 kB/s bandwidth
echo "Installing CPU-only torch (smaller variant for network-constrained environments)..."
pip install torch --index-url https://download.pytorch.org/whl/cpu --retries 10 --timeout 120 || {
    echo "Primary torch-cpu install failed, retrying with increased timeout..."
    pip install torch --index-url https://download.pytorch.org/whl/cpu --retries 10 --timeout 180 || {
        echo "Second attempt failed, trying with extended timeout..."
        pip install torch --index-url https://download.pytorch.org/whl/cpu --retries 15 --timeout 300
    }
}

# Install other core dependencies (these are relatively small)
echo "Installing core dependencies..."
pip install py-cpuinfo protobuf numpy --retries 5 --timeout 60

# Install transformers and related packages (smaller than torch)
echo "Installing transformers stack..."
pip install transformers==4.31.0 sentencepiece tokenizers==0.13.3 accelerate==0.21.0 --retries 5 --timeout 60

# Install lm_eval and tabulate
echo "Installing lm_eval and tabulate..."
pip install tabulate lm_eval --retries 5 --timeout 60

# Set up the BigDL-LLM package (Python modules only, no native binaries)
echo "Setting up BigDL-LLM Python package..."
cd /workspace/python/llm

# Create necessary directory structure for the package
mkdir -p src/bigdl/llm/libs
touch src/bigdl/llm/libs/__init__.py

# Add the package to Python path by creating a .pth file
# This allows importing bigdl.llm without full installation
echo "/workspace/python/llm/src" > "$VENV_PATH/lib/python3.11/site-packages/bigdl-llm.pth"

# Install pytest for testing
echo "Installing pytest..."
pip install pytest --retries 5 --timeout 60

# Verify installation - check that we can import the core modules
echo "Verifying installation..."
python -c "import torch; print(f'torch version: {torch.__version__} (CPU-only)')"
python -c "import transformers; print(f'transformers version: {transformers.__version__}')"
python -c "import pytest; print(f'pytest version: {pytest.__version__}')"
python -c "import sys; sys.path.insert(0, '/workspace/python/llm/src'); import bigdl.llm; print('BigDL-LLM module accessible')"

echo "=== Runtime setup complete ==="
echo "Activation command: source $VENV_PATH/bin/activate"
echo ""
echo "Note: Using CPU-only torch variant to reduce download size from >2.5GB to ~200MB."
echo "      This enables the environment to build within network bandwidth constraints."
