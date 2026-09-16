#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
# Use OPENENV_WORKSPACE if set, otherwise default to /workspace
WORKSPACE_BASE="${OPENENV_WORKSPACE:-/workspace}"
WORKSPACE_PKG_DIR="${WORKSPACE_BASE}/pkg/clustermesh/common"

# openenv: activate_runtime
# Activate the Go 1.22.0 runtime built during image construction
export PATH=/usr/local/go/bin:/root/go/bin:$PATH
export GOPATH=/root/go
export GOROOT=/usr/local/go

# openenv: install_test_only_extras
# No additional test-only dependencies needed - using standard Go testing with testify

# openenv: prepare_hidden_assets
# Copy test files from external location to the package directory so they can access source files
cp "${TESTS_DIR}/channel_deadlock_test.go" "${WORKSPACE_PKG_DIR}/channel_deadlock_test.go"

# openenv: run_verification
cd "${WORKSPACE_PKG_DIR}"

# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden deadlock test that verifies the channel buffer fix
# This test runs from the package directory so it can access remote_cluster.go
# The test verifies that a buffered channel (capacity 1) prevents deadlock
go test -v -timeout 60s -run "TestChannelBufferFixAtLine270|TestGetClusterConfigNoDeadlock" .
RC=$?

# Cleanup: Remove test files from workspace after execution
rm -f "${WORKSPACE_PKG_DIR}/channel_deadlock_test.go"

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
