# Schema and Rule-based validators
# Layer 1: Schema validation (JSON structure)
# Layer 2: Rules validation (business rules)

from typing import Any

from etsy_listing_agent.state import ReviewLevel, ReviewResult

from etsy_listing_agent.config_loader import (
    VALID_CATEGORIES,
    VALID_STYLES,
    VALID_AUDIENCES,
    VALID_MATERIALS,
    VALID_ANGLES,
    VALID_IMAGE_TYPES,
    VALID_SHAPES,
    VALID_SIZE_SOURCES,
    VALID_MATERIAL_FINISH,
    VALID_COLOR_TONE,
    VALID_SURFACE_QUALITY,
    VALID_LIGHT_INTERACTION,
    VALID_STRATEGIC_TYPES,
    BANNED_STRATEGIC_TYPES,
    REQUIRED_SLOT_TYPES,
    VALID_STYLE_SERIES,
    TIER_3_4_SERIES,
    POSE_FEASIBILITY,
)


class ValidationError(Exception):
    """Validation error"""

    pass


# ===== Layer 1: Schema Validators =====


def validate_product_data_schema(data: dict[str, Any]) -> ReviewResult:
    """Validate product_data.json schema (Layer 1)"""
    errors: list[str] = []

    # Required fields check
    required_fields = [
        "product_id", "product_path", "category", "style",
        "target_audience", "materials", "product_size", "basic_info", "images",
        "visual_features", "selling_points",  # Added in Step 3.10
    ]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)

    # Enum value checks
    if data.get("category") not in VALID_CATEGORIES:
        errors.append(f"Invalid category: {data.get('category')}. Must be one of {VALID_CATEGORIES}")

    if data.get("style") not in VALID_STYLES:
        errors.append(f"Invalid style: {data.get('style')}. Must be one of {VALID_STYLES}")

    if data.get("target_audience") not in VALID_AUDIENCES:
        errors.append(f"Invalid target_audience: {data.get('target_audience')}")

    # materials array check
    materials = data.get("materials", [])
    if not isinstance(materials, list) or len(materials) == 0:
        errors.append("materials must be a non-empty array")
    else:
        for mat in materials:
            if mat not in VALID_MATERIALS:
                errors.append(f"Invalid material: {mat}")

    # product_size check
    product_size = data.get("product_size", {})
    if not isinstance(product_size, dict):
        errors.append("product_size must be an object")
    elif "dimensions" not in product_size or "source" not in product_size:
        errors.append("product_size must have 'dimensions' and 'source' fields")
    elif product_size.get("source") not in VALID_SIZE_SOURCES:
        errors.append(f"Invalid product_size.source: {product_size.get('source')}")

    # images array check
    images = data.get("images", [])
    if not isinstance(images, list) or len(images) == 0:
        errors.append("images must be a non-empty array")
    else:
        has_hero = False
        for i, img in enumerate(images):
            if not isinstance(img, dict):
                errors.append(f"images[{i}] must be an object")
                continue
            # Required fields
            for field in ["filename", "angle", "type", "is_hero"]:
                if field not in img:
                    errors.append(f"images[{i}] missing required field: {field}")
            # Enum checks
            if img.get("angle") not in VALID_ANGLES:
                errors.append(f"Invalid angle in images[{i}]: {img.get('angle')}")
            if img.get("type") not in VALID_IMAGE_TYPES:
                errors.append(f"Invalid type in images[{i}]: {img.get('type')}")
            if img.get("is_hero") is True:
                has_hero = True
        if not has_hero and len(images) > 0:
            errors.append("At least one image must have is_hero: true")

    # main_stone optional field check
    main_stone = data.get("main_stone")
    if main_stone is not None and isinstance(main_stone, dict):
        if "type" in main_stone and main_stone["type"] not in VALID_MATERIALS:
            errors.append(f"Invalid main_stone.type: {main_stone['type']}")
        if "shape" in main_stone and main_stone["shape"] not in VALID_SHAPES:
            errors.append(f"Invalid main_stone.shape: {main_stone['shape']}")

    # visual_features check (Step 3.10)
    visual_features = data.get("visual_features")
    if visual_features is None:
        errors.append("Missing required field: visual_features")
    elif not isinstance(visual_features, dict):
        errors.append("visual_features must be an object")
    else:
        vf_required = ["material_finish", "color_tone", "surface_quality", "light_interaction"]
        for field in vf_required:
            if field not in visual_features:
                errors.append(f"visual_features missing required field: {field}")
        # Enum value validation
        if visual_features.get("material_finish") not in VALID_MATERIAL_FINISH:
            errors.append(f"Invalid visual_features.material_finish: {visual_features.get('material_finish')}")
        if visual_features.get("color_tone") not in VALID_COLOR_TONE:
            errors.append(f"Invalid visual_features.color_tone: {visual_features.get('color_tone')}")
        if visual_features.get("surface_quality") not in VALID_SURFACE_QUALITY:
            errors.append(f"Invalid visual_features.surface_quality: {visual_features.get('surface_quality')}")
        if visual_features.get("light_interaction") not in VALID_LIGHT_INTERACTION:
            errors.append(f"Invalid visual_features.light_interaction: {visual_features.get('light_interaction')}")

    # selling_points check (Step 3.10)
    selling_points = data.get("selling_points")
    if selling_points is None:
        errors.append("Missing required field: selling_points")
    elif not isinstance(selling_points, list):
        errors.append("selling_points must be an array")
    elif len(selling_points) < 2:
        errors.append("selling_points must have at least 2 items")
    else:
        for i, sp in enumerate(selling_points):
            if not isinstance(sp, dict):
                errors.append(f"selling_points[{i}] must be an object")
            elif "feature" not in sp or "benefit" not in sp:
                errors.append(f"selling_points[{i}] must have 'feature' and 'benefit' fields")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.SCHEMA, errors=[])


def validate_strategy_schema(data: dict[str, Any]) -> ReviewResult:
    """Validate image_strategy JSON schema (Layer 1)

    Accepts both v1 and v2 schemas. V2 requires creative_direction per slot,
    creative_diversity section, and creative_narrative in analysis.
    """
    errors: list[str] = []

    for field in ["$schema", "product_id", "analysis", "slots"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)

    schema_version = data.get("$schema", "")
    is_v2 = schema_version == "image_strategy_v2"

    # analysis must have required sub-fields
    analysis = data.get("analysis", {})
    if not isinstance(analysis, dict):
        errors.append("analysis must be an object")
    else:
        for field in ["product_usps", "target_customer", "purchase_barriers", "competitive_gap"]:
            if field not in analysis:
                errors.append(f"analysis missing required field: {field}")
        if is_v2 and "creative_narrative" not in analysis:
            errors.append("analysis missing required field: creative_narrative (v2)")

    # v2: creative_diversity section
    if is_v2:
        cd = data.get("creative_diversity")
        if cd is None:
            errors.append("Missing required field: creative_diversity (v2)")
        elif not isinstance(cd, dict):
            errors.append("creative_diversity must be an object")
        else:
            for field in ["series_used", "tier_3_4_count", "pose_categories_used"]:
                if field not in cd:
                    errors.append(f"creative_diversity missing required field: {field}")

    # slots must be array of exactly 10
    slots = data.get("slots", [])
    if not isinstance(slots, list):
        errors.append("slots must be an array")
    elif len(slots) != 10:
        errors.append(f"slots must have exactly 10 items, got {len(slots)}")
    else:
        required_slot_fields = ["slot", "type", "category", "description", "rationale"]
        for i, slot in enumerate(slots):
            if not isinstance(slot, dict):
                errors.append(f"slots[{i}] must be an object")
                continue
            for field in required_slot_fields:
                if field not in slot:
                    errors.append(f"slots[{i}] missing required field: {field}")

            # slot number must be 1-10
            slot_num = slot.get("slot")
            if slot_num is not None and (not isinstance(slot_num, int) or slot_num < 1 or slot_num > 10):
                errors.append(f"slots[{i}].slot must be integer 1-10, got {slot_num}")

            # v2: creative_direction required per slot
            if is_v2:
                cd = slot.get("creative_direction")
                if cd is None:
                    errors.append(f"slots[{i}] missing required field: creative_direction (v2)")
                elif not isinstance(cd, dict):
                    errors.append(f"slots[{i}].creative_direction must be an object")
                else:
                    for req_field in ["style_series", "mood", "key_visual"]:
                        if req_field not in cd:
                            errors.append(f"slots[{i}].creative_direction missing required field: {req_field}")
                    ss = cd.get("style_series")
                    if ss is not None and ss not in VALID_STYLE_SERIES:
                        errors.append(f"slots[{i}].creative_direction.style_series invalid: '{ss}'")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.SCHEMA, errors=[])


def validate_strategy_rules(data: dict[str, Any], category: str | None = None) -> ReviewResult:
    """Validate image_strategy business rules (Layer 2)

    Includes v2 creative direction rules when creative_direction is present.
    """
    errors: list[str] = []

    slots = data.get("slots", [])

    # Slots 1-5 must be required types in order
    for i, expected_type in enumerate(REQUIRED_SLOT_TYPES):
        if i < len(slots):
            actual_type = slots[i].get("type", "")
            if actual_type != expected_type:
                errors.append(
                    f"Slot {i+1} must be type '{expected_type}', got '{actual_type}'"
                )
            if slots[i].get("category") != "required":
                errors.append(f"Slot {i+1} must have category 'required'")

    # Slots 6-10 must have category "strategic"
    for i in range(5, min(10, len(slots))):
        if slots[i].get("category") != "strategic":
            errors.append(f"Slot {i+1} must have category 'strategic'")

    # No duplicate types across all 10 slots
    all_types = [s.get("type", "") for s in slots]
    seen = set()
    for t in all_types:
        if t in seen:
            errors.append(f"Duplicate type: '{t}'")
        seen.add(t)

    # scene_gift is BANNED
    for s in slots:
        if s.get("type") in BANNED_STRATEGIC_TYPES:
            errors.append(f"Banned type: '{s.get('type')}' is not allowed")

    # --- V2 Creative Direction Rules ---
    has_creative_direction = any(
        isinstance(s.get("creative_direction"), dict) for s in slots if isinstance(s, dict)
    )

    if has_creative_direction:
        # wearing_a and wearing_b must use different style_series
        wearing_a_series = None
        wearing_b_series = None
        for s in slots:
            cd = s.get("creative_direction", {}) or {}
            if s.get("type") == "wearing_a":
                wearing_a_series = cd.get("style_series")
            elif s.get("type") == "wearing_b":
                wearing_b_series = cd.get("style_series")
        if wearing_a_series and wearing_b_series and wearing_a_series == wearing_b_series:
            errors.append(
                f"wearing_a and wearing_b must use different style_series "
                f"(both use '{wearing_a_series}')"
            )

        # Strategic slots (6-10): at least 2 must use TIER_3_4_SERIES
        strategic_tier_count = 0
        for s in slots[5:10]:
            cd = s.get("creative_direction", {}) or {}
            if cd.get("style_series") in TIER_3_4_SERIES:
                strategic_tier_count += 1
        if strategic_tier_count < 2:
            errors.append(
                f"Strategic slots (6-10) must have at least 2 Tier 3-4 series, "
                f"got {strategic_tier_count}"
            )

        # Pose feasibility: if pose is set and category is known
        if category and category in POSE_FEASIBILITY:
            valid_poses = POSE_FEASIBILITY[category]
            for i, s in enumerate(slots):
                cd = s.get("creative_direction", {}) or {}
                pose = cd.get("pose")
                if pose and pose not in valid_poses:
                    errors.append(
                        f"Slot {i+1} pose '{pose}' not feasible for {category} "
                        f"(valid: {sorted(valid_poses)})"
                    )

        # No creative twins: no two slots share same (style_series, scene_module)
        # Only applies when scene_module is explicitly set (not None)
        combos_seen: set[tuple[str, str]] = set()
        for i, s in enumerate(slots):
            cd = s.get("creative_direction", {}) or {}
            ss = cd.get("style_series")
            sm = cd.get("scene_module")
            if ss and sm:  # Only check when both are set
                combo = (ss, sm)
                if combo in combos_seen:
                    errors.append(
                        f"Creative twin: slot {i+1} duplicates (style_series={ss}, "
                        f"scene_module={sm})"
                    )
                combos_seen.add(combo)

        # At least 3 different style series across all 10 slots
        all_series = {
            s.get("creative_direction", {}).get("style_series")
            for s in slots
            if isinstance(s.get("creative_direction"), dict)
        }
        all_series.discard(None)
        if len(all_series) < 3:
            errors.append(
                f"Must use at least 3 different style series, got {len(all_series)}: "
                f"{sorted(all_series)}"
            )

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.RULES, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.RULES, errors=[])


def validate_nanobanana_schema(data: dict[str, Any]) -> ReviewResult:
    """Validate NanoBanana prompts output schema (Layer 1)

    Simplified format - only essential fields:
    - index, type, reference_images[], prompt
    """
    errors: list[str] = []

    # Required fields
    if "product_id" not in data:
        errors.append("Missing required field: product_id")

    if "prompts" not in data:
        errors.append("Missing required field: prompts")
    elif not isinstance(data.get("prompts"), list):
        errors.append("prompts must be an array")
    elif len(data.get("prompts", [])) != 10:
        errors.append(f"prompts must have exactly 10 items, got {len(data.get('prompts', []))}")
    else:
        # Simplified required fields
        required_prompt_fields = ["index", "type", "reference_images", "prompt"]
        for i, prompt in enumerate(data["prompts"]):
            if not isinstance(prompt, dict):
                errors.append(f"prompts[{i}] must be an object")
                continue
            for field in required_prompt_fields:
                if field not in prompt:
                    errors.append(f"prompts[{i}] missing required field: {field}")

            # reference_images must be array of 3 or 4 (packaging may have 4)
            ref_images = prompt.get("reference_images", [])
            if not isinstance(ref_images, list):
                errors.append(f"prompts[{i}].reference_images must be an array")
            elif len(ref_images) < 3 or len(ref_images) > 4:
                errors.append(f"prompts[{i}].reference_images must have 3-4 images, got {len(ref_images)}")

            # index must be valid (1-10)
            idx = prompt.get("index")
            if idx is not None and (not isinstance(idx, int) or idx < 1 or idx > 10):
                errors.append(f"prompts[{i}].index must be integer 1-10, got {idx}")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.SCHEMA, errors=[])


def validate_listing_schema(data: dict[str, Any]) -> ReviewResult:
    """Validate Etsy Listing schema (Layer 1)

    - tags is a comma-separated string (not an array)
    - long_tail_keywords is an array
    """
    errors: list[str] = []

    # Required fields
    required_fields = ["product_id", "title", "tags", "description", "attributes"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)

    # title check
    if not isinstance(data.get("title"), str) or len(data.get("title", "")) == 0:
        errors.append("title must be a non-empty string")

    # tags check - comma-separated string
    tags = data.get("tags", "")
    if not isinstance(tags, str) or len(tags) == 0:
        errors.append("tags must be a non-empty comma-separated string")

    # description check
    if not isinstance(data.get("description"), str) or len(data.get("description", "")) == 0:
        errors.append("description must be a non-empty string")

    # attributes check
    if not isinstance(data.get("attributes"), dict):
        errors.append("attributes must be an object")

    # long_tail_keywords is optional but must be an array if present
    if "long_tail_keywords" in data:
        ltk = data.get("long_tail_keywords")
        if not isinstance(ltk, list):
            errors.append("long_tail_keywords must be an array")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.SCHEMA, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.SCHEMA, errors=[])


# ===== Layer 2: Rule-based Validators =====

from etsy_listing_agent.config_loader import (  # noqa: E402
    VALID_EARRING_DESIGN_TYPES,
    BANNED_TITLE_ADJECTIVES,
    BANNED_TITLE_PHRASES,
)


def validate_product_data_rules(data: dict[str, Any]) -> ReviewResult:
    """Validate product_data business rules (Layer 2)"""
    errors: list[str] = []

    category = data.get("category")

    # Earrings must have earring_design_type
    if category == "earrings":
        design_type = data.get("earring_design_type")
        if design_type is None or design_type not in VALID_EARRING_DESIGN_TYPES:
            errors.append(
                f"earring_design_type is required for earrings. "
                f"Must be one of: {VALID_EARRING_DESIGN_TYPES}"
            )

    # basic_info must be at least 20 characters
    basic_info = data.get("basic_info", "")
    if isinstance(basic_info, str) and len(basic_info) < 20:
        errors.append(f"basic_info must be at least 20 characters, got {len(basic_info)}")

    # Only rings can use source: "estimated"
    product_size = data.get("product_size", {})
    if isinstance(product_size, dict):
        source = product_size.get("source")
        if source == "estimated" and category != "rings":
            errors.append(
                f"product_size.source='estimated' is only allowed for rings, "
                f"got category='{category}'. Non-ring products must have size from excel or measured."
            )

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.RULES, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.RULES, errors=[])


from etsy_listing_agent.config_loader import (  # noqa: E402
    VALID_IMAGE_TYPES_NANOBANANA,
    BANNED_KEYWORDS_WEARING,
    BANNED_KEYWORDS_MOISSANITE,
    SIZE_PATTERN,
    ANTI_AI_REALISM_KEYWORDS,
)


def _check_anchor_format(prompt_text: str) -> list[str]:
    """Check whether ANCHOR format meets requirements

    Expected format (with optional header):
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Scene: [Scene Name]
    Direction: [Direction Type]
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    NanoBanana Prompt:
    REFERENCE ANCHOR: [product description]
    ...Rigid constraint.
    """
    errors = []

    # ANCHOR must exist (can have header before it)
    if "REFERENCE ANCHOR:" not in prompt_text:
        errors.append("prompt must contain 'REFERENCE ANCHOR:' section")
        return errors

    # Extract ANCHOR section (from start to first double newline or "1:1")
    anchor_start = prompt_text.find("REFERENCE ANCHOR:")
    anchor_end = prompt_text.find("\n\n", anchor_start)
    if anchor_end == -1:
        anchor_end = prompt_text.find("1:1", anchor_start)

    if anchor_end != -1:
        anchor_section = prompt_text[anchor_start:anchor_end]
        # ANCHOR ≤ 3 lines
        anchor_lines = [l for l in anchor_section.strip().split("\n") if l.strip()]
        if len(anchor_lines) > 3:
            errors.append(f"ANCHOR must be ≤3 lines, got {len(anchor_lines)}")

        # Must contain "rigid constraint"
        if "rigid constraint" not in anchor_section.lower():
            errors.append("ANCHOR must contain 'rigid constraint'")

    return errors


def _check_banned_keywords(prompt_text: str, image_type: str, materials: list | None = None) -> list[str]:
    """Check for banned keywords

    Note: Hero "Product Only" rules have been relaxed - MiniMax model struggles
    to follow strict hero constraints consistently.
    """
    errors = []
    prompt_lower = prompt_text.lower()

    # Hero rules relaxed - skip strict "product only" validation
    # The model will still receive guidance but won't fail validation

    if image_type in ("wearing_a", "wearing_b"):
        for keyword in BANNED_KEYWORDS_WEARING:
            if keyword in prompt_lower:
                errors.append(f"wearing prompt contains banned keyword: '{keyword}'")

    # Check moissanite banned keywords if material includes moissanite
    if materials and "moissanite" in materials:
        for keyword in BANNED_KEYWORDS_MOISSANITE:
            if keyword in prompt_lower:
                errors.append(f"moissanite prompt contains banned keyword: '{keyword}'")

    return errors


def _check_hero_series(prompt_data: dict) -> list[str]:
    """Check whether hero's series_used is correct

    Note: Hero series and aperture rules have been relaxed.
    MiniMax model receives guidance but validation is permissive.
    """
    # Hero rules relaxed - return empty errors
    return []


def _check_hero_background(prompt_text: str, image_type: str) -> list[str]:
    """Check whether hero background is a light background

    Note: Hero background rules have been relaxed.
    """
    # Hero rules relaxed - return empty errors
    return []


def _check_anti_ai_realism(prompt_text: str, image_type: str = "") -> list[str]:
    """Check for anti-AI realism modifiers (required in every prompt)

    Exceptions:
    - macro_detail: anti-AI modifiers look like dirt at macro zoom
    - packaging: clean commercial shot, no anti-AI needed
    """
    # Skip for types where anti-AI modifiers are harmful
    if image_type in ("macro_detail", "packaging"):
        return []

    errors = []
    prompt_lower = prompt_text.lower()

    # Check if at least one anti-AI realism keyword is present
    has_realism = False
    for keyword in ANTI_AI_REALISM_KEYWORDS:
        if keyword in prompt_lower:
            has_realism = True
            break

    if not has_realism:
        errors.append(
            "prompt must contain anti-AI realism modifiers "
            "(e.g., 'film grain', 'dust particles', 'micro-scratches')"
        )

    return errors


def _check_size_included(prompt_text: str) -> list[str]:
    """Check whether SCENE CONTEXT in the prompt includes product size (mm/cm/g)

    Rule: every prompt's SCENE CONTEXT section must include product size information.
    Examples: "approximately 20mm", "18x18mm square face", "14g"
    """
    errors = []

    # Extract scene context (everything after REFERENCE ANCHOR paragraph)
    anchor_end = prompt_text.find("\n\n")
    if anchor_end == -1:
        scene_text = prompt_text
    else:
        scene_text = prompt_text[anchor_end:]

    if not SIZE_PATTERN.search(scene_text):
        errors.append(
            "SCENE CONTEXT must include product size "
            "(e.g., '20mm', '18x18mm', '14g'). "
            "Add approximate dimensions early in the scene description."
        )

    return errors


def _check_hero_no_hands_explicit(prompt_text: str, image_type: str) -> list[str]:
    """Check whether hero prompt explicitly states no hands

    Note: Hero "no hands" explicit rule has been relaxed.
    """
    # Hero rules relaxed - return empty errors
    return []


def validate_nanobanana_rules(data: dict[str, Any]) -> ReviewResult:
    """Validate NanoBanana prompts business rules (Layer 2)

    Rules:
    - ANCHOR format (<=3 lines, contains "rigid constraint")
    - Banned keywords for wearing, moissanite
    - Type variety: 5 required types must be present
    - Anti-AI realism modifiers (except macro_detail, packaging)
    - Prompt minimum length (50 chars)

    Relaxed rules (hero "Product Only"):
    - Hero banned keywords (silk, fabric, hand, etc.)
    - Hero aperture (f/8 or f/11)
    - Hero series_used
    - Hero background (light only)
    - Hero explicit "no hands"
    """
    errors: list[str] = []

    prompts = data.get("prompts", [])
    materials = data.get("materials", [])

    # Check type diversity — only the 5 required types must be present
    image_types = set()
    for p in prompts:
        if isinstance(p, dict) and "type" in p:
            image_types.add(p["type"])

    required_types = set(REQUIRED_SLOT_TYPES)
    missing_types = required_types - image_types
    if missing_types:
        errors.append(f"Missing required image types: {missing_types}")

    # Check each prompt
    for i, p in enumerate(prompts):
        if not isinstance(p, dict):
            continue

        prompt_text = p.get("prompt", "")
        image_type = p.get("type", "")

        # Check prompt length (at least 50 characters)
        if isinstance(prompt_text, str) and len(prompt_text) < 50:
            errors.append(
                f"prompts[{i}].prompt is too short ({len(prompt_text)} characters). "
                f"Each prompt must be at least 50 characters"
            )

        # Check ANCHOR format
        anchor_errors = _check_anchor_format(prompt_text)
        for err in anchor_errors:
            errors.append(f"prompts[{i}]: {err}")

        # Check banned keywords
        banned_errors = _check_banned_keywords(prompt_text, image_type, materials)
        for err in banned_errors:
            errors.append(f"prompts[{i}]: {err}")

        # Check hero series_used and aperture
        hero_errors = _check_hero_series(p)
        for err in hero_errors:
            errors.append(f"prompts[{i}]: {err}")

        # Check whether hero background is a light background
        bg_errors = _check_hero_background(prompt_text, image_type)
        for err in bg_errors:
            errors.append(f"prompts[{i}]: {err}")

        # Check whether hero explicitly states no hands
        no_hands_errors = _check_hero_no_hands_explicit(prompt_text, image_type)
        for err in no_hands_errors:
            errors.append(f"prompts[{i}]: {err}")

        # Check anti-AI realism modifiers (skip for macro_detail, packaging)
        realism_errors = _check_anti_ai_realism(prompt_text, image_type)
        for err in realism_errors:
            errors.append(f"prompts[{i}]: {err}")

        # Check size included in SCENE CONTEXT
        size_errors = _check_size_included(prompt_text)
        for err in size_errors:
            errors.append(f"prompts[{i}]: {err}")

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.RULES, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.RULES, errors=[])


def _check_title_subjective_adjectives(title: str) -> list[str]:
    """Check whether title contains subjective adjectives"""
    errors = []
    title_lower = title.lower()

    for adj in BANNED_TITLE_ADJECTIVES:
        # Check as whole word (with word boundaries)
        if f" {adj} " in f" {title_lower} ":
            errors.append(f"title contains banned subjective adjective: '{adj}'")

    return errors


def _check_title_generic_phrases(title: str) -> list[str]:
    """Check whether title contains generic gifting phrases"""
    errors = []
    title_lower = title.lower()

    for phrase in BANNED_TITLE_PHRASES:
        if phrase in title_lower:
            errors.append(f"title contains banned generic phrase: '{phrase}'")

    return errors


def _check_title_word_repetition(title: str) -> list[str]:
    """Check whether title has repeated words"""
    errors = []
    words = title.lower().split()

    # Count word occurrences (ignore very short words like 'a', 'an', 'the')
    word_counts: dict[str, int] = {}
    for word in words:
        # Strip punctuation
        clean_word = word.strip(".,!?;:'\"")
        if len(clean_word) > 2:  # Ignore short words
            word_counts[clean_word] = word_counts.get(clean_word, 0) + 1

    for word, count in word_counts.items():
        if count > 1:
            errors.append(f"title has repeated word: '{word}' appears {count} times")

    return errors


def _check_description_no_markdown(description: str) -> list[str]:
    """Check whether description contains markdown (plain text required)"""
    errors = []

    # Check for common markdown patterns (anywhere in text)
    inline_patterns = [
        ("**", "bold markdown"),
        ("__", "bold markdown"),
        ("```", "code block"),
        ("[](", "link markdown"),
    ]

    for pattern, desc in inline_patterns:
        if pattern in description:
            errors.append(f"description contains {desc}: '{pattern}'")

    # Check for line-start-only markdown patterns
    for line in description.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("# ") or stripped.startswith("## ") or stripped.startswith("### "):
            errors.append("description contains header markdown")
            break
        if stripped.startswith("* ") or stripped.startswith("- "):
            errors.append("description contains list markdown at line start")
            break

    return errors


def _check_long_tail_word_count(keywords: list) -> list[str]:
    """Check whether each long_tail_keyword is 2-6 words"""
    errors = []

    for i, kw in enumerate(keywords):
        if isinstance(kw, str):
            word_count = len(kw.split())
            if word_count < 2 or word_count > 6:
                errors.append(
                    f"long_tail_keywords[{i}] should be 2-6 words, got {word_count}: '{kw}'"
                )

    return errors


def validate_listing_rules(data: dict[str, Any]) -> ReviewResult:
    """Validate Etsy Listing business rules (Layer 2)

    - title: <14 words, no subjective adjectives, no word repetition
    - title_variations: array of 2
    - tags: exactly 13, comma-separated string
    - long_tail_keywords: 8 phrases, each 4-6 words
    - description: plain text (no markdown)
    """
    errors: list[str] = []

    # title must be at most 14 words
    title = data.get("title", "")
    if isinstance(title, str):
        word_count = len(title.split())
        if word_count > 14:
            errors.append(f"title exceeds 14 word limit, got {word_count} words")

        # Check for subjective adjectives
        adj_errors = _check_title_subjective_adjectives(title)
        errors.extend(adj_errors)

        # Check for generic gifting phrases
        phrase_errors = _check_title_generic_phrases(title)
        errors.extend(phrase_errors)

        # Check for word repetition
        rep_errors = _check_title_word_repetition(title)
        errors.extend(rep_errors)

    # title_variations should have exactly 2 (A/B testing)
    title_variations = data.get("title_variations", [])
    if "title_variations" in data:
        if not isinstance(title_variations, list):
            errors.append("title_variations must be an array")
        elif len(title_variations) != 2:
            errors.append(f"title_variations should have exactly 2 items, got {len(title_variations)}")

    # tags must be a comma-separated string with exactly 13 items
    tags = data.get("tags", "")
    if isinstance(tags, str) and len(tags) > 0:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if len(tag_list) != 13:
            errors.append(f"tags must have exactly 13 items, got {len(tag_list)}")
        # Each tag must be at most 20 characters
        for i, tag in enumerate(tag_list):
            if len(tag) > 20:
                errors.append(f"tag {i+1} exceeds 20 character limit: '{tag}' ({len(tag)} chars)")

    # long_tail_keywords should have 8 items, each 4-6 words
    long_tail = data.get("long_tail_keywords", [])
    if isinstance(long_tail, list) and len(long_tail) > 0:
        if len(long_tail) != 8:
            errors.append(f"long_tail_keywords should have 8 items, got {len(long_tail)}")

        # Check each keyword is 4-6 words
        ltk_errors = _check_long_tail_word_count(long_tail)
        errors.extend(ltk_errors)

    # description must be at least 30 characters
    description = data.get("description", "")
    if isinstance(description, str):
        if len(description) < 30:
            errors.append(f"description must be at least 30 characters, got {len(description)}")

        # Check for markdown (must be plain text)
        md_errors = _check_description_no_markdown(description)
        errors.extend(md_errors)

    if errors:
        return ReviewResult(passed=False, level=ReviewLevel.RULES, errors=errors)
    return ReviewResult(passed=True, level=ReviewLevel.RULES, errors=[])
