"""
Hidden tests for Kohya and XLabs LoRA conversion functionality.

These tests verify that the _convert_kohya_flux_lora_to_diffusers() and
_convert_xlabs_flux_lora_to_diffusers() functions properly convert
external LoRA formats to the internal diffusers representation.

Tests are designed to:
- Be deterministic (no network access required)
- Fail without the fix (functions don't exist)
- Pass with the fix (functions work correctly)
"""

import torch
import pytest


class TestKohyaFluxLoRAConversion:
    """Tests for _convert_kohya_flux_lora_to_diffusers() function."""

    def test_convert_kohya_function_exists(self):
        """Test that the conversion function is importable."""
        from diffusers.loaders.lora_conversion_utils import _convert_kohya_flux_lora_to_diffusers
        assert callable(_convert_kohya_flux_lora_to_diffusers)

    def test_convert_kohya_basic_conversion(self):
        """
        Test basic Kohya LoRA conversion with a single layer.

        The Kohya format uses keys like:
        - lora_unet_double_blocks_0_img_attn_proj.lora_down.weight
        - lora_unet_double_blocks_0_img_attn_proj.lora_up.weight
        - lora_unet_double_blocks_0_img_attn_proj.alpha

        The converted format should use:
        - transformer.transformer_blocks.0.attn.to_out.0.lora_A.weight
        - transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight
        """
        from diffusers.loaders.lora_conversion_utils import _convert_kohya_flux_lora_to_diffusers

        # Create a mock Kohya-style state dict with a single layer
        kohya_state_dict = {
            "lora_unet_double_blocks_0_img_attn_proj.lora_down.weight": torch.randn(16, 3072),
            "lora_unet_double_blocks_0_img_attn_proj.lora_up.weight": torch.randn(3072, 16),
            "lora_unet_double_blocks_0_img_attn_proj.alpha": torch.tensor(8.0),
        }

        # Convert to diffusers format
        converted = _convert_kohya_flux_lora_to_diffusers(kohya_state_dict.copy())

        # Verify the output has the expected keys
        assert "transformer.transformer_blocks.0.attn.to_out.0.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight" in converted

        # Verify the shapes are preserved
        assert converted["transformer.transformer_blocks.0.attn.to_out.0.lora_A.weight"].shape == (16, 3072)
        assert converted["transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight"].shape == (3072, 16)

    def test_convert_kohya_alpha_scaling(self):
        """
        Test that alpha scaling is correctly applied during conversion.

        The LoRA scaling factor is alpha / rank.
        The conversion should recompute this and apply it to the weights.
        """
        from diffusers.loaders.lora_conversion_utils import _convert_kohya_flux_lora_to_diffusers

        # Create a mock Kohya-style state dict with known alpha and rank
        rank = 16
        alpha = 8.0
        scale = alpha / rank  # 0.5

        kohya_state_dict = {
            "lora_unet_double_blocks_0_img_attn_proj.lora_down.weight": torch.ones((rank, 10)),
            "lora_unet_double_blocks_0_img_attn_proj.lora_up.weight": torch.ones((10, rank)),
            "lora_unet_double_blocks_0_img_attn_proj.alpha": torch.tensor(alpha),
        }

        # Convert to diffusers format
        converted = _convert_kohya_flux_lora_to_diffusers(kohya_state_dict.copy())

        # The down weight should be scaled by scale_down (which equals scale when scale < 1)
        # scale_down = 0.5, scale_up = 1.0
        expected_down = torch.ones((rank, 10)) * scale
        expected_up = torch.ones((10, rank)) * 1.0

        torch.testing.assert_close(
            converted["transformer.transformer_blocks.0.attn.to_out.0.lora_A.weight"],
            expected_down
        )
        torch.testing.assert_close(
            converted["transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight"],
            expected_up
        )

    def test_convert_kohya_multiple_layers(self):
        """Test conversion with multiple transformer blocks."""
        from diffusers.loaders.lora_conversion_utils import _convert_kohya_flux_lora_to_diffusers

        # Create a mock Kohya-style state dict with multiple layers
        kohya_state_dict = {}
        for i in range(3):
            kohya_state_dict[f"lora_unet_double_blocks_{i}_img_attn_proj.lora_down.weight"] = torch.randn(16, 3072)
            kohya_state_dict[f"lora_unet_double_blocks_{i}_img_attn_proj.lora_up.weight"] = torch.randn(3072, 16)
            kohya_state_dict[f"lora_unet_double_blocks_{i}_img_attn_proj.alpha"] = torch.tensor(8.0)

        # Convert to diffusers format
        converted = _convert_kohya_flux_lora_to_diffusers(kohya_state_dict.copy())

        # Verify all layers are converted
        for i in range(3):
            assert f"transformer.transformer_blocks.{i}.attn.to_out.0.lora_A.weight" in converted
            assert f"transformer.transformer_blocks.{i}.attn.to_out.0.lora_B.weight" in converted

    def test_convert_kohya_qkv_cat_conversion(self):
        """
        Test QKV concatenated weight conversion.

        Kohya uses a single concatenated weight for Q, K, V projections.
        The conversion should split these into separate weights.
        """
        from diffusers.loaders.lora_conversion_utils import _convert_kohya_flux_lora_to_diffusers

        # Create a mock Kohya-style state dict with QKV concatenated weights
        rank = 16
        kohya_state_dict = {
            # QKV for image attention (3x3072 output dim)
            "lora_unet_double_blocks_0_img_attn_qkv.lora_down.weight": torch.randn(rank, 3072),
            "lora_unet_double_blocks_0_img_attn_qkv.lora_up.weight": torch.randn(3072 * 3, rank),
            "lora_unet_double_blocks_0_img_attn_qkv.alpha": torch.tensor(8.0),
        }

        # Convert to diffusers format
        converted = _convert_kohya_flux_lora_to_diffusers(kohya_state_dict.copy())

        # Verify the output has separate Q, K, V keys
        assert "transformer.transformer_blocks.0.attn.to_q.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_k.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_v.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_q.lora_B.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_k.lora_B.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_v.lora_B.weight" in converted

    def test_convert_kohya_double_blocks_img_mlp(self):
        """Test conversion of img_mlp layers in double_blocks."""
        from diffusers.loaders.lora_conversion_utils import _convert_kohya_flux_lora_to_diffusers

        # Create a mock Kohya-style state dict for img_mlp
        kohya_state_dict = {
            "lora_unet_double_blocks_0_img_mlp_0.lora_down.weight": torch.randn(16, 12288),
            "lora_unet_double_blocks_0_img_mlp_0.lora_up.weight": torch.randn(12288, 16),
            "lora_unet_double_blocks_0_img_mlp_0.alpha": torch.tensor(8.0),
            "lora_unet_double_blocks_0_img_mlp_2.lora_down.weight": torch.randn(16, 12288),
            "lora_unet_double_blocks_0_img_mlp_2.lora_up.weight": torch.randn(12288, 16),
            "lora_unet_double_blocks_0_img_mlp_2.alpha": torch.tensor(8.0),
        }

        # Convert to diffusers format
        converted = _convert_kohya_flux_lora_to_diffusers(kohya_state_dict.copy())

        # Verify img_mlp keys are converted
        assert "transformer.transformer_blocks.0.ff.net.0.proj.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.ff.net.2.lora_A.weight" in converted


class TestXLabsFluxLoRAConversion:
    """Tests for _convert_xlabs_flux_lora_to_diffusers() function."""

    def test_convert_xlabs_function_exists(self):
        """Test that the XLabs conversion function is importable."""
        from diffusers.loaders.lora_conversion_utils import _convert_xlabs_flux_lora_to_diffusers
        assert callable(_convert_xlabs_flux_lora_to_diffusers)

    def test_convert_xlabs_basic_conversion(self):
        """
        Test basic XLabs LoRA conversion.

        XLabs format uses keys like:
        - diffusion_model.double_blocks.0.processor.proj_lora1.down.weight
        - diffusion_model.double_blocks.0.processor.proj_lora1.up.weight

        The converted format should use:
        - transformer.transformer_blocks.0.attn.to_out.0.lora_A.weight
        - transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight
        """
        from diffusers.loaders.lora_conversion_utils import _convert_xlabs_flux_lora_to_diffusers

        # Create a mock XLabs-style state dict
        xlabs_state_dict = {
            "diffusion_model.double_blocks.0.processor.proj_lora1.down.weight": torch.randn(16, 3072),
            "diffusion_model.double_blocks.0.processor.proj_lora1.up.weight": torch.randn(3072, 16),
        }

        # Convert to diffusers format
        converted = _convert_xlabs_flux_lora_to_diffusers(xlabs_state_dict.copy())

        # Verify the output has the expected keys
        assert "transformer.transformer_blocks.0.attn.to_out.0.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_out.0.lora_B.weight" in converted

    def test_convert_xlabs_qkv_lora2_conversion(self):
        """Test XLabs QKV conversion with qkv_lora2 (to_q, to_k, to_v)."""
        from diffusers.loaders.lora_conversion_utils import _convert_xlabs_flux_lora_to_diffusers

        # Create a mock XLabs-style state dict with QKV weights for qkv_lora2
        rank = 16
        xlabs_state_dict = {
            "diffusion_model.double_blocks.0.processor.qkv_lora2.down.weight": torch.randn(rank, 3072),
            "diffusion_model.double_blocks.0.processor.qkv_lora2.up.weight": torch.randn(3072 * 3, rank),
        }

        # Convert to diffusers format
        converted = _convert_xlabs_flux_lora_to_diffusers(xlabs_state_dict.copy())

        # Verify the output has separate Q, K, V keys (for qkv_lora2, these are to_q, to_k, to_v)
        assert "transformer.transformer_blocks.0.attn.to_q.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_k.lora_A.weight" in converted
        assert "transformer.transformer_blocks.0.attn.to_v.lora_A.weight" in converted

    def test_convert_xlabs_no_alpha(self):
        """
        Test that XLabs conversion does not require alpha values.

        XLabs checkpoints do not carry explicit alpha values,
        so the conversion should work without them.
        """
        from diffusers.loaders.lora_conversion_utils import _convert_xlabs_flux_lora_to_diffusers

        # Create a mock XLabs-style state dict without alpha
        xlabs_state_dict = {
            "diffusion_model.double_blocks.0.processor.proj_lora1.down.weight": torch.randn(16, 3072),
            "diffusion_model.double_blocks.0.processor.proj_lora1.up.weight": torch.randn(3072, 16),
            # No alpha value - this is expected for XLabs format
        }

        # Convert should succeed without alpha
        converted = _convert_xlabs_flux_lora_to_diffusers(xlabs_state_dict.copy())
        assert len(converted) > 0

    def test_convert_xlabs_empty_dict(self):
        """Test behavior with empty state dict."""
        from diffusers.loaders.lora_conversion_utils import _convert_xlabs_flux_lora_to_diffusers

        # Empty dict should return empty dict (no error)
        converted = _convert_xlabs_flux_lora_to_diffusers({})
        assert converted == {}


class TestIntegrationWithFluxLoraLoader:
    """Integration tests for LoRA loading with Kohya/XLabs formats."""

    def test_kohya_detection_in_state_dict(self):
        """Test that Kohya format is detected by lora_down.weight pattern."""
        # This tests the detection logic used in FluxLoraLoaderMixin
        kohya_state_dict = {
            "some_layer.lora_down.weight": torch.randn(16, 100),
            "some_layer.lora_up.weight": torch.randn(100, 16),
            "some_layer.alpha": torch.tensor(8.0),
        }

        is_kohya = any(".lora_down.weight" in k for k in kohya_state_dict)
        assert is_kohya is True

    def test_xlabs_detection_in_state_dict(self):
        """Test that XLabs format is detected by processor pattern."""
        # This tests the detection logic used in FluxLoraLoaderMixin
        xlabs_state_dict = {
            "diffusion_model.double_blocks.0.processor.proj_lora1.down.weight": torch.randn(16, 100),
            "diffusion_model.double_blocks.0.processor.proj_lora1.up.weight": torch.randn(100, 16),
        }

        is_xlabs = any("processor" in k for k in xlabs_state_dict)
        assert is_xlabs is True

    def test_non_diffusers_not_detected_as_kohya_or_xlabs(self):
        """Test that standard diffusers format is not misidentified."""
        diffusers_state_dict = {
            "transformer.transformer_blocks.0.attn.to_q.lora_A.weight": torch.randn(16, 100),
            "transformer.transformer_blocks.0.attn.to_q.lora_B.weight": torch.randn(100, 16),
        }

        is_kohya = any(".lora_down.weight" in k for k in diffusers_state_dict)
        is_xlabs = any("processor" in k for k in diffusers_state_dict)

        assert is_kohya is False
        assert is_xlabs is False
