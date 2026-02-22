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
from azure.servicebus.aio.management import ServiceBusAdministrationClient

from shared.config.settings import settings

logger = logging.getLogger(__name__)

QUEUE_PENDING = "review-pending"
QUEUE_APPROVED = "review-approved"


class ReviewStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDIT_REQUESTED = "edit_requested"


# ---------------------------------------------------------------------------
# Startup — ensure queues exist
# ---------------------------------------------------------------------------

async def ensure_servicebus_queues() -> None:
    """Create the Service Bus queues if they don't already exist."""
    ns = settings.SERVICEBUS_NAMESPACE
    if not ns:
        logger.warning("SERVICEBUS_NAMESPACE not set — review queue will not work")
        return

    credential = DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID)
    try:
        admin = ServiceBusAdministrationClient(
            fully_qualified_namespace=ns, credential=credential
        )
        async with admin:
            for queue_name in (QUEUE_PENDING, QUEUE_APPROVED):
                try:
                    await admin.get_queue(queue_name)
                    logger.info(f"[Service Bus] Queue '{queue_name}' exists")
                except Exception:
                    await admin.create_queue(
                        queue_name,
                        max_delivery_count=10,
                        default_message_time_to_live="P7D",  # 7 days TTL
                    )
                    logger.info(f"[Service Bus] Created queue '{queue_name}'")
    finally:
        await credential.close()


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
        media_url: str,
        caption: str,
        hashtags: str,
        content_type: str = "image",
        topic: str = "",
        trend_source: str = "",
    ) -> dict:
        """Send a content item to the review-pending queue."""
        item_id = str(uuid.uuid4())[:8]
        item = {
            "id": item_id,
            "status": ReviewStatus.PENDING,
            "account": self._account,
            "media_url": media_url,
            "caption": caption,
            "hashtags": hashtags,
            "content_type": content_type,
            "topic": topic,
            "trend_source": trend_source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_at": None,
            "reviewer_notes": "",
        }

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
