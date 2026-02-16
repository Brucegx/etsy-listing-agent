"""Integration tests for the image generation flow."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.temp_manager import TempManager


# Minimal valid PNG header
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client():
    return TestClient(app)


def test_image_endpoint_serves_generated_files(client):
    """Full flow: create temp dir with images, serve via API."""
    tm = TempManager()
    product_dir = tm.setup("R001")
    output_dir = product_dir / "generated_1k"
    output_dir.mkdir()

    fake_image = PNG_HEADER + b"\x00" * 100
    (output_dir / "R001_00_hero_1k.png").write_bytes(fake_image)
    (output_dir / "R001_01_wearing_a_1k.png").write_bytes(fake_image)

    tm.schedule_cleanup(ttl_seconds=3600)

    # Both images should be servable
    for filename in ["R001_00_hero_1k.png", "R001_01_wearing_a_1k.png"]:
        resp = client.get(f"/api/images/{tm.run_id}/R001/generated_1k/{filename}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == fake_image

    tm.cleanup()


def test_expired_temp_dirs_purged_on_request(client):
    """Expired temp dirs get purged when a new image request comes in."""
    tm = TempManager()
    product_dir = tm.setup("R001")
    output_dir = product_dir / "generated_1k"
    output_dir.mkdir()
    (output_dir / "R001_00_hero_1k.png").write_bytes(PNG_HEADER)

    # Schedule with 0 TTL (already expired)
    tm.schedule_cleanup(ttl_seconds=0)
    time.sleep(0.05)

    # Request triggers purge — the dir no longer exists, so 404
    resp = client.get(f"/api/images/{tm.run_id}/R001/generated_1k/R001_00_hero_1k.png")
    assert resp.status_code == 404
    assert not tm.root.exists()


def test_generate_request_defaults_images_true(client):
    """SingleGenerateRequest defaults generate_images to True."""
    from app.api.generate import SingleGenerateRequest

    req = SingleGenerateRequest(
        drive_folder_id="folder_1",
        product_id="R001",
        category="rings",
        excel_file_id="excel_1",
    )
    assert req.generate_images is True


def test_multiple_concurrent_temp_dirs(client):
    """Multiple TempManagers can coexist with independent cleanup."""
    tm1 = TempManager()
    tm2 = TempManager()

    dir1 = tm1.setup("R001")
    dir2 = tm2.setup("R002")

    (dir1 / "generated_1k").mkdir()
    (dir1 / "generated_1k" / "test.png").write_bytes(PNG_HEADER)
    (dir2 / "generated_1k").mkdir()
    (dir2 / "generated_1k" / "test.png").write_bytes(PNG_HEADER)

    tm1.schedule_cleanup(ttl_seconds=0)  # Expire tm1
    tm2.schedule_cleanup(ttl_seconds=3600)  # Keep tm2

    time.sleep(0.05)
    TempManager.purge_expired()

    # tm1 should be gone
    assert not tm1.root.exists()

    # tm2 should still be accessible
    resp = client.get(f"/api/images/{tm2.run_id}/R002/generated_1k/test.png")
    assert resp.status_code == 200

    tm2.cleanup()
