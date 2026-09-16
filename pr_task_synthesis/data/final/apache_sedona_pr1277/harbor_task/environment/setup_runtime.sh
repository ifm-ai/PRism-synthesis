#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for Apache Sedona
# This script creates the runtime environment and installs base dependencies
# It is safe to call from repo_setup.sh during image build

set -e

echo "=== Apache Sedona Runtime Setup ==="

# Export JAVA_HOME for Maven and Java builds
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

echo "JAVA_HOME=$JAVA_HOME"
echo "Java version:"
java -version 2>&1 | head -3

echo "Maven version:"
mvn --version 2>&1 | head -3

# Setup Python environment for the Python module
# Using venv for faster, more reliable setup
PYTHON_MODULE_DIR="${WORKSPACE:-/workspace}/python"
VENV_DIR="${PYTHON_MODULE_DIR}/.venv"

if [ -d "$PYTHON_MODULE_DIR" ]; then
    echo "Setting up Python environment in $PYTHON_MODULE_DIR"

    # Create virtual environment
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Upgrade pip and install base dependencies
    pip install --upgrade pip setuptools wheel

    # Install the sedona Python package from source
    # This builds the C extensions that require GEOS library
    cd "$PYTHON_MODULE_DIR"
    pip install -e .

    # Install test dependencies
    pip install pytest

    echo "Python environment created successfully"

    # Verify the environment
    python --version
    pip list | head -20

    # Deactivate the environment
    deactivate
fi

echo "=== Runtime Setup Complete ==="
