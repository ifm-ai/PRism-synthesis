#!/bin/bash
# Setup runtime environment for Azure SDK for Python finetuning module
# This script creates a Python virtual environment and installs dependencies

set -e

echo "=== Setting up Python runtime environment ==="

# Install system packages if needed (python3-venv for venv creation)
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "Installing python3-venv..."
    apt-get update -qq && apt-get install -y -qq python3.11-venv
fi

# Create the benchmark environment directory
mkdir -p /opt/benchmark

# Remove any existing venv to ensure clean state
rm -rf /opt/benchmark/venv

# Create Python virtual environment
echo "Creating Python virtual environment at /opt/benchmark/venv..."
python3 -m venv /opt/benchmark/venv

# Activate the virtual environment
source /opt/benchmark/venv/bin/activate

# Upgrade pip and install setuptools (older version for pkg_resources compatibility)
# This is needed because the setup.py uses pkg_resources which is deprecated in newer setuptools
echo "Upgrading pip and installing setuptools..."
pip install --upgrade pip 'setuptools<60' wheel

# Install base test dependencies
echo "Installing test dependencies..."
pip install pytest pytest-cov pytest-mock pytest-timeout pytest-xdist pytest-asyncio

# Install azure-devtools for test utilities
echo "Installing azure-devtools..."
pip install -e /workspace/tools/azure-devtools

# Install azure-sdk-tools for devtools_testutils
echo "Installing azure-sdk-tools..."
pip install -e /workspace/tools/azure-sdk-tools

# Install the azure-ai-ml package from local source
# Using --no-build-isolation to avoid build environment issues with pkg_resources
echo "Installing azure-ai-ml package from /workspace/sdk/ml/azure-ai-ml..."
cd /workspace/sdk/ml/azure-ai-ml
pip install . --no-build-isolation

# Install marshmallow version compatible with the project (dev_requirements.txt specifies <3.20)
echo "Installing compatible marshmallow version..."
pip install 'marshmallow<3.20' 'marshmallow-jsonschema==0.10.0'

# Install additional dependencies that might be needed for tests
echo "Installing additional test dependencies..."
pip install pyyaml python-dotenv mock

echo "=== Runtime environment setup complete ==="
echo "Activation command: source /opt/benchmark/venv/bin/activate"
