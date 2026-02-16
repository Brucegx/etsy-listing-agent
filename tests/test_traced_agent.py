# tests/test_traced_agent.py
"""Tests for traced_agent wrapper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockResultMessage:
    """Mock ResultMessage from claude_agent_sdk."""
    def __init__(self, cost=0.05, input_tokens=100, output_tokens=50):
        self.total_cost_usd = cost
        self.usage = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cache_read_input_tokens': 0,
        }
        self.result = "REFERENCE ANCHOR: Test product. Rigid constraint."


class MockTextBlock:
    """Mock TextBlock message."""
    def __init__(self, text):
        self.text = text


@pytest.mark.asyncio
async def test_traced_agent_query_captures_cost():
    """traced_agent_query should capture cost from ResultMessage."""
    from etsy_listing_agent.traced_agent import traced_agent_query

    mock_messages = [
        MockTextBlock("Processing..."),
        MockResultMessage(cost=0.08, input_tokens=200, output_tokens=100),
    ]

    async def mock_query(*args, **kwargs):
        for msg in mock_messages:
            yield msg

    with patch('etsy_listing_agent.traced_agent.query', mock_query):
        result = await traced_agent_query(
            prompt="Generate a prompt",
            options=MagicMock(),
            direction_type="hero",
        )

    assert result["cost_usd"] == 0.08
    assert result["input_tokens"] == 200
    assert result["output_tokens"] == 100


@pytest.mark.asyncio
async def test_traced_agent_query_extracts_prompt():
    """traced_agent_query should extract prompt text from result."""
    from etsy_listing_agent.traced_agent import traced_agent_query

    mock_result = MockResultMessage()
    mock_result.result = "REFERENCE ANCHOR: Gold ring. Rigid constraint.\n\nSCENE CONTEXT: Studio shot."

    async def mock_query(*args, **kwargs):
        yield mock_result

    with patch('etsy_listing_agent.traced_agent.query', mock_query):
        result = await traced_agent_query(
            prompt="Generate",
            options=MagicMock(),
        )

    assert "REFERENCE ANCHOR:" in result["prompt"]
    assert "Rigid constraint" in result["prompt"]
