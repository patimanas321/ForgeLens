"""Background Service Bus consumer for the review-pending queue.

Listens on the ``review-pending`` queue. When a message arrives (containing
a ``content_id``), it reads the DB record, invokes the Communicator agent to
send a review-notification email, and marks the record as notified.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from services.azure_bus_service import (
    get_review_pending_queue_receiver,
    receive_messages_from_review_pending_queue,
)
from services.cosmos_db_service import get_content_by_id, update_content
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

QUEUE_REVIEW_PENDING = "review-pending"


def _extract_content_id_from_message(msg) -> str:
    try:
        body = msg.body_as_json()
        if isinstance(body, dict):
            content_id = body.get("content_id")
            return str(content_id).strip() if content_id else ""
    except Exception:
        pass

    try:
        body_str = msg.body_as_str(encoding="UTF-8")
        parsed = json.loads(body_str)
        if isinstance(parsed, dict):
            content_id = parsed.get("content_id")
            return str(content_id).strip() if content_id else ""
    except Exception:
        pass

    try:
        parsed = json.loads(str(msg))
        if isinstance(parsed, dict):
            content_id = parsed.get("content_id")
            return str(content_id).strip() if content_id else ""
    except Exception:
        pass

    return ""


class CommunicatorQueueWorker:
    """Consumes ``review-pending`` messages and sends review notification emails."""

    def __init__(
        self,
        poll_interval_seconds: int = 20,
    ) -> None:
        self._poll_interval = poll_interval_seconds
        self._notification_service = NotificationService()

    async def run_forever(self) -> None:
        receiver = get_review_pending_queue_receiver(max_wait_time=5)
        async with receiver:
            while True:
                try:
                    messages = await receive_messages_from_review_pending_queue(
                        receiver,
                        max_message_count=10,
                        max_wait_time=5,
                    )
                    for msg in messages:
                        try:
                            content_id = _extract_content_id_from_message(msg)
                            if not content_id:
                                logger.warning("[communicator-worker] Message missing content_id, completing")
                                await receiver.complete_message(msg)
                                continue

                            await self._process(content_id)
                            await receiver.complete_message(msg)

                        except Exception as exc:
                            logger.error(
                                "[communicator-worker] Failed to process message: %s", exc,
                            )
                            # Don't complete — let it retry

                    if not messages:
                        await asyncio.sleep(self._poll_interval)

                except Exception as exc:
                    logger.error("[communicator-worker] Listener tick failed: %s", exc)
                    await asyncio.sleep(self._poll_interval)

    async def _process(self, content_id: str) -> None:
        """Read DB record, invoke Communicator agent, update notification flag."""
        record = await get_content_by_id(content_id)
        if not record:
            logger.warning("[communicator-worker] Content %s not found in DB", content_id)
            return

        # Skip if already notified (idempotency guard)
        if record.get("auto_notified_for_pending"):
            logger.info("[communicator-worker] Content %s already notified, skipping", content_id)
            return

        # Send the review notification email directly (no agent invocation)
        payload = {
            "id": content_id,
            "content_type": record.get("media_type", "unknown"),
            "topic": record.get("description") or record.get("topic", "Pending review item"),
            "caption": record.get("caption", ""),
            "media_url": record.get("blob_url", ""),
        }
        await self._notification_service.notify_new_review(payload)

        from datetime import datetime, timezone
        await update_content(content_id, {
            "auto_notified_for_pending": True,
            "auto_notified_at": datetime.now(timezone.utc).isoformat(),
            "notification_source": "communicator-queue-worker",
        })

        logger.info("[communicator-worker] Notified for content %s", content_id)


# ---------------------------------------------------------------------------
# Background thread launcher
# ---------------------------------------------------------------------------

_worker_started = False
_worker_lock = threading.Lock()


def start_communicator_queue_trigger_worker(
    poll_interval_seconds: int = 20,
    **_kwargs: Any,
) -> None:
    """Start the communicator queue consumer in a background thread."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    worker = CommunicatorQueueWorker(
        poll_interval_seconds=poll_interval_seconds,
    )

    def _runner() -> None:
        asyncio.run(worker.run_forever())

    thread = threading.Thread(
        target=_runner, name="communicator-queue-worker", daemon=True,
    )
    thread.start()
    logger.info("[communicator-worker] Background queue consumer started (listening on %s)", QUEUE_REVIEW_PENDING)
