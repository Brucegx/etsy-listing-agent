"""Persistent image storage service.

Provides a local-disk storage backend with an interface designed for
S3 drop-in replacement later (DEC-002).

Images are stored at: {base_path}/jobs/{job_id}/{filename}
Served at stable URLs:  /api/images/{job_id}/{filename}
"""

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


# Module-level singleton — instantiated lazily so tests can override settings.
_storage: StorageService | None = None


def get_storage() -> StorageService:
    """Return the module-level StorageService singleton."""
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage
