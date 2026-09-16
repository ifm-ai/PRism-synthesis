#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
# Use OPENENV_WORKSPACE if set, otherwise default to /workspace
WORKSPACE="${OPENENV_WORKSPACE:-/workspace}"

# Change to workspace
cd "$WORKSPACE"

# openenv: activate_runtime
# Activate the Python virtual environment built during image construction
source /opt/benchmark/gudhi_env/bin/activate

# openenv: install_test_only_extras
# No additional test-only dependencies needed beyond what's in the base environment
# The gudhi TensorFlow layers are pure Python and don't require C++ compilation for this test

# openenv: prepare_hidden_assets
# The hidden tests are already in place under $TESTS_DIR
# No test.patch file exists, so we use the locally created tests
echo "Hidden tests directory: $TESTS_DIR"
ls -la "$TESTS_DIR"

# openenv: run_verification
echo "=== Running hidden verifier tests ==="
echo ">>>>> Start Test Output"

# Run the instantiation tests from the tests directory
# These tests verify that TensorFlow layers can be instantiated without errors
# The tests focus on perslay.py which is pure Python and doesn't require C++ modules
# The tests load the perslay module directly to avoid package __init__.py dependencies
python -m pytest "$TESTS_DIR/test_tensorflow_layers_instantiation.py" -v --tb=short

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
