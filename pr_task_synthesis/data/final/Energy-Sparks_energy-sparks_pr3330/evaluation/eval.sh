#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
export BUNDLE_PATH=/opt/benchmark/vendor/bundle
export BUNDLE_APP_CONFIG=/opt/benchmark/.bundle
export PATH=$PATH:/opt/benchmark/vendor/bundle/ruby/3.1.0/bin

# openenv: install_test_only_extras
# No additional test-only extras needed - rspec and all dependencies are in the base runtime

# openenv: prepare_hidden_assets
# Apply the test.patch to bring in the test file and factory trait
# The patch modifies spec/factories/schools_factory.rb and creates spec/controllers/schools/usage_controller_spec.rb
cd /workspace
git apply "$TEST_PATCH_PATH" 2>/dev/null || true

# openenv: run_verification
# Run the specific test for the usage controller
echo ">>>>> Start Test Output"
bundle exec rspec spec/controllers/schools/usage_controller_spec.rb
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
