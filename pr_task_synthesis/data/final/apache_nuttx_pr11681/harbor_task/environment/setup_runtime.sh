#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for Apache NuttX RTOS
# This script prepares the build environment for NuttX with nsh_cm7 configuration

set -e

echo "=== Setting up NuttX build environment ==="

# Ensure we're in the workspace directory
WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

# Install system packages if not already present (idempotent)
echo "Checking system dependencies..."

# Check for required tools
REQUIRED_TOOLS="make gcc g++ cmake bison flex gawk gperf"
MISSING_TOOLS=""
for tool in $REQUIRED_TOOLS; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS $tool"
    fi
done

# Check for ARM GCC toolchain
if ! command -v arm-none-eabi-gcc &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS gcc-arm-none-eabi"
fi

# Check for git and curl (should be present in base image)
if ! command -v git &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS git"
fi
if ! command -v curl &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS curl"
fi

if [ -n "$MISSING_TOOLS" ]; then
    echo "Installing missing system packages:$MISSING_TOOLS"
    apt-get update -qq
    DEBIAN_FRONTEND="noninteractive" apt-get install -y -qq $MISSING_TOOLS || true
fi

# Clone nuttx-apps repository as a SIBLING of the nuttx source tree
# The NuttX tools/configure.sh script expects apps/ to be at ../apps relative to
# the nuttx root directory (TOPDIR). So if nuttx is at /workspace, apps should be at /apps
APPS_DIR="/apps"
if [ ! -d "${APPS_DIR}" ]; then
    echo "Cloning nuttx-apps repository to ${APPS_DIR}..."
    if ! git clone --depth 1 https://github.com/apache/nuttx-apps.git "${APPS_DIR}"; then
        echo "ERROR: Failed to clone nuttx-apps repository"
        exit 1
    fi
    echo "nuttx-apps cloned successfully to ${APPS_DIR}"
else
    echo "nuttx-apps already present at ${APPS_DIR}, skipping clone"
fi

# Verify the apps directory structure is correct for configure.sh
# The configure.sh script looks for ../apps relative to the nuttx root (TOPDIR)
if [ ! -d "${APPS_DIR}" ]; then
    echo "ERROR: apps directory not found at ${APPS_DIR}"
    exit 1
fi
if [ ! -d "${WORKSPACE}/tools" ]; then
    echo "ERROR: tools directory not found at ${WORKSPACE}/tools"
    exit 1
fi
echo "Verified: apps/ exists at ${APPS_DIR} and tools/ exists at ${WORKSPACE}/tools"

# Install kconfig-frontends for kconfig-tweak command (required by NuttX configure.sh)
# The python3-kconfiglib package doesn't include the kconfig-tweak command
echo "Installing kconfig-frontends for kconfig-tweak..."
apt-get update -qq && apt-get install -y -qq kconfig-frontends

# Install Python test dependencies using --user flag for Ubuntu 22.04 compatibility
echo "Installing Python test dependencies..."
pip3 install --user -q \
    pexpect==4.8.0 \
    pytest==6.2.5 \
    pytest-repeat==0.9.1 \
    pytest-json==0.4.0 \
    pytest-ordering==0.6 \
    pyserial==3.5 || true

# Return to workspace
cd "$WORKSPACE"

# Clean any previous build artifacts
echo "Cleaning previous build artifacts..."
make distclean 2>/dev/null || true

# kconfig-tweak is now installed system-wide via apt, no PATH modification needed

# Configure NuttX with nsh_cm7 configuration (base config available in both buggy and fixed repos)
# The pysim_cm7 config is added by the fix.patch for simulator-based testing
echo "Configuring NuttX with nucleo-h745zi:nsh_cm7..."
./tools/configure.sh nucleo-h745zi:nsh_cm7

# Verify configuration was successful
if [ -f ".config" ]; then
    echo "NuttX configured successfully"
else
    echo "Warning: .config not found, configuration may have failed"
fi

echo "=== NuttX build environment setup complete ==="
echo "To build: cd $WORKSPACE && make"
echo "To test: cd $WORKSPACE/tools/ci/testrun && pytest"
