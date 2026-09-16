#!/usr/bin/env bash
# setup_runtime.sh - Build-time runtime creation script for HoneyCluster benchmark
#
# This script:
# - Installs system packages (git, curl already present in base image)
# - Installs kubectl for Kubernetes manifest validation
# - Installs poetry for Python components
# - Prepares the environment for running kubectl apply validation tests

set -e

echo "=== Setting up runtime environment for HoneyCluster ==="

# Git and curl are already provided by the base image (debian:bookworm-slim or similar)
# No need to install them separately

# Install kubectl if not present
if ! command -v kubectl &> /dev/null; then
    echo "Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/v1.31.0/bin/linux/amd64/kubectl"
    chmod +x kubectl
    mv kubectl /usr/local/bin/
fi

# Install poetry and pytest if not present
if ! command -v poetry &> /dev/null; then
    echo "Installing poetry..."
    pip3 install --break-system-packages poetry
fi

if ! command -v pytest &> /dev/null; then
    echo "Installing pytest..."
    pip3 install --break-system-packages pytest
fi

# Verify installations
echo "=== Verifying installed tools ==="
kubectl version --client
poetry --version
git --version

# Create a global poetry config to avoid interactive prompts
poetry config virtualenvs.create true --local 2>/dev/null || true

echo "=== Runtime setup complete ==="
