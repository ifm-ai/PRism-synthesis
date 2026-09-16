#!/bin/bash
# setup_runtime.sh - Runtime creation script for Rust/Cargo environment
# This script is executed at image build time to set up the Rust toolchain and dependencies

set -e

echo "=== Setting up Rust/Cargo runtime environment ==="

# Set explicit paths before running rustup
export RUSTUP_HOME="${RUSTUP_HOME:-/root/.rustup}"
export CARGO_HOME="${CARGO_HOME:-/root/.cargo}"

# Install Rust toolchain via rustup (stable channel)
# This ensures a consistent Rust version across builds
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal

# Source Rust environment from the standard location
if [ -f "$CARGO_HOME/env" ]; then
    source "$CARGO_HOME/env"
fi

# Ensure PATH includes cargo bin
export PATH="$CARGO_HOME/bin:$PATH"

# Set default toolchain explicitly in case it wasn't set
rustup default stable 2>/dev/null || true

# Verify Rust installation
rustc --version
cargo --version

echo "Rust toolchain installed"

# Note: cargo fetch is skipped here to avoid network timeouts during setup
# Dependencies will be downloaded on first build in the container

# Set up git configuration for the repository
git config --global http.proxyAuthMethod basic
git config --global http.lowSpeedLimit 0
git config --global http.lowSpeedTime 999999
git config --global http.version HTTP/1.1
git config --global http.postBuffer 1048576000

echo "=== Runtime setup complete ==="
