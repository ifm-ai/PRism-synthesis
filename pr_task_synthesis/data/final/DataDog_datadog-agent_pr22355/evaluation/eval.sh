#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# Change to workspace directory
cd /workspace

# openenv: activate_runtime
# Activate the environment built during image construction
export PATH=/usr/local/go/bin:$PATH && export GOPATH=/root/go

# openenv: install_test_only_extras
# No additional test-only packages needed - all dependencies are in go.mod

# openenv: prepare_hidden_assets
# Copy hidden tests to the package directory so they can access internal functions
# This is required because Go tests need to be in the same package to access unexported functions
cp "$TESTS_DIR"/containerd_image_consolidation_test.go /workspace/comp/core/workloadmeta/collectors/internal/containerd/

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden tests from the package directory
# The tests verify the image metadata consolidation behavior introduced in the fix:
# - getPreferredName method selects: repo digest > repo tag > image ID
# - knownImages structure consolidates multiple references to the same image ID
# - Reference tracking correctly categorizes repo tags vs repo digests
# - Name update logic only updates when new name is more readable
cd /workspace
go test -tags containerd -v ./comp/core/workloadmeta/collectors/internal/containerd/... -run "TestKnownImagesGetPreferredName|TestKnownImagesAddReferenceConsolidation|TestKnownImagesDeleteReference|TestIsAnImageID|TestIsARepoDigest|TestImageMetadataConsolidationLogic|TestNameUpdateWhenMoreReadable|TestKnownImagesReferenceReplacement"

# Capture the exit code
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
