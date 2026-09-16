#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
WORKSPACE_DIR="/workspace"

# openenv: activate_runtime
# Activate the environment built during image construction
source /opt/benchmark/dali_venv/bin/activate
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

# openenv: install_test_only_extras
# Install any test-only dependencies if needed (pytest already installed in runtime)
# No additional packages needed for our tests

# openenv: prepare_hidden_assets
# Copy test files to a temporary location for execution
# The tests are already in $TESTS_DIR and will be referenced from there
# Create a temporary test runner directory
TEMP_TEST_DIR=$(mktemp -d)
trap "rm -rf $TEMP_TEST_DIR" EXIT

# Copy Python test files to temp directory
cp "$TESTS_DIR"/test_string_view_api.py "$TEMP_TEST_DIR/"
cp "$TESTS_DIR"/test_fix_verification.py "$TEMP_TEST_DIR/"

# openenv: run_verification
# Change to workspace context as required
cd "$WORKSPACE_DIR"

# Print start delimiter
echo ">>>>> Start Test Output"

# Run the Python tests
# The test will pass if DALI is built and the API works correctly
# The test will skip if DALI is not built (which is expected in some scenarios)
# We use pytest with verbose output
python -m pytest "$TEMP_TEST_DIR/test_string_view_api.py" "$TEMP_TEST_DIR/test_fix_verification.py" -v --tb=short 2>&1

# Capture the exit code explicitly
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# Print exit code marker
echo "OPENENV_EXIT_CODE=$RC"

exit $RC
