#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
# Use externally set WORKSPACE if available, otherwise default to /workspace
export WORKSPACE="${WORKSPACE:-/workspace}"

# openenv: activate_runtime
# No activation command needed (system-level install per environment_request.json)
cd "$WORKSPACE"

# openenv: install_test_only_extras
# pytest is already available in the environment

# openenv: prepare_hidden_assets
# The test.patch is available at TEST_PATCH_PATH for reference
# Hidden tests are in TESTS_DIR and are executed externally

# openenv: run_verification
echo ">>>>> Start Test Output"

# Test runner invocation: pytest
pytest "${TESTS_DIR}/test_kubehound_stix_bundles.py"
RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
