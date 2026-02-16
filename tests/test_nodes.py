# Tests for agent and reviewer nodes
# TDD: Agent 节点和 Reviewer 节点测试

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from etsy_listing_agent.nodes import (
    preprocess_node,
    listing_node,
    preprocess_review_node,
    listing_review_node,
    prompt_node,
    prompt_aggregator_node,
    nanobanana_review_node,
    strategy_review_node,
    _l3_enabled,
    _run_semantic_review,
    _load_review_skill,
)
from etsy_listing_agent.state import (
    ProductState,
    ReviewResult,
    ReviewLevel,
    create_initial_state,
)


# ===== Fixtures =====


@pytest.fixture
def sample_state():
    """创建测试用的初始状态"""
    return create_initial_state(
        product_id="R001",
        product_path="/products/MentorArtCircle/rings/R001/",
        category="rings",
        excel_row={"SKU": "R001", "Name": "藏式六字真言戒指", "Material": "925银"},
        image_files=["R001_01.jpg", "R001_02.jpg"],
    )


@pytest.fixture
def sample_product_data():
    """有效的 product_data.json 内容"""
    return {
        "product_id": "R001",
        "product_path": "/products/MentorArtCircle/rings/R001/",
        "category": "rings",
        "style": "tibetan",
        "target_audience": "neutral",
        "occasion": "daily",
        "materials": ["sterling_silver"],
        "product_size": {"dimensions": "Band 6mm, Face 12mm", "source": "excel"},
        "basic_info": "925 Sterling Silver ring with Tibetan mantra engraving",
        "images": [
            {"filename": "R001_01.jpg", "angle": "front", "type": "product_only", "is_hero": True},
            {"filename": "R001_02.jpg", "angle": "side", "type": "product_only", "is_hero": False},
        ],
        "visual_features": {
            "material_finish": "polished",
            "color_tone": "cool",
            "surface_quality": "engraved",
            "light_interaction": "reflective",
        },
        "selling_points": [
            {"feature": "Handcrafted", "benefit": "Unique artisan quality"},
            {"feature": "Authentic Tibetan design", "benefit": "Cultural significance"},
        ],
    }


@pytest.fixture
def sample_nanobanana_output():
    """有效的 NanoBanana prompts 输出 (按 schema 格式)"""
    def make_prompt(index, image_type):
        # Hero prompt needs: no hands, light background, anti-AI realism
        if image_type == "hero":
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. Close-up macro product photograph of the ring on cream background. "
                "No hands. No fingers. No model. Film grain, dust particles, micro-scratches."
            )
        else:
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. Product photograph with film grain and natural imperfections."
            )
        return {
            "index": index,
            "type": image_type,
            "type_name": image_type.replace("_", " ").title(),
            "goal": "Test goal",
            "series_used": "Product Only" if image_type == "hero" else "S5A Body",
            "reference_images": ["img1.jpg", "img2.jpg", "img3.jpg"],
            "prompt": prompt_text,
            "design_rationale": {"scene": "test", "lighting": "test"},
            "camera_params": {"aspect_ratio": "1:1", "lens": "85mm", "aperture": "f/11" if image_type == "hero" else "f/2.8"},
        }

    image_types = [
        "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
        "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract"
    ]
    return {
        "product_id": "R001",
        "prompts": [make_prompt(i+1, t) for i, t in enumerate(image_types)],
    }


@pytest.fixture
def sample_listing_output():
    """有效的 Etsy listing 输出 (按 schema 格式)"""
    return {
        "product_id": "R001",
        "title": "Sterling Silver Tibetan Ring Buddhist Band",  # <14 words
        "tags": "tibetan ring, sterling silver, buddhist jewelry, mantra ring, meditation ring, prayer ring, spiritual jewelry, om ring, yoga ring, mens ring, unisex ring, silver band, adjustable ring",  # 13 tags as string
        "long_tail_keywords": [
            "tibetan mantra sterling silver ring",
            "buddhist prayer band meditation",
            "handmade spiritual om ring",
            "925 silver mantra engraved ring",
            "bohemian meditation ring jewelry",
            "minimalist buddhist band ring",
            "tibetan prayer ring silver",
            "yoga zen ring everyday wear",
        ],
        "description": "Handcrafted sterling silver ring featuring traditional Tibetan mantra. Perfect for daily wear.",
        "attributes": {"materials": ["Sterling Silver"], "style": "Tibetan"},
    }


# ===== Preprocess Node Tests =====


class TestPreprocessNode:
    """测试 Preprocessing Agent 节点"""

    @pytest.mark.asyncio
    async def test_preprocess_updates_stage(self, sample_state, sample_product_data, tmp_path):
        """preprocess_node 应该更新 stage 为 preprocessing"""
        sample_state["product_path"] = str(tmp_path) + "/"
        mock_result = {"text": json.dumps(sample_product_data), "usage_metadata": {}, "cost_usd": 0.04, "model": "claude"}
        with patch("etsy_listing_agent.nodes.call_claude", return_value=mock_result):
            result = await preprocess_node(sample_state)
            assert result["stage"] == "preprocessing"

    @pytest.mark.asyncio
    async def test_preprocess_creates_product_data_file(
        self, sample_state, sample_product_data, tmp_path
    ):
        """preprocess_node 应该创建 product_data.json 文件"""
        sample_state["product_path"] = str(tmp_path) + "/"
        mock_result = {"text": json.dumps(sample_product_data), "usage_metadata": {}, "cost_usd": 0.04, "model": "claude"}
        with patch("etsy_listing_agent.nodes.call_claude", return_value=mock_result):
            await preprocess_node(sample_state)

            product_data_file = tmp_path / "product_data.json"
            assert product_data_file.exists()

            with open(product_data_file) as f:
                data = json.load(f)
            assert data["product_id"] == "R001"


# ===== NanoBanana Node Tests =====


# ===== Listing Node Tests =====


class TestListingNode:
    """测试 Listing Agent 节点"""

    @pytest.mark.asyncio
    async def test_listing_updates_stage(self, sample_state, sample_listing_output, tmp_path):
        """listing_node 应该更新 stage 为 listing"""
        sample_state["product_path"] = str(tmp_path) + "/"
        # 创建前置文件
        with open(tmp_path / "product_data.json", "w") as f:
            json.dump({"product_id": "R001", "category": "rings"}, f)

        with patch("etsy_listing_agent.nodes.call_claude_agent") as mock_agent:
            mock_agent.return_value = json.dumps(sample_listing_output)
            result = await listing_node(sample_state)
            assert result["stage"] == "listing"


# ===== Review Node Tests =====


class TestPreprocessReviewNode:
    """测试 Preprocessing Review 节点"""

    @pytest.mark.asyncio
    async def test_review_passes_valid_data(self, sample_state, sample_product_data, tmp_path):
        """有效数据应该通过 review"""
        sample_state["product_path"] = str(tmp_path) + "/"
        sample_state["stage"] = "preprocessing"

        # 写入有效的 product_data.json
        with open(tmp_path / "product_data.json", "w") as f:
            json.dump(sample_product_data, f)

        result = await preprocess_review_node(sample_state, enable_l3=False)
        assert result["stage"] == "preprocessing_review"
        assert result["preprocessing_review"] is not None
        assert result["preprocessing_review"].passed is True

    @pytest.mark.asyncio
    async def test_review_fails_invalid_schema(self, sample_state, tmp_path):
        """无效 schema 应该失败"""
        sample_state["product_path"] = str(tmp_path) + "/"
        sample_state["stage"] = "preprocessing"

        # 写入无效的 product_data.json (缺少必填字段)
        with open(tmp_path / "product_data.json", "w") as f:
            json.dump({"product_id": "R001"}, f)  # missing required fields

        result = await preprocess_review_node(sample_state, enable_l3=False)
        assert result["preprocessing_review"] is not None
        assert result["preprocessing_review"].passed is False
        assert result["preprocessing_review"].level == ReviewLevel.SCHEMA


class TestListingReviewNode:
    """测试 Listing Review 节点"""

    @pytest.mark.asyncio
    async def test_review_passes_valid_listing(self, sample_state, sample_listing_output, tmp_path):
        """有效的 listing 应该通过 review"""
        sample_state["product_path"] = str(tmp_path) + "/"
        sample_state["stage"] = "listing"

        # 写入有效的 listing 文件
        with open(tmp_path / "R001_Listing.json", "w") as f:
            json.dump(sample_listing_output, f)

        result = await listing_review_node(sample_state, enable_l3=False)
        assert result["listing_review"] is not None
        assert result["listing_review"].passed is True

    @pytest.mark.asyncio
    async def test_review_fails_title_too_many_words(self, sample_state, tmp_path):
        """title 单词数太多应该失败"""
        sample_state["product_path"] = str(tmp_path) + "/"
        sample_state["stage"] = "listing"

        # title 超过 14 个单词 (按 schema)
        with open(tmp_path / "R001_Listing.json", "w") as f:
            json.dump(
                {
                    "product_id": "R001",
                    "title": "word " * 20,  # 20 words - too many
                    "tags": "a, b, c, d, e, f, g, h, i, j, k, l, m",  # 13 tags as string
                    "description": "Test description that is long enough for validation",
                    "attributes": {},
                },
                f,
            )

        result = await listing_review_node(sample_state, enable_l3=False)
        assert result["listing_review"].passed is False
        assert result["listing_review"].level == ReviewLevel.RULES


# ===== Prompt Node Tests (Fan-Out) =====


class TestPromptNode:
    """Tests for prompt_node - agentic prompt generation with tool use"""

    @pytest.mark.asyncio
    async def test_prompt_node_generates_valid_prompt(self):
        """prompt_node should use agentic_loop with read_reference and validate_prompt tools."""
        from etsy_listing_agent.nodes import prompt_node

        state = {
            "product_id": "TEST001",
            "product_path": "/tmp/test",
            "direction": "hero",
            "product_data": {
                "product_id": "TEST001",
                "category": "rings",
                "style": "tibetan",
                "materials": ["sterling_silver"],
                "reference_anchor": "REFERENCE ANCHOR: The input image depicts a tibetan silver ring.\nMaintain exact structural integrity, engraved band, color palette, and material finish.\nDo not alter the product's geometry. Rigid constraint.",
            },
            "slot_info": {"description": "Hero shot on white background"},
            "is_packaging": False,
        }

        mock_return = {
            "text": "SCENE CONTEXT: Studio.\n\nLIGHTING: Soft.\n\nCAMERA: 85mm.\n\nPHYSICS & REALISM: Film grain, dust particles visible.",
            "cost_usd": 0.05,
            "usage_metadata": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "turns": 3,
            },
            "model": "MiniMax-M2.1",
        }

        with patch('etsy_listing_agent.nodes.agentic_loop', return_value=mock_return) as mock_loop:
            result = await prompt_node(state)

        # Verify agentic_loop was called with both tools
        mock_loop.assert_called_once()
        call_kwargs = mock_loop.call_args
        tool_names = [t["name"] for t in call_kwargs.kwargs["tools"]]
        assert "read_reference" in tool_names
        assert "validate_prompt" in tool_names

        assert result["prompt_results"][0]["success"] is True
        assert "REFERENCE ANCHOR:" in result["prompt_results"][0]["prompt"]
        assert result["prompt_results"][0]["prompt"].startswith("REFERENCE ANCHOR:")
        assert result["prompt_results"][0]["cost_usd"] == 0.05

    @pytest.mark.asyncio
    async def test_prompt_node_retries_on_exception(self):
        """prompt_node should retry on RuntimeError (agent exhausted turns)."""
        from etsy_listing_agent.nodes import prompt_node

        state = {
            "product_id": "TEST001",
            "product_path": "/tmp/test",
            "direction": "hero",
            "product_data": {
                "product_id": "TEST001",
                "category": "rings",
                "reference_anchor": "REFERENCE ANCHOR: The input image depicts a silver ring.\nMaintain exact structural integrity, color palette, and material finish.\nDo not alter the product's geometry. Rigid constraint.",
            },
            "slot_info": {"description": "Hero shot"},
            "is_packaging": False,
        }

        call_count = 0

        async def mock_agentic_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First attempt: agent exhausted turns
                raise RuntimeError("Agentic loop exhausted 5 turns without generating text.")
            # Second attempt succeeds
            return {
                "text": "SCENE CONTEXT: Studio.\n\nPHYSICS & REALISM: Film grain, dust particles.",
                "cost_usd": 0.02,
                "usage_metadata": {"input_tokens": 50, "output_tokens": 25, "total_tokens": 75, "turns": 3},
                "model": "MiniMax-M2.1",
            }

        with patch('etsy_listing_agent.nodes.agentic_loop', side_effect=mock_agentic_with_retry):
            result = await prompt_node(state)

        assert call_count == 2  # Retried once after exception
        assert result["prompt_results"][0]["success"] is True
        assert result["prompt_results"][0]["cost_usd"] == 0.02


class TestPromptAggregatorNode:
    """Tests for prompt_aggregator_node - collects fan-out results"""

    def test_aggregator_collects_successful_results(self, tmp_path):
        """aggregator should collect all prompt results and save JSON."""
        from etsy_listing_agent.nodes import prompt_aggregator_node

        # Simulate 3 prompt results (simplified for test)
        prompt_results = [
            {"direction": "hero", "prompt": "REFERENCE ANCHOR: Hero. Rigid constraint.", "success": True, "cost_usd": 0.05},
            {"direction": "size_reference", "prompt": "REFERENCE ANCHOR: Size. Rigid constraint.", "success": True, "cost_usd": 0.04},
            {"direction": "macro_detail", "prompt": "REFERENCE ANCHOR: Macro. Rigid constraint.", "success": True, "cost_usd": 0.06},
        ]

        state = {
            "product_id": "TEST001",
            "product_path": str(tmp_path),
            "prompt_results": prompt_results,
            "product_data": {
                "category": "rings",
                "style": "tibetan",
                "materials": ["sterling_silver"],
                "images": [{"filename": "img1.jpg"}, {"filename": "img2.jpg"}],
            },
        }

        result = prompt_aggregator_node(state)

        assert result["nanobanana_success"] is True
        assert result["total_cost"] == 0.15
        assert "output_file" in result

        # Verify file was created
        output_file = Path(result["output_file"])
        assert output_file.exists()

        # Verify JSON structure
        with open(output_file) as f:
            data = json.load(f)
        assert data["product_id"] == "TEST001"
        assert len(data["prompts"]) == 3

    def test_aggregator_reports_failures(self, tmp_path):
        """aggregator should report when some prompts failed."""
        from etsy_listing_agent.nodes import prompt_aggregator_node

        prompt_results = [
            {"direction": "hero", "prompt": "ANCHOR: Hero.", "success": True, "cost_usd": 0.05},
            {"direction": "wearing_a", "prompt": "", "success": False, "error": "Validation failed", "cost_usd": 0.03},
        ]

        state = {
            "product_id": "TEST001",
            "product_path": str(tmp_path),
            "prompt_results": prompt_results,
            "product_data": {"images": []},
        }

        result = prompt_aggregator_node(state)

        assert result["nanobanana_success"] is False  # Has failures
        assert result["total_cost"] == 0.08


# ===== Strategy Validator Tests =====


class TestStrategyValidators:
    """Tests for strategy schema and rules validators."""

    def _make_valid_strategy(self) -> dict:
        """Create a valid v1 strategy JSON (backward compat)."""
        return {
            "$schema": "image_strategy_v1",
            "product_id": "R001",
            "analysis": {
                "product_usps": ["handcrafted", "925 silver"],
                "target_customer": "spiritual adults",
                "purchase_barriers": ["can't feel quality"],
                "competitive_gap": "no lifestyle shots",
            },
            "slots": [
                {"slot": 1, "type": "hero", "category": "required", "description": "Hero shot", "rationale": "Main image"},
                {"slot": 2, "type": "size_reference", "category": "required", "description": "Size ref", "rationale": "Scale"},
                {"slot": 3, "type": "wearing_a", "category": "required", "description": "Dark wearing", "rationale": "Emotional"},
                {"slot": 4, "type": "wearing_b", "category": "required", "description": "Light wearing", "rationale": "Commercial"},
                {"slot": 5, "type": "packaging", "category": "required", "description": "Gift box", "rationale": "Gift trigger"},
                {"slot": 6, "type": "macro_detail", "category": "strategic", "description": "Close-up", "rationale": "Show craftsmanship"},
                {"slot": 7, "type": "art_still_life", "category": "strategic", "description": "Oil painting", "rationale": "Art appeal"},
                {"slot": 8, "type": "scene_daily", "category": "strategic", "description": "Lifestyle", "rationale": "Relatability"},
                {"slot": 9, "type": "workshop", "category": "strategic", "description": "Workshop", "rationale": "Authenticity"},
                {"slot": 10, "type": "art_abstract", "category": "strategic", "description": "Abstract", "rationale": "Creative"},
            ],
        }

    def test_strategy_schema_valid(self):
        """Valid strategy passes schema validation."""
        from etsy_listing_agent.validators import validate_strategy_schema
        result = validate_strategy_schema(self._make_valid_strategy())
        assert result.passed is True

    def test_strategy_schema_missing_fields(self):
        """Missing required fields fails schema validation."""
        from etsy_listing_agent.validators import validate_strategy_schema
        result = validate_strategy_schema({"product_id": "R001"})
        assert result.passed is False
        assert any("Missing required field" in e for e in result.errors)

    def test_strategy_schema_wrong_slot_count(self):
        """Non-10 slot count fails."""
        from etsy_listing_agent.validators import validate_strategy_schema
        data = self._make_valid_strategy()
        data["slots"] = data["slots"][:5]  # Only 5 slots
        result = validate_strategy_schema(data)
        assert result.passed is False
        assert any("exactly 10" in e for e in result.errors)

    def test_strategy_rules_valid(self):
        """Valid strategy passes rules validation."""
        from etsy_listing_agent.validators import validate_strategy_rules
        result = validate_strategy_rules(self._make_valid_strategy())
        assert result.passed is True

    def test_strategy_rules_wrong_required_order(self):
        """Wrong required type order fails."""
        from etsy_listing_agent.validators import validate_strategy_rules
        data = self._make_valid_strategy()
        # Swap slots 1 and 2
        data["slots"][0], data["slots"][1] = data["slots"][1], data["slots"][0]
        result = validate_strategy_rules(data)
        assert result.passed is False

    def test_strategy_rules_banned_type(self):
        """scene_gift is banned."""
        from etsy_listing_agent.validators import validate_strategy_rules
        data = self._make_valid_strategy()
        data["slots"][9]["type"] = "scene_gift"
        result = validate_strategy_rules(data)
        assert result.passed is False
        assert any("Banned" in e for e in result.errors)

    def test_strategy_rules_duplicate_type(self):
        """Duplicate types fail."""
        from etsy_listing_agent.validators import validate_strategy_rules
        data = self._make_valid_strategy()
        data["slots"][9]["type"] = "macro_detail"  # Duplicate of slot 6
        result = validate_strategy_rules(data)
        assert result.passed is False
        assert any("Duplicate" in e for e in result.errors)


# ===== NanoBanana Validator Tests (10 prompts) =====


class TestNanoBananaValidators10:
    """Tests for updated nanobanana validators with 10 prompts."""

    def _make_10_prompts(self) -> dict:
        """Create valid 10-prompt NanoBanana data."""
        types = [
            "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
            "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
        ]
        prompts = []
        for i, t in enumerate(types):
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. The ring, approximately 18mm band diameter, "
                "product photograph with film grain and dust particles."
            )
            ref_images = ["img1.jpg", "img2.jpg", "img3.jpg"]
            if t == "packaging":
                ref_images.append("packaging_box.jpg")
            prompts.append({
                "index": i + 1,
                "type": t,
                "reference_images": ref_images,
                "prompt": prompt_text,
            })
        return {"product_id": "R001", "prompts": prompts}

    def test_nanobanana_schema_10_prompts(self):
        """10 prompts pass schema validation."""
        from etsy_listing_agent.validators import validate_nanobanana_schema
        result = validate_nanobanana_schema(self._make_10_prompts())
        assert result.passed is True

    def test_nanobanana_schema_9_prompts_fails(self):
        """9 prompts now fails (need 10)."""
        from etsy_listing_agent.validators import validate_nanobanana_schema
        data = self._make_10_prompts()
        data["prompts"] = data["prompts"][:9]
        result = validate_nanobanana_schema(data)
        assert result.passed is False
        assert any("exactly 10" in e for e in result.errors)

    def test_macro_detail_no_anti_ai_passes(self):
        """macro_detail prompt passes without anti-AI modifiers."""
        from etsy_listing_agent.validators import validate_nanobanana_rules
        data = self._make_10_prompts()
        # Remove anti-AI keywords from macro_detail prompt
        for p in data["prompts"]:
            if p["type"] == "macro_detail":
                p["prompt"] = (
                    "REFERENCE ANCHOR: The input image depicts a ring. "
                    "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                    "1:1 aspect ratio. The ring, approximately 18mm, extreme macro close-up of engraving details."
                )
        result = validate_nanobanana_rules(data)
        assert result.passed is True

    def test_packaging_no_anti_ai_passes(self):
        """packaging prompt passes without anti-AI modifiers."""
        from etsy_listing_agent.validators import validate_nanobanana_rules
        data = self._make_10_prompts()
        for p in data["prompts"]:
            if p["type"] == "packaging":
                p["prompt"] = (
                    "REFERENCE ANCHOR: The input image depicts a ring. "
                    "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                    "1:1 aspect ratio. The ring, approximately 18mm, in gift box. Clean commercial aesthetic."
                )
        result = validate_nanobanana_rules(data)
        assert result.passed is True


# ===== Packaging Template Test =====


class TestPackagingTemplate:
    """Tests for packaging fixed template handling."""

    @pytest.mark.asyncio
    async def test_packaging_uses_fixed_template(self):
        """Packaging slot should use template, not MiniMax."""
        from etsy_listing_agent.nodes import prompt_node

        state = {
            "product_id": "TEST001",
            "product_path": "/tmp/test",
            "direction": "packaging",
            "product_data": {
                "product_id": "TEST001",
                "category": "rings",
                "product_size": {"dimensions": "18mm"},
            },
            "slot_info": {"slot": 5, "type": "packaging", "category": "required",
                         "description": "Gift box", "rationale": "Gift trigger"},
            "is_packaging": True,
        }

        # Should NOT call MiniMax at all
        with patch('etsy_listing_agent.client.call_minimax') as mock_minimax:
            result = await prompt_node(state)
            mock_minimax.assert_not_called()

        assert result["prompt_results"][0]["success"] is True
        assert result["prompt_results"][0]["cost_usd"] == 0.0
        assert "REFERENCE ANCHOR:" in result["prompt_results"][0]["prompt"]


# ===== L3 Semantic Review Tests =====


class TestL3Enabled:
    """Tests for _l3_enabled() helper."""

    def test_l3_enabled_default(self):
        """L3 should be enabled by default (no env var)."""
        with patch.dict("os.environ", {}, clear=True):
            assert _l3_enabled() is True

    def test_l3_enabled_explicit_true(self):
        """L3 should be enabled when ENABLE_L3_REVIEW=true."""
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}):
            assert _l3_enabled() is True

    def test_l3_disabled_explicit_false(self):
        """L3 should be disabled when ENABLE_L3_REVIEW=false."""
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "false"}):
            assert _l3_enabled() is False

    def test_l3_disabled_case_insensitive(self):
        """ENABLE_L3_REVIEW=False (capitalized) should disable."""
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "False"}):
            assert _l3_enabled() is False


class TestSemanticReviewBugFix:
    """Tests for _run_semantic_review dict response handling."""

    @pytest.mark.asyncio
    async def test_semantic_review_parses_dict_response(self):
        """_run_semantic_review should handle call_claude's dict return value."""
        mock_response = {
            "text": "SEMANTIC_REVIEW_RESULT: PASS\n\nAll criteria met.",
            "usage_metadata": {"input_tokens": 100, "output_tokens": 50},
            "cost_usd": 0.01,
        }
        with patch("etsy_listing_agent.nodes.call_claude", return_value=mock_response):
            result = await _run_semantic_review("etsy-batch-preprocessing", {"test": "data"})
        assert result.passed is True
        assert result.level == ReviewLevel.SEMANTIC

    @pytest.mark.asyncio
    async def test_semantic_review_fail_extracts_errors(self):
        """_run_semantic_review should extract error lines from FAIL response."""
        mock_response = {
            "text": "SEMANTIC_REVIEW_RESULT: FAIL\n\nIssues found:\n- basic_info contains marketing fluff\n- Style inference incorrect\n\nSuggestions:\n- Remove adjectives",
            "usage_metadata": {"input_tokens": 100, "output_tokens": 80},
            "cost_usd": 0.01,
        }
        with patch("etsy_listing_agent.nodes.call_claude", return_value=mock_response):
            result = await _run_semantic_review("etsy-batch-preprocessing", {"test": "data"})
        assert result.passed is False
        assert result.level == ReviewLevel.SEMANTIC
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    async def test_semantic_review_no_review_skill_passes(self):
        """Missing REVIEW.md should skip L3 and pass."""
        result = await _run_semantic_review("nonexistent-skill", {"test": "data"})
        assert result.passed is True
        assert result.level == ReviewLevel.SEMANTIC

    @pytest.mark.asyncio
    async def test_semantic_review_api_error_passes(self):
        """API errors should not block — skip L3 and pass."""
        with patch("etsy_listing_agent.nodes.call_claude", side_effect=Exception("API timeout")):
            result = await _run_semantic_review("etsy-batch-preprocessing", {"test": "data"})
        assert result.passed is True
        assert "error" in result.feedback.lower()


class TestLoadReviewSkill:
    """Tests for REVIEW.md file loading."""

    def test_load_existing_review_skill(self):
        """Should load REVIEW.md content for existing skills."""
        content = _load_review_skill("image-strategy")
        assert content != ""
        assert "SEMANTIC_REVIEW_RESULT" in content

    def test_load_jewelry_prompt_review_skill(self):
        """Should load REVIEW.md for jewelry-prompt-generator."""
        content = _load_review_skill("jewelry-prompt-generator")
        assert content != ""
        assert "SEMANTIC_REVIEW_RESULT" in content

    def test_load_missing_review_skill(self):
        """Missing REVIEW.md should return empty string."""
        content = _load_review_skill("nonexistent-skill-xyz")
        assert content == ""


class TestStrategyReviewL3:
    """Tests for L3 in strategy_review_node."""

    def _make_valid_strategy(self) -> dict:
        """Create a valid v1 strategy JSON (review node accepts both v1/v2)."""
        return {
            "$schema": "image_strategy_v1",
            "product_id": "R001",
            "analysis": {
                "product_usps": ["handcrafted", "925 silver"],
                "target_customer": "spiritual adults",
                "purchase_barriers": ["can't feel quality"],
                "competitive_gap": "no lifestyle shots",
            },
            "slots": [
                {"slot": 1, "type": "hero", "category": "required", "description": "Hero shot", "rationale": "Main image"},
                {"slot": 2, "type": "size_reference", "category": "required", "description": "Size ref", "rationale": "Scale"},
                {"slot": 3, "type": "wearing_a", "category": "required", "description": "Dark wearing", "rationale": "Emotional"},
                {"slot": 4, "type": "wearing_b", "category": "required", "description": "Light wearing", "rationale": "Commercial"},
                {"slot": 5, "type": "packaging", "category": "required", "description": "Gift box", "rationale": "Gift trigger"},
                {"slot": 6, "type": "macro_detail", "category": "strategic", "description": "Close-up", "rationale": "Show craftsmanship"},
                {"slot": 7, "type": "art_still_life", "category": "strategic", "description": "Oil painting", "rationale": "Art appeal"},
                {"slot": 8, "type": "scene_daily", "category": "strategic", "description": "Lifestyle", "rationale": "Relatability"},
                {"slot": 9, "type": "workshop", "category": "strategic", "description": "Workshop", "rationale": "Authenticity"},
                {"slot": 10, "type": "art_abstract", "category": "strategic", "description": "Abstract", "rationale": "Creative"},
            ],
        }

    @pytest.mark.asyncio
    async def test_strategy_review_runs_l3_when_enabled(self, sample_state, tmp_path):
        """strategy_review_node should call L3 when enabled."""
        sample_state["product_path"] = str(tmp_path) + "/"
        strategy_data = self._make_valid_strategy()
        with open(tmp_path / "R001_image_strategy.json", "w") as f:
            json.dump(strategy_data, f)

        mock_l3 = AsyncMock(return_value=ReviewResult(
            passed=True, level=ReviewLevel.SEMANTIC, errors=[]
        ))
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await strategy_review_node(sample_state)

        assert result["strategy_review"].passed is True
        mock_l3.assert_called_once_with("image-strategy", strategy_data)

    @pytest.mark.asyncio
    async def test_strategy_review_skips_l3_when_disabled(self, sample_state, tmp_path):
        """strategy_review_node should skip L3 when ENABLE_L3_REVIEW=false."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "R001_image_strategy.json", "w") as f:
            json.dump(self._make_valid_strategy(), f)

        mock_l3 = AsyncMock()
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "false"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await strategy_review_node(sample_state)

        assert result["strategy_review"].passed is True
        assert result["strategy_review"].level == ReviewLevel.RULES
        mock_l3.assert_not_called()

    @pytest.mark.asyncio
    async def test_strategy_review_l3_fail_increments_retry(self, sample_state, tmp_path):
        """L3 failure should increment retry count."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "R001_image_strategy.json", "w") as f:
            json.dump(self._make_valid_strategy(), f)

        mock_l3 = AsyncMock(return_value=ReviewResult(
            passed=False, level=ReviewLevel.SEMANTIC,
            errors=["Generic descriptions"],
            feedback="SEMANTIC_REVIEW_RESULT: FAIL",
        ))
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await strategy_review_node(sample_state)

        assert result["strategy_review"].passed is False
        assert result["retry_counts"]["strategy"] >= 1


class TestPreprocessReviewL3:
    """Tests for L3 in preprocess_review_node with env var default."""

    @pytest.mark.asyncio
    async def test_preprocess_review_l3_enabled_by_default(self, sample_state, sample_product_data, tmp_path):
        """L3 should run by default (ENABLE_L3_REVIEW not set)."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "product_data.json", "w") as f:
            json.dump(sample_product_data, f)

        mock_l3 = AsyncMock(return_value=ReviewResult(
            passed=True, level=ReviewLevel.SEMANTIC, errors=[]
        ))
        with patch.dict("os.environ", {}, clear=True), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await preprocess_review_node(sample_state)

        assert result["preprocessing_review"].passed is True
        mock_l3.assert_called_once()

    @pytest.mark.asyncio
    async def test_preprocess_review_explicit_override(self, sample_state, sample_product_data, tmp_path):
        """enable_l3=False should override env var."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "product_data.json", "w") as f:
            json.dump(sample_product_data, f)

        mock_l3 = AsyncMock()
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await preprocess_review_node(sample_state, enable_l3=False)

        assert result["preprocessing_review"].passed is True
        mock_l3.assert_not_called()


class TestListingReviewL3:
    """Tests for L3 in listing_review_node with env var default."""

    @pytest.mark.asyncio
    async def test_listing_review_l3_enabled_by_default(self, sample_state, sample_listing_output, tmp_path):
        """L3 should run by default."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "R001_Listing.json", "w") as f:
            json.dump(sample_listing_output, f)

        mock_l3 = AsyncMock(return_value=ReviewResult(
            passed=True, level=ReviewLevel.SEMANTIC, errors=[]
        ))
        with patch.dict("os.environ", {}, clear=True), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await listing_review_node(sample_state)

        assert result["listing_review"].passed is True
        mock_l3.assert_called_once()

    @pytest.mark.asyncio
    async def test_listing_review_explicit_override(self, sample_state, sample_listing_output, tmp_path):
        """enable_l3=False should override env var."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "R001_Listing.json", "w") as f:
            json.dump(sample_listing_output, f)

        mock_l3 = AsyncMock()
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await listing_review_node(sample_state, enable_l3=False)

        assert result["listing_review"].passed is True
        mock_l3.assert_not_called()


class TestNanoBananaReviewL3:
    """Tests for L3 in nanobanana_review_node."""

    def _make_valid_nanobanana(self) -> dict:
        """Create valid 10-prompt data."""
        types = [
            "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
            "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
        ]
        prompts = []
        for i, t in enumerate(types):
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. The ring, approximately 18mm band diameter, "
                "product photograph with film grain and dust particles."
            )
            ref_images = ["img1.jpg", "img2.jpg", "img3.jpg"]
            if t == "packaging":
                ref_images.append("packaging_box.jpg")
            prompts.append({
                "index": i + 1,
                "type": t,
                "reference_images": ref_images,
                "prompt": prompt_text,
            })
        return {"product_id": "R001", "prompts": prompts}

    @pytest.mark.asyncio
    async def test_nanobanana_review_runs_l3_when_enabled(self, sample_state, tmp_path):
        """nanobanana_review_node should call L3 when enabled."""
        sample_state["product_path"] = str(tmp_path) + "/"
        nb_data = self._make_valid_nanobanana()
        with open(tmp_path / "R001_NanoBanana_Prompts.json", "w") as f:
            json.dump(nb_data, f)

        mock_l3 = AsyncMock(return_value=ReviewResult(
            passed=True, level=ReviewLevel.SEMANTIC, errors=[]
        ))
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await nanobanana_review_node(sample_state)

        assert result["nanobanana_review"].passed is True
        assert result["nanobanana_review"].level == ReviewLevel.SEMANTIC
        mock_l3.assert_called_once_with("jewelry-prompt-generator", nb_data)

    @pytest.mark.asyncio
    async def test_nanobanana_review_skips_l3_when_disabled(self, sample_state, tmp_path):
        """nanobanana_review_node should skip L3 when disabled."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "R001_NanoBanana_Prompts.json", "w") as f:
            json.dump(self._make_valid_nanobanana(), f)

        mock_l3 = AsyncMock()
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "false"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await nanobanana_review_node(sample_state)

        assert result["nanobanana_review"].passed is True
        assert result["nanobanana_review"].level == ReviewLevel.RULES
        mock_l3.assert_not_called()

    @pytest.mark.asyncio
    async def test_nanobanana_review_l3_fail_increments_retry(self, sample_state, tmp_path):
        """L3 failure should increment retry count."""
        sample_state["product_path"] = str(tmp_path) + "/"
        with open(tmp_path / "R001_NanoBanana_Prompts.json", "w") as f:
            json.dump(self._make_valid_nanobanana(), f)

        mock_l3 = AsyncMock(return_value=ReviewResult(
            passed=False, level=ReviewLevel.SEMANTIC,
            errors=["Scenes lack differentiation"],
            feedback="SEMANTIC_REVIEW_RESULT: FAIL",
        ))
        with patch.dict("os.environ", {"ENABLE_L3_REVIEW": "true"}), \
             patch("etsy_listing_agent.nodes._run_semantic_review", mock_l3):
            result = await nanobanana_review_node(sample_state)

        assert result["nanobanana_review"].passed is False
        assert result["retry_counts"]["nanobanana"] >= 1


# ===== V2 Creative Direction Tests for Nodes =====


class TestPromptNodeCreativeDirection:
    """Tests for prompt_node using creative_direction from strategy."""

    @pytest.mark.asyncio
    async def test_prompt_node_includes_creative_direction(self):
        """prompt_node user_message should include creative_direction block."""
        state = {
            "product_id": "TEST001",
            "product_path": "/tmp/test",
            "direction": "wearing_a",
            "product_data": {
                "product_id": "TEST001",
                "category": "rings",
                "style": "tibetan",
                "materials": ["sterling_silver"],
                "reference_anchor": "REFERENCE ANCHOR: Ring.\nMaintain integrity.\nRigid constraint.",
            },
            "slot_info": {
                "slot": 3,
                "type": "wearing_a",
                "description": "Editorial model shot with dramatic lighting",
                "rationale": "Emotional appeal for dark moody buyers",
                "creative_direction": {
                    "style_series": "S4C",
                    "pose": "A1",
                    "scene_module": None,
                    "mood": "dramatic, kinetic, high-fashion",
                    "key_visual": "Model with motion blur, ring sharp and sparkling",
                },
            },
            "is_packaging": False,
        }

        mock_return = {
            "text": "SCENE CONTEXT: Studio.\n\nLIGHTING: Soft.\n\nCAMERA: 85mm.\n\nPHYSICS & REALISM: Film grain.",
            "cost_usd": 0.05,
            "usage_metadata": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150, "turns": 3},
            "model": "MiniMax-M2.5",
        }

        with patch('etsy_listing_agent.nodes.agentic_loop', return_value=mock_return) as mock_loop:
            await prompt_node(state)

        # Verify creative_direction was passed in the user_message
        call_kwargs = mock_loop.call_args
        user_msg = call_kwargs.kwargs["user_message"]
        assert "Creative Direction" in user_msg
        assert "S4C" in user_msg
        assert "A1" in user_msg
        assert "dramatic, kinetic, high-fashion" in user_msg
        assert "motion blur" in user_msg

    @pytest.mark.asyncio
    async def test_prompt_node_no_creative_direction_fallback(self):
        """prompt_node should work without creative_direction (v1 compat)."""
        state = {
            "product_id": "TEST001",
            "product_path": "/tmp/test",
            "direction": "hero",
            "product_data": {
                "product_id": "TEST001",
                "category": "rings",
                "reference_anchor": "REFERENCE ANCHOR: Ring.\nMaintain integrity.\nRigid constraint.",
            },
            "slot_info": {
                "description": "Hero shot",
                "rationale": "Main image",
                # No creative_direction
            },
            "is_packaging": False,
        }

        mock_return = {
            "text": "SCENE CONTEXT: Studio.\n\nPHYSICS & REALISM: Film grain, dust particles.",
            "cost_usd": 0.03,
            "usage_metadata": {"input_tokens": 80, "output_tokens": 40, "total_tokens": 120, "turns": 2},
            "model": "MiniMax-M2.5",
        }

        with patch('etsy_listing_agent.nodes.agentic_loop', return_value=mock_return) as mock_loop:
            result = await prompt_node(state)

        # Should still work, just without creative_direction block
        user_msg = mock_loop.call_args.kwargs["user_message"]
        assert "Creative Direction" not in user_msg
        assert result["prompt_results"][0]["success"] is True


class TestAggregatorStyleSeries:
    """Tests for style_series in aggregator output."""

    def test_aggregator_includes_style_series(self, tmp_path):
        """aggregator should include style_series from strategy slots."""
        # Create strategy file with creative_direction
        strategy = {
            "slots": [
                {"type": "hero", "description": "Hero", "rationale": "Main",
                 "creative_direction": {"style_series": "S3"}},
                {"type": "macro_detail", "description": "Macro", "rationale": "Detail",
                 "creative_direction": {"style_series": "S4C"}},
            ]
        }
        with open(tmp_path / "TEST001_image_strategy.json", "w") as f:
            json.dump(strategy, f)

        prompt_results = [
            {"direction": "hero", "prompt": "Hero prompt", "success": True, "cost_usd": 0.05},
            {"direction": "macro_detail", "prompt": "Macro prompt", "success": True, "cost_usd": 0.04},
        ]

        state = {
            "product_id": "TEST001",
            "product_path": str(tmp_path),
            "prompt_results": prompt_results,
            "product_data": {"images": [{"filename": "img1.jpg"}]},
        }

        result = prompt_aggregator_node(state)
        output_file = Path(result["output_file"])
        with open(output_file) as f:
            data = json.load(f)

        assert data["prompts"][0]["style_series"] == "S3"
        assert data["prompts"][1]["style_series"] == "S4C"

    def test_aggregator_empty_style_series_for_v1(self, tmp_path):
        """aggregator should have empty style_series for v1 strategy."""
        # V1 strategy without creative_direction
        strategy = {
            "slots": [
                {"type": "hero", "description": "Hero", "rationale": "Main"},
            ]
        }
        with open(tmp_path / "TEST001_image_strategy.json", "w") as f:
            json.dump(strategy, f)

        prompt_results = [
            {"direction": "hero", "prompt": "Hero prompt", "success": True, "cost_usd": 0.05},
        ]

        state = {
            "product_id": "TEST001",
            "product_path": str(tmp_path),
            "prompt_results": prompt_results,
            "product_data": {"images": []},
        }

        result = prompt_aggregator_node(state)
        output_file = Path(result["output_file"])
        with open(output_file) as f:
            data = json.load(f)

        assert data["prompts"][0]["style_series"] == ""
