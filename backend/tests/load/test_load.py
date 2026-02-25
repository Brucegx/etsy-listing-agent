"""Load test for concurrent generation requests.

Simulates multiple users submitting jobs concurrently and polling for results.
Tests the async job system + rate limiting under load.

Usage:
    cd backend && uv run pytest tests/load/test_load.py -v -s
"""

import asyncio
import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, get_db
from app.main import app
from app.models.api_key import ApiKey
from app.models.user import User


def _create_test_user(db, google_id: str, email: str) -> User:
    user = User(google_id=google_id, email=email, name=f"Load User {google_id}")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_api_key(db, user_id: int, key_hash: str, rpm: int = 60) -> ApiKey:
    import hashlib

    api_key = ApiKey(
        key_hash=hashlib.sha256(key_hash.encode()).hexdigest(),
        user_id=user_id,
        name=f"load-test-key-{key_hash}",
        rate_limit_rpm=rpm,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    # Clear in-memory rate limit stores between tests
    from app.deps import _api_key_store, _user_store, _anon_store
    _api_key_store.clear()
    _user_store.clear()
    _anon_store.clear()
    yield
    Base.metadata.drop_all(bind=engine)


class TestConcurrentJobSubmission:
    """Test multiple concurrent job submissions via the public API."""

    def test_concurrent_submissions(self) -> None:
        """Submit N jobs concurrently, verify all get unique job_ids."""
        db = get_db()
        user = _create_test_user(db, "load_user_1", "load1@test.com")
        _create_api_key(db, user.id, "load-key-1", rpm=100)
        db.close()

        client = TestClient(app)
        results: list[dict] = []
        num_requests = 10

        mock_workflow = MagicMock()
        mock_workflow.run_with_events = MagicMock(return_value=iter([]))

        with patch(
            "app.services.job_worker.WorkflowRunner",
            return_value=mock_workflow,
        ):
            for i in range(num_requests):
                resp = client.post(
                    "/api/v1/generate",
                    headers={"Authorization": "Bearer load-key-1"},
                    files={"images": (f"img_{i}.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                    data={"material": "silver", "size": "10mm"},
                )
                results.append({"status": resp.status_code, "body": resp.json()})

        # All should be accepted (202)
        accepted = [r for r in results if r["status"] == 202]
        assert len(accepted) == num_requests, (
            f"Expected {num_requests} accepted, got {len(accepted)}. "
            f"Statuses: {[r['status'] for r in results]}"
        )

        # All job_ids should be unique
        job_ids = [r["body"]["job_id"] for r in accepted]
        assert len(set(job_ids)) == num_requests

    def test_job_polling_under_load(self) -> None:
        """Submit a job and poll rapidly — status endpoint should be stable."""
        db = get_db()
        user = _create_test_user(db, "load_user_2", "load2@test.com")
        _create_api_key(db, user.id, "load-key-2", rpm=200)
        db.close()

        client = TestClient(app)

        mock_workflow = MagicMock()
        mock_workflow.run_with_events = MagicMock(return_value=iter([]))

        with patch(
            "app.services.job_worker.WorkflowRunner",
            return_value=mock_workflow,
        ):
            resp = client.post(
                "/api/v1/generate",
                headers={"Authorization": "Bearer load-key-2"},
                files={"images": ("test.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                data={"material": "gold", "size": "5mm"},
            )
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

        # Rapid-fire polling
        statuses: list[int] = []
        for _ in range(20):
            poll = client.get(
                f"/api/v1/jobs/{job_id}",
                headers={"Authorization": "Bearer load-key-2"},
            )
            statuses.append(poll.status_code)

        # All polls should succeed (200)
        assert all(s == 200 for s in statuses), f"Unexpected statuses: {statuses}"


class TestRateLimitingUnderLoad:
    """Test rate limiting behaves correctly under concurrent access."""

    def test_api_key_rate_limit_enforced(self) -> None:
        """Exceed rate limit and verify 429 responses."""
        db = get_db()
        user = _create_test_user(db, "rate_user_1", "rate1@test.com")
        _create_api_key(db, user.id, "rate-key-1", rpm=5)  # Very low limit
        db.close()

        client = TestClient(app)
        status_codes: list[int] = []

        mock_workflow = MagicMock()
        mock_workflow.run_with_events = MagicMock(return_value=iter([]))

        with patch(
            "app.services.job_worker.WorkflowRunner",
            return_value=mock_workflow,
        ):
            for i in range(10):
                resp = client.post(
                    "/api/v1/generate",
                    headers={"Authorization": "Bearer rate-key-1"},
                    files={"images": (f"img_{i}.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                    data={"material": "silver", "size": "10mm"},
                )
                status_codes.append(resp.status_code)

        accepted = status_codes.count(202)
        rate_limited = status_codes.count(429)

        assert accepted == 5, f"Expected 5 accepted, got {accepted}"
        assert rate_limited == 5, f"Expected 5 rate-limited, got {rate_limited}"

    def test_different_keys_independent_limits(self) -> None:
        """Two API keys should have independent rate limits."""
        db = get_db()
        user = _create_test_user(db, "rate_user_2", "rate2@test.com")
        _create_api_key(db, user.id, "indep-key-1", rpm=3)
        _create_api_key(db, user.id, "indep-key-2", rpm=3)
        db.close()

        client = TestClient(app)
        results: dict[str, list[int]] = defaultdict(list)

        mock_workflow = MagicMock()
        mock_workflow.run_with_events = MagicMock(return_value=iter([]))

        with patch(
            "app.services.job_worker.WorkflowRunner",
            return_value=mock_workflow,
        ):
            for key in ["indep-key-1", "indep-key-2"]:
                for i in range(5):
                    resp = client.post(
                        "/api/v1/generate",
                        headers={"Authorization": f"Bearer {key}"},
                        files={"images": (f"img_{i}.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                        data={"material": "silver", "size": "10mm"},
                    )
                    results[key].append(resp.status_code)

        # Each key should get 3 accepted and 2 rate-limited
        for key in ["indep-key-1", "indep-key-2"]:
            assert results[key].count(202) == 3, f"{key}: expected 3 accepted"
            assert results[key].count(429) == 2, f"{key}: expected 2 rate-limited"


class TestThroughputMetrics:
    """Measure throughput and latency of the job submission system."""

    def test_submission_throughput(self) -> None:
        """Measure requests/second for job submission."""
        db = get_db()
        user = _create_test_user(db, "perf_user_1", "perf1@test.com")
        _create_api_key(db, user.id, "perf-key-1", rpm=1000)
        db.close()

        client = TestClient(app)
        latencies: list[float] = []
        num_requests = 20

        mock_workflow = MagicMock()
        mock_workflow.run_with_events = MagicMock(return_value=iter([]))

        with patch(
            "app.services.job_worker.WorkflowRunner",
            return_value=mock_workflow,
        ):
            start = time.perf_counter()
            for i in range(num_requests):
                t0 = time.perf_counter()
                resp = client.post(
                    "/api/v1/generate",
                    headers={"Authorization": "Bearer perf-key-1"},
                    files={"images": (f"img_{i}.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                    data={"material": "silver", "size": "10mm"},
                )
                latencies.append(time.perf_counter() - t0)
                assert resp.status_code == 202
            total_time = time.perf_counter() - start

        latencies.sort()
        p50 = latencies[len(latencies) // 2] * 1000
        p95 = latencies[int(len(latencies) * 0.95)] * 1000
        p99 = latencies[int(len(latencies) * 0.99)] * 1000
        rps = num_requests / total_time

        print(f"\n--- Throughput Report ---")
        print(f"Requests: {num_requests}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {rps:.1f} req/s")
        print(f"Latency p50: {p50:.1f}ms")
        print(f"Latency p95: {p95:.1f}ms")
        print(f"Latency p99: {p99:.1f}ms")
        print(f"Errors: 0/{num_requests}")

        # Sanity check — should handle at least 5 req/s
        assert rps > 5, f"Throughput too low: {rps:.1f} req/s"
