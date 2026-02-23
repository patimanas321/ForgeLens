"""
Tools for the Approver agent — human-in-the-loop approval management.

All reads come directly from Cosmos DB (not Service Bus queues).
On approve, a message is forwarded to the review-approved Service Bus queue
so the Publisher worker can pick it up.
"""

import json
import logging
from datetime import datetime, timezone

from agent_framework import FunctionTool
from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from pydantic import BaseModel, Field

from config.settings import settings
from services.media_metadata_service import (
    get_content_by_id,
    query_content,
    set_approval_status,
)

logger = logging.getLogger(__name__)

QUEUE_APPROVED = "review-approved"

# Singleton Service Bus client (only used for approve → publish forwarding)
_sb_client: ServiceBusClient | None = None
_sb_credential: DefaultAzureCredential | None = None


async def _get_sb_client() -> ServiceBusClient:
    global _sb_client, _sb_credential
    if _sb_client is None:
        _sb_credential = DefaultAzureCredential(
            managed_identity_client_id=settings.AZURE_CLIENT_ID
        )
        _sb_client = ServiceBusClient(
            fully_qualified_namespace=settings.SERVICEBUS_NAMESPACE,
            credential=_sb_credential,
        )
    return _sb_client


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class ViewDetailsInput(BaseModel):
    item_id: str = Field(..., description="The content ID to inspect.")


class ViewAllPendingInput(BaseModel):
    pass


class ViewApprovalHistoryInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class ApproveItemInput(BaseModel):
    item_id: str = Field(..., description="The content ID to approve.")
    notes: str = Field(default="", description="Optional reviewer notes.")


class RejectItemInput(BaseModel):
    item_id: str = Field(..., description="The content ID to reject.")
    notes: str = Field(default="", description="Optional rejection reason.")


class RequestEditsInput(BaseModel):
    item_id: str = Field(..., description="The content ID requiring edits.")
    notes: str = Field(..., description="Required edit instructions.")


# ------------------------------------------------------------------
# Tool functions — all read from Cosmos DB
# ------------------------------------------------------------------

async def view_all_pending() -> dict:
    """List all content items with approval_status='pending'."""
    items = await query_content(approval_status="pending", limit=100)
    summary = []
    for item in items:
        summary.append({
            "id": item.get("id"),
            "media_type": item.get("media_type"),
            "post_type": item.get("post_type"),
            "topic": item.get("description", ""),
            "caption": (item.get("caption") or "")[:120],
            "account": item.get("account") or item.get("target_account_name", ""),
            "target_account_id": item.get("target_account_id", ""),
            "generation_status": item.get("generation_status", ""),
            "blob_url": item.get("blob_url", ""),
            "created_at": item.get("created_at"),
        })
    return {"count": len(summary), "items": summary}


async def view_details(item_id: str) -> dict:
    """View full details of a specific content item from the DB."""
    item = await get_content_by_id(item_id)
    if not item:
        return {"error": f"Item {item_id} not found in database."}
    return {k: v for k, v in item.items() if not k.startswith("_")}


async def view_approval_history(limit: int = 50) -> dict:
    """View reviewed items (approved / rejected / edit_requested)."""
    results = []
    for status in ("approved", "rejected", "edit_requested"):
        items = await query_content(approval_status=status, limit=limit)
        results.extend(items)
    results.sort(
        key=lambda x: x.get("reviewed_at") or x.get("created_at") or "",
        reverse=True,
    )
    results = results[:limit]
    summary = []
    for item in results:
        summary.append({
            "id": item.get("id"),
            "approval_status": item.get("approval_status"),
            "reviewed_at": item.get("reviewed_at"),
            "reviewer_notes": item.get("reviewer_notes", ""),
            "topic": item.get("description", ""),
            "account": item.get("account") or item.get("target_account_name", ""),
        })
    return {"count": len(summary), "items": summary}


async def approve_item(item_id: str, notes: str = "") -> dict:
    """Approve a pending item — updates DB and forwards to review-approved queue."""
    item = await get_content_by_id(item_id)
    if not item:
        return {"error": f"Item {item_id} not found in database."}
    if item.get("approval_status") != "pending":
        return {
            "error": f"Item {item_id} is not pending — current status: {item.get('approval_status')}"
        }

    updated = await set_approval_status(item_id, "approved", notes)
    if not updated:
        return {"error": f"Failed to update item {item_id}."}

    # Forward to review-approved Service Bus queue for publisher
    try:
        client = await _get_sb_client()
        sender = client.get_queue_sender(QUEUE_APPROVED)
        async with sender:
            msg = ServiceBusMessage(
                body=json.dumps({"content_id": item_id}),
                application_properties={
                    "item_id": item_id,
                    "account": item.get("account")
                    or item.get("target_account_name", ""),
                    "content_type": item.get("media_type", "image"),
                },
                subject=item.get("description") or "Instagram Post",
                message_id=f"{item_id}-approved",
            )
            await sender.send_messages(msg)
        logger.info(
            "[approver] Approved %s and forwarded to review-approved queue", item_id
        )
    except Exception as e:
        logger.error(
            "[approver] Approved %s in DB but Service Bus forward failed: %s",
            item_id,
            e,
        )

    return {
        "status": "approved",
        "item_id": item_id,
        "reviewer_notes": notes,
        "reviewed_at": updated.get("reviewed_at"),
    }


async def reject_item(item_id: str, notes: str = "") -> dict:
    """Reject a pending item."""
    item = await get_content_by_id(item_id)
    if not item:
        return {"error": f"Item {item_id} not found in database."}
    if item.get("approval_status") != "pending":
        return {
            "error": f"Item {item_id} is not pending — current status: {item.get('approval_status')}"
        }

    updated = await set_approval_status(item_id, "rejected", notes)
    if not updated:
        return {"error": f"Failed to update item {item_id}."}

    logger.info("[approver] Rejected %s", item_id)
    return {
        "status": "rejected",
        "item_id": item_id,
        "reviewer_notes": notes,
        "reviewed_at": updated.get("reviewed_at"),
    }


async def request_edits(item_id: str, notes: str) -> dict:
    """Request edits for a pending item."""
    item = await get_content_by_id(item_id)
    if not item:
        return {"error": f"Item {item_id} not found in database."}
    if item.get("approval_status") != "pending":
        return {
            "error": f"Item {item_id} is not pending — current status: {item.get('approval_status')}"
        }

    updated = await set_approval_status(item_id, "edit_requested", notes)
    if not updated:
        return {"error": f"Failed to update item {item_id}."}

    logger.info("[approver] Edit requested for %s", item_id)
    return {
        "status": "edit_requested",
        "item_id": item_id,
        "reviewer_notes": notes,
        "reviewed_at": updated.get("reviewed_at"),
    }


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_review_queue_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="approve",
            description="Approve a pending content item. Updates DB and forwards to publish queue.",
            input_model=ApproveItemInput,
            func=approve_item,
        ),
        FunctionTool(
            name="reject",
            description="Reject a pending content item.",
            input_model=RejectItemInput,
            func=reject_item,
        ),
        FunctionTool(
            name="view_details",
            description="View full details of a content item by its ID.",
            input_model=ViewDetailsInput,
            func=view_details,
        ),
        FunctionTool(
            name="view_all_pending",
            description="List all items awaiting review (approval_status='pending').",
            input_model=ViewAllPendingInput,
            func=view_all_pending,
        ),
        FunctionTool(
            name="view_approval_history",
            description="View approval history (approved / rejected / edit-requested items).",
            input_model=ViewApprovalHistoryInput,
            func=view_approval_history,
        ),
        FunctionTool(
            name="request_edits",
            description="Request edits for a pending item with reviewer notes.",
            input_model=RequestEditsInput,
            func=request_edits,
        ),
    ]
