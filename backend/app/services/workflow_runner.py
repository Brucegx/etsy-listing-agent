"""Workflow runner service that bridges the FastAPI backend with the LangGraph engine.

Wraps the LangGraph workflow and provides SSE-compatible event streaming.
"""

from typing import Any, AsyncGenerator

from etsy_listing_agent.state import ProductState, create_initial_state
from etsy_listing_agent.workflow import create_workflow


class WorkflowRunner:
    """Runs the LangGraph workflow and yields SSE events."""

    def __init__(self) -> None:
        self._graph = create_workflow().compile()

    def build_state(
        self,
        product_id: str,
        product_path: str,
        category: str,
        excel_row: dict[str, Any],
        image_files: list[str],
        max_retries: int = 3,
        generate_images: bool = False,
    ) -> ProductState:
        """Build initial state for the workflow."""
        return create_initial_state(
            product_id=product_id,
            product_path=product_path,
            category=category,
            excel_row=excel_row,
            image_files=image_files,
            max_retries=max_retries,
            generate_images=generate_images,
        )

    async def run_with_events(
        self, state: ProductState, run_id: str | None = None
    ) -> AsyncGenerator[dict, None]:
        """Run workflow and yield progress events for SSE.

        Yields dicts with 'event' and 'data' keys suitable for SSE encoding.
        Events: start, progress, image_complete, image_done, complete, error.
        """
        yield {
            "event": "start",
            "data": {"product_id": state["product_id"], "status": "running"},
        }

        try:
            async for event in self._graph.astream(state, stream_mode="updates"):
                for node_name, update in event.items():
                    stage = update.get("stage", "")

                    # Emit strategy_complete when strategy node finishes
                    if node_name == "strategy" and update.get("image_strategy"):
                        yield {
                            "event": "strategy_complete",
                            "data": {
                                "strategy": update["image_strategy"],
                            },
                        }

                    # Emit image-specific events when image_gen node completes
                    image_result = update.get("image_gen_result")
                    if image_result and node_name == "image_gen" and run_id:
                        generated = image_result.get("generated", [])
                        failed = image_result.get("failed", [])
                        for img in generated:
                            # Extract subpath (generated_Xk/filename) from absolute path
                            parts = img["path"].replace("\\", "/").split("/")
                            # Find the "generated_*" directory in the path
                            gen_idx = next((i for i, p in enumerate(parts) if p.startswith("generated_")), -1)
                            subpath = "/".join(parts[gen_idx:]) if gen_idx >= 0 else parts[-1]
                            yield {
                                "event": "image_complete",
                                "data": {
                                    "direction": img["type"],
                                    "url": f"/api/images/{run_id}/{state['product_id']}/{subpath}",
                                    "index": img["index"],
                                },
                            }
                        yield {
                            "event": "image_done",
                            "data": {
                                "total": len(generated),
                                "failed": len(failed),
                            },
                        }

                    # Emit failure as an error event so the frontend shows it
                    if node_name == "failed":
                        error_msg = update.get("final_error", "Workflow failed")
                        yield {
                            "event": "error",
                            "data": {"message": error_msg},
                        }
                    else:
                        yield {
                            "event": "progress",
                            "data": {
                                "stage": stage or node_name,
                                "node": node_name,
                                "message": f"Completed: {node_name}",
                            },
                        }

            yield {
                "event": "complete",
                "data": {
                    "product_id": state["product_id"],
                    "status": "completed",
                    **({"run_id": run_id} if run_id else {}),
                },
            }

        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}
