"""Background worker for media generation via fal.ai.

Two concurrent loops run in a single background thread:

1. **Queue listener** — consumes ``media-generation`` Service Bus messages,
   reads the DB record, submits a fal.ai async request, and stores the
   ``fal_request_id`` in DB (``generation_status='submitted'``).

2. **Progress poller** — periodically queries DB for records with
   ``generation_status='submitted'``, checks fal.ai for completion, and on
   success: downloads the asset → uploads to Blob Storage → updates DB →
   enqueues onto ``review-pending`` for human approval.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fal_client.client import Completed

from services.azure_bus_service import (
    get_media_generation_queue_receiver,
    receive_messages_from_media_generation_queue,
    send_message_to_review_pending_queue,
)
from services.cosmos_db_service import (
    get_content_by_id,
    update_content,
)
from services.blob_storage_service import upload_blob
from services.fal_ai_service import FalAIService
from services.image_generator_service import ImageGeneratorService
from services.video_generator_service import VideoGeneratorService

logger = logging.getLogger(__name__)

QUEUE_GENERATION = "media-generation"
QUEUE_REVIEW_PENDING = "review-pending"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _download(url: str, ext: str) -> Path:
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    path = Path(tempfile.gettempdir()) / name
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class MediaGenerationWorker:
    """Background worker: queue listener + progress poller."""

    def __init__(self, poll_interval_seconds: int = 15) -> None:
        self._poll_interval = poll_interval_seconds
        self._fal_service = FalAIService()
        self._image_generator = ImageGeneratorService(fal_service=self._fal_service)
        self._video_generator = VideoGeneratorService(fal_service=self._fal_service)

    # ------------------------------------------------------------------
    # Loop 1 — Queue listener
    # ------------------------------------------------------------------

    async def _listen_queue(self) -> None:
        """Consume media-generation queue messages and submit to fal.ai."""
        receiver = get_media_generation_queue_receiver(max_wait_time=5)
        async with receiver:
            while True:
                messages = await receive_messages_from_media_generation_queue(
                    receiver,
                    max_message_count=10,
                    max_wait_time=5,
                )
                for msg in messages:
                    try:
                        body = json.loads(str(msg))
                        content_id = body["content_id"]
                        await self._submit_generation(content_id)
                        await receiver.complete_message(msg)
                    except Exception as exc:
                        logger.error(
                            "[gen-worker] Failed to process message: %s", exc
                        )
                        # Don't complete — let it retry
                if not messages:
                    await asyncio.sleep(2)

    async def _submit_generation(self, content_id: str) -> None:
        """Read DB record and submit generation using configured provider/services."""
        record = await get_content_by_id(content_id)
        if not record:
            logger.warning("[gen-worker] Content %s not found in DB", content_id)
            return

        if record.get("generation_status") != "queued":
            logger.info(
                "[gen-worker] Content %s status is '%s', skipping",
                content_id, record.get("generation_status"),
            )
            return

        media_type = record.get("media_type", "image")
        if media_type == "image":
            submission = await self._image_generator.generate(
                prompt=record.get("prompt", ""),
                aspect_ratio=record.get("aspect_ratio", "1:1"),
                output_format=record.get("output_format", "png"),
                resolution=record.get("resolution", "1K"),
            )
        else:
            submission = await self._video_generator.generate(
                prompt=record.get("prompt", ""),
                duration_seconds=record.get("duration_seconds") or 5,
                aspect_ratio=record.get("aspect_ratio", "9:16"),
            )

        mode = str(submission.get("mode", "async")).lower()
        provider = str(submission.get("provider", "fal")).lower()
        model_id = submission.get("model_id", "")

        if mode == "sync" and media_type == "image":
            image_url = submission.get("image_url", "")
            if not image_url:
                raise RuntimeError("Sync image generation returned no image_url")

            await update_content(content_id, {
                "generation_status": "completed",
                "generation_submitted_at": _now_iso(),
                "generation_completed_at": _now_iso(),
                "generation_provider": provider,
                "generation_mode": mode,
                "generation_model_id": model_id,
            })
            await self._handle_completed(content_id, model_id, "", record, precomputed_result={"images": [{"url": image_url}]})
            logger.info("[gen-worker] Sync image generation completed immediately content_id=%s provider=%s", content_id, provider)
            return

        request_id = submission.get("request_id", "")
        if not request_id or not model_id:
            raise RuntimeError(f"Async generation missing request_id/model_id for content {content_id}")

        await update_content(content_id, {
            "generation_status": "submitted",
            "fal_request_id": request_id,
            "fal_model_id": model_id,
            "generation_provider": provider,
            "generation_mode": mode,
            "generation_model_id": model_id,
            "generation_submitted_at": _now_iso(),
        })

        logger.info("[gen-worker] Submitted content_id=%s provider=%s mode=%s request_id=%s", content_id, provider, mode, request_id)

    # ------------------------------------------------------------------
    # Loop 2 — Progress poller
    # ------------------------------------------------------------------

    async def _poll_progress(self) -> None:
        """Periodically check fal.ai status for submitted requests."""
        while True:
            try:
                await self._check_submitted_items()
            except Exception as exc:
                logger.error("[gen-worker] Poller tick failed: %s", exc)
            await asyncio.sleep(self._poll_interval)

    async def _check_submitted_items(self) -> None:
        """Query DB for generation_status='submitted' and check fal.ai."""
        # Use a cross-partition query for generation_status
        from services.cosmos_db_service import _get_container

        container = await _get_container()
        query = (
            "SELECT * FROM c "
            "WHERE c.generation_status = 'submitted' "
            "ORDER BY c.generation_submitted_at ASC "
            "OFFSET 0 LIMIT 50"
        )

        items: list[dict] = []
        async for item in container.query_items(query=query, max_item_count=50):
            items.append(item)

        if not items:
            return

        logger.info("[gen-worker] Checking %d submitted generation(s)", len(items))

        for item in items:
            content_id = item["id"]
            request_id = item.get("fal_request_id", "")
            model_id = item.get("fal_model_id", "")
            provider = str(item.get("generation_provider", "fal")).lower()
            mode = str(item.get("generation_mode", "async")).lower()

            if provider != "fal" or mode != "async":
                logger.info(
                    "[gen-worker] Content %s has provider=%s mode=%s in submitted state; skipping poll",
                    content_id, provider, mode,
                )
                continue

            if not request_id or not model_id:
                logger.warning(
                    "[gen-worker] Content %s missing fal_request_id or fal_model_id",
                    content_id,
                )
                continue

            try:
                status = await self._fal_service.status(model_id, request_id)
            except Exception as exc:
                logger.error(
                    "[gen-worker] Failed to check status for %s: %s",
                    content_id, exc,
                )
                continue

            if isinstance(status, Completed):
                await self._handle_completed(content_id, model_id, request_id, item)
            else:
                # Still Queued or InProgress — nothing to do yet
                logger.debug(
                    "[gen-worker] Content %s still %s",
                    content_id, type(status).__name__,
                )

    async def _handle_completed(
        self,
        content_id: str,
        model_id: str,
        request_id: str,
        record: dict,
        precomputed_result: dict | None = None,
    ) -> None:
        """Download result, upload to blob, update DB, enqueue for review."""
        result = precomputed_result or await self._fal_service.result(model_id, request_id)

        media_type = record.get("media_type", "image")

        if media_type == "video":
            asset_url = result["video"]["url"]
            ext = "mp4"
        else:
            asset_url = result["images"][0]["url"]
            ext = record.get("output_format", "png")

        # Download from fal.ai CDN
        file_path = await _download(asset_url, ext)

        # Upload to Azure Blob Storage
        blob_info = await upload_blob(file_path)
        blob_url = blob_info["blob_url"]

        # Extra metadata from the result
        extra_updates: dict = {
            "generation_status": "completed",
            "generation_completed_at": _now_iso(),
            "blob_url": blob_url,
            "blob_name": blob_info["blob_name"],
            "file_size_bytes": blob_info["file_size_bytes"],
            "fal_url": asset_url,
            "media_review_status": "pending",
            "approval_status": "pending",
        }

        if media_type == "image" and "images" in result:
            img = result["images"][0]
            extra_updates["width"] = img.get("width")
            extra_updates["height"] = img.get("height")
            extra_updates["description"] = result.get("description", "")

        await update_content(content_id, extra_updates)

        # Agent gate #2: auto-review generated media before any human approval step
        try:
            from agents.content_reviewer.tools import review_generated_media

            review_result = await review_generated_media(content_id)
            verdict = str(review_result.get("verdict", "")).upper().strip()
            text_safety = review_result.get("content_safety") or review_result.get("text_content_safety") or {}
            safe_from_content_safety = bool(text_safety.get("safe", False)) if isinstance(text_safety, dict) else False

            should_block = False
            if verdict:
                should_block = verdict != "APPROVED"
            else:
                should_block = not safe_from_content_safety

            if should_block:
                logger.warning(
                    "[gen-worker] Media review blocked content %s (verdict=%s): %s",
                    content_id,
                    verdict or "N/A",
                    review_result.get("summary", ""),
                )
                return
        except Exception as exc:
            logger.error(
                "[gen-worker] Media review step failed for %s: %s",
                content_id,
                exc,
            )
            return

        # Enqueue for human gate #3 (posting approval)
        try:
            await send_message_to_review_pending_queue(
                content_id=content_id,
                media_type=media_type,
                account=record.get("account", ""),
                subject=record.get("description") or "Instagram Post",
                message_id=f"{content_id}-review",
            )
            await update_content(content_id, {"approval_status": "pending"})
            logger.info(
                "[gen-worker] Enqueued %s for human posting approval → review-pending queue",
                content_id,
            )
        except Exception as exc:
            logger.error(
                "[gen-worker] Completed %s but failed to enqueue for review: %s",
                content_id, exc,
            )

        logger.info(
            "[gen-worker] Completed %s generation content_id=%s → %s",
            media_type, content_id, blob_url,
        )


# ---------------------------------------------------------------------------
# Background thread launcher (same pattern as communicator/publisher)
# ---------------------------------------------------------------------------

_worker_started = False
_worker_lock = threading.Lock()


def start_media_generation_worker(poll_interval_seconds: int = 15) -> None:
    """Start the media generation worker in a background thread."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    worker = MediaGenerationWorker(poll_interval_seconds=poll_interval_seconds)

    async def _run() -> None:
        await asyncio.gather(
            worker._listen_queue(),
            worker._poll_progress(),
        )

    def _runner() -> None:
        asyncio.run(_run())

    thread = threading.Thread(
        target=_runner, name="media-generation-worker", daemon=True,
    )
    thread.start()
    logger.info("[gen-worker] Media generation background worker started")
