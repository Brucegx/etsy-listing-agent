from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_save_requires_auth():
    """POST /api/save without cookies should return 401."""
    r = client.post(
        "/api/save",
        json={
            "drive_folder_id": "folder_abc",
            "product_id": "R001",
            "listing": {"title": "Test"},
        },
    )
    assert r.status_code == 401


@patch("app.api.save.DriveClient")
def test_save_uploads_listing(MockDriveClient):
    """POST /api/save with listing should upload to Drive."""
    mock_client = AsyncMock()
    MockDriveClient.return_value = mock_client
    mock_client.upload_file.return_value = {"id": "file_abc", "name": "R001_Listing.json"}

    r = client.post(
        "/api/save",
        json={
            "drive_folder_id": "folder_abc",
            "product_id": "R001",
            "listing": {"title": "Beautiful Ring", "tags": "ring, silver"},
        },
        cookies={"session": "google_123", "access_token": "test_token"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["type"] == "listing"
    assert data["uploaded"][0]["id"] == "file_abc"

    mock_client.upload_file.assert_called_once()
    call_kwargs = mock_client.upload_file.call_args
    assert call_kwargs.kwargs["name"] == "R001_Listing.json"
    assert call_kwargs.kwargs["folder_id"] == "folder_abc"


@patch("app.api.save.DriveClient")
def test_save_uploads_all_three(MockDriveClient):
    """POST /api/save with all result types should upload 3 files."""
    mock_client = AsyncMock()
    MockDriveClient.return_value = mock_client
    mock_client.upload_file.return_value = {"id": "file_xyz", "name": "test.json"}

    r = client.post(
        "/api/save",
        json={
            "drive_folder_id": "folder_abc",
            "product_id": "R001",
            "listing": {"title": "Ring"},
            "prompts": {"prompts": [{"type": "hero", "prompt": "A ring..."}]},
            "product_data": {"category": "rings"},
        },
        cookies={"session": "google_123", "access_token": "test_token"},
    )

    assert r.status_code == 200
    data = r.json()
    assert len(data["uploaded"]) == 3
    types = {u["type"] for u in data["uploaded"]}
    assert types == {"listing", "prompts", "product_data"}
    assert mock_client.upload_file.call_count == 3


@patch("app.api.save.DriveClient")
def test_save_skips_empty_fields(MockDriveClient):
    """POST /api/save with only product_id should upload nothing."""
    mock_client = AsyncMock()
    MockDriveClient.return_value = mock_client

    r = client.post(
        "/api/save",
        json={
            "drive_folder_id": "folder_abc",
            "product_id": "R001",
        },
        cookies={"session": "google_123", "access_token": "test_token"},
    )

    assert r.status_code == 200
    data = r.json()
    assert len(data["uploaded"]) == 0
    mock_client.upload_file.assert_not_called()
