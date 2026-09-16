#!/bin/bash
# Setup runtime for Bevy Rust project
# This script installs Rust toolchain and system dependencies required for Bevy development

set -e

echo "=== Setting up Bevy Rust runtime ==="

# Install system dependencies required for Bevy on Linux
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    git \
    curl \
    pkg-config \
    libasound2-dev \
    libudev-dev \
    libwayland-dev \
    libxkbcommon-dev \
    ca-certificates \
    build-essential \
    libssl-dev

echo "System dependencies installed."

# Install rustup and Rust toolchain
echo "Installing Rust toolchain via rustup..."
export RUSTUP_HOME=/opt/rustup
export CARGO_HOME=/opt/cargo
export PATH="$CARGO_HOME/bin:$PATH"

# Download rustup installer
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh

# Run rustup installer with stable Rust (1.76.0+ required by Bevy 0.13.0)
chmod +x /tmp/rustup-init.sh
/tmp/rustup-init.sh -y --default-toolchain stable --no-modify-path

# Clean up installer
rm -f /tmp/rustup-init.sh

# Verify installation
echo "Verifying Rust installation..."
/opt/cargo/bin/rustc --version
/opt/cargo/bin/cargo --version

# Set up environment variables for the shell
echo "Setting up environment variables..."
cat > /etc/profile.d/rust-env.sh << 'EOF'
export RUSTUP_HOME=/opt/rustup
export CARGO_HOME=/opt/cargo
export PATH="$CARGO_HOME/bin:$PATH"
EOF

echo "=== Bevy Rust runtime setup complete ==="
