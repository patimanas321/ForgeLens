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
from fal_client.client import AsyncClient as FalAsyncClient, Completed

from config.settings import settings
from services.azure_bus_service import (
    get_media_generation_queue_receiver,
    receive_messages_from_media_generation_queue,
    send_message_to_review_pending_queue,
)
from services.cosmos_db_service import (
    get_content_by_id,
    query_content,
    update_content,
)
from services.blob_storage_service import upload_blob

logger = logging.getLogger(__name__)

QUEUE_GENERATION = "media-generation"
QUEUE_REVIEW_PENDING = "review-pending"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_video_model(hint: str) -> str:
    if not hint:
        return settings.FAL_VIDEO_MODEL
    h = hint.strip().lower()
    if h == "kling":
        return settings.FAL_VIDEO_MODEL
    if h == "sora":
        return settings.FAL_VIDEO_MODEL_ALT
    if h.startswith("fal-ai/"):
        return h
    return settings.FAL_VIDEO_MODEL


async def _download(url: str, ext: str) -> Path:
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    path = Path(tempfile.gettempdir()) / name
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def _build_fal_arguments(record: dict) -> dict:
    """Build model-specific fal.ai arguments from the DB record."""
    media_type = record.get("media_type", "image")
    prompt = record["prompt"]
    aspect_ratio = record.get("aspect_ratio", "1:1")

    if media_type == "video":
        model_id = _resolve_video_model(record.get("video_model", ""))
        duration = record.get("duration_seconds") or 5
        is_sora = "sora" in model_id
        is_kling = "kling" in model_id

        if is_sora:
            sora_dur = min([d for d in [4, 8, 12] if d >= duration], default=12)
            sora_aspect = aspect_ratio if aspect_ratio in ("9:16", "16:9") else "9:16"
            return model_id, {
                "prompt": prompt,
                "duration": str(sora_dur),
                "aspect_ratio": sora_aspect,
                "resolution": "720p",
                "delete_video": False,
            }
        elif is_kling:
            kling_dur = max(3, min(duration, 15))
            kling_aspect = aspect_ratio if aspect_ratio in ("9:16", "16:9", "1:1") else "9:16"
            return model_id, {
                "prompt": prompt,
                "duration": str(kling_dur),
                "aspect_ratio": kling_aspect,
                "negative_prompt": "blur, distort, and low quality",
                "generate_audio": True,
            }
        else:
            return model_id, {
                "prompt": prompt,
                "duration": str(duration),
                "aspect_ratio": aspect_ratio,
            }
    else:
        model_id = record.get("model") or settings.FAL_IMAGE_MODEL
        return model_id, {
            "prompt": prompt,
            "num_images": 1,
            "aspect_ratio": aspect_ratio,
            "output_format": record.get("output_format", "png"),
            "resolution": record.get("resolution", "1K"),
            "safety_tolerance": "4",
        }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class MediaGenerationWorker:
    """Background worker: queue listener + progress poller."""

    def __init__(self, poll_interval_seconds: int = 15) -> None:
        self._poll_interval = poll_interval_seconds
        self._fal: FalAsyncClient | None = None

    def _get_fal(self) -> FalAsyncClient:
        if self._fal is None:
            self._fal = FalAsyncClient(key=settings.FAL_KEY)
        return self._fal

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
                        await self._submit_to_fal(content_id)
                        await receiver.complete_message(msg)
                    except Exception as exc:
                        logger.error(
                            "[gen-worker] Failed to process message: %s", exc
                        )
                        # Don't complete — let it retry
                if not messages:
                    await asyncio.sleep(2)

    async def _submit_to_fal(self, content_id: str) -> None:
        """Read DB record and submit an async request to fal.ai."""
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

        model_id, arguments = _build_fal_arguments(record)
        fal = self._get_fal()

        logger.info(
            "[gen-worker] Submitting %s generation to fal.ai model=%s content_id=%s",
            record.get("media_type", "image"), model_id, content_id,
        )

        handle = await fal.submit(model_id, arguments=arguments)

        await update_content(content_id, {
            "generation_status": "submitted",
            "fal_request_id": handle.request_id,
            "fal_model_id": model_id,
            "generation_submitted_at": _now_iso(),
        })

        logger.info(
            "[gen-worker] Submitted content_id=%s → fal request_id=%s",
            content_id, handle.request_id,
        )

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
        fal = self._get_fal()

        for item in items:
            content_id = item["id"]
            request_id = item.get("fal_request_id", "")
            model_id = item.get("fal_model_id", "")

            if not request_id or not model_id:
                logger.warning(
                    "[gen-worker] Content %s missing fal_request_id or fal_model_id",
                    content_id,
                )
                continue

            try:
                status = await fal.status(model_id, request_id)
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
    ) -> None:
        """Download result, upload to blob, update DB, enqueue for review."""
        fal = self._get_fal()
        result = await fal.result(model_id, request_id)

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
            verdict = str(review_result.get("verdict", "NEEDS_REVISION")).upper()
            if verdict != "APPROVED":
                logger.warning(
                    "[gen-worker] Media review blocked content %s (verdict=%s): %s",
                    content_id,
                    verdict,
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
