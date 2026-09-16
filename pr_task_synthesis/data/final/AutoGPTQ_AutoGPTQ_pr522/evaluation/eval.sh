#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# Test dependencies (pytest, parameterized) are already installed in the base environment
# No additional packages needed for these tests

# openenv: prepare_hidden_assets
# The hidden tests are already in place under $TESTS_DIR
# No additional setup required - tests are external to /workspace

# openenv: run_verification
cd /workspace

echo ">>>>> Start Test Output"

# Run the marlin_utils interface tests
# These tests verify the fix was applied by checking:
# 1. marlin_utils module exists and can be imported
# 2. Key functions have correct signatures
# 3. BaseQuantizeConfig has is_marlin_format field
# The buggy code will fail with ImportError because marlin_utils.py doesn't exist
python -m pytest "$TESTS_DIR/test_marlin_utils.py" -v

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
