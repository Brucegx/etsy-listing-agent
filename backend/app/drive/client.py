import json as json_module
import logging

import httpx

DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

logger = logging.getLogger(__name__)


class DriveClient:
    """Google Drive API wrapper using user's OAuth access token.

    All requests are authenticated with the bearer token supplied at
    construction time — results are always scoped to the token owner's Drive
    so we never accidentally return cached or cross-user data.
    """

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            # Disable any proxy-layer caching so we always get fresh Drive data
            "Cache-Control": "no-cache",
        }

    async def _request(self, url: str, params: dict | None = None) -> dict:
        """Make authenticated GET request to Drive API."""
        logger.debug("Drive API GET %s params=%s", url, params)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, params=params)
            if not resp.is_success:
                logger.error(
                    "Drive API error %s for %s: %s",
                    resp.status_code,
                    url,
                    resp.text[:500],
                )
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Drive API response keys: %s", list(data.keys()))
            return data

    async def _download(self, file_id: str) -> bytes:
        """Download file content by ID."""
        url = f"{DRIVE_API_BASE}/files/{file_id}"
        logger.debug("Drive download file_id=%s", file_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=self._headers,
                params={"alt": "media"},
            )
            if not resp.is_success:
                logger.error(
                    "Drive download error %s for file %s: %s",
                    resp.status_code,
                    file_id,
                    resp.text[:200],
                )
            resp.raise_for_status()
            return resp.content

    async def list_folders(self, parent_id: str | None = None) -> list[dict]:
        """List folders in the authenticated user's Drive.

        Folders are always filtered to ``'me' in owners`` so we only return
        folders that belong to the authenticated user — never shared/cached
        results from other users.

        Args:
            parent_id: If provided, only return folders directly under this
                       parent.  Otherwise returns top-level folders.

        Returns:
            List of folder metadata dicts with id, name, mimeType, modifiedTime.
            Sorted by most-recently-modified first so the dashboard shows current
            work at the top.
        """
        # Scope to the token owner's own folders to prevent stale/cross-user data
        query = (
            "mimeType='application/vnd.google-apps.folder'"
            " and trashed=false"
            " and 'me' in owners"
        )
        if parent_id:
            query += f" and '{parent_id}' in parents"

        logger.info("list_folders parent_id=%s query=%r", parent_id, query)

        data = await self._request(
            f"{DRIVE_API_BASE}/files",
            params={
                "q": query,
                "fields": "files(id,name,mimeType,modifiedTime)",
                # Most-recently-modified first — keeps dashboard current
                "orderBy": "modifiedTime desc",
                "pageSize": 100,
            },
        )
        folders = data.get("files", [])
        logger.info("list_folders returned %d folders", len(folders))
        return folders

    async def list_files(self, folder_id: str) -> list[dict]:
        """List all files directly inside a specific folder.

        Args:
            folder_id: The Google Drive folder ID.

        Returns:
            List of file metadata dicts with id, name, mimeType, size, modifiedTime.
            Sorted alphabetically by name for predictable display order.
        """
        logger.info("list_files folder_id=%s", folder_id)
        data = await self._request(
            f"{DRIVE_API_BASE}/files",
            params={
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "files(id,name,mimeType,size,modifiedTime)",
                "orderBy": "name",
                "pageSize": 200,
            },
        )
        files = data.get("files", [])
        logger.info("list_files folder_id=%s returned %d files", folder_id, len(files))
        return files

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
