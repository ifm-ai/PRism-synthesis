#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for PlayCanvas engine
# This script installs project dependencies in the Node.js 18.x environment
# It is called by repo_setup.sh during image build, not at runtime
#
# Prerequisites (should be installed at image level via base_setup_commands):
# - Node.js 18.x with npm
# - git, curl (baseline)
# - xvfb (for karma tests)
# - chromium (for karma tests)

set -e

echo "=== PlayCanvas Engine Runtime Setup ==="

# Verify Node.js 18.x is available
NODE_VERSION=$(node --version 2>/dev/null || echo "none")
if [[ "$NODE_VERSION" != "v18"* ]]; then
    echo "ERROR: Node.js 18.x required but found: $NODE_VERSION"
    exit 1
fi
echo "Node.js version: $NODE_VERSION"

# Verify npm is available
if ! command -v npm &>/dev/null; then
    echo "ERROR: npm is required but not found. Install at image level."
    exit 1
fi
echo "npm version: $(npm --version)"

# Install project dependencies
echo "Installing project dependencies..."
cd /workspace

# Clean install to match CI behavior
npm clean-install --progress=false --no-fund

# Verify installation
if [ -d "node_modules" ]; then
    echo "Dependencies installed successfully"
else
    echo "ERROR: node_modules directory not found"
    exit 1
fi

echo "=== Runtime Setup Complete ==="
