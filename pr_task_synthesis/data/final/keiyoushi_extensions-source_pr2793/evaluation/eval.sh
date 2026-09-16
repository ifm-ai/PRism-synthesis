#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"
VERIFY_SCRIPT="$TESTS_DIR/verify_fix.sh"

# openenv: activate_runtime
# Activate the environment built during image construction
export JAVA_HOME=/opt/benchmark/temurin-17 && export GRADLE_HOME=/opt/benchmark/gradle-8.7 && export ANDROID_HOME=/opt/android-sdk && export PATH=$JAVA_HOME/bin:$GRADLE_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH

# openenv: install_test_only_extras
# No additional test-only packages needed - verification uses shell-based checks

# openenv: prepare_hidden_assets
# Hidden verifier script is already in place at $TESTS_DIR/verify_fix.sh
# Ensure the script is executable
chmod +x "$VERIFY_SCRIPT"

# Change to workspace context
cd /workspace

# openenv: run_verification
echo ">>>>> Start Test Output"
echo ""
echo "Running VoyceMe extension fix verification..."
echo ""

# Run the hidden verifier script
bash "$VERIFY_SCRIPT"
RC=$?

echo ""
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
