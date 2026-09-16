#!/bin/bash
# Runtime setup script for Microsoft Recognizers Text - Python environment
# This script creates the Python runtime and installs all dependencies

set -e

WORKSPACE="${WORKSPACE:-/workspace}"
VENV_PATH="/opt/benchmark/venv"

echo "=== Setting up Python runtime for Microsoft Recognizers Text ==="

# Create mount point directory for outer verifier's /tests/ mount
# The outer verifier will bind-mount /artifacts/evaluation/ to /tests/ at runtime
# This directory must exist with proper permissions for the mount to succeed
# Set explicit permissions (rwxr-xr-x) to allow bind mount from /artifacts/evaluation/
mkdir -p /tests
chmod 755 /tests

# Install system packages (git and curl are already available in the base image)
# Installing python3-venv for virtual environment support
apt-get update -qq 2>/dev/null || true
apt-get install -y python3.11-venv 2>/dev/null || apt-get install -y python3-venv 2>/dev/null || true

# Create virtual environment
echo "Creating virtual environment at $VENV_PATH..."
python3 -m venv "$VENV_PATH"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Upgrade pip
pip install --upgrade pip --quiet

# Navigate to Python directory
cd "$WORKSPACE/Python"

# Install the resource generator dependencies first
echo "Installing resource generator dependencies..."
pip install -r ./libraries/resource-generator/requirements.txt --quiet

# Build resources using the resource generator
echo "Building resources..."
cd libraries/resource-generator
python index.py ../recognizers-choice/resource-definitions.json
python index.py ../recognizers-number/resource-definitions.json
python index.py ../recognizers-number-with-unit/resource-definitions.json
python index.py ../recognizers-date-time/resource-definitions.json
python index.py ../recognizers-sequence/resource-definitions.json
cd ../..

# Install all recognizers libraries in editable mode
echo "Installing recognizers-text..."
pip install -e ./libraries/recognizers-text/ --quiet

echo "Installing recognizers-number..."
pip install -e ./libraries/recognizers-number/ --quiet

echo "Installing recognizers-number-with-unit..."
pip install -e ./libraries/recognizers-number-with-unit/ --quiet

echo "Installing datatypes-timex-expression..."
pip install -e ./libraries/datatypes-timex-expression/ --quiet

echo "Installing recognizers-date-time..."
pip install -e ./libraries/recognizers-date-time/ --quiet

echo "Installing recognizers-sequence..."
pip install -e ./libraries/recognizers-sequence/ --quiet

echo "Installing recognizers-choice..."
pip install -e ./libraries/recognizers-choice/ --quiet

echo "Installing recognizers-suite..."
pip install -e ./libraries/recognizers-suite/ --quiet

# Install test dependencies
echo "Installing test dependencies..."
pip install -r ./tests/requirements.txt --quiet

echo "=== Python runtime setup complete ==="

# Verify installation
echo "Verifying installation..."
python -c "import recognizers_suite; print('recognizers_suite imported successfully')"

echo "=== Runtime setup finished successfully ==="
