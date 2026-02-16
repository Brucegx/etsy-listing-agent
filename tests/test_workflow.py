# Tests for LangGraph workflow structure
# TDD: 工作流图结构测试

import pytest
from etsy_listing_agent.workflow import (
    create_workflow,
    get_next_stage,
    should_retry,
)
from etsy_listing_agent.state import (
    ProductState,
    ReviewResult,
    ReviewLevel,
    create_initial_state,
)


class TestWorkflowStructure:
    """测试工作流图的基本结构"""

    def test_create_workflow_returns_graph(self):
        """create_workflow 应该返回一个可编译的图"""
        graph = create_workflow()
        assert graph is not None
        # 验证是 LangGraph 的 StateGraph
        assert hasattr(graph, "compile")

    def test_workflow_has_required_nodes(self):
        """工作流应该包含所有必需的节点"""
        graph = create_workflow()
        compiled = graph.compile()
        # LangGraph compiled graph 有 nodes 属性
        node_names = set(compiled.nodes.keys())
        required_nodes = {
            "preprocess",
            "preprocess_review",
            "nanobanana_fan_out",  # Fan-out dispatcher
            "prompt_node",  # Parallel prompt generation
            "prompt_aggregator",  # Collects results
            "image_gen",  # Optional image generation
            "listing",
            "listing_review",
        }
        for node in required_nodes:
            assert node in node_names, f"Missing required node: {node}"


class TestStageTransitions:
    """测试阶段转换逻辑"""

    def test_pending_to_preprocessing(self):
        """pending 阶段应该转到 preprocessing"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
        )
        next_stage = get_next_stage(state)
        assert next_stage == "preprocessing"

    def test_preprocessing_review_passed_to_strategy(self):
        """preprocessing_review 通过后应该转到 strategy"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
        )
        state["stage"] = "preprocessing_review"
        state["preprocessing_review"] = ReviewResult(passed=True, level=ReviewLevel.SCHEMA)
        next_stage = get_next_stage(state)
        assert next_stage == "strategy"

    def test_preprocessing_review_failed_to_preprocessing(self):
        """preprocessing_review 失败后应该重试 preprocessing"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
        )
        state["stage"] = "preprocessing_review"
        state["preprocessing_review"] = ReviewResult(
            passed=False, level=ReviewLevel.RULES, errors=["test error"]
        )
        state["retry_counts"]["preprocessing"] = 0
        next_stage = get_next_stage(state)
        assert next_stage == "preprocessing"  # retry

    def test_max_retries_to_failed(self):
        """达到最大重试次数后应该转到 failed"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
            max_retries=3,
        )
        state["stage"] = "preprocessing_review"
        state["preprocessing_review"] = ReviewResult(
            passed=False, level=ReviewLevel.RULES, errors=["test error"]
        )
        state["retry_counts"]["preprocessing"] = 3  # already at max
        next_stage = get_next_stage(state)
        assert next_stage == "failed"

    def test_listing_review_passed_to_completed(self):
        """listing_review 通过后应该转到 completed"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
        )
        state["stage"] = "listing_review"
        state["listing_review"] = ReviewResult(passed=True, level=ReviewLevel.SEMANTIC)
        next_stage = get_next_stage(state)
        assert next_stage == "completed"


class TestRetryLogic:
    """测试重试逻辑"""

    def test_should_retry_when_under_limit(self):
        """未达到重试上限时应该重试"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
            max_retries=3,
        )
        state["retry_counts"]["preprocessing"] = 1
        assert should_retry(state, "preprocessing") is True

    def test_should_not_retry_at_limit(self):
        """达到重试上限时不应该重试"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
            max_retries=3,
        )
        state["retry_counts"]["preprocessing"] = 3
        assert should_retry(state, "preprocessing") is False

    def test_should_retry_different_stages_independently(self):
        """不同阶段的重试计数应该独立"""
        state = create_initial_state(
            product_id="R001",
            product_path="/test/",
            category="rings",
            excel_row={},
            image_files=[],
            max_retries=3,
        )
        state["retry_counts"]["preprocessing"] = 3  # maxed out
        state["retry_counts"]["nanobanana"] = 1  # still has retries
        assert should_retry(state, "preprocessing") is False
        assert should_retry(state, "nanobanana") is True
