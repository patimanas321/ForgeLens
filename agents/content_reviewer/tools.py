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
- Be advisory-first: prefer APPROVED with concerns for minor quality/style imperfections
- Use NEEDS_REVISION for moderate quality or brand-alignment issues that are fixable
- Use REJECTED only for clear harmful/sensitive content, explicit policy violations, or severe deceptive brand misuse
- Political visuals: reject only if persuasive, partisan, or inflammatory; otherwise mark concern
- Cultural sensitivity: reject only for clearly harmful/derogatory content; otherwise mark concern
- Trademark/brand likeness (logos, packaging, pendant/props) should usually be concern + legal caution, not automatic rejection
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

    Uses Azure Content Safety text scoring as the only gate for text content.
    """
    doc = await get_content_by_id(content_id)
    if not doc:
        return {"error": f"Content {content_id} not found in DB."}

    reviewable_text = _doc_to_reviewable_text(doc)

    if not reviewable_text.strip():
        return {"error": "No reviewable text found in document.", "content_id": content_id}

    # Text gate: Azure Content Safety only
    safety_result = analyze_text(reviewable_text)
    mapped_status = "approved" if safety_result.safe else "rejected"
    notes = "Azure Content Safety text scan"
    if not safety_result.safe:
        notes = f"Blocked categories: {', '.join(safety_result.blocked_categories)}"
    elif safety_result.error:
        notes = f"Azure Content Safety error: {safety_result.error}"
        mapped_status = "needs_revision"

    await set_media_review_status(content_id, mapped_status, notes)

    return {
        "content_id": content_id,
        "content_safety": safety_result.as_dict(),
        "llm_review": None,
    }


async def review_generated_media(content_id: str) -> dict:
    """Review generated media (image/video) AFTER generation.

    For images: vision + Content Safety on the blob URL.
    For videos: Azure Content Safety text scoring on metadata only.
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
            await set_media_review_status(content_id, "rejected", summary, review_score=0)
            result["verdict"] = "REJECTED"
            result["summary"] = summary
            return result

    # Also check the text metadata
    text_safety = analyze_text("")
    reviewable_text = _doc_to_reviewable_text(doc)
    if reviewable_text.strip():
        text_safety = analyze_text(reviewable_text)
        result["text_content_safety"] = text_safety.as_dict()

        if not text_safety.safe:
            summary = f"Text metadata blocked by Content Safety. Categories: {', '.join(text_safety.blocked_categories)}"
            await set_media_review_status(content_id, "rejected", summary, review_score=0)
            result["content_safety"] = text_safety.as_dict()
            return result

    # Layer 2: LLM vision review for images only.
    if media_type == "image" and blob_url:
        llm_result = await _llm_review_image(blob_url, context)
        result["llm_visual_review"] = llm_result
        verdict = str(llm_result.get("verdict", "NEEDS_REVISION")).strip().upper()
        raw_score = llm_result.get("overall_score")
        review_score = None
        try:
            if raw_score is not None:
                review_score = max(0, min(100, int(raw_score)))
        except Exception:
            review_score = None
        if verdict == "APPROVED":
            mapped_status = "approved"
        elif verdict == "REJECTED":
            mapped_status = "rejected"
        else:
            mapped_status = "needs_revision"
        await set_media_review_status(content_id, mapped_status, llm_result.get("summary", ""), review_score=review_score)

        result["verdict"] = verdict
        result["summary"] = llm_result.get("summary", "")
    else:
        mapped_status = "approved" if text_safety.safe else "rejected"
        notes = "Azure Content Safety text scan"
        if text_safety.error:
            mapped_status = "needs_revision"
            notes = f"Azure Content Safety error: {text_safety.error}"
        await set_media_review_status(content_id, mapped_status, notes, review_score=None)
        result["llm_text_review"] = None
        result["content_safety"] = text_safety.as_dict()

    return result


async def review_text(text: str) -> dict:
    """Review arbitrary text for safety (ad-hoc check).

    Useful for checking a caption, prompt, or hashtag set independently.
    """
    if not text or not text.strip():
        return {"error": "No text provided."}

    # Text review: Azure Content Safety only
    safety_result = analyze_text(text)

    return {
        "content_safety": safety_result.as_dict(),
        "llm_review": None,
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
                "Uses Azure Content Safety text scores only for prompt/caption/hashtags/topic. "
                "Returns only raw content_safety fields from the service."
            ),
            input_model=ReviewContentPlanInput,
            func=review_content_plan,
        ),
        FunctionTool(
            name="review_generated_media",
            description=(
                "Review generated media (image or video) AFTER generation. "
                "For images: analyzes the actual image via vision + Content Safety API. "
                "For videos: uses Azure Content Safety text scores on metadata only. "
                "Returns raw content_safety fields for text path; image path includes vision review output."
            ),
            input_model=ReviewGeneratedMediaInput,
            func=review_generated_media,
        ),
        FunctionTool(
            name="review_text",
            description=(
                "Review arbitrary text using Azure Content Safety scores only. "
                "Returns only raw content_safety fields from the service."
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
