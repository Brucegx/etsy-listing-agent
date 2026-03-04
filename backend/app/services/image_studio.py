"""Image Studio service — Phase 6A.

Orchestrates the "image_only" job type:
  1. Runs preprocess_node (Claude Vision) to extract product_data from images.
  2. Calls prompt_node directly for the requested image category (skips strategy).
  3. Generates N images with Gemini (variation_index 1..N + variation hints).
  4. Post-processes each image: crops to requested aspect ratio with Pillow.

Category → direction mapping (mirrors NanoBanana slot names):
  white_bg  → hero
  scene     → scene_daily
  model     → wearing_a
  detail    → macro_detail

Aspect ratio cropping:
  1:1  → square centre-crop
  3:4  → portrait centre-crop
  4:3  → landscape centre-crop
  (no value / None) → no crop, return as-is

Variation hints injected into the prompt_node user_message per index:
  index 1 — (no extra hint — baseline shot)
  index 2 — "Slightly different angle, same lighting"
  index 3 — "Different background tone / depth-of-field variation"
  index 4 — "Creative crop, show unique detail not in previous shots"
  index 5+ — "Variation {N}: explore a distinct angle or composition"
"""

import io
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --- Category → direction mapping ---

CATEGORY_TO_DIRECTION: dict[str, str] = {
    "white_bg": "hero",
    "scene": "scene_daily",
    "model": "wearing_a",
    "detail": "macro_detail",
}

# --- Aspect ratio constants ---

ASPECT_RATIO_1_1 = "1:1"
ASPECT_RATIO_3_4 = "3:4"
ASPECT_RATIO_4_3 = "4:3"

VALID_ASPECT_RATIOS = {ASPECT_RATIO_1_1, ASPECT_RATIO_3_4, ASPECT_RATIO_4_3}

# --- Variation hints (index 1-based) ---

_VARIATION_HINTS: dict[int, str] = {
    1: "",  # baseline — no extra instruction
    2: "Slightly different angle, same lighting and background.",
    3: "Vary the depth-of-field or background tone subtly for a fresh look.",
    4: "Creative crop or composition — highlight a unique detail not shown in previous shots.",
}

_VARIATION_HINT_FALLBACK = "Variation {index}: explore a distinct angle or composition not used in previous shots."


def _get_variation_hint(index: int) -> str:
    """Return a variation hint for the given 1-based variation index."""
    return _VARIATION_HINTS.get(index, _VARIATION_HINT_FALLBACK.format(index=index))


def _crop_to_aspect_ratio(image_bytes: bytes, aspect_ratio: str | None) -> bytes:
    """Centre-crop image_bytes to the requested aspect ratio using Pillow.

    Args:
        image_bytes: Raw image bytes (PNG or JPEG).
        aspect_ratio: One of "1:1", "3:4", "4:3", or None (no crop).

    Returns:
        Processed image bytes (PNG format).
    """
    if not aspect_ratio or aspect_ratio not in VALID_ASPECT_RATIOS:
        return image_bytes

    from PIL import Image  # noqa: PLC0415

    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    if aspect_ratio == ASPECT_RATIO_1_1:
        target_w, target_h = min(w, h), min(w, h)
    elif aspect_ratio == ASPECT_RATIO_3_4:
        # Portrait: height is taller — fit width, crop height
        # target_w / target_h = 3 / 4  →  target_h = target_w * 4 / 3
        target_w = w
        target_h = int(w * 4 / 3)
        if target_h > h:
            target_h = h
            target_w = int(h * 3 / 4)
    else:  # 4:3
        # Landscape: width is wider — fit height, crop width
        target_h = h
        target_w = int(h * 4 / 3)
        if target_w > w:
            target_w = w
            target_h = int(w * 3 / 4)

    # Centre crop
    left = (w - target_w) // 2
    top = (h - target_h) // 2
    cropped = img.crop((left, top, left + target_w, top + target_h))

    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    logger.debug(
        "Cropped image from %dx%d to %dx%d (%s)",
        w, h, target_w, target_h, aspect_ratio,
    )
    return buf.getvalue()


def _build_image_only_prompt(
    product_data: dict[str, Any],
    direction: str,
    variation_index: int,
    additional_prompt: str,
    aspect_ratio: str | None,
) -> str:
    """Build a self-contained Gemini image prompt for Image Studio.

    Does NOT call prompt_node (which requires the full agentic loop and
    proprietary skill content).  Instead, builds a direct, concise prompt
    that instructs Gemini on category, product details, variation, and
    aspect ratio — enough for high-quality e-commerce photography.

    Args:
        product_data: Output of preprocess_node (product_data.json content).
        direction: NanoBanana direction string (e.g. "hero", "scene_daily").
        variation_index: 1-based variation counter for this direction.
        additional_prompt: Free-text extra instructions from the user.
        aspect_ratio: Requested aspect ratio ("1:1", "3:4", "4:3", or None).

    Returns:
        Prompt text string to send to Gemini.
    """
    # Extract key product attributes
    category = product_data.get("category", "product")
    materials = ", ".join(product_data.get("materials", []))
    style = product_data.get("style", "")
    dimensions = product_data.get("product_size", {}).get("dimensions", "")
    selling_points = product_data.get("selling_points", [])
    selling_str = "; ".join(str(sp) for sp in selling_points[:3])
    reference_anchor = product_data.get("reference_anchor", "")

    # Direction → shot description
    direction_descriptions: dict[str, str] = {
        "hero": (
            "a clean, professional hero shot on a pure white background, "
            "centred product, soft even lighting, no shadows"
        ),
        "scene_daily": (
            "a lifestyle scene with the product in a natural daily-life setting, "
            "warm ambient light, shallow depth-of-field background"
        ),
        "wearing_a": (
            "a model wearing the product, lifestyle fashion shot, "
            "natural light, elegant pose"
        ),
        "macro_detail": (
            "an extreme close-up macro detail shot emphasising craftsmanship "
            "and texture, sharp focus, studio lighting"
        ),
    }
    shot_desc = direction_descriptions.get(
        direction,
        "a high-quality e-commerce product photograph",
    )

    # Aspect ratio instruction
    ar_instruction = ""
    if aspect_ratio and aspect_ratio in VALID_ASPECT_RATIOS:
        ar_instruction = f" Compose for a {aspect_ratio} aspect ratio."

    # Variation hint
    variation_hint = _get_variation_hint(variation_index)
    variation_block = ""
    if variation_hint:
        variation_block = f"\n\nVariation note: {variation_hint}"

    # Additional user prompt
    extra_block = ""
    if additional_prompt and additional_prompt.strip():
        extra_block = f"\n\nExtra instructions: {additional_prompt.strip()}"

    # Reference anchor from preprocessing (Claude's visual description)
    anchor_block = ""
    if reference_anchor:
        anchor_block = f"\n\n{reference_anchor}"

    prompt = (
        f"E-commerce product photography: {shot_desc}.{ar_instruction}\n\n"
        f"Product: {category}"
        + (f", {materials}" if materials else "")
        + (f", {style}" if style else "")
        + (f", {dimensions}" if dimensions else "")
        + (f".\nKey features: {selling_str}" if selling_str else ".")
        + anchor_block
        + variation_block
        + extra_block
    )
    return prompt


async def run_preprocess_for_image_studio(
    product_id: str,
    product_dir: Path,
    image_files: list[str],
    product_info: str,
) -> dict[str, Any]:
    """Run preprocessing to extract structured product_data from uploaded images.

    Calls the existing preprocess_node (Claude Vision) via a minimal ProductState.
    Writes product_data.json to product_dir.

    Args:
        product_id: Product identifier string.
        product_dir: Directory where images live and output will be written.
        image_files: List of image filenames (relative to product_dir).
        product_info: Free-text product description from the user.

    Returns:
        Parsed product_data dict (from product_data.json).

    Raises:
        RuntimeError: If preprocess_node fails to produce valid product_data.json.
    """
    from etsy_listing_agent.nodes import preprocess_node

    # Build a minimal state for preprocess_node
    state: dict[str, Any] = {
        "product_id": product_id,
        "product_path": str(product_dir),
        "category": "",  # let Claude infer from images
        "excel_row": {
            "款号": product_id,
            "备注": product_info or "",
        },
        "image_files": image_files,
        "preprocessing_review": None,
        "stage": "pending",
        "retry_counts": {"preprocessing": 0},
        "max_retries": 1,
    }

    logger.info("Running preprocess_node for image_studio job %s", product_id)
    await preprocess_node(state)  # type: ignore[arg-type]

    product_data_path = product_dir / "product_data.json"
    if not product_data_path.exists():
        raise RuntimeError("preprocess_node did not produce product_data.json")

    try:
        product_data: dict[str, Any] = json.loads(product_data_path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"product_data.json is not valid JSON: {exc}") from exc

    logger.info("Preprocess complete for %s — category=%s", product_id, product_data.get("category"))
    return product_data


async def generate_image_studio_images(
    job_id: str,
    product_id: str,
    product_dir: Path,
    image_files: list[str],
    product_info: str,
    image_config: dict[str, Any],
    api_key: str | None = None,
) -> list[str]:
    """Full Image Studio generation pipeline.

    Steps:
      1. Preprocess: run Claude Vision to get product_data.
      2. For each variation (1..count):
         a. Build a Gemini prompt for the requested category/direction.
         b. Call generate_image_gemini() in a thread pool.
         c. Crop to aspect_ratio with Pillow.
         d. Save to persistent storage.
      3. Return list of stable image URL paths.

    Args:
        job_id: The job UUID string (used as storage namespace).
        product_id: Product identifier string.
        product_dir: Temp directory containing uploaded images.
        image_files: List of image filenames relative to product_dir.
        product_info: Free-text product description.
        image_config: Dict with keys:
            category      — "white_bg" | "scene" | "model" | "detail"
            count         — number of variations (1-8, default 4)
            aspect_ratio  — "1:1" | "3:4" | "4:3" | None
            additional_prompt — optional extra instructions string
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).

    Returns:
        List of stable image URL paths (e.g. ["/api/images/{job_id}/..."]).
    """
    import asyncio
    import functools

    from app.database import get_db
    from app.services.job_service import JobService
    from app.services.storage import get_storage
    from etsy_listing_agent.image_generator import generate_image_gemini

    job_service = JobService()

    # --- Resolve config ---
    category = image_config.get("category", "white_bg")
    direction = CATEGORY_TO_DIRECTION.get(category, "hero")
    count = max(1, min(8, int(image_config.get("count", 4))))
    aspect_ratio: str | None = image_config.get("aspect_ratio") or None
    additional_prompt = image_config.get("additional_prompt", "")

    api_key = api_key or os.environ.get("GEMINI_API_KEY")

    logger.info(
        "Image Studio job %s: category=%s direction=%s count=%d aspect_ratio=%s",
        job_id, category, direction, count, aspect_ratio,
    )

    # --- Step 1: Preprocess ---
    db = get_db()
    try:
        job_service.update_status(
            db, job_id, status="strategy", progress=10,
            stage_name="preprocessing_images",
        )
    finally:
        db.close()

    product_data = await run_preprocess_for_image_studio(
        product_id=product_id,
        product_dir=product_dir,
        image_files=image_files,
        product_info=product_info,
    )

    # Resolve reference image paths (use compressed input images as references)
    ref_paths = [
        str(product_dir / fname)
        for fname in image_files
        if (product_dir / fname).exists()
    ]

    # --- Step 2: Generate images ---
    storage = get_storage()
    storage_job_dir = storage.job_dir(job_id)
    output_dir = storage_job_dir / "image_studio"
    output_dir.mkdir(parents=True, exist_ok=True)

    db = get_db()
    try:
        job_service.update_status(
            db, job_id, status="generating", progress=40,
            stage_name="generating_images",
        )
    finally:
        db.close()

    loop = asyncio.get_running_loop()
    image_urls: list[str] = []
    generated = 0
    failed = 0

    for variation_index in range(1, count + 1):
        prompt = _build_image_only_prompt(
            product_data=product_data,
            direction=direction,
            variation_index=variation_index,
            additional_prompt=additional_prompt,
            aspect_ratio=aspect_ratio,
        )

        logger.info(
            "Generating image %d/%d for job %s (direction=%s)",
            variation_index, count, job_id, direction,
        )

        try:
            image_bytes = await loop.run_in_executor(
                None,
                functools.partial(
                    generate_image_gemini,
                    prompt=prompt,
                    reference_image_paths=ref_paths if ref_paths else None,
                    resolution="1k",
                    api_key=api_key,
                ),
            )

            # Post-process: crop to aspect ratio
            image_bytes = _crop_to_aspect_ratio(image_bytes, aspect_ratio)

            # Save to persistent storage
            filename = f"{product_id}_{direction}_{variation_index}.png"
            image_path = output_dir / filename
            image_path.write_bytes(image_bytes)

            # Build stable URL
            rel = image_path.relative_to(storage_job_dir)
            url = f"/api/images/{job_id}/{str(rel).replace(chr(92), '/')}"
            image_urls.append(url)
            generated += 1

            # Update progress (40-95 range for image generation)
            progress = 40 + int(variation_index / count * 55)
            db = get_db()
            try:
                job_service.update_status(
                    db, job_id, status="generating", progress=progress,
                    stage_name=f"image_{variation_index}_of_{count}",
                )
            finally:
                db.close()

        except Exception as exc:
            logger.warning(
                "Failed to generate variation %d/%d for job %s: %s",
                variation_index, count, job_id, exc,
            )
            failed += 1

    logger.info(
        "Image Studio generation complete for job %s — %d generated, %d failed",
        job_id, generated, failed,
    )
    if generated == 0:
        raise RuntimeError(
            f"All {count} image generation attempts failed for job {job_id}"
        )
    return image_urls
