#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
cd /workspace
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# No additional packages needed - test dependencies already installed in runtime

# openenv: prepare_hidden_assets
# Apply the test patch to introduce the new test columns for all-null categorical
# and extension dtype handling. Use --forward to skip if already applied.
patch -p1 --forward < "$TEST_PATCH_PATH" || true

# openenv: run_verification
echo ">>>>> Start Test Output"
cd /workspace/apis/python
python -m pytest tests/test_basic_anndata_io.py::test_null_obs -v
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
