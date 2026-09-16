// Test that verifies NumberListAlignment enum exists and works correctly
// This test will fail to compile on buggy code (enum missing) and pass on fixed code

using Microsoft.VisualStudio.TestTools.UnitTesting;
using FracturedJson;

namespace Tests;

[TestClass]
public class NumberListAlignmentTest
{
    [TestMethod]
    public void NumberListAlignment_EnumExists_AndHasExpectedValues()
    {
        // Test that NumberListAlignment enum exists and has the expected values
        var left = NumberListAlignment.Left;
        var right = NumberListAlignment.Right;
        var decimalAlign = NumberListAlignment.Decimal;
        var normalize = NumberListAlignment.Normalize;

        Assert.AreEqual(NumberListAlignment.Left, left);
        Assert.AreEqual(NumberListAlignment.Right, right);
        Assert.AreEqual(NumberListAlignment.Decimal, decimalAlign);
        Assert.AreEqual(NumberListAlignment.Normalize, normalize);
    }

    [TestMethod]
    public void FracturedJsonOptions_HasNumberListAlignmentProperty()
    {
        // Test that FracturedJsonOptions has NumberListAlignment property
        var options = new FracturedJsonOptions();

        // Default should be Normalize according to fix.patch
        Assert.AreEqual(NumberListAlignment.Normalize, options.NumberListAlignment);

        // Should be able to set all values
        options.NumberListAlignment = NumberListAlignment.Left;
        Assert.AreEqual(NumberListAlignment.Left, options.NumberListAlignment);

        options.NumberListAlignment = NumberListAlignment.Right;
        Assert.AreEqual(NumberListAlignment.Right, options.NumberListAlignment);

        options.NumberListAlignment = NumberListAlignment.Decimal;
        Assert.AreEqual(NumberListAlignment.Decimal, options.NumberListAlignment);

        options.NumberListAlignment = NumberListAlignment.Normalize;
        Assert.AreEqual(NumberListAlignment.Normalize, options.NumberListAlignment);
    }

    [TestMethod]
    public void NumberListAlignment_WithFormatter_ProducesExpectedOutput()
    {
        // Test that NumberListAlignment.Left produces left-aligned output
        const string input = "[1, 2.1, 3, -99]";
        // With Left alignment, numbers should be left-aligned without justification
        const string expectedOutput = "[\n    1  , 2.1, 3  , -99\n]";

        var opts = new FracturedJsonOptions()
        {
            MaxInlineComplexity = -1,
            NumberListAlignment = NumberListAlignment.Left,
            JsonEolStyle = EolStyle.Lf
        };

        var formatter = new Formatter() { Options = opts };
        var output = formatter.Reformat(input, 0);

        Assert.AreEqual(expectedOutput, output.TrimEnd());
    }
}
