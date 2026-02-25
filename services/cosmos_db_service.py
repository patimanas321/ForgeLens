"""Azure Cosmos DB (NoSQL) service — persist media metadata.

Uses DefaultAzureCredential (passwordless auth) per Cosmos DB best practices.
The database and container are auto-created on first use.

Partition key: /media_type  (high cardinality: "image", "video")
Each document stores the blob URL, generation metadata, and timestamps.
"""

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-local client cache.
# Background worker threads each run their own asyncio.run() loop, while the
# main DevServer uses the uvicorn event loop.  An aiohttp-backed async client
# created on one loop cannot be reused on another.  threading.local() gives
# each thread its own client instance automatically.
# ---------------------------------------------------------------------------
_local = threading.local()


async def _get_container():
    """Return (or lazily create) the Cosmos container client for the *current* thread."""
    client: CosmosClient | None = getattr(_local, "cosmos_client", None)

    if client is None:
        credential = DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID)
        client = CosmosClient(
            url=settings.COSMOS_ENDPOINT,
            credential=credential,
        )
        _local.cosmos_client = client
        _local.cosmos_credential = credential

    db = client.get_database_client(settings.COSMOS_DATABASE)
    container = db.get_container_client(settings.COSMOS_CONTAINER)
    return container


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def save_media_metadata(
    *,
    media_type: str,
    blob_url: str,
    blob_name: str,
    prompt: str,
    model: str,
    aspect_ratio: str = "",
    resolution: str = "",
    width: int | None = None,
    height: int | None = None,
    duration_seconds: int | None = None,
    file_size_bytes: int | None = None,
    source_media_url: str = "",
    post_type: str = "post",
    target_account_id: str = "",
    target_account_name: str = "",
    description: str = "",
    caption: str = "",
    hashtags: list[str] | None = None,
    publish_status: str = "pending",
    extra: dict[str, Any] | None = None,
) -> dict:
    """Persist a media metadata document in Cosmos DB.

    Args:
        media_type: ``"image"`` or ``"video"`` (partition key).
        blob_url: Public Azure Blob Storage URL.
        blob_name: Blob name inside the container.
        prompt: Original generation prompt.
        model: Model ID that produced the media (e.g. ``fal-ai/nano-banana-pro``).
        aspect_ratio: e.g. ``"1:1"``, ``"9:16"``.
        resolution: e.g. ``"1K"``, ``"720p"``.
        width / height: Pixel dimensions (if known).
        duration_seconds: Video duration (images = ``None``).
        file_size_bytes: File size on disk.
        source_media_url: Original provider media URL (before blob upload).
        extra: Any additional metadata to store.

    Returns:
        The full Cosmos document as a dict (includes ``id``).
    """
    container = await _get_container()

    doc = {
        "id": uuid.uuid4().hex,
        "media_type": media_type,
        "post_type": post_type,
        "blob_url": blob_url,
        "blob_name": blob_name,
        "prompt": prompt,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "width": width,
        "height": height,
        "duration_seconds": duration_seconds,
        "file_size_bytes": file_size_bytes,
        "source_media_url": source_media_url,
        "target_account_id": target_account_id,
        "target_account_name": target_account_name,
        "description": description,
        "caption": caption,
        "hashtags": hashtags or [],
        "media_review_status": "pending",
        "approval_status": "pending",
        "media_reviewed_at": None,
        "media_review_score": None,
        "media_reviewer_notes": "",
        "human_reviewed_at": None,
        "human_reviewer_notes": "",
        "publish_status": publish_status,
        "instagram_media_id": "",
        "instagram_container_id": "",
        "published_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }

    # Backward compatibility for existing readers/records that still expect fal_url
    if "fal_url" not in doc:
        doc["fal_url"] = source_media_url

    created = await container.create_item(body=doc)
    logger.info(f"[cosmos] Saved metadata id={created['id']} type={media_type} blob={blob_url}")
    return created


async def get_media_by_id(item_id: str, media_type: str) -> dict | None:
    """Read a single media document by ``id`` + partition key."""
    container = await _get_container()
    try:
        return await container.read_item(item=item_id, partition_key=media_type)
    except Exception:
        return None


async def get_content_by_id(content_id: str) -> dict | None:
    """Read a single content document by ID (cross-partition query)."""
    container = await _get_container()
    query = "SELECT * FROM c WHERE c.id = @id OFFSET 0 LIMIT 1"
    params = [{"name": "@id", "value": content_id}]

    async for item in container.query_items(
        query=query,
        parameters=params,
        max_item_count=1,
    ):
        return item
    return None


async def update_content(content_id: str, updates: dict[str, Any]) -> dict | None:
    """Patch a content document by ID and return the updated document."""
    container = await _get_container()
    item = await get_content_by_id(content_id)
    if not item:
        return None

    item.update(updates)
    updated = await container.replace_item(item=item["id"], body=item)
    return updated


async def delete_media_metadata(content_id: str, media_type: str) -> bool:
    """Delete a media metadata document by id + partition key.

    Returns True if deleted, False if not found.
    """
    container = await _get_container()
    try:
        await container.delete_item(item=content_id, partition_key=media_type)
        logger.info("[cosmos] Deleted metadata id=%s", content_id)
        return True
    except Exception:
        logger.warning("[cosmos] Could not delete id=%s (not found?)", content_id)
        return False


async def set_media_review_status(
    content_id: str,
    status: str,
    reviewer_notes: str = "",
    review_score: int | None = None,
) -> dict | None:
    """Update generated media review status (agent gate #2)."""
    return await update_content(
        content_id,
        {
            "media_review_status": status,
            "media_reviewed_at": datetime.now(timezone.utc).isoformat(),
            "media_review_score": review_score,
            "media_reviewer_notes": reviewer_notes,
        },
    )


async def set_approval_status(
    content_id: str,
    status: str,
    reviewer_notes: str = "",
) -> dict | None:
    """Update human posting approval status (gate #3)."""
    return await update_content(
        content_id,
        {
            "approval_status": status,
            "human_reviewed_at": datetime.now(timezone.utc).isoformat(),
            "human_reviewer_notes": reviewer_notes,
        },
    )


async def mark_content_published(
    content_id: str,
    instagram_media_id: str,
    instagram_container_id: str = "",
) -> dict | None:
    """Mark a content document as published and store Instagram IDs."""
    return await update_content(
        content_id,
        {
            "publish_status": "published",
            "instagram_media_id": instagram_media_id,
            "instagram_container_id": instagram_container_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def query_media(
    media_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query recent media metadata, optionally filtered by type.

    Args:
        media_type: ``"image"`` or ``"video"`` to filter; ``None`` for all.
        limit: Maximum documents to return (default 50).
    """
    container = await _get_container()

    if media_type:
        query = (
            "SELECT * FROM c WHERE c.media_type = @type "
            "ORDER BY c.created_at DESC OFFSET 0 LIMIT @limit"
        )
        params = [
            {"name": "@type", "value": media_type},
            {"name": "@limit", "value": limit},
        ]
        partition_key = media_type
    else:
        query = (
            "SELECT * FROM c ORDER BY c.created_at DESC OFFSET 0 LIMIT @limit"
        )
        params = [{"name": "@limit", "value": limit}]
        partition_key = None

    items = []
    async for item in container.query_items(
        query=query,
        parameters=params,
        partition_key=partition_key,
        max_item_count=limit,
    ):
        items.append(item)
    return items


async def query_content(
    *,
    media_review_status: str | None = None,
    approval_status: str | None = None,
    publish_status: str | None = None,
    target_account_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query content records by lifecycle status fields."""
    container = await _get_container()

    filters = []
    params: list[dict[str, Any]] = [{"name": "@limit", "value": limit}]

    if media_review_status:
        filters.append("c.media_review_status = @media_review_status")
        params.append({"name": "@media_review_status", "value": media_review_status})
    if approval_status:
        filters.append("c.approval_status = @approval_status")
        params.append({"name": "@approval_status", "value": approval_status})
    if publish_status:
        filters.append("c.publish_status = @publish_status")
        params.append({"name": "@publish_status", "value": publish_status})
    if target_account_id:
        filters.append("c.target_account_id = @target_account_id")
        params.append({"name": "@target_account_id", "value": target_account_id})

    where_clause = ""
    if filters:
        where_clause = " WHERE " + " AND ".join(filters)

    query = (
        "SELECT * FROM c"
        f"{where_clause} "
        "ORDER BY c.created_at DESC OFFSET 0 LIMIT @limit"
    )

    items: list[dict] = []
    async for item in container.query_items(
        query=query,
        parameters=params,
        max_item_count=limit,
    ):
        items.append(item)
    return items
