package tachiyomi.verification;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.stream.Stream;

/**
 * Verification test for the DATE_MODIFIED fix in ImageSaver.kt.
 *
 * This test inspects the actual ImageSaver.kt source code to verify that
 * DATE_MODIFIED uses epochSecond (seconds) instead of toEpochMilli() (milliseconds).
 *
 * Bug: Using toEpochMilli() produces millisecond values (trillions) which Android
 * interprets as seconds, resulting in dates far in the future (year ~58000).
 *
 * Fix: Using epochSecond produces second values (billions) which Android correctly
 * interprets as the current date.
 */
public class ImageSaverTimestampTest {

    // Use the workspace.dir system property to find ImageSaver.kt
    // This allows the test to work with both /workspace (buggy) and /workspace_fixed (fixed)
    private static final String IMAGE_SAVER_PATH = System.getProperty("workspace.dir", "/workspace") + "/app/src/main/java/eu/kanade/tachiyomi/data/saver/ImageSaver.kt";

    public static void main(String[] args) {
        int failures = 0;

        System.out.println("ImageSaver.kt DATE_MODIFIED Fix Verification");
        System.out.println("============================================");
        System.out.println("");

        // Read the ImageSaver.kt source code
        String sourceCode;
        try {
            sourceCode = readSourceFile(IMAGE_SAVER_PATH);
            System.out.println("Successfully read ImageSaver.kt");
        } catch (IOException e) {
            System.out.println("FAIL: Could not read ImageSaver.kt: " + e.getMessage());
            System.out.println("VERIFICATION FAILED: Cannot verify fix without source file");
            System.exit(1);
            return;
        }

        // Test 1: Verify that DATE_MODIFIED uses epochSecond (not toEpochMilli)
        try {
            testDateModifiedUsesEpochSecond(sourceCode);
            System.out.println("PASS: DATE_MODIFIED uses epochSecond (seconds)");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }

        // Test 2: Verify that toEpochMilli is NOT used for DATE_MODIFIED
        try {
            testDateModifiedDoesNotUseToEpochMilli(sourceCode);
            System.out.println("PASS: DATE_MODIFIED does not use toEpochMilli()");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }

        // Test 3: Verify the fix pattern is present (Instant.now().epochSecond)
        try {
            testFixPatternPresent(sourceCode);
            System.out.println("PASS: Fix pattern Instant.now().epochSecond is present");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }

        // Test 4: Verify buggy pattern is NOT present for DATE_MODIFIED
        try {
            testBuggyPatternAbsent(sourceCode);
            System.out.println("PASS: Buggy pattern toEpochMilli() is not used for DATE_MODIFIED");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }

        System.out.println("");
        System.out.println("========================================");
        System.out.println("Tests completed: " + (4 - failures) + "/4 passed");
        System.out.println("========================================");

        if (failures > 0) {
            System.out.println("VERIFICATION FAILED: " + failures + " test(s) failed");
            System.out.println("The fix has NOT been applied correctly.");
            System.exit(1);
        } else {
            System.out.println("VERIFICATION PASSED: All tests passed");
            System.out.println("The fix has been applied correctly - DATE_MODIFIED uses epochSecond.");
            System.exit(0);
        }
    }

    private static String readSourceFile(String path) throws IOException {
        Path filePath = Paths.get(path);
        return Files.readString(filePath);
    }

    private static void testDateModifiedUsesEpochSecond(String sourceCode) {
        // Look for the pattern: DATE_MODIFIED to Instant.now().epochSecond
        // The fix should have: MediaStore.Images.Media.DATE_MODIFIED to Instant.now().epochSecond
        boolean hasCorrectPattern = sourceCode.contains("DATE_MODIFIED to Instant.now().epochSecond") ||
                                    sourceCode.contains("DATE_MODIFIED  to Instant.now().epochSecond");

        if (!hasCorrectPattern) {
            throw new AssertionError("DATE_MODIFIED should use Instant.now().epochSecond");
        }
    }

    private static void testDateModifiedDoesNotUseToEpochMilli(String sourceCode) {
        // Look for the buggy pattern: DATE_MODIFIED to Instant.now().toEpochMilli()
        boolean hasBuggyPattern = sourceCode.contains("DATE_MODIFIED to Instant.now().toEpochMilli()") ||
                                  sourceCode.contains("DATE_MODIFIED  to Instant.now().toEpochMilli()");

        if (hasBuggyPattern) {
            throw new AssertionError("DATE_MODIFIED should NOT use toEpochMilli() - this is the bug");
        }
    }

    private static void testFixPatternPresent(String sourceCode) {
        // The fix pattern is Instant.now().epochSecond
        if (!sourceCode.contains("Instant.now().epochSecond")) {
            throw new AssertionError("Fix pattern 'Instant.now().epochSecond' should be present in source");
        }
    }

    private static void testBuggyPatternAbsent(String sourceCode) {
        // The buggy pattern is Instant.now().toEpochMilli() specifically for DATE_MODIFIED
        // We need to check if toEpochMilli() is used in the context of DATE_MODIFIED
        String[] lines = sourceCode.split("\n");
        for (String line : lines) {
            if (line.contains("DATE_MODIFIED") && line.contains("toEpochMilli()")) {
                throw new AssertionError("Buggy pattern 'toEpochMilli()' found on DATE_MODIFIED line: " + line.trim());
            }
        }
    }
}
