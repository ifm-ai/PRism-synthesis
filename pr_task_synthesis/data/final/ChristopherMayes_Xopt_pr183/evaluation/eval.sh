#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
cd /workspace
source /opt/conda/etc/profile.d/conda.sh && conda activate xopt-dev

# openenv: install_test_only_extras
# No additional packages needed - all dependencies already in xopt-dev environment

# openenv: prepare_hidden_assets
# Apply the test patch to add the test_cnsga_baddf test to the existing test file
# The patch is applied to /workspace/tests/generators/ga/test_cnsga.py
# First reset any previous changes to ensure clean state
git checkout -- tests/generators/ga/test_cnsga.py 2>/dev/null || true
git apply "$TEST_PATCH_PATH" 2>/dev/null || {
    echo "Warning: Could not apply test patch, test may already be present"
}

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the specific test that verifies the fix for non-unique DataFrame indices
# This test exercises the CNSGAGenerator with DataFrames that have duplicate indices
# The test verifies that population size stays at configured limit (32) even with
# DataFrames that have non-unique indices
python -m pytest tests/generators/ga/test_cnsga.py::test_cnsga_baddf -v

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
