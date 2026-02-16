# Integration tests using real R001 sample data
# TDD: Full workflow end-to-end tests
# V3: Updated for strategy stage + 10 prompts (fan-out via MiniMax)

import json
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock

from etsy_listing_agent.workflow import create_workflow
from etsy_listing_agent.state import create_initial_state, ReviewLevel
from etsy_listing_agent.excel_loader import load_excel_row


# Path to real R001 sample data
SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "R001"


# ===== Mock Data Helpers =====

def _patch_product_data(data: dict) -> dict:
    """Ensure product_data has V3 required fields (visual_features, selling_points, reference_anchor)."""
    if "visual_features" not in data:
        data["visual_features"] = {
            "material_finish": "metallic",
            "color_tone": "cool",
            "surface_quality": "engraved",
            "light_interaction": "reflective",
        }
    if "selling_points" not in data:
        data["selling_points"] = [
            {"feature": "Traditional craftsmanship", "benefit": "Authentic handmade quality"},
            {"feature": "Sterling silver material", "benefit": "Durable and hypoallergenic"},
        ]
    if "reference_anchor" not in data:
        data["reference_anchor"] = (
            "REFERENCE ANCHOR: The input image depicts a Tibetan mantra ring in 925 sterling silver.\n"
            "Maintain exact structural integrity, engraved Sanskrit mantras, oxidized silver band, and material finish.\n"
            "Do not alter the product's geometry. Rigid constraint."
        )
    return data


def _make_mock_strategy(product_id: str = "R001") -> dict:
    """Create a valid strategy JSON for mocking."""
    types_10 = [
        "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
        "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
    ]
    return {
        "$schema": "image_strategy",
        "product_id": product_id,
        "analysis": {
            "product_usps": "Tibetan spiritual significance",
            "target_customer": "Spiritually-minded jewelry buyer",
            "purchase_barriers": "Size uncertainty",
            "competitive_gap": "Authentic craftsmanship",
        },
        "slots": [
            {
                "slot": i + 1,
                "type": t,
                "category": "required" if i < 5 else "strategic",
                "description": f"Test slot {i+1} for {t}",
                "rationale": "Test rationale",
            }
            for i, t in enumerate(types_10)
        ],
    }


def _make_mock_prompt_text(direction: str) -> str:
    """Create a valid prompt text (4 modules only — ANCHOR is prepended by prompt_node)."""
    anti_ai = "film grain, dust particles, micro-scratches"
    if direction in ("macro_detail", "packaging"):
        anti_ai = "clean commercial lighting"
    return (
        f"SCENE CONTEXT: 1:1 aspect ratio. The ring, approximately 18mm band, "
        f"rests on a surface. {direction} shot composition.\n\n"
        f"LIGHTING: L1 soft diffused from above-right.\n\n"
        f"CAMERA: 85mm, f/8, shallow DOF.\n\n"
        f"PHYSICS & REALISM: Fresnel reflections, {anti_ai}."
    )


async def _mock_agentic_loop(*args, **kwargs):
    """Mock agentic_loop for prompt_node — returns prompt text in agentic format."""
    user_msg = kwargs.get("user_message", args[1] if len(args) > 1 else "")
    direction = "hero"
    for d in ["hero", "size_reference", "wearing_a", "wearing_b",
              "macro_detail", "art_still_life", "scene_daily",
              "workshop", "art_abstract", "packaging"]:
        if f"Direction: {d}" in user_msg:
            direction = d
            break
    return {
        "text": _make_mock_prompt_text(direction),
        "cost_usd": 0.001,
        "usage_metadata": {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300, "turns": 2},
        "model": "MiniMax-M2.1",
    }


async def _mock_minimax_listing(r001_listing):
    """Create a mock for call_minimax that only handles listing calls."""
    async def _inner(*args, **kwargs):
        return {
            "text": json.dumps(r001_listing),
            "cost_usd": 0.001,
            "usage_metadata": {"input_tokens": 100, "output_tokens": 200},
        }
    return _inner


def _make_mock_claude(r001_product_data, strategy=None):
    """Create a mock for call_claude that handles preprocess and strategy.

    Preprocess and strategy nodes call call_claude directly (not call_claude_agent).
    Returns dict with {text, usage_metadata, cost_usd, model}.
    """
    call_count = 0

    async def _inner(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        trace = kwargs.get("trace_name", "")
        if "Preprocess" in trace or call_count == 1:
            text = json.dumps(_patch_product_data(r001_product_data))
        else:
            text = json.dumps(strategy or _make_mock_strategy())
        return {
            "text": text,
            "usage_metadata": {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300},
            "cost_usd": 0.04,
            "model": "claude-sonnet-4-20250514",
        }

    return _inner


# ===== Fixtures =====


@pytest.fixture
def r001_config():
    """Load R001 sample config"""
    with open(SAMPLES_DIR / "config.json") as f:
        return json.load(f)


@pytest.fixture
def r001_input(r001_config):
    """Load real R001 data from Excel file"""
    excel_path = SAMPLES_DIR / r001_config["excel_file"]
    excel_row = load_excel_row(excel_path, r001_config["row_id"])

    # Get image files from images directory
    images_dir = SAMPLES_DIR / r001_config["images_dir"]
    image_files = [f.name for f in images_dir.glob("*.jpg")]

    return {
        "excel_row": excel_row,
        "category": r001_config["category"],
        "image_files": image_files,
    }


@pytest.fixture
def r001_product_data():
    """Load expected R001 product_data.json output"""
    with open(SAMPLES_DIR / "expected_output" / "product_data.json") as f:
        return json.load(f)


@pytest.fixture
def r001_listing():
    """Load expected R001 listing output"""
    with open(SAMPLES_DIR / "expected_output" / "R001_Listing.json") as f:
        return json.load(f)


@pytest.fixture
def integration_workspace(tmp_path, r001_config):
    """Create a temporary workspace with R001 supplier images"""
    workspace = tmp_path / "R001"
    workspace.mkdir()
    # Copy supplier images from samples/R001/images/
    images_dir = SAMPLES_DIR / r001_config["images_dir"]
    if images_dir.exists():
        for img in images_dir.glob("*.jpg"):
            shutil.copy(img, workspace / img.name)
    else:
        # Create placeholder if images not found
        (workspace / "hero_01.jpg").write_bytes(b"fake image")
    return workspace


# ===== Test Classes =====


class TestFullWorkflowHappyPath:
    """Test complete workflow from PENDING to COMPLETED using real R001 data.

    V3 flow: preprocess → strategy → fan-out (10 agentic prompt_nodes) → listing
    Mocks: call_claude_agent (preprocess, strategy) + agentic_loop (prompts) + call_minimax (listing)
    """

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_completes_with_real_r001_data(
        self,
        integration_workspace,
        r001_input,
        r001_product_data,
        r001_listing,
    ):
        """Full workflow should complete successfully with R001 data"""
        state = create_initial_state(
            product_id="R001",
            product_path=str(integration_workspace) + "/",
            category=r001_input["category"],
            excel_row=r001_input["excel_row"],
            image_files=r001_input["image_files"],
        )

        workflow = create_workflow()
        app = workflow.compile()

        # Mock Claude (preprocess + strategy call call_claude directly)
        mock_claude = _make_mock_claude(r001_product_data)
        mock_listing = await _mock_minimax_listing(r001_listing)

        with patch("etsy_listing_agent.nodes.call_claude", side_effect=mock_claude), \
             patch("etsy_listing_agent.nodes.agentic_loop", side_effect=_mock_agentic_loop), \
             patch("etsy_listing_agent.nodes.call_minimax", side_effect=mock_listing), \
             patch("etsy_listing_agent.client.call_minimax", side_effect=mock_listing):
            final_state = await app.ainvoke(state)

        # Verify successful completion
        assert final_state["stage"] == "completed"
        assert final_state["success"] is True
        assert final_state["final_error"] is None

        # Verify all reviews passed
        assert final_state["preprocessing_review"] is not None
        assert final_state["preprocessing_review"].passed is True
        assert final_state["listing_review"] is not None
        assert final_state["listing_review"].passed is True

        # Verify files were created
        assert (integration_workspace / "product_data.json").exists()
        assert (integration_workspace / "R001_image_strategy.json").exists()
        assert (integration_workspace / "R001_NanoBanana_Prompts.json").exists()
        assert (integration_workspace / "R001_Listing.json").exists()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_creates_correct_output_files(
        self,
        integration_workspace,
        r001_input,
        r001_product_data,
        r001_listing,
    ):
        """Workflow should create files matching the real R001 structure"""
        state = create_initial_state(
            product_id="R001",
            product_path=str(integration_workspace) + "/",
            category=r001_input["category"],
            excel_row=r001_input["excel_row"],
            image_files=r001_input["image_files"],
        )

        workflow = create_workflow()
        app = workflow.compile()

        mock_claude = _make_mock_claude(r001_product_data)
        mock_listing = await _mock_minimax_listing(r001_listing)

        with patch("etsy_listing_agent.nodes.call_claude", side_effect=mock_claude), \
             patch("etsy_listing_agent.nodes.agentic_loop", side_effect=_mock_agentic_loop), \
             patch("etsy_listing_agent.nodes.call_minimax", side_effect=mock_listing), \
             patch("etsy_listing_agent.client.call_minimax", side_effect=mock_listing):
            await app.ainvoke(state)

        # Verify product_data.json content
        with open(integration_workspace / "product_data.json") as f:
            saved_data = json.load(f)
        assert saved_data["product_id"] == "R001"
        assert saved_data["category"] == "rings"
        assert saved_data["style"] == "tibetan"

        # Verify NanoBanana prompts (10 prompts in V3)
        with open(integration_workspace / "R001_NanoBanana_Prompts.json") as f:
            saved_prompts = json.load(f)
        assert len(saved_prompts["prompts"]) == 10

        # Verify strategy file
        assert (integration_workspace / "R001_image_strategy.json").exists()

        # Verify Listing
        with open(integration_workspace / "R001_Listing.json") as f:
            saved_listing = json.load(f)
        assert "Sterling Silver" in saved_listing["title"]


class TestWorkflowRetryOnFailure:
    """Test workflow retry behavior when validation fails"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_retries_on_preprocessing_failure(
        self,
        integration_workspace,
        r001_input,
        r001_product_data,
        r001_listing,
    ):
        """Workflow should retry preprocessing when validation fails"""
        state = create_initial_state(
            product_id="R001",
            product_path=str(integration_workspace) + "/",
            category=r001_input["category"],
            excel_row=r001_input["excel_row"],
            image_files=r001_input["image_files"],
            max_retries=3,
        )

        workflow = create_workflow()
        app = workflow.compile()

        # Claude: call 1 = invalid preprocess, call 2 = valid preprocess, call 3 = strategy
        claude_count = 0
        async def mock_claude_retry(*args, **kwargs):
            nonlocal claude_count
            claude_count += 1
            if claude_count == 1:
                return {"text": json.dumps({"product_id": "R001"}), "usage_metadata": {}, "cost_usd": 0.04, "model": "claude"}
            elif claude_count == 2:
                return {"text": json.dumps(_patch_product_data(r001_product_data)), "usage_metadata": {}, "cost_usd": 0.04, "model": "claude"}
            else:
                return {"text": json.dumps(_make_mock_strategy()), "usage_metadata": {}, "cost_usd": 0.04, "model": "claude"}

        mock_listing = await _mock_minimax_listing(r001_listing)

        with patch("etsy_listing_agent.nodes.call_claude", side_effect=mock_claude_retry), \
             patch("etsy_listing_agent.nodes.agentic_loop", side_effect=_mock_agentic_loop), \
             patch("etsy_listing_agent.nodes.call_minimax", side_effect=mock_listing), \
             patch("etsy_listing_agent.client.call_minimax", side_effect=mock_listing):
            final_state = await app.ainvoke(state)

        # Should eventually complete
        assert final_state["stage"] == "completed"
        assert final_state["success"] is True
        # Preprocessing was retried once
        assert final_state["retry_counts"]["preprocessing"] == 1


class TestWorkflowMaxRetriesExceeded:
    """Test workflow failure when max retries exceeded"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_fails_after_max_retries(self, integration_workspace, r001_input):
        """Workflow should fail when max retries exceeded"""
        state = create_initial_state(
            product_id="R001",
            product_path=str(integration_workspace) + "/",
            category=r001_input["category"],
            excel_row=r001_input["excel_row"],
            image_files=r001_input["image_files"],
            max_retries=2,
        )

        workflow = create_workflow()
        app = workflow.compile()

        # Always return invalid data
        async def mock_claude_invalid(*args, **kwargs):
            return {"text": json.dumps({"product_id": "R001"}), "usage_metadata": {}, "cost_usd": 0.04, "model": "claude"}

        with patch("etsy_listing_agent.nodes.call_claude", side_effect=mock_claude_invalid):
            final_state = await app.ainvoke(state)

        # Should fail
        assert final_state["stage"] == "failed"
        assert final_state["success"] is False
        assert final_state["final_error"] is not None
        # Retried max times
        assert final_state["retry_counts"]["preprocessing"] == 2
