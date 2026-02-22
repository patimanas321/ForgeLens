"""
Tools for the Publisher agent — posting content to Instagram via Graph API.

Dry-run mode: when INSTAGRAM_ACCESS_TOKEN is empty, tools simulate the Instagram API
and return mock responses so the full pipeline can be tested end-to-end.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.config.settings import settings
from shared.services.instagram_service import InstagramService
from shared.services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)

_queue_service = ReviewQueueService()

# Dry-run mode when Instagram credentials are missing
DRY_RUN = not settings.INSTAGRAM_ACCESS_TOKEN
if DRY_RUN:
    logger.warning("[DRY-RUN] Instagram tokens not configured — Publisher runs in simulation mode")


def _get_ig_service(account_name: str = "") -> InstagramService:
    """Get an InstagramService for a specific account, or the default."""
    if account_name:
        accounts = settings.INSTAGRAM_ACCOUNTS
        account_id = accounts.get(account_name)
        if not account_id:
            raise ValueError(f"Unknown account '{account_name}'. Available: {list(accounts.keys())}")
        return InstagramService(account_id=account_id)
    return InstagramService()


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class ListInstagramAccountsInput(BaseModel):
    pass  # No input needed


class PublishImagePostInput(BaseModel):
    image_url: str = Field(..., description="Publicly accessible URL of the image to post.")
    caption: str = Field(..., description="Full caption text including hashtags.")
    account_name: str = Field(default="", description="Target IG account name (e.g. 'oreo'). Leave empty for default.")


class PublishReelInput(BaseModel):
    video_url: str = Field(..., description="Publicly accessible URL of the video.")
    caption: str = Field(..., description="Full caption text including hashtags.")
    account_name: str = Field(default="", description="Target IG account name. Leave empty for default.")


class PublishCarouselInput(BaseModel):
    image_urls: list[str] = Field(..., description="List of publicly accessible image URLs (2-10 images).")
    caption: str = Field(..., description="Full caption text including hashtags.")
    account_name: str = Field(default="", description="Target IG account name. Leave empty for default.")


class CheckPublishStatusInput(BaseModel):
    container_id: str = Field(..., description="The media container ID to check.")


class GetApprovedItemsInput(BaseModel):
    pass  # No input needed


class MarkAsPublishedInput(BaseModel):
    item_id: str = Field(..., description="Review queue item ID.")
    media_id: str = Field(..., description="Instagram media ID after successful publish.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

def _mock_id(prefix: str = "ig") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def list_instagram_accounts() -> dict:
    """List all configured Instagram accounts available for publishing."""
    accounts = settings.INSTAGRAM_ACCOUNTS
    return {
        "accounts": [
            {"name": name, "account_id": aid}
            for name, aid in accounts.items()
        ],
        "default": next(iter(accounts), "") if accounts else "",
        "count": len(accounts),
    }


async def get_approved_items() -> dict:
    """Fetch all approved items from the review queue that are ready to publish."""
    items = await _queue_service.get_approved_items()
    return {
        "count": len(items),
        "items": items,
    }


async def publish_image_post(image_url: str, caption: str, account_name: str = "") -> dict:
    """Publish a single image post to Instagram (two-step: create container → publish)."""
    if DRY_RUN:
        mock_container = _mock_id("container")
        mock_media = _mock_id("media")
        logger.info(f"[DRY-RUN] Simulated image publish: {mock_media}")
        return {
            "status": "published (dry-run)",
            "media_id": mock_media,
            "container_id": mock_container,
            "type": "image",
            "dry_run": True,
            "image_url": image_url,
            "caption_preview": caption[:100],
        }
    try:
        svc = _get_ig_service(account_name)
        container_id = await svc.create_image_container(image_url, caption)
        media_id = await svc.publish_container(container_id)
        return {
            "status": "published",
            "media_id": media_id,
            "container_id": container_id,
            "type": "image",
            "account": account_name or "default",
        }
    except Exception as e:
        logger.error(f"[FAIL] Image publish failed: {e}")
        return {"status": "error", "error": str(e), "type": "image"}


async def publish_reel(video_url: str, caption: str, account_name: str = "") -> dict:
    """Publish a reel/video to Instagram (create container → wait for processing → publish)."""
    if DRY_RUN:
        mock_container = _mock_id("container")
        mock_media = _mock_id("media")
        logger.info(f"[DRY-RUN] Simulated reel publish: {mock_media}")
        return {
            "status": "published (dry-run)",
            "media_id": mock_media,
            "container_id": mock_container,
            "type": "reel",
            "dry_run": True,
            "video_url": video_url,
            "caption_preview": caption[:100],
        }
    try:
        svc = _get_ig_service(account_name)
        container_id = await svc.create_video_container(video_url, caption)

        # Wait for video processing (poll every 30s, max 5 min)
        for attempt in range(10):
            await asyncio.sleep(30)
            status = await svc.check_container_status(container_id)
            status_code = status.get("status_code", "")
            logger.info(f"Reel processing status ({attempt + 1}/10): {status_code}")

            if status_code == "FINISHED":
                media_id = await svc.publish_container(container_id)
                return {
                    "status": "published",
                    "media_id": media_id,
                    "container_id": container_id,
                    "type": "reel",
                    "account": account_name or "default",
                }
            elif status_code == "ERROR":
                return {
                    "status": "error",
                    "error": f"Video processing failed: {status}",
                    "type": "reel",
                }

        return {
            "status": "error",
            "error": "Video processing timed out after 5 minutes",
            "container_id": container_id,
            "type": "reel",
        }
    except Exception as e:
        logger.error(f"[FAIL] Reel publish failed: {e}")
        return {"status": "error", "error": str(e), "type": "reel"}


async def publish_carousel(image_urls: list[str], caption: str, account_name: str = "") -> dict:
    """Publish a carousel post (multiple images) to Instagram."""
    if DRY_RUN:
        mock_container = _mock_id("container")
        mock_media = _mock_id("media")
        logger.info(f"[DRY-RUN] Simulated carousel publish: {mock_media} ({len(image_urls)} images)")
        return {
            "status": "published (dry-run)",
            "media_id": mock_media,
            "container_id": mock_container,
            "children_count": len(image_urls),
            "type": "carousel",
            "dry_run": True,
            "caption_preview": caption[:100],
        }
    try:
        svc = _get_ig_service(account_name)
        # Step 1: Create child containers for each image
        children_ids = []
        for url in image_urls:
            child_id = await svc.create_image_container(url, "")
            children_ids.append(child_id)

        # Step 2: Create carousel container
        container_id = await svc.create_carousel_container(children_ids, caption)

        # Step 3: Publish
        media_id = await svc.publish_container(container_id)
        return {
            "status": "published",
            "media_id": media_id,
            "container_id": container_id,
            "children_count": len(children_ids),
            "type": "carousel",
            "account": account_name or "default",
        }
    except Exception as e:
        logger.error(f"[FAIL] Carousel publish failed: {e}")
        return {"status": "error", "error": str(e), "type": "carousel"}


async def check_publish_status(container_id: str) -> dict:
    """Check whether a media container has finished processing."""
    if DRY_RUN:
        return {"id": container_id, "status_code": "FINISHED", "dry_run": True}
    try:
        svc = InstagramService()  # Status check doesn't need account-specific service
        return await svc.check_container_status(container_id)
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def mark_as_published(item_id: str, media_id: str) -> dict:
    """Mark a review queue item as published with the Instagram media ID."""
    return await _queue_service.mark_published(item_id, media_id)


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_publisher_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="list_instagram_accounts",
            description="List all configured Instagram accounts available for publishing. Shows account names you can pass to publish tools.",
            input_model=ListInstagramAccountsInput,
            func=list_instagram_accounts,
        ),
        FunctionTool(
            name="get_approved_items",
            description="Fetch all approved items from the review queue that are ready to publish. Call this first to see what's available.",
            input_model=GetApprovedItemsInput,
            func=get_approved_items,
        ),
        FunctionTool(
            name="publish_image_post",
            description="Publish a single image post to Instagram. Requires a publicly accessible image URL and caption.",
            input_model=PublishImagePostInput,
            func=publish_image_post,
        ),
        FunctionTool(
            name="publish_reel",
            description="Publish a reel/video to Instagram. Waits for video processing (up to 5 min) before publishing.",
            input_model=PublishReelInput,
            func=publish_reel,
        ),
        FunctionTool(
            name="publish_carousel",
            description="Publish a carousel (2-10 images) to Instagram. Provide a list of image URLs and a single caption.",
            input_model=PublishCarouselInput,
            func=publish_carousel,
        ),
        FunctionTool(
            name="check_publish_status",
            description="Check if a media container has finished processing (mainly for videos/reels).",
            input_model=CheckPublishStatusInput,
            func=check_publish_status,
        ),
        FunctionTool(
            name="mark_as_published",
            description="Update the review queue item as published. Call after successful Instagram publish.",
            input_model=MarkAsPublishedInput,
            func=mark_as_published,
        ),
    ]
