#!/usr/bin/env python3
"""L1 + L2 validator CLI for product_data.json

Usage:
    python scripts/validate_product_data.py /path/to/product/folder

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
    validate_product_data_schema,
    validate_product_data_rules,
)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_product_data.py <product_path>", file=sys.stderr)
        return 1

    product_path = Path(sys.argv[1])
    data_file = product_path / "product_data.json"

    # Check file exists
    if not data_file.exists():
        print(f"L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - File not found: {data_file}", file=sys.stderr)
        return 1

    # Load JSON
    try:
        data = json.loads(data_file.read_text())
    except json.JSONDecodeError as e:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        print(f"  - Invalid JSON: {e}", file=sys.stderr)
        return 1

    # L1: Schema validation
    result = validate_product_data_schema(data)
    if not result.passed:
        print("L1_SCHEMA_FAILED", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # L2: Rules validation
    result = validate_product_data_rules(data)
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
