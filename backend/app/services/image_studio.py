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

import asyncio
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


# ---------------------------------------------------------------------------
# NanoBanana 5-Module Prompt Architecture — Helper functions
# ---------------------------------------------------------------------------

# Scene / background modules (F-series)
_SCENE_F1 = "clean light background (white, cream, or soft beige), minimal studio setup"
_SCENE_F2 = "dark moody background, rich deep tones, dramatic atmosphere"
_SCENE_F3 = "velvet or silk surface, soft romantic texture, warm ambient glow"
_SCENE_F4 = "natural linen or woven textile surface, organic earthy tones"
_SCENE_F5 = "marble or stone surface, cool natural texture, neutral tones"

# Prop modules (G-series)
_PROP_G1 = "a small natural shell placed nearby as a soft accent"
_PROP_G2 = "a few dried flower petals scattered around, complementing the product"
_PROP_G3 = "a smooth stone tray or small slate slab as a display surface"
_PROP_G4 = "a delicate satin ribbon loosely arranged alongside the product"
_PROP_G5 = "a thin dried branch or twig providing organic visual contrast"

# Pose modules for earrings (A-series)
_POSE_A1 = "model facing camera directly, head level, ear clearly visible from front"
_POSE_A4 = "model with gentle three-quarter turn, earring fully visible in profile"
_POSE_B1 = "model's face slightly tilted, hair swept back, earring prominently displayed"

# Pose modules for rings (A/D-series)
_POSE_A2 = "hand elegantly extended toward camera, fingers together, ring centered"
_POSE_A3 = "hand resting palm-down on a neutral surface, ring facing camera"
_POSE_D1 = "fingers interlaced, ring hand on top, close-up of knuckles and ring"
_POSE_D2 = "single hand touching chin or cheek, ring clearly visible"
_POSE_D3 = "hand holding a small prop (flower, book edge), ring in focus"
_POSE_D4 = "wrist and hand framed from side, ring visible on finger"

# Pose modules for necklaces (B-series)
_POSE_B3 = "collarbone and décolletage visible, necklace centered on neck, shoulders relaxed"

# Pose modules for bracelets (C-series)
_POSE_C1 = "wrist extended forward, bracelet centered, hand relaxed"
_POSE_C2 = "wrist turned slightly to show bracelet clasp and full circumference"
_POSE_C3 = "both wrists together, bracelet on one, drawing eye to the piece"


def _detect_material(product_data: dict[str, Any]) -> str:
    """Detect the primary material type from product_data.

    Args:
        product_data: Parsed product_data dict from preprocess_node.

    Returns:
        One of: "gold", "silver", "pearl", "gemstone", "enamel",
                "moissanite", "mixed".
    """
    materials_raw: list[str] = product_data.get("materials", [])
    materials_lower = " ".join(str(m).lower() for m in materials_raw)

    if "enamel" in materials_lower:
        return "enamel"
    if "moissanite" in materials_lower:
        return "moissanite"
    if "pearl" in materials_lower:
        return "pearl"
    if "gemstone" in materials_lower or "crystal" in materials_lower or "sapphire" in materials_lower or "ruby" in materials_lower or "emerald" in materials_lower or "topaz" in materials_lower or "opal" in materials_lower:
        return "gemstone"
    if "gold" in materials_lower or "brass" in materials_lower or "vermeil" in materials_lower:
        if "silver" in materials_lower or "rhodium" in materials_lower:
            return "mixed"
        return "gold"
    if "silver" in materials_lower or "rhodium" in materials_lower or "platinum" in materials_lower or "steel" in materials_lower:
        return "silver"
    return "gold"  # default for jewelry


def _detect_earring_type(product_data: dict[str, Any]) -> str:
    """Classify earring style for angle selection.

    Args:
        product_data: Parsed product_data dict from preprocess_node.

    Returns:
        One of: "flat_front", "3d_sculptural", "drop_dangle".
    """
    category = str(product_data.get("category", "")).lower()
    style = str(product_data.get("style", "")).lower()
    materials_raw: list[str] = product_data.get("materials", [])
    materials_lower = " ".join(str(m).lower() for m in materials_raw)
    combined = f"{category} {style} {materials_lower}"

    if any(kw in combined for kw in ("enamel", "polymer", "clay", "resin", "acrylic")):
        return "flat_front"
    if any(kw in combined for kw in ("dangle", "drop", "chain", "tassel", "chandelier")):
        return "drop_dangle"
    if any(kw in combined for kw in ("bead", "sphere", "woven", "knot", "ball", "orb")):
        return "3d_sculptural"
    return "3d_sculptural"


def _is_enamel(product_data: dict[str, Any]) -> bool:
    """Return True if the product uses enamel as a material.

    Args:
        product_data: Parsed product_data dict from preprocess_node.

    Returns:
        True if enamel is detected.
    """
    materials_raw: list[str] = product_data.get("materials", [])
    materials_lower = " ".join(str(m).lower() for m in materials_raw)
    return "enamel" in materials_lower


def _get_physics_keywords(material: str, direction: str) -> str:
    """Return PHYSICS & REALISM module text for the given material and direction.

    Args:
        material: Material type string from _detect_material().
        direction: NanoBanana direction string.

    Returns:
        Full PHYSICS & REALISM module text.
    """
    material_physics: dict[str, str] = {
        "gold": "Fresnel reflections, specular highlights, warm bounce light",
        "silver": "Fresnel reflections, cool metallic sheen",
        "pearl": "Subsurface scattering, iridescent luster, soft inner glow",
        "gemstone": "Caustics, fire and dispersion, refraction through facets",
        "enamel": "Smooth glossy reflections, depth of color in the enamel layer",
        "moissanite": "Fire, light dispersion, spectral color splitting",
        "mixed": "Fresnel reflections, dual-tone specular highlights, material contrast",
    }
    physics = material_physics.get(material, "Fresnel reflections, specular highlights")

    lines: list[str] = [
        f"PHYSICS & REALISM: {physics}.",
        "Contact shadow on the surface beneath the product.",
        "Ambient occlusion where product meets surface.",
    ]

    # Enamel texture fidelity
    if material == "enamel":
        lines.append(
            "All enamel textures preserved from the original reference image. "
            "Lighting emphasizes the enamel's luminosity exactly as shown."
        )

    # Anti-AI-plastic grain (skip for macro shots — looks like dirt at micro scale)
    if direction != "macro_detail":
        lines.append("Film grain, ISO 800 noise, raw camera file quality.")

    return "\n".join(lines)


def _get_lighting(material: str, direction: str) -> str:
    """Return LIGHTING module text for the given material and direction.

    Args:
        material: Material type string from _detect_material().
        direction: NanoBanana direction string.

    Returns:
        Full LIGHTING module text.
    """
    if direction == "hero":
        return "LIGHTING: Clean studio softbox lighting, even illumination, no harsh shadows."
    if direction == "macro_detail":
        return "LIGHTING: Focused studio lighting, sharp detail illumination, controlled highlights."

    material_lighting: dict[str, str] = {
        "gold": "LIGHTING: L4 — warm golden hour sunlight, honeyed amber lighting tone, soft fill from opposite side.",
        "silver": "LIGHTING: L2 — directional window light, cool rim light accent, subtle blue-grey tones.",
        "pearl": "LIGHTING: L1 — soft diffused natural daylight, gentle window light, even and shadow-free.",
        "gemstone": "LIGHTING: L3 — strong single-source side lighting, dramatic chiaroscuro to reveal depth and fire.",
        "enamel": "LIGHTING: L1 — soft diffused even light, no harsh shadows, to reveal enamel color uniformly.",
        "moissanite": "LIGHTING: L3 — strong single-source side lighting, dramatic contrast to maximize dispersion and fire.",
        "mixed": "LIGHTING: L3 with L1 fill — directional key light, soft diffused fill to flatter both metal and stone.",
    }
    return material_lighting.get(
        material,
        "LIGHTING: L1 — soft diffused natural daylight, gentle window light.",
    )


def _get_camera(product_data: dict[str, Any], direction: str) -> str:
    """Return CAMERA module text based on product size and direction.

    Args:
        product_data: Parsed product_data dict from preprocess_node.
        direction: NanoBanana direction string.

    Returns:
        Full CAMERA module text.
    """
    dimensions = str(product_data.get("product_size", {}).get("dimensions", "")).lower()

    # Estimate size category from dimensions string
    is_very_small = any(kw in dimensions for kw in ("1cm", "0.", "tiny", "petite", "stud"))
    is_medium_large = any(kw in dimensions for kw in ("10cm", "12cm", "15cm", "large"))

    # Direction-specific apertures
    aperture_map: dict[str, str] = {
        "hero": "f/8",
        "macro_detail": "f/2.8 to f/5.6",
        "scene_daily": "f/2.8",
        "wearing_a": "f/2.8",
    }
    aperture = aperture_map.get(direction, "f/2.8")

    if direction == "macro_detail" or is_very_small:
        lens = "macro lens"
        aperture = "f/2.8 to f/5.6"
    elif is_medium_large:
        lens = "50mm to 85mm lens"
    else:
        lens = "85mm lens"

    return f"CAMERA: {lens}, {aperture} aperture, sharp focus on the product."


def _get_scene_context(
    product_data: dict[str, Any],
    direction: str,
    variation_index: int,
    additional_prompt: str,
    aspect_ratio: str | None,
) -> str:
    """Build the SCENE CONTEXT module for the given direction and product.

    Args:
        product_data: Parsed product_data dict from preprocess_node.
        direction: NanoBanana direction string.
        variation_index: 1-based variation index.
        additional_prompt: Free-text extra instructions from the user.
        aspect_ratio: Requested aspect ratio or None.

    Returns:
        Full SCENE CONTEXT module text.
    """
    category = str(product_data.get("category", "jewelry")).strip()
    style = str(product_data.get("style", "")).strip()
    dimensions = str(product_data.get("product_size", {}).get("dimensions", "")).strip()
    materials_list: list[str] = product_data.get("materials", [])
    materials_str = ", ".join(str(m) for m in materials_list) if materials_list else ""
    is_enamel = _is_enamel(product_data)
    category_lower = category.lower()

    # Build a rich product descriptor: "sterling silver, cubic zirconia rings"
    if materials_str:
        product_desc = f"{materials_str} {category}"
    else:
        product_desc = category

    size_phrase = f"approximately {dimensions}" if dimensions else "approximately standard jewelry size"

    # Aspect ratio instruction
    ar_note = ""
    if aspect_ratio and aspect_ratio in VALID_ASPECT_RATIOS:
        ar_note = f" Compose image for a {aspect_ratio} aspect ratio."

    # Variation hint
    variation_hint = _get_variation_hint(variation_index)
    variation_note = f" {variation_hint}" if variation_hint else ""

    # Additional user instructions
    extra_note = f" {additional_prompt.strip()}" if additional_prompt and additional_prompt.strip() else ""

    if direction == "hero":
        lines = [
            f"SCENE CONTEXT: The {product_desc}, {size_phrase}, is centered on a clean LIGHT background (white, cream, or soft beige).",
            "No hands, no fingers.",
            "Pure studio setup — no props, no distractions.",
            "Product fills most of the frame, perfectly centered.",
        ]
        if style:
            lines.append(f"Style: {style}.")
        lines.append(f"{ar_note}{variation_note}{extra_note}".strip())
        return "\n".join(line for line in lines if line.strip())

    if direction == "scene_daily":
        # Select scene and props based on style
        style_lower = style.lower()
        if any(kw in style_lower for kw in ("minimalist", "simple", "clean", "modern")):
            scene = _SCENE_F1
            prop1 = _PROP_G3
            prop2 = _PROP_G2
        elif any(kw in style_lower for kw in ("vintage", "bohemian", "boho", "folk", "rustic")):
            scene = _SCENE_F4
            prop1 = _PROP_G5
            prop2 = _PROP_G1
        elif any(kw in style_lower for kw in ("luxury", "elegant", "glamour", "glam", "opulent")):
            scene = _SCENE_F2
            prop1 = _PROP_G3
            prop2 = _PROP_G4
        elif any(kw in style_lower for kw in ("romantic", "soft", "feminine", "delicate")):
            scene = _SCENE_F3
            prop1 = _PROP_G4
            prop2 = _PROP_G1
        else:
            scene = _SCENE_F1
            prop1 = _PROP_G3
            prop2 = _PROP_G2

        lines = [
            f"SCENE CONTEXT: The {product_desc}, {size_phrase}, is sitting firmly on {scene}.",
            f"Styled alongside: {prop1}; and {prop2}.",
            "Lifestyle mood — warm, inviting, aspirational.",
        ]
        if style:
            lines.append(f"Visual style: {style}.")
        lines.append(f"{ar_note}{variation_note}{extra_note}".strip())
        return "\n".join(line for line in lines if line.strip())

    if direction == "wearing_a":
        # Select pose based on product category
        if "earring" in category_lower or "ear" in category_lower:
            earring_type = _detect_earring_type(product_data)
            if earring_type == "flat_front":
                angle_rule = "Face turned only 10-20 degrees from camera, showing the full front design of the earring."
                pose = _POSE_A1
            elif earring_type == "drop_dangle":
                angle_rule = "Side angle to display full vertical length of the earring, head slightly tilted."
                pose = _POSE_B1
            else:  # 3d_sculptural
                angle_rule = "Three-quarter view showing the dimensional form of the earring."
                pose = _POSE_A4
            pose_desc = f"{pose} {angle_rule}"
        elif "ring" in category_lower:
            _poses = [_POSE_A2, _POSE_A3, _POSE_D1, _POSE_D2]
            pose_desc = _poses[(variation_index - 1) % len(_poses)]
        elif "necklace" in category_lower or "pendant" in category_lower or "chain" in category_lower:
            pose_desc = _POSE_B3
        elif "bracelet" in category_lower or "bangle" in category_lower or "cuff" in category_lower:
            _poses = [_POSE_C1, _POSE_C2, _POSE_C3, _POSE_D4]
            pose_desc = _poses[(variation_index - 1) % len(_poses)]
        else:
            pose_desc = "Model wearing the product, elegant natural pose, product clearly visible."

        lines = [
            f"SCENE CONTEXT: A model is wearing the {product_desc}, {size_phrase}.",
            f"Pose: {pose_desc}",
            "Minimalist backdrop only — no location keywords, no identifiable environment.",
            "Model's skin and hair are secondary; the product is the hero.",
        ]
        if style:
            lines.append(f"Style mood: {style}.")
        lines.append(f"{ar_note}{variation_note}{extra_note}".strip())
        return "\n".join(line for line in lines if line.strip())

    if direction == "macro_detail":
        enamel_note = ""
        if is_enamel:
            enamel_note = (
                "Lighting emphasizes the enamel's luminosity and patterns exactly as shown in "
                "reference image. Razor sharp focus, 8K detail, all enamel textures preserved from the original."
            )

        lines = [
            f"SCENE CONTEXT: Extreme close-up macro of the {product_desc}, {size_phrase}.",
            "Fills the entire frame — craftsmanship, surface texture, and material details are the subject.",
            "Sharp focus throughout the visible product surface.",
        ]
        if enamel_note:
            lines.append(enamel_note)
        if style:
            lines.append(f"Visual character: {style}.")
        lines.append(f"{ar_note}{variation_note}{extra_note}".strip())
        return "\n".join(line for line in lines if line.strip())

    # Fallback for unknown directions
    return (
        f"SCENE CONTEXT: The {product_desc}, {size_phrase}, is displayed in a clean studio setting."
        f"{ar_note}{variation_note}{extra_note}"
    )


def _build_image_only_prompt(
    product_data: dict[str, Any],
    direction: str,
    variation_index: int,
    additional_prompt: str,
    aspect_ratio: str | None,
) -> str:
    """Build a self-contained Gemini image prompt using the NanoBanana 5-module architecture.

    The five modules are assembled in order:
      1. REFERENCE ANCHOR — identity lock (≤3 lines, ends with "Rigid constraint.")
      2. SCENE CONTEXT — environment, pose, size, variation, and user hints
      3. LIGHTING — material-appropriate lighting setup
      4. CAMERA — lens and aperture based on size and direction
      5. PHYSICS & REALISM — material physics + anti-AI-plastic modifiers

    Args:
        product_data: Output of preprocess_node (product_data.json content).
        direction: NanoBanana direction string (e.g. "hero", "scene_daily").
        variation_index: 1-based variation counter for this direction.
        additional_prompt: Free-text extra instructions from the user.
        aspect_ratio: Requested aspect ratio ("1:1", "3:4", "4:3", or None).

    Returns:
        Complete prompt string with all 5 NanoBanana modules.
    """
    category = str(product_data.get("category", "jewelry piece")).strip()
    material = _detect_material(product_data)
    is_enamel_product = _is_enamel(product_data)

    # -----------------------------------------------------------------------
    # Module 1: REFERENCE ANCHOR
    # Identity lock — NOT an instruction manual, ≤3 lines, ends rigid constraint.
    # For enamel: do NOT describe the enamel pattern.
    # -----------------------------------------------------------------------
    if is_enamel_product:
        anchor = (
            f"REFERENCE ANCHOR: The input image depicts a {category}.\n"
            "Maintain exact structural integrity, color palette, and material finish.\n"
            "Do not alter the product's geometry. Rigid constraint."
        )
    else:
        anchor = (
            f"REFERENCE ANCHOR: The input image depicts a {category}.\n"
            "Maintain exact structural integrity, color palette, and material finish.\n"
            "Do not alter the product's geometry. Rigid constraint."
        )

    # -----------------------------------------------------------------------
    # Module 2: SCENE CONTEXT
    # -----------------------------------------------------------------------
    scene_context = _get_scene_context(
        product_data=product_data,
        direction=direction,
        variation_index=variation_index,
        additional_prompt=additional_prompt,
        aspect_ratio=aspect_ratio,
    )

    # -----------------------------------------------------------------------
    # Module 3: LIGHTING
    # -----------------------------------------------------------------------
    lighting = _get_lighting(material=material, direction=direction)

    # -----------------------------------------------------------------------
    # Module 4: CAMERA
    # -----------------------------------------------------------------------
    camera = _get_camera(product_data=product_data, direction=direction)

    # -----------------------------------------------------------------------
    # Module 5: PHYSICS & REALISM
    # -----------------------------------------------------------------------
    physics = _get_physics_keywords(material=material, direction=direction)

    # -----------------------------------------------------------------------
    # Assemble final prompt
    # -----------------------------------------------------------------------
    prompt = "\n\n".join([
        "Single product photograph (NOT a collage or grid).",
        anchor,
        scene_context,
        lighting,
        camera,
        physics,
    ])
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
    image_model: str = image_config.get("model", "gemini-3-pro-image-preview")
    resolution: str = image_config.get("resolution", "2k")

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

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                image_bytes = await loop.run_in_executor(
                    None,
                    functools.partial(
                        generate_image_gemini,
                        prompt=prompt,
                        reference_image_paths=ref_paths if ref_paths else None,
                        resolution=resolution,
                        api_key=api_key,
                        model=image_model,
                    ),
                )

                # Post-process: crop to aspect ratio
                image_bytes = _crop_to_aspect_ratio(image_bytes, aspect_ratio)

                # Save to storage
                filename = f"{product_id}_{direction}_{variation_index}.png"
                storage_filename = f"image_studio/{filename}"
                url = storage.store_file(job_id, storage_filename, image_bytes)
                image_urls.append(url)
                generated += 1

                # Save prompt alongside the image for admin debugging
                prompts_path = output_dir / "prompts.json"
                existing_prompts: dict[str, str] = {}
                if prompts_path.exists():
                    try:
                        existing_prompts = json.loads(prompts_path.read_text())
                    except json.JSONDecodeError:
                        existing_prompts = {}
                existing_prompts[filename] = prompt
                storage.store_file(
                    job_id,
                    "image_studio/prompts.json",
                    json.dumps(existing_prompts, ensure_ascii=False, indent=2).encode(),
                )

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
                break  # success, no more retries

            except Exception as exc:
                if attempt < max_retries:
                    logger.warning(
                        "Attempt %d/%d failed for variation %d of job %s: %s — retrying",
                        attempt, max_retries, variation_index, job_id, exc,
                    )
                    await asyncio.sleep(2 * attempt)  # backoff
                else:
                    logger.warning(
                        "Failed to generate variation %d/%d for job %s after %d attempts: %s",
                        variation_index, count, job_id, max_retries, exc,
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

    # --- Deduct credits for successfully generated images only ---
    user_id: int | None = image_config.get("user_id")
    if user_id is not None and generated > 0:
        from app.services.credit_service import calculate_job_cost, deduct_credits

        actual_cost = calculate_job_cost(image_model, resolution, generated)
        db = get_db()
        try:
            deduct_credits(db, user_id, actual_cost)
        finally:
            db.close()
        logger.info(
            "Deducted %d credits for %d successfully generated images (job %s, user %d)",
            actual_cost, generated, job_id, user_id,
        )

    return image_urls
