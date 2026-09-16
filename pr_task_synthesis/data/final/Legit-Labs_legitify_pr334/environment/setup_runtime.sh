#!/bin/bash
set -e

# setup_runtime.sh - Go runtime environment creation for Legitify project
# This script creates the Go runtime environment and installs dependencies

echo "=== Setting up Go runtime environment ==="

# Install system dependencies (git, curl, make are required)
echo "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq git curl make golang-go >/dev/null 2>&1 || {
    apt-get update
    apt-get install -y git curl make golang-go
}

# Verify git and curl are available
echo "Verifying system tools..."
git --version || { echo "ERROR: git not installed"; exit 1; }
curl --version | head -1 || { echo "ERROR: curl not installed"; exit 1; }
make --version | head -1 || { echo "ERROR: make not installed"; exit 1; }

# Verify Go installation (using apt-installed Go 1.19+)
echo "Verifying Go installation..."
go version || { echo "ERROR: Go not installed"; exit 1; }

# Set up Go environment variables
export GOPATH="/root/go"
export PATH="${GOPATH}/bin:${PATH}"

# Create GOPATH directories
mkdir -p "${GOPATH}/src" "${GOPATH}/bin" "${GOPATH}/pkg"

echo "Go installed successfully at $(go version)"

# Install OPA (Open Policy Agent) for policy validation from GitHub releases
echo "Installing OPA..."
OPA_VERSION="v0.55.0"
OPA_URL="https://github.com/open-policy-agent/opa/releases/download/${OPA_VERSION}/opa_linux_amd64_static"
curl -sSL "${OPA_URL}" -o /usr/local/bin/opa
chmod 755 /usr/local/bin/opa
/usr/local/bin/opa version || { echo "ERROR: OPA installation failed"; exit 1; }
echo "OPA installed successfully"

# Install Regal for Rego linting from GitHub releases
echo "Installing Regal..."
REGAL_VERSION="0.11.0"
REGAL_URL="https://github.com/StyraInc/regal/releases/download/v${REGAL_VERSION}/regal_Linux_x86_64"
curl -sSL "${REGAL_URL}" -o /usr/local/bin/regal
chmod 755 /usr/local/bin/regal
/usr/local/bin/regal version || { echo "ERROR: Regal installation failed"; exit 1; }
echo "Regal installed successfully"

# Set up Go environment for the workspace
echo "Setting up Go environment..."
export PATH="${GOPATH}/bin:${PATH}"

# Navigate to workspace and download dependencies
if [ -d "/workspace" ] && [ -f "/workspace/go.mod" ]; then
    echo "Downloading Go dependencies..."
    cd /workspace
    go mod verify || echo "Warning: go mod verify had issues"
    go mod download || { echo "ERROR: go mod download failed"; exit 1; }
    echo "Go dependencies downloaded successfully"
else
    echo "Warning: /workspace/go.mod not found, skipping dependency download"
fi

# Note: Go development tools (mockgen, wire) are not installed here as they are
# only needed for code generation during development, not for running tests.
# The project uses pre-generated mocks that are already in the repository.

echo "=== Go runtime environment setup complete ==="
echo "Go version: $(go version)"
echo "OPA version: $(/usr/local/bin/opa version)"
echo "Regal version: $(/usr/local/bin/regal version 2>&1 | head -1)"
echo ""
echo "Environment variables set:"
echo "  PATH includes: ${GOPATH}/bin"
echo "  GOPATH: ${GOPATH}"
