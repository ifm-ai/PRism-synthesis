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

# Change to workspace directory
cd /workspace

# openenv: install_test_only_extras
# Copy workspace Python source files over the installed PyPI package
# This allows us to override Python source files while keeping compiled extensions from PyPI
cp -r /workspace/apis/python/src/tiledb/vector_search/*.py /opt/benchmark/venv/lib/python3.11/site-packages/tiledb/vector_search/

# openenv: prepare_hidden_assets
# Apply the test patch to add the hidden verifier tests
# The test.patch modifies test_distance_metrics.py and common.py to add comprehensive distance metric tests
if [ -f "$TEST_PATCH_PATH" ]; then
    # Apply the test patch to add the verifier tests
    git apply "$TEST_PATCH_PATH" 2>/dev/null || true
fi

# Apply fix.patch conditionally based on TEST_WITH_FIX environment variable
if [ "${TEST_WITH_FIX:-0}" = "1" ]; then
    # Apply the fix patch to test with the fixed code
    FIX_PATCH_PATH="/tasks/fix.patch"
    if [ -f "$FIX_PATCH_PATH" ]; then
        git apply "$FIX_PATCH_PATH" 2>/dev/null || true
    fi
fi

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the distance metrics tests
# These tests verify COSINE and INNER_PRODUCT distance metric support
cd /workspace/apis/python
pytest test/test_distance_metrics.py -s \
    -x \
    -v \
    --tb=short \
    -k "test_cosine_distance or test_inner_product_distances or test_ivf_flat_cosine_simple or test_ivf_flat_ingestion_cosine"
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
