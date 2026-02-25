"""Background Service Bus consumer for the review-approved queue.

Listens on the ``review-approved`` queue. When a message arrives (containing
a ``content_id``), it reads the DB record, invokes the Publisher agent to
publish to Instagram, and sends a confirmation email on success.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from services.azure_bus_service import (
    get_review_approved_queue_receiver,
    receive_messages_from_review_approved_queue,
)
from services.cosmos_db_service import get_content_by_id

logger = logging.getLogger(__name__)

QUEUE_REVIEW_APPROVED = "review-approved"


class PublisherQueueWorker:
    """Consumes ``review-approved`` messages and publishes directly (no agent)."""

    def __init__(
        self,
        poll_interval_seconds: int = 20,
    ) -> None:
        self._poll_interval = poll_interval_seconds

    async def run_forever(self) -> None:
        receiver = get_review_approved_queue_receiver(max_wait_time=5)
        async with receiver:
            while True:
                try:
                    messages = await receive_messages_from_review_approved_queue(
                        receiver,
                        max_message_count=5,
                        max_wait_time=5,
                    )
                    for msg in messages:
                        try:
                            body = json.loads(str(msg))
                            content_id = body.get("content_id")
                            if not content_id:
                                logger.warning("[publisher-worker] Message missing content_id, completing")
                                await receiver.complete_message(msg)
                                continue

                            await self._process(content_id)
                            await receiver.complete_message(msg)

                        except Exception as exc:
                            logger.error(
                                "[publisher-worker] Failed to process message: %s", exc,
                            )
                            # Don't complete — let it retry

                    if not messages:
                        await asyncio.sleep(self._poll_interval)

                except Exception as exc:
                    logger.error("[publisher-worker] Listener tick failed: %s", exc)
                    await asyncio.sleep(self._poll_interval)

    async def _process(self, content_id: str) -> None:
        """Read DB record, validate, publish directly + send confirmation."""
        from agents.publisher.tools import publish_content_by_id, send_publish_confirmation

        record = await get_content_by_id(content_id)
        if not record:
            logger.warning("[publisher-worker] Content %s not found in DB", content_id)
            return

        if record.get("approval_status") != "approved":
            logger.info(
                "[publisher-worker] Content %s not human-approved (status=%s), skipping",
                content_id, record.get("approval_status"),
            )
            return

        if record.get("media_review_status") != "approved":
            logger.info(
                "[publisher-worker] Content %s media review not approved (status=%s), skipping",
                content_id, record.get("media_review_status"),
            )
            return

        if record.get("publish_status") == "published":
            logger.info("[publisher-worker] Content %s already published, skipping", content_id)
            return

        # Publish directly (no agent invocation — avoids event-loop mismatch)
        result = await publish_content_by_id(content_id)
        if result.get("status") == "published":
            logger.info("[publisher-worker] Published content %s (ig_media=%s)",
                        content_id, result.get("instagram_media_id", ""))
            # Send confirmation email
            try:
                await send_publish_confirmation(content_id)
                logger.info("[publisher-worker] Confirmation sent for %s", content_id)
            except Exception as exc:
                logger.error("[publisher-worker] Confirm email failed for %s: %s", content_id, exc)
        else:
            logger.error("[publisher-worker] Publish failed for %s: %s",
                         content_id, result.get("error", result))


# ---------------------------------------------------------------------------
# Background thread launcher
# ---------------------------------------------------------------------------

_worker_started = False
_worker_lock = threading.Lock()


def start_publisher_queue_trigger_worker(
    poll_interval_seconds: int = 20,
    **_kwargs: Any,
) -> None:
    """Start the publisher queue consumer in a background thread."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    worker = PublisherQueueWorker(
        poll_interval_seconds=poll_interval_seconds,
    )

    def _runner() -> None:
        asyncio.run(worker.run_forever())

    thread = threading.Thread(
        target=_runner, name="publisher-queue-worker", daemon=True,
    )
    thread.start()
    logger.info("[publisher-worker] Background queue consumer started (listening on %s)", QUEUE_REVIEW_APPROVED)
