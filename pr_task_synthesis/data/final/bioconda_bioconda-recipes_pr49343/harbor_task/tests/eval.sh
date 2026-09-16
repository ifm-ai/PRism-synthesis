#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Activate the environment built during image construction
source /opt/conda/etc/profile.d/conda.sh && conda activate bioconda

# openenv: install_test_only_extras
# Install pytest and pyyaml for running the hidden tests (if not already present)
# These are test-only dependencies, not part of the base runtime
pip install -q pytest pyyaml 2>/dev/null || true

# openenv: prepare_hidden_assets
# The hidden tests are already in place at $TESTS_DIR
# No additional setup needed as test.patch is not present

# openenv: run_verification
# Use WORKSPACE_DIR env var if set (for testing), otherwise default to /workspace
cd "${WORKSPACE_DIR:-/workspace}"

echo ">>>>> Start Test Output"

# Run the hidden tests that verify the fix is correctly applied
# These tests check meta.yaml and build.sh for the required changes
python -m pytest "$TESTS_DIR/test_fix_verification.py" -v

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
