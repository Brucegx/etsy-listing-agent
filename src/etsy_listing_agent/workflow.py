# LangGraph workflow for Etsy Listing Agent
# Defines workflow graph structure and stage transition logic

import json
from pathlib import Path
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langsmith import traceable

from etsy_listing_agent.state import ProductState, ReviewResult
from etsy_listing_agent.nodes import (
    preprocess_node,
    preprocess_review_node,
    strategy_node,
    strategy_review_node,
    prompt_node,
    prompt_aggregator_node,
    listing_node,
    listing_fan_out_node,
    listing_review_node,
    image_gen_node,
)
from etsy_listing_agent.config_loader import NANOBANANA_DIRECTIONS


# ===== Fan-Out Configuration =====

FALLBACK_DIRECTIONS = NANOBANANA_DIRECTIONS


def _fan_out_to_prompts(state: ProductState) -> list[Send]:
    """
    Fan-out routing function - returns Send objects for parallel prompt generation.

    Reads strategy JSON to determine 10 dynamic slots.
    Falls back to FALLBACK_DIRECTIONS if no strategy file exists.
    """
    product_path = Path(state["product_path"])
    product_id = state["product_id"]

    # Load product_data for each prompt node
    product_data_file = product_path / "product_data.json"
    with open(product_data_file, encoding="utf-8") as f:
        product_data = json.load(f)

    # Load strategy (dynamic slots)
    strategy_file = product_path / f"{product_id}_image_strategy.json"
    if strategy_file.exists():
        with open(strategy_file, encoding="utf-8") as f:
            strategy = json.load(f)
        slots = strategy.get("slots", [])
    else:
        # Fallback to default directions (backward compat)
        slots = [
            {"slot": i + 1, "type": d, "category": "required" if i < 5 else "strategic",
             "description": "", "rationale": ""}
            for i, d in enumerate(FALLBACK_DIRECTIONS)
        ]

    print(f"  🚀 Fan-out: dispatching {len(slots)} parallel prompt_nodes + listing")

    sends = []
    for slot in slots:
        slot_type = slot.get("type", "unknown")
        sends.append(
            Send(
                "prompt_node",
                {
                    "product_id": product_id,
                    "product_path": str(product_path),
                    "direction": slot_type,
                    "product_data": product_data,
                    "slot_info": slot,
                    "is_packaging": slot_type == "packaging",
                }
            )
        )

    # Dispatch listing in parallel — it only needs product_data (already on disk)
    sends.append(Send("listing_fan_out", dict(state)))

    return sends


def _nanobanana_pass_through(state: ProductState) -> dict:
    """Pass-through node that marks stage transition to nanobanana."""
    return {"stage": "nanobanana"}


# ===== Stage Transition Logic =====


def should_retry(state: ProductState, stage: str) -> bool:
    """Determine whether the specified stage should be retried."""
    current_count = state["retry_counts"].get(stage, 0)
    return current_count < state["max_retries"]


def get_next_stage(
    state: ProductState,
) -> Literal[
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
]:
    """Determine the next stage based on current state."""
    current = state["stage"]

    # Initial state
    if current == "pending":
        return "preprocessing"

    # After preprocessing completes, enter review
    if current == "preprocessing":
        return "preprocessing_review"

    # Branch after preprocessing_review -> strategy (not nanobanana)
    if current == "preprocessing_review":
        review = state.get("preprocessing_review")
        if review and review.passed:
            return "strategy"
        else:
            if should_retry(state, "preprocessing"):
                return "preprocessing"
            else:
                return "failed"

    # After strategy completes, enter review
    if current == "strategy":
        return "strategy_review"

    # Branch after strategy_review
    if current == "strategy_review":
        review = state.get("strategy_review")
        if review and review.passed:
            return "nanobanana"
        else:
            if should_retry(state, "strategy"):
                return "strategy"
            else:
                return "failed"

    # After nanobanana completes, enter review
    if current == "nanobanana":
        return "nanobanana_review"

    # Branch after nanobanana_review
    if current == "nanobanana_review":
        review = state.get("nanobanana_review")
        if review and review.passed:
            return "listing"
        else:
            if should_retry(state, "nanobanana"):
                return "nanobanana"
            else:
                return "failed"

    # After listing completes, enter review
    if current == "listing":
        return "listing_review"

    # Branch after listing_review
    if current == "listing_review":
        review = state.get("listing_review")
        if review and review.passed:
            return "completed"
        else:
            if should_retry(state, "listing"):
                return "listing"
            else:
                return "failed"

    # Already completed or failed
    if current in ("completed", "failed"):
        return current

    # Default: return failed
    return "failed"


# ===== Terminal Nodes =====


def _completed_node(state: ProductState) -> ProductState:
    """Mark workflow as successfully completed."""
    state["stage"] = "completed"
    state["success"] = True
    state["final_error"] = None
    return state


def _failed_node(state: ProductState) -> ProductState:
    """Mark workflow as failed."""
    state["stage"] = "failed"
    state["success"] = False
    # Collect the error from the last failed review
    for review_key in ["listing_review", "nanobanana_review", "strategy_review", "preprocessing_review"]:
        review = state.get(review_key)
        if review and not review.passed:
            state["final_error"] = "; ".join(review.errors) if review.errors else "Validation failed"
            break
    else:
        state["final_error"] = "Unknown error"
    return state


# ===== Routing Functions =====


def _route_after_preprocess_review(
    state: ProductState,
) -> Literal["strategy", "preprocess", "failed"]:
    """Route after preprocessing_review - now routes to strategy."""
    next_stage = get_next_stage(state)
    if next_stage == "strategy":
        return "strategy"
    elif next_stage == "preprocessing":
        return "preprocess"
    else:
        return "failed"


def _route_after_strategy_review(
    state: ProductState,
) -> Literal["nanobanana_fan_out", "strategy", "failed"]:
    """Route after strategy_review."""
    next_stage = get_next_stage(state)
    if next_stage == "nanobanana":
        return "nanobanana_fan_out"
    elif next_stage == "strategy":
        return "strategy"
    else:
        return "failed"


def _route_after_aggregator(
    state: ProductState,
) -> Literal["image_gen", "listing_review", "failed"]:
    """Route after prompt aggregation.

    Listing was already generated in parallel during fan-out,
    so we skip to listing_review (or image_gen first if enabled).
    """
    if not state.get("nanobanana_success", False):
        return "failed"

    # Check if image generation is enabled
    if state.get("generate_images", False):
        return "image_gen"

    return "listing_review"


def _route_after_listing_review(
    state: ProductState,
) -> Literal["listing", "completed", "failed"]:
    """Route after listing_review."""
    next_stage = get_next_stage(state)
    if next_stage == "listing":
        return "listing"
    elif next_stage == "completed":
        return "completed"
    else:
        return "failed"


# ===== Workflow Graph Construction =====


def create_workflow() -> StateGraph:
    """Create the LangGraph workflow graph.

    V3 architecture with strategy stage and fan-out pattern:
    preprocess → preprocess_review → strategy → strategy_review
        → nanobanana_fan_out → [prompt_node (×10) + listing (×1)] parallel
        → prompt_aggregator → [image_gen] (optional)
        → listing_review → completed
    """
    # Create the state graph
    workflow = StateGraph(ProductState)

    # Add processing nodes
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("preprocess_review", preprocess_review_node)

    # Strategy nodes
    workflow.add_node("strategy", strategy_node)
    workflow.add_node("strategy_review", strategy_review_node)

    # Fan-out nodes for parallel prompt generation + listing
    workflow.add_node("nanobanana_fan_out", _nanobanana_pass_through)
    workflow.add_node("prompt_node", prompt_node)
    workflow.add_node("listing_fan_out", listing_fan_out_node)
    workflow.add_node("prompt_aggregator", prompt_aggregator_node)

    # Optional image generation
    workflow.add_node("image_gen", image_gen_node)

    # Listing nodes (listing for retry path, listing_review for validation)
    workflow.add_node("listing", listing_node)
    workflow.add_node("listing_review", listing_review_node)

    # Add terminal nodes
    workflow.add_node("completed", _completed_node)
    workflow.add_node("failed", _failed_node)

    # Set the entry point
    workflow.set_entry_point("preprocess")

    # ===== Edges =====

    # preprocess -> preprocess_review
    workflow.add_edge("preprocess", "preprocess_review")

    # preprocess_review -> strategy (instead of fan_out)
    workflow.add_conditional_edges(
        "preprocess_review",
        _route_after_preprocess_review,
        {
            "strategy": "strategy",
            "preprocess": "preprocess",
            "failed": "failed",
        },
    )

    # strategy -> strategy_review
    workflow.add_edge("strategy", "strategy_review")

    # strategy_review -> fan_out | retry strategy | failed
    workflow.add_conditional_edges(
        "strategy_review",
        _route_after_strategy_review,
        {
            "nanobanana_fan_out": "nanobanana_fan_out",
            "strategy": "strategy",
            "failed": "failed",
        },
    )

    # Fan-out: nanobanana_fan_out -> prompt_node (×10) + listing_fan_out (×1) in parallel
    workflow.add_conditional_edges(
        "nanobanana_fan_out", _fan_out_to_prompts, ["prompt_node", "listing_fan_out"]
    )

    # All fan-out branches converge at prompt_aggregator
    workflow.add_edge("prompt_node", "prompt_aggregator")
    workflow.add_edge("listing_fan_out", "prompt_aggregator")

    # After aggregator: image_gen (optional) or listing_review
    # (listing was already generated in parallel, skip to review)
    workflow.add_conditional_edges(
        "prompt_aggregator",
        _route_after_aggregator,
        {
            "image_gen": "image_gen",
            "listing_review": "listing_review",
            "failed": "failed",
        },
    )

    # image_gen -> listing_review (listing already generated, go straight to review)
    workflow.add_edge("image_gen", "listing_review")

    # listing -> listing_review (retry path only)
    workflow.add_edge("listing", "listing_review")

    # listing_review -> conditional routing
    workflow.add_conditional_edges(
        "listing_review",
        _route_after_listing_review,
        {
            "listing": "listing",
            "completed": "completed",
            "failed": "failed",
        },
    )

    # Terminal nodes -> END
    workflow.add_edge("completed", END)
    workflow.add_edge("failed", END)

    return workflow
