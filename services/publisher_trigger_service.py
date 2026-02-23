"""Background queue-trigger worker for publisher automation."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from services.media_metadata_service import get_content_by_id
from services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)


class PublisherQueueTriggerWorker:
    def __init__(self, publisher_agent: Any, poll_interval_seconds: int = 20) -> None:
        self._poll_interval_seconds = poll_interval_seconds
        self._queue_service = ReviewQueueService()
        self._publisher_agent = publisher_agent

    async def _tick(self) -> None:
        approved_items = await self._queue_service.get_approved_items()
        approved_items = sorted(approved_items, key=lambda item: item.get("created_at", ""))

        for item in approved_items:
            item_id = item.get("content_id") or item.get("id")
            if not item_id:
                continue

            record = await get_content_by_id(item_id)
            if not record:
                continue

            if record.get("approval_status") != "approved":
                continue

            if record.get("publish_status") == "published":
                continue

            await self._publisher_agent.run(
                (
                    f"Content {item_id} is approved and ready for publishing. "
                    "Use publish_content_by_id with "
                    f"content_id={item_id}. "
                    "Do not call any other tool."
                )
            )
            logger.info(f"[publisher-trigger] Triggered publish for item {item_id}")

    async def run_forever(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception as exc:
                logger.error(f"[publisher-trigger] Worker tick failed: {exc}")
            await asyncio.sleep(self._poll_interval_seconds)


_worker_started = False
_worker_lock = threading.Lock()


def start_publisher_queue_trigger_worker(
    publisher_agent: Any,
    poll_interval_seconds: int = 20,
) -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    worker = PublisherQueueTriggerWorker(
        publisher_agent=publisher_agent,
        poll_interval_seconds=poll_interval_seconds,
    )

    def _runner() -> None:
        asyncio.run(worker.run_forever())

    thread = threading.Thread(target=_runner, name="publisher-queue-trigger", daemon=True)
    thread.start()
    logger.info("[publisher-trigger] Background queue trigger worker started")
