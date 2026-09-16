#!/bin/bash
# setup_runtime.sh - Runtime creation script for datadog-agent benchmark environment
# This script installs dependencies and prepares the Go environment for testing

set -e

echo "=== Setting up datadog-agent runtime environment ==="

# Install system packages if not already present
echo "Installing system packages..."
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq git curl cmake g++ python3 python3-dev libseccomp-dev python3.11-venv 2>/dev/null || true

# Install Go 1.21.7 (required by .go-version)
echo "Setting up Go 1.21.7..."
GO_TARGET_VERSION="1.21.7"
GO_INSTALLED_VERSION=$(/usr/local/go/bin/go version 2>/dev/null | grep -oP 'go\K[0-9.]+' || echo "none")

if [ "$GO_INSTALLED_VERSION" != "$GO_TARGET_VERSION" ]; then
    # Try to download Go 1.21.7 from Google CDN
    if curl -fsSL "https://dl.google.com/go/go1.21.7.linux-amd64.tar.gz" -o /tmp/go1.21.7.linux-amd64.tar.gz 2>/dev/null; then
        echo "Installing Go $GO_TARGET_VERSION..."
        rm -rf /usr/local/go 2>/dev/null || true
        tar -C /usr/local -xzf /tmp/go1.21.7.linux-amd64.tar.gz
        rm -f /tmp/go1.21.7.linux-amd64.tar.gz
    else
        echo "Warning: Could not download Go $GO_TARGET_VERSION"
        echo "Using system Go if available"
    fi
fi

# Set up Go environment
export GOPATH="${GOPATH:-/root/go}"
if [ -d "/usr/local/go" ]; then
    export GOROOT="/usr/local/go"
    export PATH="/usr/local/go/bin:$PATH"
fi

# Verify Go installation
echo "Verifying Go installation..."
go version || { echo "ERROR: Go not available"; exit 1; }

# Install Python invoke if not present
echo "Installing Python invoke..."
pip3 install --break-system-packages invoke 2>/dev/null || pip3 install invoke 2>/dev/null || true

# Create the benchmark environment directory
mkdir -p /opt/benchmark

# Create a virtual environment for Python dependencies (invoke, etc.)
if [ ! -d "/opt/benchmark/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv /opt/benchmark/venv
    source /opt/benchmark/venv/bin/activate
    pip install --upgrade pip
    pip install invoke
    deactivate
fi

# Install Go dependencies for the project
echo "Installing Go module dependencies..."
cd /workspace
go mod download 2>/dev/null || echo "Note: go mod download skipped (may require network)"

echo "=== Runtime setup complete ==="
echo "Go version: $(go version)"
echo "Python version: $(python3 --version)"
echo "CMake version: $(cmake --version | head -1)"
