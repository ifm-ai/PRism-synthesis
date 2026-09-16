#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace directory where the source code lives
cd /workspace

# openenv: activate_runtime
# No activation command needed - system-level Node.js installation
# Node.js and npm are available globally in the container

# openenv: install_test_only_extras
# No extra test-only dependencies needed beyond what's in package.json
# The hidden test uses only built-in Node.js modules and the project's existing dependencies

# openenv: prepare_hidden_assets
# Copy hidden tests to a temporary hidden subdirectory of workspace/tests
# This allows Jest to discover them using the existing project configuration
HIDDEN_TEST_SUBDIR="/workspace/tests/.openenv_hidden"
rm -rf "$HIDDEN_TEST_SUBDIR"
mkdir -p "$HIDDEN_TEST_SUBDIR"
cp -r "$TESTS_DIR"/* "$HIDDEN_TEST_SUBDIR/"

# openenv: run_verification
# Run only the hidden batch_size fix test
# The test imports the actual code from /workspace/src/transformers.js
# and verifies that addPastKeyValues handles missing dims property correctly

echo ">>>>> Start Test Output"

# Run Jest with the specific test file pattern
# Using the workspace's existing Jest configuration
node --experimental-vm-modules node_modules/jest/bin/jest.js \
    --testPathPatterns=".openenv_hidden/batch_size_fix" \
    --verbose \
    --no-coverage
RC=$?

# Cleanup hidden test directory
rm -rf "$HIDDEN_TEST_SUBDIR"

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
