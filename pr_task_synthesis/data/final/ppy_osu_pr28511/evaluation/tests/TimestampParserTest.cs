// Copyright (c) ppy Pty Ltd <contact@ppy.sh>. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Game.Rulesets.Edit;

namespace osu.Game.Tests.Editing
{
    /// <summary>
    /// Standalone test for EditorTimestampParser.TryParse method.
    /// This test verifies the timestamp parsing functionality added by the fix.
    /// </summary>
    public class TimestampParserTest
    {
        public static int Main()
        {
            int failures = 0;
            
            // Test case 1: Invalid format
            TestCase(":", false, null, null, ref failures);
            
            // Test case 2: Bare milliseconds - valid (this is the KEY fix being tested)
            TestCase("1", true, 1, null, ref failures);
            TestCase("99", true, 99, null, ref failures);
            TestCase("320000", true, 320000, null, ref failures);
            
            // Test case 3: mm:ss format - valid (also part of the fix)
            TestCase("1:2", true, 62000, null, ref failures);
            TestCase("1:02", true, 62000, null, ref failures);
            
            // Test case 4: Invalid seconds (>= 60) - should fail
            TestCase("1:92", false, null, null, ref failures);
            TestCase("1:002", false, null, null, ref failures);
            
            // Test case 5: mm:ss:ms format - valid
            TestCase("1:02:3", true, 62003, null, ref failures);
            TestCase("1:02:300", true, 62300, null, ref failures);
            
            // Test case 6: Invalid milliseconds (>= 1000) - should fail
            TestCase("1:02:3000", false, null, null, ref failures);
            
            // Test case 7: Empty selection clause - invalid
            TestCase("1:02:300 ()", false, null, null, ref failures);
            
            // Test case 8: Valid selection clause
            TestCase("1:02:300 (1,2,3)", true, 62300, "1,2,3", ref failures);
            
            Console.WriteLine($"\nTotal failures: {failures}");
            return failures > 0 ? 1 : 0;
        }
        
        private static void TestCase(string input, bool expectedValid, int? expectedMs, string expectedSelection, ref int failures)
        {
            bool valid = EditorTimestampParser.TryParse(input, out var time, out var selection);
            
            int actualMs = time.HasValue ? (int)time.Value.TotalMilliseconds : -1;
            string status = "PASS";
            string details = "";
            
            if (valid != expectedValid)
            {
                status = "FAIL";
                details += $" Valid mismatch: expected {expectedValid}, got {valid}.";
            }
            else if (expectedValid && expectedMs.HasValue && actualMs != expectedMs.Value)
            {
                status = "FAIL";
                details += $" Time mismatch: expected {expectedMs.Value}ms, got {actualMs}ms.";
            }
            else if (expectedValid && expectedSelection != null && selection != expectedSelection)
            {
                status = "FAIL";
                details += $" Selection mismatch: expected '{expectedSelection}', got '{selection ?? "null"}'.";
            }
            
            if (status == "FAIL")
            {
                failures++;
                Console.WriteLine($"FAIL: '{input}' -{details}");
            }
            else
            {
                Console.WriteLine($"PASS: '{input}'");
            }
        }
    }
}
