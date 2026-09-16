#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TEST_PATCH_PATH="$SCRIPT_DIR/test.patch"
TESTS_DIR="$SCRIPT_DIR/tests"

# openenv: activate_runtime
# Activate the environment built during image construction
export JAVA_HOME=/opt/java/jdk8u412-b08 && export PATH=$JAVA_HOME/bin:$PATH && export MAVEN_HOME=/usr/share/maven && export PATH=$MAVEN_HOME/bin:$PATH

# openenv: install_test_only_extras
# No extra test-only dependencies needed - Maven and Java 8 are already available

# openenv: prepare_hidden_assets
# Apply the test.patch to add the test method to the workspace before running tests.
# This test is the verifier that exercises the fix in fix.patch.
if [ -f "$TEST_PATCH_PATH" ]; then
    cd /workspace
    git apply "$TEST_PATCH_PATH"
fi

# openenv: run_verification
cd /workspace

echo ">>>>> Start Test Output"
mvn -pl flink-cdc-runtime -B test -Dtest=PostTransformOperatorTest#testDataChangeEventTransformWithDuplicateColumns
RC=$?
echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
