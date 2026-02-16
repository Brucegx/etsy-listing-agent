"""Tests for image serving endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.temp_manager import TempManager

# Minimal valid 1x1 PNG
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_with_image():
    """Create a TempManager with a fake generated image."""
    tm = TempManager()
    product_dir = tm.setup("R001")
    output_dir = product_dir / "generated_1k"
    output_dir.mkdir()
    (output_dir / "R001_00_hero_1k.png").write_bytes(PNG_BYTES)
    tm.schedule_cleanup(ttl_seconds=3600)
    yield tm
    tm.cleanup()


def test_serve_image_returns_png(client, temp_with_image):
    """GET /api/images/{run_id}/{product_id}/{path} returns the image."""
    tm = temp_with_image
    resp = client.get(f"/api/images/{tm.run_id}/R001/generated_1k/R001_00_hero_1k.png")
    assert resp.status_code == 200
    assert "image/png" in resp.headers["content-type"]
    assert resp.content == PNG_BYTES


def test_serve_image_404_for_missing_file(client):
    """GET /api/images with bad run_id returns 404."""
    resp = client.get("/api/images/badid/R001/generated_1k/missing.png")
    assert resp.status_code == 404


def test_serve_image_blocks_path_traversal(client, temp_with_image):
    """Path traversal attempts should be blocked."""
    tm = temp_with_image
    resp = client.get(f"/api/images/{tm.run_id}/R001/../../etc/passwd")
    assert resp.status_code == 404


def test_serve_jpeg_image(client):
    """Endpoint serves JPEG files with correct content type."""
    tm = TempManager()
    product_dir = tm.setup("R001")
    output_dir = product_dir / "generated_1k"
    output_dir.mkdir()
    (output_dir / "R001_01_wearing_1k.jpg").write_bytes(b"\xff\xd8\xff\xe0fake_jpeg")
    tm.schedule_cleanup(ttl_seconds=3600)

    resp = client.get(f"/api/images/{tm.run_id}/R001/generated_1k/R001_01_wearing_1k.jpg")
    assert resp.status_code == 200
    assert "image/jpeg" in resp.headers["content-type"]

    tm.cleanup()
