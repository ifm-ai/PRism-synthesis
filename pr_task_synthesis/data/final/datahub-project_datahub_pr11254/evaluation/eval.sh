#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Activate the environment built during image construction
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# No additional packages needed - all dependencies installed in base environment

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No runtime mutation of /workspace is needed

# openenv: run_verification
cd /workspace

echo ">>>>> Start Test Output"

# Run the CLUSTERING_KEY verification tests from the external tests directory
# The tests import from /workspace but run from the external test harness
pytest "$TESTS_DIR/test_clustering_key.py" -v --tb=short

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
