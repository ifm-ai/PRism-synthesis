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
# Activate the Rust environment
source /opt/cargo/env

# openenv: install_test_only_extras
# No additional test-only dependencies needed - cargo test handles dependencies

# openenv: prepare_hidden_assets
# Create the tests directory if it doesn't exist and copy the test file
mkdir -p /workspace/native/core/tests
cp "$TESTS_DIR/decimal_promotion_check.rs" /workspace/native/core/tests/decimal_promotion_check.rs

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the decimal promotion check test from datafusion-comet crate (core)
# This test verifies that low-precision Decimal128 operations do NOT trigger
# unnecessary Decimal256 promotion (the optimization fix in planner.rs)
#
# Expected behavior:
# - FIXED code: Test PASSES (no unnecessary Decimal256 casts)
# - BUGGY code: Test FAILS (finds unnecessary Decimal256 casts)
cd /workspace/native
cargo test --package datafusion-comet --test decimal_promotion_check 2>&1
RC=$?

# openenv: emit_result
echo ">>>>> End Test Output"
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
