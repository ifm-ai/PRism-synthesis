// Compilation-based test for NumberListAlignment enum
// This test verifies that the NumberListAlignment enum exists and can be used.
// If this code compiles, the fix is present. If it fails to compile, the bug is present.

using System;

namespace FracturedJson
{
    public class TestProgram
    {
        public static int Main(string[] args)
        {
            // Test 1: Verify NumberListAlignment enum exists and has expected values
            var left = NumberListAlignment.Left;
            var right = NumberListAlignment.Right;
            var decimalAlign = NumberListAlignment.Decimal;
            var normalize = NumberListAlignment.Normalize;

            // Test 2: Verify FracturedJsonOptions has NumberListAlignment property
            var options = new FracturedJsonOptions();
            options.NumberListAlignment = NumberListAlignment.Normalize;

            Console.WriteLine("NumberListAlignment enum test PASSED");
            Console.WriteLine($"  Left = {left}");
            Console.WriteLine($"  Right = {right}");
            Console.WriteLine($"  Decimal = {decimalAlign}");
            Console.WriteLine($"  Normalize = {normalize}");
            Console.WriteLine($"  Default options.NumberListAlignment = {options.NumberListAlignment}");

            return 0;
        }
    }
}
