#!/bin/bash
# setup_runtime.sh - Runtime setup for Apache Arrow Rust (arrow-rs) project
# This script installs the Rust toolchain and prepares the workspace

set -e

echo "=== Setting up Rust runtime environment ==="

# Check if rustc is available and meets version requirements (>= 1.70.0)
RUSTUP_INSTALLED=false
if command -v rustc &> /dev/null; then
    RUSTC_VERSION=$(rustc --version 2>/dev/null || echo "unknown")
    echo "Found existing rustc: $RUSTC_VERSION"
    
    # Extract version number and check if it meets minimum requirement
    RUSTC_MAJOR=$(echo "$RUSTC_VERSION" | grep -oP 'rustc \K[0-9]+' || echo "0")
    RUSTC_MINOR=$(echo "$RUSTC_VERSION" | grep -oP 'rustc [0-9]+\.\K[0-9]+' || echo "0")
    
    if [ "$RUSTC_MAJOR" -gt 1 ] || { [ "$RUSTC_MAJOR" -eq 1 ] && [ "$RUSTC_MINOR" -ge 70 ]; }; then
        echo "Rust version $RUSTC_VERSION meets minimum requirement (>= 1.70.0). Using existing installation."
        # Rust is pre-installed in the base image, no rustup needed
        # The PATH should already include cargo/bin from the base image
        RUSTUP_INSTALLED=false
    else
        echo "Rust version $RUSTC_VERSION is too old. Installing newer version via rustup..."
        export RUSTUP_HOME=/root/.rustup
        export CARGO_HOME=/root/.cargo
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
        source "$CARGO_HOME/env"
        RUSTUP_INSTALLED=true
    fi
else
    echo "Rust toolchain not found. Installing via rustup..."
    export RUSTUP_HOME=/root/.rustup
    export CARGO_HOME=/root/.cargo
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
    source "$CARGO_HOME/env"
    RUSTUP_INSTALLED=true
fi

# Source the cargo environment only if rustup was installed
export CARGO_HOME=/root/.cargo
if [ "$RUSTUP_INSTALLED" = true ] && [ -f "$CARGO_HOME/env" ]; then
    source "$CARGO_HOME/env"
    echo "Cargo environment sourced from rustup installation."
else
    echo "Using pre-installed Rust toolchain (no rustup)."
fi

# Verify Rust installation
rustc --version
cargo --version

# Install base system dependencies (git and curl should already be present in base image)
# but ensure they're available
echo "Ensuring base system dependencies..."
apt-get update -qq && apt-get install -y -qq git curl pkg-config libssl-dev 2>/dev/null || true

# Navigate to workspace and install project dependencies
if [ -d "/workspace" ]; then
    cd /workspace
    echo "Fetching project dependencies..."
    # Fetch dependencies for the project
    cargo fetch 2>&1 || true
    echo "Project dependencies fetched."
else
    echo "Warning: /workspace directory not found."
fi

echo "=== Runtime setup complete ==="
