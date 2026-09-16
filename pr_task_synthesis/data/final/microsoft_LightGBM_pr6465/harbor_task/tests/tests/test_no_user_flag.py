"""
Tests to verify that CI scripts do not use --user flag in pip install commands.
This ensures no cross-job contamination in CI pipelines.
"""
import re
import pytest
from pathlib import Path


def get_ci_script_content(script_path: str) -> str:
    """Read the content of a CI script."""
    # Use current working directory as the workspace root
    ci_path = Path.cwd() / script_path
    if not ci_path.exists():
        pytest.fail(f"CI script not found: {ci_path}")
    return ci_path.read_text()


def find_pip_install_lines(content: str) -> list[str]:
    """Find all lines that contain pip install commands."""
    lines = content.split("\n")
    pip_install_lines = []
    for line in lines:
        # Match pip install commands (including escaped newlines with backslash)
        if re.search(r"pip\s+install", line):
            pip_install_lines.append(line)
    return pip_install_lines


class TestNoUserFlagInCiScripts:
    """Test that CI scripts don't use --user flag in pip install commands."""

    def test_test_sh_no_user_flag(self):
        """Verify .ci/test.sh doesn't have --user in pip install commands."""
        content = get_ci_script_content(".ci/test.sh")
        pip_lines = find_pip_install_lines(content)

        # Check each pip install line for --user flag
        for line in pip_lines:
            # Remove comments and check for --user
            code_part = line.split("#")[0] if "#" in line else line
            assert "--user" not in code_part, (
                f"Found --user flag in pip install command: {line.strip()}"
            )

    def test_test_windows_ps1_no_user_flag(self):
        """Verify .ci/test_windows.ps1 doesn't have --user in pip install commands."""
        content = get_ci_script_content(".ci/test_windows.ps1")
        pip_lines = find_pip_install_lines(content)

        # Check each pip install line for --user flag
        for line in pip_lines:
            # Remove comments and check for --user
            code_part = line.split("#")[0] if "#" in line else line
            assert "--user" not in code_part, (
                f"Found --user flag in pip install command: {line.strip()}"
            )

    def test_test_sh_has_pip_install_commands(self):
        """Verify .ci/test.sh actually has pip install commands (sanity check)."""
        content = get_ci_script_content(".ci/test.sh")
        pip_lines = find_pip_install_lines(content)
        assert len(pip_lines) > 0, "Expected to find pip install commands in .ci/test.sh"

    def test_test_windows_ps1_has_pip_install_commands(self):
        """Verify .ci/test_windows.ps1 actually has pip install commands (sanity check)."""
        content = get_ci_script_content(".ci/test_windows.ps1")
        pip_lines = find_pip_install_lines(content)
        assert len(pip_lines) > 0, "Expected to find pip install commands in .ci/test_windows.ps1"
