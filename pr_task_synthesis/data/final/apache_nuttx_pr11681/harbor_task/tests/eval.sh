#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
# Resolve the verifier bundle directory from the script location
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace context
cd /workspace

# openenv: activate_runtime
# No activation command needed (system-level install per environment_request.json)
# The environment was prepared by setup_runtime.sh at build time

# openenv: install_test_only_extras
# pytest is already installed as part of base_setup_commands
# No additional test-only dependencies needed

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No test.patch to apply - tests are created locally

# openenv: run_verification
# Run the hidden tests from the tests directory
# Tests verify the fix by checking /workspace for:
# - Core bug fix: setbits = 0 initialization in stm32_adc.c
# - New driver files exist with proper structure (ADC, GPIO, PWM, QEncoder, USB)
# - pysim_cm7 configuration has proper settings
# - Makefile updates include new drivers
# - Board header updates include pin definitions

echo ">>>>> Start Test Output"

# Run pytest with the hidden tests, pointing to the test directory
# The tests verify the fix.patch was correctly applied to /workspace
PYTHONPATH="$TESTS_DIR" python3 -m pytest "$TESTS_DIR/test_fix_verification.py" -v --tb=short

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
