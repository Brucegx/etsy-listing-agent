#!/usr/bin/env python3
"""
Integration test script for Etsy Listing Agent

This script tests the full workflow with real Claude API calls.
Requires ANTHROPIC_API_KEY environment variable or --api-key flag.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etsy_listing_agent.cli import run_workflow


async def main():
    """Run integration test"""
    # API key from environment or hardcoded for testing
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        print("Usage: ANTHROPIC_API_KEY=sk-xxx python scripts/test_integration.py")
        sys.exit(1)

    # Sample product data
    product_path = Path(__file__).parent.parent / "samples" / "R001"
    product_path.mkdir(parents=True, exist_ok=True)

    # Create placeholder image if not exists
    placeholder = product_path / "R001_01.jpg"
    if not placeholder.exists():
        # Create a 1x1 JPEG placeholder
        placeholder.write_bytes(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9televent\xff\xd9'
        )
        print(f"Created placeholder image: {placeholder}")

    # Excel row data
    excel_row = {
        "SKU": "R001",
        "Name": "藏式六字真言戒指",
        "Material": "925银",
        "Size": "可调节 US 7-12",
        "Notes": "手工打磨，复古做旧工艺，藏传佛教六字真言: 嗡嘛呢叭咪吽",
    }

    print("=" * 60)
    print("Etsy Listing Agent - Integration Test")
    print("=" * 60)
    print(f"Product ID: R001")
    print(f"Path: {product_path}")
    print(f"Excel Data: {json.dumps(excel_row, ensure_ascii=False, indent=2)}")
    print("=" * 60)

    # Run workflow
    result = await run_workflow(
        product_id="R001",
        product_path=str(product_path) + "/",
        category="rings",
        excel_row=excel_row,
        image_files=["R001_01.jpg"],
        max_retries=2,
        api_key=api_key,
    )

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(f"Success: {result['success']}")
    print(f"Stage: {result['stage']}")

    # Check output files
    print("\nGenerated Files:")
    for filename in ["product_data.json", "R001_NanoBanana_Prompts.json", "R001_Listing.json"]:
        filepath = product_path / filename
        if filepath.exists():
            print(f"  ✓ {filename}")
            # Show first 200 chars of content
            content = filepath.read_text()
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"    Preview: {preview}")
        else:
            print(f"  ✗ {filename} (not created)")

    return result["success"]


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
