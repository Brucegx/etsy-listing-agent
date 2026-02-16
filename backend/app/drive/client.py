import json as json_module

import httpx

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


class DriveClient:
    """Google Drive API wrapper using user's OAuth access token."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def _request(self, url: str, params: dict | None = None) -> dict:
        """Make authenticated GET request to Drive API."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _download(self, file_id: str) -> bytes:
        """Download file content by ID."""
        url = f"{DRIVE_API_BASE}/files/{file_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers,
                params={"alt": "media"},
            )
            resp.raise_for_status()
            return resp.content

    async def list_folders(self, parent_id: str | None = None) -> list[dict]:
        """List folders, optionally filtered to a parent folder.

        Args:
            parent_id: If provided, only return folders under this parent.

        Returns:
            List of folder metadata dicts with id, name, mimeType, modifiedTime.
        """
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        data = await self._request(
            f"{DRIVE_API_BASE}/files",
            params={
                "q": query,
                "fields": "files(id,name,mimeType,modifiedTime)",
                "orderBy": "name",
                "pageSize": 100,
            },
        )
        return data.get("files", [])

    async def list_files(self, folder_id: str) -> list[dict]:
        """List all files in a specific folder.

        Args:
            folder_id: The Google Drive folder ID.

        Returns:
            List of file metadata dicts with id, name, mimeType, size, modifiedTime.
        """
        data = await self._request(
            f"{DRIVE_API_BASE}/files",
            params={
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "files(id,name,mimeType,size,modifiedTime)",
                "orderBy": "name",
                "pageSize": 200,
            },
        )
        return data.get("files", [])

    async def download_file(self, file_id: str) -> bytes:
        """Download a file's content by ID.

        Args:
            file_id: The Google Drive file ID.

        Returns:
            Raw file bytes.
        """
        return await self._download(file_id)

    async def download_google_sheet_as_xlsx(self, file_id: str) -> bytes:
        """Export a Google Sheet as xlsx format.

        Args:
            file_id: The Google Drive file ID of the Sheet.

        Returns:
            Raw xlsx bytes.
        """
        url = f"{DRIVE_API_BASE}/files/{file_id}/export"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers,
                params={
                    "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
            )
            resp.raise_for_status()
            return resp.content

    async def upload_file(
        self,
        name: str,
        content: bytes,
        folder_id: str,
        mime_type: str = "application/json",
    ) -> dict:
        """Upload a file to a Drive folder.

        Args:
            name: Filename for the uploaded file.
            content: Raw file bytes.
            folder_id: Target folder ID in Drive.
            mime_type: MIME type of the file content.

        Returns:
            Dict with id and name of the created file.
        """
        metadata = {"name": name, "parents": [folder_id]}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.googleapis.com/upload/drive/v3/files",
                headers={**self._headers},
                params={"uploadType": "multipart", "fields": "id,name"},
                files={
                    "metadata": (
                        "metadata",
                        json_module.dumps(metadata),
                        "application/json",
                    ),
                    "file": (name, content, mime_type),
                },
            )
            resp.raise_for_status()
            return resp.json()
