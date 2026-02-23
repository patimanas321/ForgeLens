"""Internal tools owned by account agents (non-specialist).

These tools help account agents inspect published history and frequency
to avoid repeating content.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.media_metadata_service import get_content_by_id, query_content
from shared.services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)


class GetRecentPostHistoryInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    content_type: str = Field(
        default="",
        description="Optional type filter: post, reel, carousel, image, video",
    )


class GetContentFrequencyInput(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=200, ge=1, le=500)


class QueueForReviewInput(BaseModel):
    content_id: str = Field(..., description="Cosmos content ID for the generated media.")
    media_url: str = Field(..., description="URL or path to the generated media file.")
    caption: str = Field(default="", description="The full Instagram caption text.")
    hashtags: str = Field(default="", description="The hashtag string to accompany the post.")
    content_type: str = Field(
        default="image",
        description="Type of content: 'image', 'carousel', 'reel', 'story'.",
    )
    post_type: str = Field(
        default="post",
        description="Post type: 'post', 'reel', or 'carousel'.",
    )
    topic: str = Field(default="", description="The topic/theme of the post.")
    trend_source: str = Field(default="", description="Where the trend was discovered.")


class GetReviewStatusInput(BaseModel):
    item_id: str = Field(..., description="The ID of the review item to check.")


class GetPendingReviewsInput(BaseModel):
    pass


class GetApprovedItemsInput(BaseModel):
    pass


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def build_account_internal_tools(
    *,
    account_name: str,
    target_account_id: str,
    frequency_targets: dict[str, str],
) -> list[FunctionTool]:
    queue_service = ReviewQueueService(account_name=account_name)

    async def get_recent_post_history(limit: int = 20, content_type: str = "") -> dict:
        try:
            items = await query_content(
                publish_status="published",
                target_account_id=target_account_id or None,
                limit=max(limit * 3, 30),
            )
        except Exception as e:
            logger.warning("[account:%s] get_recent_post_history failed: %s", account_name, e)
            return {"account": account_name, "count": 0, "items": [], "note": "No publishing history yet or DB unavailable."}

        normalized_type = (content_type or "").strip().lower()
        if normalized_type:
            filtered = []
            for item in items:
                post_type = (item.get("post_type") or "").lower()
                media_type = (item.get("media_type") or "").lower()
                if normalized_type in {post_type, media_type}:
                    filtered.append(item)
            items = filtered

        items = items[:limit]
        return {
            "account": account_name,
            "target_account_id": target_account_id,
            "count": len(items),
            "items": items,
        }

    async def get_content_type_frequency(days: int = 30, limit: int = 200) -> dict:
        try:
            items = await query_content(
                publish_status="published",
                target_account_id=target_account_id or None,
                limit=limit,
            )
        except Exception as e:
            logger.warning("[account:%s] get_content_type_frequency failed: %s", account_name, e)
            return {
                "account": account_name,
                "window_days": days,
                "published_items_analyzed": 0,
                "counts_by_type": {"post": 0, "reel": 0, "carousel": 0, "other": 0},
                "frequency_targets": frequency_targets,
                "note": "No publishing history yet or DB unavailable.",
            }

        window_start = datetime.now(timezone.utc) - timedelta(days=days)
        counts = {"post": 0, "reel": 0, "carousel": 0, "other": 0}

        in_window = []
        for item in items:
            published_at = _parse_iso(item.get("published_at"))
            created_at = _parse_iso(item.get("created_at"))
            timestamp = published_at or created_at
            if not timestamp or timestamp < window_start:
                continue
            in_window.append(item)

            post_type = (item.get("post_type") or "").lower()
            if post_type in counts:
                counts[post_type] += 1
            else:
                counts["other"] += 1

        return {
            "account": account_name,
            "target_account_id": target_account_id,
            "window_days": days,
            "published_items_analyzed": len(in_window),
            "counts_by_type": counts,
            "frequency_targets": frequency_targets,
        }

    async def queue_for_review(
        content_id: str,
        media_url: str,
        caption: str = "",
        hashtags: str = "",
        content_type: str = "image",
        post_type: str = "post",
        topic: str = "",
        trend_source: str = "",
    ) -> dict:
        return await queue_service.queue_for_review(
            content_id=content_id,
            media_url=media_url,
            caption=caption,
            hashtags=hashtags,
            content_type=content_type,
            post_type=post_type,
            target_account_id=target_account_id,
            topic=topic,
            trend_source=trend_source,
        )

    async def get_pending_reviews() -> dict:
        items = await queue_service.get_pending_reviews()
        return {
            "account": account_name,
            "target_account_id": target_account_id,
            "count": len(items),
            "items": items,
        }

    async def get_review_status(item_id: str) -> dict:
        record = await get_content_by_id(item_id)
        if not record:
            return {"error": f"Item {item_id} not found"}
        if target_account_id and record.get("target_account_id") != target_account_id:
            return {"error": "Access denied for this account"}

        status = await queue_service.get_review_status(item_id)
        if "error" in status:
            return status
        if target_account_id and status.get("target_account_id") and status.get("target_account_id") != target_account_id:
            return {"error": "Access denied for this account"}
        return status

    async def get_approved_items() -> dict:
        items = await queue_service.get_approved_items()
        return {
            "account": account_name,
            "target_account_id": target_account_id,
            "count": len(items),
            "items": items,
        }

    return [
        FunctionTool(
            name="get_recent_post_history",
            description=(
                "Get recently published content for this account so you can avoid repeating themes, formats, and captions."
            ),
            input_model=GetRecentPostHistoryInput,
            func=get_recent_post_history,
        ),
        FunctionTool(
            name="get_content_type_frequency",
            description=(
                "Get content-type frequency summary (post/reel/carousel) for this account over a time window."
            ),
            input_model=GetContentFrequencyInput,
            func=get_content_type_frequency,
        ),
        FunctionTool(
            name="queue_for_review",
            description="Queue this account's content for approval. Access is restricted to this account.",
            input_model=QueueForReviewInput,
            func=queue_for_review,
        ),
        FunctionTool(
            name="get_pending_reviews",
            description="View pending review items for this account only.",
            input_model=GetPendingReviewsInput,
            func=get_pending_reviews,
        ),
        FunctionTool(
            name="get_review_status",
            description="View review status/details for one item in this account only.",
            input_model=GetReviewStatusInput,
            func=get_review_status,
        ),
        FunctionTool(
            name="get_approved_items",
            description="View approved items for this account only.",
            input_model=GetApprovedItemsInput,
            func=get_approved_items,
        ),
    ]
