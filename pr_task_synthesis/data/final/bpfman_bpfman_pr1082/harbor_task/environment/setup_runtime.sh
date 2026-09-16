#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for bpfman Rust eBPF project
# This script creates the Rust environment, installs dependencies, and prepares the project

set -e

echo "=== bpfman Runtime Environment Setup ==="

# Export Rust environment
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"

# Source cargo environment if available
if [ -f "$CARGO_HOME/env" ]; then
    source "$CARGO_HOME/env"
fi

# Verify Rust toolchain
echo "Checking Rust toolchain..."
rustc --version || { echo "ERROR: rustc not found"; exit 1; }
cargo --version || { echo "ERROR: cargo not found"; exit 1; }

# Ensure both stable and nightly toolchains are available
echo "Ensuring nightly toolchain is available..."
rustup toolchain list | grep -q nightly || rustup toolchain install nightly --profile minimal

# Add rust-src component for eBPF development
echo "Adding rust-src component..."
rustup component add rust-src --toolchain nightly 2>/dev/null || true

# Set up workspace
WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

echo "Working directory: $WORKSPACE"

# Install Rust dependencies for the workspace
# This builds the project and downloads all crates
echo "Installing Rust dependencies..."
cargo fetch --verbose

# Build the eBPF programs first (requires libbpf)
# The project uses xtask for custom build tasks
echo "Building eBPF programs..."
if [ -d "./libbpf" ]; then
    cargo xtask build-ebpf --libbpf-dir ./libbpf
else
    # Try without explicit libbpf-dir if submodule not present
    cargo xtask build-ebpf 2>/dev/null || echo "Note: eBPF build skipped (libbpf not available)"
fi

# Build the main project
echo "Building main project..."
cargo build --verbose -p bpfman-api -p bpfman

# Build the RPC binary specifically (mentioned in smoke test)
echo "Building bpfman-rpc binary..."
cargo build --bin bpfman-rpc -p bpfman-api

# Build the CLI binary
echo "Building bpfman CLI binary..."
cargo build --bin bpfman -p bpfman

echo "=== Runtime Environment Setup Complete ==="
echo "Rust toolchain: $(rustc --version)"
echo "Cargo version: $(cargo --version)"
echo "Active toolchain: $(rustup show active-toolchain 2>/dev/null || echo 'N/A')"
