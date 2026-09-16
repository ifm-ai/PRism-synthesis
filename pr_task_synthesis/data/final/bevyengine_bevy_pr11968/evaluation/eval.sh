#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"
FIX_VERIFIER_DIR="$TESTS_DIR/fix_verifier"

# Change to the workspace directory (the buggy repository)
cd /workspace

# openenv: activate_runtime
# Activate the Rust environment built during image construction
export RUSTUP_HOME=/opt/rustup
export CARGO_HOME=/opt/cargo
export PATH="$CARGO_HOME/bin:$PATH"

# openenv: install_test_only_extras
# No additional test-only dependencies needed

# openenv: prepare_hidden_assets
# Copy the fix verifier test crate to a temporary location
# Tests must NOT be copied into /workspace to avoid mutating the reference checkout
TEMP_TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_TEST_DIR"' EXIT
cp -r "$FIX_VERIFIER_DIR" "$TEMP_TEST_DIR/"

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the fix verifier test using cargo test
# The test verifies the MSAA multi-camera fix through implementation pattern matching
cd "$TEMP_TEST_DIR/fix_verifier"
cargo test --test verify_fix --release -- --nocapture 2>&1

# Capture the exit code from cargo test
RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
