#!/bin/bash
# setup_runtime.sh - Runtime creation script for alloy-rs/core Rust project
# This script is called during image build to prepare the Rust environment
# Handles both rustup-managed and pre-installed Rust toolchains

set -e

echo "=== Setting up Rust runtime environment ==="

# Set environment variables for Rust
export RUSTUP_HOME=/root/.rustup
export CARGO_HOME=/root/.cargo

# Ensure HOME is set correctly for rustup operations during image build
# This is critical when running in container build contexts
if [ -z "$HOME" ] || [ "$HOME" = "/home/agent_sandbox" ]; then
    export HOME=/root
fi

# Function to add environment variables to /etc/environment idempotently
add_to_environment() {
    local key="$1"
    local value="$2"

    # Remove any existing lines with this key
    if [ -f /etc/environment ]; then
        grep -v "^export $key=" /etc/environment > /tmp/env_temp 2>/dev/null || true
        mv /tmp/env_temp /etc/environment
    fi

    # Add the new line
    echo "export $key=$value" >> /etc/environment
}

# Function to configure rustup-managed installation
configure_rustup() {
    echo "Configuring rustup-managed Rust installation..."

    # Source the environment if available
    if [ -f "$CARGO_HOME/env" ]; then
        . "$CARGO_HOME/env"
    fi

    # Set default toolchain explicitly
    rustup default stable

    # Ensure rustup is in PATH for future sessions (idempotent)
    add_to_environment "RUSTUP_HOME" "$RUSTUP_HOME"
    add_to_environment "CARGO_HOME" "$CARGO_HOME"
    add_to_environment "PATH" '"$CARGO_HOME/bin:$PATH"'
}

# Function to handle pre-installed Rust (without rustup)
handle_preinstalled_rust() {
    echo "Using pre-installed Rust toolchain..."
    rustc --version
    cargo --version

    # Set environment variables for pre-installed Rust
    # Find the cargo bin directory from PATH
    CARGO_BIN_DIR=$(dirname "$(command -v cargo)")

    # Add to /etc/environment for persistence (idempotent)
    add_to_environment "CARGO_HOME" "$CARGO_HOME"

    # Only add PATH modification if not already present
    if ! grep -q "CARGO_HOME/bin" /etc/environment 2>/dev/null; then
        echo 'export PATH="$CARGO_HOME/bin:$PATH"' >> /etc/environment
    fi
}

# Check if Rust is already installed
if command -v rustc &> /dev/null && command -v cargo &> /dev/null; then
    echo "Rust toolchain already available"

    # Check if rustup is available and functional
    if command -v rustup &> /dev/null; then
        echo "rustup is available, configuring toolchain..."
        configure_rustup
    else
        echo "rustup not available, using pre-installed Rust..."
        handle_preinstalled_rust
    fi
else
    echo "Installing Rust toolchain via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal

    # Source the environment
    . "$CARGO_HOME/env"

    # Configure rustup
    configure_rustup
fi

# Verify Rust installation
echo "=== Verifying Rust installation ==="
rustc --version
cargo --version

# Verify rustup if available
if command -v rustup &> /dev/null; then
    rustup --version
    rustup show
fi

echo "=== Rust runtime setup complete ==="
