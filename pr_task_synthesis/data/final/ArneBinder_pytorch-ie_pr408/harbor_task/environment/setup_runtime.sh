#!/bin/bash
set -e

# setup_runtime.sh - Build-time runtime creation for pytorch-ie
# This script creates the Poetry virtual environment and installs dependencies

echo "=== Setting up Python Poetry runtime for pytorch-ie ==="

# Ensure poetry is in PATH
export PATH="/root/.local/bin:$PATH"

# Change to workspace directory
cd /workspace

echo "Creating Poetry virtual environment..."
poetry env use python3.11

echo "Installing project dependencies (including dev)..."
# Use --no-interaction to avoid prompts during build
# The --with dev flag installs development dependencies including pytest
poetry install --with dev --no-interaction

echo "Verifying environment..."
poetry env info

echo "=== Runtime setup complete ==="
