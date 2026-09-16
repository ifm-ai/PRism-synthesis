#!/usr/bin/env python3
"""
Verification test for the Parquet Arrow benchmark fix.

This test verifies that the BytesForItems template function and its specializations
are correctly implemented in the benchmark source file.

The fix introduces:
1. A BytesForItems template function for calculating correct byte counts
2. Specialization for BooleanType using bit_util::BytesForBits (bit-packing)
3. Specialization for Float16LogicalType using 2 bytes per item
4. Changed SetBytesProcessed to use separate items_processed and bytes_processed
"""

import re
import sys
from pathlib import Path


def check_bytes_for_items_template(content: str) -> tuple[bool, str]:
    """Check if the BytesForItems template function exists."""
    # Look for the template declaration
    pattern = r'template\s*<\s*typename\s+ParquetType\s*>\s*\n?\s*int64_t\s+BytesForItems\s*\(\s*int64_t\s+num_items\s*\)'
    if re.search(pattern, content):
        return True, "BytesForItems template function found"
    return False, "BytesForItems template function NOT found"


def check_boolean_specialization(content: str) -> tuple[bool, str]:
    """Check if BooleanType specialization uses bit-packing."""
    # Look for the BooleanType specialization with bit_util::BytesForBits
    pattern = r'template\s*<>\s*\n?\s*int64_t\s+BytesForItems\s*<\s*BooleanType\s*>\s*\(\s*int64_t\s+num_items\s*\)\s*\{[^}]*::arrow::bit_util::BytesForBits\s*\(\s*num_items\s*\)'
    if re.search(pattern, content, re.DOTALL):
        return True, "BooleanType specialization uses bit-packing (bit_util::BytesForBits)"
    return False, "BooleanType specialization with bit-packing NOT found"


def check_float16_specialization(content: str) -> tuple[bool, str]:
    """Check if Float16LogicalType specialization uses 2 bytes."""
    # Look for the Float16LogicalType specialization with sizeof(uint16_t) or * 2
    pattern = r'template\s*<>\s*\n?\s*int64_t\s+BytesForItems\s*<\s*Float16LogicalType\s*>\s*\(\s*int64_t\s+num_items\s*\)\s*\{[^}]*num_items\s*\*\s*(sizeof\s*\(\s*uint16_t\s*\)\s*|2\s*)'
    if re.search(pattern, content, re.DOTALL):
        return True, "Float16LogicalType specialization uses 2 bytes per item"
    return False, "Float16LogicalType specialization NOT found"


def check_set_bytes_processed_signature(content: str) -> tuple[bool, str]:
    """Check if SetBytesProcessed has single template parameter (fixed version)."""
    # The fixed version has: template <typename ParquetType>
    # The buggy version has: template <bool nullable, typename ParquetType>

    # Check for the fixed signature
    fixed_pattern = r'template\s*<\s*typename\s+ParquetType\s*>\s*\n?\s*void\s+SetBytesProcessed\s*\(\s*::benchmark::State\s*&\s*state'
    if re.search(fixed_pattern, content):
        return True, "SetBytesProcessed has fixed single template parameter"

    # Check for the buggy signature (should not be present in fixed version)
    buggy_pattern = r'template\s*<\s*bool\s+nullable\s*,\s*typename\s+ParquetType\s*>\s*\n?\s*void\s+SetBytesProcessed'
    if re.search(buggy_pattern, content):
        return False, "SetBytesProcessed still has buggy two template parameters"

    return False, "SetBytesProcessed signature not found"


def check_items_processed_separate(content: str) -> tuple[bool, str]:
    """Check that items_processed and bytes_processed are handled separately."""
    # Look for SetItemsProcessed being called with items_processed (not bytes)
    # The fix changes: state.SetItemsProcessed(bytes_processed) -> state.SetItemsProcessed(items_processed)

    # Find the SetBytesProcessed function body
    pattern = r'void\s+SetBytesProcessed[^{]*\{([^}]+)\}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        func_body = match.group(1)
        # Check that SetItemsProcessed is called with items_processed
        if 'SetItemsProcessed(items_processed)' in func_body or 'SetItemsProcessed( items_processed )' in func_body:
            return True, "SetItemsProcessed correctly uses items_processed"
        if 'SetItemsProcessed(bytes_processed)' in func_body:
            return False, "SetItemsProcessed incorrectly uses bytes_processed (buggy)"

    return False, "Could not verify SetItemsProcessed usage"


def check_bytesforitems_usage_in_setbytesprocessed(content: str) -> tuple[bool, str]:
    """Check that SetBytesProcessed uses BytesForItems."""
    # Look for BytesForItems<ParquetType> being called in SetBytesProcessed
    pattern = r'void\s+SetBytesProcessed[^{]*\{([^}]+)\}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        func_body = match.group(1)
        if 'BytesForItems<ParquetType>' in func_body:
            return True, "SetBytesProcessed uses BytesForItems<ParquetType>"

    return False, "SetBytesProcessed does not use BytesForItems"


def check_type_traits_include(content: str) -> tuple[bool, str]:
    """Check that <type_traits> is included (needed for static_assert in BytesForItems)."""
    if '#include <type_traits>' in content:
        return True, "<type_traits> header is included"
    return False, "<type_traits> header NOT included"


def check_bit_util_include(content: str) -> tuple[bool, str]:
    """Check that arrow/util/bit_util.h is included (needed for BytesForBits)."""
    if '#include "arrow/util/bit_util.h"' in content:
        return True, "arrow/util/bit_util.h header is included"
    return False, "arrow/util/bit_util.h header NOT included"


def run_verification(benchmark_file: Path) -> int:
    """Run all verification checks on the benchmark file."""
    if not benchmark_file.exists():
        print(f"ERROR: Benchmark file not found: {benchmark_file}")
        return 1

    content = benchmark_file.read_text()

    tests = [
        ("Type traits include", check_type_traits_include),
        ("Bit util include", check_bit_util_include),
        ("BytesForItems template", check_bytes_for_items_template),
        ("Boolean specialization (bit-packing)", check_boolean_specialization),
        ("Float16 specialization (2 bytes)", check_float16_specialization),
        ("SetBytesProcessed signature", check_set_bytes_processed_signature),
        ("Items/bytes processed separate", check_items_processed_separate),
        ("BytesForItems usage", check_bytesforitems_usage_in_setbytesprocessed),
    ]

    all_passed = True
    results = []

    for test_name, test_func in tests:
        passed, message = test_func(content)
        status = "PASS" if passed else "FAIL"
        results.append((test_name, passed, message))
        print(f"[{status}] {test_name}: {message}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("=== All verification checks PASSED ===")
        print("The fix for correct byte calculations is properly implemented.")
        return 0
    else:
        print("=== Some verification checks FAILED ===")
        print("The benchmark file does not have the correct fix applied.")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_fix.py <path_to_benchmark_file>")
        sys.exit(1)

    benchmark_path = Path(sys.argv[1])
    exit_code = run_verification(benchmark_path)
    sys.exit(exit_code)
