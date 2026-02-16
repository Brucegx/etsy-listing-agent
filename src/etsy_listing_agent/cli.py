#!/usr/bin/env python3
# CLI entry point for Etsy Listing Agent
# Command-line entry point for processing a single product

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from etsy_listing_agent.excel_loader import load_excel_row, detect_category_from_path
from etsy_listing_agent.state import create_initial_state
from etsy_listing_agent.workflow import create_workflow
from etsy_listing_agent.nodes import (
    preprocess_node,
    preprocess_review_node,
    nanobanana_node,
    nanobanana_review_node,
    listing_node,
    listing_review_node,
    image_gen_node,
)


async def run_workflow(
    product_id: str,
    product_path: str,
    category: str,
    excel_row: dict,
    image_files: list[str],
    max_retries: int = 3,
    api_key: str | None = None,
    generate_images: bool = False,
    image_resolution: str = "1k",
    gemini_api_key: str | None = None,
) -> dict:
    """Run the full workflow.

    Args:
        product_id: Product ID
        product_path: Path to the product folder
        category: Product category
        excel_row: Excel row data
        image_files: List of image files
        max_retries: Maximum number of retries
        api_key: Anthropic API key
        generate_images: Whether to generate images
        image_resolution: Image resolution (1k, 2k, 4k)
        gemini_api_key: Gemini API key

    Returns:
        Final state dict
    """
    # Set API key
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    # Create initial state
    state = create_initial_state(
        product_id=product_id,
        product_path=product_path,
        category=category,
        excel_row=excel_row,
        image_files=image_files,
        max_retries=max_retries,
    )

    print(f"Starting workflow for product: {product_id}")
    print(f"Category: {category}")
    print(f"Path: {product_path}")

    # Manually execute workflow steps (simplified, without full LangGraph compilation)
    # This makes it easier to debug and control

    while state["stage"] not in ("completed", "failed"):
        current_stage = state["stage"]
        print(f"\n[Stage: {current_stage}]")

        if current_stage == "pending":
            state = await preprocess_node(state)
        elif current_stage == "preprocessing":
            state = await preprocess_review_node(state)
        elif current_stage == "preprocessing_review":
            review = state.get("preprocessing_review")
            if review and review.passed:
                state = await nanobanana_node(state)
            elif state["retry_counts"]["preprocessing"] < state["max_retries"]:
                print(f"  Retry preprocessing ({state['retry_counts']['preprocessing']}/{state['max_retries']})")
                state = await preprocess_node(state)
            else:
                state["stage"] = "failed"
                state["final_error"] = f"Preprocessing failed after {state['max_retries']} retries"
        elif current_stage == "nanobanana":
            state = await nanobanana_review_node(state)
        elif current_stage == "nanobanana_review":
            review = state.get("nanobanana_review")
            if review and review.passed:
                state = await listing_node(state)
            elif state["retry_counts"]["nanobanana"] < state["max_retries"]:
                print(f"  Retry nanobanana ({state['retry_counts']['nanobanana']}/{state['max_retries']})")
                state = await nanobanana_node(state)
            else:
                state["stage"] = "failed"
                state["final_error"] = f"NanoBanana failed after {state['max_retries']} retries"
        elif current_stage == "listing":
            state = await listing_review_node(state)
        elif current_stage == "listing_review":
            review = state.get("listing_review")
            if review and review.passed:
                if generate_images:
                    state["stage"] = "image_gen"
                else:
                    state["stage"] = "completed"
                    state["success"] = True
                    print("\n✅ Workflow completed successfully!")
            elif state["retry_counts"]["listing"] < state["max_retries"]:
                print(f"  Retry listing ({state['retry_counts']['listing']}/{state['max_retries']})")
                state = await listing_node(state)
            else:
                state["stage"] = "failed"
                state["final_error"] = f"Listing failed after {state['max_retries']} retries"
        elif current_stage == "image_gen":
            state = await image_gen_node(state, resolution=image_resolution, gemini_api_key=gemini_api_key)
            if state.get("image_gen_result", {}).get("success"):
                state["stage"] = "completed"
                state["success"] = True
                print("\n✅ Workflow completed successfully (with images)!")
            else:
                state["stage"] = "failed"
                state["final_error"] = f"Image generation failed: {state.get('image_gen_result', {}).get('error', 'Unknown')}"

        # Print review results
        for stage_name in ["preprocessing", "nanobanana", "listing"]:
            review_key = f"{stage_name}_review"
            review = state.get(review_key)
            if review and current_stage == f"{stage_name}_review":
                if review.passed:
                    print(f"  ✓ Review passed (Level: {review.level.name})")
                else:
                    print(f"  ✗ Review failed (Level: {review.level.name})")
                    for error in review.errors[:3]:  # Only show the first 3 errors
                        print(f"    - {error}")

    if state["stage"] == "failed":
        print(f"\n❌ Workflow failed: {state.get('final_error')}")

    return dict(state)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Etsy Listing Agent - Process a single product"
    )
    parser.add_argument(
        "--product-path",
        required=True,
        help="Path to product folder (must contain images)",
    )
    parser.add_argument(
        "--product-id",
        help="Product ID (default: folder name)",
    )
    parser.add_argument(
        "--category",
        choices=["rings", "earrings", "necklaces", "bracelets", "pendants"],
        required=True,
        help="Product category",
    )
    parser.add_argument(
        "--excel-file",
        type=str,
        help="Path to Excel file containing product data",
    )
    parser.add_argument(
        "--row-id",
        type=str,
        help="Product ID to find in Excel file (uses '款号' column)",
    )
    parser.add_argument(
        "--excel-data",
        type=str,
        default="{}",
        help="Excel row data as JSON string (alternative to --excel-file)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per stage (default: 3)",
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help="Generate product images using Gemini API",
    )
    parser.add_argument(
        "--image-resolution",
        type=str,
        default="1k",
        choices=["1k", "2k", "4k"],
        help="Image resolution (default: 1k)",
    )
    parser.add_argument(
        "--gemini-api-key",
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )

    args = parser.parse_args()

    # Validate path
    product_path = Path(args.product_path).resolve()
    if not product_path.exists():
        print(f"Error: Product path does not exist: {product_path}")
        sys.exit(1)

    # Get product ID
    product_id = args.product_id or product_path.name

    # Get image files
    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    image_files = [
        f.name
        for f in product_path.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    if not image_files:
        print(f"Warning: No image files found in {product_path}")

    # Parse Excel data - supports two methods
    if args.excel_file:
        # Load from Excel file
        if not args.row_id:
            # Default to using the product ID
            args.row_id = product_id
        try:
            excel_row = load_excel_row(args.excel_file, args.row_id)
            print(f"Loaded row '{args.row_id}' from Excel: {args.excel_file}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Parse from JSON string
        try:
            excel_row = json.loads(args.excel_data)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --excel-data: {args.excel_data}")
            sys.exit(1)

    # Run workflow
    result = asyncio.run(
        run_workflow(
            product_id=product_id,
            product_path=str(product_path) + "/",
            category=args.category,
            excel_row=excel_row,
            image_files=image_files,
            max_retries=args.max_retries,
            api_key=args.api_key,
            generate_images=args.generate_images,
            image_resolution=args.image_resolution,
            gemini_api_key=args.gemini_api_key,
        )
    )

    # Output final result
    print("\n" + "=" * 50)
    print("Final Result:")
    print(f"  Success: {result['success']}")
    print(f"  Stage: {result['stage']}")
    if result.get("final_error"):
        print(f"  Error: {result['final_error']}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
