#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for uv (Rust-based Python installer)
# This script sets up the Rust 1.79 toolchain and installs base dependencies

set -e

echo "=== Setting up Rust 1.79 toolchain ==="

# Source cargo environment
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export PATH="$CARGO_HOME/bin:$PATH"

# Check if rustup is already installed
if ! command -v rustup &> /dev/null; then
    echo "Installing rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain 1.79
fi

# Verify rust installation
echo "Verifying Rust installation..."
rustc --version
cargo --version

# Ensure Rust 1.79 toolchain is active (rust-toolchain.toml will enforce this)
rustup show

echo "=== Installing system dependencies ==="

# Install system build dependencies if not already present
if ! command -v cmake &> /dev/null || ! command -v pkg-config &> /dev/null; then
    apt-get update
    apt-get install -y build-essential cmake pkg-config libssl-dev
fi

echo "=== Installing cargo-nextest (test runner) ==="

# Install cargo-nextest if not present - use prebuilt binary
if ! command -v cargo-nextest &> /dev/null && ! cargo nextest --version &> /dev/null 2>/dev/null; then
    echo "Installing cargo-nextest from prebuilt binary..."
    NEXTEST_VERSION="0.9.85"
    NEXTEST_URL="https://github.com/nextest-rs/nextest/releases/download/cargo-nextest-${NEXTEST_VERSION}/nextest-x86_64-unknown-linux-gnu.tar.gz"
    
    if curl -sSfL "$NEXTEST_URL" -o /tmp/nextest.tar.gz 2>/dev/null; then
        tar xzf /tmp/nextest.tar.gz -C "$CARGO_HOME/bin"
        rm -f /tmp/nextest.tar.gz
        echo "cargo-nextest installed successfully"
    else
        echo "Warning: Could not download cargo-nextest prebuilt binary"
        echo "Tests can still be run with 'cargo test' as fallback"
    fi
fi

echo "=== Runtime setup complete ==="
echo "Rust toolchain: $(rustc --version)"
echo "Cargo version: $(cargo --version)"

# Verify git and curl are available (should be in base image)
# Note: git and curl are expected to be in the base image
if command -v git &> /dev/null; then
    echo "Git version: $(git --version)"
else
    echo "Warning: git not found in base image"
fi

if command -v curl &> /dev/null; then
    echo "Curl version: $(curl --version | head -1)"
else
    echo "Warning: curl not found in base image"
fi

echo "=== Setup complete ==="
