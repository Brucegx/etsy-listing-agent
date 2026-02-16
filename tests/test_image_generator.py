"""Tests for image generator using Gemini 3 Pro."""

from unittest.mock import patch, MagicMock

from etsy_listing_agent.image_generator import generate_image_gemini


def test_generate_image_uses_flash_model():
    """generate_image_gemini calls Gemini with the 3 Pro Image model."""
    mock_client = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = b"fake_png_data"
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_response

    with patch("etsy_listing_agent.image_generator.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        result = generate_image_gemini("test prompt", api_key="fake-key")

    call_kwargs = mock_client.models.generate_content.call_args
    assert call_kwargs.kwargs["model"] == "gemini-3-pro-image-preview"
    assert result == b"fake_png_data"


def test_generate_image_returns_bytes():
    """generate_image_gemini returns raw image bytes from API response."""
    mock_client = MagicMock()
    expected_bytes = b"\x89PNG_fake_image_data"
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = expected_bytes
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_client.models.generate_content.return_value = mock_response

    with patch("etsy_listing_agent.image_generator.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        result = generate_image_gemini("a product photo", api_key="test-key")

    assert result == expected_bytes
