"""
Review Queue service — human-in-the-loop approval via Azure Service Bus.

Two queues:
  review-pending   → agent enqueues content; reviewer dequeues to review
  review-approved  → reviewer enqueues approved content; agent reads to publish

Auth: DefaultAzureCredential (passwordless).
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient

from shared.config.settings import settings
from shared.services.media_metadata_service import (
    get_content_by_id,
    mark_content_published,
    set_approval_status,
    update_content,
)

logger = logging.getLogger(__name__)

QUEUE_PENDING = "review-pending"
QUEUE_APPROVED = "review-approved"


class ReviewStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDIT_REQUESTED = "edit_requested"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ReviewQueueService:
    """Service Bus-backed review queue for the human-in-the-loop workflow."""

    _credential: DefaultAzureCredential | None = None
    _client_instance: ServiceBusClient | None = None

    def __init__(self, account_name: str = "") -> None:
        self._account = account_name
        self._ns = settings.SERVICEBUS_NAMESPACE

    @classmethod
    def _get_client(cls) -> ServiceBusClient:
        """Return a shared ServiceBusClient (lazily created, singleton)."""
        if cls._client_instance is None:
            cls._credential = DefaultAzureCredential(
                managed_identity_client_id=settings.AZURE_CLIENT_ID
            )
            cls._client_instance = ServiceBusClient(
                fully_qualified_namespace=settings.SERVICEBUS_NAMESPACE,
                credential=cls._credential,
            )
        return cls._client_instance

    # ------------------------------------------------------------------
    # Agent-facing: submit content for review
    # ------------------------------------------------------------------

    async def queue_for_review(
        self,
        *,
        content_id: str,
        media_url: str,
        caption: str = "",
        hashtags: str = "",
        content_type: str = "image",
        post_type: str = "post",
        target_account_id: str = "",
        topic: str = "",
        trend_source: str = "",
    ) -> dict:
        """Send a content item to the review-pending queue."""
        item_id = content_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        item = {
            "id": item_id,
            "content_id": item_id,
            "status": ReviewStatus.PENDING,
            "account": self._account,
            "target_account_id": target_account_id,
            "media_url": media_url,
            "caption": caption,
            "hashtags": hashtags,
            "content_type": content_type,
            "post_type": post_type,
            "topic": topic,
            "trend_source": trend_source,
            "created_at": now,
            "reviewed_at": None,
            "reviewer_notes": "",
        }

        db_item = await get_content_by_id(item_id)
        if db_item:
            await update_content(
                item_id,
                {
                    "approval_status": ReviewStatus.PENDING,
                    "publish_status": db_item.get("publish_status", "pending"),
                    "queued_for_review_at": now,
                    "caption": caption or db_item.get("caption", ""),
                    "hashtags": [h.strip() for h in hashtags.split() if h.strip()] or db_item.get("hashtags", []),
                    "post_type": post_type or db_item.get("post_type", "post"),
                    "target_account_id": target_account_id or db_item.get("target_account_id", ""),
                },
            )

        client = self._get_client()
        sender = client.get_queue_sender(QUEUE_PENDING)
        async with sender:
            msg = ServiceBusMessage(
                body=json.dumps(item),
                application_properties={
                    "item_id": item_id,
                    "account": self._account,
                    "content_type": content_type,
                },
                subject=topic or "Instagram Post",
                message_id=item_id,
            )
            await sender.send_messages(msg)
        logger.info(
            f"[Service Bus] Queued item {item_id} for review "
            f"(account={self._account})"
        )
        return item

    # ------------------------------------------------------------------
    # Agent-facing: check what's pending / approved
    # ------------------------------------------------------------------

    async def get_pending_reviews(self) -> list[dict]:
        """Peek at all items awaiting human review."""
        return await self._peek_queue(QUEUE_PENDING)

    async def get_approved_items(self) -> list[dict]:
        """Peek at approved items ready to publish."""
        return await self._peek_queue(QUEUE_APPROVED)

    async def get_review_status(self, item_id: str) -> dict:
        """Get status for an item from pending/approved queue, or fallback to DB."""
        pending = await self._peek_queue(QUEUE_PENDING)
        for item in pending:
            if item.get("id") == item_id:
                return item

        approved = await self._peek_queue(QUEUE_APPROVED)
        for item in approved:
            if item.get("id") == item_id:
                return item

        db_item = await get_content_by_id(item_id)
        if db_item:
            return {
                "id": db_item.get("id"),
                "status": db_item.get("approval_status", "unknown"),
                "publish_status": db_item.get("publish_status", "pending"),
                "target_account_id": db_item.get("target_account_id", ""),
                "created_at": db_item.get("created_at"),
                "reviewed_at": db_item.get("reviewed_at"),
                "reviewer_notes": db_item.get("reviewer_notes", ""),
            }

        return {"error": f"Item {item_id} not found"}

    # ------------------------------------------------------------------
    # Reviewer-facing: approve / reject / request edits
    # ------------------------------------------------------------------

    async def approve_item(self, item_id: str, notes: str = "") -> dict:
        """Move an item from pending → approved."""
        return await self._transition_item(item_id, ReviewStatus.APPROVED, notes)

    async def reject_item(self, item_id: str, notes: str = "") -> dict:
        """Reject an item (removes from pending)."""
        return await self._transition_item(item_id, ReviewStatus.REJECTED, notes)

    async def request_edits(self, item_id: str, notes: str) -> dict:
        """Request edits — removes from pending so agent can re-process."""
        return await self._transition_item(item_id, ReviewStatus.EDIT_REQUESTED, notes)

    # ------------------------------------------------------------------
    # Post-publish: remove from approved queue
    # ------------------------------------------------------------------

    async def mark_published(self, item_id: str, media_id: str) -> dict:
        """Complete (remove) an approved item after publishing."""
        client = self._get_client()
        receiver = client.get_queue_receiver(QUEUE_APPROVED, max_wait_time=5)
        async with receiver:
            messages = await receiver.receive_messages(
                max_message_count=50, max_wait_time=5
            )
            for msg in messages:
                body = json.loads(str(msg))
                if body.get("id") == item_id:
                    body["published_at"] = datetime.now(timezone.utc).isoformat()
                    body["instagram_media_id"] = media_id
                    await receiver.complete_message(msg)
                    await mark_content_published(item_id, media_id)
                    logger.info(f"[Service Bus] Marked {item_id} as published")
                    return body
                else:
                    await receiver.abandon_message(msg)
        return {"error": f"Item {item_id} not found in approved queue"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _peek_queue(self, queue_name: str) -> list[dict]:
        """Peek all messages in a queue (non-destructive), filtered by account."""
        client = self._get_client()
        items: list[dict] = []
        receiver = client.get_queue_receiver(queue_name, max_wait_time=5)
        async with receiver:
            peeked = await receiver.peek_messages(max_message_count=50)
            for msg in peeked:
                body = json.loads(str(msg))
                if self._account and body.get("account") != self._account:
                    continue
                items.append(body)
        items.sort(key=lambda x: x.get("created_at", ""))
        return items

    async def _transition_item(
        self, item_id: str, new_status: str, notes: str
    ) -> dict:
        """Receive a specific item from pending, update status, and route it."""
        client = self._get_client()
        receiver = client.get_queue_receiver(QUEUE_PENDING, max_wait_time=5)
        async with receiver:
            messages = await receiver.receive_messages(
                max_message_count=50, max_wait_time=5
            )
            for msg in messages:
                body = json.loads(str(msg))
                if body.get("id") == item_id:
                    body["status"] = new_status
                    body["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    body["reviewer_notes"] = notes
                    await receiver.complete_message(msg)
                    await set_approval_status(item_id, new_status, notes)

                    # If approved, forward to the approved queue
                    if new_status == ReviewStatus.APPROVED:
                        sender = client.get_queue_sender(QUEUE_APPROVED)
                        async with sender:
                            approved_msg = ServiceBusMessage(
                                body=json.dumps(body),
                                application_properties={
                                    "item_id": item_id,
                                    "account": body.get("account", ""),
                                    "content_type": body.get(
                                        "content_type", "image"
                                    ),
                                },
                                subject=body.get("topic", "Instagram Post"),
                                message_id=f"{item_id}-approved",
                            )
                            await sender.send_messages(approved_msg)

                    logger.info(
                        f"[Service Bus] Item {item_id} → {new_status}"
                    )
                    return body
                else:
                    await receiver.abandon_message(msg)

        return {"error": f"Item {item_id} not found in pending queue"}
