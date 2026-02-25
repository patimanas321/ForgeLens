"""Azure Service Bus helper service.

Centralizes async Service Bus client creation and queue message publishing.
Uses thread-local client caching so each thread/event loop gets its own
`ServiceBusClient`, mirroring the Cosmos DB pattern in this codebase.
"""

from __future__ import annotations

import json
import threading

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver

from config.settings import settings

_local = threading.local()

QUEUE_MEDIA_GENERATION = "media-generation"
QUEUE_REVIEW_PENDING = "review-pending"
QUEUE_REVIEW_APPROVED = "review-approved"


def _get_or_create_client() -> ServiceBusClient:
    client: ServiceBusClient | None = getattr(_local, "servicebus_client", None)
    if client is None:
        credential = DefaultAzureCredential(
            managed_identity_client_id=settings.AZURE_CLIENT_ID
        )
        client = ServiceBusClient(
            fully_qualified_namespace=settings.SERVICEBUS_NAMESPACE,
            credential=credential,
        )
        _local.servicebus_client = client
        _local.servicebus_credential = credential
    return client


async def send_json_message(
    *,
    queue_name: str,
    payload: dict,
    application_properties: dict | None = None,
    subject: str = "",
    message_id: str | None = None,
) -> None:
    """Send a JSON message to a Service Bus queue."""
    client = _get_or_create_client()
    sender = client.get_queue_sender(queue_name)
    async with sender:
        msg = ServiceBusMessage(
            body=json.dumps(payload),
            application_properties=application_properties or {},
            subject=subject,
            message_id=message_id,
        )
        await sender.send_messages(msg)


def get_media_generation_queue_receiver(max_wait_time: int = 5) -> ServiceBusReceiver:
    """Create a receiver bound to the media-generation queue."""
    client = _get_or_create_client()
    return client.get_queue_receiver(QUEUE_MEDIA_GENERATION, max_wait_time=max_wait_time)


def get_review_pending_queue_receiver(max_wait_time: int = 5) -> ServiceBusReceiver:
    """Create a receiver bound to the review-pending queue."""
    client = _get_or_create_client()
    return client.get_queue_receiver(QUEUE_REVIEW_PENDING, max_wait_time=max_wait_time)


def get_review_approved_queue_receiver(max_wait_time: int = 5) -> ServiceBusReceiver:
    """Create a receiver bound to the review-approved queue."""
    client = _get_or_create_client()
    return client.get_queue_receiver(QUEUE_REVIEW_APPROVED, max_wait_time=max_wait_time)


async def receive_messages_from_media_generation_queue(
    receiver: ServiceBusReceiver,
    max_message_count: int = 10,
    max_wait_time: int = 5,
):
    """Receive messages from media-generation queue using the provided receiver."""
    return await receiver.receive_messages(
        max_message_count=max_message_count,
        max_wait_time=max_wait_time,
    )


async def receive_messages_from_review_pending_queue(
    receiver: ServiceBusReceiver,
    max_message_count: int = 10,
    max_wait_time: int = 5,
):
    """Receive messages from review-pending queue using the provided receiver."""
    return await receiver.receive_messages(
        max_message_count=max_message_count,
        max_wait_time=max_wait_time,
    )


async def receive_messages_from_review_approved_queue(
    receiver: ServiceBusReceiver,
    max_message_count: int = 5,
    max_wait_time: int = 5,
):
    """Receive messages from review-approved queue using the provided receiver."""
    return await receiver.receive_messages(
        max_message_count=max_message_count,
        max_wait_time=max_wait_time,
    )


async def send_message_to_media_generation_queue(
    *,
    content_id: str,
    media_type: str,
    account: str = "",
    subject: str = "Media Generation",
    message_id: str | None = None,
) -> None:
    """Send a content generation message to media-generation queue."""
    await send_json_message(
        queue_name=QUEUE_MEDIA_GENERATION,
        payload={"content_id": content_id},
        application_properties={
            "content_id": content_id,
            "media_type": media_type,
            "account": account,
        },
        subject=subject,
        message_id=message_id or content_id,
    )


async def send_message_to_review_pending_queue(
    *,
    content_id: str,
    media_type: str,
    account: str = "",
    subject: str = "Instagram Post",
    message_id: str | None = None,
) -> None:
    """Send a content review request message to review-pending queue."""
    await send_json_message(
        queue_name=QUEUE_REVIEW_PENDING,
        payload={"content_id": content_id},
        application_properties={
            "content_id": content_id,
            "media_type": media_type,
            "account": account,
        },
        subject=subject,
        message_id=message_id or f"{content_id}-review",
    )


async def send_message_to_review_approved_queue(
    *,
    item_id: str,
    account: str = "",
    content_type: str = "image",
    subject: str = "Instagram Post",
    message_id: str | None = None,
) -> None:
    """Send an approval-forward message to review-approved queue."""
    await send_json_message(
        queue_name=QUEUE_REVIEW_APPROVED,
        payload={"content_id": item_id},
        application_properties={
            "item_id": item_id,
            "account": account,
            "content_type": content_type,
        },
        subject=subject,
        message_id=message_id or f"{item_id}-approved",
    )
