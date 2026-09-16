#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Activate the environment built during image construction
source /opt/benchmark/mlcommons-venv/bin/activate

# Change to workspace context
cd /workspace

# openenv: install_test_only_extras
# Install any test-only extras if needed (pytest should already be installed)
# This section is reserved for additional test dependencies not in the base environment

# openenv: prepare_hidden_assets
# The hidden tests are already in place under $TESTS_DIR
# No additional setup needed for the test files

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the librosa API compatibility tests
pytest "$TESTS_DIR/test_librosa_api_compatibility.py" -v

# Capture the exit code
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
