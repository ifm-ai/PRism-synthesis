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
source /root/.cargo/env

# openenv: install_test_only_extras
# No additional test-only dependencies needed - rstest is already in dev-dependencies

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# The test file test_se_skip_certs.rs verifies SE_SKIP_CERTS_VERIFICATION behavior

# openenv: run_verification
# Run the hidden tests that verify SE_SKIP_CERTS_VERIFICATION behavior
# These tests are external to /workspace and verify the environment variable parsing
# that is central to the fix.patch changes

echo ">>>>> Start Test Output"

# Run the hidden tests for SE_SKIP_CERTS_VERIFICATION
# The tests verify that:
# 1. SE_SKIP_CERTS_VERIFICATION=true parses as true (enabling skip mode)
# 2. SE_SKIP_CERTS_VERIFICATION=false/unset/invalid parses as false (verification enabled)
# 3. The default constant is "false" for secure-by-default behavior
# 4. The env_or_default macro works correctly for this variable
# Tests run from /workspace but use external test crate under $TESTS_DIR
cargo test --manifest-path "$TESTS_DIR/Cargo.toml" --features se-verifier
RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
