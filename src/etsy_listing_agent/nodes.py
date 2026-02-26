# Agent and Reviewer nodes for the workflow
# Agent node and Reviewer node implementation

import json
import os
from pathlib import Path
from typing import Any, Callable

from langsmith import traceable

from etsy_listing_agent.state import ProductState, ReviewResult, ReviewLevel
from etsy_listing_agent.validators import (
    validate_product_data_schema,
    validate_product_data_rules,
    validate_strategy_schema,
    validate_strategy_rules,
    validate_nanobanana_schema,
    validate_nanobanana_rules,
    validate_listing_schema,
    validate_listing_rules,
)
from etsy_listing_agent.config_loader import (
    PREPROCESS_PROMPT,
    STRATEGY_PROMPT,
    LISTING_PROMPT,
    PROMPT_NODE_USER_MESSAGE,
    ANTI_AI_KEYWORDS,
    WEARING_BANNED,
    NANOBANANA_DIRECTIONS,
    READ_REFERENCE_TOOL,
    VALIDATE_PROMPT_TOOL,
)


# ===== Multi-Model API Call Functions =====

from etsy_listing_agent.client import call_claude, call_kimi, call_minimax, call_llm_with_fallback, agentic_loop, extract_json_from_response


async def call_claude_agent(
    system_prompt: str,
    user_message: str,
    cwd: str | None = None,
    api_key: str | None = None,
    use_cache: bool = False,
    image_files: list[str] | None = None,
    trace_name: str | None = None,
) -> str:
    """Call LLM Agent to execute task (Kimi primary, Claude fallback)

    Used for Preprocessing (requires image input) and Strategy (text-only).
    Provider controlled by LLM_PROVIDER env var (auto/kimi/claude).

    Args:
        image_files: List of image filenames. Resolved against cwd if provided.
        trace_name: Override trace name in LangSmith.
    """
    # Build image paths from filenames + cwd
    image_paths = None
    if image_files and cwd:
        image_paths = [Path(cwd) / f for f in image_files]

    result = await call_llm_with_fallback(
        system_prompt=system_prompt,
        user_message=user_message,
        images=image_paths,
        use_cache=use_cache,
        trace_name=trace_name,
    )
    provider = result.get("provider", "unknown")
    print(f"  ✓ Provider used: {provider}")
    text = result["text"] if isinstance(result, dict) else result
    return extract_json_from_response(text)


async def call_minimax_agent(
    system_prompt: str,
    user_message: str,
    api_key: str | None = None,
    trace_name: str | None = None,
) -> str:
    """Call MiniMax M2.5 Agent to execute task (used for NanoBanana + Listing)

    70-80% cheaper than Claude, suitable for text-only generation.
    """
    result = await call_minimax(
        system_prompt=system_prompt,
        user_message=user_message,
        api_key=api_key,
        trace_name=trace_name,
    )
    # call_minimax returns dict {"text": ..., "usage_metadata": ...}
    text = result["text"] if isinstance(result, dict) else result
    return extract_json_from_response(text)


# ===== Helper Functions =====


def _l3_enabled() -> bool:
    """L3 semantic review on by default. Set ENABLE_L3_REVIEW=false/0/no to disable."""
    return os.environ.get("ENABLE_L3_REVIEW", "true").lower() not in ("false", "0", "no")


def _find_skills_dir() -> Path:
    """Find the skills directory, checking source tree and PROJECT_ROOT env."""
    # Try source tree layout first
    source_dir = Path(__file__).parent.parent.parent / "skills"
    if source_dir.exists():
        return source_dir
    # Fall back to PROJECT_ROOT env var (set by backend for venv installs)
    project_root = os.environ.get("PROJECT_ROOT", "")
    if project_root:
        env_dir = Path(project_root) / "skills"
        if env_dir.exists():
            return env_dir
    return source_dir  # return default even if missing


def _load_skill_content(skill_name: str) -> str:
    """Load skill content from SKILL.md file."""
    skill_path = _find_skills_dir() / skill_name / "SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    return ""


def _load_review_skill(skill_name: str) -> str:
    """Load REVIEW.md content (Layer 3 semantic review criteria)."""
    review_path = _find_skills_dir() / skill_name / "REVIEW.md"
    if review_path.exists():
        return review_path.read_text()
    return ""


async def _run_semantic_review(
    skill_name: str,
    data: dict[str, Any],
    api_key: str | None = None,
) -> ReviewResult:
    """Execute Layer 3 semantic validation (AI-powered).

    Uses Claude to evaluate data quality based on defined criteria.
    """
    review_skill = _load_review_skill(skill_name)
    if not review_skill:
        # No REVIEW.md, skip L3
        return ReviewResult(passed=True, level=ReviewLevel.SEMANTIC, errors=[])

    # Build request
    system_prompt = f"""You are a quality reviewer for Etsy product data.
Your job is to evaluate the data against the semantic criteria provided.

{review_skill}

IMPORTANT: Respond ONLY with the exact format specified in the review criteria above.
Start your response with "SEMANTIC_REVIEW_RESULT: PASS" or "SEMANTIC_REVIEW_RESULT: FAIL"
"""

    user_message = f"""Please review the following data:

```json
{json.dumps(data, ensure_ascii=False, indent=2)}
```

Evaluate against ALL criteria in the review document and provide your assessment.
"""

    try:
        response = await call_claude(
            system_prompt=system_prompt,
            user_message=user_message,
            api_key=api_key,
            trace_name=f"L3 Review: {skill_name}",
        )

        # Parse response
        response_text = response["text"].strip()
        if "SEMANTIC_REVIEW_RESULT: PASS" in response_text:
            return ReviewResult(passed=True, level=ReviewLevel.SEMANTIC, errors=[])
        elif "SEMANTIC_REVIEW_RESULT: FAIL" in response_text:
            # Extract issues from response
            errors = []
            lines = response_text.split("\n")
            in_issues = False
            for line in lines:
                if "Issues found" in line or "issues:" in line.lower():
                    in_issues = True
                    continue
                if in_issues and line.strip().startswith("-"):
                    errors.append(line.strip()[1:].strip())
                if "Suggestions" in line:
                    in_issues = False

            return ReviewResult(
                passed=False,
                level=ReviewLevel.SEMANTIC,
                errors=errors if errors else ["Semantic review failed, see feedback"],
                feedback=response_text,
            )
        else:
            # Unclear response, treat as pass with warning
            return ReviewResult(
                passed=True,
                level=ReviewLevel.SEMANTIC,
                errors=[],
                feedback=f"L3 review response unclear: {response_text[:200]}",
            )
    except Exception as e:
        # On error, skip L3 (don't block on API issues)
        return ReviewResult(
            passed=True,
            level=ReviewLevel.SEMANTIC,
            errors=[],
            feedback=f"L3 review skipped due to error: {e}",
        )


def _build_retry_feedback(review: ReviewResult | None) -> str:
    """Build retry feedback message."""
    if not review or review.passed:
        return ""

    feedback_parts = []
    if review.errors:
        feedback_parts.append("Previous attempt failed with errors:")
        for error in review.errors:
            feedback_parts.append(f"  - {error}")
    if review.feedback:
        feedback_parts.append(f"\nAdditional feedback: {review.feedback}")

    return "\n".join(feedback_parts)


# ===== Agent Nodes =====


async def preprocess_node(state: ProductState) -> ProductState:
    """Preprocessing Agent node.

    Reads Excel data and images, generates product_data.json.
    """
    product_path = Path(state["product_path"])

    # Load skill
    skill_content = _load_skill_content("etsy-batch-preprocessing")

    # Build request
    request = PREPROCESS_PROMPT.format(
        product_id=state["product_id"],
        category=state["category"],
        excel_row=json.dumps(state["excel_row"], ensure_ascii=False),
        image_files=state["image_files"],
        product_path=state["product_path"],
    )

    # Add retry feedback
    retry_feedback = _build_retry_feedback(state.get("preprocessing_review"))
    if retry_feedback:
        request += f"\n\n{retry_feedback}"

    # Call Claude Agent (Preprocessing needs reliable JSON schema -- Claude passes first try)
    print(f"  🧠 Using Claude Sonnet (multimodal + cache, {len(state['image_files'])} images)")
    image_paths = None
    if state["image_files"] and str(product_path):
        image_paths = [product_path / f for f in state["image_files"]]

    result = await call_claude(
        system_prompt=skill_content,
        user_message=request,
        use_cache=True,
        images=image_paths,
        trace_name="Preprocess (Claude Vision)",
    )
    response = extract_json_from_response(result["text"])

    # Parse response and save file
    try:
        product_data = json.loads(response)
        output_file = product_path / "product_data.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(product_data, f, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pass  # Review node will handle this

    # Update state
    state["stage"] = "preprocessing"
    return state


async def strategy_node(state: ProductState) -> ProductState:
    """Image Strategy Agent node

    Analyzes product data and plans 10 strategic images.
    Uses Claude for reasoning (same as preprocess).
    """
    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Load skill
    skill_content = _load_skill_content("image-strategy")

    # Read product_data.json
    product_data_file = product_path / "product_data.json"
    try:
        with open(product_data_file, encoding="utf-8") as f:
            product_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        state["stage"] = "strategy"
        state["image_strategy"] = None
        return state

    # Build request
    category = product_data.get("category", "rings")
    request = STRATEGY_PROMPT.format(
        product_data_json=json.dumps(product_data, ensure_ascii=False, indent=2),
        category=category,
    )

    # Add retry feedback
    retry_feedback = _build_retry_feedback(state.get("strategy_review"))
    if retry_feedback:
        request += f"\n\n{retry_feedback}"

    # Call LLM with fallback (Strategy is text-only -- Kimi is cheaper, Claude as fallback)
    # V2 creative direction output is larger (~10 slots x creative_direction), need 16K tokens
    print("  🎯 Using Kimi (strategy, text-only)")
    result = await call_llm_with_fallback(
        system_prompt=skill_content,
        user_message=request,
        max_tokens=16384,
        use_cache=True,
        trace_name="Strategy",
    )
    provider = result.get("provider", "unknown")
    print(f"  ✓ Strategy provider: {provider}")
    response = extract_json_from_response(result["text"])

    # Parse and save
    try:
        strategy_data = json.loads(response)
        output_file = product_path / f"{product_id}_image_strategy.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(strategy_data, f, ensure_ascii=False, indent=2)

        state["image_strategy"] = strategy_data
    except json.JSONDecodeError:
        pass  # Review node will handle

    state["stage"] = "strategy"
    return state


async def strategy_review_node(state: ProductState) -> ProductState:
    """Strategy Review node — validates the image strategy.

    Layer 1 (Schema) + Layer 2 (Rules) validation.
    """
    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Read strategy file
    strategy_file = product_path / f"{product_id}_image_strategy.json"
    try:
        with open(strategy_file, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        state["strategy_review"] = ReviewResult(
            passed=False,
            level=ReviewLevel.SCHEMA,
            errors=[f"Failed to read image_strategy.json: {e}"],
        )
        state["stage"] = "strategy_review"
        state["retry_counts"]["strategy"] = state["retry_counts"].get("strategy", 0) + 1
        return state

    # Layer 1: Schema validation
    schema_result = validate_strategy_schema(data)
    if not schema_result.passed:
        print(f"  ✗ Strategy L1 Schema errors: {schema_result.errors}")
        state["strategy_review"] = schema_result
        state["stage"] = "strategy_review"
        state["retry_counts"]["strategy"] = state["retry_counts"].get("strategy", 0) + 1
        return state

    # Layer 2: Rules validation (pass category for pose feasibility)
    category = state.get("category")
    rules_result = validate_strategy_rules(data, category=category)
    if not rules_result.passed:
        print(f"  ✗ Strategy L2 Rules errors: {rules_result.errors}")
        state["strategy_review"] = rules_result
        state["stage"] = "strategy_review"
        state["retry_counts"]["strategy"] = state["retry_counts"].get("strategy", 0) + 1
        return state

    # Layer 3: Semantic review (only if L1+L2 pass and L3 is enabled)
    l3_active = _l3_enabled()
    if l3_active:
        l3_result = await _run_semantic_review("image-strategy", data)
        if not l3_result.passed:
            print(f"  ✗ Strategy L3 Semantic errors: {l3_result.errors}")
            state["strategy_review"] = l3_result
            state["stage"] = "strategy_review"
            state["retry_counts"]["strategy"] = state["retry_counts"].get("strategy", 0) + 1
            return state

    review_level = ReviewLevel.SEMANTIC if l3_active else ReviewLevel.RULES
    print(f"  ✓ Strategy review passed (L1 + L2{' + L3' if l3_active else ''})")
    state["strategy_review"] = ReviewResult(
        passed=True, level=review_level, errors=[]
    )
    state["stage"] = "strategy_review"
    return state


async def listing_node(state: ProductState) -> ProductState:
    """Listing Agent node.

    Reads product_data.json, generates Etsy listing.
    """
    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Read product_data.json
    product_data_file = product_path / "product_data.json"
    with open(product_data_file, encoding="utf-8") as f:
        product_data = json.load(f)

    # Load skill
    skill_content = _load_skill_content("etsy-listing-batch-generator")

    # Build request
    request = LISTING_PROMPT.format(
        product_data_json=json.dumps(product_data, ensure_ascii=False, indent=2),
        product_id=product_id,
    )

    # Add retry feedback
    retry_feedback = _build_retry_feedback(state.get("listing_review"))
    if retry_feedback:
        request += f"\n\n{retry_feedback}"

    # Call MiniMax Agent (Listing is text-only, MiniMax is cheaper)
    print("  🤖 Using MiniMax M2.5 (cost-effective)")
    response = await call_minimax_agent(
        system_prompt=skill_content,
        user_message=request,
        trace_name="Listing (MiniMax)",
    )

    # Parse response and save file
    try:
        listing_data = json.loads(response)
        output_file = product_path / f"{product_id}_Listing.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(listing_data, f, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pass  # Review node will handle this

    # Update state
    state["stage"] = "listing"
    return state


async def listing_fan_out_node(state: ProductState) -> dict:
    """Listing node for parallel execution in fan-out phase.

    Runs listing generation in parallel with prompt_nodes.
    Writes listing file to disk (side effect) and returns
    fan-out-compatible state update (empty prompt_results).
    """
    await listing_node(state)
    # Return empty prompt_results to merge cleanly with prompt fan-out reducer
    return {"prompt_results": []}


# ===== Reviewer Nodes =====

_ETSY_TAG_MAX_CHARS = 20


def _auto_fix_tags(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Auto-fix tags that exceed Etsy's 20-character limit.

    Truncates at word boundaries.  Returns (data, was_fixed).
    """
    tags = data.get("tags", "")
    if not isinstance(tags, str) or not tags:
        return data, False

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    fixed = False
    for i, tag in enumerate(tag_list):
        if len(tag) > _ETSY_TAG_MAX_CHARS:
            # Truncate at word boundary
            words = tag.split()
            truncated = ""
            for word in words:
                candidate = f"{truncated} {word}".strip() if truncated else word
                if len(candidate) <= _ETSY_TAG_MAX_CHARS:
                    truncated = candidate
                else:
                    break
            tag_list[i] = truncated or tag[:_ETSY_TAG_MAX_CHARS]
            fixed = True

    if fixed:
        data["tags"] = ", ".join(tag_list)
    return data, fixed


def _run_layered_review(
    data: dict[str, Any],
    schema_validator,
    rules_validator,
) -> ReviewResult:
    """Execute layered validation: Layer 1 (Schema) -> Layer 2 (Rules).

    Note: L3 (Semantic) is handled separately via _run_semantic_review()
    """
    # Layer 1: Schema validation
    schema_result = schema_validator(data)
    if not schema_result.passed:
        return schema_result

    # Layer 2: Rules validation
    rules_result = rules_validator(data)
    if not rules_result.passed:
        return rules_result

    # L1 + L2 passed
    return ReviewResult(passed=True, level=ReviewLevel.RULES, errors=[])


async def preprocess_review_node(
    state: ProductState,
    enable_l3: bool | None = None,
    api_key: str | None = None,
) -> ProductState:
    """Preprocessing Review node.

    Validates product_data.json.
    L1 (Schema) + L2 (Rules) always run.
    L3 (Semantic) controlled by ENABLE_L3_REVIEW env var (default: on).

    Args:
        state: Product state
        enable_l3: Explicit override for L3 toggle (None = use env var)
        api_key: Claude API key (required for L3)
    """
    product_path = Path(state["product_path"])

    # Read product_data.json
    product_data_file = product_path / "product_data.json"
    try:
        with open(product_data_file, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        state["preprocessing_review"] = ReviewResult(
            passed=False,
            level=ReviewLevel.SCHEMA,
            errors=[f"Failed to read product_data.json: {e}"],
        )
        state["stage"] = "preprocessing_review"
        return state

    # Execute layered validation (L1 + L2)
    review_result = _run_layered_review(
        data,
        validate_product_data_schema,
        validate_product_data_rules,
    )

    # L3 semantic validation (explicit override > env var, default: on)
    l3_active = enable_l3 if enable_l3 is not None else _l3_enabled()
    if review_result.passed and l3_active:
        l3_result = await _run_semantic_review(
            "etsy-batch-preprocessing", data, api_key
        )
        if not l3_result.passed:
            review_result = l3_result

    # Update retry count
    if not review_result.passed:
        state["retry_counts"]["preprocessing"] = state["retry_counts"].get("preprocessing", 0) + 1

    state["preprocessing_review"] = review_result
    state["stage"] = "preprocessing_review"
    return state


async def listing_review_node(
    state: ProductState,
    enable_l3: bool | None = None,
    api_key: str | None = None,
) -> ProductState:
    """Listing Review node.

    Validates Etsy listing.
    L1 (Schema) + L2 (Rules) always run.
    L3 (Semantic) controlled by ENABLE_L3_REVIEW env var (default: on).

    Args:
        state: Product state
        enable_l3: Explicit override for L3 toggle (None = use env var)
        api_key: Claude API key (required for L3)
    """
    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Read listing file
    listing_file = product_path / f"{product_id}_Listing.json"
    try:
        with open(listing_file, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        state["listing_review"] = ReviewResult(
            passed=False,
            level=ReviewLevel.SCHEMA,
            errors=[f"Failed to read listing: {e}"],
        )
        state["stage"] = "listing_review"
        return state

    # Auto-fix tags that exceed Etsy's 20-character limit by truncating
    # at word boundaries. This prevents repeated retry failures when the
    # AI generates tags like "moissanite engagement" (21 chars).
    data, tags_fixed = _auto_fix_tags(data)
    if tags_fixed:
        with open(listing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # Execute layered validation (L1 + L2)
    review_result = _run_layered_review(
        data,
        validate_listing_schema,
        validate_listing_rules,
    )

    # L3 semantic validation (explicit override > env var, default: on)
    # L3 is advisory only — log suggestions but never block the pipeline.
    # L1+L2 passing means the listing is structurally valid for Etsy.
    l3_active = enable_l3 if enable_l3 is not None else _l3_enabled()
    if review_result.passed and l3_active:
        l3_result = await _run_semantic_review(
            "etsy-listing-batch-generator", data, api_key
        )
        if not l3_result.passed:
            print(f"  ⚠️ L3 semantic suggestions (non-blocking): {l3_result.errors}")
            # Do NOT override review_result — L3 is advisory

    # Update retry count
    if not review_result.passed:
        state["retry_counts"]["listing"] = state["retry_counts"].get("listing", 0) + 1

    state["listing_review"] = review_result
    state["stage"] = "listing_review"
    return state


# ============================================================
# Image Generation Node
# ============================================================


@traceable(run_type="tool", name="Image Generation")
async def image_gen_node(
    state: ProductState,
    resolution: str = "4k",
    gemini_api_key: str | None = None,
) -> ProductState:
    """Generate product images.

    Uses Gemini API to generate images based on NanoBanana prompts.

    Args:
        state: Product state
        resolution: Image resolution (1k, 2k, 4k)
        gemini_api_key: Gemini API key
    """
    from etsy_listing_agent.image_generator import generate_images_for_product

    product_path = state["product_path"]
    product_id = state["product_id"]

    print(f"\n🎨 Generating images for {product_id}...")

    try:
        result = generate_images_for_product(
            product_path=product_path,
            product_id=product_id,
            resolution=resolution,
            api_key=gemini_api_key,
        )

        if result["success"]:
            state["stage"] = "image_gen_complete"
            state["image_gen_result"] = result
            print(f"✅ Generated {len(result['generated'])} images")
        else:
            state["stage"] = "image_gen_failed"
            state["image_gen_result"] = result
            print(f"❌ Image generation failed: {result.get('error', 'Unknown error')}")

    except Exception as e:
        state["stage"] = "image_gen_failed"
        state["image_gen_result"] = {"success": False, "error": str(e)}
        print(f"❌ Image generation error: {e}")

    return state


# ============================================================
# Prompt Node (Fan-Out Pattern)
# ============================================================

MAX_PROMPT_RETRIES = 2  # Exception-only retries (agent self-validates internally)


# ===== Agentic Tool Use for Prompt Node =====

SKILL_NAME = "jewelry-prompt-generator"


def _handle_read_reference(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute read_reference tool calls from the agentic loop."""
    if tool_name != "read_reference":
        return f"Unknown tool: {tool_name}"
    file_path = tool_input.get("file_path", "")
    ref_dir = _find_skills_dir() / SKILL_NAME / "references"
    full_path = (ref_dir / file_path).resolve()
    # Safety: ensure path stays within references/
    if not str(full_path).startswith(str(ref_dir.resolve())):
        return f"Invalid path: {file_path}"
    if full_path.exists():
        return full_path.read_text()
    return f"File not found: {file_path}"


def _make_prompt_tool_handler(
    direction: str, reference_anchor: str,
) -> Callable[[str, dict[str, Any]], str]:
    """Create a tool handler that handles both read_reference and validate_prompt.

    Uses closure to capture direction and reference_anchor for validation.
    """
    def handler(tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "read_reference":
            return _handle_read_reference(tool_name, tool_input)
        elif tool_name == "validate_prompt":
            prompt_text = tool_input.get("prompt_text", "")
            # Prepend anchor for full validation (agent generates without ANCHOR)
            if reference_anchor and "REFERENCE ANCHOR:" not in prompt_text:
                full_prompt = reference_anchor + "\n\n" + prompt_text
            else:
                full_prompt = prompt_text
            errors = _validate_prompt(full_prompt, direction)
            if not errors:
                return "PASS — All validation checks passed. Output your final prompt text now."
            return "FAILED — Fix these issues:\n" + "\n".join(f"- {e}" for e in errors) + "\n\nFix the issues above and output the corrected prompt."
        return f"Unknown tool: {tool_name}"
    return handler


def _list_available_references() -> list[str]:
    """List all reference files available in the skill's references/ directory.

    Returns relative paths from references/, e.g. 'pose-modules.md' or
    'style-series/series-3-chromatic-minimalism.md'.
    """
    ref_dir = _find_skills_dir() / SKILL_NAME / "references"
    if not ref_dir.exists():
        return []
    results = []
    for f in ref_dir.rglob("*.md"):
        results.append(str(f.relative_to(ref_dir)))
    return sorted(results)


def _format_selling_points(selling_points: list) -> str:
    """Format selling_points for prompt - handles both string and dict formats."""
    if not selling_points:
        return "handcrafted quality"

    points = []
    for sp in selling_points[:3]:
        if isinstance(sp, dict):
            points.append(sp.get("feature", str(sp)))
        else:
            points.append(str(sp))

    return ", ".join(points) if points else "handcrafted quality"


def _fix_anchor_length(prompt: str) -> str:
    """Auto-fix ANCHOR if it has more than 3 lines by condensing to standard format."""
    if "REFERENCE ANCHOR:" not in prompt:
        return prompt

    anchor_start = prompt.find("REFERENCE ANCHOR:")
    anchor_end = prompt.find("\n\n", anchor_start)
    if anchor_end == -1:
        anchor_end = prompt.find("SCENE CONTEXT:", anchor_start)
    if anchor_end == -1:
        return prompt

    anchor = prompt[anchor_start:anchor_end]
    lines = [line.strip() for line in anchor.split("\n") if line.strip()]

    if len(lines) <= 3:
        return prompt  # Already valid

    # Extract product type from first line
    first_line = lines[0]
    if "depicts" in first_line:
        product_type = first_line.split("depicts")[-1].strip().rstrip(".")
    else:
        product_type = "jewelry"

    # Create condensed 3-line ANCHOR
    fixed_anchor = f"""REFERENCE ANCHOR: The input image depicts {product_type}.
Maintain exact structural integrity, color palette, and material finish.
Do not alter the product's geometry. Rigid constraint."""

    return prompt[:anchor_start] + fixed_anchor + prompt[anchor_end:]


def _validate_prompt(prompt: str, direction: str) -> list[str]:
    """Validate prompt format. Returns list of errors."""
    errors = []
    prompt_lower = prompt.lower()

    # ANCHOR validation
    if "REFERENCE ANCHOR:" not in prompt:
        errors.append("Missing REFERENCE ANCHOR section")
        return errors

    # Check "Rigid constraint"
    if "rigid constraint" not in prompt_lower:
        errors.append("ANCHOR must contain 'Rigid constraint.'")

    # Check ANCHOR line count (≤3 lines)
    anchor_start = prompt.find("REFERENCE ANCHOR:")
    anchor_end = prompt.find("\n\n", anchor_start)
    if anchor_end != -1:
        anchor = prompt[anchor_start:anchor_end]
        lines = [line for line in anchor.split("\n") if line.strip()]
        if len(lines) > 3:
            errors.append(f"ANCHOR too long: {len(lines)} lines (max 3)")

    # Anti-AI realism check (skip for macro_detail and packaging)
    if direction not in ("macro_detail", "packaging"):
        has_realism = any(kw in prompt_lower for kw in ANTI_AI_KEYWORDS)
        if not has_realism:
            errors.append("Missing anti-AI realism modifiers (film grain, dust particles, etc.)")

    # Wearing banned keywords
    if direction in ("wearing_a", "wearing_b"):
        for kw in WEARING_BANNED:
            if kw in prompt_lower:
                errors.append(f"Wearing prompt has banned keyword: '{kw}'")
                break

    return errors


def _load_packaging_template() -> str:
    """Load the fixed packaging prompt template."""
    template_path = _find_skills_dir() / "image-strategy" / "packaging_template.txt"
    if template_path.exists():
        return template_path.read_text()
    return ""


@traceable(run_type="chain", name="Prompt Node")
async def prompt_node(state: dict) -> dict:
    """Generate a single NanoBanana prompt via agentic loop with tool use.

    The agent receives prompt config as system prompt and can dynamically read
    reference files (series guides, physics keywords, etc.) before generating.

    Typical flow (2 turns):
      Turn 1: Agent reasons about direction → parallel read_reference calls
      Turn 2: Agent uses loaded context → generates prompt text

    For packaging slot: uses fixed template (no model call).
    """
    direction = state["direction"]
    product_data = state["product_data"]
    product_id = state["product_id"]
    slot_info = state.get("slot_info", {})
    is_packaging = state.get("is_packaging", False)

    # Handle packaging slot with fixed template (no change)
    if is_packaging or direction == "packaging":
        template = _load_packaging_template()
        if template:
            product_type = product_data.get("category", "jewelry")
            product_size = product_data.get("product_size", {}).get("dimensions", "standard size")
            prompt_text = template.replace("{product_type}", product_type)
            prompt_text = prompt_text.replace("{product_size}", product_size)
            ref_anchor = product_data.get("reference_anchor", "")
            if ref_anchor and "REFERENCE ANCHOR:" in prompt_text:
                scene_idx = prompt_text.find("SCENE CONTEXT:")
                if scene_idx != -1:
                    prompt_text = ref_anchor + "\n\n" + prompt_text[scene_idx:]
            return {
                "prompt_results": [{
                    "direction": "packaging",
                    "prompt": prompt_text,
                    "success": True,
                    "error": None,
                    "cost_usd": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }]
            }
        else:
            print("  ⚠️ Packaging template not found, falling back to agentic generation")

    # ----- Agentic prompt generation -----
    import time as _time
    _node_start = _time.time()

    # System prompt = prompt generation config
    skill_content = _load_skill_content(SKILL_NAME)
    if not skill_content:
        skill_content = "You are a jewelry photography prompt generator."

    # Pre-written ANCHOR from preprocessing (Claude saw the images)
    reference_anchor = product_data.get("reference_anchor", "")

    # Direction description from strategy node (V3)
    description = "Product photography"
    if slot_info and slot_info.get("description"):
        description = slot_info["description"]

    slot_context = ""
    if slot_info and slot_info.get("rationale"):
        slot_context = f"\n- Strategic Rationale: {slot_info['rationale']}"

    # V2 Creative Direction block (from strategy node)
    creative_dir = slot_info.get("creative_direction", {}) if slot_info else {}
    creative_block = ""
    if creative_dir:
        creative_block = f"""
## Creative Direction (from strategy — follow this exactly)
- Style Series: {creative_dir.get('style_series', 'S3')}
- Pose: {creative_dir.get('pose') or 'none'}
- Scene Module: {creative_dir.get('scene_module') or 'none'}
- Mood: {creative_dir.get('mood', '')}
- Key Visual: {creative_dir.get('key_visual', '')}
"""

    earring_note = ""
    if product_data.get("category") == "earrings":
        design_type = product_data.get("earring_design_type", "unknown")
        earring_note = f"\n- Earring Design Type: {design_type} (read earring-angle-guide.md for angle rules)"

    # List available reference files for the agent
    available_refs = _list_available_references()
    refs_list = "\n".join(f"- {ref}" for ref in available_refs) if available_refs else "- (no references available)"

    # Build user message with agentic workflow instructions
    user_message = PROMPT_NODE_USER_MESSAGE.format(
        category=product_data.get('category', 'jewelry'),
        materials=', '.join(product_data.get('materials', ['unknown'])),
        style=product_data.get('style', 'classic'),
        dimensions=product_data.get('product_size', {}).get('dimensions', 'standard size'),
        selling_points=_format_selling_points(product_data.get('selling_points', [])),
        visual_features=json.dumps(product_data.get('visual_features', {}), ensure_ascii=False),
        earring_note=earring_note,
        direction=direction,
        description=description,
        slot_context=slot_context,
        creative_block=creative_block,
        reference_anchor=reference_anchor,
        refs_list=refs_list,
    )

    # Create closure-based tool handler (captures direction + anchor for validation)
    tool_handler = _make_prompt_tool_handler(direction, reference_anchor)

    # Retry loop: only retries on exceptions (agent self-validates internally)
    total_cost = 0.0
    total_input = 0
    total_output = 0
    result = None

    for attempt in range(MAX_PROMPT_RETRIES):
        print(f"  🤖 [{direction}] Agentic prompt generation (attempt {attempt + 1})")
        try:
            result = await agentic_loop(
                system_prompt=skill_content,
                user_message=user_message,
                tools=[READ_REFERENCE_TOOL, VALIDATE_PROMPT_TOOL],
                tool_handler=tool_handler,
                model="MiniMax-M2.5",
                max_tokens=2000,
                max_turns=10,
                trace_name=f"Prompt: {direction} (Agentic)",
            )
            total_cost += result["cost_usd"]
            total_input += result["usage_metadata"]["input_tokens"]
            total_output += result["usage_metadata"]["output_tokens"]

            # Check for API error or empty output
            if result.get("error") or not result["text"].strip():
                print(f"  ⚠️ [{direction}] Attempt {attempt + 1}: "
                      f"error={result.get('error')}, empty={not result['text'].strip()}")
                result = None
                continue

            break  # Got usable output
        except RuntimeError as e:
            print(f"  ❌ [{direction}] Attempt {attempt + 1} failed: {e}")
            result = None
            continue

    _node_elapsed = round(_time.time() - _node_start, 1)

    if result is None:
        print(f"  ⏱️ [{direction}] Failed after {_node_elapsed}s")
        return {
            "prompt_results": [{
                "direction": direction,
                "prompt": "",
                "success": False,
                "error": f"Failed after {MAX_PROMPT_RETRIES} attempts (agent errors)",
                "cost_usd": total_cost,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "elapsed_seconds": _node_elapsed,
            }]
        }

    prompt_text = result["text"].strip()

    # Strip any ANCHOR the model may have written despite instructions
    if "REFERENCE ANCHOR:" in prompt_text:
        scene_idx = prompt_text.find("SCENE CONTEXT:")
        if scene_idx != -1:
            prompt_text = prompt_text[scene_idx:]

    # Prepend the pre-written ANCHOR from preprocessing
    if reference_anchor:
        prompt_text = reference_anchor + "\n\n" + prompt_text

    # Safety net: external validation (just logging, agent should have self-validated)
    errors = _validate_prompt(prompt_text, direction)
    if errors:
        print(f"  ⚠️ [{direction}] Post-validation warnings (agent may have missed): {errors}")

    turns_used = result["usage_metadata"].get("turns", 0)
    print(f"  ⏱️ [{direction}] Done in {_node_elapsed}s, {turns_used} turns, ${total_cost:.4f}")

    # Prompt is successful as long as we have non-empty text.
    # Validation warnings are informational — they don't block the pipeline.
    has_prompt = bool(prompt_text.strip())

    return {
        "prompt_results": [{
            "direction": direction,
            "prompt": prompt_text,
            "success": has_prompt,
            "error": f"Validation warnings: {errors}" if errors else None,
            "cost_usd": total_cost,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "elapsed_seconds": _node_elapsed,
            "turns": turns_used,
        }]
    }


# ============================================================
# Prompt Aggregator Node (Fan-In)
# ============================================================


@traceable(run_type="tool", name="Prompt Aggregator")
def prompt_aggregator_node(state: dict) -> dict:
    """
    Collect prompt results from fan-out and save to JSON.

    Receives aggregated results from all 10 prompt_nodes.
    """
    product_id = state["product_id"]
    product_path = Path(state["product_path"])
    prompt_results = state.get("prompt_results", [])

    # Load product_data from file (not in state after fan-out)
    product_data_file = product_path / "product_data.json"
    try:
        with open(product_data_file, encoding="utf-8") as f:
            product_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        product_data = {}

    # Load strategy for slot metadata
    strategy_file = product_path / f"{product_id}_image_strategy.json"
    slot_map = {}
    if strategy_file.exists():
        try:
            with open(strategy_file, encoding="utf-8") as f:
                strategy = json.load(f)
            for s in strategy.get("slots", []):
                slot_map[s.get("type", "")] = s
        except (json.JSONDecodeError, KeyError):
            pass

    # Extract image filenames
    image_filenames = []
    for img in product_data.get("images", [])[:3]:
        if isinstance(img, dict) and "filename" in img:
            image_filenames.append(img["filename"])
        elif isinstance(img, str):
            image_filenames.append(img)

    # Build prompts array
    prompts_array = []
    successful = 0
    failed = 0
    total_cost = 0.0

    for i, result in enumerate(prompt_results, 1):
        total_cost += result.get("cost_usd", 0)

        direction = result["direction"]
        slot = slot_map.get(direction, {})

        # Packaging gets 4 reference images (3 product refs + packaging_box.jpg) if asset exists
        if direction == "packaging":
            base_refs = image_filenames or ["ref1.jpg", "ref2.jpg", "ref3.jpg"]
            packaging_asset = product_path / "packaging_box.jpg"
            if packaging_asset.exists():
                ref_images = base_refs + ["packaging_box.jpg"]
            else:
                ref_images = base_refs
        else:
            ref_images = image_filenames or ["ref1.jpg", "ref2.jpg", "ref3.jpg"]

        prompt_obj = {
            "index": i,
            "type": direction,
            "style_series": slot.get("creative_direction", {}).get("style_series", ""),
            "type_name": slot.get("description", direction.replace("_", " ").title()),
            "goal": slot.get("rationale", ""),
            "reference_images": ref_images,
            "prompt": result.get("prompt", ""),
        }
        prompts_array.append(prompt_obj)

        if result.get("success"):
            successful += 1
        else:
            failed += 1

    # Build output
    output_data = {
        "product_id": product_id,
        "category": product_data.get("category", ""),
        "style": product_data.get("style", ""),
        "materials": product_data.get("materials", []),
        "prompts": prompts_array,
    }

    # Save to file
    output_file = product_path / f"{product_id}_NanoBanana_Prompts.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"  📊 Aggregated: {successful} successful, {failed} failed, ${total_cost:.4f} total")

    return {
        **state,
        "nanobanana_success": failed == 0,
        "output_file": str(output_file),
        "total_cost": total_cost,
        "stage": "nanobanana_aggregated",
    }


# ============================================================
# NanoBanana Node Wrapper (CLI compatibility)
# ============================================================

@traceable(run_type="chain", name="NanoBanana Node")
async def nanobanana_node(state: ProductState) -> ProductState:
    """NanoBanana Agent wrapper for CLI compatibility.

    Orchestrates the fan-out pattern internally:
    1. Loads product_data.json and strategy (if exists)
    2. Runs prompt_node for each of 10 directions
    3. Aggregates results and saves to {product_id}_NanoBanana_Prompts.json
    """
    import asyncio

    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Load product_data.json
    product_data_file = product_path / "product_data.json"
    try:
        with open(product_data_file, encoding="utf-8") as f:
            product_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {
            **state,
            "stage": "nanobanana",
            "nanobanana_error": f"Failed to load product_data.json: {e}",
        }

    # Load strategy file if it exists (dynamic slots)
    strategy_file = product_path / f"{product_id}_image_strategy.json"
    if strategy_file.exists():
        with open(strategy_file, encoding="utf-8") as f:
            strategy = json.load(f)
        slots = strategy.get("slots", [])
        directions = [s["type"] for s in slots]
        slot_infos = {s["type"]: s for s in slots}
    else:
        directions = NANOBANANA_DIRECTIONS
        slot_infos = {}

    print(f"  🍌 Generating NanoBanana prompts for {product_id} ({len(directions)} directions)...")

    # Run all prompt_nodes in parallel
    tasks = []
    for direction in directions:
        prompt_state = {
            "direction": direction,
            "product_data": product_data,
            "product_id": product_id,
            "slot_info": slot_infos.get(direction, {}),
            "is_packaging": direction == "packaging",
        }
        tasks.append(prompt_node(prompt_state))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect prompt_results
    all_prompt_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            all_prompt_results.append({
                "direction": directions[i],
                "prompt": "",
                "success": False,
                "error": str(result),
                "cost_usd": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            })
        else:
            # result is dict with "prompt_results" key containing list
            all_prompt_results.extend(result.get("prompt_results", []))

    # Aggregate results
    agg_state = {
        "product_id": product_id,
        "product_path": str(product_path),
        "prompt_results": all_prompt_results,
    }
    agg_result = prompt_aggregator_node(agg_state)

    # Update main state
    return {
        **state,
        "stage": "nanobanana",
        "nanobanana_prompts": agg_result.get("output_file"),
        "nanobanana_success": agg_result.get("nanobanana_success", False),
    }


@traceable(run_type="tool", name="NanoBanana Review")
async def nanobanana_review_node(state: ProductState) -> ProductState:
    """NanoBanana Review node - validates generated prompts.

    3-layer validation:
    - Layer 1 (Schema): JSON structure validation
    - Layer 2 (Rules): Business logic validation
    - Layer 3 (Semantic): Optional AI quality review
    """
    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Load NanoBanana prompts file
    prompts_file = product_path / f"{product_id}_NanoBanana_Prompts.json"
    try:
        with open(prompts_file, encoding="utf-8") as f:
            prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return {
            **state,
            "stage": "nanobanana_review",
            "nanobanana_review": ReviewResult(
                passed=False,
                level=ReviewLevel.SCHEMA,
                errors=[f"Failed to load prompts file: {e}"],
            ),
            "retry_counts": {
                **state["retry_counts"],
                "nanobanana": state["retry_counts"]["nanobanana"] + 1,
            },
        }

    # Layer 1: Schema validation (returns ReviewResult)
    schema_result = validate_nanobanana_schema(prompts_data)
    if not schema_result.passed:
        print(f"  ✗ L1 Schema errors: {schema_result.errors}")
        return {
            **state,
            "stage": "nanobanana_review",
            "nanobanana_review": schema_result,
            "retry_counts": {
                **state["retry_counts"],
                "nanobanana": state["retry_counts"]["nanobanana"] + 1,
            },
        }

    # Layer 2: Rules validation (returns ReviewResult)
    rules_result = validate_nanobanana_rules(prompts_data)
    if not rules_result.passed:
        print(f"  ✗ L2 Rules errors: {rules_result.errors}")
        return {
            **state,
            "stage": "nanobanana_review",
            "nanobanana_review": rules_result,
            "retry_counts": {
                **state["retry_counts"],
                "nanobanana": state["retry_counts"]["nanobanana"] + 1,
            },
        }

    # Layer 3: Semantic review (only if L1+L2 pass and L3 is enabled)
    l3_active = _l3_enabled()
    if l3_active:
        l3_result = await _run_semantic_review("jewelry-prompt-generator", prompts_data)
        if not l3_result.passed:
            print(f"  ✗ NanoBanana L3 Semantic errors: {l3_result.errors}")
            return {
                **state,
                "stage": "nanobanana_review",
                "nanobanana_review": l3_result,
                "retry_counts": {
                    **state["retry_counts"],
                    "nanobanana": state["retry_counts"]["nanobanana"] + 1,
                },
            }

    review_level = ReviewLevel.SEMANTIC if l3_active else ReviewLevel.RULES
    print(f"  ✓ NanoBanana review passed (L1 + L2{' + L3' if l3_active else ''})")

    return {
        **state,
        "stage": "nanobanana_review",
        "nanobanana_review": ReviewResult(
            passed=True,
            level=review_level,
            errors=[],
        ),
    }
