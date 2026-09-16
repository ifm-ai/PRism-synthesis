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
# No activation command needed - system-level installation (activation_command is empty)

# openenv: install_test_only_extras
# No additional packages needed - all dependencies installed during environment setup

# openenv: prepare_hidden_assets
# Copy hidden test file to the test_cases directory where CMake will find it
# We use a libs subdirectory to match the existing test organization
mkdir -p /workspace/tests/src/test_cases/libs
cp "$TESTS_DIR/test_gif_imgdsc_header.c" /workspace/tests/src/test_cases/libs/

# openenv: run_verification
# Build LVGL tests and run the specific GIF header test
# First, clean any previous build
rm -rf /workspace/tests/build_test_sysheap

# Build the test configuration
cd /workspace/tests
cmake -S . -B build_test_sysheap -GNinja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DOPTIONS_TEST_SYSHEAP=1 \
    2>&1
CMAKE_RC=$?

if [ $CMAKE_RC -ne 0 ]; then
    echo "CMake configuration failed with exit code: $CMAKE_RC"
    RC=$CMAKE_RC
    echo ">>>>> Start Test Output"
    echo "CMake configuration failed"
    echo ">>>>> End Test Output"
    echo "OPENENV_EXIT_CODE=$RC"
    exit $RC
fi

# Build all tests (this will include our GIF test)
# The test will fail to compile with the buggy version because:
# - imgdsc is lv_draw_buf_t (not lv_image_dsc_t)
# - lv_draw_buf_t doesn't have 'reserved' field
# - lv_draw_buf_t.data is non-const
cmake --build build_test_sysheap --target test_gif_imgdsc_header 2>&1
BUILD_RC=$?

if [ $BUILD_RC -ne 0 ]; then
    echo "Build failed with exit code: $BUILD_RC"
    echo "This indicates the buggy version is present (imgdsc is lv_draw_buf_t instead of lv_image_dsc_t)"
    RC=$BUILD_RC
    echo ">>>>> Start Test Output"
    echo "Compilation failed - buggy version detected"
    echo "The fix changes imgdsc from lv_draw_buf_t to lv_image_dsc_t"
    echo ">>>>> End Test Output"
    echo "OPENENV_EXIT_CODE=$RC"
    exit $RC
fi

# Run only the GIF imgdsc header test
cd /workspace/tests/build_test_sysheap
ctest --output-on-failure --tests-regex test_gif_imgdsc_header 2>&1
RC=$?

# openenv: emit_result
echo ">>>>> Start Test Output"
if [ $RC -eq 0 ]; then
    echo "All tests passed - fix is present"
    echo "imgdsc is correctly typed as lv_image_dsc_t"
    echo "Header fields (magic, flags, stride, data_size) are properly initialized"
else
    echo "Tests failed with exit code: $RC"
fi
echo ">>>>> End Test Output"

echo "OPENENV_EXIT_CODE=$RC"
exit $RC
