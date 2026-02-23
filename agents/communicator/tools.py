"""Tools for Communicator agent — reminders and notification actions."""

from __future__ import annotations

from datetime import datetime, timezone

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.media_metadata_service import get_content_by_id, update_content
from shared.services.notification_service import NotificationService
from shared.services.review_queue_service import ReviewQueueService

_notification_service = NotificationService()
_queue_service = ReviewQueueService()


class SendReviewReminderInput(BaseModel):
    item_id: str = Field(..., description="Review/content item id")
    note: str = Field(default="", description="Optional reminder note")


class NotifyPendingForAccountInput(BaseModel):
    target_account_id: str = Field(..., description="Target account id to notify for")
    limit: int = Field(default=20, ge=1, le=200)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def send_review_reminder(item_id: str, note: str = "") -> dict:
    status = await _queue_service.get_review_status(item_id)
    if "error" in status:
        return status

    payload = {
        "id": status.get("id", item_id),
        "content_type": status.get("content_type", "unknown"),
        "topic": status.get("topic", "Pending review item"),
        "caption": status.get("caption", ""),
        "media_url": status.get("media_url", ""),
    }
    if note:
        payload["topic"] = f"{payload['topic']} — Reminder: {note}"

    await _notification_service.notify_new_review(payload)
    await update_content(item_id, {"last_reminder_at": _now_iso(), "last_reminder_note": note})

    return {
        "status": "notified",
        "item_id": item_id,
        "note": note,
    }


async def notify_pending_for_account(target_account_id: str, limit: int = 20) -> dict:
    pending = await _queue_service.get_pending_reviews()
    sent = 0
    skipped = 0

    for item in pending:
        if target_account_id and item.get("target_account_id") != target_account_id:
            continue
        item_id = item.get("content_id") or item.get("id")
        if not item_id:
            skipped += 1
            continue

        record = await get_content_by_id(item_id)
        if not record:
            skipped += 1
            continue

        await _notification_service.notify_new_review(item)
        await update_content(item_id, {"last_reminder_at": _now_iso(), "notification_source": "communicator_agent"})
        sent += 1
        if sent >= limit:
            break

    return {
        "status": "completed",
        "target_account_id": target_account_id,
        "sent": sent,
        "skipped": skipped,
    }


def build_communicator_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="send_review_reminder",
            description="Send a reminder notification for one pending review item.",
            input_model=SendReviewReminderInput,
            func=send_review_reminder,
        ),
        FunctionTool(
            name="notify_pending_for_account",
            description="Send reminder notifications for pending items of a target account.",
            input_model=NotifyPendingForAccountInput,
            func=notify_pending_for_account,
        ),
    ]
