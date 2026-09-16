#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
WORKSPACE="${OPENENV_WORKSPACE:-/workspace}"
CRATE_DIR="$WORKSPACE/crates/primitives"

# openenv: activate_runtime
# Activate the Rust environment built during image construction
export RUSTUP_HOME=/root/.rustup
export CARGO_HOME=/root/.cargo
source /root/.cargo/env

# openenv: install_test_only_extras
# No additional test-only dependencies needed - serde_json is already a dev-dependency

# openenv: prepare_hidden_assets
# Copy hidden test files to the crate's tests directory for integration testing
# This is required because Rust integration tests must be in the crate's tests/ directory
mkdir -p "$CRATE_DIR/tests"
cp "$TESTS_DIR/test_signature_v_hex.rs" "$CRATE_DIR/tests/test_signature_v_hex.rs"

# openenv: run_verification
# Change to workspace directory
cd "$WORKSPACE"

# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden integration tests for v hex serialization
# The test verifies that v field is hex-encoded (e.g., "0x1b") not plain integer (e.g., 27)
# Use test name filter that matches all tests in the hidden test file
cargo test --package alloy-primitives --features serde -- test_v --nocapture
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
