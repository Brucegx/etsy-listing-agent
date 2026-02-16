# Tests for multi-provider client (Kimi K2.5 + Claude fallback)

import base64
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


# ===== call_kimi Tests =====


class TestCallKimi:
    """Tests for call_kimi — Kimi K2.5 via OpenAI-compatible API"""

    @pytest.mark.asyncio
    async def test_call_kimi_returns_correct_format(self):
        """call_kimi should return dict with text, usage_metadata, model, cost_usd"""
        from etsy_listing_agent.client import call_kimi

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.prompt_cache_hit_tokens = 0

        mock_message = MagicMock()
        mock_message.content = "Test response from Kimi"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("etsy_listing_agent.client.get_kimi_client", return_value=mock_client):
            result = await call_kimi(
                system_prompt="You are a helpful assistant.",
                user_message="Hello",
            )

        assert result["text"] == "Test response from Kimi"
        assert result["model"] == "moonshotai/kimi-k2.5"
        assert result["cost_usd"] >= 0
        assert "usage_metadata" in result
        assert result["usage_metadata"]["input_tokens"] == 100
        assert result["usage_metadata"]["output_tokens"] == 50

    @pytest.mark.asyncio
    async def test_call_kimi_with_images(self, tmp_path):
        """call_kimi should handle images via OpenAI image_url format"""
        from etsy_listing_agent.client import call_kimi

        # Create a fake image
        img_path = tmp_path / "test.jpg"
        img_path.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 200
        mock_usage.completion_tokens = 80
        mock_usage.prompt_cache_hit_tokens = 0

        mock_message = MagicMock()
        mock_message.content = "I see a product image"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("etsy_listing_agent.client.get_kimi_client", return_value=mock_client):
            result = await call_kimi(
                system_prompt="Analyze this image.",
                user_message="What do you see?",
                images=[img_path],
            )

        # Verify image was passed as OpenAI format
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        # First block should be image_url
        assert user_msg["content"][0]["type"] == "image_url"
        assert "data:image/jpeg;base64," in user_msg["content"][0]["image_url"]["url"]
        # Last block should be text
        assert user_msg["content"][-1]["type"] == "text"

        assert result["text"] == "I see a product image"

    @pytest.mark.asyncio
    async def test_call_kimi_system_prompt_in_messages(self):
        """call_kimi should put system prompt as messages[0] with role 'system'"""
        from etsy_listing_agent.client import call_kimi

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 20
        mock_usage.prompt_cache_hit_tokens = 0

        mock_message = MagicMock()
        mock_message.content = "OK"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("etsy_listing_agent.client.get_kimi_client", return_value=mock_client):
            await call_kimi(
                system_prompt="Be concise.",
                user_message="Hi",
            )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be concise."
        assert messages[1]["role"] == "user"


# ===== call_llm_with_fallback Tests =====


class TestCallLLMWithFallback:
    """Tests for call_llm_with_fallback — provider fallback logic"""

    @pytest.mark.asyncio
    async def test_fallback_uses_primary_on_success(self):
        """Should use primary provider when it succeeds"""
        from etsy_listing_agent.client import call_llm_with_fallback

        kimi_result = {
            "text": "Kimi response",
            "usage_metadata": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "model": "moonshotai/kimi-k2.5",
            "cost_usd": 0.001,
        }

        with patch("etsy_listing_agent.client.call_kimi", return_value=kimi_result) as mock_kimi, \
             patch("etsy_listing_agent.client.call_claude") as mock_claude:
            result = await call_llm_with_fallback(
                system_prompt="test",
                user_message="test",
                primary="kimi",
                fallback="claude",
            )

        assert result["text"] == "Kimi response"
        assert result["provider"] == "kimi"
        mock_kimi.assert_called_once()
        mock_claude.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_claude_on_kimi_failure(self):
        """Should fall back to Claude when Kimi fails"""
        from etsy_listing_agent.client import call_llm_with_fallback

        claude_result = {
            "text": "Claude fallback response",
            "usage_metadata": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "model": "claude-sonnet-4-20250514",
            "cost_usd": 0.005,
        }

        with patch("etsy_listing_agent.client.call_kimi", side_effect=Exception("Kimi 529 overloaded")), \
             patch("etsy_listing_agent.client.call_claude", return_value=claude_result):
            result = await call_llm_with_fallback(
                system_prompt="test",
                user_message="test",
                primary="kimi",
                fallback="claude",
            )

        assert result["text"] == "Claude fallback response"
        assert result["provider"] == "claude"

    @pytest.mark.asyncio
    async def test_fallback_raises_when_all_fail(self):
        """Should raise when both providers fail"""
        from etsy_listing_agent.client import call_llm_with_fallback

        with patch("etsy_listing_agent.client.call_kimi", side_effect=Exception("Kimi down")), \
             patch("etsy_listing_agent.client.call_claude", side_effect=Exception("Claude 529")):
            with pytest.raises(Exception, match="Claude 529"):
                await call_llm_with_fallback(
                    system_prompt="test",
                    user_message="test",
                    primary="kimi",
                    fallback="claude",
                )

    @pytest.mark.asyncio
    async def test_fallback_respects_llm_provider_env(self):
        """LLM_PROVIDER=claude should skip Kimi entirely"""
        from etsy_listing_agent.client import call_llm_with_fallback

        claude_result = {
            "text": "Claude only",
            "usage_metadata": {"input_tokens": 50, "output_tokens": 25, "total_tokens": 75},
            "model": "claude-sonnet-4-20250514",
            "cost_usd": 0.003,
        }

        with patch("etsy_listing_agent.client.LLM_PROVIDER", "claude"), \
             patch("etsy_listing_agent.client.call_claude", return_value=claude_result) as mock_claude, \
             patch("etsy_listing_agent.client.call_kimi") as mock_kimi:
            result = await call_llm_with_fallback(
                system_prompt="test",
                user_message="test",
            )

        assert result["provider"] == "claude"
        mock_claude.assert_called_once()
        mock_kimi.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_passes_images_to_provider(self, tmp_path):
        """Images should be forwarded to the provider"""
        from etsy_listing_agent.client import call_llm_with_fallback

        img = tmp_path / "test.jpg"
        img.write_bytes(b"fake")

        kimi_result = {
            "text": "saw image",
            "usage_metadata": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "model": "moonshotai/kimi-k2.5",
            "cost_usd": 0.001,
        }

        with patch("etsy_listing_agent.client.call_kimi", return_value=kimi_result) as mock_kimi:
            await call_llm_with_fallback(
                system_prompt="test",
                user_message="test",
                images=[img],
                primary="kimi",
                fallback="claude",
            )

        call_kwargs = mock_kimi.call_args.kwargs
        assert call_kwargs["images"] == [img]


# ===== Kimi Pricing Tests =====


class TestKimiPricing:
    """Tests for Kimi cost calculation"""

    def test_kimi_pricing_in_cost_table(self):
        """moonshotai/kimi-k2.5 should be in COST_PER_1M table"""
        from etsy_listing_agent.client import COST_PER_1M
        assert "moonshotai/kimi-k2.5" in COST_PER_1M
        assert COST_PER_1M["moonshotai/kimi-k2.5"]["input"] == 0.5
        assert COST_PER_1M["moonshotai/kimi-k2.5"]["output"] == 2.8

    def test_kimi_cost_calculation(self):
        """Cost for 1000 input + 500 output tokens"""
        from etsy_listing_agent.client import calculate_cost
        cost = calculate_cost("moonshotai/kimi-k2.5", 1000, 500)
        # (1000/1M * 0.5) + (500/1M * 2.8) = 0.0005 + 0.0014 = 0.0019
        assert abs(cost - 0.0019) < 1e-6


# ===== OpenAI Image Format Tests =====


class TestOpenAIImageBlocks:
    """Tests for _build_openai_image_blocks"""

    def test_build_openai_image_blocks(self, tmp_path):
        """Should create OpenAI-format image_url blocks with base64"""
        from etsy_listing_agent.client import _build_openai_image_blocks

        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0test_image")

        blocks = _build_openai_image_blocks([img])
        assert len(blocks) == 1
        assert blocks[0]["type"] == "image_url"
        assert blocks[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    def test_build_openai_image_blocks_skips_missing(self, tmp_path):
        """Should skip missing image files"""
        from etsy_listing_agent.client import _build_openai_image_blocks

        missing = tmp_path / "nonexistent.jpg"
        blocks = _build_openai_image_blocks([missing])
        assert len(blocks) == 0

    def test_build_openai_image_blocks_png(self, tmp_path):
        """Should handle PNG images with correct media type"""
        from etsy_listing_agent.client import _build_openai_image_blocks

        img = tmp_path / "photo.png"
        img.write_bytes(b"\x89PNG\r\ntest")

        blocks = _build_openai_image_blocks([img])
        assert blocks[0]["image_url"]["url"].startswith("data:image/png;base64,")
