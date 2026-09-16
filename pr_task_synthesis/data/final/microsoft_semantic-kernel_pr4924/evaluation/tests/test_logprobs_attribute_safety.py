# Copyright (c) Microsoft. All rights reserved.

"""
Tests for safe attribute access in _get_metadata_from_chat_choice.

This test module verifies that the fix for Azure OpenAI logprobs attribute
handling works correctly. The issue is that Azure OpenAI responses may not
include the logprobs field, causing an AttributeError when accessing
choice.logprobs directly.

The fix uses getattr(choice, "logprobs", None) to safely access the attribute.
"""

import pytest
from unittest.mock import MagicMock, patch

from openai import AsyncOpenAI


class TestLogprobsAttributeSafety:
    """Tests for _get_metadata_from_chat_choice method."""

    @pytest.fixture
    def chat_completion_base(self):
        """Create an instance of OpenAIChatCompletionBase for testing."""
        # Mock the async client to avoid needing real API credentials
        mock_client = MagicMock(spec=AsyncOpenAI)

        # Import and instantiate with mocked client
        from semantic_kernel.connectors.ai.open_ai.services.open_ai_chat_completion import (
            OpenAIChatCompletion,
        )

        return OpenAIChatCompletion(
            ai_model_id="test_model",
            async_client=mock_client,
        )

    def test_get_metadata_with_logprobs_present(self, chat_completion_base):
        """Test metadata extraction when logprobs attribute is present."""
        # Create a mock choice object WITH logprobs attribute
        mock_choice = MagicMock()
        mock_choice.logprobs = {"token_logprobs": [-0.1, -0.2, -0.3]}

        result = chat_completion_base._get_metadata_from_chat_choice(mock_choice)

        assert result == {"logprobs": {"token_logprobs": [-0.1, -0.2, -0.3]}}

    def test_get_metadata_without_logprobs_attribute(self, chat_completion_base):
        """
        Test metadata extraction when logprobs attribute is NOT present.

        This is the key test for the Azure OpenAI bug fix. Azure OpenAI
        responses may not include the logprobs field, and the code should
        return None instead of raising AttributeError.
        """
        # Create a mock choice object WITHOUT logprobs attribute
        mock_choice = MagicMock(spec=[])  # Empty spec means no attributes

        result = chat_completion_base._get_metadata_from_chat_choice(mock_choice)

        # Should return {"logprobs": None} instead of raising AttributeError
        assert result == {"logprobs": None}

    def test_get_metadata_with_logprobs_none(self, chat_completion_base):
        """Test metadata extraction when logprobs is explicitly None."""
        # Create a mock choice object with logprobs explicitly set to None
        mock_choice = MagicMock()
        mock_choice.logprobs = None

        result = chat_completion_base._get_metadata_from_chat_choice(mock_choice)

        assert result == {"logprobs": None}

    def test_get_metadata_chunk_choice_with_logprobs(self, chat_completion_base):
        """Test metadata extraction for ChunkChoice with logprobs present."""
        # Create a mock chunk choice WITH logprobs attribute
        mock_chunk_choice = MagicMock()
        mock_chunk_choice.logprobs = {"content": [{"token": "test", "logprob": -0.5}]}

        result = chat_completion_base._get_metadata_from_chat_choice(
            mock_chunk_choice
        )

        assert result == {
            "logprobs": {"content": [{"token": "test", "logprob": -0.5}]}
        }

    def test_get_metadata_chunk_choice_without_logprobs(self, chat_completion_base):
        """
        Test metadata extraction for ChunkChoice without logprobs attribute.

        This tests the streaming scenario where Azure OpenAI may not include
        logprobs in chunk choices.
        """
        # Create a mock chunk choice WITHOUT logprobs attribute
        mock_chunk_choice = MagicMock(spec=[])  # Empty spec means no attributes

        result = chat_completion_base._get_metadata_from_chat_choice(
            mock_chunk_choice
        )

        # Should return {"logprobs": None} instead of raising AttributeError
        assert result == {"logprobs": None}
