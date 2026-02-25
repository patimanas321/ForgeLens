"""Service Bus queue interface for the media-generation queue.

The account agent enqueues generation requests here (DB record ID as payload).
The MediaGenerationWorker listens and processes them.
"""

import json
import logging
from datetime import datetime, timezone

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient

from config.settings import settings
from services.media_metadata_service import delete_media_metadata, save_media_metadata

logger = logging.getLogger(__name__)

QUEUE_GENERATION = "media-generation"


class GenerationQueueService:
    """Enqueue media-generation requests into Service Bus."""

    _credential: DefaultAzureCredential | None = None
    _client_instance: ServiceBusClient | None = None

    def __init__(self, account_name: str = "") -> None:
        self._account = account_name

    @classmethod
    def _get_client(cls) -> ServiceBusClient:
        if cls._client_instance is None:
            cls._credential = DefaultAzureCredential(
                managed_identity_client_id=settings.AZURE_CLIENT_ID
            )
            cls._client_instance = ServiceBusClient(
                fully_qualified_namespace=settings.SERVICEBUS_NAMESPACE,
                credential=cls._credential,
            )
        return cls._client_instance

    async def create_content_record(
        self,
        *,
        media_type: str,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        output_format: str = "png",
        duration: int = 5,
        video_model: str = "",
        post_type: str = "post",
        target_account_id: str = "",
        target_account_name: str = "",
        topic: str = "",
        caption: str = "",
        hashtags: list[str] | None = None,
    ) -> dict:
        """Create a DB record for a content plan WITHOUT queuing for generation.

        The record is saved with ``generation_status='pending_review'`` so the
        Content Reviewer agent can inspect it before generation begins.
        Call :meth:`submit_to_queue` after the reviewer approves.

        Returns the DB document with ``id`` (content_id).
        """
        model = (
            settings.FAL_VIDEO_MODEL if media_type == "video" else settings.FAL_IMAGE_MODEL
        )

        doc = await save_media_metadata(
            media_type=media_type,
            blob_url="",
            blob_name="",
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution="" if media_type == "video" else resolution,
            duration_seconds=duration if media_type == "video" else None,
            fal_url="",
            post_type=post_type,
            target_account_id=target_account_id,
            target_account_name=target_account_name,
            description=topic,
            caption=caption,
            hashtags=hashtags,
            approval_status="pending_review",
            publish_status="pending",
            extra={
                "generation_status": "pending_review",
                "output_format": output_format,
                "video_model": video_model,
                "account": self._account,
                "source": "account_agent",
            },
        )

        logger.info(
            "[generation-queue] Saved content plan %s (account=%s, type=%s) — pending review",
            doc["id"], self._account, media_type,
        )
        return doc

    async def submit_to_queue(self, content_id: str, media_type: str) -> None:
        """Send a generation request to Service Bus for an existing DB record.

        Called after the Content Reviewer approves the content plan.
        """
        from services.media_metadata_service import update_content

        # Mark as queued in DB
        await update_content(content_id, {
            "generation_status": "queued",
            "approval_status": "approved_by_reviewer",
            "generation_requested_at": datetime.now(timezone.utc).isoformat(),
        })

        try:
            client = self._get_client()
            sender = client.get_queue_sender(QUEUE_GENERATION)
            async with sender:
                msg = ServiceBusMessage(
                    body=json.dumps({"content_id": content_id}),
                    application_properties={
                        "content_id": content_id,
                        "media_type": media_type,
                        "account": self._account,
                    },
                    subject="Media Generation",
                    message_id=content_id,
                )
                await sender.send_messages(msg)
        except Exception as exc:
            # Revert status so it can be retried
            await update_content(content_id, {"generation_status": "pending_review"})
            logger.error(
                "[generation-queue] Service Bus send failed for %s: %s", content_id, exc,
            )
            raise

        logger.info(
            "[generation-queue] Enqueued %s generation %s (account=%s)",
            media_type, content_id, self._account,
        )

    async def submit_generation(
        self,
        *,
        media_type: str,
        prompt: str,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        output_format: str = "png",
        duration: int = 5,
        video_model: str = "",
        post_type: str = "post",
        target_account_id: str = "",
        target_account_name: str = "",
        topic: str = "",
        caption: str = "",
        hashtags: list[str] | None = None,
    ) -> dict:
        """Create a DB record and enqueue a generation request.

        Returns the DB document with ``id`` (content_id) so the agent can
        hand it back to the user immediately.
        """
        model = (
            settings.FAL_VIDEO_MODEL if media_type == "video" else settings.FAL_IMAGE_MODEL
        )

        doc = await save_media_metadata(
            media_type=media_type,
            blob_url="",
            blob_name="",
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution="" if media_type == "video" else resolution,
            duration_seconds=duration if media_type == "video" else None,
            fal_url="",
            post_type=post_type,
            target_account_id=target_account_id,
            target_account_name=target_account_name,
            description=topic,
            caption=caption,
            hashtags=hashtags,
            approval_status="pending",
            publish_status="pending",
            extra={
                "generation_status": "queued",
                "generation_requested_at": datetime.now(timezone.utc).isoformat(),
                "output_format": output_format,
                "video_model": video_model,
                "account": self._account,
                "source": "account_agent",
            },
        )

        content_id = doc["id"]

        # Send message to Service Bus — roll back DB record on failure
        try:
            client = self._get_client()
            sender = client.get_queue_sender(QUEUE_GENERATION)
            async with sender:
                msg = ServiceBusMessage(
                    body=json.dumps({"content_id": content_id}),
                    application_properties={
                        "content_id": content_id,
                        "media_type": media_type,
                        "account": self._account,
                    },
                    subject=topic or "Media Generation",
                    message_id=content_id,
                )
                await sender.send_messages(msg)
        except Exception as exc:
            # Clean up the orphaned DB record so retries don't pile up
            logger.error(
                "[generation-queue] Service Bus send failed for %s — deleting DB record: %s",
                content_id, exc,
            )
            try:
                await delete_media_metadata(content_id, media_type)
            except Exception:
                logger.warning("[generation-queue] Could not delete orphaned record %s", content_id)
            raise

        logger.info(
            "[generation-queue] Enqueued %s generation %s (account=%s)",
            media_type, content_id, self._account,
        )
        return doc
