#!/usr/bin/env python3
"""Gemini Image Generation for Etsy Listing Agent.

Generates product images using Gemini API based on NanoBanana prompts.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


@dataclass
class PromptEntry:
    """Single prompt entry from NanoBanana prompts."""

    index: int
    type_name: str  # Chinese name
    type_en: str  # English name
    goal: str
    prompt: str
    reference_images: list[str] = field(default_factory=list)


def parse_nanobanana_json(file_path: Path) -> list[PromptEntry]:
    """Parse NanoBanana prompts JSON file."""
    data = json.loads(file_path.read_text(encoding="utf-8"))
    entries = []

    for p in data.get("prompts", []):
        entries.append(
            PromptEntry(
                index=p["index"],
                type_name=p.get("type_name", ""),
                type_en=p.get("type", ""),
                goal=p.get("goal", ""),
                prompt=p["prompt"],
                reference_images=p.get("reference_images", []),
            )
        )

    return entries


def generate_image_gemini(
    prompt: str,
    reference_image_paths: list[str] | None = None,
    resolution: str = "4k",
    api_key: str | None = None,
) -> bytes:
    """Generate image using Gemini API.

    Args:
        prompt: Generation prompt
        reference_image_paths: List of reference image paths
        resolution: 1k, 2k, or 4k
        api_key: Gemini API key

    Returns:
        Image bytes (PNG)
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    size_map = {"1k": "1K", "2k": "2K", "4k": "4K"}

    contents = []

    # Add reference images
    for ref_path in reference_image_paths or []:
        p = Path(ref_path)
        if p.exists():
            ext = p.suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            contents.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime_type))

    contents.append(prompt)

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                image_size=size_map[resolution.lower()],
            ),
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise ValueError("No image generated in response")


def generate_images_for_product(
    product_path: str,
    product_id: str,
    resolution: str = "4k",
    prompt_indices: list[int] | None = None,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate all images for a product.

    Args:
        product_path: Path to product directory
        product_id: Product ID (e.g., R001)
        resolution: Image resolution (1k, 2k, 4k)
        prompt_indices: Only generate specific prompt indices
        dry_run: If True, don't actually generate
        api_key: Gemini API key

    Returns:
        Result dict with generated image paths
    """
    product_dir = Path(product_path)

    # Find prompts file
    prompts_file = product_dir / f"{product_id}_NanoBanana_Prompts.json"
    if not prompts_file.exists():
        return {"success": False, "error": f"Prompts file not found: {prompts_file}"}

    # Parse prompts
    entries = parse_nanobanana_json(prompts_file)
    print(f"📄 Parsed {len(entries)} prompts from {prompts_file.name}")

    # Create output directory
    output_dir = product_dir / f"generated_{resolution}"
    output_dir.mkdir(exist_ok=True)

    results = {
        "success": True,
        "output_dir": str(output_dir),
        "generated": [],
        "failed": [],
    }

    for entry in entries:
        # Filter by indices if specified
        if prompt_indices and entry.index not in prompt_indices:
            continue

        print(f"\n  📸 {entry.index}. {entry.type_name} | {entry.type_en}")
        print(f"     Goal: {entry.goal}")
        print(f"     References: {len(entry.reference_images)} images")

        if dry_run:
            print("     [DRY RUN] Skipping generation")
            continue

        # Build reference image paths — require at least 1 reference
        ref_paths = []
        missing_refs = []
        for ref_name in entry.reference_images:
            ref_path = product_dir / ref_name
            if ref_path.exists():
                ref_paths.append(str(ref_path))
            else:
                missing_refs.append(ref_name)

        if missing_refs:
            # Diagnose: list actual files in product_dir for debugging
            actual_files = sorted([f.name for f in product_dir.iterdir() if f.is_file()])
            print(f"     ⚠️ Reference images missing: {missing_refs}")
            print(f"     📂 Actual files in {product_dir.name}/: {actual_files}")

        if not ref_paths and entry.reference_images:
            actual_files = sorted([f.name for f in product_dir.iterdir() if f.is_file()])
            raise FileNotFoundError(
                f"All reference images missing for {entry.type_en}. "
                f"Expected: {missing_refs}. "
                f"Actual files: {actual_files}. "
                f"Product dir: {product_dir}"
            )

        try:
            # Generate image
            image_data = generate_image_gemini(
                prompt=entry.prompt,
                reference_image_paths=ref_paths if ref_paths else None,
                resolution=resolution,
                api_key=api_key,
            )

            # Save image
            safe_title = entry.type_en.replace("/", "_").replace(" ", "_")
            output_filename = f"{product_id}_{entry.index:02d}_{safe_title}_{resolution}.png"
            output_path = output_dir / output_filename
            output_path.write_bytes(image_data)

            print(f"     ✅ Saved: {output_filename}")
            results["generated"].append(
                {
                    "index": entry.index,
                    "type": entry.type_en,
                    "path": str(output_path),
                }
            )

        except Exception as e:
            print(f"     ❌ Failed: {e}")
            results["failed"].append(
                {
                    "index": entry.index,
                    "type": entry.type_en,
                    "error": str(e),
                }
            )

    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Generation Summary for {product_id}")
    print(f"   Generated: {len(results['generated'])} images")
    print(f"   Failed: {len(results['failed'])} images")
    print(f"   Output: {output_dir}")

    if results["failed"]:
        results["success"] = False

    return results
