"""Tests for WorkflowRunner."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.workflow_runner import WorkflowRunner


def test_workflow_runner_creates_initial_state():
    """WorkflowRunner.build_state creates a valid ProductState."""
    runner = WorkflowRunner()
    state = runner.build_state(
        product_id="R001",
        product_path="/tmp/R001",
        category="rings",
        excel_row={"款号": "R001", "材质": "925银"},
        image_files=["img1.jpg", "img2.jpg"],
    )
    assert state["product_id"] == "R001"
    assert state["category"] == "rings"
    assert state["stage"] == "pending"
    assert state["max_retries"] == 3


@pytest.mark.asyncio
async def test_run_with_events_emits_image_events():
    """WorkflowRunner emits image_complete and image_done SSE events."""
    runner = WorkflowRunner()

    # Mock the graph to emit an image_gen node update
    image_gen_update = {
        "image_gen": {
            "stage": "image_gen_complete",
            "image_gen_result": {
                "success": True,
                "generated": [
                    {"index": 0, "type": "hero", "path": "/tmp/etsy_agent_abc123/R001/generated_1k/R001_00_hero_1k.png"},
                    {"index": 1, "type": "wearing_a", "path": "/tmp/etsy_agent_abc123/R001/generated_1k/R001_01_wearing_a_1k.png"},
                ],
                "failed": [],
            },
        }
    }

    async def mock_stream(*args, **kwargs):
        yield image_gen_update

    runner._graph = MagicMock()
    runner._graph.astream = mock_stream

    state = runner.build_state(
        product_id="R001",
        product_path="/tmp/etsy_agent_abc123/R001",
        category="rings",
        excel_row={},
        image_files=[],
        generate_images=True,
    )

    events = []
    async for event in runner.run_with_events(state, run_id="abc123"):
        events.append(event)

    event_types = [e["event"] for e in events]
    assert "image_complete" in event_types
    assert "image_done" in event_types

    # Check image_complete events
    img_completes = [e for e in events if e["event"] == "image_complete"]
    assert len(img_completes) == 2
    assert img_completes[0]["data"]["direction"] == "hero"
    assert "/api/images/abc123/" in img_completes[0]["data"]["url"]

    # Check image_done event
    img_done = [e for e in events if e["event"] == "image_done"][0]
    assert img_done["data"]["total"] == 2
    assert img_done["data"]["failed"] == 0


@pytest.mark.asyncio
async def test_run_with_events_without_run_id():
    """WorkflowRunner works without run_id (backward compatible)."""
    runner = WorkflowRunner()

    async def mock_stream(*args, **kwargs):
        yield {"listing": {"stage": "listing"}}

    runner._graph = MagicMock()
    runner._graph.astream = mock_stream

    state = runner.build_state(
        product_id="R001",
        product_path="/tmp/R001",
        category="rings",
        excel_row={},
        image_files=[],
    )

    events = []
    async for event in runner.run_with_events(state):
        events.append(event)

    # Should have start, progress, complete
    event_types = [e["event"] for e in events]
    assert "start" in event_types
    assert "progress" in event_types
    assert "complete" in event_types
