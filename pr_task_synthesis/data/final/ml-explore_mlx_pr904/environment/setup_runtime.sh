#!/bin/bash
# setup_runtime.sh - Build-time runtime creation for MLX library
# Creates Python environment, installs system deps, and builds MLX from source
# Configured for proxy environment with custom PyPI mirror

set -eo pipefail

echo "=== MLX Runtime Setup ==="

# Configure pip for proxy environment
# Use the internal PyPI proxy mirror for faster and more reliable installs
export PIP_INDEX_URL="http://mirror.proxy.hpc:8081/repository/pypi-proxy/simple/"
export PIP_TRUSTED_HOST="mirror.proxy.hpc"

# Configure pip timeout for large package downloads (e.g., torch ~2GB)
# Default timeout is 15 seconds which is too short for large packages through proxy
export PIP_DEFAULT_TIMEOUT="300"

# Create pip config directory and set persistent timeout configuration
mkdir -p /root/.pip
cat > /root/.pip/pip.conf << 'EOF'
[global]
index-url = http://mirror.proxy.hpc:8081/repository/pypi-proxy/simple/
trusted-host = mirror.proxy.hpc
timeout = 300
EOF

# Install system dependencies
echo "Installing system dependencies..."
apt-get update -qq 2>/dev/null || apt-get update
apt-get install -y -qq \
    cmake \
    libblas-dev \
    liblapack-dev \
    liblapacke-dev \
    python3-venv \
    python3-dev \
    git \
    curl \
    > /dev/null 2>&1 || apt-get install -y cmake libblas-dev liblapack-dev liblapacke-dev python3-venv python3-dev git curl

echo "System dependencies installed."

# Create Python virtual environment for MLX
VENV_DIR="/opt/benchmark/mlx_env"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv for subsequent operations
export PATH="$VENV_DIR/bin:$PATH"
export VIRTUAL_ENV="$VENV_DIR"

# Upgrade pip and install build dependencies
echo "Installing Python build dependencies..."
pip install --upgrade pip setuptools wheel --timeout=300 -q

# Fix setuptools version for torch compatibility (torch requires setuptools<82)
pip install "setuptools<82" --timeout=300 -q

# Install nanobind - use PyPI version which is faster than building from git
# The pyproject.toml specifies a git commit, but recent PyPI versions are compatible
echo "Installing nanobind..."
pip install --no-cache-dir --timeout=300 nanobind -q

# Install cmake package
echo "Installing cmake package..."
pip install --no-cache-dir --timeout=300 "cmake>=3.24" -q

# Install test dependencies
# Use extended timeout for torch (2GB package) through proxy
echo "Installing test dependencies (numpy, torch)..."
pip install --no-cache-dir --timeout=300 numpy torch -q

# Build and install MLX from source
# Use MLX_BUILD_METAL=OFF for Linux compatibility
# Note: This build step takes ~5-10 minutes as it compiles C++ code
echo "Building MLX from source (this may take 5-10 minutes)..."
cd /workspace

# Capture full output to log file for debugging
BUILD_LOG="/tmp/mlx_build.log"
echo "Build log will be written to: $BUILD_LOG"

# Use extended timeout (600s) for the MLX build as it compiles C++ code
CMAKE_ARGS="-DMLX_BUILD_METAL=OFF" pip install --no-cache-dir --timeout=600 -e . -v 2>&1 | tee "$BUILD_LOG"
BUILD_EXIT_CODE=${PIPESTATUS[0]}

if [ $BUILD_EXIT_CODE -ne 0 ]; then
    echo "ERROR: MLX build failed with exit code $BUILD_EXIT_CODE"
    echo "Last 50 lines of build log:"
    tail -50 "$BUILD_LOG"
    exit $BUILD_EXIT_CODE
fi

echo "MLX build completed successfully"

# Set up library path for the shared library
# The editable install puts libmlx.so in /workspace/python/mlx/lib/
echo "Setting up library path..."
cat > "$VENV_DIR/bin/mlx_activate.sh" << 'EOF'
#!/bin/bash
# MLX-specific activation script
export LD_LIBRARY_PATH="/workspace/python/mlx/lib:$LD_LIBRARY_PATH"
EOF
chmod +x "$VENV_DIR/bin/mlx_activate.sh"

echo "=== MLX Runtime Setup Complete ==="
echo "Activation command: source $VENV_DIR/bin/activate && source $VENV_DIR/bin/mlx_activate.sh"
