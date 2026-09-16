#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Activate the environment built during image construction
# Set LD_LIBRARY_PATH before sourcing mlx_activate.sh to avoid set -u errors
source /opt/benchmark/mlx_env/bin/activate
export LD_LIBRARY_PATH="/workspace/python/mlx/lib:${LD_LIBRARY_PATH:-}"
source /opt/benchmark/mlx_env/bin/mlx_activate.sh

# Change to workspace directory
cd /workspace

# openenv: install_test_only_extras
# No extra test-only dependencies needed - numpy and torch already installed at build time

# openenv: prepare_hidden_assets
# Apply the test patch to add the half-precision infinity check test
# The patch is applied to the test file in /workspace/python/tests/
cd /workspace
git apply "$TEST_PATCH_PATH" 2>/dev/null || true

# Check if the fix is present in mlx/random.cpp (look for above_minus_one function)
# If the fix is present, we need to rebuild the C++ extension
if grep -q "above_minus_one" /workspace/mlx/random.cpp; then
    echo "Fix detected in mlx/random.cpp - rebuilding MLX C++ extension..."
    cd /workspace
    pip install -e . --no-build-isolation --force-reinstall --quiet
    REBUILD_EXIT_CODE=$?
    if [ $REBUILD_EXIT_CODE -ne 0 ]; then
        echo "Warning: Rebuild failed with exit code $REBUILD_EXIT_CODE"
    fi
    cd /workspace
fi

# openenv: run_verification
# Run the specific test that checks for half-precision infinity values
# This test exercises the fix in mlx/random.cpp (above_minus_one helper)
echo ">>>>> Start Test Output"
cd /workspace/python/tests && python -m unittest test_random.TestRandom.test_normal
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
