#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for govips
# This script creates the Go runtime environment and installs dependencies

set -e

echo "=== Setting up Go runtime environment for govips ==="

# Ensure git and curl are available (required for Go module downloads)
# These should already be in the base image, but verify
if ! command -v git &> /dev/null; then
    echo "ERROR: git is required but not found"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo "ERROR: curl is required but not found"
    exit 1
fi

# Verify Go is installed (should be done in base_setup_commands)
if ! command -v go &> /dev/null; then
    echo "ERROR: Go is required but not found. Ensure golang-go is installed in base_setup_commands."
    exit 1
fi

# Verify libvips-dev is installed (should be done in base_setup_commands)
if ! pkg-config --modversion vips &> /dev/null; then
    echo "ERROR: libvips-dev is required but not found. Ensure libvips-dev is installed in base_setup_commands."
    exit 1
fi

echo "Go version: $(go version)"
echo "libvips version: $(pkg-config --modversion vips)"

# Verify key libvips dependencies are available via pkg-config
echo "Verifying libvips dependencies..."
for dep in vips glib-2.0 gobject-2.0; do
    if ! pkg-config --modversion "$dep" &> /dev/null; then
        echo "ERROR: Required dependency $dep is not available"
        exit 1
    fi
    echo "  $dep: $(pkg-config --modversion $dep)"
done

# Set up Go workspace
export GOPATH=${GOPATH:-/root/go}
export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin

# Create workspace directory if it doesn't exist
WORKSPACE=${WORKSPACE:-/workspace}
cd "$WORKSPACE"

# Download Go module dependencies
echo "Downloading Go module dependencies..."
CGO_CFLAGS_ALLOW=-Xpreprocessor go mod download

# Verify the build works
echo "Verifying build..."
CGO_CFLAGS_ALLOW=-Xpreprocessor go build -v ./vips

echo "=== Go runtime environment setup complete ==="
