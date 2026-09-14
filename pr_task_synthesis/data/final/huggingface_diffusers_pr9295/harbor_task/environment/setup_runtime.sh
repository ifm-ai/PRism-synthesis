#!/bin/bash
# Setup runtime environment for diffusers
# This script is meant to be run at build time to prepare the environment
# It should NOT be run as an entrypoint

set -e

# PyPI index URLs
PYPI_INDEX="https://pypi.org/simple"
PYTORCH_CPU_INDEX="https://download.pytorch.org/whl/cpu"

# Create the benchmark virtual environment
echo "Creating Python virtual environment at /opt/benchmark/venv..."
python3 -m venv /opt/benchmark/venv

# Activate the virtual environment
source /opt/benchmark/venv/bin/activate

# Upgrade pip to avoid warnings
echo "Upgrading pip..."
pip install --upgrade pip

# Set pip retry configuration for resilience
export PIP_RETRIES=5
export PIP_TIMEOUT=120

# Install core dependencies
echo "Installing core dependencies..."
pip install --no-cache-dir --retries 5 --timeout 120 --index-url "$PYPI_INDEX" \
    importlib_metadata \
    filelock \
    "huggingface-hub>=0.23.2,<1.0" \
    numpy \
    "regex!=2019.12.17" \
    requests \
    "safetensors>=0.3.1" \
    Pillow

# Install PyTorch CPU version from the official CPU-only index
echo "Installing PyTorch (CPU) from ${PYTORCH_CPU_INDEX}..."
pip install --no-cache-dir --retries 5 --timeout 120 --index-url "$PYTORCH_CPU_INDEX" \
    "torch>=1.4"

# Install accelerate from PyPI (not available from PyTorch CPU index)
echo "Installing accelerate..."
pip install --no-cache-dir --retries 5 --timeout 120 --index-url "$PYPI_INDEX" \
    "accelerate>=0.31.0"

# Install test dependencies for LoRA tests
echo "Installing test dependencies..."
pip install --no-cache-dir --retries 5 --timeout 120 --index-url "$PYPI_INDEX" \
    pytest \
    pytest-timeout \
    pytest-xdist \
    parameterized \
    scipy \
    torchvision \
    "transformers>=4.41.2,<5.0.0" \
    "peft>=0.6.0" \
    Jinja2 \
    datasets

# Install diffusers from /workspace in editable mode
echo "Installing diffusers from /workspace in editable mode..."
cd /workspace
pip install --no-cache-dir --retries 5 --timeout 120 \
    --index-url "$PYPI_INDEX" \
    -e .

# Verify installation
echo "Verifying diffusers installation..."
python -c "import diffusers; print(f'diffusers version: {diffusers.__version__}')"

echo "Runtime setup complete!"
