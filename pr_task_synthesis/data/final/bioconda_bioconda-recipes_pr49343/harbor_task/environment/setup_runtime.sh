#!/bin/bash
set -xeu

# Setup runtime environment for bioconda-recipes
# This script creates the bioconda conda environment
# Base image: condaforge/mambaforge:latest (conda pre-installed at /opt/conda)

# Export conda paths for downstream use
export PATH="/opt/conda/bin:$PATH"
export CONDA_PREFIX="/opt/conda"

# Source conda initialization
source /opt/conda/etc/profile.d/conda.sh

# Configure conda channels for bioconda
# Order matters: defaults, conda-forge, bioconda
conda config --add channels defaults
conda config --add channels conda-forge
conda config --add channels bioconda
conda config --set channel_priority flexible

# Create bioconda environment with build tools
# Simplified package list to avoid dependency conflicts:
# - Removed bioconda-utils (has import issues and conflicts)
# - Use conda-build only for building recipes
# - Use gcc/gxx from conda-forge (simpler than gcc_linux-64)
# - Let conda choose compatible Python version
conda create -n bioconda -y \
    python \
    conda-build \
    conda-verify \
    make \
    wget \
    gcc \
    gxx

# Activate the environment and verify installation
conda activate bioconda

# Verify conda-build is available (main tool for building recipes)
which conda-build

echo "Bioconda runtime setup complete!"
echo "Environment: bioconda"
echo "Activation: source /opt/conda/etc/profile.d/conda.sh && conda activate bioconda"
