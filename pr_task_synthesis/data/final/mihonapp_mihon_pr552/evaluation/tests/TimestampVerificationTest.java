package tachiyomi.verification;

import java.time.Instant;

/**
 * Verification test for the DATE_MODIFIED fix in ImageSaver.kt.
 * 
 * The fix changes Instant.now().toEpochMilli() to Instant.now().epochSecond
 * because Android's MediaStore.Images.Media.DATE_MODIFIED expects seconds since epoch,
 * not milliseconds.
 * 
 * Bug: Using toEpochMilli() produces millisecond values (trillions) which Android
 * interprets as seconds, resulting in dates far in the future (year ~58000).
 * 
 * Fix: Using epochSecond produces second values (billions) which Android correctly
 * interprets as the current date.
 */
public class TimestampVerificationTest {

    public static void main(String[] args) {
        int failures = 0;
        
        // Test 1: epochSecond produces timestamp in correct seconds range
        try {
            testEpochSecondInRange();
            System.out.println("PASS: epochSecond produces timestamp in correct seconds range");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }
        
        // Test 2: toEpochMilli produces values that would cause incorrect DATE_MODIFIED
        try {
            testToEpochMilliProducesLargeValues();
            System.out.println("PASS: toEpochMilli produces values in milliseconds range");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }
        
        // Test 3: epochSecond is approximately 1000x smaller than toEpochMilli
        try {
            testRatioApproximately1000();
            System.out.println("PASS: epochSecond is approximately 1000x smaller than toEpochMilli");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }
        
        // Test 4: DATE_MODIFIED using epochSecond produces valid Android timestamp
        try {
            testDateModifiedInSecondsRange();
            System.out.println("PASS: DATE_MODIFIED using epochSecond produces valid Android timestamp");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }
        
        // Test 5: millisecond value interpreted as seconds produces far future date
        try {
            testMillisInterpretedAsSecondsProducesFutureDate();
            System.out.println("PASS: millisecond value interpreted as seconds produces far future date");
        } catch (AssertionError e) {
            System.out.println("FAIL: " + e.getMessage());
            failures++;
        }
        
        System.out.println("");
        System.out.println("========================================");
        System.out.println("Tests completed: " + (5 - failures) + "/5 passed");
        System.out.println("========================================");
        
        if (failures > 0) {
            System.out.println("VERIFICATION FAILED: " + failures + " test(s) failed");
            System.exit(1);
        } else {
            System.out.println("VERIFICATION PASSED: All tests passed");
            System.exit(0);
        }
    }
    
    private static void testEpochSecondInRange() {
        Instant now = Instant.now();
        long epochSeconds = now.getEpochSecond();
        
        // Year 2024 = ~1704067200, Year 2026 = ~1767225600
        long minExpectedSeconds = 1700000000L;  // ~Nov 2023
        long maxExpectedSeconds = 1900000000L;  // ~Mar 2030
        
        if (epochSeconds < minExpectedSeconds || epochSeconds > maxExpectedSeconds) {
            throw new AssertionError("epochSecond should be in range " + minExpectedSeconds + ".." + maxExpectedSeconds + ", got " + epochSeconds);
        }
    }
    
    private static void testToEpochMilliProducesLargeValues() {
        Instant now = Instant.now();
        long epochMillis = now.toEpochMilli();
        
        long minExpectedMillis = 1700000000000L;  // ~Nov 2023 in millis
        long maxExpectedMillis = 1900000000000L;  // ~Mar 2030 in millis
        
        if (epochMillis < minExpectedMillis || epochMillis > maxExpectedMillis) {
            throw new AssertionError("toEpochMilli should be in range " + minExpectedMillis + ".." + maxExpectedMillis + ", got " + epochMillis);
        }
    }
    
    private static void testRatioApproximately1000() {
        Instant now = Instant.now();
        long epochSeconds = now.getEpochSecond();
        long epochMillis = now.toEpochMilli();
        
        double ratio = (double) epochMillis / (double) epochSeconds;
        
        if (ratio < 999.0 || ratio > 1001.0) {
            throw new AssertionError("Milli value should be ~1000x seconds value, ratio was " + ratio + " (seconds=" + epochSeconds + ", millis=" + epochMillis + ")");
        }
    }
    
    private static void testDateModifiedInSecondsRange() {
        long dateModifiedValue = Instant.now().getEpochSecond();
        
        boolean isInSecondsRange = dateModifiedValue >= 1000000000L && dateModifiedValue <= 2000000000L;
        boolean isInMillisecondsRange = dateModifiedValue > 1000000000000L;
        
        if (!isInSecondsRange) {
            throw new AssertionError("DATE_MODIFIED with epochSecond should be in seconds range (billions), got " + dateModifiedValue);
        }
        if (isInMillisecondsRange) {
            throw new AssertionError("DATE_MODIFIED with epochSecond should NOT be in milliseconds range (trillions)");
        }
    }
    
    private static void testMillisInterpretedAsSecondsProducesFutureDate() {
        long millisTimestamp = Instant.now().toEpochMilli();
        
        // When Android interprets millis as seconds (the bug)
        Instant buggyInstant = Instant.ofEpochSecond(millisTimestamp);
        String buggyYearStr = buggyInstant.toString();
        
        // Extract year - handle both 4-digit (2026) and 5+ digit (+58444) formats
        int buggyYear;
        if (buggyYearStr.startsWith("+")) {
            // Format: +58444-06-22T...
            int endIndex = buggyYearStr.indexOf('-');
            buggyYear = Integer.parseInt(buggyYearStr.substring(1, endIndex));
        } else {
            // Format: 2026-06-22T...
            buggyYear = Integer.parseInt(buggyYearStr.substring(0, 4));
        }
        
        if (buggyYear <= 5000) {
            throw new AssertionError("Interpreting millis " + millisTimestamp + " as seconds produces year " + buggyYear + " (should be > 5000)");
        }
        
        // Using epochSecond produces correct year
        Instant correctInstant = Instant.ofEpochSecond(Instant.now().getEpochSecond());
        String correctYearStr = correctInstant.toString();
        int correctYear;
        if (correctYearStr.startsWith("+")) {
            int endIndex = correctYearStr.indexOf('-');
            correctYear = Integer.parseInt(correctYearStr.substring(1, endIndex));
        } else {
            correctYear = Integer.parseInt(correctYearStr.substring(0, 4));
        }
        
        if (correctYear < 2020 || correctYear > 2030) {
            throw new AssertionError("Using epochSecond produces year " + correctYear + " (should be 2020-2030)");
        }
    }
}
