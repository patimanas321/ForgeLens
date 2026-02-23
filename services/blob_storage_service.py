"""Azure Blob Storage service — upload media files and return public URLs.

Auth priority:
  1. Connection string (AZURE_STORAGE_CONNECTION_STRING) — if set
  2. DefaultAzureCredential (passwordless) via account URL — preferred for Azure

Container is auto-created on first use.
"""

import logging
import mimetypes
import threading
from pathlib import Path

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-local client cache (same rationale as media_metadata_service).
# ---------------------------------------------------------------------------
_local = threading.local()


async def _get_async_client() -> AsyncBlobServiceClient:
    client: AsyncBlobServiceClient | None = getattr(_local, "blob_client", None)
    if client is None:
        if settings.AZURE_STORAGE_CONNECTION_STRING:
            client = AsyncBlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING,
            )
        else:
            client = AsyncBlobServiceClient(
                account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
                credential=DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID),
            )
        _local.blob_client = client
    return client


def _content_type(file_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(file_path))
    return mime or "application/octet-stream"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def upload_blob(local_path: str | Path, blob_name: str | None = None) -> dict:
    """Upload a local file to Azure Blob Storage.

    Args:
        local_path: Path to the local file.
        blob_name: Optional custom blob name. Defaults to the file name.

    Returns:
        dict with ``blob_url``, ``blob_name``, ``container``, ``content_type``,
        ``file_size_bytes``.
    """
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {local_path}")

    blob_name = blob_name or path.name
    content_type = _content_type(path)
    container = settings.AZURE_STORAGE_CONTAINER_NAME

    client = await _get_async_client()

    # Ensure container exists
    container_client = client.get_container_client(container)
    try:
        await container_client.get_container_properties()
    except Exception:
        await container_client.create_container(public_access="blob")
        logger.info(f"[blob] Created container '{container}'")

    blob_client = container_client.get_blob_client(blob_name)

    with open(path, "rb") as data:
        await blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    blob_url = blob_client.url
    file_size = path.stat().st_size

    logger.info(f"[blob] Uploaded {blob_name} ({file_size} bytes) → {blob_url}")

    return {
        "blob_url": blob_url,
        "blob_name": blob_name,
        "container": container,
        "content_type": content_type,
        "file_size_bytes": file_size,
    }
