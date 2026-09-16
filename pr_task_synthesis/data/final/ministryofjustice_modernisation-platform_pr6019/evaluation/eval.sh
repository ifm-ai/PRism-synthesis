#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace context
cd /workspace

# openenv: activate_runtime
# Activate the environment built during image construction
export GOROOT=/usr/local/go && export GOPATH=/home/agent_sandbox/go && export PATH=$GOROOT/bin:$GOPATH/bin:$PATH && export GOPROXY=${GOPROXY:-http://mirror.proxy.hpc:8081/repository/go-proxy/,direct}

# openenv: install_test_only_extras
# Download go modules for the test directory if needed
cd "$TESTS_DIR" && go mod download 2>/dev/null || true
cd /workspace

# openenv: prepare_hidden_assets
# Hidden tests are already in place at $TESTS_DIR
# No additional setup needed - tests read from /workspace which is the buggy base

# openenv: run_verification
echo ">>>>> Start Test Output"

# Run the IAM policy verification tests from the external tests directory
cd "$TESTS_DIR"
go test -v ./... 2>&1
RC=$?

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
