# src/etsy_listing_agent/traced_agent.py
"""
LangSmith-traced wrapper for claude_agent_sdk.

Captures token usage and cost from ResultMessage for LangSmith visibility.
"""

import re
from typing import Any

from claude_agent_sdk import query, ClaudeAgentOptions
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree


def _extract_prompt_from_result(result_text: str) -> str:
    """Extract prompt text from result, handling escaped newlines."""
    text = result_text.replace("\\n", "\n")

    # Find REFERENCE ANCHOR start
    anchor_idx = text.find("REFERENCE ANCHOR:")
    if anchor_idx == -1:
        return text

    # Find end markers
    end_markers = ["\n\nDesign Rationale:", "\n\n## ", '",']
    end_idx = len(text)
    for marker in end_markers:
        idx = text.find(marker, anchor_idx)
        if idx != -1 and idx < end_idx:
            end_idx = idx

    return text[anchor_idx:end_idx].strip()


@traceable(run_type="llm", name="Claude Agent SDK")
async def traced_agent_query(
    prompt: str,
    options: ClaudeAgentOptions,
    direction_type: str = "",
) -> dict[str, Any]:
    """
    Wrapper around claude_agent_sdk.query() with LangSmith tracing.

    Captures from ResultMessage:
    - total_cost_usd
    - usage (input_tokens, output_tokens, cache tokens)
    - duration_ms

    Args:
        prompt: User prompt to send
        options: ClaudeAgentOptions configuration
        direction_type: Optional label for tracing (e.g., "hero", "wearing_a")

    Returns:
        dict with: prompt, cost_usd, input_tokens, output_tokens, messages
    """
    total_cost = 0.0
    total_input = 0
    total_output = 0
    total_cache_read = 0
    messages = []
    final_result = ""

    async for message in query(prompt=prompt, options=options):
        messages.append(message)

        # Capture cost/tokens from ResultMessage
        if hasattr(message, 'total_cost_usd'):
            total_cost += message.total_cost_usd

        if hasattr(message, 'usage') and isinstance(message.usage, dict):
            total_input += message.usage.get('input_tokens', 0)
            total_output += message.usage.get('output_tokens', 0)
            total_cache_read += message.usage.get('cache_read_input_tokens', 0)

        # Capture final result text
        if hasattr(message, 'result') and message.result:
            final_result = message.result

    # Extract clean prompt from result
    extracted_prompt = _extract_prompt_from_result(final_result)

    # Set LangSmith metadata
    try:
        run = get_current_run_tree()
        if run:
            run.extra["total_cost"] = total_cost
            run.extra["metadata"] = {
                "direction": direction_type,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "cache_read_tokens": total_cache_read,
            }
    except Exception:
        pass

    return {
        "prompt": extracted_prompt,
        "cost_usd": total_cost,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cache_read_tokens": total_cache_read,
        "messages": messages,
        "raw_result": final_result,
    }
