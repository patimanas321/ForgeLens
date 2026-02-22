"""Tools for the Insta Post Generator agent — media generation + caption tooling.

Includes:
    - Image generation (Nano Banana Pro via fal.ai)
    - Video generation (Kling O3 / Sora 2 via fal.ai)
    - Caption/hashtag/refinement helper tools

Media generation is handled entirely through fal.ai's unified API:
  - Images: Nano Banana Pro (Google Gemini 3 Pro Image) — state-of-the-art text-to-image
  - Video:  Kling O3 (primary) or Sora 2 (alt) — configurable via FAL_VIDEO_MODEL

Every generated asset is:
  1. Downloaded from fal.ai CDN to local disk
  2. Uploaded to Azure Blob Storage (public URL)
  3. Metadata persisted in Azure Cosmos DB (NoSQL)
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import fal_client
import httpx
from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.config.settings import settings
from shared.services.blob_storage_service import upload_blob
from shared.services.media_metadata_service import save_media_metadata
from shared.services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)
_review_queue = ReviewQueueService()

# Local media storage for MVP (swap for Azure Blob Storage in production)
MEDIA_DIR = Path(__file__).parent.parent.parent / "data" / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class GenerateImageInput(BaseModel):
    prompt: str = Field(
        ...,
        description=(
            "Detailed prompt describing the image to generate. "
            "Include style, composition, colors, mood, lighting, perspective. "
            "Nano Banana Pro has excellent text rendering — you CAN include text if needed."
        ),
    )
    aspect_ratio: str = Field(
        default="1:1",
        description=(
            "Aspect ratio for the image. Instagram formats: "
            "'1:1' (feed/carousel), '4:5' (portrait feed), '9:16' (story/reel cover), "
            "'16:9' (landscape). Also supports: 'auto', '21:9', '3:2', '4:3', '5:4', '3:4', '2:3'."
        ),
    )
    resolution: str = Field(
        default="1K",
        description="Image resolution: '1K' (standard), '2K' (high), '4K' (ultra). Use '1K' for most Instagram content.",
    )
    output_format: str = Field(
        default="png",
        description="Output format: 'png', 'jpeg', or 'webp'.",
    )


class GenerateVideoInput(BaseModel):
    prompt: str = Field(
        ...,
        description=(
            "Detailed description of the video to generate. Include motion, transitions, "
            "style, camera movements, and mood. Be specific about actions and visual flow."
        ),
    )
    duration: int = Field(
        default=5,
        ge=3,
        le=15,
        description="Video duration in seconds. Kling O3: 3-15s, Sora 2: 4/8/12s.",
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="Aspect ratio: '9:16' (Reels/Stories), '16:9' (landscape), '1:1' (square, Kling only).",
    )
    video_model: str = Field(
        default="",
        description=(
            "Which video model to use. Leave empty for default (FAL_VIDEO_MODEL). "
            "Options: 'kling' for Kling O3, 'sora' for Sora 2."
        ),
    )


class UploadMediaInput(BaseModel):
    local_file_path: str = Field(
        ...,
        description="Path to the local media file to upload to storage.",
    )


class WriteCaptionInput(BaseModel):
    topic: str = Field(..., description="The topic/subject of the post.")
    tone: str = Field(
        default="engaging",
        description="Desired tone: 'inspiring', 'funny', 'educational', 'provocative', 'casual', 'professional'.",
    )
    content_format: str = Field(
        default="image",
        description="Post format: 'image', 'carousel', 'reel', 'story'. Affects caption length.",
    )
    visual_description: str = Field(
        default="",
        description="Description of the media/visual so the caption complements it.",
    )
    target_audience: str = Field(
        default="",
        description="Who the post is for (e.g. 'fitness beginners', 'tech enthusiasts').",
    )
    hook_type: str = Field(
        default="",
        description="Preferred hook style: 'question', 'bold_statement', 'number_list', 'controversy'. Leave empty to auto-select.",
    )


class SuggestHashtagsInput(BaseModel):
    topic: str = Field(..., description="The topic to find hashtags for.")
    caption: str = Field(default="", description="The written caption for context.")
    count: int = Field(default=20, ge=5, le=30, description="Number of hashtags to suggest.")


class RefineCaptionInput(BaseModel):
    original_caption: str = Field(..., description="The current caption to refine.")
    feedback: str = Field(..., description="What to change or improve (e.g. 'make it funnier', 'shorter', 'add a question').")


# ------------------------------------------------------------------
# Helper — download fal.ai output to local disk
# ------------------------------------------------------------------

async def _download_to_local(url: str, extension: str) -> Path:
    """Download a file from a URL and save it locally."""
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{extension}"
    file_path = MEDIA_DIR / file_name
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        file_path.write_bytes(resp.content)
    return file_path


def _resolve_video_model(model_hint: str) -> str:
    """Resolve a video model hint ('kling', 'sora', or full ID) to a fal.ai model ID."""
    if not model_hint:
        return settings.FAL_VIDEO_MODEL
    hint = model_hint.strip().lower()
    if hint == "kling":
        return settings.FAL_VIDEO_MODEL  # default is Kling O3
    if hint == "sora":
        return settings.FAL_VIDEO_MODEL_ALT  # Sora 2
    # Allow passing a full fal.ai model ID directly
    if hint.startswith("fal-ai/"):
        return hint
    return settings.FAL_VIDEO_MODEL


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def generate_image(
    prompt: str,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    output_format: str = "png",
) -> dict:
    """
    Generate an image using Nano Banana Pro (Google Gemini 3 Pro Image) via fal.ai.
    Returns local file path and metadata.
    """
    try:
        model_id = settings.FAL_IMAGE_MODEL
        logger.info(f"[fal.ai] Generating image via {model_id} | aspect={aspect_ratio} res={resolution}")

        result = await fal_client.subscribe_async(
            model_id,
            arguments={
                "prompt": prompt,
                "num_images": 1,
                "aspect_ratio": aspect_ratio,
                "output_format": output_format,
                "resolution": resolution,
                "safety_tolerance": "4",
            },
        )

        image_data = result["images"][0]
        image_url = image_data["url"]

        # Download to local storage
        file_path = await _download_to_local(image_url, output_format)

        # Upload to Azure Blob Storage
        blob_info = await upload_blob(file_path)
        blob_url = blob_info["blob_url"]

        # Persist metadata in Cosmos DB
        doc = await save_media_metadata(
            media_type="image",
            blob_url=blob_url,
            blob_name=blob_info["blob_name"],
            prompt=prompt,
            model=model_id,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            width=image_data.get("width"),
            height=image_data.get("height"),
            file_size_bytes=blob_info["file_size_bytes"],
            fal_url=image_url,
            post_type="post",
            target_account_id=settings.INSTAGRAM_BUSINESS_ACCOUNT_ID,
            description=result.get("description", ""),
            approval_status="pending",
            publish_status="pending",
            extra={"source": "insta_post_generator"},
        )

        await _review_queue.queue_for_review(
            content_id=doc["id"],
            media_url=blob_url,
            caption="",
            hashtags="",
            content_type="image",
            post_type="post",
            target_account_id=settings.INSTAGRAM_BUSINESS_ACCOUNT_ID,
            topic=result.get("description", "") or "Generated image",
            trend_source="insta_post_generator",
        )

        logger.info(f"[OK] Generated image via Nano Banana Pro: {file_path} → {blob_url}")
        return {
            "status": "success",
            "model": model_id,
            "local_file_path": str(file_path),
            "file_name": file_path.name,
            "blob_url": blob_url,
            "cosmos_id": doc["id"],
            "content_id": doc["id"],
            "approval_status": "pending",
            "queue_status": "queued",
            "prompt_used": prompt,
            "description": result.get("description", ""),
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "width": image_data.get("width"),
            "height": image_data.get("height"),
            "fal_url": image_url,
        }

    except Exception as e:
        logger.error(f"[FAIL] Image generation failed: {e}")
        return {"status": "error", "error": str(e), "prompt_used": prompt}


async def generate_video(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    video_model: str = "",
) -> dict:
    """
    Generate a video clip using Kling O3 or Sora 2 via fal.ai.
    Returns local file path and metadata.
    """
    model_id = ""
    try:
        model_id = _resolve_video_model(video_model)
        is_sora = "sora" in model_id
        is_kling = "kling" in model_id

        logger.info(f"[fal.ai] Generating video via {model_id} | duration={duration}s aspect={aspect_ratio}")

        # Build model-specific arguments
        if is_sora:
            # Sora 2: durations 4/8/12, aspect 9:16 or 16:9
            sora_duration = min([d for d in [4, 8, 12] if d >= duration], default=12)
            sora_aspect = aspect_ratio if aspect_ratio in ("9:16", "16:9") else "9:16"
            arguments = {
                "prompt": prompt,
                "duration": str(sora_duration),
                "aspect_ratio": sora_aspect,
                "resolution": "720p",
                "delete_video": False,
            }
        elif is_kling:
            # Kling O3: durations 3-15, aspect 9:16/16:9/1:1
            kling_duration = max(3, min(duration, 15))
            kling_aspect = aspect_ratio if aspect_ratio in ("9:16", "16:9", "1:1") else "9:16"
            arguments = {
                "prompt": prompt,
                "duration": str(kling_duration),
                "aspect_ratio": kling_aspect,
                "negative_prompt": "blur, distort, and low quality",
                "generate_audio": True,
            }
        else:
            # Generic fallback
            arguments = {
                "prompt": prompt,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
            }

        result = await fal_client.subscribe_async(model_id, arguments=arguments)

        video_data = result["video"]
        video_url = video_data["url"]

        # Download to local storage
        file_path = await _download_to_local(video_url, "mp4")

        # Upload to Azure Blob Storage
        blob_info = await upload_blob(file_path)
        blob_url = blob_info["blob_url"]

        # Persist metadata in Cosmos DB
        doc = await save_media_metadata(
            media_type="video",
            blob_url=blob_url,
            blob_name=blob_info["blob_name"],
            prompt=prompt,
            model=model_id,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration,
            file_size_bytes=blob_info["file_size_bytes"],
            fal_url=video_url,
            post_type="reel",
            target_account_id=settings.INSTAGRAM_BUSINESS_ACCOUNT_ID,
            approval_status="pending",
            publish_status="pending",
            extra={"source": "insta_post_generator"},
        )

        await _review_queue.queue_for_review(
            content_id=doc["id"],
            media_url=blob_url,
            caption="",
            hashtags="",
            content_type="video",
            post_type="reel",
            target_account_id=settings.INSTAGRAM_BUSINESS_ACCOUNT_ID,
            topic="Generated reel",
            trend_source="insta_post_generator",
        )

        logger.info(f"[OK] Generated video via {model_id}: {file_path} → {blob_url}")
        return {
            "status": "success",
            "model": model_id,
            "local_file_path": str(file_path),
            "file_name": file_path.name,
            "blob_url": blob_url,
            "cosmos_id": doc["id"],
            "content_id": doc["id"],
            "approval_status": "pending",
            "queue_status": "queued",
            "prompt_used": prompt,
            "duration_seconds": duration,
            "aspect_ratio": aspect_ratio,
            "file_size_bytes": blob_info["file_size_bytes"],
            "fal_url": video_url,
        }

    except Exception as e:
        logger.error(f"[FAIL] Video generation failed: {e}")
        return {"status": "error", "error": str(e), "prompt_used": prompt, "model": model_id}


async def upload_media(local_file_path: str) -> dict:
    """
    Upload a local media file to Azure Blob Storage and return a public URL.

    This is a standalone re-upload tool — useful for uploading externally
    provided files that weren't generated by generate_image / generate_video
    (those already upload automatically).
    """
    path = Path(local_file_path)
    if not path.exists():
        return {"status": "error", "error": f"File not found: {local_file_path}"}

    try:
        blob_info = await upload_blob(path)
        logger.info(f"[OK] Uploaded {path.name} → {blob_info['blob_url']}")
        return {
            "status": "success",
            "local_file_path": str(path),
            "file_name": path.name,
            "file_size_bytes": blob_info["file_size_bytes"],
            "public_url": blob_info["blob_url"],
            "blob_name": blob_info["blob_name"],
            "container": blob_info["container"],
        }
    except Exception as e:
        logger.error(f"[FAIL] Upload failed: {e}")
        return {"status": "error", "error": str(e), "local_file_path": str(path)}


async def write_caption(
    topic: str,
    tone: str = "engaging",
    content_format: str = "image",
    visual_description: str = "",
    target_audience: str = "",
    hook_type: str = "",
) -> dict:
    """Prepare caption-writing brief for the agent's LLM."""
    length_guide = {
        "image": "medium (100-200 words)",
        "carousel": "long (150-300 words, educational)",
        "reel": "short (30-80 words)",
        "story": "very short (10-30 words)",
    }

    return {
        "status": "ready",
        "brief": {
            "topic": topic,
            "tone": tone,
            "format": content_format,
            "visual_description": visual_description,
            "target_audience": target_audience,
            "hook_type": hook_type or "auto-select best fit",
            "recommended_length": length_guide.get(content_format, "medium"),
            "instructions": (
                "Write the caption now. Start with a strong hook in the first line. "
                "Use line breaks for readability. End with a clear CTA. "
                "Do NOT include hashtags in the caption — they go separately."
            ),
        },
    }


async def suggest_hashtags(topic: str, caption: str = "", count: int = 20) -> dict:
    """Provide hashtag selection guidance for the agent's LLM."""
    return {
        "status": "ready",
        "brief": {
            "topic": topic,
            "caption_context": caption[:200] if caption else "N/A",
            "target_count": count,
            "distribution": {
                "broad_popular (1M+ posts)": f"{count // 4} hashtags",
                "medium (100K-1M posts)": f"{count // 2} hashtags",
                "niche (<100K posts)": f"{count - count // 4 - count // 2} hashtags",
            },
            "instructions": (
                "Generate the hashtag list now. Mix broad, medium, and niche hashtags. "
                "All lowercase, no spaces after #. Group them in a single paragraph."
            ),
        },
    }


async def refine_caption(original_caption: str, feedback: str) -> dict:
    """Refine an existing caption based on human or agent feedback."""
    return {
        "status": "ready",
        "original_caption": original_caption,
        "feedback": feedback,
        "instructions": (
            "Rewrite the caption incorporating the feedback. "
            "Keep the same general structure but apply the requested changes. "
            "Return the full updated caption."
        ),
    }


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_insta_post_generator_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="generate_image",
            description=(
                "Generate an image using Nano Banana Pro (Google's state-of-the-art image model). "
                "Supports excellent text rendering, multiple aspect ratios (1:1, 4:5, 9:16, 16:9), "
                "and up to 4K resolution. Automatically uploads to Azure Blob Storage and "
                "persists metadata in Cosmos DB. Returns blob URL + cosmos_id."
            ),
            input_model=GenerateImageInput,
            func=generate_image,
        ),
        FunctionTool(
            name="generate_video",
            description=(
                "Generate a short video clip for Instagram Reels using Kling O3 (default) or Sora 2. "
                "Kling O3: 3-15s, 9:16/16:9/1:1, with native audio. "
                "Sora 2: 4/8/12s, 9:16/16:9, cinematic quality. "
                "Automatically uploads to Azure Blob Storage and persists metadata in Cosmos DB. "
                "Returns blob URL + cosmos_id."
            ),
            input_model=GenerateVideoInput,
            func=generate_video,
        ),
        FunctionTool(
            name="upload_media",
            description=(
                "Upload any local media file to Azure Blob Storage and get a public URL. "
                "Note: generate_image and generate_video already upload automatically — "
                "use this only for externally provided files."
            ),
            input_model=UploadMediaInput,
            func=upload_media,
        ),
        FunctionTool(
            name="write_caption",
            description="Prepare a caption brief with topic, tone, format, and audience. Then write the caption.",
            input_model=WriteCaptionInput,
            func=write_caption,
        ),
        FunctionTool(
            name="suggest_hashtags",
            description="Generate a set of 15-25 relevant hashtags (mix of popular, medium, and niche).",
            input_model=SuggestHashtagsInput,
            func=suggest_hashtags,
        ),
        FunctionTool(
            name="refine_caption",
            description="Rewrite/improve an existing caption based on feedback from human review.",
            input_model=RefineCaptionInput,
            func=refine_caption,
        ),
    ]
