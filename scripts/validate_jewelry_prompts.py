#!/usr/bin/env python3
"""L1 + L2 validator CLI for {product_id}_Jewelry_Prompts.json

Usage:
    python scripts/validate_jewelry_prompts.py /path/to/product/folder

Exit codes:
    0 = L1+L2 validation passed
    1 = L1 (schema) or L2 (rules) validation failed

Stderr contains specific error messages for retry feedback.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etsy_listing_agent.validators import (
    validate_nanobanana_schema,
    validate_nanobanana_rules,
)


def find_jewelry_prompts_file(product_path: Path) -> Path | None:
    """Find the jewelry prompts JSON file in the product folder."""
    # Try new pattern: {product_id}_Jewelry_Prompts.json
    matches = list(product_path.glob("*_Jewelry_Prompts.json"))
    if matches:
        return matches[0]
    # Also try lowercase
    matches = list(product_path.glob("*_jewelry_prompts.json"))
    if matches:
        return matches[0]
    # Fallback to old NanoBanana pattern for backwards compatibility
    matches = list(product_path.glob("*_NanoBanana_Prompts.json"))
    if matches:
        return matches[0]
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_jewelry_prompts.py <product_path>", file=sys.stderr)
        return 1

    product_path = Path(sys.argv[1])

    # Find jewelry prompts file
    data_file = find_jewelry_prompts_file(product_path)
    if data_file is None:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - No jewelry prompts file found in {product_path}", file=sys.stderr)
        print(f"  - Expected: *_Jewelry_Prompts.json", file=sys.stderr)
        return 1

    # Load JSON
    try:
        data = json.loads(data_file.read_text())
    except json.JSONDecodeError as e:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - Invalid JSON in {data_file.name}: {e}", file=sys.stderr)
        return 1

    # L1: Schema validation (reuse nanobanana validators - same format)
    result = validate_nanobanana_schema(data)
    if not result.passed:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # L2: Rules validation
    result = validate_nanobanana_rules(data)
    if not result.passed:
        print("L2_RULES_FAILED", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # All passed
    print("L1_L2_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
