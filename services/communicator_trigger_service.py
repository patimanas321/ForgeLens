"""Background queue-trigger worker for communicator notifications."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any
from datetime import datetime, timezone

from services.media_metadata_service import get_content_by_id, update_content
from services.review_queue_service import ReviewQueueService

logger = logging.getLogger(__name__)


class CommunicatorQueueTriggerWorker:
    def __init__(self, poll_interval_seconds: int = 20, communicator_agent: Any = None) -> None:
        self._poll_interval_seconds = poll_interval_seconds
        self._queue_service = ReviewQueueService()
        self._communicator_agent = communicator_agent

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _notify_pending_item(self, item: dict, item_id: str) -> str:
        await self._communicator_agent.run(
            (
                f"Content {item_id} is pending review and needs a reminder. "
                "Use send_review_reminder with "
                f"item_id={item_id} and note='Automated queue trigger reminder'. "
                "Do not call any other tool."
            )
        )
        return "communicator-agent-trigger"

    async def _tick(self) -> None:
        pending_items = await self._queue_service.get_pending_reviews()
        for item in pending_items:
            item_id = item.get("content_id") or item.get("id")
            if not item_id:
                continue

            record = await get_content_by_id(item_id)
            if not record:
                continue

            if record.get("auto_notified_for_pending"):
                continue

            notification_source = await self._notify_pending_item(item, item_id)
            await update_content(
                item_id,
                {
                    "auto_notified_for_pending": True,
                    "auto_notified_at": self._now_iso(),
                    "notification_source": notification_source,
                },
            )
            logger.info(f"[communicator-trigger] Notified pending item {item_id}")

    async def run_forever(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception as exc:
                logger.error(f"[communicator-trigger] Worker tick failed: {exc}")
            await asyncio.sleep(self._poll_interval_seconds)


_worker_started = False
_worker_lock = threading.Lock()


def start_communicator_queue_trigger_worker(
    poll_interval_seconds: int = 20,
    communicator_agent: Any = None,
) -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    worker = CommunicatorQueueTriggerWorker(
        poll_interval_seconds=poll_interval_seconds,
        communicator_agent=communicator_agent,
    )

    def _runner() -> None:
        asyncio.run(worker.run_forever())

    thread = threading.Thread(target=_runner, name="communicator-queue-trigger", daemon=True)
    thread.start()
    logger.info("[communicator-trigger] Background queue trigger worker started")
