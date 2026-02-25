"""Tests for the persistent image storage service (DEC-002)."""

import tempfile
from pathlib import Path

import pytest

from app.services.storage import StorageService


@pytest.fixture
def tmp_storage(tmp_path: Path) -> StorageService:
    """Return a StorageService rooted at a temp directory."""
    return StorageService(base_path=str(tmp_path))


def test_job_dir_creates_directory(tmp_storage: StorageService):
    """job_dir() creates and returns the job directory."""
    d = tmp_storage.job_dir("job123")
    assert d.exists()
    assert d.is_dir()


def test_store_file_writes_bytes(tmp_storage: StorageService):
    """store_file() writes bytes to disk and returns a stable URL path."""
    url = tmp_storage.store_file("job1", "photo.png", b"fake-png-data")
    assert url == "/api/images/job1/photo.png"

    stored = tmp_storage.resolve("job1", "photo.png")
    assert stored.exists()
    assert stored.read_bytes() == b"fake-png-data"


def test_copy_file_copies_existing_file(tmp_storage: StorageService, tmp_path: Path):
    """copy_file() copies a file into storage and returns the URL path."""
    src = tmp_path / "original.png"
    src.write_bytes(b"image-content")

    url = tmp_storage.copy_file("job2", src)
    assert url == "/api/images/job2/original.png"

    dest = tmp_storage.resolve("job2", "original.png")
    assert dest.exists()
    assert dest.read_bytes() == b"image-content"


def test_copy_tree_copies_flat_directory(tmp_storage: StorageService, tmp_path: Path):
    """copy_tree() copies all files from a flat directory."""
    src_dir = tmp_path / "outputs"
    src_dir.mkdir()
    (src_dir / "a.png").write_bytes(b"a")
    (src_dir / "b.png").write_bytes(b"b")
    (src_dir / "c.png").write_bytes(b"c")

    urls = tmp_storage.copy_tree("job3", src_dir)
    assert len(urls) == 3
    assert "/api/images/job3/a.png" in urls
    assert "/api/images/job3/b.png" in urls
    assert "/api/images/job3/c.png" in urls


def test_copy_subtree_preserves_subdir(tmp_storage: StorageService, tmp_path: Path):
    """copy_subtree() copies files into a named subdirectory."""
    src_dir = tmp_path / "generated_1k"
    src_dir.mkdir()
    (src_dir / "hero.png").write_bytes(b"hero")

    urls = tmp_storage.copy_subtree("job4", src_dir, "generated_1k")
    assert len(urls) == 1
    assert urls[0] == "/api/images/job4/generated_1k/hero.png"

    dest = tmp_storage._base / "jobs" / "job4" / "generated_1k" / "hero.png"
    assert dest.exists()


def test_delete_job_removes_directory(tmp_storage: StorageService):
    """delete_job() removes all stored files for a job."""
    tmp_storage.store_file("job5", "img.png", b"data")
    assert tmp_storage.resolve("job5", "img.png").exists()

    tmp_storage.delete_job("job5")
    assert not (tmp_storage._base / "jobs" / "job5").exists()


def test_delete_job_noop_when_missing(tmp_storage: StorageService):
    """delete_job() does nothing if job directory doesn't exist."""
    # Should not raise
    tmp_storage.delete_job("nonexistent_job")


def test_url_to_path_round_trips(tmp_storage: StorageService):
    """url_to_path() converts a stable URL back to an absolute Path."""
    url = "/api/images/job6/subdir/img.png"
    path = tmp_storage.url_to_path(url)
    assert path is not None
    assert str(path).endswith("jobs/job6/subdir/img.png")


def test_url_to_path_returns_none_for_unknown_prefix(tmp_storage: StorageService):
    """url_to_path() returns None for unrecognised URL paths."""
    assert tmp_storage.url_to_path("/other/path/img.png") is None


def test_store_file_with_subdirectory(tmp_storage: StorageService):
    """store_file() creates intermediate directories when filename has slashes."""
    url = tmp_storage.store_file("job7", "generated_1k/hero.png", b"data")
    assert url == "/api/images/job7/generated_1k/hero.png"
    stored = tmp_storage._base / "jobs" / "job7" / "generated_1k" / "hero.png"
    assert stored.exists()
