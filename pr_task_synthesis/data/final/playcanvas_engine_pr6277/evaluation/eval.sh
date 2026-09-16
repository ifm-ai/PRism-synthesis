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
export CHROME_BIN=/usr/bin/chromium

# openenv: install_test_only_extras
# No additional test-only dependencies needed - all required packages are installed via setup_runtime.sh

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No test.patch to apply - tests were created locally

# Create symlink to node_modules for ESM module resolution
# This allows external tests to resolve 'chai' and other packages
if [ ! -L "$TESTS_DIR/node_modules" ]; then
    ln -sf /workspace/node_modules "$TESTS_DIR/node_modules"
fi

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the hidden tests that verify the fix
# Test 1: Duplicate attribute handling in shader-utils.js
# Test 2: Conditional sampler uniforms in particle shaders
# Use --no-warnings to suppress ESM loader warnings and ensure proper module resolution
NODE_OPTIONS="--no-warnings" npm test -- --require test/fixtures.mjs "$TESTS_DIR/test-shader-utils-duplicate-attrs.test.mjs" "$TESTS_DIR/test-particle-shader-conditionals.test.mjs" 2>&1
RC=$?

# Emit explicit pass/fail summary for verifier recognition
if [ "$RC" -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "TEST RESULT: PASSED"
    echo "All tests passed successfully."
    echo "========================================"
else
    echo ""
    echo "========================================"
    echo "TEST RESULT: FAILED"
    echo "One or more tests failed."
    echo "========================================"
fi

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
