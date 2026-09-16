#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
HIDDEN_TEST_FILE="$TESTS_DIR/hidden_token_type_test.go"

# openenv: activate_runtime
# Activate the Go environment as specified in environment_request.json
export PATH=/usr/local/go/bin:$PATH
export GOPATH=/root/go
export GOBIN=$GOPATH/bin

# openenv: install_test_only_extras
# No additional test-only packages needed - Go test handles dependencies via go.mod

# openenv: prepare_hidden_assets
# Create a temporary directory for test execution
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Copy the auth module to temp directory for isolated test execution
# Use the workspace where eval.sh is invoked (PWD)
cp -r "$PWD/auth" "$TMPDIR/"

# Check if TestGrpcCredentialsProvider_TokenType already exists in the test file
# If not, add our hidden test
if ! grep -q "func TestGrpcCredentialsProvider_TokenType" "$TMPDIR/auth/grpctransport/grpctransport_test.go" 2>/dev/null; then
    # Test doesn't exist, copy our hidden test file
    cp "$HIDDEN_TEST_FILE" "$TMPDIR/auth/grpctransport/"
fi

# openenv: run_verification
# Change to the auth module directory and run the test
cd "$TMPDIR/auth"

echo ">>>>> Start Test Output"

# Run the specific test that verifies token type handling
go test -v -run TestGrpcCredentialsProvider_TokenType ./grpctransport/... 2>&1

# Capture the exit code
RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
