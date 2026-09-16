// Simple test runner that verifies NumberListAlignment enum exists
// This is a console app that acts as a test runner
// Returns 0 if tests pass (enum exists), 1 if tests fail (enum missing)

using System;

namespace FracturedJson
{
    public class TestRunner
    {
        public static int Main(string[] args)
        {
            Console.WriteLine("Running NumberListAlignment tests...");

            try
            {
                // Test 1: Verify NumberListAlignment enum exists and has expected values
                var left = NumberListAlignment.Left;
                var right = NumberListAlignment.Right;
                var decimalAlign = NumberListAlignment.Decimal;
                var normalize = NumberListAlignment.Normalize;

                Console.WriteLine($"  Test 1 PASSED: Enum values exist - Left={left}, Right={right}, Decimal={decimalAlign}, Normalize={normalize}");

                // Test 2: Verify FracturedJsonOptions has NumberListAlignment property
                var options = new FracturedJsonOptions();
                var defaultAlignment = options.NumberListAlignment;

                Console.WriteLine($"  Test 2 PASSED: FracturedJsonOptions.NumberListAlignment exists, default={defaultAlignment}");

                // Test 3: Verify we can set all values
                options.NumberListAlignment = NumberListAlignment.Left;
                if (options.NumberListAlignment != NumberListAlignment.Left)
                {
                    Console.WriteLine("  Test 3 FAILED: Could not set NumberListAlignment.Left");
                    return 1;
                }

                options.NumberListAlignment = NumberListAlignment.Right;
                if (options.NumberListAlignment != NumberListAlignment.Right)
                {
                    Console.WriteLine("  Test 4 FAILED: Could not set NumberListAlignment.Right");
                    return 1;
                }

                options.NumberListAlignment = NumberListAlignment.Decimal;
                if (options.NumberListAlignment != NumberListAlignment.Decimal)
                {
                    Console.WriteLine("  Test 5 FAILED: Could not set NumberListAlignment.Decimal");
                    return 1;
                }

                options.NumberListAlignment = NumberListAlignment.Normalize;
                if (options.NumberListAlignment != NumberListAlignment.Normalize)
                {
                    Console.WriteLine("  Test 6 FAILED: Could not set NumberListAlignment.Normalize");
                    return 1;
                }

                Console.WriteLine("  Test 6 PASSED: All NumberListAlignment values can be set");

                Console.WriteLine("\nAll tests PASSED!");
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Test FAILED with exception: {ex.Message}");
                return 1;
            }
        }
    }
}
