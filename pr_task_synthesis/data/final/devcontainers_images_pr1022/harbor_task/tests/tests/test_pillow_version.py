"""
Hidden test to verify Pillow version is 10.3.0 (security fix).

This test verifies that the Pillow library has been updated to version 10.3.0
to address security vulnerability GHSA-44wm-f244-xhp3.

The test will:
- PASS when Pillow version is 10.3.0 (fixed state)
- FAIL when Pillow version is 10.2.0 (buggy state)
"""

import pytest
from PIL import Image


class TestPillowVersion:
    """Test suite for verifying Pillow security fix version."""

    def test_pillow_importable(self):
        """Verify that PIL/Pillow can be imported successfully."""
        # If we got here, import worked
        assert Image is not None

    def test_pillow_has_version_attribute(self):
        """Verify that PIL.Image has a __version__ attribute."""
        assert hasattr(Image, '__version__'), "PIL.Image should have __version__ attribute"

    def test_pillow_version_is_10_3_0(self):
        """
        Verify that Pillow version is exactly 10.3.0 (security fix).

        This test ensures the container was built with the patched version
        that addresses GHSA-44wm-f244-xhp3.

        Expected behavior:
        - Version 10.3.0: PASS (fix applied)
        - Version 10.2.0: FAIL (vulnerable version)
        """
        expected_version = "10.3.0"
        actual_version = Image.__version__

        assert actual_version == expected_version, (
            f"Pillow version mismatch: expected {expected_version}, "
            f"got {actual_version}. "
            f"Security fix GHSA-44wm-f244-xhp3 requires Pillow >= 10.3.0"
        )

    def test_pillow_version_at_least_10_3_0(self):
        """
        Verify that Pillow version is at least 10.3.0.

        This is a secondary check using version tuple comparison
        to ensure the fix version or newer is installed.
        """
        def parse_version(version_str):
            """Parse version string into tuple of integers."""
            return tuple(int(x) for x in version_str.split('.')[:3])

        minimum_version = (10, 3, 0)
        actual_version = parse_version(Image.__version__)

        assert actual_version >= minimum_version, (
            f"Pillow version {Image.__version__} is below minimum required "
            f"version 10.3.0. Security vulnerability GHSA-44wm-f244-xhp3 "
            f"requires Pillow >= 10.3.0"
        )
