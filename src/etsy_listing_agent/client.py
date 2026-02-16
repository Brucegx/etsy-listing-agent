# Multi-model API client
# Supports Claude (with prompt caching) and MiniMax M2.1
# Integrates LangSmith tracing (manual control of tokens + cost)

import base64
import os
from pathlib import Path
from typing import Any, Callable, Optional

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from openai import AsyncOpenAI

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# ===== API Keys =====
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")

# MiniMax Anthropic-compatible endpoint
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"

# Kimi (Moonshot) OpenAI-compatible endpoint
MOONSHOT_BASE_URL = os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")

# Provider preference: "kimi" | "claude" | "auto" (auto = kimi primary, claude fallback)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto")

# ===== Cost configuration (USD per 1M tokens) =====
COST_PER_1M = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "MiniMax-M2.5": {"input": 0.3, "output": 1.2},
    "MiniMax-M2.5-highspeed": {"input": 0.3, "output": 2.4},
    "MiniMax-M2.1": {"input": 0.7, "output": 2.8},
    "MiniMax-M2.1-lightning": {"input": 0.7, "output": 2.8},
    "moonshotai/kimi-k2.5": {"input": 0.5, "output": 2.8, "cache_read": 0.15},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0) -> float:
    """Calculate API call cost."""
    costs = COST_PER_1M.get(model, {"input": 1.0, "output": 1.0, "cache_read": 0.1})
    cost = (
        (input_tokens / 1_000_000) * costs["input"]
        + (output_tokens / 1_000_000) * costs["output"]
        + (cache_read / 1_000_000) * costs.get("cache_read", 0.1)
    )
    return cost


def get_claude_client(api_key: Optional[str] = None) -> AsyncAnthropic:
    """Get async Claude client (auto-retries on 429/529 with exponential backoff)."""
    key = api_key or ANTHROPIC_API_KEY
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return AsyncAnthropic(api_key=key, max_retries=3)


def get_minimax_client(api_key: Optional[str] = None) -> AsyncAnthropic:
    """Get async MiniMax client (auto-retries on 429/529 with exponential backoff)."""
    key = api_key or MINIMAX_API_KEY
    if not key:
        raise ValueError("MINIMAX_API_KEY not set")
    return AsyncAnthropic(api_key=key, base_url=MINIMAX_BASE_URL, max_retries=3)


def _build_image_blocks(image_paths: list[Path]) -> list[dict]:
    """Encode images as base64 content blocks for Claude Vision API."""
    blocks: list[dict] = []
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    for p in image_paths:
        if not p.exists():
            print(f"  ⚠️ Image not found, skipping: {p}")
            continue
        media_type = mime_map.get(p.suffix.lower(), "image/jpeg")
        data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })
    return blocks


def get_kimi_client(api_key: Optional[str] = None) -> AsyncOpenAI:
    """Get async Kimi (Moonshot) client -- OpenAI-compatible API."""
    key = api_key or MOONSHOT_API_KEY
    if not key:
        raise ValueError("MOONSHOT_API_KEY not set")
    return AsyncOpenAI(api_key=key, base_url=MOONSHOT_BASE_URL, max_retries=3)


def _build_openai_image_blocks(image_paths: list[Path]) -> list[dict]:
    """Encode images as OpenAI-format image_url content blocks for Kimi Vision."""
    blocks: list[dict] = []
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    for p in image_paths:
        if not p.exists():
            print(f"  ⚠️ Image not found, skipping: {p}")
            continue
        media_type = mime_map.get(p.suffix.lower(), "image/jpeg")
        data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
        blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{data}"},
        })
    return blocks


@traceable(run_type="llm", name="Kimi API")
async def call_kimi(
    system_prompt: str,
    user_message: str,
    api_key: Optional[str] = None,
    model: str = "moonshotai/kimi-k2.5",
    max_tokens: int = 4096,
    images: list[Path] | None = None,
    trace_name: str | None = None,
) -> dict:
    """Call Kimi K2.5 API (OpenAI-compatible, multimodal).

    Args:
        system_prompt: System prompt text
        user_message: User message text
        images: Optional list of image Paths (Vision API)

    Returns:
        dict with text, usage_metadata, cost_usd (same format as call_claude)
    """
    if trace_name:
        try:
            run = get_current_run_tree()
            if run:
                run.name = trace_name
        except Exception:
            pass

    client = get_kimi_client(api_key)

    # Build user content: image blocks + text (OpenAI format)
    if images:
        image_blocks = _build_openai_image_blocks(images)
        user_content = image_blocks + [{"type": "text", "text": user_message}]
    else:
        user_content = user_message

    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )

    # Check for truncation
    finish_reason = response.choices[0].finish_reason
    if finish_reason == "length":
        print(f"  ⚠️ Kimi: response truncated (finish_reason=length, max_tokens={max_tokens})")

    # Extract text
    text_content = response.choices[0].message.content or ""

    if finish_reason == "length" and not text_content.strip():
        raise RuntimeError(f"Kimi response truncated with empty text (max_tokens={max_tokens})")

    # Usage info
    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    cache_read = getattr(usage, "prompt_cache_hit_tokens", 0) or 0

    # Calculate cost
    cost = calculate_cost(model, input_tokens, output_tokens, cache_read)

    print(f"  📊 Kimi: in={input_tokens}, out={output_tokens}, cache_read={cache_read}, cost=${cost:.4f}")

    # LangSmith cost tracking
    try:
        run = get_current_run_tree()
        if run:
            run.extra["total_cost"] = cost
    except Exception:
        pass

    return {
        "text": text_content,
        "usage_metadata": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cache_read_tokens": cache_read,
            "total_cost": cost,
        },
        "model": model,
        "cost_usd": cost,
    }


@traceable(run_type="llm", name="Claude API")
async def call_claude(
    system_prompt: str,
    user_message: str,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    use_cache: bool = False,
    images: list[Path] | None = None,
    trace_name: str | None = None,
) -> dict:
    """Call Claude API (supports Prompt Caching + Vision).

    Args:
        system_prompt: System prompt text
        user_message: User message text
        images: Optional list of image Paths to include (Vision API)

    Returns:
        dict with text, usage_metadata, cost for LangSmith
    """
    # Dynamic trace name for LangSmith
    if trace_name:
        try:
            run = get_current_run_tree()
            if run:
                run.name = trace_name
        except Exception:
            pass

    client = get_claude_client(api_key)

    # Build user content: image blocks + text
    if images:
        image_blocks = _build_image_blocks(images)
        user_content = image_blocks + [{"type": "text", "text": user_message}]
    else:
        user_content = user_message

    # Build messages
    if use_cache and system_prompt.strip():
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
    else:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

    # Extract text content
    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    # Get usage info
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0

    # Calculate cost
    cost = calculate_cost(model, input_tokens, output_tokens, cache_read)

    # Print usage info
    print(f"  📊 Claude: in={input_tokens}, out={output_tokens}, cache_read={cache_read}, cost=${cost:.4f}")
    if cache_created > 0:
        print(f"  📦 Cache created: {cache_created} tokens")

    # Set LangSmith cost (directly on the run)
    try:
        run = get_current_run_tree()
        if run:
            # Cost field recognized by LangSmith
            run.extra["total_cost"] = cost
    except Exception:
        pass

    # Return dict containing all tracing info
    return {
        "text": text_content,
        "usage_metadata": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cache_read_tokens": cache_read,
            "cache_created_tokens": cache_created,
            "total_cost": cost,  # Also included in usage_metadata
        },
        "model": model,
        "cost_usd": cost,
    }


@traceable(run_type="llm", name="MiniMax API")
async def call_minimax(
    system_prompt: str,
    user_message: str,
    api_key: Optional[str] = None,
    model: str = "MiniMax-M2.5",
    max_tokens: int = 16000,
    trace_name: str | None = None,
) -> dict:
    """Call MiniMax M2.1 API (Anthropic-compatible).

    Returns:
        dict with text, usage_metadata, cost for LangSmith
    """
    if trace_name:
        try:
            run = get_current_run_tree()
            if run:
                run.name = trace_name
        except Exception:
            pass

    client = get_minimax_client(api_key)

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text content
    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    # Get usage info
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens

    # Calculate cost
    cost = calculate_cost(model, input_tokens, output_tokens)

    # Print usage info
    print(f"  📊 MiniMax: in={input_tokens}, out={output_tokens}, cost=${cost:.4f}")

    # Set LangSmith cost (directly on the run)
    try:
        run = get_current_run_tree()
        if run:
            run.extra["total_cost"] = cost
    except Exception:
        pass

    # Return dict containing all tracing info
    return {
        "text": text_content,
        "usage_metadata": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "total_cost": cost,
        },
        "model": model,
        "cost_usd": cost,
    }


@traceable(run_type="chain", name="LLM with Fallback")
async def call_llm_with_fallback(
    system_prompt: str,
    user_message: str,
    images: list[Path] | None = None,
    primary: str | None = None,
    fallback: str | None = None,
    max_tokens: int = 4096,
    use_cache: bool = False,
    trace_name: str | None = None,
) -> dict:
    """Call LLM with automatic fallback on failure.

    Provider resolution:
    - LLM_PROVIDER="kimi"  → kimi only (no fallback)
    - LLM_PROVIDER="claude" → claude only (no fallback)
    - LLM_PROVIDER="auto"  → primary=kimi, fallback=claude (default)

    Returns dict with same format + extra `provider` field.
    """
    if trace_name:
        try:
            run = get_current_run_tree()
            if run:
                run.name = trace_name
        except Exception:
            pass

    # Resolve provider order from env or params
    if primary is None:
        if LLM_PROVIDER == "kimi":
            primary, fallback = "kimi", None
        elif LLM_PROVIDER == "claude":
            primary, fallback = "claude", None
        else:  # "auto"
            primary, fallback = "kimi", "claude"

    providers = [primary]
    if fallback:
        providers.append(fallback)

    last_error = None
    for provider in providers:
        try:
            if provider == "kimi":
                result = await call_kimi(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    images=images,
                    max_tokens=max_tokens,
                    trace_name=f"{trace_name} [Kimi]" if trace_name else "Kimi",
                )
            else:  # claude
                result = await call_claude(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    images=images,
                    max_tokens=max_tokens,
                    use_cache=use_cache,
                    trace_name=f"{trace_name} [Claude]" if trace_name else "Claude",
                )
            result["provider"] = provider
            return result
        except Exception as e:
            last_error = e
            provider_name = provider.capitalize()
            print(f"  ⚠️ {provider_name} failed: {e}")
            if fallback and provider == primary:
                print(f"  🔄 Falling back to {fallback}...")
                continue
            raise

    # Should not reach here, but just in case
    raise last_error


def _serialize_content(content: list) -> list[dict]:
    """Serialize Anthropic SDK content blocks to dicts for message history.

    Ensures cross-provider compatibility (Claude / MiniMax).
    """
    result = []
    for block in content:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


@traceable(run_type="chain", name="LLM Call")
async def _agent_llm_call(
    client, model: str, system_prompt: str, messages: list,
    tools: list, max_tokens: int, turn_number: int,
):
    """Single LLM call — traced as child span in LangSmith."""
    try:
        run = get_current_run_tree()
        if run:
            run.name = f"Turn {turn_number}"
    except Exception:
        pass
    return await client.messages.create(
        model=model,
        system=system_prompt,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
        timeout=120.0,
    )


@traceable(run_type="tool", name="Tool Execution")
def _traced_tool_call(tool_handler: Callable, tool_name: str, tool_input: dict) -> str:
    """Execute a tool call — traced as child span in LangSmith."""
    try:
        run = get_current_run_tree()
        if run:
            run.name = tool_name
    except Exception:
        pass
    return tool_handler(tool_name, tool_input)


@traceable(run_type="chain", name="Agentic Loop")
async def agentic_loop(
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]],
    tool_handler: Callable[[str, dict[str, Any]], str],
    model: str = "MiniMax-M2.5",
    max_tokens: int = 4096,
    max_turns: int = 5,
    api_key: str | None = None,
    trace_name: str | None = None,
) -> dict:
    """Multi-turn agentic loop with tool use.

    The agent can call tools (e.g., read_reference, validate_prompt) to
    load context and self-validate, then generate its final output.

    Typical flow (3-4 turns):
      Turn 1: Agent reasons + parallel tool calls (read references)
      Turn 2: Agent generates prompt + calls validate_prompt
      Turn 3: Agent sees validation result → outputs final text (with fixes)

    Args:
        system_prompt: System prompt (e.g., prompt generation config)
        user_message: Task description with available tools listed
        tools: Tool definitions in Anthropic format
        tool_handler: Function(tool_name, tool_input) -> result string
        model: Model name — "MiniMax*" uses MiniMax client, else Claude
        max_tokens: Max tokens per response
        max_turns: Max conversation turns (safety limit)
        api_key: Optional API key override
        trace_name: Override trace name in LangSmith (e.g., "Prompt: hero")
    """
    if trace_name:
        try:
            run = get_current_run_tree()
            if run:
                run.name = trace_name
        except Exception:
            pass

    if "MiniMax" in model:
        client = get_minimax_client(api_key)
    else:
        client = get_claude_client(api_key)

    messages: list[dict] = [{"role": "user", "content": user_message}]
    total_input = 0
    total_output = 0
    total_cost = 0.0
    turns_used = 0

    for turn in range(max_turns):
        turns_used = turn + 1

        try:
            response = await _agent_llm_call(
                client, model, system_prompt, messages,
                tools, max_tokens, turns_used,
            )
        except Exception as e:
            print(f"  ❌ Agentic: API error on turn {turns_used}: {e}")
            # Return whatever we have so far
            text = ""
            for msg in reversed(messages):
                if msg["role"] == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text += block["text"]
                    break
            return {
                "text": text,
                "usage_metadata": {
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "total_tokens": total_input + total_output,
                    "total_cost": total_cost,
                    "turns": turns_used,
                },
                "model": model,
                "cost_usd": total_cost,
                "error": str(e),
            }

        # Track usage
        usage = response.usage
        total_input += usage.input_tokens
        total_output += usage.output_tokens
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        total_cost += calculate_cost(model, usage.input_tokens, usage.output_tokens, cache_read)

        if response.stop_reason == "tool_use":
            # Execute all tool calls (may be parallel from agent)
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"    🔧 Tool: {block.name}({block.input})")
                    try:
                        result = _traced_tool_call(tool_handler, block.name, block.input)
                    except Exception as e:
                        print(f"    ❌ Tool error: {e}")
                        result = f"Error executing tool: {e}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Continue conversation with tool results
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            messages.append({"role": "user", "content": tool_results})
        else:
            # Final text response
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            print(f"  📊 Agentic: {turns_used} turns, in={total_input}, out={total_output}, cost=${total_cost:.4f}")

            try:
                run = get_current_run_tree()
                if run:
                    run.extra["total_cost"] = total_cost
            except Exception:
                pass

            return {
                "text": text,
                "usage_metadata": {
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "total_tokens": total_input + total_output,
                    "total_cost": total_cost,
                    "turns": turns_used,
                },
                "model": model,
                "cost_usd": total_cost,
            }

    # Max turns exceeded — extract any text from last response
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    if not text.strip():
        # No text output after exhausting all turns — this is a real failure
        print(f"  ❌ Agentic: max turns ({max_turns}) exhausted with NO text output")
        raise RuntimeError(
            f"Agentic loop exhausted {max_turns} turns without generating text. "
            f"Agent spent all turns on tool calls. "
            f"Cost: ${total_cost:.4f}, tokens: in={total_input} out={total_output}"
        )

    # Had text but hit max turns — return with warning
    print(f"  ⚠️ Agentic: max turns ({max_turns}) reached, but text present ({len(text)} chars)")
    return {
        "text": text,
        "usage_metadata": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": total_cost,
            "turns": turns_used,
        },
        "model": model,
        "cost_usd": total_cost,
    }


def extract_json_from_response(response: str) -> str:
    """Extract JSON from response text."""
    response = response.strip()

    if response.startswith("{") and response.endswith("}"):
        return response
    if response.startswith("[") and response.endswith("]"):
        return response

    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end > start:
            return response[start:end].strip()

    if "```" in response:
        start = response.find("```") + 3
        if response[start : start + 4] == "json":
            start += 4
        end = response.find("```", start)
        if end > start:
            return response[start:end].strip()

    first_brace = response.find("{")
    last_brace = response.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        return response[first_brace : last_brace + 1]

    first_bracket = response.find("[")
    last_bracket = response.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        return response[first_bracket : last_bracket + 1]

    return response
