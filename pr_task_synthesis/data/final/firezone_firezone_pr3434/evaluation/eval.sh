#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
WORKSPACE="/workspace"

# openenv: activate_runtime
export RUSTUP_HOME=/root/.rustup
export CARGO_HOME=/root/.cargo
export PATH="/root/.cargo/bin:$PATH"

# openenv: install_test_only_extras
# No additional packages needed - proptest feature is enabled at test time

# openenv: prepare_hidden_assets
# Apply the test.patch to the workspace at runtime (in a temporary manner)
# The patch modifies rust/relay/tests/regression.rs to add IPv6 ping-pong tests
cd "$WORKSPACE"
git apply "$TEST_PATCH_PATH" 2>/dev/null || true

# openenv: run_verification
cd "$WORKSPACE/rust"

# Clean the firezone-relay package to ensure fresh compilation
cargo clean -p firezone-relay 2>/dev/null || true

echo ">>>>> Start Test Output"

# Run the deterministic test that exercises can_relay_to() fix
# This test creates IPv6 allocation and binds to IPv6 peer
# - Buggy code: can_relay_to() returns false -> test fails
# - Fixed code: can_relay_to() returns true -> test passes
cargo test --package firezone-relay --features proptest test_ipv6_allocation_can_bind_ipv6_peer -- --nocapture

RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
