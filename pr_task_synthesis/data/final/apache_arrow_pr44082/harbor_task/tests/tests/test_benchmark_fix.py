#!/usr/bin/env python3
"""
Pytest-based verification test for the Parquet Arrow benchmark fix.

This test verifies that the BytesForItems template function and its specializations
are correctly implemented in the benchmark source file.

The fix introduces:
1. A BytesForItems template function for calculating correct byte counts
2. Specialization for BooleanType using bit_util::BytesForBits (bit-packing)
3. Specialization for Float16LogicalType using 2 bytes per item
4. Changed SetBytesProcessed to use separate items_processed and bytes_processed
"""

import re
import os
from pathlib import Path
import pytest


def get_benchmark_content() -> str:
    """Get the content of the benchmark file from environment or default path."""
    benchmark_path = os.environ.get(
        "BENCHMARK_FILE",
        "/workspace/cpp/src/parquet/arrow/reader_writer_benchmark.cc"
    )
    path = Path(benchmark_path)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {path}")
    return path.read_text()


class TestBytesForItemsTemplate:
    """Test suite for BytesForItems template function verification."""

    def test_bytes_for_items_template_exists(self):
        """Check if the BytesForItems template function exists."""
        content = get_benchmark_content()
        pattern = r'template\s*<\s*typename\s+ParquetType\s*>\s*\n?\s*int64_t\s+BytesForItems\s*\(\s*int64_t\s+num_items\s*\)'
        assert re.search(pattern, content), "BytesForItems template function NOT found"

    def test_boolean_specialization_uses_bit_packing(self):
        """Check if BooleanType specialization uses bit-packing."""
        content = get_benchmark_content()
        pattern = r'template\s*<>\s*\n?\s*int64_t\s+BytesForItems\s*<\s*BooleanType\s*>\s*\(\s*int64_t\s+num_items\s*\)\s*\{[^}]*::arrow::bit_util::BytesForBits\s*\(\s*num_items\s*\)'
        assert re.search(pattern, content, re.DOTALL), \
            "BooleanType specialization with bit-packing NOT found"

    def test_float16_specialization_uses_2_bytes(self):
        """Check if Float16LogicalType specialization uses 2 bytes."""
        content = get_benchmark_content()
        pattern = r'template\s*<>\s*\n?\s*int64_t\s+BytesForItems\s*<\s*Float16LogicalType\s*>\s*\(\s*int64_t\s+num_items\s*\)\s*\{[^}]*num_items\s*\*\s*(sizeof\s*\(\s*uint16_t\s*\)\s*|2\s*)'
        assert re.search(pattern, content, re.DOTALL), \
            "Float16LogicalType specialization NOT found"


class TestSetBytesProcessed:
    """Test suite for SetBytesProcessed function verification."""

    def test_set_bytes_processed_signature_fixed(self):
        """Check if SetBytesProcessed has single template parameter (fixed version)."""
        content = get_benchmark_content()
        # The fixed version has: template <typename ParquetType>
        fixed_pattern = r'template\s*<\s*typename\s+ParquetType\s*>\s*\n?\s*void\s+SetBytesProcessed\s*\(\s*::benchmark::State\s*&\s*state'
        assert re.search(fixed_pattern, content), \
            "SetBytesProcessed does not have fixed single template parameter"

        # The buggy version should NOT be present
        buggy_pattern = r'template\s*<\s*bool\s+nullable\s*,\s*typename\s+ParquetType\s*>\s*\n?\s*void\s+SetBytesProcessed'
        assert not re.search(buggy_pattern, content), \
            "SetBytesProcessed still has buggy two template parameters"

    def test_items_processed_separate_from_bytes_processed(self):
        """Check that items_processed and bytes_processed are handled separately."""
        content = get_benchmark_content()
        pattern = r'void\s+SetBytesProcessed[^{]*\{([^}]+)\}'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "Could not find SetBytesProcessed function"

        func_body = match.group(1)
        assert 'SetItemsProcessed(items_processed)' in func_body or \
               'SetItemsProcessed( items_processed )' in func_body, \
            "SetItemsProcessed does not use items_processed correctly"

    def test_bytesforitems_used_in_setbytesprocessed(self):
        """Check that SetBytesProcessed uses BytesForItems."""
        content = get_benchmark_content()
        pattern = r'void\s+SetBytesProcessed[^{]*\{([^}]+)\}'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "Could not find SetBytesProcessed function"

        func_body = match.group(1)
        assert 'BytesForItems<ParquetType>' in func_body, \
            "SetBytesProcessed does not use BytesForItems<ParquetType>"


class TestRequiredIncludes:
    """Test suite for required header includes."""

    def test_type_traits_include(self):
        """Check that <type_traits> is included."""
        content = get_benchmark_content()
        assert '#include <type_traits>' in content, \
            "<type_traits> header NOT included"

    def test_bit_util_include(self):
        """Check that arrow/util/bit_util.h is included."""
        content = get_benchmark_content()
        assert '#include "arrow/util/bit_util.h"' in content, \
            "arrow/util/bit_util.h header NOT included"
