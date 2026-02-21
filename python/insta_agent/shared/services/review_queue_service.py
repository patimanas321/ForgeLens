"""
Review Queue service — manages the human-in-the-loop approval workflow.

Uses a simple JSON-based local storage for the MVP.
Can be swapped for Azure Table Storage, CosmosDB, or PostgreSQL later.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

QUEUE_DIR = Path(__file__).parent.parent.parent / "data" / "review_queue"


class ReviewStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDIT_REQUESTED = "edit_requested"


class ReviewQueueService:
    """Simple file-based review queue for MVP."""

    def __init__(self) -> None:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    def _item_path(self, item_id: str) -> Path:
        return QUEUE_DIR / f"{item_id}.json"

    async def queue_for_review(
        self,
        *,
        media_url: str,
        caption: str,
        hashtags: str,
        content_type: str = "image",
        topic: str = "",
        trend_source: str = "",
    ) -> dict:
        """Add a new content item to the review queue."""
        item_id = str(uuid.uuid4())[:8]
        item = {
            "id": item_id,
            "status": ReviewStatus.PENDING,
            "media_url": media_url,
            "caption": caption,
            "hashtags": hashtags,
            "content_type": content_type,
            "topic": topic,
            "trend_source": trend_source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_at": None,
            "reviewer_notes": "",
        }
        self._item_path(item_id).write_text(json.dumps(item, indent=2))
        logger.info(f"[OK] Queued item {item_id} for review")
        return item

    async def get_pending_reviews(self) -> list[dict]:
        """Return all items awaiting human review."""
        items = []
        for path in QUEUE_DIR.glob("*.json"):
            item = json.loads(path.read_text())
            if item["status"] == ReviewStatus.PENDING:
                items.append(item)
        items.sort(key=lambda x: x["created_at"])
        return items

    async def get_review_status(self, item_id: str) -> dict:
        """Check the review status of a specific item."""
        path = self._item_path(item_id)
        if not path.exists():
            return {"error": f"Item {item_id} not found"}
        return json.loads(path.read_text())

    async def approve_item(self, item_id: str, notes: str = "") -> dict:
        """Mark an item as approved by the human reviewer."""
        return await self._update_status(item_id, ReviewStatus.APPROVED, notes)

    async def reject_item(self, item_id: str, notes: str = "") -> dict:
        """Reject an item with optional feedback."""
        return await self._update_status(item_id, ReviewStatus.REJECTED, notes)

    async def request_edits(self, item_id: str, notes: str) -> dict:
        """Request edits on an item — the agent will regenerate."""
        return await self._update_status(item_id, ReviewStatus.EDIT_REQUESTED, notes)

    async def get_approved_items(self) -> list[dict]:
        """Return all approved items that haven't been published yet."""
        items = []
        for path in QUEUE_DIR.glob("*.json"):
            item = json.loads(path.read_text())
            if item["status"] == ReviewStatus.APPROVED and not item.get("published_at"):
                items.append(item)
        return items

    async def mark_published(self, item_id: str, media_id: str) -> dict:
        """Mark an approved item as published."""
        path = self._item_path(item_id)
        if not path.exists():
            return {"error": f"Item {item_id} not found"}
        item = json.loads(path.read_text())
        item["published_at"] = datetime.now(timezone.utc).isoformat()
        item["instagram_media_id"] = media_id
        path.write_text(json.dumps(item, indent=2))
        return item

    async def _update_status(self, item_id: str, status: str, notes: str) -> dict:
        path = self._item_path(item_id)
        if not path.exists():
            return {"error": f"Item {item_id} not found"}
        item = json.loads(path.read_text())
        item["status"] = status
        item["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        item["reviewer_notes"] = notes
        path.write_text(json.dumps(item, indent=2))
        logger.info(f"[OK] Item {item_id} marked as {status}")
        return item
