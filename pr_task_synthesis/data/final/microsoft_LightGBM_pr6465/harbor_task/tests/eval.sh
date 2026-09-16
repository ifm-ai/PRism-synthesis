#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Use OPENENV_WORKSPACE if set, otherwise default to /workspace
WORKSPACE_DIR="${OPENENV_WORKSPACE:-/workspace}"
cd "$WORKSPACE_DIR"
source /opt/conda/etc/profile.d/conda.sh && conda activate lightgbm-env

# openenv: install_test_only_extras
# No extra test-only dependencies needed - pytest is already in the base environment

# openenv: prepare_hidden_assets
# Hidden tests are already in place under TESTS_DIR

# openenv: run_verification
echo ">>>>> Start Test Output"
pytest "$TESTS_DIR/test_no_user_flag.py" -v
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
