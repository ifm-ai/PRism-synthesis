#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
# Use current working directory to support both /workspace and /workspace_fixed contexts
BENCHMARK_FILE="$(pwd)/cpp/src/parquet/arrow/reader_writer_benchmark.cc"

# openenv: activate_runtime
# Activate the conda environment built during image construction
source /opt/conda/etc/profile.d/conda.sh && conda activate arrow-cpp

# openenv: install_test_only_extras
# Install pytest as a test-only dependency for running verification tests
pip install --quiet pytest

# openenv: prepare_hidden_assets
# The pytest-based test file is already in place at $TESTS_DIR/test_benchmark_fix.py
# Export the benchmark file path for the test to use
export BENCHMARK_FILE

# Change to workspace directory for verification
cd /workspace

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run pytest test runner against the benchmark fix verification tests
python3 -m pytest "$TESTS_DIR/test_benchmark_fix.py" -v
RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
