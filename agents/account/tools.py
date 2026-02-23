"""
Unified tool set for an Instagram Account Agent.

Combines tools from all former specialist agents into a single set,
scoped to a specific account. Each account agent gets its own tool
instances bound to its Instagram account.
"""

import asyncio
import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fal_client
import httpx
from agent_framework import FunctionTool
from pydantic import BaseModel, Field
from tavily import AsyncTavilyClient

from shared.account_profile import AccountProfile
from shared.config.settings import settings
from shared.services.blob_storage_service import upload_blob
from shared.services.instagram_service import InstagramService
from shared.services.media_metadata_service import save_media_metadata
from shared.services.review_queue_service import ReviewQueueService
from shared.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

# -- Web search --
class WebSearchInput(BaseModel):
    query: str = Field(..., description="The search query.")
    max_results: int = Field(default=5, ge=1, le=20, description="Number of results.")


# -- Content strategy --
class PostingHistoryInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=50, description="Number of recent posts to fetch.")


# -- Media generation --
class GenerateImageInput(BaseModel):
    prompt: str = Field(..., description="Detailed image prompt.")
    aspect_ratio: str = Field(default="4:5", description="Aspect ratio.")
    resolution: str = Field(default="1K", description="'1K', '2K', or '4K'.")
    output_format: str = Field(default="png", description="'png', 'jpeg', or 'webp'.")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., description="Detailed video prompt.")
    duration: int = Field(default=5, ge=3, le=15, description="Duration in seconds.")
    aspect_ratio: str = Field(default="9:16", description="Aspect ratio.")
    video_model: str = Field(default="", description="'kling' or 'sora'. Empty for default.")


class UploadMediaInput(BaseModel):
    local_file_path: str = Field(..., description="Path to local media file.")


# -- Copywriting --
class WriteCaptionInput(BaseModel):
    topic: str = Field(..., description="Post topic.")
    tone: str = Field(default="engaging", description="Desired tone.")
    content_format: str = Field(default="image", description="'image', 'carousel', 'reel'.")
    visual_description: str = Field(default="", description="Media description.")


class SuggestHashtagsInput(BaseModel):
    topic: str = Field(..., description="Topic for hashtags.")
    caption: str = Field(default="", description="Caption for context.")
    count: int = Field(default=20, ge=5, le=30, description="Number of hashtags.")


# -- Review queue --
class QueueForReviewInput(BaseModel):
    media_url: str = Field(..., description="URL of the media.")
    caption: str = Field(..., description="Full caption text.")
    hashtags: str = Field(..., description="Hashtag string.")
    content_type: str = Field(default="image", description="'image', 'carousel', 'reel'.")
    topic: str = Field(default="", description="Post topic.")


class GetPendingReviewsInput(BaseModel):
    pass


class GetApprovedItemsInput(BaseModel):
    pass


# -- Publishing --
class PublishImagePostInput(BaseModel):
    image_url: str = Field(..., description="Public image URL.")
    caption: str = Field(..., description="Full caption with hashtags.")


class PublishReelInput(BaseModel):
    video_url: str = Field(..., description="Public video URL.")
    caption: str = Field(..., description="Full caption with hashtags.")


class PublishCarouselInput(BaseModel):
    image_urls: list[str] = Field(..., description="List of public image URLs (2-10).")
    caption: str = Field(..., description="Full caption with hashtags.")


class CheckPublishStatusInput(BaseModel):
    container_id: str = Field(..., description="Media container ID to check.")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _download_to_local(url: str, extension: str) -> Path:
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{extension}"
    file_path = Path(tempfile.gettempdir()) / file_name
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        file_path.write_bytes(resp.content)
    return file_path


def _resolve_video_model(model_hint: str) -> str:
    if not model_hint:
        return settings.FAL_VIDEO_MODEL
    hint = model_hint.strip().lower()
    if hint == "sora":
        return settings.FAL_VIDEO_MODEL_ALT
    if hint.startswith("fal-ai/"):
        return hint
    return settings.FAL_VIDEO_MODEL


def _mock_id(prefix: str = "ig") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Tool builder — returns tools bound to a specific account
# ---------------------------------------------------------------------------

def build_account_tools(profile: AccountProfile) -> list[FunctionTool]:
    """Build all tools for a single account agent, scoped to its IG account."""

    # Resolve the Instagram account ID from KV
    accounts = settings.INSTAGRAM_ACCOUNTS
    ig_account_id = accounts.get(profile.instagram_account_key, "")

    # Services scoped to this account
    ig_service = InstagramService(account_id=ig_account_id) if ig_account_id else None
    queue_service = ReviewQueueService(account_name=profile.account_name)
    notification_service = NotificationService()

    # Dry-run when no token
    dry_run = not settings.INSTAGRAM_ACCESS_TOKEN

    # Tavily client
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(settings.TAVILY_MCP_URL)
        api_key = parse_qs(parsed.query).get("tavilyApiKey", [""])[0]
    tavily_client = AsyncTavilyClient(api_key=api_key) if api_key else None

    # ------------------------------------------------------------------
    # Tool functions (closures over account-scoped services)
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

    async def get_posting_history(limit: int = 20) -> list[dict]:
        if ig_service:
            try:
                return await ig_service.get_recent_media(limit=limit)
            except Exception as e:
                logger.warning(f"Could not fetch IG history: {e}")
        return []

    async def generate_image(
        prompt: str, aspect_ratio: str = "4:5", resolution: str = "1K", output_format: str = "png",
    ) -> dict:
        try:
            model_id = settings.FAL_IMAGE_MODEL
            result = await fal_client.subscribe_async(model_id, arguments={
                "prompt": prompt, "num_images": 1, "aspect_ratio": aspect_ratio,
                "output_format": output_format, "resolution": resolution, "safety_tolerance": "4",
            })
            image_data = result["images"][0]
            file_path = await _download_to_local(image_data["url"], output_format)
            blob_info = await upload_blob(file_path)
            doc = await save_media_metadata(
                media_type="image", blob_url=blob_info["blob_url"], blob_name=blob_info["blob_name"],
                prompt=prompt, model=model_id, aspect_ratio=aspect_ratio, resolution=resolution,
                width=image_data.get("width"), height=image_data.get("height"),
                file_size_bytes=blob_info["file_size_bytes"], fal_url=image_data["url"],
                extra={"account": profile.account_name},
            )
            return {
                "status": "success", "blob_url": blob_info["blob_url"], "cosmos_id": doc["id"],
                "local_file_path": str(file_path), "aspect_ratio": aspect_ratio,
                "width": image_data.get("width"), "height": image_data.get("height"),
            }
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"status": "error", "error": str(e)}

    async def generate_video(
        prompt: str, duration: int = 5, aspect_ratio: str = "9:16", video_model: str = "",
    ) -> dict:
        model_id = _resolve_video_model(video_model)
        try:
            is_sora = "sora" in model_id
            is_kling = "kling" in model_id
            if is_sora:
                sora_dur = min([d for d in [4, 8, 12] if d >= duration], default=12)
                arguments = {"prompt": prompt, "duration": str(sora_dur),
                             "aspect_ratio": aspect_ratio if aspect_ratio in ("9:16", "16:9") else "9:16",
                             "resolution": "720p", "delete_video": False}
            elif is_kling:
                arguments = {"prompt": prompt, "duration": str(max(3, min(duration, 15))),
                             "aspect_ratio": aspect_ratio if aspect_ratio in ("9:16", "16:9", "1:1") else "9:16",
                             "negative_prompt": "blur, distort, and low quality", "generate_audio": True}
            else:
                arguments = {"prompt": prompt, "duration": str(duration), "aspect_ratio": aspect_ratio}

            result = await fal_client.subscribe_async(model_id, arguments=arguments)
            video_url = result["video"]["url"]
            file_path = await _download_to_local(video_url, "mp4")
            blob_info = await upload_blob(file_path)
            doc = await save_media_metadata(
                media_type="video", blob_url=blob_info["blob_url"], blob_name=blob_info["blob_name"],
                prompt=prompt, model=model_id, aspect_ratio=aspect_ratio, duration_seconds=duration,
                file_size_bytes=blob_info["file_size_bytes"], fal_url=video_url,
                extra={"account": profile.account_name},
            )
            return {
                "status": "success", "blob_url": blob_info["blob_url"], "cosmos_id": doc["id"],
                "local_file_path": str(file_path), "model": model_id,
                "duration_seconds": duration, "aspect_ratio": aspect_ratio,
            }
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return {"status": "error", "error": str(e), "model": model_id}

    async def upload_media(local_file_path: str) -> dict:
        path = Path(local_file_path)
        if not path.exists():
            return {"status": "error", "error": f"File not found: {local_file_path}"}
        try:
            blob_info = await upload_blob(path)
            return {"status": "success", "public_url": blob_info["blob_url"],
                    "blob_name": blob_info["blob_name"], "file_size_bytes": blob_info["file_size_bytes"]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def write_caption(
        topic: str, tone: str = "engaging", content_format: str = "image", visual_description: str = "",
    ) -> dict:
        length_guide = {"image": "medium (100-200 words)", "carousel": "long (150-300 words)",
                        "reel": "short (30-80 words)"}
        return {
            "status": "ready",
            "brief": {
                "topic": topic, "tone": tone, "format": content_format,
                "visual_description": visual_description,
                "recommended_length": length_guide.get(content_format, "medium"),
                "persona_voice": profile.persona.voice,
                "caption_style": profile.content_rules.caption_style,
                "instructions": (
                    f"Write the caption now AS {profile.display_name}. Stay in character. "
                    "Start with a strong hook. Use line breaks. End with a CTA. "
                    "Do NOT include hashtags in the caption."
                ),
            },
        }

    async def suggest_hashtags(topic: str, caption: str = "", count: int = 20) -> dict:
        return {
            "status": "ready",
            "brief": {
                "topic": topic, "caption_context": caption[:200] if caption else "",
                "target_count": count,
                "distribution": {
                    "broad (1M+)": f"{count // 4}", "medium (100K-1M)": f"{count // 2}",
                    "niche (<100K)": f"{count - count // 4 - count // 2}",
                },
                "instructions": "Generate hashtags now. Mix sizes. All lowercase.",
            },
        }

    async def queue_for_review(
        media_url: str, caption: str, hashtags: str,
        content_type: str = "image", topic: str = "",
    ) -> dict:
        return await queue_service.queue_for_review(
            media_url=media_url, caption=caption, hashtags=hashtags,
            content_type=content_type, topic=topic, trend_source=profile.account_name,
        )

    async def get_pending_reviews() -> list[dict]:
        return await queue_service.get_pending_reviews()

    async def get_approved_items() -> list[dict]:
        return await queue_service.get_approved_items()

    async def publish_image_post(image_url: str, caption: str) -> dict:
        if dry_run:
            return {"status": "published (dry-run)", "media_id": _mock_id("media"),
                    "type": "image", "dry_run": True, "caption_preview": caption[:100]}
        try:
            container_id = await ig_service.create_image_container(image_url, caption)
            media_id = await ig_service.publish_container(container_id)
            return {"status": "published", "media_id": media_id, "type": "image",
                    "account": profile.account_name}
        except Exception as e:
            return {"status": "error", "error": str(e), "type": "image"}

    async def publish_reel(video_url: str, caption: str) -> dict:
        if dry_run:
            return {"status": "published (dry-run)", "media_id": _mock_id("media"),
                    "type": "reel", "dry_run": True, "caption_preview": caption[:100]}
        try:
            container_id = await ig_service.create_video_container(video_url, caption)
            for attempt in range(10):
                await asyncio.sleep(30)
                status = await ig_service.check_container_status(container_id)
                if status.get("status_code") == "FINISHED":
                    media_id = await ig_service.publish_container(container_id)
                    return {"status": "published", "media_id": media_id, "type": "reel",
                            "account": profile.account_name}
                if status.get("status_code") == "ERROR":
                    return {"status": "error", "error": f"Processing failed: {status}", "type": "reel"}
            return {"status": "error", "error": "Timed out after 5 min", "type": "reel"}
        except Exception as e:
            return {"status": "error", "error": str(e), "type": "reel"}

    async def publish_carousel(image_urls: list[str], caption: str) -> dict:
        if dry_run:
            return {"status": "published (dry-run)", "media_id": _mock_id("media"),
                    "children_count": len(image_urls), "type": "carousel", "dry_run": True}
        try:
            children_ids = []
            for url in image_urls:
                child_id = await ig_service.create_image_container(url, "")
                children_ids.append(child_id)
            container_id = await ig_service.create_carousel_container(children_ids, caption)
            media_id = await ig_service.publish_container(container_id)
            return {"status": "published", "media_id": media_id, "type": "carousel",
                    "account": profile.account_name}
        except Exception as e:
            return {"status": "error", "error": str(e), "type": "carousel"}

    async def check_publish_status(container_id: str) -> dict:
        if dry_run:
            return {"id": container_id, "status_code": "FINISHED", "dry_run": True}
        try:
            svc = InstagramService()
            return await svc.check_container_status(container_id)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Assemble all tools
    # ------------------------------------------------------------------
    tools = [
        FunctionTool(name="web_search", description="Search the web for inspiration, trends, or references.",
                     input_model=WebSearchInput, func=web_search),
        FunctionTool(name="get_posting_history", description="Fetch recent Instagram posts to avoid repetition.",
                     input_model=PostingHistoryInput, func=get_posting_history),
        FunctionTool(name="generate_image", description="Generate an image via AI. Auto-uploads to storage.",
                     input_model=GenerateImageInput, func=generate_image),
        FunctionTool(name="generate_video", description="Generate a video via AI. Auto-uploads to storage.",
                     input_model=GenerateVideoInput, func=generate_video),
        FunctionTool(name="upload_media", description="Upload a local file to get a public URL.",
                     input_model=UploadMediaInput, func=upload_media),
        FunctionTool(name="write_caption", description="Prepare a caption brief, then write the caption in character.",
                     input_model=WriteCaptionInput, func=write_caption),
        FunctionTool(name="suggest_hashtags", description="Get guidance for generating relevant hashtags.",
                     input_model=SuggestHashtagsInput, func=suggest_hashtags),
        FunctionTool(name="queue_for_review", description="Submit a complete post for human approval.",
                     input_model=QueueForReviewInput, func=queue_for_review),
        FunctionTool(name="get_pending_reviews", description="List items awaiting human review.",
                     input_model=GetPendingReviewsInput, func=get_pending_reviews),
        FunctionTool(name="get_approved_items", description="Get approved items ready to publish.",
                     input_model=GetApprovedItemsInput, func=get_approved_items),
        FunctionTool(name="publish_image_post", description="Publish an approved image post to Instagram.",
                     input_model=PublishImagePostInput, func=publish_image_post),
        FunctionTool(name="publish_reel", description="Publish an approved reel to Instagram.",
                     input_model=PublishReelInput, func=publish_reel),
        FunctionTool(name="publish_carousel", description="Publish an approved carousel to Instagram.",
                     input_model=PublishCarouselInput, func=publish_carousel),
        FunctionTool(name="check_publish_status", description="Check if a video container has finished processing.",
                     input_model=CheckPublishStatusInput, func=check_publish_status),
    ]
    return tools
