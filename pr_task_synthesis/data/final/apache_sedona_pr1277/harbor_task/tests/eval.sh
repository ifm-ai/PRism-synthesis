#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Activate the environment built during image construction
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

# Determine workspace directory (use WORKSPACE env var if set, otherwise default to /workspace)
WORKSPACE_DIR="${WORKSPACE:-/workspace}"

# Always use the venv from /workspace (shared environment)
source /workspace/python/.venv/bin/activate

# Change to the target workspace directory
cd "${WORKSPACE_DIR}"

# openenv: install_test_only_extras
# Install pyspark as test-only extra for Spark-related tests
pip install pyspark

# Reinstall sedona from current workspace to pick up fix.patch changes
pip install -e "${WORKSPACE_DIR}/python" --no-deps

# openenv: prepare_hidden_assets
# The hidden tests are already in place under TESTS_DIR
# Apply the test.patch to understand what tests exist (for reference only)
# The actual test execution uses the hidden tests under TESTS_DIR

# openenv: run_verification
# Run the hidden verifier tests for ST_S2ToGeom function
# These tests verify:
# 1. ST_S2ToGeom function exists and is callable in Python API
# 2. ST_S2ToGeom is properly exported from sedona.sql.st_functions
# 3. ST_S2ToGeom has the expected function signature
echo ">>>>> Start Test Output"

python -m pytest "$TESTS_DIR/test_st_s2_to_geom_quick.py" -v

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
