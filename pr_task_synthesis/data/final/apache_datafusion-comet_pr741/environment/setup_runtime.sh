#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for DataFusion Comet Rust project
# This script sets up the Rust toolchain and prepares the environment
# Note: Full dependency compilation happens during eval.sh, not here

set -e

echo "=== DataFusion Comet Environment Setup ==="

# Ensure git and curl are available (baseline system packages)
# These are typically pre-installed in the base image
if ! command -v git &> /dev/null; then
    echo "Installing git..."
    apt-get update && apt-get install -y git
fi

if ! command -v curl &> /dev/null; then
    echo "Installing curl..."
    apt-get update && apt-get install -y curl
fi

# Install protobuf-compiler if not present (required for protobuf message generation)
if ! command -v protoc &> /dev/null; then
    echo "Installing protobuf-compiler..."
    apt-get update && apt-get install -y protobuf-compiler
fi

# Install Rust toolchain via rustup if not already available
if ! command -v rustc &> /dev/null || ! command -v cargo &> /dev/null; then
    echo "Installing Rust toolchain 1.79..."
    export RUSTUP_HOME=/opt/rustup
    export CARGO_HOME=/opt/cargo
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.79 --profile minimal

    # Source the cargo environment
    . "/opt/cargo/env"
else
    # Use existing rustup installation
    if [ -d "$HOME/.rustup" ]; then
        export RUSTUP_HOME="$HOME/.rustup"
    fi
    if [ -d "$HOME/.cargo" ]; then
        export CARGO_HOME="$HOME/.cargo"
        export PATH="$CARGO_HOME/bin:$PATH"
    fi
fi

# Source cargo environment if it exists
if [ -f "/opt/cargo/env" ]; then
    . "/opt/cargo/env"
elif [ -f "$HOME/.cargo/env" ]; then
    . "$HOME/.cargo/env"
fi

# Verify Rust installation
echo "Verifying Rust installation..."
rustc --version
cargo --version

# Check minimum Rust version (1.75 required)
RUST_VERSION=$(rustc --version | awk '{print $2}')
echo "Detected Rust version: $RUST_VERSION"

# Pre-download dependencies and do a quick check (faster than full build)
if [ -d "/workspace/native" ]; then
    echo "Pre-fetching Rust dependencies..."
    cd /workspace/native

    # Fetch dependencies (downloads crates without full compilation)
    cargo fetch

    # Do a quick check to ensure the project is valid
    cargo check --message-format=short || true

    echo "Rust environment ready."
else
    echo "Warning: /workspace/native not found, skipping dependency pre-fetch."
fi

echo "=== Setup Complete ==="
