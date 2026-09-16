#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
cd /workspace
source /opt/conda/etc/profile.d/conda.sh && conda activate benchmark

# openenv: install_test_only_extras
# pytest is already installed in the benchmark environment per setup_runtime.sh
# However, we need to sync Pillow version with the repository state
# The fix.patch changes src/anaconda/.devcontainer/Dockerfile to specify pillow==10.3.0
# We parse the Dockerfile to determine the required version and install it

# Determine the Pillow version from the repository's Dockerfile
DOCKERFILE_PATH="/workspace/src/anaconda/.devcontainer/Dockerfile"
if [ -f "$DOCKERFILE_PATH" ]; then
    # Extract pillow version from Dockerfile (e.g., pillow==10.3.0)
    REQUIRED_PILLOW_VERSION=$(grep -oP 'pillow==\K[0-9.]+' "$DOCKERFILE_PATH" | head -1)
    if [ -n "$REQUIRED_PILLOW_VERSION" ]; then
        # Upgrade/downgrade Pillow to match the repository state
        pip install --quiet "Pillow==${REQUIRED_PILLOW_VERSION}"
    fi
fi

# openenv: prepare_hidden_assets
# Hidden tests are already in place under $TESTS_DIR
# No test.patch was provided, so we use the locally created hidden tests

# openenv: run_verification
echo ">>>>> Start Test Output"
python -m pytest "$TESTS_DIR/test_pillow_version.py" -v
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
