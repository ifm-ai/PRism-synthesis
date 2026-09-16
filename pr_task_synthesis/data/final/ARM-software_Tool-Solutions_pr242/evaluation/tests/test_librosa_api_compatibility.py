"""
Test suite for librosa API compatibility fixes in mlcommons_rnnt.patch.

This module tests that the mlcommons_rnnt.patch file contains the correct
librosa API patterns introduced by the fix.

The fix.patch modifies docker/pytorch-aarch64/patches/mlcommons_rnnt.patch to:
1. librosa.filters.mel(sample_rate, self.n_fft, ...) → librosa.filters.mel(sr=sample_rate, n_fft=self.n_fft, ...)
2. librosa.core.resample(samples, sample_rate, target_sr) → librosa.core.resample(samples, orig_sr=sample_rate, target_sr=target_sr)
3. librosa.effects.trim(samples, trim_db) → librosa.effects.trim(samples, top_db=trim_db)
4. torch.stft(..., center=True, window=...) → torch.stft(..., return_complex=True) + torch.view_as_real()
5. np.array(self.label_list) → np.array(self.label_list, dtype=object)

These tests PARSE the mlcommons_rnnt.patch file to verify the correct fixed patterns are present.
Tests FAIL if the fixed patterns are missing (buggy workspace) and PASS if present (fixed workspace).
"""

import os
import pytest


class TestPatchFileExists:
    """Test that the mlcommons_rnnt.patch file exists."""

    def test_patch_file_exists(self):
        """Test that the mlcommons_rnnt.patch file exists in the workspace."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        assert os.path.exists(patch_path), f"Patch file not found at {patch_path}"


class TestLibrosaFiltersMel:
    """Test librosa.filters.mel() fix in the patch file."""

    @pytest.fixture
    def patch_content(self):
        """Read the mlcommons_rnnt.patch file content."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        with open(patch_path, 'r') as f:
            return f.read()

    def test_fixed_mel_pattern_present(self, patch_content):
        """Test that the fixed librosa.filters.mel pattern with sr= and n_fft= is present."""
        # The fixed pattern should be present (with + prefix indicating addition)
        fixed_pattern = "+            librosa.filters.mel(sr=sample_rate, n_fft=self.n_fft"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern '{fixed_pattern}' not found in patch file - librosa.filters.mel should use keyword arguments"


class TestLibrosaCoreResample:
    """Test librosa.core.resample() fix in the patch file."""

    @pytest.fixture
    def patch_content(self):
        """Read the mlcommons_rnnt.patch file content."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        with open(patch_path, 'r') as f:
            return f.read()

    def test_fixed_resample_pattern_present(self, patch_content):
        """Test that the fixed librosa.core.resample pattern with orig_sr= and target_sr= is present."""
        fixed_pattern = "+            samples = librosa.core.resample(samples, orig_sr=sample_rate, target_sr=target_sr)"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern '{fixed_pattern}' not found in patch file - librosa.core.resample should use keyword arguments"


class TestLibrosaEffectsTrim:
    """Test librosa.effects.trim() fix in the patch file."""

    @pytest.fixture
    def patch_content(self):
        """Read the mlcommons_rnnt.patch file content."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        with open(patch_path, 'r') as f:
            return f.read()

    def test_fixed_trim_pattern_present(self, patch_content):
        """Test that the fixed librosa.effects.trim pattern with top_db= is present."""
        fixed_pattern = "+            samples, _ = librosa.effects.trim(samples, top_db=trim_db)"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern '{fixed_pattern}' not found in patch file - librosa.effects.trim should use top_db= keyword"


class TestTorchSTFT:
    """Test torch.stft() fix in the patch file."""

    @pytest.fixture
    def patch_content(self):
        """Read the mlcommons_rnnt.patch file content."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        with open(patch_path, 'r') as f:
            return f.read()

    def test_fixed_stft_return_complex_present(self, patch_content):
        """Test that torch.stft with return_complex=True is present."""
        fixed_pattern = "+                       center=True, window=self.window.to(dtype=torch.float), return_complex = True)"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern with return_complex=True not found in patch file - torch.stft should use return_complex=True"

    def test_fixed_view_as_real_present(self, patch_content):
        """Test that torch.view_as_real() is present after stft."""
        fixed_pattern = "+        x = torch.view_as_real(x)"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern 'torch.view_as_real(x)' not found in patch file - should convert complex STFT output to real"


class TestNumpyArrayDtypeObject:
    """Test numpy array dtype=object fix in the patch file."""

    @pytest.fixture
    def patch_content(self):
        """Read the mlcommons_rnnt.patch file content."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        with open(patch_path, 'r') as f:
            return f.read()

    def test_fixed_numpy_dtype_present(self, patch_content):
        """Test that np.array with dtype=object is present."""
        fixed_pattern = "+        self.label_list = np.array(self.label_list, dtype=object)"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern with dtype=object not found in patch file - np.array should use dtype=object"


class TestContextManagerPattern:
    """Test the torch.no_grad() context manager fix in the patch file."""

    @pytest.fixture
    def patch_content(self):
        """Read the mlcommons_rnnt.patch file content."""
        patch_path = "/workspace/docker/pytorch-aarch64/patches/mlcommons_rnnt.patch"
        with open(patch_path, 'r') as f:
            return f.read()

    def test_fixed_context_manager_present(self, patch_content):
        """Test that 'with torch.no_grad():' context manager pattern is present."""
        fixed_pattern = "+        with torch.no_grad():"
        assert fixed_pattern in patch_content, \
            f"Fixed pattern 'with torch.no_grad():' not found in patch file - should use context manager instead of decorator"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
