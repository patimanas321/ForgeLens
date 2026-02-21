"""
Tools for the Publisher agent — posting content to Instagram via Graph API.
"""

import asyncio
import logging

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.instagram_service import InstagramService
from shared.services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)

_ig_service = InstagramService()
_queue_service = ReviewQueueService()


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class PublishImagePostInput(BaseModel):
    image_url: str = Field(..., description="Publicly accessible URL of the image to post.")
    caption: str = Field(..., description="Full caption text including hashtags.")


class PublishReelInput(BaseModel):
    video_url: str = Field(..., description="Publicly accessible URL of the video.")
    caption: str = Field(..., description="Full caption text including hashtags.")


class PublishCarouselInput(BaseModel):
    image_urls: list[str] = Field(..., description="List of publicly accessible image URLs (2-10 images).")
    caption: str = Field(..., description="Full caption text including hashtags.")


class CheckPublishStatusInput(BaseModel):
    container_id: str = Field(..., description="The media container ID to check.")


class MarkAsPublishedInput(BaseModel):
    item_id: str = Field(..., description="Review queue item ID.")
    media_id: str = Field(..., description="Instagram media ID after successful publish.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def publish_image_post(image_url: str, caption: str) -> dict:
    """Publish a single image post to Instagram (two-step: create container → publish)."""
    try:
        container_id = await _ig_service.create_image_container(image_url, caption)
        media_id = await _ig_service.publish_container(container_id)
        return {
            "status": "published",
            "media_id": media_id,
            "container_id": container_id,
            "type": "image",
        }
    except Exception as e:
        logger.error(f"[FAIL] Image publish failed: {e}")
        return {"status": "error", "error": str(e), "type": "image"}


async def publish_reel(video_url: str, caption: str) -> dict:
    """Publish a reel/video to Instagram (create container → wait for processing → publish)."""
    try:
        container_id = await _ig_service.create_video_container(video_url, caption)

        # Wait for video processing (poll every 30s, max 5 min)
        for attempt in range(10):
            await asyncio.sleep(30)
            status = await _ig_service.check_container_status(container_id)
            status_code = status.get("status_code", "")
            logger.info(f"Reel processing status ({attempt + 1}/10): {status_code}")

            if status_code == "FINISHED":
                media_id = await _ig_service.publish_container(container_id)
                return {
                    "status": "published",
                    "media_id": media_id,
                    "container_id": container_id,
                    "type": "reel",
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


async def publish_carousel(image_urls: list[str], caption: str) -> dict:
    """Publish a carousel post (multiple images) to Instagram."""
    try:
        # Step 1: Create child containers for each image
        children_ids = []
        for url in image_urls:
            child_id = await _ig_service.create_image_container(url, "")
            children_ids.append(child_id)

        # Step 2: Create carousel container
        container_id = await _ig_service.create_carousel_container(children_ids, caption)

        # Step 3: Publish
        media_id = await _ig_service.publish_container(container_id)
        return {
            "status": "published",
            "media_id": media_id,
            "container_id": container_id,
            "children_count": len(children_ids),
            "type": "carousel",
        }
    except Exception as e:
        logger.error(f"[FAIL] Carousel publish failed: {e}")
        return {"status": "error", "error": str(e), "type": "carousel"}


async def check_publish_status(container_id: str) -> dict:
    """Check whether a media container has finished processing."""
    try:
        return await _ig_service.check_container_status(container_id)
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
