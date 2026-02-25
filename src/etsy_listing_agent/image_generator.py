#!/usr/bin/env python3
"""Gemini Image Generation for Etsy Listing Agent.

Generates product images using Gemini Batch API based on NanoBanana prompts.
Batch API is ~50% cheaper than synchronous calls and decouples generation from
the user session entirely (DEC-006).

Flow:
    1. Parse prompts from NanoBanana JSON file.
    2. Build a list of GenerateContentRequest dicts (one per image).
    3. Submit as a single batch job via client.batches.create().
    4. Poll client.batches.get() until the job reaches a terminal state.
    5. Collect inlined image responses and write them to persistent storage.

Synchronous fallback (generate_image_gemini) is retained for unit-test use
and the legacy SSE streaming path.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Gemini model used for image generation (DEC-001)
_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"

# Terminal states for a Gemini Batch job
_BATCH_TERMINAL_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}

# Seconds to wait between status polls when polling manually
_POLL_INTERVAL_SECONDS = 30


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
    """Parse NanoBanana prompts JSON file.

    Args:
        file_path: Absolute path to the _NanoBanana_Prompts.json file.

    Returns:
        List of PromptEntry objects in file order.
    """
    data = json.loads(file_path.read_text(encoding="utf-8"))
    entries: list[PromptEntry] = []

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


# ---------------------------------------------------------------------------
# Low-level synchronous helper (retained for legacy / unit-test use)
# ---------------------------------------------------------------------------


def generate_image_gemini(
    prompt: str,
    reference_image_paths: list[str] | None = None,
    resolution: str = "1k",
    api_key: str | None = None,
) -> bytes:
    """Generate a single image using the synchronous Gemini API.

    This is the original per-image synchronous approach.  It is kept for
    backwards compatibility with tests and the legacy SSE streaming path.
    For production batch generation use ``submit_image_batch`` instead.

    Args:
        prompt: Generation prompt text.
        reference_image_paths: Optional list of local reference image paths.
        resolution: "1k", "2k", or "4k" — mapped to Gemini ImageConfig sizes.
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).

    Returns:
        Raw PNG bytes of the generated image.

    Raises:
        ValueError: If no API key is available or no image was returned.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    size_map = {"1k": "1K", "2k": "2K", "4k": "4K"}

    contents: list[Any] = []

    # Add reference images as inline parts
    for ref_path in reference_image_paths or []:
        p = Path(ref_path)
        if p.exists():
            ext = p.suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            contents.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime_type))

    contents.append(prompt)

    response = client.models.generate_content(
        model=_IMAGE_MODEL,
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


# ---------------------------------------------------------------------------
# Batch API (DEC-006)
# ---------------------------------------------------------------------------


def _build_request_for_entry(
    entry: PromptEntry,
    product_dir: Path,
    resolution: str = "1k",
) -> dict[str, Any]:
    """Build a single GenerateContentRequest dict for a PromptEntry.

    The returned dict follows the Gemini Batch API inline-request schema
    (list of content dicts with role/parts).

    Args:
        entry: The NanoBanana prompt entry.
        product_dir: Directory containing reference images.
        resolution: Image size ("1k", "2k", "4k").

    Returns:
        A GenerateContentRequest dict suitable for ``client.batches.create(src=...)``.
    """
    size_map = {"1k": "1K", "2k": "2K", "4k": "4K"}
    image_size = size_map.get(resolution.lower(), "1K")

    parts: list[dict[str, Any]] = []

    # Embed reference images as inline base64 data
    for ref_name in entry.reference_images:
        ref_path = product_dir / ref_name
        if ref_path.exists():
            import base64
            ext = ref_path.suffix.lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            b64_data = base64.b64encode(ref_path.read_bytes()).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data,
                }
            })

    # Add the prompt text as the final part
    parts.append({"text": entry.prompt})

    return {
        "contents": [{"role": "user", "parts": parts}],
        "generation_config": {
            "response_modalities": ["TEXT", "IMAGE"],
            "image_generation_config": {"image_size": image_size},
        },
    }


def submit_image_batch(
    entries: list[PromptEntry],
    product_dir: Path,
    resolution: str = "1k",
    api_key: str | None = None,
    display_name: str = "etsy-listing-agent-batch",
) -> str:
    """Submit all prompt entries as a single Gemini Batch job.

    Args:
        entries: List of NanoBanana prompt entries to generate images for.
        product_dir: Directory containing reference images for the product.
        resolution: Image resolution — "1k", "2k", or "4k".
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).
        display_name: Human-readable name for the batch job.

    Returns:
        The batch job name (e.g. "batches/abc123") used to poll for results.

    Raises:
        ValueError: If no API key is available.
        RuntimeError: If batch creation fails.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)

    inline_requests = [
        _build_request_for_entry(entry, product_dir, resolution)
        for entry in entries
    ]

    logger.info(
        "Submitting Gemini batch with %d image requests (model=%s)",
        len(inline_requests),
        _IMAGE_MODEL,
    )

    batch_job = client.batches.create(
        model=_IMAGE_MODEL,
        src=inline_requests,
        config={"display_name": display_name},
    )

    logger.info("Batch job submitted: %s", batch_job.name)
    return batch_job.name


def poll_batch_until_done(
    batch_name: str,
    api_key: str | None = None,
    poll_interval: float = _POLL_INTERVAL_SECONDS,
    timeout: float = 86400.0,  # 24 hours — Gemini guarantees <24h turnaround
) -> Any:
    """Poll a Gemini Batch job until it reaches a terminal state.

    This is a blocking synchronous poll loop.  For async usage, run in a
    thread pool (``asyncio.get_event_loop().run_in_executor(None, ...)``) or
    use the async wrapper ``poll_batch_until_done_async``.

    Args:
        batch_name: The batch job name returned by ``submit_image_batch``.
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).
        poll_interval: Seconds between status checks (default 30s).
        timeout: Maximum total wait time in seconds (default 86400s / 24h).

    Returns:
        The completed BatchJob object.

    Raises:
        TimeoutError: If the job does not finish within ``timeout`` seconds.
        RuntimeError: If the job failed, was cancelled, or expired.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    elapsed = 0.0

    while elapsed < timeout:
        batch_job = client.batches.get(name=batch_name)
        state_name = batch_job.state.name if hasattr(batch_job.state, "name") else str(batch_job.state)

        logger.debug("Batch %s state: %s (elapsed %.0fs)", batch_name, state_name, elapsed)

        if state_name in _BATCH_TERMINAL_STATES:
            if state_name == "JOB_STATE_SUCCEEDED":
                logger.info("Batch %s succeeded after %.0fs", batch_name, elapsed)
                return batch_job
            else:
                raise RuntimeError(
                    f"Batch job {batch_name} ended with state {state_name}"
                )

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(
        f"Batch job {batch_name} did not complete within {timeout}s"
    )


async def poll_batch_until_done_async(
    batch_name: str,
    api_key: str | None = None,
    poll_interval: float = _POLL_INTERVAL_SECONDS,
    timeout: float = 86400.0,
) -> Any:
    """Async wrapper around ``poll_batch_until_done``.

    Runs the blocking poll in a thread-pool executor so it does not block
    the asyncio event loop used by the FastAPI background worker.

    Args:
        batch_name: The batch job name returned by ``submit_image_batch``.
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).
        poll_interval: Seconds between status checks.
        timeout: Maximum total wait time in seconds.

    Returns:
        The completed BatchJob object.
    """
    import asyncio
    import functools

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(
            poll_batch_until_done,
            batch_name,
            api_key=api_key,
            poll_interval=poll_interval,
            timeout=timeout,
        ),
    )


def collect_batch_images(
    batch_job: Any,
    entries: list[PromptEntry],
    output_dir: Path,
    product_id: str,
    resolution: str = "1k",
) -> dict[str, Any]:
    """Extract generated images from a completed batch job and save them.

    Each image is matched to its prompt entry by position (same order as
    the requests submitted to the batch).

    Args:
        batch_job: Completed BatchJob object from ``poll_batch_until_done``.
        entries: The same ordered list of PromptEntry objects used for submission.
        output_dir: Directory where generated images are saved.
        product_id: Product identifier used in output filenames.
        resolution: Resolution string for filename suffix.

    Returns:
        Result dict with ``generated`` and ``failed`` lists, each item
        containing ``index``, ``type``, and (on success) ``path``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {
        "success": True,
        "output_dir": str(output_dir),
        "generated": [],
        "failed": [],
    }

    responses = []
    if hasattr(batch_job, "dest") and batch_job.dest:
        if hasattr(batch_job.dest, "inlined_responses") and batch_job.dest.inlined_responses:
            responses = list(batch_job.dest.inlined_responses)

    for i, entry in enumerate(entries):
        safe_title = entry.type_en.replace("/", "_").replace(" ", "_")
        output_filename = f"{product_id}_{entry.index:02d}_{safe_title}_{resolution}.png"
        output_path = output_dir / output_filename

        if i >= len(responses):
            logger.warning("No response at index %d for entry %s", i, entry.type_en)
            results["failed"].append(
                {"index": entry.index, "type": entry.type_en, "error": "No response from batch"}
            )
            continue

        response_item = responses[i]
        # response_item may be a BatcGenerateContentResponse or raw dict
        image_data: bytes | None = None

        try:
            # Try structured response object first
            if hasattr(response_item, "response"):
                resp = response_item.response
                for candidate in resp.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data is not None:
                            image_data = part.inline_data.data
                            break
                    if image_data:
                        break
            elif isinstance(response_item, dict):
                # Raw dict from file-based batch response
                import base64
                candidates = response_item.get("response", {}).get("candidates", [])
                for candidate in candidates:
                    for part in candidate.get("content", {}).get("parts", []):
                        if "inlineData" in part:
                            image_data = base64.b64decode(part["inlineData"]["data"])
                            break
                    if image_data:
                        break
        except Exception as exc:
            logger.warning("Error extracting image for entry %s: %s", entry.type_en, exc)

        if image_data:
            output_path.write_bytes(image_data)
            logger.info("Saved batch image: %s", output_filename)
            results["generated"].append(
                {"index": entry.index, "type": entry.type_en, "path": str(output_path)}
            )
        else:
            logger.warning("No image data in batch response for entry %s", entry.type_en)
            results["failed"].append(
                {"index": entry.index, "type": entry.type_en, "error": "Empty image response"}
            )

    if results["failed"]:
        results["success"] = False

    return results


# ---------------------------------------------------------------------------
# High-level orchestration function
# ---------------------------------------------------------------------------


def generate_images_for_product(
    product_path: str,
    product_id: str,
    resolution: str = "1k",
    prompt_indices: list[int] | None = None,
    dry_run: bool = False,
    api_key: str | None = None,
    use_batch: bool = True,
    poll_interval: float = _POLL_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Generate all images for a product using the Gemini Batch API.

    This is the primary entry point called by the LangGraph image_gen node
    and the job worker.  By default it uses the Batch API (50% cheaper,
    async-by-nature).  Pass ``use_batch=False`` for legacy synchronous
    per-image generation (useful for interactive tests).

    Args:
        product_path: Path to the product directory.
        product_id: Product identifier (e.g. "R001").
        resolution: Image resolution — "1k", "2k", or "4k".
        prompt_indices: If set, only generate images for these prompt indices.
        dry_run: Skip actual API calls (logs what would be generated).
        api_key: Gemini API key (falls back to GEMINI_API_KEY env var).
        use_batch: Use Batch API (default True).  Set False for sync mode.
        poll_interval: Seconds between batch status polls.

    Returns:
        Result dict with keys: success, output_dir, generated, failed.
    """
    product_dir = Path(product_path)

    # Find prompts file
    prompts_file = product_dir / f"{product_id}_NanoBanana_Prompts.json"
    if not prompts_file.exists():
        return {"success": False, "error": f"Prompts file not found: {prompts_file}"}

    # Parse prompts
    entries = parse_nanobanana_json(prompts_file)
    logger.info("Parsed %d prompts from %s", len(entries), prompts_file.name)

    # Apply index filter
    if prompt_indices:
        entries = [e for e in entries if e.index in prompt_indices]

    # Create output directory
    output_dir = product_dir / f"generated_{resolution}"
    output_dir.mkdir(exist_ok=True)

    if dry_run:
        logger.info("[DRY RUN] Would generate %d images for %s", len(entries), product_id)
        return {
            "success": True,
            "output_dir": str(output_dir),
            "generated": [],
            "failed": [],
        }

    if use_batch:
        return _generate_images_batch(
            entries=entries,
            product_dir=product_dir,
            product_id=product_id,
            output_dir=output_dir,
            resolution=resolution,
            api_key=api_key,
            poll_interval=poll_interval,
        )
    else:
        return _generate_images_sync(
            entries=entries,
            product_dir=product_dir,
            product_id=product_id,
            output_dir=output_dir,
            resolution=resolution,
            api_key=api_key,
        )


def _generate_images_batch(
    entries: list[PromptEntry],
    product_dir: Path,
    product_id: str,
    output_dir: Path,
    resolution: str,
    api_key: str | None,
    poll_interval: float,
) -> dict[str, Any]:
    """Internal: submit batch + poll + collect results (synchronous)."""
    try:
        batch_name = submit_image_batch(
            entries=entries,
            product_dir=product_dir,
            resolution=resolution,
            api_key=api_key,
            display_name=f"etsy-agent-{product_id}",
        )

        batch_job = poll_batch_until_done(
            batch_name=batch_name,
            api_key=api_key,
            poll_interval=poll_interval,
        )

        results = collect_batch_images(
            batch_job=batch_job,
            entries=entries,
            output_dir=output_dir,
            product_id=product_id,
            resolution=resolution,
        )
        return results

    except Exception as exc:
        logger.exception("Batch image generation failed for product %s", product_id)
        return {
            "success": False,
            "output_dir": str(output_dir),
            "generated": [],
            "failed": [
                {"index": e.index, "type": e.type_en, "error": str(exc)}
                for e in entries
            ],
            "error": str(exc),
        }


def _generate_images_sync(
    entries: list[PromptEntry],
    product_dir: Path,
    product_id: str,
    output_dir: Path,
    resolution: str,
    api_key: str | None,
) -> dict[str, Any]:
    """Internal: legacy per-image synchronous generation (fallback)."""
    results: dict[str, Any] = {
        "success": True,
        "output_dir": str(output_dir),
        "generated": [],
        "failed": [],
    }

    for entry in entries:
        # Resolve reference image paths
        ref_paths: list[str] = []
        missing_refs: list[str] = []
        for ref_name in entry.reference_images:
            ref_path = product_dir / ref_name
            if ref_path.exists():
                ref_paths.append(str(ref_path))
            else:
                missing_refs.append(ref_name)

        if missing_refs:
            logger.warning("Reference images missing for %s: %s", entry.type_en, missing_refs)

        if not ref_paths and entry.reference_images:
            actual_files = sorted([f.name for f in product_dir.iterdir() if f.is_file()])
            raise FileNotFoundError(
                f"All reference images missing for {entry.type_en}. "
                f"Expected: {missing_refs}. Actual files: {actual_files}. "
                f"Product dir: {product_dir}"
            )

        try:
            image_data = generate_image_gemini(
                prompt=entry.prompt,
                reference_image_paths=ref_paths if ref_paths else None,
                resolution=resolution,
                api_key=api_key,
            )

            safe_title = entry.type_en.replace("/", "_").replace(" ", "_")
            output_filename = f"{product_id}_{entry.index:02d}_{safe_title}_{resolution}.png"
            output_path = output_dir / output_filename
            output_path.write_bytes(image_data)

            logger.info("Saved: %s", output_filename)
            results["generated"].append(
                {"index": entry.index, "type": entry.type_en, "path": str(output_path)}
            )

        except Exception as e:
            logger.warning("Failed to generate image %s: %s", entry.type_en, e)
            results["failed"].append(
                {"index": entry.index, "type": entry.type_en, "error": str(e)}
            )

    if results["failed"]:
        results["success"] = False

    return results
