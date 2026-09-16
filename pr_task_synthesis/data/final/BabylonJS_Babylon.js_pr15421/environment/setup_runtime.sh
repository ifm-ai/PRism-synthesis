#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for Babylon.js
# This script sets up Node.js, installs dependencies, and prepares the environment

set -e

echo "=== Babylon.js Environment Setup ==="

# Install system dependencies
echo "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    build-essential \
    ca-certificates \
    curl \
    git \
    libcairo2-dev \
    libjpeg-dev \
    libpango1.0-dev \
    libgif-dev \
    openssl \
    pkg-config \
    wget \
    xvfb \
    || true

# Install Node.js 20.x LTS using direct binary download
echo "Installing Node.js 20.x LTS..."

# Download and install Node.js 20.x binary directly
NODE_VERSION="20.18.0"
NODE_DIR="/opt/nodejs"

# Remove any existing installation
rm -rf "$NODE_DIR"
mkdir -p "$NODE_DIR"

# Download Node.js tarball
curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz

# Extract to target directory
tar -xf /tmp/node.tar.xz -C "$NODE_DIR" --strip-components=1
rm /tmp/node.tar.xz

# Create symlinks
ln -sf "$NODE_DIR/bin/node" /usr/local/bin/node
ln -sf "$NODE_DIR/bin/npm" /usr/local/bin/npm
ln -sf "$NODE_DIR/bin/npx" /usr/local/bin/npx

# Verify Node.js installation
NODE_VERSION_INSTALLED=$(node --version)
NPM_VERSION=$(npm --version)
echo "Installed Node.js: $NODE_VERSION_INSTALLED"
echo "Installed npm: $NPM_VERSION"

# Verify Node.js version is within required range
NODE_MAJOR=$(echo "$NODE_VERSION_INSTALLED" | cut -d'.' -f1 | tr -d 'v')
if [ "$NODE_MAJOR" -lt 16 ] || [ "$NODE_MAJOR" -ge 23 ]; then
    echo "ERROR: Node.js version $NODE_VERSION_INSTALLED is outside required range (>=16.0.0 <23.0.0)"
    exit 1
fi

# Set up global npm configuration
echo "Configuring npm..."
npm config set script-shell /bin/bash
npm config set fund false
npm config set update-notifier false
npm config set prefer-offline true

# Set environment variable to skip puppeteer browser download
export PUPPETEER_SKIP_DOWNLOAD=true
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Install project dependencies
echo "Installing project dependencies..."
cd /workspace

# Run npm install with workspaces, ignoring scripts that can hang
npm install --legacy-peer-deps --ignore-scripts 2>&1 | tail -20

# Install ts-patch globally so it's available
echo "Installing ts-patch globally..."
npm install -g ts-patch 2>&1 | tail -5 || echo "ts-patch global install skipped"

# Install ts-patch in workspace
echo "Installing ts-patch in workspace..."
ts-patch install -s 2>&1 | tail -5 || echo "ts-patch install completed or skipped"

# Build tools if required (this may fail if dependencies aren't fully installed, which is ok)
echo "Building development tools..."
timeout 120 npm run build:tools 2>&1 | tail -10 || echo "Build tools step completed or timed out"

echo "=== Environment Setup Complete ==="
echo "Node.js: $(node --version)"
echo "npm: $(npm --version)"
echo "Workspace: /workspace"
