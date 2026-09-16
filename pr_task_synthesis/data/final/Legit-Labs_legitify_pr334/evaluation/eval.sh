#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
export GOPATH=/root/go
export PATH=/usr/local/go/bin:${GOPATH}/bin:${PATH}

# openenv: install_test_only_extras
# No additional test-only packages needed - Go test resolves dependencies automatically

# openenv: prepare_hidden_assets
# Apply the test patch to add the test to the test package (only if not already present)
cd /workspace
if ! grep -q "func TestGitlabRepositoryRestrictsOverrideVariables" test/repository_test.go 2>/dev/null; then
    git apply "$TEST_PATCH_PATH" 2>/dev/null || true
fi

# Rebuild to ensure embedded policies are updated
go build ./...

# openenv: run_verification
cd /workspace

# Print start delimiter
echo ">>>>> Start Test Output"

# Run the specific test that verifies the overriding_defined_variables_isnt_restricted policy
# This test checks that:
# - When RestrictUserDefinedVariables=false, the policy should report a violation (expectFailure=true)
# - When RestrictUserDefinedVariables=true, the policy should not report a violation (expectFailure=false)
# Using -v flag for verbose output to ensure at least 2 non-blank lines in test output
go test -v -count=1 -timeout=5m -run TestGitlabRepositoryRestrictsOverrideVariables ./test/...

# Capture exit code
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
