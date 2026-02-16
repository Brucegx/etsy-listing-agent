#!/usr/bin/env python3
"""Stage 4: Generate images using Gemini API from jewelry prompts.

Usage:
    python scripts/generate_images.py /path/to/product/folder

Reads {product_id}_Jewelry_Prompts.json and generates 9 images using Gemini.
Saves images as {product_id}_gen_{type}.png at 1024x1024 resolution.

Environment:
    GOOGLE_API_KEY or GEMINI_API_KEY - Required API key for Gemini
"""

import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import google.generativeai as genai
    from PIL import Image
except ImportError as e:
    print(f"Missing dependency: {e}", file=sys.stderr)
    print("Install with: uv add google-generativeai pillow", file=sys.stderr)
    sys.exit(1)


# Configuration
IMAGE_RESOLUTION = 1024  # 1k resolution
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 5


def get_api_key() -> str:
    """Get Gemini API key from environment."""
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable."
        )
    return key


def load_reference_image(product_path: Path, filename: str) -> Image.Image | None:
    """Load a reference image from the product folder."""
    image_path = product_path / filename
    if not image_path.exists():
        print(f"  Warning: Reference image not found: {filename}", file=sys.stderr)
        return None

    try:
        img = Image.open(image_path)
        # Resize if too large (Gemini has limits)
        max_size = 1024
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        print(f"  Warning: Failed to load {filename}: {e}", file=sys.stderr)
        return None


def generate_single_image(
    model: genai.GenerativeModel,
    prompt_data: dict,
    product_path: Path,
    product_id: str,
) -> dict:
    """Generate a single image from prompt data.

    Returns:
        dict with keys: index, type, status, output_file (if success),
                       error (if failed), generation_time_ms
    """
    prompt_type = prompt_data["type"]
    index = prompt_data["index"]
    prompt_text = prompt_data["prompt"]
    reference_images = prompt_data.get("reference_images", [])

    result = {
        "index": index,
        "type": prompt_type,
        "status": "pending",
        "output_file": None,
        "error": None,
        "generation_time_ms": 0,
    }

    start_time = time.time()

    # Load reference images
    images = []
    for img_filename in reference_images:
        img = load_reference_image(product_path, img_filename)
        if img:
            images.append(img)

    if not images:
        result["status"] = "failed"
        result["error"] = "No valid reference images found"
        return result

    # Build content for Gemini
    # Gemini imagen expects: images first, then text prompt
    content_parts = images + [prompt_text]

    # Retry loop
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Generate image using Gemini
            response = model.generate_content(
                content_parts,
                generation_config=genai.GenerationConfig(
                    response_mime_type="image/png",
                ),
            )

            # Check if we got an image
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        # Save the generated image
                        output_filename = f"{product_id}_gen_{prompt_type}.png"
                        output_path = product_path / output_filename

                        # Decode and save
                        image_data = base64.b64decode(part.inline_data.data)
                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        result["status"] = "success"
                        result["output_file"] = output_filename
                        result["generation_time_ms"] = int((time.time() - start_time) * 1000)
                        return result

            # No image in response
            last_error = "No image in response"

        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} for {prompt_type}: {e}")
                time.sleep(RETRY_DELAY_SECONDS)

    # All retries failed
    result["status"] = "failed"
    result["error"] = last_error
    result["generation_time_ms"] = int((time.time() - start_time) * 1000)
    return result


def find_jewelry_prompts_file(product_path: Path) -> Path | None:
    """Find the jewelry prompts JSON file in the product folder."""
    patterns = [
        "*_Jewelry_Prompts.json",
        "*_jewelry_prompts.json",
        "*_NanoBanana_Prompts.json",  # Legacy fallback
    ]
    for pattern in patterns:
        matches = list(product_path.glob(pattern))
        if matches:
            return matches[0]
    return None


def extract_product_id(prompts_file: Path) -> str:
    """Extract product ID from prompts filename."""
    name = prompts_file.stem
    # Remove suffixes like _Jewelry_Prompts, _jewelry_prompts, _NanoBanana_Prompts
    for suffix in ["_Jewelry_Prompts", "_jewelry_prompts", "_NanoBanana_Prompts"]:
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: generate_images.py <product_path>", file=sys.stderr)
        return 1

    product_path = Path(sys.argv[1])
    if not product_path.is_dir():
        print(f"Error: Not a directory: {product_path}", file=sys.stderr)
        return 1

    # Find prompts file
    prompts_file = find_jewelry_prompts_file(product_path)
    if not prompts_file:
        print(f"Error: No jewelry prompts file found in {product_path}", file=sys.stderr)
        return 1

    print(f"Loading prompts from: {prompts_file.name}")

    # Load prompts
    try:
        data = json.loads(prompts_file.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {prompts_file.name}: {e}", file=sys.stderr)
        return 1

    prompts = data.get("prompts", [])
    if not prompts:
        print("Error: No prompts found in JSON", file=sys.stderr)
        return 1

    product_id = extract_product_id(prompts_file)
    print(f"Product ID: {product_id}")
    print(f"Found {len(prompts)} prompts to generate")
    print(f"Resolution: {IMAGE_RESOLUTION}x{IMAGE_RESOLUTION}")
    print()

    # Initialize Gemini
    try:
        api_key = get_api_key()
        genai.configure(api_key=api_key)

        # Use Gemini 2.0 Flash for image generation
        model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")
    except Exception as e:
        print(f"Error initializing Gemini: {e}", file=sys.stderr)
        return 1

    # Generate images
    results = []
    successful = 0
    failed = 0

    for i, prompt_data in enumerate(prompts):
        prompt_type = prompt_data.get("type", f"unknown_{i}")
        print(f"[{i+1}/{len(prompts)}] Generating {prompt_type}...", end=" ", flush=True)

        result = generate_single_image(model, prompt_data, product_path, product_id)
        results.append(result)

        if result["status"] == "success":
            successful += 1
            print(f"✓ ({result['generation_time_ms']}ms)")
        else:
            failed += 1
            print(f"✗ {result['error']}")

    print()
    print(f"Generation complete: {successful} successful, {failed} failed")

    # Write generation report
    report = {
        "product_id": product_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "resolution": f"{IMAGE_RESOLUTION}x{IMAGE_RESOLUTION}",
        "total_prompts": len(prompts),
        "successful": successful,
        "failed": failed,
        "results": results,
    }

    report_path = product_path / f"{product_id}_generation_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"Report saved: {report_path.name}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
