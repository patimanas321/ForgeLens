"""
Tools for the Content Reviewer agent — safety and quality gate.

Two-layer review:
  1. Azure AI Content Safety — hard moderation (text + image severity scores)
  2. Azure OpenAI vision — nuanced LLM review (brand, sentiment, politics, vulgarity)
"""

from __future__ import annotations

import json
import logging

from agent_framework import FunctionTool
from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.identity import get_bearer_token_provider
from pydantic import BaseModel, Field

from config.settings import settings
from services.content_safety_service import analyze_text, analyze_image_from_url
from services.cosmos_db_service import (
    get_content_by_id,
    set_media_review_status,
    set_prompt_review_status,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy OpenAI client for vision calls (async)
# ---------------------------------------------------------------------------

_openai_client: AsyncAzureOpenAI | None = None
_openai_credential: AsyncDefaultAzureCredential | None = None


async def _get_openai_client() -> AsyncAzureOpenAI:
    """Lazily create an async Azure OpenAI client for vision / chat calls."""
    global _openai_client, _openai_credential
    if _openai_client is None:
        _openai_credential = AsyncDefaultAzureCredential(
            managed_identity_client_id=settings.AZURE_CLIENT_ID
        )
        _openai_client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            azure_ad_token_provider=get_bearer_token_provider(
                _openai_credential, "https://cognitiveservices.azure.com/.default"
            ),
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    return _openai_client


# ---------------------------------------------------------------------------
# LLM review prompt templates
# ---------------------------------------------------------------------------

_TEXT_REVIEW_SYSTEM = """You are a content safety and brand compliance reviewer. Analyze the given content and return a JSON object with exactly this structure:
{
  "verdict": "APPROVED" | "REJECTED" | "NEEDS_REVISION",
  "persona_alignment": {"status": "pass" | "concern", "detail": "..."},
  "sentiment_risk": {"level": "none" | "low" | "medium" | "high", "detail": "..."},
  "political_angle": {"status": "none" | "detected", "detail": "..."},
  "vulgarity": {"status": "clean" | "concern", "detail": "..."},
  "hashtag_safety": {"status": "pass" | "concern", "detail": "..."},
  "prompt_quality": {"status": "good" | "needs_work", "detail": "..."},
  "cultural_sensitivity": {"status": "pass" | "concern", "detail": "..."},
  "summary": "One-paragraph explanation of the verdict"
}

Rules:
- REJECT anything with political undertones, even subtle ones
- REJECT anything that could hurt religious, cultural, or minority sentiments
- NEEDS_REVISION for minor persona drift or quality issues
- APPROVE only if everything passes
- Be specific in your details — explain exactly what the issue is
Return ONLY the JSON, no markdown fences."""

_IMAGE_REVIEW_SYSTEM = """You are a visual content safety and brand compliance reviewer. You will be shown an image that was generated for an Instagram account. Analyze it and return a JSON object with exactly this structure:
{
  "verdict": "APPROVED" | "REJECTED" | "NEEDS_REVISION",
  "visual_safety": {"status": "pass" | "concern", "detail": "..."},
  "brand_alignment": {"status": "pass" | "concern", "detail": "..."},
  "quality": {"status": "good" | "poor", "detail": "..."},
  "sentiment_risk": {"level": "none" | "low" | "medium" | "high", "detail": "..."},
  "political_angle": {"status": "none" | "detected", "detail": "..."},
  "cultural_sensitivity": {"status": "pass" | "concern", "detail": "..."},
  "description": "Brief description of what you see in the image",
  "summary": "One-paragraph explanation of the verdict"
}

Rules:
- REJECT anything visually inappropriate, politically charged, or culturally insensitive
- NEEDS_REVISION for quality issues or minor brand misalignment
- APPROVE only if the image is safe, on-brand, and high quality
- Describe what you actually see in the image
Return ONLY the JSON, no markdown fences."""


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class ReviewContentPlanInput(BaseModel):
    content_id: str = Field(..., description="The content ID (Cosmos DB document ID) to review before generation.")


class ReviewGeneratedMediaInput(BaseModel):
    content_id: str = Field(..., description="The content ID to review after media generation.")


class ReviewTextInput(BaseModel):
    text: str = Field(..., description="Arbitrary text to check for safety (caption, prompt, hashtags, etc.).")


class GetReviewGuidelinesInput(BaseModel):
    account_name: str = Field(default="", description="Account name to get persona guidelines for. Leave empty for general guidelines.")


# ---------------------------------------------------------------------------
# Helper: LLM text review
# ---------------------------------------------------------------------------

async def _llm_review_text(text: str, context: str = "") -> dict:
    """Call Azure OpenAI to perform nuanced text review."""
    try:
        client = await _get_openai_client()
        user_msg = f"Review the following content:\n\n{text}"
        if context:
            user_msg += f"\n\nAdditional context (persona/brand info):\n{context}"

        response = await client.responses.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            instructions=_TEXT_REVIEW_SYSTEM,
            input=user_msg,
        )

        # Extract text from response
        result_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for block in item.content:
                    if hasattr(block, "text"):
                        result_text += block.text

        return json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("[content-reviewer] LLM returned non-JSON: %s", result_text[:200])
        return {"verdict": "NEEDS_REVISION", "summary": f"LLM review parse error. Raw: {result_text[:500]}"}
    except Exception as e:
        logger.error("[content-reviewer] LLM text review failed: %s", e)
        return {"verdict": "NEEDS_REVISION", "summary": f"LLM review error: {e}"}


async def _llm_review_image(image_url: str, context: str = "") -> dict:
    """Call Azure OpenAI with vision to review a generated image."""
    try:
        client = await _get_openai_client()
        user_content = [
            {"type": "input_text", "text": f"Review this generated Instagram image.\n\nContext: {context}" if context else "Review this generated Instagram image."},
            {"type": "input_image", "image_url": image_url},
        ]

        response = await client.responses.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            instructions=_IMAGE_REVIEW_SYSTEM,
            input=[{"role": "user", "content": user_content}],
        )

        result_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for block in item.content:
                    if hasattr(block, "text"):
                        result_text += block.text

        return json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("[content-reviewer] LLM image review returned non-JSON: %s", result_text[:200])
        return {"verdict": "NEEDS_REVISION", "summary": f"LLM image review parse error. Raw: {result_text[:500]}"}
    except Exception as e:
        logger.error("[content-reviewer] LLM image review failed: %s", e)
        return {"verdict": "NEEDS_REVISION", "summary": f"LLM image review error: {e}"}


# ---------------------------------------------------------------------------
# Helper: build reviewable text from a Cosmos doc
# ---------------------------------------------------------------------------

def _doc_to_reviewable_text(doc: dict) -> str:
    """Extract all text fields from a Cosmos content document for review."""
    parts = []
    if doc.get("prompt"):
        parts.append(f"IMAGE/VIDEO PROMPT: {doc['prompt']}")
    if doc.get("caption"):
        parts.append(f"CAPTION: {doc['caption']}")
    if doc.get("hashtags"):
        tags = doc["hashtags"]
        if isinstance(tags, list):
            tags = " ".join(f"#{t}" for t in tags)
        parts.append(f"HASHTAGS: {tags}")
    if doc.get("description"):
        parts.append(f"TOPIC: {doc['description']}")
    if doc.get("media_type"):
        parts.append(f"MEDIA TYPE: {doc['media_type']}")
    if doc.get("post_type"):
        parts.append(f"POST TYPE: {doc['post_type']}")
    return "\n".join(parts)


def _doc_to_context(doc: dict) -> str:
    """Extract persona/account context from the doc."""
    parts = []
    if doc.get("target_account_name"):
        parts.append(f"Account: {doc['target_account_name']}")
    if doc.get("account"):
        parts.append(f"Account key: {doc['account']}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

async def review_content_plan(content_id: str) -> dict:
    """Review a content plan (Cosmos doc) BEFORE media generation.

    Runs both Azure Content Safety (hard gate) and LLM review (nuanced).
    """
    doc = await get_content_by_id(content_id)
    if not doc:
        return {"error": f"Content {content_id} not found in DB."}

    reviewable_text = _doc_to_reviewable_text(doc)
    context = _doc_to_context(doc)

    if not reviewable_text.strip():
        return {"error": "No reviewable text found in document.", "content_id": content_id}

    # Layer 1: Azure Content Safety (hard gate)
    safety_result = analyze_text(reviewable_text)

    if not safety_result.safe:
        summary = f"Content blocked by Azure Content Safety. Categories flagged: {', '.join(safety_result.blocked_categories)}"
        await set_prompt_review_status(content_id, "rejected", summary)
        return {
            "content_id": content_id,
            "verdict": "REJECTED",
            "reason": "Azure Content Safety hard block",
            "content_safety": safety_result.as_dict(),
            "llm_review": None,
            "summary": summary,
        }

    # Layer 2: LLM nuanced review
    llm_result = await _llm_review_text(reviewable_text, context)
    verdict = str(llm_result.get("verdict", "NEEDS_REVISION")).strip().upper()
    status_map = {
        "APPROVED": "approved",
        "REJECTED": "rejected",
        "NEEDS_REVISION": "needs_revision",
    }
    mapped_status = status_map.get(verdict, "needs_revision")
    await set_prompt_review_status(content_id, mapped_status, llm_result.get("summary", ""))

    return {
        "content_id": content_id,
        "verdict": verdict,
        "content_safety": safety_result.as_dict(),
        "llm_review": llm_result,
        "summary": llm_result.get("summary", ""),
    }


async def review_generated_media(content_id: str) -> dict:
    """Review generated media (image/video) AFTER generation.

    For images: vision + Content Safety on the blob URL.
    For videos: Content Safety on thumbnail / first frame if available,
                plus LLM review of the associated text metadata.
    """
    doc = await get_content_by_id(content_id)
    if not doc:
        return {"error": f"Content {content_id} not found in DB."}

    blob_url = doc.get("blob_url", "")
    media_type = doc.get("media_type", "")
    context = _doc_to_context(doc)

    if not blob_url:
        return {
            "error": "No blob_url found — media may not be generated yet.",
            "content_id": content_id,
            "generation_status": doc.get("generation_status", "unknown"),
        }

    result: dict = {
        "content_id": content_id,
        "media_type": media_type,
        "blob_url": blob_url,
    }

    # Layer 1: Azure Content Safety on the image
    if media_type == "image":
        image_safety = analyze_image_from_url(blob_url)
        result["image_content_safety"] = image_safety.as_dict()

        if not image_safety.safe:
            summary = f"Image blocked by Azure Content Safety. Categories: {', '.join(image_safety.blocked_categories)}"
            await set_media_review_status(content_id, "rejected", summary)
            result["verdict"] = "REJECTED"
            result["summary"] = summary
            return result

    # Also check the text metadata
    reviewable_text = _doc_to_reviewable_text(doc)
    if reviewable_text.strip():
        text_safety = analyze_text(reviewable_text)
        result["text_content_safety"] = text_safety.as_dict()

        if not text_safety.safe:
            summary = f"Text metadata blocked by Content Safety. Categories: {', '.join(text_safety.blocked_categories)}"
            await set_media_review_status(content_id, "rejected", summary)
            result["verdict"] = "REJECTED"
            result["summary"] = summary
            return result

    # Layer 2: LLM vision review (images only — videos get text-only review)
    if media_type == "image" and blob_url:
        llm_result = await _llm_review_image(blob_url, context)
        result["llm_visual_review"] = llm_result
    else:
        # For video: review the text metadata only (vision on keyframes is a future enhancement)
        llm_result = await _llm_review_text(reviewable_text, context + " [This is a video — visual review not available, reviewing text metadata only.]")
        result["llm_text_review"] = llm_result

    verdict = str(llm_result.get("verdict", "NEEDS_REVISION")).strip().upper()
    status_map = {
        "APPROVED": "approved",
        "REJECTED": "rejected",
        "NEEDS_REVISION": "needs_revision",
    }
    mapped_status = status_map.get(verdict, "needs_revision")
    await set_media_review_status(content_id, mapped_status, llm_result.get("summary", ""))

    result["verdict"] = verdict
    result["summary"] = llm_result.get("summary", "")
    return result


async def review_text(text: str) -> dict:
    """Review arbitrary text for safety (ad-hoc check).

    Useful for checking a caption, prompt, or hashtag set independently.
    """
    if not text or not text.strip():
        return {"error": "No text provided."}

    # Layer 1: Content Safety
    safety_result = analyze_text(text)

    if not safety_result.safe:
        return {
            "verdict": "REJECTED",
            "content_safety": safety_result.as_dict(),
            "llm_review": None,
            "summary": f"Text blocked by Azure Content Safety. Categories: {', '.join(safety_result.blocked_categories)}",
        }

    # Layer 2: LLM review
    llm_result = await _llm_review_text(text)

    return {
        "verdict": llm_result.get("verdict", "NEEDS_REVISION"),
        "content_safety": safety_result.as_dict(),
        "llm_review": llm_result,
        "summary": llm_result.get("summary", ""),
    }


async def get_review_guidelines(account_name: str = "") -> dict:
    """Return the persona avoid-list and brand rules for an account.

    Loads from insta_profiles/<account_name>.json if available.
    """
    from account_profile import load_all_profiles

    profiles = load_all_profiles()

    if account_name and account_name in profiles:
        profile = profiles[account_name]
        return {
            "account": account_name,
            "display_name": profile.display_name,
            "avoid": profile.persona.get("avoid", []),
            "tone": profile.persona.get("tone", ""),
            "themes": profile.persona.get("themes", []),
            "visual_style": profile.content_rules.get("visual_style", ""),
            "caption_style": profile.content_rules.get("caption_style", ""),
            "hashtag_rules": profile.content_rules.get("hashtag_count", {}),
        }

    # Return all profiles' guidelines
    all_guidelines = {}
    for name, profile in profiles.items():
        all_guidelines[name] = {
            "display_name": profile.display_name,
            "avoid": profile.persona.get("avoid", []),
            "tone": profile.persona.get("tone", ""),
        }
    return {"accounts": all_guidelines}


# ---------------------------------------------------------------------------
# Assemble tools
# ---------------------------------------------------------------------------

def build_content_reviewer_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="review_content_plan",
            description=(
                "Review a content plan (Cosmos DB record) BEFORE media generation. "
                "Checks prompt, caption, hashtags, and topic for safety, brand alignment, "
                "political content, sentiment risk, and vulgarity. "
                "Returns verdict: APPROVED / REJECTED / NEEDS_REVISION."
            ),
            input_model=ReviewContentPlanInput,
            func=review_content_plan,
        ),
        FunctionTool(
            name="review_generated_media",
            description=(
                "Review generated media (image or video) AFTER generation. "
                "For images: analyzes the actual image via vision + Content Safety API. "
                "For videos: reviews text metadata (visual keyframe review is future enhancement). "
                "Returns verdict: APPROVED / REJECTED / NEEDS_REVISION."
            ),
            input_model=ReviewGeneratedMediaInput,
            func=review_generated_media,
        ),
        FunctionTool(
            name="review_text",
            description=(
                "Review arbitrary text for safety — useful for ad-hoc checks on "
                "captions, prompts, hashtags, or any text content."
            ),
            input_model=ReviewTextInput,
            func=review_text,
        ),
        FunctionTool(
            name="get_review_guidelines",
            description=(
                "Get the persona avoid-list, brand rules, tone, and visual style "
                "guidelines for an account. Helps inform review decisions."
            ),
            input_model=GetReviewGuidelinesInput,
            func=get_review_guidelines,
        ),
    ]
