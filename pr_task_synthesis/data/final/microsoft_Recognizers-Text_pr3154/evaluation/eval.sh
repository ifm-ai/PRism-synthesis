#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace for test execution
cd "${WORKSPACE:-/workspace}"

# openenv: activate_runtime
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# No additional test-only packages needed - pytest already installed in venv

# openenv: prepare_hidden_assets
# Hidden tests are already in place at $TESTS_DIR
# Clear Python bytecode cache to ensure fresh module loading
find "${WORKSPACE:-/workspace}/Python" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$TESTS_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /opt/benchmark/venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Regenerate Python resources from YAML patterns if the pattern files have been updated
# This is required when fix.patch has been applied to pick up the new pattern definitions
cd "${WORKSPACE:-/workspace}/Python/libraries/resource-generator"
python index.py "${WORKSPACE:-/workspace}/Python/libraries/recognizers-date-time/resource-definitions.json" 2>/dev/null || true
python index.py "${WORKSPACE:-/workspace}/Python/libraries/recognizers-number-with-unit/resource-definitions.json" 2>/dev/null || true
cd "${WORKSPACE:-/workspace}"

# Clear bytecode cache again after regeneration to ensure fresh module loading
find "${WORKSPACE:-/workspace}/Python" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Reinstall recognizers packages in editable mode to pick up regenerated resources
pip install -e "${WORKSPACE:-/workspace}/Python/libraries/recognizers-date-time/" --no-deps -q 2>/dev/null || true
pip install -e "${WORKSPACE:-/workspace}/Python/libraries/recognizers-number-with-unit/" --no-deps -q 2>/dev/null || true
pip install -e "${WORKSPACE:-/workspace}/Python/libraries/recognizers-suite/" --no-deps -q 2>/dev/null || true

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the Spanish datetime/age recognition fix tests
python -m pytest "$TESTS_DIR/test_spanish_datetime_age_fix.py" -v --tb=short

RC=$?

# openenv: emit_result
echo ">>>>> End Test Output"
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
