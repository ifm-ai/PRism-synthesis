#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
source $HOME/.cargo/env

# openenv: install_test_only_extras
# No additional test-only dependencies needed - cargo test handles build deps

# openenv: prepare_hidden_assets
# Apply the test.patch to add --isolated expectations to the snapshot tests
cd /workspace
git checkout -- crates/uv/tests/help.rs
git apply "$TEST_PATCH_PATH"

# openenv: run_verification
cd /workspace
echo ">>>>> Start Test Output"
cargo test --package uv --test help
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
