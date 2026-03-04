"""Tests for the Image Studio service and API endpoint (Phase 6A).

Covers:
  - _crop_to_aspect_ratio: Pillow post-processing
  - _build_image_only_prompt: prompt construction
  - _get_variation_hint: variation hint selection
  - CATEGORY_TO_DIRECTION mapping
  - POST /api/jobs/image-studio: input validation + job creation
  - JobService.create_job: job_type / image_config / product_info fields
"""

import io
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import _sign_session
from app.deps import _anon_store
from app.main import app
from app.models import Base
from app.models.job import (
    Job,
    JOB_STATUS_QUEUED,
    JOB_TYPE_FULL_LISTING,
    JOB_TYPE_IMAGE_ONLY,
)
from app.models.user import User
from app.services.image_studio import (
    CATEGORY_TO_DIRECTION,
    VALID_ASPECT_RATIOS,
    _build_image_only_prompt,
    _crop_to_aspect_ratio,
    _get_variation_hint,
)
from app.services.job_service import JobService

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _create_user(session_factory, google_id: str = "test_studio_1") -> User:
    s = session_factory()
    user = User(
        google_id=google_id,
        email=f"{google_id}@example.com",
        name="Studio User",
    )
    s.add(user)
    s.commit()
    s.refresh(user)
    s.close()
    return user


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create minimal valid PNG bytes for testing."""
    img = Image.new("RGB", (width, height), color=(200, 150, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit tests: _get_variation_hint
# ---------------------------------------------------------------------------


def test_variation_hint_index_1_is_empty():
    assert _get_variation_hint(1) == ""


def test_variation_hint_index_2_is_set():
    hint = _get_variation_hint(2)
    assert hint != ""
    assert len(hint) > 5


def test_variation_hint_high_index_uses_fallback():
    hint = _get_variation_hint(99)
    assert "99" in hint or "Variation" in hint


# ---------------------------------------------------------------------------
# Unit tests: CATEGORY_TO_DIRECTION mapping
# ---------------------------------------------------------------------------


def test_category_mapping_white_bg():
    assert CATEGORY_TO_DIRECTION["white_bg"] == "hero"


def test_category_mapping_scene():
    assert CATEGORY_TO_DIRECTION["scene"] == "scene_daily"


def test_category_mapping_model():
    assert CATEGORY_TO_DIRECTION["model"] == "wearing_a"


def test_category_mapping_detail():
    assert CATEGORY_TO_DIRECTION["detail"] == "macro_detail"


# ---------------------------------------------------------------------------
# Unit tests: _build_image_only_prompt
# ---------------------------------------------------------------------------


_SAMPLE_PRODUCT_DATA = {
    "category": "rings",
    "materials": ["sterling silver", "cubic zirconia"],
    "style": "minimalist",
    "product_size": {"dimensions": "US 7"},
    "selling_points": ["hypoallergenic", "tarnish-resistant"],
    "reference_anchor": "REFERENCE ANCHOR: Silver ring with round stone.",
}


def test_build_prompt_contains_category():
    prompt = _build_image_only_prompt(
        product_data=_SAMPLE_PRODUCT_DATA,
        direction="hero",
        variation_index=1,
        additional_prompt="",
        aspect_ratio=None,
    )
    assert "rings" in prompt.lower() or "hero" in prompt.lower()


def test_build_prompt_contains_materials():
    prompt = _build_image_only_prompt(
        product_data=_SAMPLE_PRODUCT_DATA,
        direction="hero",
        variation_index=1,
        additional_prompt="",
        aspect_ratio=None,
    )
    assert "sterling silver" in prompt.lower()


def test_build_prompt_includes_additional_prompt():
    prompt = _build_image_only_prompt(
        product_data=_SAMPLE_PRODUCT_DATA,
        direction="hero",
        variation_index=1,
        additional_prompt="Add a floral background",
        aspect_ratio=None,
    )
    assert "floral background" in prompt.lower()


def test_build_prompt_includes_aspect_ratio_instruction():
    prompt = _build_image_only_prompt(
        product_data=_SAMPLE_PRODUCT_DATA,
        direction="hero",
        variation_index=1,
        additional_prompt="",
        aspect_ratio="1:1",
    )
    assert "1:1" in prompt


def test_build_prompt_includes_reference_anchor():
    prompt = _build_image_only_prompt(
        product_data=_SAMPLE_PRODUCT_DATA,
        direction="hero",
        variation_index=1,
        additional_prompt="",
        aspect_ratio=None,
    )
    assert "REFERENCE ANCHOR" in prompt


def test_build_prompt_variation_2_includes_hint():
    prompt = _build_image_only_prompt(
        product_data=_SAMPLE_PRODUCT_DATA,
        direction="scene_daily",
        variation_index=2,
        additional_prompt="",
        aspect_ratio=None,
    )
    # Variation 2 should include a variation note
    assert "Variation note" in prompt or "angle" in prompt.lower()


def test_build_prompt_no_crash_with_empty_product_data():
    prompt = _build_image_only_prompt(
        product_data={},
        direction="hero",
        variation_index=1,
        additional_prompt="",
        aspect_ratio=None,
    )
    assert isinstance(prompt, str)
    assert len(prompt) > 10


# ---------------------------------------------------------------------------
# Unit tests: _crop_to_aspect_ratio
# ---------------------------------------------------------------------------


def test_crop_no_ratio_returns_unchanged():
    original = _make_png_bytes(200, 150)
    result = _crop_to_aspect_ratio(original, None)
    assert result == original


def test_crop_invalid_ratio_returns_unchanged():
    original = _make_png_bytes(200, 150)
    result = _crop_to_aspect_ratio(original, "2:3")
    assert result == original


def test_crop_1_1_produces_square():
    original = _make_png_bytes(200, 150)
    result = _crop_to_aspect_ratio(original, "1:1")
    img = Image.open(io.BytesIO(result))
    w, h = img.size
    assert w == h, f"Expected square, got {w}x{h}"
    # Shorter dimension of 200x150 is 150
    assert w == 150


def test_crop_1_1_square_input_unchanged_dimensions():
    original = _make_png_bytes(100, 100)
    result = _crop_to_aspect_ratio(original, "1:1")
    img = Image.open(io.BytesIO(result))
    assert img.size == (100, 100)


def test_crop_3_4_portrait():
    """3:4 → height > width. Starting from 300x300 → should produce 300x400? No:
    we can only crop, not expand. So from 300x300, 3:4 portrait:
    target_w = 300, target_h = 400 → exceeds h (300), so clamp:
    target_h = 300, target_w = int(300*3/4) = 225.
    """
    original = _make_png_bytes(300, 300)
    result = _crop_to_aspect_ratio(original, "3:4")
    img = Image.open(io.BytesIO(result))
    w, h = img.size
    # Should be 225x300 (portrait orientation: taller than wide)
    assert h >= w, f"Portrait expected (h>=w), got {w}x{h}"
    assert abs(w / h - 3 / 4) < 0.02, f"Expected ~3:4 ratio, got {w}:{h}"


def test_crop_4_3_landscape():
    """4:3 → width > height. From 300x300:
    target_h = 300, target_w = 400 → exceeds w (300), clamp:
    target_w = 300, target_h = int(300*3/4) = 225.
    """
    original = _make_png_bytes(300, 300)
    result = _crop_to_aspect_ratio(original, "4:3")
    img = Image.open(io.BytesIO(result))
    w, h = img.size
    assert w >= h, f"Landscape expected (w>=h), got {w}x{h}"
    assert abs(w / h - 4 / 3) < 0.02, f"Expected ~4:3 ratio, got {w}:{h}"


def test_crop_result_is_valid_png():
    original = _make_png_bytes(200, 150)
    result = _crop_to_aspect_ratio(original, "1:1")
    img = Image.open(io.BytesIO(result))
    assert img.format == "PNG"


# ---------------------------------------------------------------------------
# Unit tests: JobService with new fields
# ---------------------------------------------------------------------------


def test_job_service_create_full_listing_default():
    sf = _make_test_db()
    svc = JobService()
    s = sf()
    job = svc.create_job(s, "R001", user_id=None)
    assert job.job_type == JOB_TYPE_FULL_LISTING
    assert job.image_config is None
    assert job.product_info is None
    s.close()


def test_job_service_create_image_only():
    sf = _make_test_db()
    svc = JobService()
    s = sf()
    config = {"category": "white_bg", "count": 2, "aspect_ratio": "1:1"}
    job = svc.create_job(
        s,
        "studio_abc",
        user_id=None,
        job_type=JOB_TYPE_IMAGE_ONLY,
        image_config=config,
        product_info="A silver ring",
    )
    assert job.job_type == JOB_TYPE_IMAGE_ONLY
    assert job.image_config == config
    assert job.product_info == "A silver ring"
    s.close()


def test_job_service_image_config_persists():
    sf = _make_test_db()
    svc = JobService()
    s = sf()
    config = {"category": "scene", "count": 4, "aspect_ratio": "4:3", "additional_prompt": "forest"}
    job = svc.create_job(s, "P002", job_type=JOB_TYPE_IMAGE_ONLY, image_config=config)
    fetched = svc.get_by_job_id(s, job.job_id)
    assert fetched is not None
    assert fetched.image_config["category"] == "scene"
    assert fetched.image_config["additional_prompt"] == "forest"
    s.close()


# ---------------------------------------------------------------------------
# API tests: POST /api/jobs/image-studio
# ---------------------------------------------------------------------------


def _make_auth_cookie(user: User) -> dict:
    token = _sign_session({"user_id": user.id, "email": user.email})
    return {"session": token}


def _png_upload(name: str = "test.png", width: int = 100, height: int = 100):
    """Create an UploadFile-compatible tuple for TestClient."""
    return (name, _make_png_bytes(width, height), "image/png")


@pytest.fixture()
def test_db_and_user():
    """Fixture: in-memory DB + user, patched into the app."""
    sf = _make_test_db()
    user = _create_user(sf)

    with patch("app.deps.get_db", return_value=sf()), \
         patch("app.api.jobs.get_db", return_value=sf()), \
         patch("app.services.job_service.JobService.create_job",
               wraps=JobService().create_job) as _create_mock:
        yield sf, user


def test_image_studio_missing_images():
    """No images → 422 validation error."""
    response = client.post(
        "/api/jobs/image-studio",
        data={"category": "white_bg"},
    )
    assert response.status_code == 422


def test_image_studio_invalid_category(tmp_path):
    """Bad category → 400."""
    png = _make_png_bytes()
    response = client.post(
        "/api/jobs/image-studio",
        files=[("images", ("img.png", png, "image/png"))],
        data={"category": "invalid_cat"},
    )
    assert response.status_code == 400
    assert "category" in response.json()["detail"].lower()


def test_image_studio_invalid_aspect_ratio(tmp_path):
    """Bad aspect_ratio → 400."""
    png = _make_png_bytes()
    response = client.post(
        "/api/jobs/image-studio",
        files=[("images", ("img.png", png, "image/png"))],
        data={"category": "white_bg", "aspect_ratio": "2:3"},
    )
    assert response.status_code == 400
    assert "aspect_ratio" in response.json()["detail"].lower()


def test_image_studio_too_many_files():
    """More than 10 images → 400."""
    files = [("images", (f"img{i}.png", _make_png_bytes(), "image/png")) for i in range(11)]
    response = client.post(
        "/api/jobs/image-studio",
        files=files,
        data={"category": "white_bg"},
    )
    assert response.status_code == 400
    assert "maximum" in response.json()["detail"].lower()


def test_image_studio_valid_submission_queued(tmp_path):
    """Valid submission → 200 with job_id, background task triggered."""
    png = _make_png_bytes()

    mock_job = MagicMock()
    mock_job.job_id = uuid.uuid4().hex

    with patch("app.api.jobs._job_service.create_job", return_value=mock_job), \
         patch("app.api.jobs.get_db", return_value=MagicMock()), \
         patch("app.api.jobs.TempManager") as MockTemp, \
         patch("asyncio.create_task"):

        mock_temp_instance = MagicMock()
        mock_temp_instance.setup.return_value = tmp_path
        MockTemp.return_value = mock_temp_instance

        response = client.post(
            "/api/jobs/image-studio",
            files=[("images", ("ring.png", png, "image/png"))],
            data={
                "category": "white_bg",
                "count": "2",
                "aspect_ratio": "1:1",
                "additional_prompt": "bright studio lighting",
                "product_info": "Silver ring",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_image_studio_valid_count_range():
    """count out of 1-8 range → FastAPI validation error (422)."""
    png = _make_png_bytes()
    response = client.post(
        "/api/jobs/image-studio",
        files=[("images", ("img.png", png, "image/png"))],
        data={"category": "scene", "count": "0"},
    )
    assert response.status_code == 422


def test_image_studio_count_too_high():
    png = _make_png_bytes()
    response = client.post(
        "/api/jobs/image-studio",
        files=[("images", ("img.png", png, "image/png"))],
        data={"category": "scene", "count": "9"},
    )
    assert response.status_code == 422


def test_image_studio_empty_aspect_ratio_accepted(tmp_path):
    """Empty aspect_ratio string is valid (means no crop)."""
    png = _make_png_bytes()

    mock_job = MagicMock()
    mock_job.job_id = uuid.uuid4().hex

    with patch("app.api.jobs._job_service.create_job", return_value=mock_job), \
         patch("app.api.jobs.get_db", return_value=MagicMock()), \
         patch("app.api.jobs.TempManager") as MockTemp, \
         patch("asyncio.create_task"):

        mock_temp_instance = MagicMock()
        mock_temp_instance.setup.return_value = tmp_path
        MockTemp.return_value = mock_temp_instance

        response = client.post(
            "/api/jobs/image-studio",
            files=[("images", ("img.png", png, "image/png"))],
            data={"category": "detail", "aspect_ratio": ""},
        )

    assert response.status_code == 200


def test_image_studio_all_valid_categories(tmp_path):
    """Each valid category should be accepted."""
    # Clear anonymous rate-limit state accumulated by earlier tests in this file
    _anon_store.clear()

    valid_cats = ["white_bg", "scene", "model", "detail"]
    png = _make_png_bytes()

    for cat in valid_cats:
        mock_job = MagicMock()
        mock_job.job_id = uuid.uuid4().hex

        with patch("app.api.jobs._job_service.create_job", return_value=mock_job), \
             patch("app.api.jobs.get_db", return_value=MagicMock()), \
             patch("app.api.jobs.TempManager") as MockTemp, \
             patch("asyncio.create_task"):

            mock_temp_instance = MagicMock()
            mock_temp_instance.setup.return_value = tmp_path
            MockTemp.return_value = mock_temp_instance

            response = client.post(
                "/api/jobs/image-studio",
                files=[("images", ("img.png", png, "image/png"))],
                data={"category": cat},
            )

        assert response.status_code == 200, f"Category {cat!r} rejected: {response.json()}"
