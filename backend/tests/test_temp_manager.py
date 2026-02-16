"""Tests for TempManager delayed cleanup functionality."""

import time
from pathlib import Path

from app.services.temp_manager import TempManager, _cleanup_registry


def test_setup_creates_directory():
    """TempManager.setup creates the product directory."""
    tm = TempManager(base_dir="/tmp")
    product_dir = tm.setup("R001")
    try:
        assert product_dir.exists()
        assert product_dir.name == "R001"
    finally:
        tm.cleanup()


def test_cleanup_removes_directory():
    """TempManager.cleanup removes the temp directory."""
    tm = TempManager(base_dir="/tmp")
    tm.setup("R001")
    root = tm.root
    assert root.exists()
    tm.cleanup()
    assert not root.exists()


def test_schedule_cleanup_does_not_delete_immediately():
    """schedule_cleanup marks for later deletion, not immediate."""
    tm = TempManager(base_dir="/tmp")
    product_dir = tm.setup("R001")
    (product_dir / "test.png").write_bytes(b"fake image")

    tm.schedule_cleanup(ttl_seconds=3600)

    # Directory and files should still exist
    assert tm.root.exists()
    assert (product_dir / "test.png").exists()
    # Should be in registry
    assert tm.run_id in _cleanup_registry

    # Manual cleanup for test
    tm.cleanup()


def test_schedule_cleanup_registers_in_registry():
    """schedule_cleanup adds entry to _cleanup_registry."""
    tm = TempManager(base_dir="/tmp")
    tm.setup("R001")

    tm.schedule_cleanup(ttl_seconds=600)
    assert tm.run_id in _cleanup_registry
    root_path, expiry = _cleanup_registry[tm.run_id]
    assert root_path == tm.root
    assert expiry > time.time()

    tm.cleanup()


def test_cleanup_removes_from_registry():
    """cleanup() also removes the entry from _cleanup_registry."""
    tm = TempManager(base_dir="/tmp")
    tm.setup("R001")
    tm.schedule_cleanup(ttl_seconds=3600)
    assert tm.run_id in _cleanup_registry

    tm.cleanup()
    assert tm.run_id not in _cleanup_registry


def test_get_product_dir_returns_correct_path():
    """get_product_dir returns the expected path for a given run_id."""
    tm = TempManager(base_dir="/tmp")
    tm.setup("R001")
    try:
        result = TempManager.get_product_dir(tm.run_id, "R001", base_dir="/tmp")
        assert result == tm.product_dir
    finally:
        tm.cleanup()


def test_purge_expired_removes_old_dirs():
    """purge_expired cleans up dirs past their TTL."""
    tm = TempManager(base_dir="/tmp")
    tm.setup("R001")
    tm.schedule_cleanup(ttl_seconds=0)  # Already expired
    time.sleep(0.05)

    TempManager.purge_expired()
    assert not tm.root.exists()
    assert tm.run_id not in _cleanup_registry


def test_purge_expired_keeps_non_expired_dirs():
    """purge_expired does not remove dirs with future TTL."""
    tm = TempManager(base_dir="/tmp")
    tm.setup("R001")
    tm.schedule_cleanup(ttl_seconds=3600)  # Far future

    TempManager.purge_expired()
    assert tm.root.exists()
    assert tm.run_id in _cleanup_registry

    tm.cleanup()
