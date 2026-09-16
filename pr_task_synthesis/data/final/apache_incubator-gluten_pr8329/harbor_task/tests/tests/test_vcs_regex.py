#!/usr/bin/env python3
"""
Test for Apache Gluten .idea/vcs.xml regex pattern.

This test verifies that the issueRegexp pattern correctly captures
issue numbers from both "#123" and "GLUTEN-123" formats into a
single capture group that can be used by the link template.

The fix changes the regex from:
  #(\d+)|GLUTEN-(\d+)   (two capture groups)
to:
  (?:#|GLUTEN-)(\d+)    (single capture group)

The link template uses $1, so both formats must capture the number
in the first (and only) capture group.
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_issue_regexp_from_vcs_xml(vcs_xml_path: str) -> str:
    """Extract the issueRegexp value from .idea/vcs.xml."""
    tree = ET.parse(vcs_xml_path)
    root = tree.getroot()

    # Find the option element with issueRegexp
    for option in root.findall(".//option[@name='issueRegexp']"):
        value = option.get("value")
        if value:
            return value

    raise ValueError("Could not find issueRegexp in vcs.xml")


def test_regex_captures_hash_format():
    """Test that #123 format captures the number correctly."""
    # The fixed regex pattern
    pattern = r"(?:#|GLUTEN-)(\d+)"
    regex = re.compile(pattern)

    test_string = "See #123 for details"
    match = regex.search(test_string)

    assert match is not None, "Regex should match #123 format"
    assert match.group(1) == "123", f"Expected '123', got '{match.group(1)}'"
    print("PASS: #123 format captures '123' in group 1")


def test_regex_captures_gluten_format():
    """Test that GLUTEN-123 format captures the number correctly."""
    pattern = r"(?:#|GLUTEN-)(\d+)"
    regex = re.compile(pattern)

    test_string = "See GLUTEN-456 for details"
    match = regex.search(test_string)

    assert match is not None, "Regex should match GLUTEN-456 format"
    assert match.group(1) == "456", f"Expected '456', got '{match.group(1)}'"
    print("PASS: GLUTEN-456 format captures '456' in group 1")


def test_buggy_regex_gluten_format():
    """
    Demonstrate the bug: with the old regex, GLUTEN-123 captures in group 2,
    not group 1. The link template uses $1, so it would fail.
    """
    # The buggy regex pattern
    buggy_pattern = r"#(\d+)|GLUTEN-(\d+)"
    regex = re.compile(buggy_pattern)

    test_string = "See GLUTEN-789 for details"
    match = regex.search(test_string)

    assert match is not None, "Regex should match GLUTEN-789 format"
    # In the buggy version, group 1 is None, group 2 has the number
    assert match.group(1) is None, f"Buggy regex: group 1 should be None for GLUTEN- format, got '{match.group(1)}'"
    assert match.group(2) == "789", f"Buggy regex: group 2 should be '789', got '{match.group(2)}'"
    print("PASS: Buggy regex demonstrates the issue - GLUTEN-789 has number in group 2, not group 1")


def test_vcs_xml_has_fixed_regex():
    """
    Test that the actual vcs.xml file has the fixed regex pattern.
    This is the main verification test.
    """
    # Use current working directory to support both /workspace and /workspace_fixed
    vcs_xml_path = Path.cwd() / ".idea" / "vcs.xml"

    if not vcs_xml_path.exists():
        print(f"FAIL: vcs.xml not found at {vcs_xml_path}")
        sys.exit(1)

    try:
        issue_regexp = extract_issue_regexp_from_vcs_xml(str(vcs_xml_path))
    except Exception as e:
        print(f"FAIL: Could not parse vcs.xml: {e}")
        sys.exit(1)

    # The fixed pattern should be: (?:#|GLUTEN-)(\d+)
    fixed_pattern = r"(?:#|GLUTEN-)(\d+)"
    # The buggy pattern was: #(\d+)|GLUTEN-(\d+)
    buggy_pattern = r"#(\d+)|GLUTEN-(\d+)"

    if issue_regexp == fixed_pattern:
        print(f"PASS: vcs.xml has the fixed regex pattern: {issue_regexp}")
    elif issue_regexp == buggy_pattern:
        print(f"FAIL: vcs.xml still has the buggy regex pattern: {issue_regexp}")
        print(f"      Expected: {fixed_pattern}")
        assert False, f"vcs.xml has buggy regex pattern: {issue_regexp}"
    else:
        print(f"FAIL: vcs.xml has unexpected regex pattern: {issue_regexp}")
        print(f"      Expected: {fixed_pattern}")
        assert False, f"vcs.xml has unexpected regex pattern: {issue_regexp}"


def test_fixed_regex_both_formats_single_group():
    """
    Test that the fixed regex correctly handles both formats with a single group.
    This simulates what the IDE link template expects.
    """
    pattern = r"(?:#|GLUTEN-)(\d+)"
    regex = re.compile(pattern)

    test_cases = [
        ("#123", "123"),
        ("#999", "999"),
        ("GLUTEN-1", "1"),
        ("GLUTEN-12345", "12345"),
        ("See #42 and GLUTEN-99", "42"),  # First match
    ]

    for test_input, expected_group1 in test_cases:
        match = regex.search(test_input)
        assert match is not None, f"Regex should match '{test_input}'"
        assert match.group(1) == expected_group1, \
            f"For '{test_input}': expected group(1)='{expected_group1}', got '{match.group(1)}'"
        # Verify there's only one capture group
        assert len(match.groups()) == 1, \
            f"Expected 1 capture group, got {len(match.groups())}"
        print(f"PASS: '{test_input}' -> group(1)='{match.group(1)}'")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Apache Gluten .idea/vcs.xml Regex Verification Tests")
    print("=" * 60)

    all_passed = True

    # Run unit tests for the regex behavior
    print("\n--- Testing fixed regex behavior ---")
    try:
        test_regex_captures_hash_format()
        test_regex_captures_gluten_format()
        test_fixed_regex_both_formats_single_group()
    except AssertionError as e:
        print(f"FAIL: {e}")
        all_passed = False

    print("\n--- Demonstrating the bug in old regex ---")
    try:
        test_buggy_regex_gluten_format()
    except AssertionError as e:
        print(f"FAIL: {e}")
        all_passed = False

    print("\n--- Testing actual vcs.xml file ---")
    try:
        test_vcs_xml_has_fixed_regex()
        print("vcs.xml test passed")
    except AssertionError as e:
        print(f"FAIL: {e}")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
