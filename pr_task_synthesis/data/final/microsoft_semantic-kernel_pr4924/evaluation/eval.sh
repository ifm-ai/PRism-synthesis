#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
source /workspace/python/.venv/bin/activate

# openenv: install_test_only_extras
# No additional packages needed - pytest and pytest-asyncio already installed

# openenv: prepare_hidden_assets
# Hidden tests are already in $TESTS_DIR

# openenv: run_verification
cd /workspace/python

echo ">>>>> Start Test Output"
pytest "$TESTS_DIR/test_logprobs_attribute_safety.py" -v
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
