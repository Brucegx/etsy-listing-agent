#!/usr/bin/env python3
"""
E2E Runner for Etsy Listing Agent

Run the workflow nodes directly on a real product directory.
Usage: uv run python scripts/run_e2e.py /path/to/product/R001
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etsy_listing_agent.nodes import (
    preprocess_review_node,
    nanobanana_node,
    nanobanana_review_node,
    listing_node,
    listing_review_node,
)
from etsy_listing_agent.state import create_initial_state
from etsy_listing_agent.validators import (
    validate_product_data_schema,
    validate_product_data_rules,
    validate_nanobanana_schema,
    validate_nanobanana_rules,
    validate_listing_schema,
    validate_listing_rules,
)


def validate_file(filepath: Path, schema_validator, rules_validator) -> bool:
    """Validate a JSON file and print results."""
    print(f"\n📋 Validating {filepath.name}...")

    try:
        with open(filepath) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  ❌ Failed to read: {e}")
        return False

    # Schema validation
    result = schema_validator(data)
    if not result.passed:
        print(f"  ❌ Schema validation FAILED:")
        for err in result.errors[:5]:
            print(f"     - {err}")
        if len(result.errors) > 5:
            print(f"     ... and {len(result.errors) - 5} more errors")
        return False
    print("  ✅ Schema validation PASSED")

    # Rules validation
    result = rules_validator(data)
    if not result.passed:
        print(f"  ❌ Rules validation FAILED:")
        for err in result.errors[:5]:
            print(f"     - {err}")
        if len(result.errors) > 5:
            print(f"     ... and {len(result.errors) - 5} more errors")
        return False
    print("  ✅ Rules validation PASSED")

    return True


async def run_e2e(product_path: str):
    """Run E2E workflow nodes directly on a product directory."""
    product_dir = Path(product_path)

    if not product_dir.exists():
        print(f"❌ Product directory not found: {product_dir}")
        return False

    print(f"🚀 Running E2E workflow on: {product_dir}")
    print("=" * 60)

    # Get product_id from directory name
    product_id = product_dir.name

    # Check for existing product_data.json
    product_data_file = product_dir / "product_data.json"
    if not product_data_file.exists():
        print(f"❌ No product_data.json found in {product_dir}")
        return False

    # Read existing product_data
    with open(product_data_file) as f:
        product_data = json.load(f)

    # Get image files
    image_files = [img["filename"] for img in product_data.get("images", [])]

    # Create initial state
    state = create_initial_state(
        product_id=product_id,
        product_path=str(product_dir) + "/",
        category=product_data.get("category", "rings"),
        excel_row={"basic_info": product_data.get("basic_info", "")},
        image_files=image_files,
        max_retries=3,
    )

    # Step 1: Validate preprocessing output
    print("\n📦 Step 1: Validating product_data.json...")
    state["stage"] = "preprocessing"
    state = await preprocess_review_node(state)

    review = state.get("preprocessing_review")
    if not review or not review.passed:
        print(f"❌ Preprocessing validation FAILED: {review.errors if review else 'No review'}")
        return False
    print("✅ product_data.json validated")

    # Step 2: Generate NanoBanana prompts
    print("\n🎨 Step 2: Generating NanoBanana prompts...")
    print("   (Calling Claude API - this may take ~30 seconds)")
    state["stage"] = "preprocessing_review"  # After preprocess_review
    try:
        state = await nanobanana_node(state)
    except Exception as e:
        print(f"❌ NanoBanana generation failed: {e}")
        return False
    print(f"✅ Generated {product_id}_NanoBanana_Prompts.json")

    # Step 3: Validate NanoBanana output
    print("\n🔍 Step 3: Validating NanoBanana prompts...")
    state = await nanobanana_review_node(state)

    review = state.get("nanobanana_review")
    if not review or not review.passed:
        print(f"❌ NanoBanana validation FAILED:")
        for err in (review.errors if review else ["No review"])[:5]:
            print(f"   - {err}")
        return False
    print("✅ NanoBanana prompts validated")

    # Step 4: Generate Listing
    print("\n📝 Step 4: Generating Etsy listing...")
    print("   (Calling Claude API - this may take ~30 seconds)")
    try:
        state = await listing_node(state)
    except Exception as e:
        print(f"❌ Listing generation failed: {e}")
        return False
    print(f"✅ Generated {product_id}_Listing.json")

    # Step 5: Validate Listing output
    print("\n🔍 Step 5: Validating Etsy listing...")
    state = await listing_review_node(state)

    review = state.get("listing_review")
    if not review or not review.passed:
        print(f"❌ Listing validation FAILED:")
        for err in (review.errors if review else ["No review"])[:5]:
            print(f"   - {err}")
        return False
    print("✅ Etsy listing validated")

    # Final summary
    print("\n" + "=" * 60)
    print("🎉 E2E WORKFLOW COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nGenerated files:")
    print(f"  - {product_dir / 'product_data.json'}")
    print(f"  - {product_dir / f'{product_id}_NanoBanana_Prompts.json'}")
    print(f"  - {product_dir / f'{product_id}_Listing.json'}")

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/run_e2e.py /path/to/product/R001")
        print("\nExample:")
        print("  uv run python scripts/run_e2e.py /path/to/products/Ring/R001")
        sys.exit(1)

    product_path = sys.argv[1]
    success = asyncio.run(run_e2e(product_path))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
