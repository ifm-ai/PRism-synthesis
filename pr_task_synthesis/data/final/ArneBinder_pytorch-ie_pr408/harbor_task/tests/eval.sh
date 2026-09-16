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
source $(poetry env info --path)/bin/activate

# openenv: install_test_only_extras
# Reinstall the package from /workspace to ensure current state is tested
pip install -e . --quiet

# openenv: prepare_hidden_assets
# Hidden tests are stored externally under $TESTS_DIR
# No modification to /workspace is needed - tests reference /workspace imports

# openenv: run_verification
# Print start delimiter
echo ">>>>> Start Test Output"

# Run the hidden test for annotation sorting from external tests directory
poetry run pytest "$TESTS_DIR/test_annotation_sort.py" -v
RC=$?

# Print end delimiter
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
