"""Credit service — tracks and enforces per-user image generation credits."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.user import User

logger = logging.getLogger(__name__)

# Credit costs per image based on (model, resolution)
CREDIT_COSTS: dict[tuple[str, str], int] = {
    ("gemini-3-pro-image-preview", "1k"): 7,
    ("gemini-3-pro-image-preview", "2k"): 10,
    ("gemini-3.1-flash-image-preview", "1k"): 7,
    ("gemini-3.1-flash-image-preview", "2k"): 10,
}


def calculate_job_cost(model: str, resolution: str, count: int) -> int:
    """Calculate total credits required for a job.

    Args:
        model: Gemini model name.
        resolution: Image resolution ("1k" or "2k").
        count: Number of images to generate.

    Returns:
        Total credit cost as an integer.
    """
    per_image = CREDIT_COSTS.get((model, resolution), 10)
    return per_image * count


def check_credits(
    user: "User",
    model: str,
    resolution: str,
    count: int,
    is_admin: bool,
) -> tuple[bool, int]:
    """Check if a user has enough credits for a job.

    Admin users are always allowed regardless of balance.

    Args:
        user: The User ORM object.
        model: Gemini model name.
        resolution: Image resolution ("1k" or "2k").
        count: Number of images requested.
        is_admin: Whether the user is an admin (bypasses balance check).

    Returns:
        Tuple of (allowed: bool, cost: int).
    """
    cost = calculate_job_cost(model, resolution, count)
    if is_admin:
        return True, cost
    return user.credit_balance >= cost, cost


def deduct_credits(db: "Session", user_id: int, amount: int) -> None:
    """Deduct credits from a user's balance and increment their usage counter.

    Balance is floored at 0 (never goes negative).

    Args:
        db: SQLAlchemy Session.
        user_id: The user's primary key.
        amount: Number of credits to deduct.
    """
    from app.models.user import User

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.credit_balance = max(0, user.credit_balance - amount)
        user.credits_used += amount
        db.commit()
        logger.info(
            "Deducted %d credits from user %d — balance=%d used=%d",
            amount, user_id, user.credit_balance, user.credits_used,
        )
