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
export GOPATH=/root/go && export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin && export CGO_CFLAGS_ALLOW=-Xpreprocessor

# openenv: install_test_only_extras
# No additional test-only packages needed - dependencies handled via go mod download in setup_runtime

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No test.patch to apply - tests were created during synthesis
# The tests directory has its own go.mod that replaces the vips module with /workspace/vips

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden tests for TIFF export functionality from the external tests directory
# These tests verify the Pyramid, Tile, TileHeight, and TileWidth fields exist and work correctly
# The tests import the vips package from /workspace via go.mod replace directive
# Without the fix, these tests will fail to compile because the fields don't exist in TiffExportParams
cd "$TESTS_DIR"
CGO_CFLAGS_ALLOW=-Xpreprocessor go test -v -mod=mod .
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
