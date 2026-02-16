#!/usr/bin/env python3
"""L1 + L2 validator CLI for {product_id}_listing.json

Usage:
    python scripts/validate_listing.py /path/to/product/folder

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
    validate_listing_schema,
    validate_listing_rules,
)


def find_listing_file(product_path: Path) -> Path | None:
    """Find the listing JSON file in the product folder."""
    # Try pattern: {product_id}_listing.json or {product_id}_Listing.json
    for pattern in ["*_listing.json", "*_Listing.json"]:
        matches = list(product_path.glob(pattern))
        if matches:
            return matches[0]
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_listing.py <product_path>", file=sys.stderr)
        return 1

    product_path = Path(sys.argv[1])

    # Find listing file
    data_file = find_listing_file(product_path)
    if data_file is None:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - No listing file found in {product_path}", file=sys.stderr)
        print(f"  - Expected: *_listing.json or *_Listing.json", file=sys.stderr)
        return 1

    # Load JSON
    try:
        data = json.loads(data_file.read_text())
    except json.JSONDecodeError as e:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - Invalid JSON in {data_file.name}: {e}", file=sys.stderr)
        return 1

    # L1: Schema validation
    result = validate_listing_schema(data)
    if not result.passed:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # L2: Rules validation
    result = validate_listing_rules(data)
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
