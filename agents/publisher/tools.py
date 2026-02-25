"""Tools for the Publisher agent — publish approved content + send confirmation email.

All reads come from Cosmos DB. No Service Bus peeking.
After publishing, a confirmation email is sent via NotificationService.
"""

import asyncio
import logging

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from config.settings import settings
from services.instagram_service import InstagramService
from services.cosmos_db_service import (
    get_content_by_id,
    mark_content_published,
    query_content,
)
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

_notification_service = NotificationService()


def _build_caption(record: dict) -> str:
    caption = (record.get("caption") or "").strip()
    hashtags = record.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags_text = hashtags.strip()
    else:
        hashtags_text = " ".join(h for h in hashtags if h)

    if hashtags_text and not caption:
        return hashtags_text
    if hashtags_text and caption:
        return f"{caption}\n\n{hashtags_text}"
    return caption


def _get_ig_service(account_name: str = "") -> InstagramService:
    if account_name:
        accounts = settings.INSTAGRAM_ACCOUNTS
        account_id = accounts.get(account_name)
        if not account_id:
            raise ValueError(f"Unknown account '{account_name}'. Available: {list(accounts.keys())}")
        return InstagramService(account_id=account_id)
    return InstagramService()


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class ListInstagramAccountsInput(BaseModel):
    pass


class GetPendingToPublishInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)


class GetPublishHistoryInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)


class GetContentByIdInput(BaseModel):
    content_id: str = Field(..., description="Cosmos content ID (GUID/hex).")


class PublishContentByIdInput(BaseModel):
    content_id: str = Field(..., description="Cosmos content ID (GUID/hex).")
    account_name: str = Field(
        default="",
        description="Optional override account name. Leave empty to use content record target/default account.",
    )


class PublishAllPendingInput(BaseModel):
    account_name: str = Field(
        default="",
        description="Optional override account name for all published items.",
    )
    limit: int = Field(default=50, ge=1, le=200)


class SendPublishConfirmationInput(BaseModel):
    content_id: str = Field(..., description="Content ID that was just published.")


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

async def list_instagram_accounts() -> dict:
    accounts = settings.INSTAGRAM_ACCOUNTS
    return {
        "accounts": [{"name": name, "account_id": aid} for name, aid in accounts.items()],
        "default": next(iter(accounts), "") if accounts else "",
        "count": len(accounts),
    }


async def get_pending_to_be_published(limit: int = 50) -> dict:
    items = await query_content(
        approval_status="approved",
        publish_status="pending",
        limit=limit,
    )
    return {"count": len(items), "items": items}


async def get_publish_history(limit: int = 50) -> dict:
    items = await query_content(publish_status="published", limit=limit)
    return {"count": len(items), "items": items}


async def get_content_details(content_id: str) -> dict:
    record = await get_content_by_id(content_id)
    if not record:
        return {"status": "error", "error": f"Content {content_id} not found"}
    return {"status": "ok", "content": record}


async def _publish_record(record: dict, account_name: str = "") -> dict:
    """Core publish logic for a single record."""
    content_id = record.get("id", "")
    approval_status = record.get("approval_status", "pending")
    if approval_status != "approved":
        return {
            "status": "error",
            "error": f"Content {content_id} is not approved (status={approval_status})",
            "content_id": content_id,
        }

    if record.get("publish_status") == "published":
        return {
            "status": "ok",
            "content_id": content_id,
            "message": "Content already published",
            "instagram_media_id": record.get("instagram_media_id", ""),
        }

    media_type = record.get("media_type", "image")
    post_type = record.get("post_type", "post")
    media_url = record.get("blob_url", "")
    caption_text = _build_caption(record)

    if not media_url:
        return {
            "status": "error",
            "error": f"Content {content_id} has no blob_url",
            "content_id": content_id,
        }

    target_account_id = record.get("target_account_id", "")
    target_account_name = record.get("target_account_name", "")

    try:
        svc = InstagramService(account_id=target_account_id)

        if post_type == "carousel":
            image_urls = record.get("blob_urls") or []
            if not image_urls:
                return {
                    "status": "error",
                    "error": "Carousel content requires blob_urls list",
                    "content_id": content_id,
                }
            children_ids = []
            for url in image_urls:
                child_id = await svc.create_image_container(url, "")
                children_ids.append(child_id)
            container_id = await svc.create_carousel_container(children_ids, caption_text)
            media_id = await svc.publish_container(container_id)
        elif post_type == "reel" or media_type == "video":
            container_id = await svc.create_video_container(media_url, caption_text)
            for _ in range(10):
                await asyncio.sleep(30)
                status = await svc.check_container_status(container_id)
                if status.get("status_code") == "FINISHED":
                    break
                if status.get("status_code") == "ERROR":
                    return {
                        "status": "error",
                        "error": f"Video processing failed: {status}",
                        "content_id": content_id,
                    }
            else:
                return {
                    "status": "error",
                    "error": "Video processing timed out after 5 minutes",
                    "content_id": content_id,
                }
            media_id = await svc.publish_container(container_id)
        else:
            container_id = await svc.create_image_container(media_url, caption_text)
            media_id = await svc.publish_container(container_id)

        # Update DB: mark as published
        await mark_content_published(content_id, media_id, container_id)

        return {
            "status": "published",
            "content_id": content_id,
            "media_type": media_type,
            "post_type": post_type,
            "container_id": container_id,
            "instagram_media_id": media_id,
            "account": target_account_name or "default",
        }
    except Exception as e:
        logger.error(f"[FAIL] Publish failed for content_id={content_id}: {e}")
        return {"status": "error", "content_id": content_id, "error": str(e)}


async def publish_content_by_id(content_id: str, account_name: str = "") -> dict:
    record = await get_content_by_id(content_id)
    if not record:
        return {"status": "error", "error": f"Content {content_id} not found", "content_id": content_id}
    return await _publish_record(record, account_name)


async def publish_all_pending(account_name: str = "", limit: int = 50) -> dict:
    """Publish all approved items that are pending publish, up to limit."""
    pending = await query_content(
        approval_status="approved",
        publish_status="pending",
        limit=limit,
    )

    if not pending:
        return {
            "status": "empty",
            "message": "No approved pending items to publish",
            "processed": 0,
            "published": 0,
            "failed": 0,
            "results": [],
        }

    pending = sorted(pending, key=lambda x: x.get("created_at", ""))

    results: list[dict] = []
    published = 0
    failed = 0

    for record in pending:
        result = await _publish_record(record, account_name)
        results.append(result)
        if str(result.get("status", "")).startswith("published"):
            published += 1
        else:
            failed += 1

    return {
        "status": "completed",
        "processed": len(results),
        "published": published,
        "failed": failed,
        "results": results,
    }


async def send_publish_confirmation(content_id: str) -> dict:
    """Send a confirmation email after content has been published."""
    record = await get_content_by_id(content_id)
    if not record:
        return {"status": "error", "error": f"Content {content_id} not found"}

    if record.get("publish_status") != "published":
        return {"status": "error", "error": f"Content {content_id} is not published yet"}

    await _notification_service.notify_published(record)
    return {"status": "confirmation_sent", "content_id": content_id}


# ---------------------------------------------------------------------------
# Build tools list
# ---------------------------------------------------------------------------

def build_publisher_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="list_instagram_accounts",
            description="List all configured Instagram accounts available for publishing.",
            input_model=ListInstagramAccountsInput,
            func=list_instagram_accounts,
        ),
        FunctionTool(
            name="get_pending_to_be_published",
            description="Get approved content that is pending publish from Cosmos DB.",
            input_model=GetPendingToPublishInput,
            func=get_pending_to_be_published,
        ),
        FunctionTool(
            name="get_publish_history",
            description="Get previously published content history.",
            input_model=GetPublishHistoryInput,
            func=get_publish_history,
        ),
        FunctionTool(
            name="get_content_details",
            description="Get full content details by content_id.",
            input_model=GetContentByIdInput,
            func=get_content_details,
        ),
        FunctionTool(
            name="publish_content_by_id",
            description="Publish a specific approved content item by content_id. Will fail if not approved.",
            input_model=PublishContentByIdInput,
            func=publish_content_by_id,
        ),
        FunctionTool(
            name="publish_all_pending",
            description="Batch publish all approved content that is pending publish (up to limit).",
            input_model=PublishAllPendingInput,
            func=publish_all_pending,
        ),
        FunctionTool(
            name="send_publish_confirmation",
            description="Send a confirmation email after content has been published to Instagram.",
            input_model=SendPublishConfirmationInput,
            func=send_publish_confirmation,
        ),
    ]
