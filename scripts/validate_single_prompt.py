#!/usr/bin/env python3
"""L1 + L2 validator CLI for single jewelry prompt

Usage:
    python scripts/validate_single_prompt.py /path/to/product/folder hero
    python scripts/validate_single_prompt.py /path/to/product/folder wearing_a

Exit codes:
    0 = L1+L2 validation passed
    1 = L1 (schema) or L2 (rules) validation failed

Stderr contains specific error messages for retry feedback.
"""

import json
import re
import sys
from pathlib import Path

# Valid prompt types
VALID_TYPES = {
    "hero", "size_reference", "art_abstract",
    "wearing_a", "wearing_b", "macro_detail",
    "art_still_life", "scene_daily", "workshop"
}

# Type-specific banned keywords
BANNED_KEYWORDS = {
    "hero": {
        "positive": ["hand", "finger", "model", "silk", "fabric", "holding", "wearing"],
        "background": ["dark background", "charcoal", "black velvet", "dark gray"],
    },
    "wearing_a": {
        "locations": ["cafe", "beach", "garden", "office", "flowers", "coffee", "books"],
    },
    "wearing_b": {
        "locations": ["cafe", "beach", "garden", "office", "flowers", "coffee", "books"],
    },
}

# Hero must have specific aperture
HERO_VALID_APERTURES = ["f/8", "f/11"]


def validate_anchor_format(prompt_text: str) -> list[str]:
    """Validate ANCHOR format (≤3 lines, ends with 'Rigid constraint.')"""
    errors = []

    if "REFERENCE ANCHOR:" not in prompt_text:
        errors.append("Prompt must contain 'REFERENCE ANCHOR:'")
        return errors

    # Extract ANCHOR section
    anchor_start = prompt_text.find("REFERENCE ANCHOR:")

    # Find where ANCHOR ends (double newline or next section)
    anchor_end = prompt_text.find("\n\n", anchor_start)
    if anchor_end == -1:
        anchor_end = prompt_text.find("SCENE CONTEXT:", anchor_start)
    if anchor_end == -1:
        anchor_end = len(prompt_text)

    anchor_section = prompt_text[anchor_start:anchor_end].strip()

    # Check line count (≤3 lines)
    anchor_lines = [l for l in anchor_section.split("\n") if l.strip()]
    if len(anchor_lines) > 3:
        errors.append(f"ANCHOR must be ≤3 lines, got {len(anchor_lines)} lines")

    # Check ends with "Rigid constraint."
    if "rigid constraint" not in anchor_section.lower():
        errors.append("ANCHOR must contain 'Rigid constraint.'")

    return errors


def validate_hero_rules(prompt_text: str, data: dict) -> list[str]:
    """Validate hero-specific rules"""
    errors = []
    prompt_lower = prompt_text.lower()

    # Check banned keywords (but allow negative statements like "no hands")
    for keyword in BANNED_KEYWORDS["hero"]["positive"]:
        if keyword in prompt_lower:
            # Check if it's a negative statement
            negative_patterns = [f"no {keyword}", f"without {keyword}", f"no {keyword}s"]
            is_negative = any(neg in prompt_lower for neg in negative_patterns)
            if not is_negative:
                errors.append(f"Hero prompt contains banned keyword: '{keyword}'")

    # Check banned dark backgrounds
    for keyword in BANNED_KEYWORDS["hero"]["background"]:
        if keyword in prompt_lower:
            errors.append(f"Hero must have light background, found: '{keyword}'")

    # Check aperture (must be f/8 or f/11)
    camera_params = data.get("camera_params", {})
    aperture = camera_params.get("aperture", "")
    if aperture and aperture not in HERO_VALID_APERTURES:
        errors.append(f"Hero aperture must be f/8 or f/11, got '{aperture}'")

    # Check prompt text for wide apertures
    if "f/1.8" in prompt_lower or "f/2.8" in prompt_lower or "f/4" in prompt_lower:
        errors.append("Hero must use f/8 or f/11, found wide aperture in prompt")

    return errors


def validate_wearing_rules(prompt_text: str, prompt_type: str) -> list[str]:
    """Validate wearing_a/wearing_b rules"""
    errors = []
    prompt_lower = prompt_text.lower()

    # Check banned location keywords
    for keyword in BANNED_KEYWORDS.get(prompt_type, {}).get("locations", []):
        if keyword in prompt_lower:
            errors.append(f"Wearing prompt contains banned location: '{keyword}'")

    return errors


def validate_single_prompt(data: dict, prompt_type: str) -> list[str]:
    """Validate a single prompt JSON"""
    errors = []

    # L1: Schema - required fields
    required_fields = ["prompt", "reference_images", "index", "design_rationale"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check index is a positive integer
    index = data.get("index")
    if index is not None:
        if not isinstance(index, int) or index < 1 or index > 9:
            errors.append(f"index must be integer 1-9, got: {index}")

    # Check reference_images is array of exactly 3
    ref_images = data.get("reference_images")
    if ref_images is not None:
        if not isinstance(ref_images, list):
            errors.append("reference_images must be an array")
        elif len(ref_images) != 3:
            errors.append(f"reference_images must have exactly 3 items, got {len(ref_images)}")
        else:
            for i, img in enumerate(ref_images):
                if not isinstance(img, str) or not img:
                    errors.append(f"reference_images[{i}] must be a non-empty string")

    # Check design_rationale is a dict
    rationale = data.get("design_rationale")
    if rationale is not None and not isinstance(rationale, dict):
        errors.append("design_rationale must be an object")

    # Early return if critical fields missing
    if "prompt" not in data:
        return errors

    prompt_text = data.get("prompt", "")

    # Check prompt length
    if len(prompt_text) < 50:
        errors.append(f"Prompt too short: {len(prompt_text)} chars (min 50)")

    # Validate ANCHOR format
    anchor_errors = validate_anchor_format(prompt_text)
    errors.extend(anchor_errors)

    # L2: Type-specific rules
    if prompt_type == "hero":
        hero_errors = validate_hero_rules(prompt_text, data)
        errors.extend(hero_errors)

    elif prompt_type in ("wearing_a", "wearing_b"):
        wearing_errors = validate_wearing_rules(prompt_text, prompt_type)
        errors.extend(wearing_errors)

    return errors


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: validate_single_prompt.py <product_path> <prompt_type>", file=sys.stderr)
        print(f"Valid types: {', '.join(sorted(VALID_TYPES))}", file=sys.stderr)
        return 1

    product_path = Path(sys.argv[1])
    prompt_type = sys.argv[2]

    # Validate prompt type
    if prompt_type not in VALID_TYPES:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - Invalid prompt type: {prompt_type}", file=sys.stderr)
        print(f"  - Valid types: {', '.join(sorted(VALID_TYPES))}", file=sys.stderr)
        return 1

    # Find prompt file
    prompt_file = product_path / f"*_prompt_{prompt_type}.json"
    matches = list(product_path.glob(f"*_prompt_{prompt_type}.json"))

    if not matches:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - No prompt file found for type: {prompt_type}", file=sys.stderr)
        print(f"  - Expected: *_prompt_{prompt_type}.json", file=sys.stderr)
        return 1

    data_file = matches[0]

    # Load JSON
    try:
        data = json.loads(data_file.read_text())
    except json.JSONDecodeError as e:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - Invalid JSON: {e}", file=sys.stderr)
        return 1

    # Validate
    errors = validate_single_prompt(data, prompt_type)

    if errors:
        print("L2_RULES_FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # All passed
    print(f"L1_L2_PASSED ({prompt_type})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
