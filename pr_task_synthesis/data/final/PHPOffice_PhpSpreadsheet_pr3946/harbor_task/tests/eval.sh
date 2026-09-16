#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# No activation command needed - PHP uses system-level installation
cd /workspace

# openenv: install_test_only_extras
# Install composer dependencies if vendor/ doesn't exist
if [ ! -d "vendor" ]; then
    composer install --no-progress --prefer-dist --optimize-autoloader
fi

# openenv: prepare_hidden_assets
# Apply test.patch to create the test file in /workspace
if [ -f "$TEST_PATCH_PATH" ]; then
    git apply "$TEST_PATCH_PATH"
fi

# openenv: run_verification
# Run the specific PHPUnit test for the Conditional bug
echo ">>>>> Start Test Output"
vendor/bin/phpunit tests/PhpSpreadsheetTests/Style/ConditionalFormatting/PR3946Test.php
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
