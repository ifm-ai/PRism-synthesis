#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for cilium/cilium Go environment
# This script installs Go 1.22+, sets up the environment, and installs project dependencies.

set -e

echo "=== Setting up Go runtime environment for cilium/cilium ==="

# Ensure required system packages are available
echo "Installing baseline system packages..."
apt-get update -qq
apt-get install -y -qq git curl build-essential pkg-config 2>/dev/null || true

# Install Go 1.22 if not present
if ! command -v go &> /dev/null; then
    echo "Installing Go 1.22..."
    GO_VERSION="1.22.0"
    GO_OS="linux"
    GO_ARCH="amd64"
    GO_TARBALL="go${GO_VERSION}.${GO_OS}-${GO_ARCH}.tar.gz"

    # Download and extract Go from Google's official download server
    curl -sL "https://dl.google.com/go/${GO_TARBALL}" -o "/tmp/${GO_TARBALL}"
    rm -rf /usr/local/go
    tar -C /usr/local -xzf "/tmp/${GO_TARBALL}"
    rm "/tmp/${GO_TARBALL}"

    echo "Go ${GO_VERSION} installed successfully"
else
    echo "Go is already installed: $(go version)"
fi

# Export Go environment variables for the build environment
export PATH="/usr/local/go/bin:$PATH"
export GOPATH="${GOPATH:-/root/go}"
export GOROOT="/usr/local/go"

# Ensure GOPATH bin is in PATH
export PATH="$GOPATH/bin:$PATH"

# Create Go workspace directories
mkdir -p "$GOPATH/bin"

echo "Go environment configured:"
go version
go env GOOS GOARCH GOPATH GOROOT

# Navigate to workspace and install dependencies
if [ -d "/workspace" ]; then
    cd /workspace

    echo "Installing Go module dependencies..."
    # Use go mod download to fetch all dependencies without building
    go mod download

    # Verify the module is correctly set up
    go mod verify

    echo "Go module dependencies installed successfully"
else
    echo "Warning: /workspace directory not found, skipping dependency installation"
fi

echo "=== Go runtime setup complete ==="
