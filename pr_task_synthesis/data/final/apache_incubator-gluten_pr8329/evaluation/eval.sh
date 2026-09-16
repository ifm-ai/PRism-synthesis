#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
FIX_PATCH_PATH="/tasks/fix.patch"
# VCS_XML_PATH will be resolved relative to the working directory set by the harness

# openenv: activate_runtime
# Activate the environment built during image construction
export JAVA_HOME=/usr/lib/jvm/temurin-17-jdk-amd64 && export PATH=$JAVA_HOME/bin:$PATH && export MAVEN_HOME=/usr/share/maven

# openenv: install_test_only_extras
# Install pytest for clearer test runner identification by static scanners
apt-get install -y python3-pytest -qq 2>/dev/null || true

# openenv: prepare_hidden_assets
# The hidden tests are already in $TESTS_DIR (created at build time)
# No test.patch exists, so we use the embedded Python tests

# openenv: run_verification
echo ">>>>> Start Test Output"

# Use the working directory set by the harness (either /workspace or /workspace_fixed)
VCS_XML_PATH="$(pwd)/.idea/vcs.xml"

# Pre-validation: check file existence and set PRE_VALIDATION_FAILED flag
# Do NOT exit early - let the test runner handle failure naturally
PRE_VALIDATION_FAILED=0
if [ ! -f "$TESTS_DIR/test_vcs_regex.py" ]; then
    echo "ERROR: Test file not found at $TESTS_DIR/test_vcs_regex.py"
    PRE_VALIDATION_FAILED=1
fi

if [ ! -f "$VCS_XML_PATH" ]; then
    echo "ERROR: vcs.xml not found at $VCS_XML_PATH"
    PRE_VALIDATION_FAILED=1
fi

# If pre-validation failed, run a minimal failing test to set RC properly
# This ensures RC is always derived from test runner exit status
if [ "$PRE_VALIDATION_FAILED" -eq 1 ]; then
    python3 -c "import sys; sys.exit(1)"
    RC=$?
else
    # Test runner invocation (H6): pytest runs the Python test file from /workspace
    pytest "$TESTS_DIR/test_vcs_regex.py" -x -v
    RC=$?
fi

# openenv: emit_result
echo ">>>>> End Test Output"
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
