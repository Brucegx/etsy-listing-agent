# ProductState and ReviewResult definitions
# Data structure definitions for product state and review results

import operator
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Annotated, Literal, Optional, TypedDict


class ReviewLevel(IntEnum):
    """Review levels: Schema(1) -> Rules(2) -> Semantic(3)"""

    SCHEMA = 1  # JSON schema validation, 0 tokens
    RULES = 2  # Business rules validation, 0 tokens
    SEMANTIC = 3  # AI semantic review, ~1000 tokens


@dataclass
class ReviewResult:
    """Review result"""

    passed: bool
    level: ReviewLevel
    errors: list[str] = field(default_factory=list)
    feedback: Optional[str] = None  # AI feedback, used for retry


# Stage type definition
StageType = Literal[
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


class ProductState(TypedDict):
    """LangGraph state: processing state for a single product"""

    # Product identifiers
    product_id: str
    product_path: str
    category: str

    # Input data
    excel_row: dict  # Excel row data
    image_files: list[str]  # List of product image files

    # Workflow state
    stage: StageType

    # Review results for each stage
    preprocessing_review: Optional[ReviewResult]
    strategy_review: Optional[ReviewResult]
    nanobanana_review: Optional[ReviewResult]
    listing_review: Optional[ReviewResult]

    # Image strategy
    image_strategy: Optional[dict]

    # Retry control
    retry_counts: dict[str, int]  # {"preprocessing": 0, "nanobanana": 0, "listing": 0}
    max_retries: int

    # Final results
    success: bool
    final_error: Optional[str]

    # Image generation
    generate_images: bool  # Whether to generate images
    image_gen_result: Optional[dict]  # Image generation result {"success", "generated", "failed"}

    # Fan-out support
    prompt_results: Annotated[list[dict], operator.add]  # prompt_node result collection (reducer for fan-out)
    nanobanana_success: bool  # Whether all prompts succeeded
    output_file: str  # NanoBanana JSON output path
    total_cost: float  # Total cost


class PromptNodeState(TypedDict, total=False):
    """State for individual prompt generation node in fan-out.

    Each prompt_node receives this state with direction-specific data,
    generates a validated prompt, and returns results for aggregation.
    """
    # Input from fan-out
    product_id: str
    product_path: str
    direction: str  # e.g., "hero", "wearing_a", "art_abstract"
    product_data: dict  # Full product data for prompt generation
    slot_info: dict  # Strategy slot context: description, rationale, category
    is_packaging: bool  # True for packaging slot (fixed template, no MiniMax)

    # Output
    prompt: str  # Generated prompt text
    success: bool
    error: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int


def create_initial_state(
    product_id: str,
    product_path: str,
    category: str,
    excel_row: dict,
    image_files: list[str],
    max_retries: int = 3,
    generate_images: bool = False,
) -> ProductState:
    """Create initial state for a product"""
    return ProductState(
        product_id=product_id,
        product_path=product_path,
        category=category,
        excel_row=excel_row,
        image_files=image_files,
        stage="pending",
        preprocessing_review=None,
        strategy_review=None,
        nanobanana_review=None,
        listing_review=None,
        image_strategy=None,
        retry_counts={"preprocessing": 0, "strategy": 0, "nanobanana": 0, "listing": 0},
        max_retries=max_retries,
        success=False,
        final_error=None,
        generate_images=generate_images,
        image_gen_result=None,
        prompt_results=[],
        nanobanana_success=False,
        output_file="",
        total_cost=0.0,
    )
