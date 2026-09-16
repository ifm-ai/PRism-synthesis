#!/usr/bin/env bash
# NOTE: do NOT use set -e — the script must capture RC=$? explicitly without premature exit.
set -uo pipefail

# openenv: resolve_paths
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
TESTS_DIR="$SCRIPT_DIR/tests"
# Use the current working directory as the workspace
# This allows the harness to swap /workspace contents between runs
WORKSPACE_DIR="$(pwd)"

# openenv: activate_runtime
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
export GRADLE_USER_HOME=/opt/gradle
export PATH=/opt/gradle/gradle-8.6/bin:$PATH

# openenv: install_test_only_extras
# No additional test dependencies needed - pure Java test using java.time.Instant

# openenv: prepare_hidden_assets
# Create a temporary directory for compiling and running the test
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Copy the test file to temp directory
cp "$TESTS_DIR/ImageSaverTimestampTest.java" "$TEMP_DIR/"

# openenv: run_verification
cd "$WORKSPACE_DIR"

echo ">>>>> Start Test Output"

# Compile the Java test
javac -d "$TEMP_DIR" "$TEMP_DIR/ImageSaverTimestampTest.java"
COMPILE_RC=$?

if [ $COMPILE_RC -ne 0 ]; then
    echo "Compilation failed with exit code $COMPILE_RC"
    RC=$COMPILE_RC
else
    # Run the test from the workspace directory so it can find ImageSaver.kt
    java -Dworkspace.dir="$WORKSPACE_DIR" -cp "$TEMP_DIR" tachiyomi.verification.ImageSaverTimestampTest
    RC=$?
fi

echo ">>>>> End Test Output"

# openenv: emit_result
echo "OPENENV_EXIT_CODE=$RC"
exit $RC
