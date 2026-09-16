#!/bin/bash
set -e

# Semantic Kernel Python Runtime Setup Script
# Optimized for fast installation using pip instead of poetry

# Install system dependencies if needed (git and curl should already be present)
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq python3-pip python3-venv python3-full 2>/dev/null || true

# Create a virtual environment in the project directory
cd /workspace/python
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip --quiet

# Install main dependencies directly (faster than poetry install)
# These are the core dependencies from pyproject.toml with pinned versions for compatibility
pip install --quiet \
    aiohttp==3.9.1 \
    numpy==1.24.4 \
    openai==1.5.0 \
    aiofiles==23.2.1 \
    python-dotenv==1.0.0 \
    regex==2023.10.3 \
    openapi_core==0.18.2 \
    prance==23.6.21.0 \
    pydantic==2.5.2 \
    motor==3.3.2

# Install only the required test dependencies (not all dev deps)
pip install --quiet \
    pytest==7.4.3 \
    pytest-asyncio==0.23.2 \
    snoop==0.4.3

# Install semantic-kernel in editable mode
pip install -e . --quiet --no-deps

# Verify the installation
python --version
pip show semantic-kernel | grep -i "Name\|Version" || echo "semantic-kernel package check complete"

echo "Runtime setup complete!"
