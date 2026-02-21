"""
Tools for the Review Queue agent — human-in-the-loop approval workflow.
"""

import logging
from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.review_queue_service import ReviewQueueService
from shared.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

_queue_service = ReviewQueueService()
_notification_service = NotificationService()


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class QueueForReviewInput(BaseModel):
    media_url: str = Field(..., description="URL or path to the generated media file.")
    caption: str = Field(..., description="The full Instagram caption text.")
    hashtags: str = Field(..., description="The hashtag string to accompany the post.")
    content_type: str = Field(
        default="image",
        description="Type of content: 'image', 'carousel', 'reel', 'story'.",
    )
    topic: str = Field(default="", description="The topic/theme of the post.")
    trend_source: str = Field(default="", description="Where the trend was discovered.")


class GetReviewStatusInput(BaseModel):
    item_id: str = Field(..., description="The ID of the review item to check.")


class GetApprovedItemsInput(BaseModel):
    pass  # No parameters needed


class GetPendingReviewsInput(BaseModel):
    pass  # No parameters needed


class NotifyReviewerInput(BaseModel):
    item_id: str = Field(..., description="The ID of the item to notify about.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def queue_for_review(
    media_url: str,
    caption: str,
    hashtags: str,
    content_type: str = "image",
    topic: str = "",
    trend_source: str = "",
) -> dict:
    """Add a complete post to the human review queue."""
    item = await _queue_service.queue_for_review(
        media_url=media_url,
        caption=caption,
        hashtags=hashtags,
        content_type=content_type,
        topic=topic,
        trend_source=trend_source,
    )
    return item


async def get_pending_reviews() -> list[dict]:
    """Get all items currently awaiting human review."""
    return await _queue_service.get_pending_reviews()


async def get_review_status(item_id: str) -> dict:
    """Check the review status of a specific item."""
    return await _queue_service.get_review_status(item_id)


async def get_approved_items() -> list[dict]:
    """Get all approved items that are ready to be published."""
    return await _queue_service.get_approved_items()


async def notify_reviewer(item_id: str) -> dict:
    """Send a notification to the human reviewer about a pending item."""
    item = await _queue_service.get_review_status(item_id)
    if "error" in item:
        return item
    await _notification_service.notify_new_review(item)
    return {"status": "notified", "item_id": item_id}


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_review_queue_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="queue_for_review",
            description=(
                "Add a complete Instagram post (media + caption + hashtags) to the "
                "human review queue. Returns the item ID and status."
            ),
            input_model=QueueForReviewInput,
            func=queue_for_review,
        ),
        FunctionTool(
            name="get_pending_reviews",
            description="List all items currently awaiting human review.",
            input_model=GetPendingReviewsInput,
            func=get_pending_reviews,
        ),
        FunctionTool(
            name="get_review_status",
            description="Check the review status of a specific item by its ID.",
            input_model=GetReviewStatusInput,
            func=get_review_status,
        ),
        FunctionTool(
            name="get_approved_items",
            description="Get all approved items that are ready to be published to Instagram.",
            input_model=GetApprovedItemsInput,
            func=get_approved_items,
        ),
        FunctionTool(
            name="notify_reviewer",
            description="Send a Slack/email notification to the human reviewer about a pending item.",
            input_model=NotifyReviewerInput,
            func=notify_reviewer,
        ),
    ]
