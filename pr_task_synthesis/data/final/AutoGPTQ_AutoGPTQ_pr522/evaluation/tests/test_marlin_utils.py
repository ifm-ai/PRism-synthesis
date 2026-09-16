"""
Tests for the marlin_utils module interface.

These tests verify that the marlin_utils module exists and exposes the expected
public API, without requiring GPU hardware to run. The tests check:
1. The module can be imported
2. Key functions are present with correct signatures
3. The _get_cached_marlin_save_name function returns paths containing 'assets'
4. The _validate_marlin_compatibility function works correctly
5. The _validate_marlin_device_support function exists
6. The prepare_model_for_marlin_load function exists

These are structural/interface tests that verify the fix was applied correctly.
The buggy code will fail because marlin_utils.py does not exist.
"""

import unittest
import os
import tempfile
from unittest.mock import MagicMock, patch


class TestMarlinUtilsInterface(unittest.TestCase):
    """Test that marlin_utils module exists and has correct interface."""

    def test_marlin_utils_module_exists(self):
        """Test that the marlin_utils module can be imported."""
        from auto_gptq.utils.marlin_utils import (
            prepare_model_for_marlin_load,
            _validate_marlin_compatibility,
            _validate_marlin_device_support,
            _get_cached_marlin_save_name,
            convert_to_marlin,
        )

    def test_get_cached_marlin_save_name_returns_assets_path(self):
        """Test _get_cached_marlin_save_name returns path containing 'assets' for remote models."""
        from auto_gptq.utils.marlin_utils import _get_cached_marlin_save_name

        # Test with a remote model ID (should contain 'assets')
        model_id = "test-org/test-model"
        path = _get_cached_marlin_save_name(model_id)

        # The path should contain 'assets' for remote models
        self.assertIn("assets", path)
        self.assertTrue(path.endswith("autogptq_model.safetensors"))

    def test_get_cached_marlin_save_name_local_path(self):
        """Test _get_cached_marlin_save_name returns local path for local directories."""
        from auto_gptq.utils.marlin_utils import _get_cached_marlin_save_name

        # Test with a local path
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _get_cached_marlin_save_name(tmpdir)
            expected = os.path.join(tmpdir, "autogptq_model.safetensors")
            self.assertEqual(path, expected)

    def test_validate_marlin_compatibility_valid_config(self):
        """Test _validate_marlin_compatibility returns None for valid config."""
        from auto_gptq.utils.marlin_utils import _validate_marlin_compatibility

        # Create a valid quantization config
        config = MagicMock()
        config.bits = 4
        config.group_size = 128
        config.sym = True
        config.desc_act = False

        result = _validate_marlin_compatibility(config)
        self.assertIsNone(result)

    def test_validate_marlin_compatibility_invalid_bits(self):
        """Test _validate_marlin_compatibility rejects invalid bits."""
        from auto_gptq.utils.marlin_utils import _validate_marlin_compatibility

        config = MagicMock()
        config.bits = 8  # Invalid - must be 4
        config.group_size = 128
        config.sym = True
        config.desc_act = False

        result = _validate_marlin_compatibility(config)
        self.assertIsNotNone(result)
        self.assertIn("bitwidth", result)

    def test_validate_marlin_compatibility_invalid_group_size(self):
        """Test _validate_marlin_compatibility rejects invalid group_size."""
        from auto_gptq.utils.marlin_utils import _validate_marlin_compatibility

        config = MagicMock()
        config.bits = 4
        config.group_size = 64  # Invalid - must be 128 or -1
        config.sym = True
        config.desc_act = False

        result = _validate_marlin_compatibility(config)
        self.assertIsNotNone(result)
        self.assertIn("group size", result)

    def test_validate_marlin_compatibility_asymmetric(self):
        """Test _validate_marlin_compatibility rejects asymmetric quantization."""
        from auto_gptq.utils.marlin_utils import _validate_marlin_compatibility

        config = MagicMock()
        config.bits = 4
        config.group_size = 128
        config.sym = False  # Invalid - must be symmetric
        config.desc_act = False

        result = _validate_marlin_compatibility(config)
        self.assertIsNotNone(result)
        self.assertIn("asymmetric", result)

    def test_validate_marlin_compatibility_desc_act(self):
        """Test _validate_marlin_compatibility rejects desc_act."""
        from auto_gptq.utils.marlin_utils import _validate_marlin_compatibility

        config = MagicMock()
        config.bits = 4
        config.group_size = 128
        config.sym = True
        config.desc_act = True  # Invalid - act-order not supported

        result = _validate_marlin_compatibility(config)
        self.assertIsNotNone(result)
        self.assertIn("act-order" if "act-order" in result else "desc-act", result.lower())

    def test_validate_marlin_device_support_exists(self):
        """Test _validate_marlin_device_support function exists."""
        from auto_gptq.utils.marlin_utils import _validate_marlin_device_support
        import torch

        # This function requires CUDA hardware to actually run
        # On CPU-only systems, we just verify the function exists and is callable
        # If CUDA is available, verify it returns a bool
        if torch.cuda.is_available():
            result = _validate_marlin_device_support()
            self.assertIsInstance(result, bool)
        else:
            # Just verify the function is callable (exists)
            self.assertTrue(callable(_validate_marlin_device_support))

    def test_prepare_model_for_marlin_load_exists(self):
        """Test prepare_model_for_marlin_load function exists with correct signature."""
        from auto_gptq.utils.marlin_utils import prepare_model_for_marlin_load
        import inspect

        # Verify the function signature
        sig = inspect.signature(prepare_model_for_marlin_load)
        params = list(sig.parameters.keys())

        expected_params = [
            "model_name_or_path",
            "model",
            "quantize_config",
            "quant_linear_class",
            "torch_dtype",
            "current_model_save_name",
            "device_map",
        ]
        self.assertEqual(params, expected_params)

    def test_convert_to_marlin_exists(self):
        """Test convert_to_marlin function exists with correct signature."""
        from auto_gptq.utils.marlin_utils import convert_to_marlin
        import inspect

        # Verify the function signature
        sig = inspect.signature(convert_to_marlin)
        params = list(sig.parameters.keys())

        expected_params = ["model", "model_quantlinear", "quantization_config", "repack"]
        self.assertEqual(params, expected_params)


class TestBaseQuantizeConfigMarlinField(unittest.TestCase):
    """Test that BaseQuantizeConfig has is_marlin_format field."""

    def test_is_marlin_format_field_exists(self):
        """Test that BaseQuantizeConfig has is_marlin_format field."""
        from auto_gptq.modeling._base import BaseQuantizeConfig
        from dataclasses import fields

        field_names = [field.name for field in fields(BaseQuantizeConfig)]
        self.assertIn("is_marlin_format", field_names)

    def test_is_marlin_format_default_value(self):
        """Test that is_marlin_format has correct default value."""
        from auto_gptq.modeling._base import BaseQuantizeConfig

        config = BaseQuantizeConfig()
        # Default should be False
        self.assertEqual(config.is_marlin_format, False)

    def test_is_marlin_format_can_be_set(self):
        """Test that is_marlin_format can be set to True."""
        from auto_gptq.modeling._base import BaseQuantizeConfig

        config = BaseQuantizeConfig()
        config.is_marlin_format = True
        self.assertEqual(config.is_marlin_format, True)

    def test_to_dict_includes_is_marlin_format(self):
        """Test that to_dict() includes is_marlin_format field."""
        from auto_gptq.modeling._base import BaseQuantizeConfig

        config = BaseQuantizeConfig()
        config.is_marlin_format = True
        config_dict = config.to_dict()

        self.assertIn("is_marlin_format", config_dict)
        self.assertEqual(config_dict["is_marlin_format"], True)


class TestMarlinImportInBase(unittest.TestCase):
    """Test that _base.py imports from marlin_utils correctly."""

    def test_marlin_imports_in_base(self):
        """Test that _base.py imports marlin utilities from the right location."""
        # This test verifies the import structure by checking if the module loads
        # If the imports are wrong, this will fail with ImportError
        from auto_gptq.modeling._base import BaseGPTQForCausalLM

        # If we got here, the imports are correct
        self.assertIsNotNone(BaseGPTQForCausalLM)


if __name__ == "__main__":
    unittest.main()
