#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
cd /workspace

# openenv: install_test_only_extras
# No additional test-only dependencies needed beyond what's in the base environment

# openenv: prepare_hidden_assets
# Apply the test patch to add the test for non-database boolean attributes
# The test patch adds a test that verifies format_attribute handles nil boolean
# attributes correctly using attribute_types instead of columns_hash.
if [ -f "$TEST_PATCH_PATH" ]; then
  git apply "$TEST_PATCH_PATH" 2>/dev/null || true
fi

# Ensure the test Rails app exists (required for RSpec tests)
if [ ! -d "tmp/test_apps" ]; then
  bundle exec rake setup:create
fi

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the specific test for the display helper boolean attribute issue
# This test verifies that format_attribute properly handles non-database boolean
# attributes with nil values by returning the correct status-tag HTML.
# On buggy code: uses columns_hash which doesn't work for virtual attributes -> test fails
# On fixed code: uses attribute_types which works for virtual attributes -> test passes
bundle exec rspec spec/helpers/display_helper_spec.rb \
  --example "calls status_tag even when attribute is nil"

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
