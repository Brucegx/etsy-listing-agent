#!/usr/bin/env python3
"""
Convert NanoBanana prompts to Gemini-compatible format

Usage:
    python convert_prompts_for_gemini.py --input samples/R001/R001_NanoBanana_Prompts.json
"""

import argparse
import json
from pathlib import Path


def convert_prompts(input_file: Path) -> dict:
    """Convert our format to Gemini-compatible format"""
    with open(input_file) as f:
        data = json.load(f)

    converted_prompts = []
    for p in data.get("prompts", []):
        converted_prompts.append({
            "index": p.get("prompt_id", 0),
            "type": p.get("shot_type", "hero"),
            "type_name": p.get("shot_type", "hero").replace("_", " ").title(),
            "goal": "",  # Not in our format
            "prompt": p.get("prompt", ""),
            "design_rationale": {},
            "reference_images": [],  # Will use product images
        })

    return {
        "product_id": data.get("product_id", ""),
        "prompts": converted_prompts,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert NanoBanana prompts for Gemini")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Input JSON file")
    parser.add_argument("--output", "-o", type=Path, help="Output file (default: overwrite input)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    converted = convert_prompts(args.input)

    output_file = args.output or args.input
    with open(output_file, "w") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)

    print(f"Converted {len(converted['prompts'])} prompts")
    print(f"Saved to: {output_file}")
    return 0


if __name__ == "__main__":
    exit(main())
