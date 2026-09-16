#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
# Resolve paths relative to the script location
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to the workspace directory (supports TEST_WORKSPACE_PATH env var for flexibility)
cd "${TEST_WORKSPACE_PATH:-/workspace}"

# openenv: activate_runtime
# No activation command needed - Node.js is system-installed in the container
# The environment_request.json has activation_command: "" (system-level install)

# openenv: install_test_only_extras
# No additional packages needed - Jest is already available via npm workspaces

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# The test file was created at synthesis time and is ready to run

# openenv: run_verification
# Print the start delimiter
echo ">>>>> Start Test Output"

# Run the WGSL shader fixes test using the external Jest config
# The --runInBand flag ensures tests run sequentially for deterministic output
# The --config flag points to our external Jest configuration
# The test file is external to the workspace but runs in the /workspace context
# Use the workspace's Jest binary which is already installed
cd "$SCRIPT_DIR"
/workspace/node_modules/.bin/jest --config "$TESTS_DIR/jest.config.external.js" --runInBand --no-coverage 2>&1

# Capture the exit code immediately after the test command
RC=$?

# Print the end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
# Print the exit code for the outer pipeline
echo "OPENENV_EXIT_CODE=$RC"

# Exit with the captured exit code
exit $RC
