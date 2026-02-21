"""Azure Cosmos DB (NoSQL) service — persist media metadata.

Uses DefaultAzureCredential (passwordless auth) per Cosmos DB best practices.
The database and container are auto-created on first use.

Partition key: /media_type  (high cardinality: "image", "video")
Each document stores the blob URL, generation metadata, and timestamps.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

from shared.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton client (reuse across calls — Cosmos DB best practice)
# ---------------------------------------------------------------------------
_client: CosmosClient | None = None
_credential: DefaultAzureCredential | None = None


async def _get_container():
    """Return (or lazily create) the Cosmos container client."""
    global _client, _credential

    if _client is None:
        _credential = DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID)
        _client = CosmosClient(
            url=settings.COSMOS_ENDPOINT,
            credential=_credential,
        )

    db = _client.get_database_client(settings.COSMOS_DATABASE)
    container = db.get_container_client(settings.COSMOS_CONTAINER)
    return container


async def ensure_cosmos_resources() -> None:
    """Verify (or create) the Cosmos DB database and container.

    Call once at startup (e.g. from main.py).  If the database/container
    already exist (created via ARM / az CLI) this is a cheap no-op.
    If AAD data-plane RBAC isn't enabled for create operations the
    function catches the 403 and logs a warning instead of crashing.
    """
    global _client, _credential

    if _client is None:
        _credential = DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID)
        _client = CosmosClient(
            url=settings.COSMOS_ENDPOINT,
            credential=_credential,
        )

    try:
        # Try create — works when data-plane RBAC is fully enabled
        db = await _client.create_database_if_not_exists(id=settings.COSMOS_DATABASE)
        await db.create_container_if_not_exists(
            id=settings.COSMOS_CONTAINER,
            partition_key=PartitionKey(path="/media_type"),
        )
        logger.info(
            f"[cosmos] Ensured database='{settings.COSMOS_DATABASE}' "
            f"container='{settings.COSMOS_CONTAINER}'"
        )
    except Exception as e:
        # 403 = AAD token can't create resources on data plane.
        # The db/container were likely pre-created via ARM (az CLI).
        # Verify we can at least read the container.
        try:
            db = _client.get_database_client(settings.COSMOS_DATABASE)
            container = db.get_container_client(settings.COSMOS_CONTAINER)
            await container.read()
            logger.info(
                f"[cosmos] Database/container exist (pre-created via ARM). "
                f"Data-plane create blocked: {e}"
            )
        except Exception as verify_err:
            logger.error(
                f"[cosmos] Cannot reach database/container: {verify_err}. "
                f"Media metadata will NOT be persisted."
            )


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
    fal_url: str = "",
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
        fal_url: Original fal.ai CDN URL (before blob upload).
        extra: Any additional metadata to store.

    Returns:
        The full Cosmos document as a dict (includes ``id``).
    """
    container = await _get_container()

    doc = {
        "id": uuid.uuid4().hex,
        "media_type": media_type,
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
        "fal_url": fal_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }

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
