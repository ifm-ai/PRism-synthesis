#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace context
cd /workspace

# openenv: activate_runtime
# Activate the environment built during image construction
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# Install PyYAML for YAML parsing in tests (if not already present)
pip install --quiet PyYAML 2>/dev/null || true

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No additional setup needed - tests are external to /workspace

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden tests that verify the import path fix
python -m pytest "$TESTS_DIR/test_import_path_fix.py" -v

# Capture exit code
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
