#!/usr/bin/env bash
# Hidden verifier script for VoyceMe extension fix
# This script verifies the fix.patch changes are correctly applied
# It must be run from /workspace context

set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
WORKSPACE_DIR="/workspace"

BUILD_GRADLE="$WORKSPACE_DIR/src/en/voyceme/build.gradle"
VOYCEME_KT="$WORKSPACE_DIR/src/en/voyceme/src/eu/kanade/tachiyomi/extension/en/voyceme/VoyceMe.kt"

ERRORS=0

echo "===== VoyceMe Extension Fix Verification ====="
echo ""

# Test 1: Verify baseUrl is https://www.voyce.me (not http://voyce.me)
echo "Test 1: Checking baseUrl uses HTTPS..."
if grep -q 'override val baseUrl = "https://www.voyce.me"' "$VOYCEME_KT"; then
    echo "  PASS: baseUrl is correctly set to https://www.voyce.me"
else
    echo "  FAIL: baseUrl is NOT set to https://www.voyce.me"
    echo "        Found: $(grep 'override val baseUrl' "$VOYCEME_KT" 2>/dev/null || echo 'not found')"
    ERRORS=$((ERRORS + 1))
fi

# Test 2: Verify extVersionCode is 4 (not 3)
echo "Test 2: Checking extVersionCode is 4..."
if grep -q 'extVersionCode = 4' "$BUILD_GRADLE"; then
    echo "  PASS: extVersionCode is correctly set to 4"
else
    echo "  FAIL: extVersionCode is NOT set to 4"
    echo "        Found: $(grep 'extVersionCode' "$BUILD_GRADLE" 2>/dev/null || echo 'not found')"
    ERRORS=$((ERRORS + 1))
fi

# Test 3: Verify isNsfw = false is present
echo "Test 3: Checking isNsfw flag is set to false..."
if grep -q 'isNsfw = false' "$BUILD_GRADLE"; then
    echo "  PASS: isNsfw is correctly set to false"
else
    echo "  FAIL: isNsfw is NOT set to false"
    echo "        Found: $(grep 'isNsfw' "$BUILD_GRADLE" 2>/dev/null || echo 'not found')"
    ERRORS=$((ERRORS + 1))
fi

# Test 4: Verify no insecure http://voyce.me URL remains
echo "Test 4: Checking no insecure http://voyce.me URL remains..."
if grep -q 'http://voyce\.me' "$VOYCEME_KT"; then
    echo "  FAIL: Insecure http://voyce.me URL still present"
    echo "        Found: $(grep 'http://voyce\.me' "$VOYCEME_KT")"
    ERRORS=$((ERRORS + 1))
else
    echo "  PASS: No insecure http://voyce.me URL found"
fi

# Test 5: Verify build.gradle syntax is valid (can be parsed)
echo "Test 5: Checking build.gradle syntax..."
if [ -f "$BUILD_GRADLE" ]; then
    # Basic syntax check - ensure ext block is properly structured
    if grep -q 'ext {' "$BUILD_GRADLE" && grep -q '}' "$BUILD_GRADLE"; then
        echo "  PASS: build.gradle has valid ext block structure"
    else
        echo "  FAIL: build.gradle ext block structure is invalid"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  FAIL: build.gradle file not found"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "===== Verification Summary ====="
echo "Errors: $ERRORS"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo "All tests PASSED - Fix is correctly applied"
    exit 0
else
    echo "Tests FAILED - Fix is NOT correctly applied"
    exit 1
fi
