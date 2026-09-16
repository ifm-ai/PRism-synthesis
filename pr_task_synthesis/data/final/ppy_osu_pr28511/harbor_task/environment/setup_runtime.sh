#!/bin/bash
# setup_runtime.sh - Build-time runtime setup script for osu!lazer (.NET 8.0)
# This script is idempotent and safe to run multiple times
# No NuGet package restoration needed - test runner uses only .NET BCL

set -e

echo "=== Setting up .NET 8.0 SDK runtime ==="

# Install system packages (git and curl are baseline requirements)
if ! command -v git &> /dev/null || ! command -v curl &> /dev/null; then
    echo "Installing baseline system packages (git, curl)..."
    apt-get update -qq
    apt-get install -y -qq git curl
fi

# Check if .NET SDK 8.0 is already installed
if command -v dotnet &> /dev/null; then
    DOTNET_VERSION=$(dotnet --version 2>/dev/null || echo "unknown")
    echo "dotnet SDK already installed: $DOTNET_VERSION"
else
    echo "Installing .NET 8.0 SDK via Microsoft packages..."

    # Download and install Microsoft package signing key and repository
    wget -q https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
    dpkg -i /tmp/packages-microsoft-prod.deb
    rm -f /tmp/packages-microsoft-prod.deb

    # Update package lists
    apt-get update -qq

    # Install .NET 8.0 SDK
    apt-get install -y -qq dotnet-sdk-8.0

    echo ".NET 8.0 SDK installed successfully"
fi

# Verify .NET installation
dotnet --version
echo "dotnet SDK setup complete"

# Set up environment variables for .NET
export DOTNET_ROOT=/usr/share/dotnet
export PATH=$PATH:$DOTNET_ROOT

echo "=== Runtime setup complete ==="
echo "Note: Test execution uses only .NET BCL types - no NuGet package restoration needed."
