#!/bin/bash
# Setup runtime environment for Terraform infrastructure repository
# This script handles build-time runtime creation, environment exports,
# activation preparation, and base repository dependency installation.

set -e

echo "=== Setting up Terraform/Go runtime environment ==="

# Export Go environment variables
export GOROOT=/usr/local/go
export GOPATH=${GOPATH:-/home/agent_sandbox/go}
export PATH=$GOROOT/bin:$GOPATH/bin:$PATH

echo "Go version: $(go version)"

# Install conftest if not present (for OPA testing)
# Use v0.48.0 which is compatible with Go 1.23.2 (latest requires Go 1.25.8+)
if ! command -v conftest &> /dev/null; then
    echo "Installing conftest..."
    export GOPROXY="${GOPROXY:-http://mirror.proxy.hpc:8081/repository/go-proxy/,direct}"
    go install github.com/open-policy-agent/conftest@v0.48.0
fi

# Ensure conftest is in system PATH by copying to /usr/local/bin if needed
if [ -f "$GOPATH/bin/conftest" ] && ! command -v conftest &> /dev/null; then
    cp "$GOPATH/bin/conftest" /usr/local/bin/conftest
    chmod +x /usr/local/bin/conftest
fi

echo "conftest version: $(conftest --version 2>&1 | head -1)"

# Install Terraform if not present
# In container build context with network access, download and install
# For local development or restricted network, check if it's available
if ! command -v terraform &> /dev/null; then
    echo "Installing Terraform..."
    # Try to download terraform (works in container build with network access)
    TERRAFORM_VERSION="1.6.6"
    if curl -fsSL --connect-timeout 30 "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip 2>/dev/null; then
        unzip -o /tmp/terraform.zip -d /usr/local/bin
        rm /tmp/terraform.zip
        echo "Terraform ${TERRAFORM_VERSION} installed"
    else
        echo "Note: Terraform download failed (network restricted). Base image should include terraform."
    fi
fi

# Install jq if not present (for JSON processing)
if ! command -v jq &> /dev/null; then
    echo "Installing jq..."
    apt-get update && apt-get install -y jq
fi

echo "jq version: $(jq --version)"

# Verify git and curl are available (should be present in golang base image)
echo "git version: $(git --version)"
echo "curl version: $(curl --version | head -1)"

# Setup Go modules for test directories
echo "=== Setting up Go test dependencies ==="

# Find and initialize Go modules in test directories
TEST_DIRS=$(find /workspace -name "go.mod" -type f 2>/dev/null | xargs -I {} dirname {} || true)

for test_dir in $TEST_DIRS; do
    if [ -d "$test_dir" ]; then
        echo "Setting up Go modules in: $test_dir"
        cd "$test_dir"
        export GOPROXY="${GOPROXY:-http://mirror.proxy.hpc:8081/repository/go-proxy/,direct}"
        go mod download 2>/dev/null || echo "Note: go mod download skipped for $test_dir"
    fi
done

echo "=== Runtime setup complete ==="
echo "Environment variables set:"
echo "  GOROOT=$GOROOT"
echo "  GOPATH=$GOPATH"
echo "  PATH includes: $GOROOT/bin and $GOPATH/bin"
