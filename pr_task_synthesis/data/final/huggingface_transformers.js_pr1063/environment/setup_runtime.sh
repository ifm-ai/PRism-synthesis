#!/bin/bash
# setup_runtime.sh - Runtime creation script for Transformers.js benchmark environment
# This script creates the Node.js runtime environment and installs dependencies.
# It is designed to be run during image build after /workspace is materialized.

set -e

echo "=== Setting up Transformers.js runtime environment ==="

# Ensure git-lfs is configured
echo "Configuring git-lfs..."
git lfs install 2>/dev/null || true

# Navigate to workspace
cd /workspace

# The onnxruntime-node package attempts to download GPU binaries from GitHub during postinstall
# which causes ConnectTimeoutError. Since tests only need CPU inference, we:
# 1. Install all dependencies except onnxruntime-node first (using --ignore-scripts)
# 2. Then install onnxruntime-node with --ignore-scripts to skip the binary download
# 3. The CPU fallback in onnxruntime-web will be used at runtime

echo "Configuring npm to handle onnxruntime-node network issue..."

# Set npm config for network resilience
npm config set fetch-retries 3
npm config set fetch-retry-mintimeout 10000
npm config set fetch-retry-maxtimeout 60000

# Install dependencies without running postinstall scripts (avoids GPU binary download)
echo "Installing npm dependencies (skipping postinstall scripts)..."
npm install --ignore-scripts

# The onnxruntime-node package is now installed but without the native binary.
# For CPU-only inference, onnxruntime-web provides a pure JS/WASM fallback.
# Verify that onnxruntime-node is present
if [ -d "node_modules/onnxruntime-node" ]; then
    echo "onnxruntime-node package installed (CPU fallback via onnxruntime-web)"
else
    echo "ERROR: onnxruntime-node not installed"
    exit 1
fi

# Verify installation
echo "Verifying installation..."
if [ -d "node_modules" ]; then
    echo "node_modules directory created successfully"
else
    echo "ERROR: node_modules directory not found"
    exit 1
fi

# Check that key dependencies are installed
echo "Checking key dependencies..."
node --version
npm --version
git lfs version

# Verify Jest is installed (needed for tests)
if [ -f "node_modules/jest/bin/jest.js" ]; then
    echo "Jest installed successfully"
else
    echo "WARNING: Jest not found in expected location"
fi

echo "=== Runtime environment setup complete ==="
