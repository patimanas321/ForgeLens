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
from services.azure_bus_service import send_message_to_media_generation_queue
from services.cosmos_db_service import delete_media_metadata, save_media_metadata
from services.instagram_service import InstagramService
from services.cosmos_db_service import get_content_by_id, query_content

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
    caption: str = Field(..., description="The full Instagram caption text for this reel.")
    hashtags: list[str] = Field(..., description="List of hashtags (without #) e.g. ['goldenretriever', 'reels'].")
    topic: str = Field(..., description="Brief topic/theme of the reel, e.g. 'morning walk montage'.")


class GetReviewStatusInput(BaseModel):
    item_id: str = Field(..., description="The content ID to check status for.")


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

    async def _create_content_record(
        *,
        media_type: str,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        output_format: str = "png",
        duration: int = 5,
        post_type: str = "post",
        topic: str = "",
        caption: str = "",
        hashtags: list[str] | None = None,
    ) -> dict:
        if media_type == "video":
            model = settings.VIDEO_GENERATION_MODEL
        else:
            model = settings.IMAGE_GENERATION_MODEL
        doc = await save_media_metadata(
            media_type=media_type,
            blob_url="",
            blob_name="",
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution="" if media_type == "video" else resolution,
            duration_seconds=duration if media_type == "video" else None,
            source_media_url="",
            post_type=post_type,
            target_account_id=target_account_id,
            target_account_name=profile.display_name,
            description=topic,
            caption=caption,
            hashtags=hashtags,
            publish_status="pending",
            extra={
                "generation_status": "queued",
                "generation_requested_at": datetime.now(timezone.utc).isoformat(),
                "media_review_status": "pending",
                "approval_status": "pending",
                "output_format": output_format,
                "account": account_name,
                "source": "account_agent",
            },
        )
        logger.info(
            "[account:%s] Saved reviewed content plan %s (type=%s) — queued",
            account_name,
            doc["id"],
            media_type,
        )
        return doc

    async def generate_image(
        prompt: str, aspect_ratio: str = "4:5", resolution: str = "1K", output_format: str = "png",
        caption: str = "", hashtags: list[str] | None = None, topic: str = "",
    ) -> dict:
        try:
            doc = await _create_content_record(
                media_type="image",
                prompt=_truncate_prompt(prompt, MAX_IMAGE_PROMPT_CHARS),
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_format=output_format,
                post_type="post",
                topic=topic,
                caption=caption,
                hashtags=hashtags,
            )
            try:
                await send_message_to_media_generation_queue(
                    content_id=doc["id"],
                    media_type="image",
                    account=account_name,
                    subject="Media Generation",
                    message_id=doc["id"],
                )
            except Exception as queue_error:
                await delete_media_metadata(doc["id"], "image")
                logger.error("Image generation queue failed; rolled back DB record: %s", queue_error)
                return {"status": "error", "error": str(queue_error)}
            return {
                "status": "queued",
                "content_id": doc["id"],
                "message": (
                    "Content saved and queued for generation. "
                    "Use get_review_status(content_id) to track progress."
                ),
            }
        except Exception as e:
            logger.error(f"Image generation queue failed: {e}")
            return {"status": "error", "error": str(e)}

    async def generate_video(
        prompt: str, duration: int = 5, aspect_ratio: str = "9:16",
        caption: str = "", hashtags: list[str] | None = None, topic: str = "",
    ) -> dict:
        try:
            doc = await _create_content_record(
                media_type="video",
                prompt=_truncate_prompt(prompt, MAX_VIDEO_PROMPT_CHARS),
                aspect_ratio=aspect_ratio,
                duration=duration,
                post_type="reel",
                topic=topic,
                caption=caption,
                hashtags=hashtags,
            )
            try:
                await send_message_to_media_generation_queue(
                    content_id=doc["id"],
                    media_type="video",
                    account=account_name,
                    subject="Media Generation",
                    message_id=doc["id"],
                )
            except Exception as queue_error:
                await delete_media_metadata(doc["id"], "video")
                logger.error("Video generation queue failed; rolled back DB record: %s", queue_error)
                return {"status": "error", "error": str(queue_error)}
            return {
                "status": "queued",
                "content_id": doc["id"],
                "message": (
                    "Content saved and queued for generation. "
                    "Use get_review_status(content_id) to track progress."
                ),
            }
        except Exception as e:
            logger.error(f"Video generation queue failed: {e}")
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Review status (read-only, from DB)
    # ------------------------------------------------------------------

    async def get_review_status(item_id: str) -> dict:
        record = await get_content_by_id(item_id)
        if not record:
            return {"error": f"Item {item_id} not found"}
        if target_account_id and record.get("target_account_id") != target_account_id:
            return {"error": "Access denied for this account"}
        return {
            "id": record["id"],
            "media_review_status": record.get("media_review_status", "unknown"),
            "approval_status": record.get("approval_status", "unknown"),
            "generation_status": record.get("generation_status", "unknown"),
            "publish_status": record.get("publish_status", "pending"),
            "blob_url": record.get("blob_url", ""),
            "created_at": record.get("created_at"),
            "media_reviewed_at": record.get("media_reviewed_at"),
            "media_review_score": record.get("media_review_score"),
            "media_reviewer_notes": record.get("media_reviewer_notes", ""),
            "human_reviewed_at": record.get("human_reviewed_at"),
            "human_reviewer_notes": record.get("human_reviewer_notes", ""),
        }

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
            description="Create DB entry and queue image generation. Call Content Reviewer agent first before using this tool.",
            input_model=GenerateImageInput,
            func=generate_image,
        ),
        FunctionTool(
            name="generate_video",
            description="Create DB entry and queue video generation. Call Content Reviewer agent first before using this tool.",
            input_model=GenerateVideoInput,
            func=generate_video,
        ),
        FunctionTool(
            name="get_review_status",
            description="Check the current generation/approval/publish status of a content item by its ID.",
            input_model=GetReviewStatusInput,
            func=get_review_status,
        ),
    ]
