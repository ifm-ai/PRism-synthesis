#!/bin/bash
# Setup runtime for Rust 1.75.0 benchmark environment
# This script is run at image build time to prepare the Rust toolchain and environment

set -e

# Install build-essential for C compiler/linker required by Rust
apt-get update && apt-get install -y build-essential

# Ensure we're using the correct Rust toolchain
export RUSTUP_HOME=/root/.rustup
export CARGO_HOME=/root/.cargo
export PATH="/root/.cargo/bin:$PATH"

# Verify Rust is available
if ! command -v rustc &> /dev/null; then
    echo "ERROR: Rust is not installed"
    exit 1
fi

# Verify Rust version is 1.75.0
RUST_VERSION=$(rustc --version | awk '{print $2}')
if [ "$RUST_VERSION" != "1.75.0" ]; then
    echo "Setting Rust toolchain to 1.75.0..."
    rustup default 1.75.0
fi

# Verify cargo is available
if ! command -v cargo &> /dev/null; then
    echo "ERROR: Cargo is not installed"
    exit 1
fi

# Install proptest-related dev dependencies for the firezone-relay package
# This ensures the test dependencies are cached in the image
cd /workspace/rust
echo "Installing dev dependencies for firezone-relay with proptest feature..."
cargo fetch --package firezone-relay --features proptest 2>/dev/null || true

echo "Rust runtime setup complete."
echo "  rustc: $(rustc --version)"
echo "  cargo: $(cargo --version)"
echo "  rustup: $(rustup --version)"
