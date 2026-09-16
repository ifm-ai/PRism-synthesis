#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"
WORKSPACE="/workspace"

# openenv: activate_runtime
# Activate the Rust environment
source "$HOME/.cargo/env"

# openenv: install_test_only_extras
# No additional test-only dependencies needed beyond what the environment provides
# The tests use only std library features

# openenv: prepare_hidden_assets
# Hidden tests are already in place under TESTS_DIR
# No test.patch to apply - tests were synthesized

# openenv: run_verification
# Change to workspace to run tests against the built binaries
cd "$WORKSPACE"

# Ensure binaries are built before running tests
# This uses the existing build infrastructure
cargo build --bin bpfman-rpc -p bpfman-api --quiet 2>/dev/null
cargo build --bin bpfman -p bpfman --quiet 2>/dev/null

# Print start delimiter
echo ">>>>> Start Test Output"

# Create a temporary test runner that uses the hidden tests
TEST_RUNNER_DIR=$(mktemp -d)
trap "rm -rf $TEST_RUNNER_DIR" EXIT

# Copy test files to temp directory for compilation
cp "$TESTS_DIR"/*.rs "$TEST_RUNNER_DIR/"

# Create a minimal Cargo.toml for the test harness
cat > "$TEST_RUNNER_DIR/Cargo.toml" << 'EOF'
[package]
name = "bpfman_verifier_tests"
version = "0.1.0"
edition = "2021"

[dependencies]

[[test]]
name = "verifier_tests"
path = "mod.rs"
EOF

# Run the tests from the temp directory, but binaries are in workspace target/
cd "$TEST_RUNNER_DIR"
RUST_TEST_THREADS=1 cargo test --quiet 2>&1

# Capture the exit code
RC=$?

# openenv: emit_result
# Print end delimiter
echo ">>>>> End Test Output"

# Print exit code for machine parsing
echo "OPENENV_EXIT_CODE=$RC"

exit $RC
