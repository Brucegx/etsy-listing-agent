"""Persistent image storage service.

Provides a local-disk storage backend and an S3-compatible R2 backend
(DEC-002).  The ``get_storage()`` factory auto-detects which to use
based on the ``r2_endpoint_url`` config setting.

Local images are stored at: {base_path}/jobs/{job_id}/{filename}
R2 images are stored at:    s3://{bucket}/jobs/{job_id}/{filename}
Served at stable URLs:      /api/images/{job_id}/{filename}
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Manages persistent image storage for job outputs.

    The local backend writes files to ``{base_path}/jobs/{job_id}/``.
    When an S3 backend is needed, replace this class with one that uploads
    to S3 and returns pre-signed URLs; the interface stays the same.
    """

    def __init__(self, base_path: str | None = None) -> None:
        self._base = Path(base_path or settings.storage_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _job_dir(self, job_id: str) -> Path:
        return self._base / "jobs" / job_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def job_dir(self, job_id: str) -> Path:
        """Return (and create) the directory for a job's files."""
        d = self._job_dir(job_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store_file(self, job_id: str, filename: str, data: bytes) -> str:
        """Write raw bytes to storage and return the stable URL path.

        ``filename`` may contain forward slashes for subdirectories
        (e.g. ``generated_1k/hero.png``).  Intermediate directories are
        created automatically.

        Returns the URL path component (e.g. ``/api/images/{job_id}/{filename}``).
        The caller can prepend the host to form an absolute URL.
        """
        dest = self.job_dir(job_id) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.debug("Stored %s bytes → %s", len(data), dest)
        return f"/api/images/{job_id}/{filename}"

    def copy_file(self, job_id: str, src: Path) -> str:
        """Copy an existing file into storage and return the stable URL path."""
        dest = self.job_dir(job_id) / src.name
        shutil.copy2(src, dest)
        logger.debug("Copied %s → %s", src, dest)
        return f"/api/images/{job_id}/{src.name}"

    def copy_tree(self, job_id: str, src_dir: Path) -> list[str]:
        """Copy all files from src_dir into storage and return URL paths.

        Non-recursive: only copies files directly inside src_dir.
        For subdirectories (e.g. generated_1k/), use ``copy_subtree``.
        """
        urls: list[str] = []
        dest_dir = self.job_dir(job_id)
        for f in src_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, dest_dir / f.name)
                urls.append(f"/api/images/{job_id}/{f.name}")
        return urls

    def copy_subtree(self, job_id: str, src_dir: Path, subdir: str) -> list[str]:
        """Copy an entire subdirectory into storage/{job_id}/{subdir}/.

        Returns a list of stable URL paths for all copied files.
        """
        dest_dir = self.job_dir(job_id) / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        urls: list[str] = []
        for f in src_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, dest_dir / f.name)
                urls.append(f"/api/images/{job_id}/{subdir}/{f.name}")
        return urls

    def resolve(self, job_id: str, filename: str) -> Path:
        """Return the absolute path for a stored file (for serving)."""
        return self._job_dir(job_id) / filename

    def delete_job(self, job_id: str) -> None:
        """Delete all stored files for a job (for cleanup / error handling)."""
        d = self._job_dir(job_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            logger.info("Deleted storage for job %s", job_id)

    def url_to_path(self, url_path: str) -> Path | None:
        """Convert a stable URL path back to an absolute filesystem path.

        Accepts paths like ``/api/images/{job_id}/{filename}`` and returns the
        absolute Path, or None if the URL format is not recognised.
        """
        prefix = "/api/images/"
        if not url_path.startswith(prefix):
            return None
        relative = url_path[len(prefix):]
        return self._base / "jobs" / relative


class R2StorageService:
    """S3-compatible storage backend for Cloudflare R2.

    Implements the same public interface as ``StorageService`` so callers
    are backend-agnostic.  Files are uploaded to R2 and served via the
    R2 public URL (or a custom domain in front of it).
    """

    def __init__(self) -> None:
        import boto3

        self._bucket_name = settings.r2_bucket_name
        self._public_url = settings.r2_public_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, job_id: str, filename: str) -> str:
        return f"jobs/{job_id}/{filename}"

    def _content_type(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(ext, "application/octet-stream")

    # ------------------------------------------------------------------
    # Public API (mirrors StorageService)
    # ------------------------------------------------------------------

    def store_file(self, job_id: str, filename: str, data: bytes) -> str:
        key = self._key(job_id, filename)
        self._client.put_object(
            Bucket=self._bucket_name,
            Key=key,
            Body=data,
            ContentType=self._content_type(filename),
        )
        logger.debug("Stored %s bytes → R2 %s", len(data), key)
        return f"/api/images/{job_id}/{filename}"

    def copy_file(self, job_id: str, src: Path) -> str:
        return self.store_file(job_id, src.name, src.read_bytes())

    def copy_tree(self, job_id: str, src_dir: Path) -> list[str]:
        urls: list[str] = []
        for f in src_dir.iterdir():
            if f.is_file():
                urls.append(self.store_file(job_id, f.name, f.read_bytes()))
        return urls

    def copy_subtree(self, job_id: str, src_dir: Path, subdir: str) -> list[str]:
        urls: list[str] = []
        for f in src_dir.iterdir():
            if f.is_file():
                filename = f"{subdir}/{f.name}"
                urls.append(self.store_file(job_id, filename, f.read_bytes()))
        return urls

    def delete_job(self, job_id: str) -> None:
        prefix = f"jobs/{job_id}/"
        resp = self._client.list_objects_v2(
            Bucket=self._bucket_name, Prefix=prefix
        )
        objects = resp.get("Contents", [])
        if objects:
            self._client.delete_objects(
                Bucket=self._bucket_name,
                Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
            )
        logger.info("Deleted R2 objects for job %s (%d files)", job_id, len(objects))

    def get_public_url(self, job_id: str, filename: str) -> str:
        """Return the direct public URL for an R2 object."""
        return f"{self._public_url}/jobs/{job_id}/{filename}"

    def is_r2(self) -> bool:
        return True


# Module-level singleton — instantiated lazily so tests can override settings.
_storage: StorageService | R2StorageService | None = None


def get_storage() -> StorageService | R2StorageService:
    """Return the module-level storage singleton.

    Auto-detects R2 vs local based on ``settings.r2_endpoint_url``.
    """
    global _storage
    if _storage is None:
        if settings.r2_endpoint_url:
            _storage = R2StorageService()
            logger.info("Using R2 storage backend")
        else:
            _storage = StorageService()
            logger.info("Using local storage backend")
    return _storage
