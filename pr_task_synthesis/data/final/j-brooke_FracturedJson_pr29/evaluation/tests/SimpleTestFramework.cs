// Minimal test framework for offline testing
// This provides just enough to make dotnet test work

using System;

namespace SimpleTest
{
    [AttributeUsage(AttributeTargets.Method)]
    public class TestMethodAttribute : Attribute { }

    [AttributeUsage(AttributeTargets.Class)]
    public class TestClassAttribute : Attribute { }

    public class TestRunner
    {
        public static int RunTests(Type testType)
        {
            int passed = 0;
            int failed = 0;

            var methods = testType.GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
            foreach (var method in methods)
            {
                if (method.GetCustomAttributes(typeof(TestMethodAttribute), false).Length > 0)
                {
                    try
                    {
                        var instance = Activator.CreateInstance(testType);
                        method.Invoke(instance, null);
                        Console.WriteLine($"  PASS: {method.Name}");
                        passed++;
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"  FAIL: {method.Name} - {ex.InnerException?.Message ?? ex.Message}");
                        failed++;
                    }
                }
            }

            Console.WriteLine($"\nResults: {passed} passed, {failed} failed");
            return failed > 0 ? 1 : 0;
        }
    }
}
