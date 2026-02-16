# Tests for ProductState and ReviewResult
# TDD: 先写测试，看它失败，再写代码

import pytest
from etsy_listing_agent.state import ProductState, ReviewResult, ReviewLevel


class TestReviewResult:
    """测试 ReviewResult dataclass"""

    def test_create_passed_review(self):
        """ReviewResult 应该能表示通过的审核"""
        result = ReviewResult(passed=True, level=ReviewLevel.SCHEMA)
        assert result.passed is True
        assert result.level == ReviewLevel.SCHEMA
        assert result.errors == []
        assert result.feedback is None

    def test_create_failed_review_with_errors(self):
        """ReviewResult 应该能包含错误列表"""
        errors = ["Missing required field: product_id", "Invalid category value"]
        result = ReviewResult(
            passed=False,
            level=ReviewLevel.SCHEMA,
            errors=errors,
        )
        assert result.passed is False
        assert result.errors == errors

    def test_create_review_with_feedback(self):
        """ReviewResult 应该能包含 AI 反馈（用于 semantic level）"""
        result = ReviewResult(
            passed=False,
            level=ReviewLevel.SEMANTIC,
            errors=["Title not compelling"],
            feedback="The title should highlight the unique Tibetan craftsmanship...",
        )
        assert result.level == ReviewLevel.SEMANTIC
        assert result.feedback is not None

    def test_review_levels(self):
        """验证三层 review 级别"""
        assert ReviewLevel.SCHEMA.value == 1
        assert ReviewLevel.RULES.value == 2
        assert ReviewLevel.SEMANTIC.value == 3


class TestProductState:
    """测试 ProductState TypedDict"""

    def test_create_initial_state(self):
        """ProductState 应该能创建初始状态"""
        state = ProductState(
            product_id="R001",
            product_path="/products/MentorArtCircle/rings/R001/",
            category="rings",
            excel_row={"SKU": "R001", "Name": "藏式六字真言戒指"},
            image_files=["R001_01.jpg", "R001_02.jpg"],
            stage="pending",
            preprocessing_review=None,
            strategy_review=None,
            nanobanana_review=None,
            listing_review=None,
            image_strategy=None,
            retry_counts={"preprocessing": 0, "strategy": 0, "nanobanana": 0, "listing": 0},
            max_retries=3,
            success=False,
            final_error=None,
        )
        assert state["product_id"] == "R001"
        assert state["stage"] == "pending"
        assert state["success"] is False

    def test_state_stage_literals(self):
        """验证 stage 的所有有效值"""
        valid_stages = [
            "pending",
            "preprocessing",
            "preprocessing_review",
            "strategy",
            "strategy_review",
            "nanobanana",
            "nanobanana_review",
            "listing",
            "listing_review",
            "completed",
            "failed",
        ]
        # 创建每个 stage 的状态验证类型正确
        for stage in valid_stages:
            state = ProductState(
                product_id="R001",
                product_path="/test/",
                category="rings",
                excel_row={},
                image_files=[],
                stage=stage,
                preprocessing_review=None,
                strategy_review=None,
                nanobanana_review=None,
                listing_review=None,
                image_strategy=None,
                retry_counts={},
                max_retries=3,
                success=False,
                final_error=None,
            )
            assert state["stage"] == stage

    def test_state_with_review_result(self):
        """ProductState 应该能包含 ReviewResult"""
        review = ReviewResult(passed=True, level=ReviewLevel.SCHEMA)
        state = ProductState(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
            stage="preprocessing_review",
            preprocessing_review=review,
            strategy_review=None,
            nanobanana_review=None,
            listing_review=None,
            image_strategy=None,
            retry_counts={"preprocessing": 0},
            max_retries=3,
            success=False,
            final_error=None,
        )
        assert state["preprocessing_review"] is not None
        assert state["preprocessing_review"].passed is True


class TestStateFactory:
    """测试创建初始状态的工厂函数"""

    def test_create_initial_state_from_product_path(self):
        """从产品路径创建初始状态"""
        from etsy_listing_agent.state import create_initial_state

        state = create_initial_state(
            product_id="R001",
            product_path="/products/MentorArtCircle/rings/R001/",
            category="rings",
            excel_row={"SKU": "R001", "Name": "藏式六字真言戒指"},
            image_files=["R001_01.jpg"],
        )
        assert state["product_id"] == "R001"
        assert state["stage"] == "pending"
        assert state["retry_counts"] == {"preprocessing": 0, "strategy": 0, "nanobanana": 0, "listing": 0}
        assert state["max_retries"] == 3
        assert state["success"] is False
