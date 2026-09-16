#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace directory
cd /workspace

# openenv: activate_runtime
# Activate the environment built during image construction
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# No additional test-only dependencies needed; pytest is already installed in base environment

# openenv: prepare_hidden_assets
# Hidden tests are already in place at $TESTS_DIR
# No test.patch file was provided; tests are synthesized from fix.patch analysis

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the hidden verifier tests from the external tests directory
# The tests verify that BigDLLM correctly handles optimize_model and use_cache flags
# SOURCE_ROOT is set to /workspace (the buggy repo state in the final image)
export SOURCE_ROOT=/workspace
python -m pytest "$TESTS_DIR/test_bigdl_llm_kwargs.py" -v

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
