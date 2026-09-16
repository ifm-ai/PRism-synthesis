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
# No extra test-only dependencies needed; pytest is already in dev dependencies

# openenv: prepare_hidden_assets
# Apply the test.patch to add the test_custom_ouputs test to test_commands.py
cd /workspace
git apply "$TEST_PATCH_PATH" 2>/dev/null || true

# openenv: run_verification
cd /workspace

echo ">>>>> Start Test Output"
# Skip test data download by setting RAVENPY_SKIP_TEST_DATA=1
RAVENPY_SKIP_TEST_DATA=1 pytest tests/test_commands.py::test_custom_ouputs -v
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
