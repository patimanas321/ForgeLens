"""
Tools for the Approver agent — human-in-the-loop approval management.
"""

import logging
from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.review_queue_service import ReviewQueueService
from shared.services.media_metadata_service import query_content

logger = logging.getLogger(__name__)

_queue_service = ReviewQueueService()


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class ViewDetailsInput(BaseModel):
    item_id: str = Field(..., description="The ID of the review item to check.")


class ViewAllPendingInput(BaseModel):
    pass  # No parameters needed


class ViewApprovalHistoryInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class ApproveItemInput(BaseModel):
    item_id: str = Field(..., description="The ID of the item to approve.")
    notes: str = Field(default="", description="Optional reviewer notes.")


class RejectItemInput(BaseModel):
    item_id: str = Field(..., description="The ID of the item to reject.")
    notes: str = Field(default="", description="Optional rejection reason.")


class RequestEditsInput(BaseModel):
    item_id: str = Field(..., description="The ID of the item requiring edits.")
    notes: str = Field(..., description="Required edit instructions for revision.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def view_all_pending() -> list[dict]:
    """View all items currently awaiting human review."""
    return await _queue_service.get_pending_reviews()


async def view_details(item_id: str) -> dict:
    """View approval details/status of a specific item."""
    return await _queue_service.get_review_status(item_id)


async def view_approval_history(limit: int = 50) -> dict:
    """View reviewed approval history (approved/rejected/edit_requested)."""
    items = await query_content(limit=limit)
    reviewed = [
        item for item in items
        if item.get("approval_status") in {"approved", "rejected", "edit_requested"}
    ]
    reviewed.sort(key=lambda x: x.get("reviewed_at") or x.get("created_at") or "", reverse=True)
    return {"count": len(reviewed), "items": reviewed}


async def approve_item(item_id: str, notes: str = "") -> dict:
    """Approve a pending item and move it to approved queue."""
    return await _queue_service.approve_item(item_id, notes)


async def reject_item(item_id: str, notes: str = "") -> dict:
    """Reject a pending item."""
    return await _queue_service.reject_item(item_id, notes)


async def request_edits(item_id: str, notes: str) -> dict:
    """Request edits for a pending item."""
    return await _queue_service.request_edits(item_id, notes)


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_review_queue_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="approve",
            description=(
                "Approve a pending content item and move it to the approved queue."
            ),
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
            description="View detailed approval status for a specific item ID.",
            input_model=ViewDetailsInput,
            func=view_details,
        ),
        FunctionTool(
            name="view_all_pending",
            description="View all pending items awaiting review.",
            input_model=ViewAllPendingInput,
            func=view_all_pending,
        ),
        FunctionTool(
            name="view_approval_history",
            description="View approval history across approved/rejected/edit-requested items.",
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
