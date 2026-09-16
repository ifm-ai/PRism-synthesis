"""
Hidden tests to verify the cancerit-allelecount recipe fix is correctly applied.
These tests check the key changes from fix.patch:
1. meta.yaml has linux-aarch64 in additional-platforms
2. meta.yaml has build number 7
3. meta.yaml has run_exports
4. meta.yaml has correct license fields (GPL-3.0-only, license_file, license_family)
5. build.sh uses set -xeu (not set -eu)
6. build.sh uses parallel make (-j ${CPU_COUNT})

Note: We use text-based verification instead of YAML parsing because conda
recipes use Jinja2 templating which standard YAML parsers cannot handle.
"""

import os
import re
import pytest

RECIPE_DIR = os.path.join(os.getcwd(), "recipes/cancerit-allelecount")
META_YAML_PATH = os.path.join(RECIPE_DIR, "meta.yaml")
BUILD_SH_PATH = os.path.join(RECIPE_DIR, "build.sh")


def read_file(path):
    """Read file content."""
    with open(path, 'r') as f:
        return f.read()


class TestMetaYaml:
    """Tests for meta.yaml fix verification."""

    @pytest.fixture
    def meta_content(self):
        """Read meta.yaml content."""
        return read_file(META_YAML_PATH)

    def test_additional_platforms_linux_aarch64(self, meta_content):
        """Verify linux-aarch64 is in additional-platforms."""
        # Check for the additional-platforms section with linux-aarch64
        assert 'additional-platforms' in meta_content, \
            "Missing 'additional-platforms' in meta.yaml"
        assert 'linux-aarch64' in meta_content, \
            "linux-aarch64 not found in meta.yaml additional-platforms"

        # More precise check: ensure it's under extra section
        pattern = r'extra:\s*\n\s*additional-platforms:\s*\n\s*-\s*linux-aarch64'
        assert re.search(pattern, meta_content), \
            "linux-aarch64 should be under extra.additional-platforms"

    def test_build_number_is_7(self, meta_content):
        """Verify build number is 7 (fixed version)."""
        # Look for build number in the build section
        # The fix changes number from 6 to 7
        pattern = r'build:\s*\n\s*number:\s*7'
        assert re.search(pattern, meta_content), \
            "Expected build number 7, not found in meta.yaml"

    def test_run_exports_present(self, meta_content):
        """Verify run_exports is present in build section."""
        assert 'run_exports' in meta_content, \
            "Missing 'run_exports' in build section"
        # Check for pin_subpackage reference
        assert 'pin_subpackage' in meta_content, \
            "run_exports should use pin_subpackage"
        assert 'cancerit-allelecount' in meta_content, \
            "run_exports should reference cancerit-allelecount"

    def test_license_is_gpl3_only(self, meta_content):
        """Verify license is GPL-3.0-only (not GPLv3)."""
        # The fix changes 'license: GPLv3' to 'license: GPL-3.0-only'
        assert 'license: GPL-3.0-only' in meta_content, \
            "Expected license 'GPL-3.0-only', not found in meta.yaml"
        # Ensure old format is not present
        lines = meta_content.split('\n')
        for line in lines:
            if line.strip().startswith('license:') and 'family' not in line.lower():
                assert 'GPL-3.0-only' in line, \
                    f"Found incorrect license format: {line}"

    def test_license_file_present(self, meta_content):
        """Verify license_file is specified."""
        assert 'license_file: LICENCE' in meta_content, \
            "Missing 'license_file: LICENCE' in meta.yaml"

    def test_license_family_present(self, meta_content):
        """Verify license_family is specified."""
        assert 'license_family: GPL3' in meta_content, \
            "Missing 'license_family: GPL3' in meta.yaml"


class TestBuildSh:
    """Tests for build.sh fix verification."""

    @pytest.fixture
    def build_sh_content(self):
        """Read build.sh content."""
        return read_file(BUILD_SH_PATH)

    def test_set_xeu_not_set_eu(self, build_sh_content):
        """Verify build.sh uses 'set -xeu' (with -x for debugging)."""
        # The fix changes 'set -eu' to 'set -xeu'
        lines = build_sh_content.split('\n')
        set_line = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('set -'):
                set_line = stripped
                break

        assert set_line is not None, "Could not find 'set -' line in build.sh"
        assert 'xeu' in set_line or '-x' in set_line, \
            f"Expected 'set -xeu' but found '{set_line}'. The fix adds -x for verbose debugging."
        # Ensure it's NOT just 'set -eu' without -x
        assert set_line != 'set -eu', \
            f"build.sh still has 'set -eu' without -x flag. Found: {set_line}"

    def test_parallel_make_with_cpu_count(self, build_sh_content):
        """Verify build.sh uses parallel make with -j ${CPU_COUNT}."""
        # The fix adds -j ${CPU_COUNT} to the make command
        # Look for the make command with parallel flag
        assert '-j ${CPU_COUNT}' in build_sh_content or '-j${CPU_COUNT}' in build_sh_content, \
            "build.sh should use parallel make with '-j ${CPU_COUNT}'"

        # Also verify the make command exists with the OPTINC flag
        make_pattern = r'make\s+-j\s+\$\{CPU_COUNT\}'
        assert re.search(make_pattern, build_sh_content), \
            "Could not find 'make -j ${CPU_COUNT}' pattern in build.sh"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
