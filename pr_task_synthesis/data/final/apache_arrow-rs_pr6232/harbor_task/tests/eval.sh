#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace directory (use PARQUET_WORKSPACE env var if set, otherwise default to /workspace)
WORKSPACE_DIR="${PARQUET_WORKSPACE:-/workspace}"
cd "$WORKSPACE_DIR"

# openenv: activate_runtime
# Activate the Rust environment (as specified in environment_request.json)
source /root/.cargo/env || true

# openenv: install_test_only_extras
# No additional test-only dependencies needed - cargo test handles dependency resolution

# openenv: prepare_hidden_assets
# The test harness is a standalone Cargo project in $TESTS_DIR
# It depends on the parquet crate from /workspace/parquet

# openenv: run_verification
# Run the hidden test harness that verifies the infinite loop fix
# The test harness is in /artifacts/evaluation/tests/ and depends on /workspace/parquet
# Uses cargo test as the authoritative test runner with a timeout to detect infinite loops

echo ">>>>> Start Test Output"

# Update Cargo.toml to point to the correct parquet path
# The sed command replaces the path value in the [dependencies.parquet] section
sed -i 's|^path = ".*"|path = "'"$WORKSPACE_DIR/parquet"'"|' "$TESTS_DIR/Cargo.toml"

# Verify the path was updated correctly
echo "Updated Cargo.toml parquet path to: $WORKSPACE_DIR/parquet"

cd "$TESTS_DIR"

# Build first without timeout to allow for compilation time
echo "Building in release mode..."
cargo build --release
BUILD_RC=$?
if [ $BUILD_RC -ne 0 ]; then
    echo "BUILD FAILED: Build failed with exit code $BUILD_RC"
    RC=$BUILD_RC
else
    # Run only the test execution with timeout to detect infinite loops
    # Exit code 124 from timeout indicates the test timed out (infinite loop bug present)
    # Exit code 0 means tests passed (fix is present)
    # Any other non-zero exit code means test failure
    echo "Running cargo test --release with 30-second timeout (build complete)..."
    timeout 30 cargo test --release --no-run 2>/dev/null
    BUILD_CHECK_RC=$?
    if [ $BUILD_CHECK_RC -eq 0 ]; then
        # Now run the actual tests with timeout
        timeout 30 cargo test --release -- --test-threads=1
        RC=$?
    else
        RC=$BUILD_CHECK_RC
    fi
fi

# Check if timeout occurred (exit code 124 from timeout command)
# This indicates the infinite loop bug is present
if [ $RC -eq 124 ]; then
    echo "TEST FAILED: Test timed out after 30 seconds, indicating infinite loop bug is present"
fi

cd /workspace

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
