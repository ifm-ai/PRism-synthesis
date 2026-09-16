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
source /opt/benchmark/venv/bin/activate

# openenv: install_test_only_extras
# Use PYTHONPATH to prioritize workspace source over installed package
# This ensures tests run against the workspace code, not a pre-installed version
export PYTHONPATH="/workspace/sdk/ml/azure-ai-ml:${PYTHONPATH:-}"

# openenv: prepare_hidden_assets
# Apply the test.patch to use camelCase task strings ("chatCompletion", "textCompletion")
# These tests verify that the SDK accepts camelCase input and converts to snake_case for REST
# Only apply if not already applied (check if patch would apply cleanly)
if [ -f "$TEST_PATCH_PATH" ]; then
    if ! git apply --check "$TEST_PATCH_PATH" 2>/dev/null; then
        echo "test.patch already applied or not applicable"
    else
        git apply "$TEST_PATCH_PATH"
    fi
fi

# openenv: run_verification
# Run the specific finetuning schema tests that verify camelCase task handling
# These tests use camelCase task strings ("chatCompletion", "textCompletion")
# and verify the SDK correctly accepts them and converts to snake_case for REST
# Set environment variables to skip the test proxy which would otherwise hang
export AZURE_TEST_RUN_LIVE=true
export AZURE_SKIP_LIVE_RECORDING=true

echo ">>>>> Start Test Output"
cd /workspace/sdk/ml/azure-ai-ml && pytest tests/finetuning_job/unittests/test_azure_openai_finetuning_job_schema.py::TestAzureOpenAIFineTuningJobSchema::test_azure_openai_finetuning_job_full tests/finetuning_job/unittests/test_custom_model_finetuning_job_schema.py::TestCustomModelFineTuningJobSchema::test_custom_model_finetuning_job_full -v
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
