"""
Unified tool set for an Instagram Account Agent.

All tools for a single account — web search, media generation, posting history,
review queue, and content frequency analysis — scoped to one Instagram account.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from agent_framework import FunctionTool
from pydantic import BaseModel, Field
from tavily import AsyncTavilyClient

from account_profile import AccountProfile
from config.settings import settings
from services.generation_queue_service import GenerationQueueService
from services.instagram_service import InstagramService
from services.media_metadata_service import get_content_by_id, query_content
from services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class WebSearchInput(BaseModel):
    query: str = Field(..., description="The search query.")
    max_results: int = Field(default=5, ge=1, le=20, description="Number of results.")


class PostingHistoryInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    content_type: str = Field(
        default="",
        description="Optional type filter: post, reel, carousel, image, video",
    )


class ContentFrequencyInput(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=200, ge=1, le=500)


class GenerateImageInput(BaseModel):
    prompt: str = Field(..., description="Detailed image prompt.")
    aspect_ratio: str = Field(default="4:5", description="Aspect ratio.")
    resolution: str = Field(default="1K", description="'1K', '2K', or '4K'.")
    output_format: str = Field(default="png", description="'png', 'jpeg', or 'webp'.")
    caption: str = Field(..., description="The full Instagram caption text for this post.")
    hashtags: list[str] = Field(..., description="List of hashtags (without #) e.g. ['goldenretriever', 'coffeedate'].")
    topic: str = Field(..., description="Brief topic/theme of the post, e.g. 'celebrity coffee date'.")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., description="Detailed video prompt.")
    duration: int = Field(default=5, ge=3, le=15, description="Duration in seconds.")
    aspect_ratio: str = Field(default="9:16", description="Aspect ratio.")
    video_model: str = Field(default="", description="'kling' or 'sora'. Empty for default.")
    caption: str = Field(..., description="The full Instagram caption text for this reel.")
    hashtags: list[str] = Field(..., description="List of hashtags (without #) e.g. ['goldenretriever', 'reels'].")
    topic: str = Field(..., description="Brief topic/theme of the reel, e.g. 'morning walk montage'.")


class QueueForReviewInput(BaseModel):
    content_id: str = Field(..., description="Cosmos content ID for the generated media.")
    media_url: str = Field(..., description="URL or path to the generated media file.")
    caption: str = Field(default="", description="The full Instagram caption text.")
    hashtags: str = Field(default="", description="The hashtag string to accompany the post.")
    content_type: str = Field(default="image", description="'image', 'carousel', 'reel', 'story'.")
    post_type: str = Field(default="post", description="'post', 'reel', or 'carousel'.")
    topic: str = Field(default="", description="The topic/theme of the post.")
    trend_source: str = Field(default="", description="Where the trend was discovered.")


class GetPendingReviewsInput(BaseModel):
    pass


class GetApprovedItemsInput(BaseModel):
    pass


class GetReviewStatusInput(BaseModel):
    item_id: str = Field(..., description="The ID of the review item to check.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool builder — returns all tools bound to a specific account
# ---------------------------------------------------------------------------

def build_account_tools(
    profile: AccountProfile,
    *,
    target_account_id: str = "",
    frequency_targets: dict[str, str] | None = None,
) -> list[FunctionTool]:
    """Build every tool for a single account agent, scoped to its IG account."""

    account_name = profile.account_name
    freq_targets = frequency_targets or {}

    # Resolve the Instagram account ID from KV if not passed
    if not target_account_id:
        accounts = settings.INSTAGRAM_ACCOUNTS
        target_account_id = accounts.get(profile.instagram_account_key, "")

    # Services scoped to this account
    ig_service = InstagramService(account_id=target_account_id) if target_account_id else None
    queue_service = ReviewQueueService(account_name=account_name)
    generation_queue = GenerationQueueService(account_name=account_name)

    # Tavily client
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(settings.TAVILY_MCP_URL)
        api_key = parse_qs(parsed.query).get("tavilyApiKey", [""])[0]
    tavily_client = AsyncTavilyClient(api_key=api_key) if api_key else None

    # ------------------------------------------------------------------
    # Web search
    # ------------------------------------------------------------------

    async def web_search(query: str, max_results: int = 5) -> str:
        if not tavily_client:
            return json.dumps({"error": "Tavily API key not configured"})
        try:
            result = await tavily_client.search(query=query, max_results=max_results, include_images=True)
            output = {
                "query": result.get("query", query),
                "results": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")[:500]}
                    for r in result.get("results", [])
                ],
                "images": result.get("images", [])[:5],
            }
            return json.dumps(output)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------
    # Posting history & frequency
    # ------------------------------------------------------------------

    async def get_posting_history(limit: int = 20, content_type: str = "") -> dict:
        # Try Instagram API first
        if ig_service and not content_type:
            try:
                media = await ig_service.get_recent_media(limit=limit)
                if media:
                    return {"account": account_name, "source": "instagram_api", "count": len(media), "items": media}
            except Exception as e:
                logger.warning(f"Could not fetch IG history: {e}")

        # Fall back to Cosmos DB
        try:
            items = await query_content(
                publish_status="published",
                target_account_id=target_account_id or None,
                limit=max(limit * 3, 30),
            )
        except Exception as e:
            logger.warning("[account:%s] get_posting_history failed: %s", account_name, e)
            return {"account": account_name, "count": 0, "items": [], "note": "No history available."}

        normalized_type = (content_type or "").strip().lower()
        if normalized_type:
            items = [
                item for item in items
                if normalized_type in {(item.get("post_type") or "").lower(), (item.get("media_type") or "").lower()}
            ]

        items = items[:limit]
        return {"account": account_name, "count": len(items), "items": items}

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
                "frequency_targets": freq_targets,
                "note": "No history available.",
            }

        window_start = datetime.now(timezone.utc) - timedelta(days=days)
        counts: dict[str, int] = {"post": 0, "reel": 0, "carousel": 0, "other": 0}
        in_window = []

        for item in items:
            timestamp = _parse_iso(item.get("published_at")) or _parse_iso(item.get("created_at"))
            if not timestamp or timestamp < window_start:
                continue
            in_window.append(item)
            post_type = (item.get("post_type") or "").lower()
            counts[post_type] = counts.get(post_type, 0) + 1

        return {
            "account": account_name,
            "window_days": days,
            "published_items_analyzed": len(in_window),
            "counts_by_type": counts,
            "frequency_targets": freq_targets,
        }

    # ------------------------------------------------------------------
    # Media generation (queue-based)
    # ------------------------------------------------------------------

    # fal.ai prompt length limits (undocumented, derived from testing)
    MAX_IMAGE_PROMPT_CHARS = 2000   # Nano Banana Pro (Gemini-based)
    MAX_VIDEO_PROMPT_CHARS = 2500   # Kling O3

    def _truncate_prompt(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        # Cut at last sentence boundary within limit, fall back to hard cut
        truncated = text[:limit]
        last_period = truncated.rfind(". ")
        if last_period > limit // 2:
            truncated = truncated[: last_period + 1]
        logger.warning(
            "[prompt] Truncated from %d to %d chars (limit %d)",
            len(text), len(truncated), limit,
        )
        return truncated

    async def generate_image(
        prompt: str, aspect_ratio: str = "4:5", resolution: str = "1K", output_format: str = "png",
        caption: str = "", hashtags: list[str] | None = None, topic: str = "",
    ) -> dict:
        try:
            doc = await generation_queue.submit_generation(
                media_type="image",
                prompt=_truncate_prompt(prompt, MAX_IMAGE_PROMPT_CHARS),
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_format=output_format,
                post_type="post",
                target_account_id=target_account_id,
                target_account_name=profile.display_name,
                topic=topic,
                caption=caption,
                hashtags=hashtags,
            )
            return {
                "status": "queued",
                "content_id": doc["id"],
                "message": "Image generation submitted to background worker.",
            }
        except Exception as e:
            logger.error(f"Image generation queue failed: {e}")
            return {"status": "error", "error": str(e)}

    async def generate_video(
        prompt: str, duration: int = 5, aspect_ratio: str = "9:16", video_model: str = "",
        caption: str = "", hashtags: list[str] | None = None, topic: str = "",
    ) -> dict:
        try:
            doc = await generation_queue.submit_generation(
                media_type="video",
                prompt=_truncate_prompt(prompt, MAX_VIDEO_PROMPT_CHARS),
                aspect_ratio=aspect_ratio,
                duration=duration,
                video_model=video_model,
                post_type="reel",
                target_account_id=target_account_id,
                target_account_name=profile.display_name,
                topic=topic,
                caption=caption,
                hashtags=hashtags,
            )
            return {
                "status": "queued",
                "content_id": doc["id"],
                "message": "Video generation submitted to background worker.",
            }
        except Exception as e:
            logger.error(f"Video generation queue failed: {e}")
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Review queue
    # ------------------------------------------------------------------

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
        return {"account": account_name, "count": len(items), "items": items}

    async def get_approved_items() -> dict:
        items = await queue_service.get_approved_items()
        return {"account": account_name, "count": len(items), "items": items}

    async def get_review_status(item_id: str) -> dict:
        record = await get_content_by_id(item_id)
        if not record:
            return {"error": f"Item {item_id} not found"}
        if target_account_id and record.get("target_account_id") != target_account_id:
            return {"error": "Access denied for this account"}

        status = await queue_service.get_review_status(item_id)
        if "error" in status:
            return status
        if target_account_id and status.get("target_account_id") and status["target_account_id"] != target_account_id:
            return {"error": "Access denied for this account"}
        return status

    # ------------------------------------------------------------------
    # Assemble
    # ------------------------------------------------------------------

    return [
        FunctionTool(
            name="web_search",
            description="Search the web for inspiration, trends, or references.",
            input_model=WebSearchInput,
            func=web_search,
        ),
        FunctionTool(
            name="get_posting_history",
            description="Get recently published content for this account to avoid repeating themes, formats, and captions.",
            input_model=PostingHistoryInput,
            func=get_posting_history,
        ),
        FunctionTool(
            name="get_content_type_frequency",
            description="Get content-type frequency (post/reel/carousel) over a time window vs configured targets.",
            input_model=ContentFrequencyInput,
            func=get_content_type_frequency,
        ),
        FunctionTool(
            name="generate_image",
            description="Submit an image generation request. Returns content_id immediately — generation happens in background.",
            input_model=GenerateImageInput,
            func=generate_image,
        ),
        FunctionTool(
            name="generate_video",
            description="Submit a video generation request. Returns content_id immediately — generation happens in background.",
            input_model=GenerateVideoInput,
            func=generate_video,
        ),
        FunctionTool(
            name="queue_for_review",
            description="Queue generated content for human approval. Requires the content_id from generate_image/generate_video.",
            input_model=QueueForReviewInput,
            func=queue_for_review,
        ),
        FunctionTool(
            name="get_pending_reviews",
            description="List items awaiting human review for this account.",
            input_model=GetPendingReviewsInput,
            func=get_pending_reviews,
        ),
        FunctionTool(
            name="get_approved_items",
            description="Get approved items ready to publish for this account.",
            input_model=GetApprovedItemsInput,
            func=get_approved_items,
        ),
        FunctionTool(
            name="get_review_status",
            description="View review status/details for one item by its ID.",
            input_model=GetReviewStatusInput,
            func=get_review_status,
        ),
    ]
