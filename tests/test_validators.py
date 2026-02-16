# Tests for schema and rule-based validators
# TDD: Layer 1 (Schema) 和 Layer 2 (Rules) 验证器

import pytest
from etsy_listing_agent.validators import (
    validate_product_data_schema,
    validate_nanobanana_schema,
    validate_listing_schema,
    ValidationError,
)
from etsy_listing_agent.state import ReviewResult, ReviewLevel


class TestProductDataSchemaValidator:
    """Layer 1: product_data.json schema 验证"""

    # Shared valid visual_features and selling_points for all tests
    VISUAL_FEATURES = {
        "material_finish": "metallic",
        "color_tone": "cool",
        "surface_quality": "engraved",
        "light_interaction": "reflective",
    }
    SELLING_POINTS = [
        {"feature": "Tibetan mantra", "benefit": "Spiritual significance"},
        {"feature": "Sterling silver", "benefit": "Durable and hypoallergenic"},
    ]

    def test_valid_product_data(self):
        """有效的 product_data 应该通过验证"""
        data = {
            "product_id": "R001",
            "product_path": "/products/rings/R001/",
            "category": "rings",
            "style": "tibetan",
            "target_audience": "neutral",
            "materials": ["sterling_silver"],
            "product_size": {"dimensions": "Band 6mm", "source": "excel"},
            "basic_info": "925 Sterling Silver Tibetan ring",
            "images": [
                {"filename": "R001_01.jpg", "angle": "front", "type": "product_only", "is_hero": True}
            ],
            "visual_features": self.VISUAL_FEATURES,
            "selling_points": self.SELLING_POINTS,
        }
        result = validate_product_data_schema(data)
        assert result.passed is True
        assert result.level == ReviewLevel.SCHEMA
        assert result.errors == []

    def test_missing_required_field(self):
        """缺少必填字段应该失败"""
        data = {
            "product_id": "R001",
            # missing: product_path, category, style, target_audience, materials, product_size, basic_info, images
        }
        result = validate_product_data_schema(data)
        assert result.passed is False
        assert result.level == ReviewLevel.SCHEMA
        assert any("product_path" in e for e in result.errors)

    def test_invalid_category(self):
        """无效的 category 值应该失败"""
        data = {
            "product_id": "R001",
            "product_path": "/products/rings/R001/",
            "category": "shoes",  # invalid
            "style": "tibetan",
            "target_audience": "neutral",
            "materials": ["sterling_silver"],
            "product_size": {"dimensions": "Band 6mm", "source": "excel"},
            "basic_info": "test",
            "images": [{"filename": "test.jpg", "angle": "front", "type": "product_only", "is_hero": True}],
            "visual_features": self.VISUAL_FEATURES,
            "selling_points": self.SELLING_POINTS,
        }
        result = validate_product_data_schema(data)
        assert result.passed is False
        assert any("category" in e.lower() for e in result.errors)

    def test_invalid_style(self):
        """无效的 style 值应该失败"""
        data = {
            "product_id": "R001",
            "product_path": "/products/rings/R001/",
            "category": "rings",
            "style": "gothic",  # invalid
            "target_audience": "neutral",
            "materials": ["sterling_silver"],
            "product_size": {"dimensions": "Band 6mm", "source": "excel"},
            "basic_info": "test",
            "images": [{"filename": "test.jpg", "angle": "front", "type": "product_only", "is_hero": True}],
            "visual_features": self.VISUAL_FEATURES,
            "selling_points": self.SELLING_POINTS,
        }
        result = validate_product_data_schema(data)
        assert result.passed is False
        assert any("style" in e.lower() for e in result.errors)

    def test_empty_images_array(self):
        """空的 images 数组应该失败"""
        data = {
            "product_id": "R001",
            "product_path": "/products/rings/R001/",
            "category": "rings",
            "style": "tibetan",
            "target_audience": "neutral",
            "materials": ["sterling_silver"],
            "product_size": {"dimensions": "Band 6mm", "source": "excel"},
            "basic_info": "test",
            "images": [],  # empty
            "visual_features": self.VISUAL_FEATURES,
            "selling_points": self.SELLING_POINTS,
        }
        result = validate_product_data_schema(data)
        assert result.passed is False
        assert any("images" in e.lower() for e in result.errors)

    def test_invalid_image_angle(self):
        """无效的 image angle 应该失败"""
        data = {
            "product_id": "R001",
            "product_path": "/products/rings/R001/",
            "category": "rings",
            "style": "tibetan",
            "target_audience": "neutral",
            "materials": ["sterling_silver"],
            "product_size": {"dimensions": "Band 6mm", "source": "excel"},
            "basic_info": "test",
            "images": [{"filename": "test.jpg", "angle": "diagonal", "type": "product_only", "is_hero": True}],
            "visual_features": self.VISUAL_FEATURES,
            "selling_points": self.SELLING_POINTS,
        }
        result = validate_product_data_schema(data)
        assert result.passed is False
        assert any("angle" in e.lower() for e in result.errors)


class TestNanoBananaSchemaValidator:
    """Layer 1: NanoBanana prompts schema 验证 (按 schema 定义, V3: 10 prompts)"""

    # V3: 10 types (5 required + 5 strategic)
    ALL_10_TYPES = [
        "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
        "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
    ]

    def _make_valid_prompt(self, index: int, image_type: str) -> dict:
        """创建一个符合 schema 格式的有效 prompt"""
        # Hero needs: no hands, light background, anti-AI realism
        if image_type == "hero":
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. Close-up macro on cream background. No hands. No fingers. "
                "Film grain, dust particles."
            )
        else:
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. Close-up with film grain and natural imperfections."
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
            "camera_params": {"aspect_ratio": "1:1", "lens": "85mm", "aperture": "f/11"},
        }

    def test_valid_nanobanana_output(self):
        """有效的 NanoBanana output 应该通过验证 (10 prompts)"""
        data = {
            "product_id": "R001",
            "prompts": [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)],
        }
        result = validate_nanobanana_schema(data)
        assert result.passed is True
        assert result.level == ReviewLevel.SCHEMA

    def test_missing_product_id(self):
        """缺少 product_id 应该失败"""
        data = {
            "prompts": [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)],
        }
        result = validate_nanobanana_schema(data)
        assert result.passed is False
        assert any("product_id" in e for e in result.errors)

    def test_wrong_prompt_count(self):
        """不是 10 个 prompts 应该失败"""
        data = {
            "product_id": "R001",
            "prompts": [self._make_valid_prompt(1, "hero")] * 5,  # only 5
        }
        result = validate_nanobanana_schema(data)
        assert result.passed is False
        assert any("10" in e or "prompts" in e.lower() for e in result.errors)

    def test_missing_required_fields(self):
        """缺少必填字段应该失败"""
        data = {
            "product_id": "R001",
            "prompts": [{"index": i+1, "type": "hero", "prompt": "test"} for i in range(10)],
        }
        result = validate_nanobanana_schema(data)
        assert result.passed is False
        assert any("reference_images" in e for e in result.errors)

    def test_reference_images_must_be_3_or_4(self):
        """reference_images 必须是 3-4 张"""
        prompts = [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)]
        prompts[0]["reference_images"] = ["img1.jpg"]  # only 1 — fails
        data = {
            "product_id": "R001",
            "prompts": prompts,
        }
        result = validate_nanobanana_schema(data)
        assert result.passed is False
        assert any("reference_images" in e for e in result.errors)

    def test_missing_prompt_text_fails(self):
        """missing prompt text field should fail"""
        prompts = [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)]
        del prompts[0]["prompt"]  # Remove required field
        data = {
            "product_id": "R001",
            "prompts": prompts,
        }
        result = validate_nanobanana_schema(data)
        assert result.passed is False
        assert any("prompt" in e for e in result.errors)


class TestListingSchemaValidator:
    """Layer 1: Etsy Listing schema 验证 (按 schema 定义)"""

    def test_valid_listing(self):
        """有效的 listing 应该通过验证"""
        data = {
            "product_id": "R001",
            "title": "Sterling Silver Tibetan Ring Buddhist Band",
            "tags": "tibetan ring, sterling silver, buddhist jewelry, meditation ring, prayer ring, spiritual jewelry, om ring, yoga ring, mens ring, unisex ring, silver band, mantra ring, adjustable ring",  # 13 tags as string
            "description": "Handcrafted sterling silver ring with traditional Tibetan mantra...",
            "attributes": {
                "material": "Sterling Silver",
                "style": "Tibetan",
            },
        }
        result = validate_listing_schema(data)
        assert result.passed is True
        assert result.level == ReviewLevel.SCHEMA

    def test_missing_title(self):
        """缺少 title 应该失败"""
        data = {
            "product_id": "R001",
            "tags": "test tag, another tag",
            "description": "test description that is long enough",
            "attributes": {},
        }
        result = validate_listing_schema(data)
        assert result.passed is False
        assert any("title" in e for e in result.errors)

    def test_empty_tags(self):
        """空的 tags 字符串应该失败"""
        data = {
            "product_id": "R001",
            "title": "Test Title",
            "tags": "",  # empty string
            "description": "test description that is long enough",
            "attributes": {},
        }
        result = validate_listing_schema(data)
        assert result.passed is False
        assert any("tags" in e.lower() for e in result.errors)

    def test_tags_as_array_fails(self):
        """tags 作为数组应该失败（应该是字符串）"""
        data = {
            "product_id": "R001",
            "title": "Test Title",
            "tags": ["tag1", "tag2"],  # array instead of string
            "description": "test description that is long enough",
            "attributes": {},
        }
        result = validate_listing_schema(data)
        assert result.passed is False
        assert any("tags" in e.lower() and "string" in e.lower() for e in result.errors)


# ===== Layer 2: Rule-based Validators =====

from etsy_listing_agent.validators import (
    validate_product_data_rules,
    validate_nanobanana_rules,
    validate_listing_rules,
    validate_strategy_schema,
    validate_strategy_rules,
    VALID_STYLE_SERIES,
    TIER_3_4_SERIES,
    POSE_FEASIBILITY,
)


class TestProductDataRulesValidator:
    """Layer 2: product_data 业务规则验证"""

    def test_earrings_must_have_design_type(self):
        """耳环类产品必须有 earring_design_type"""
        data = {
            "product_id": "E001",
            "category": "earrings",
            "earring_design_type": None,  # missing for earrings
        }
        result = validate_product_data_rules(data)
        assert result.passed is False
        assert result.level == ReviewLevel.RULES
        assert any("earring_design_type" in e for e in result.errors)

    def test_earrings_with_valid_design_type(self):
        """耳环有有效的 design_type 应该通过"""
        data = {
            "product_id": "E001",
            "category": "earrings",
            "earring_design_type": "flat_front",
            "basic_info": "Pearl earrings with sterling silver posts and lever back closure",
        }
        result = validate_product_data_rules(data)
        assert result.passed is True

    def test_rings_no_design_type_ok(self):
        """戒指不需要 earring_design_type"""
        data = {
            "product_id": "R001",
            "category": "rings",
            "earring_design_type": None,
            "basic_info": "925 Sterling Silver Tibetan ring with mantra engraving",
        }
        result = validate_product_data_rules(data)
        assert result.passed is True

    def test_basic_info_not_too_short(self):
        """basic_info 不能太短 (至少 20 字符)"""
        data = {
            "product_id": "R001",
            "category": "rings",
            "basic_info": "short",  # too short
        }
        result = validate_product_data_rules(data)
        assert result.passed is False
        assert any("basic_info" in e for e in result.errors)


class TestNanoBananaRulesValidator:
    """Layer 2: NanoBanana prompts 业务规则验证 (V3: 5 required + 5 strategic)"""

    # V3: 10 types (5 required + 5 strategic)
    ALL_10_TYPES = [
        "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
        "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
    ]

    def _make_valid_prompt(self, index: int, image_type: str) -> dict:
        """创建一个符合 schema 格式的有效 prompt (with size info)"""
        if image_type == "hero":
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                "1:1 aspect ratio. The ring, approximately 18mm band, on cream background. "
                "No hands. No fingers. Film grain, dust particles."
            )
        elif image_type in ("macro_detail", "packaging"):
            # No anti-AI modifiers for these types
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                f"1:1 aspect ratio. {image_type} shot. The ring, approximately 18mm band. "
                "Clean commercial lighting."
            )
        else:
            prompt_text = (
                "REFERENCE ANCHOR: The input image depicts a ring. "
                "Maintain exact structural integrity. Do not alter geometry. Rigid constraint.\n\n"
                f"1:1 aspect ratio. The ring, approximately 18mm band. "
                "Close-up with film grain and natural imperfections."
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

    def test_missing_required_types_fails(self):
        """prompts missing required types should fail"""
        # All same type - should fail (missing other required types)
        data = {
            "prompts": [self._make_valid_prompt(i, "hero") for i in range(1, 11)],
        }
        result = validate_nanobanana_rules(data)
        assert result.passed is False
        assert any("missing" in e.lower() and "type" in e.lower() for e in result.errors)

    def test_prompts_with_all_10_types_pass(self):
        """包含所有 10 种 image types (5 required + 5 strategic) 应该通过"""
        data = {
            "prompts": [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)],
        }
        result = validate_nanobanana_rules(data)
        assert result.passed is True

    def test_prompt_text_not_too_short(self):
        """每个 prompt 文本不能太短 (至少 50 字符)"""
        prompts = [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)]
        prompts[0]["prompt"] = "short"  # First one is too short
        data = {"prompts": prompts}
        result = validate_nanobanana_rules(data)
        assert result.passed is False
        assert any("prompt" in e.lower() and ("short" in e.lower() or "character" in e.lower()) for e in result.errors)

    def test_hero_series_rules_relaxed(self):
        """hero series_used rules are relaxed — wrong series should still pass"""
        prompts = [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)]
        prompts[0]["series_used"] = "S1 Ephemeral Contrast"  # Different series
        data = {"prompts": prompts}
        result = validate_nanobanana_rules(data)
        # Hero rules are relaxed, so this should pass
        assert result.passed is True

    def test_hero_aperture_rules_relaxed(self):
        """hero aperture rules are relaxed — wrong aperture should still pass"""
        prompts = [self._make_valid_prompt(i+1, t) for i, t in enumerate(self.ALL_10_TYPES)]
        prompts[0]["camera_params"]["aperture"] = "f/2.8"  # Different aperture
        data = {"prompts": prompts}
        result = validate_nanobanana_rules(data)
        # Hero rules are relaxed, so this should pass
        assert result.passed is True


class TestListingRulesValidator:
    """Layer 2: Etsy Listing 业务规则验证 (按 schema)"""

    def test_title_max_14_words(self):
        """title 不能超过 14 个单词"""
        data = {
            "title": "word " * 20,  # 20 words - too many
            "tags": "a, b, c, d, e, f, g, h, i, j, k, l, m",  # 13 tags
            "description": "test description that is long enough for validation",
        }
        result = validate_listing_rules(data)
        assert result.passed is False
        assert any("title" in e.lower() and "14" in e and "word" in e.lower() for e in result.errors)

    def test_title_within_14_words(self):
        """title 14 个单词以内应该通过"""
        data = {
            "title": "Sterling Silver Tibetan Ring Buddhist Band Mantra",  # 7 words
            "tags": "a, b, c, d, e, f, g, h, i, j, k, l, m",  # exactly 13
            "description": "test description that is long enough for validation",
        }
        result = validate_listing_rules(data)
        assert result.passed is True

    def test_tags_exactly_13(self):
        """必须正好 13 个 tags"""
        data = {
            "title": "Test Title",
            "tags": "a, b, c, d, e",  # only 5
            "description": "test description that is long enough for validation",
        }
        result = validate_listing_rules(data)
        assert result.passed is False
        assert any("13" in e and "tags" in e.lower() for e in result.errors)

    def test_each_tag_max_20_chars(self):
        """每个 tag 不能超过 20 字符"""
        long_tag = "a" * 25
        # 13 tags but one is too long
        data = {
            "title": "Test Title",
            "tags": f"{long_tag}, b, c, d, e, f, g, h, i, j, k, l, m",
            "description": "test description that is long enough for validation",
        }
        result = validate_listing_rules(data)
        assert result.passed is False
        assert any("20" in e and "character" in e.lower() for e in result.errors)

    def test_long_tail_keywords_should_be_8(self):
        """long_tail_keywords 应该是 8 个"""
        data = {
            "title": "Test Title",
            "tags": "a, b, c, d, e, f, g, h, i, j, k, l, m",
            "description": "test description that is long enough for validation",
            "long_tail_keywords": ["kw1", "kw2", "kw3"],  # only 3
        }
        result = validate_listing_rules(data)
        assert result.passed is False
        assert any("8" in e and "long_tail" in e.lower() for e in result.errors)

    def test_description_min_length(self):
        """description 至少 30 字符"""
        data = {
            "title": "Test Title",
            "tags": "a, b, c, d, e, f, g, h, i, j, k, l, m",
            "description": "short",  # too short
        }
        result = validate_listing_rules(data)
        assert result.passed is False
        assert any("description" in e.lower() for e in result.errors)


# ===== V2 Creative Direction Strategy Tests =====


class TestStrategyV2Schema:
    """Layer 1: V2 schema requires creative_direction fields."""

    def _make_creative_direction(self, series: str = "S3", pose: str | None = None,
                                  scene: str | None = None) -> dict:
        return {
            "style_series": series,
            "pose": pose,
            "scene_module": scene,
            "mood": "clean, minimal",
            "key_visual": "Product centered with sharp focus",
        }

    def _make_v2_strategy(self) -> dict:
        """Create a valid v2 strategy."""
        series_choices = ["S3", "S5A", "S1", "S5A", "S3",
                          "S4C", "S1", "S4B", "S2", "S5C"]
        scenes = [None, None, None, None, None,
                  None, "G1", "F2", None, "H2"]
        poses = [None, "A1", "A2", "B1", None,
                 None, None, None, None, None]
        return {
            "$schema": "image_strategy_v2",
            "product_id": "R001",
            "analysis": {
                "product_usps": ["handcrafted", "925 silver"],
                "target_customer": "spiritual adults",
                "purchase_barriers": ["can't feel quality"],
                "competitive_gap": "no lifestyle shots",
                "creative_narrative": "Moody editorial meets modern minimalism",
            },
            "creative_diversity": {
                "series_used": ["S1", "S2", "S3", "S4B", "S4C", "S5A", "S5C"],
                "tier_3_4_count": 4,
                "pose_categories_used": ["A", "B"],
            },
            "slots": [
                {
                    "slot": i + 1,
                    "type": t,
                    "category": "required" if i < 5 else "strategic",
                    "description": f"Slot {i+1} desc",
                    "rationale": f"Slot {i+1} rationale",
                    "creative_direction": self._make_creative_direction(
                        series=series_choices[i],
                        pose=poses[i],
                        scene=scenes[i],
                    ),
                }
                for i, t in enumerate([
                    "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
                    "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
                ])
            ],
        }

    def test_v2_schema_valid(self):
        """Valid v2 strategy passes schema validation."""
        result = validate_strategy_schema(self._make_v2_strategy())
        assert result.passed is True

    def test_v2_schema_missing_creative_direction(self):
        """V2 schema requires creative_direction per slot."""
        data = self._make_v2_strategy()
        del data["slots"][0]["creative_direction"]
        result = validate_strategy_schema(data)
        assert result.passed is False
        assert any("creative_direction" in e for e in result.errors)

    def test_v2_schema_missing_creative_narrative(self):
        """V2 schema requires creative_narrative in analysis."""
        data = self._make_v2_strategy()
        del data["analysis"]["creative_narrative"]
        result = validate_strategy_schema(data)
        assert result.passed is False
        assert any("creative_narrative" in e for e in result.errors)

    def test_v2_schema_missing_creative_diversity(self):
        """V2 schema requires creative_diversity section."""
        data = self._make_v2_strategy()
        del data["creative_diversity"]
        result = validate_strategy_schema(data)
        assert result.passed is False
        assert any("creative_diversity" in e for e in result.errors)

    def test_v2_schema_invalid_style_series(self):
        """Invalid style_series should fail schema."""
        data = self._make_v2_strategy()
        data["slots"][0]["creative_direction"]["style_series"] = "S99"
        result = validate_strategy_schema(data)
        assert result.passed is False
        assert any("style_series" in e for e in result.errors)

    def test_v2_schema_missing_required_cd_fields(self):
        """creative_direction missing mood or key_visual should fail."""
        data = self._make_v2_strategy()
        del data["slots"][0]["creative_direction"]["key_visual"]
        result = validate_strategy_schema(data)
        assert result.passed is False
        assert any("key_visual" in e for e in result.errors)

    def test_v1_schema_still_valid(self):
        """V1 strategy (no creative_direction) should still pass schema."""
        data = {
            "$schema": "image_strategy_v1",
            "product_id": "R001",
            "analysis": {
                "product_usps": ["handcrafted"],
                "target_customer": "adults",
                "purchase_barriers": ["quality"],
                "competitive_gap": "basic shots",
            },
            "slots": [
                {"slot": i + 1, "type": t, "category": "required" if i < 5 else "strategic",
                 "description": "desc", "rationale": "rationale"}
                for i, t in enumerate([
                    "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
                    "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
                ])
            ],
        }
        result = validate_strategy_schema(data)
        assert result.passed is True


class TestStrategyV2Rules:
    """Layer 2: V2 creative direction business rules."""

    def _make_creative_direction(self, series: str = "S3", pose: str | None = None,
                                  scene: str | None = None) -> dict:
        return {
            "style_series": series,
            "pose": pose,
            "scene_module": scene,
            "mood": "clean, minimal",
            "key_visual": "Product centered",
        }

    def _make_v2_strategy(self, wearing_a_series: str = "S1",
                           wearing_b_series: str = "S5A") -> dict:
        """Create a valid v2 strategy with configurable wearing series."""
        types = [
            "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
            "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
        ]
        series = ["S3", "S5A", wearing_a_series, wearing_b_series, "S3",
                  "S4C", "S1", "S4B", "S2", "S5C"]
        # Each slot gets a unique scene_module to avoid creative twins
        scenes = ["F1", "F2", None, None, "F3",
                  "G3", "G1", "G2", "H1", "H2"]
        poses = [None, "A1", "A2", "B1", None,
                 None, None, None, None, None]
        return {
            "$schema": "image_strategy_v2",
            "product_id": "R001",
            "analysis": {
                "product_usps": ["handcrafted"],
                "target_customer": "adults",
                "purchase_barriers": ["quality"],
                "competitive_gap": "basic shots",
                "creative_narrative": "Contrast story",
            },
            "creative_diversity": {
                "series_used": list(set(series)),
                "tier_3_4_count": 4,
                "pose_categories_used": ["A", "B"],
            },
            "slots": [
                {
                    "slot": i + 1,
                    "type": types[i],
                    "category": "required" if i < 5 else "strategic",
                    "description": f"Slot {i+1}",
                    "rationale": f"Reason {i+1}",
                    "creative_direction": self._make_creative_direction(
                        series=series[i], pose=poses[i], scene=scenes[i],
                    ),
                }
                for i in range(10)
            ],
        }

    def test_wearing_different_series_passes(self):
        """wearing_a and wearing_b with different series passes."""
        data = self._make_v2_strategy(wearing_a_series="S1", wearing_b_series="S5A")
        result = validate_strategy_rules(data)
        assert result.passed is True

    def test_wearing_same_series_fails(self):
        """wearing_a and wearing_b with same series fails."""
        data = self._make_v2_strategy(wearing_a_series="S5A", wearing_b_series="S5A")
        result = validate_strategy_rules(data)
        assert result.passed is False
        assert any("wearing_a" in e and "wearing_b" in e for e in result.errors)

    def test_tier_3_4_minimum(self):
        """Strategic slots need at least 2 Tier 3-4 series."""
        data = self._make_v2_strategy()
        # Set all strategic slots to Tier 1-2 (S3, S5A, S5B)
        for slot in data["slots"][5:10]:
            slot["creative_direction"]["style_series"] = "S3"
            slot["creative_direction"]["scene_module"] = f"F{slot['slot']}"  # avoid twins
        result = validate_strategy_rules(data)
        assert result.passed is False
        assert any("Tier 3-4" in e for e in result.errors)

    def test_pose_feasibility_rings(self):
        """Invalid pose for rings should fail."""
        data = self._make_v2_strategy()
        # E2 (Whisper Close) is NOT valid for rings
        data["slots"][2]["creative_direction"]["pose"] = "E2"
        result = validate_strategy_rules(data, category="rings")
        assert result.passed is False
        assert any("pose" in e.lower() and "E2" in e for e in result.errors)

    def test_pose_feasibility_valid(self):
        """Valid pose for rings should pass."""
        data = self._make_v2_strategy()
        data["slots"][2]["creative_direction"]["pose"] = "A1"
        result = validate_strategy_rules(data, category="rings")
        assert result.passed is True

    def test_no_creative_twins(self):
        """Two slots with same (series, scene_module) should fail."""
        data = self._make_v2_strategy()
        # Make slots 6 and 7 identical
        data["slots"][5]["creative_direction"]["style_series"] = "S4C"
        data["slots"][5]["creative_direction"]["scene_module"] = "G1"
        data["slots"][6]["creative_direction"]["style_series"] = "S4C"
        data["slots"][6]["creative_direction"]["scene_module"] = "G1"
        result = validate_strategy_rules(data)
        assert result.passed is False
        assert any("twin" in e.lower() for e in result.errors)

    def test_same_series_null_scene_not_twin(self):
        """Two slots with same series but both scene_module=None should NOT be twins."""
        data = self._make_v2_strategy()
        # wearing_a and wearing_b slots both have scene_module=None — that's fine
        data["slots"][2]["creative_direction"]["scene_module"] = None
        data["slots"][3]["creative_direction"]["scene_module"] = None
        # They already have different series, but let's also test same series case
        data2 = self._make_v2_strategy()
        data2["slots"][0]["creative_direction"]["style_series"] = "S3"
        data2["slots"][0]["creative_direction"]["scene_module"] = None
        data2["slots"][4]["creative_direction"]["style_series"] = "S3"
        data2["slots"][4]["creative_direction"]["scene_module"] = None
        result = validate_strategy_rules(data2)
        # Should not fail on twins (both scene_module=None is allowed)
        assert not any("twin" in e.lower() for e in result.errors)

    def test_minimum_3_series(self):
        """Must use at least 3 different style series."""
        data = self._make_v2_strategy()
        # Set all slots to same 2 series
        for i, slot in enumerate(data["slots"]):
            slot["creative_direction"]["style_series"] = "S3" if i % 2 == 0 else "S5A"
            slot["creative_direction"]["scene_module"] = f"F{i+1}"  # avoid twins
        result = validate_strategy_rules(data)
        assert result.passed is False
        assert any("3 different" in e for e in result.errors)

    def test_v1_strategy_no_creative_rules(self):
        """V1 strategy (no creative_direction) should skip creative rules."""
        data = {
            "$schema": "image_strategy_v1",
            "product_id": "R001",
            "analysis": {
                "product_usps": ["handcrafted"],
                "target_customer": "adults",
                "purchase_barriers": ["quality"],
                "competitive_gap": "basic shots",
            },
            "slots": [
                {"slot": i + 1, "type": t, "category": "required" if i < 5 else "strategic",
                 "description": "desc", "rationale": "rationale"}
                for i, t in enumerate([
                    "hero", "size_reference", "wearing_a", "wearing_b", "packaging",
                    "macro_detail", "art_still_life", "scene_daily", "workshop", "art_abstract",
                ])
            ],
        }
        result = validate_strategy_rules(data)
        assert result.passed is True


class TestCreativeDirectionConstants:
    """Test creative direction constants are correct."""

    def test_valid_style_series_count(self):
        assert len(VALID_STYLE_SERIES) == 9

    def test_tier_3_4_subset(self):
        assert TIER_3_4_SERIES.issubset(VALID_STYLE_SERIES)

    def test_s4c_in_tier_3_4(self):
        assert "S4C" in TIER_3_4_SERIES

    def test_pose_feasibility_rings(self):
        assert "A1" in POSE_FEASIBILITY["rings"]
        assert "E2" not in POSE_FEASIBILITY["rings"]

    def test_pose_feasibility_earrings(self):
        assert "E2" in POSE_FEASIBILITY["earrings"]
        assert "C1" not in POSE_FEASIBILITY["earrings"]
