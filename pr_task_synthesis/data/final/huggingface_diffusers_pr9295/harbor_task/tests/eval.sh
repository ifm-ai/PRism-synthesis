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
# No additional test-only packages needed beyond what's in the base environment

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No test.patch to apply - tests are synthesized locally

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden tests for LoRA conversion functionality
# These tests verify the _convert_kohya_flux_lora_to_diffusers() and
# _convert_xlabs_flux_lora_to_diffusers() functions
pytest "$TESTS_DIR/test_lora_conversion.py" -v --tb=short

# Capture the exit code explicitly
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
