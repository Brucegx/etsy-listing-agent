from unittest.mock import patch, AsyncMock

import pytest

from app.drive.client import DriveClient


@pytest.fixture
def drive_client():
    return DriveClient(access_token="fake_token")


@pytest.mark.asyncio
async def test_list_folders(drive_client):
    """DriveClient.list_folders returns folder list."""
    mock_response = {
        "files": [
            {"id": "folder_1", "name": "rings", "mimeType": "application/vnd.google-apps.folder"},
            {"id": "folder_2", "name": "earrings", "mimeType": "application/vnd.google-apps.folder"},
        ]
    }
    with patch.object(drive_client, "_request", new_callable=AsyncMock, return_value=mock_response):
        folders = await drive_client.list_folders()
        assert len(folders) == 2
        assert folders[0]["name"] == "rings"


@pytest.mark.asyncio
async def test_list_files_in_folder(drive_client):
    """DriveClient.list_files returns files in a folder."""
    mock_response = {
        "files": [
            {"id": "file_1", "name": "products.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            {"id": "file_2", "name": "image1.jpg", "mimeType": "image/jpeg"},
        ]
    }
    with patch.object(drive_client, "_request", new_callable=AsyncMock, return_value=mock_response):
        files = await drive_client.list_files(folder_id="folder_1")
        assert len(files) == 2


@pytest.mark.asyncio
async def test_download_file(drive_client):
    """DriveClient.download_file returns file bytes."""
    mock_bytes = b"fake excel content"
    with patch.object(drive_client, "_download", new_callable=AsyncMock, return_value=mock_bytes):
        data = await drive_client.download_file(file_id="file_1")
        assert data == mock_bytes
