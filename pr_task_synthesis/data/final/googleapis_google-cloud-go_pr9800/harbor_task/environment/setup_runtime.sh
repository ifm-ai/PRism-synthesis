#!/bin/bash
# Runtime setup script for Google Cloud Client Libraries for Go
# This script prepares the Go environment and installs dependencies

set -e

# Export Go path
export PATH=/usr/local/go/bin:$PATH
export GOPATH=/root/go
export GOBIN=$GOPATH/bin

echo "Setting up Go runtime environment..."

# Verify Go is available
go version

# Create GOPATH directories if they don't exist
mkdir -p $GOPATH/bin

# Set up Go modules workspace
cd /workspace

# Tidy the main module
echo "Running go mod tidy on root module..."
go mod tidy

# Tidy the auth submodule (where the fix is located)
echo "Running go mod tidy on auth module..."
cd /workspace/auth
go mod tidy

# Download all dependencies
echo "Downloading dependencies..."
cd /workspace
go mod download

# Build the auth package to verify it compiles
echo "Building auth package..."
cd /workspace/auth
go build ./...

echo "Go runtime setup complete."
echo "GOPATH: $GOPATH"
echo "GOBIN: $GOBIN"
