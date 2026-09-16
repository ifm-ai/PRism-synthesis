#!/bin/bash
# setup_runtime.sh - Build-time runtime creation script for .NET project
# This script is called by repo_setup.sh after creating /workspace
# It sets up the .NET runtime environment and installs base dependencies

set -e

echo "=== Setting up .NET runtime environment ==="

# Ensure .NET SDK is available (installed via base image)
if ! command -v dotnet &> /dev/null; then
    echo "ERROR: .NET SDK not found. Ensure base image includes dotnet-sdk-8.0"
    exit 1
fi

echo "Using .NET SDK version: $(dotnet --version)"

# Disable telemetry for cleaner output
export DOTNET_CLI_TELEMETRY_OPTOUT=1

# Create workspace directory if it doesn't exist
mkdir -p /workspace
cd /workspace

# Restore NuGet packages for all projects in the solution
# This downloads all dependencies needed for building and testing
# Note: This requires network access to nuget.org
echo "=== Restoring NuGet packages ==="
# Use timeout to prevent hanging on network issues; restore can happen at test time
if timeout 60 dotnet restore --verbosity minimal 2>&1; then
    echo "NuGet restore completed successfully"
else
    RESTORE_EXIT=$?
    if [ "$RESTORE_EXIT" -eq 124 ]; then
        echo "WARNING: dotnet restore timed out (network issue)"
    else
        echo "WARNING: dotnet restore exited with code $RESTORE_EXIT"
    fi
    echo "Packages will be restored at test time if needed."
fi

echo "=== .NET runtime setup complete ==="
exit 0
