"""
Tools for the Content Strategist agent — posting history.
"""

import logging

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.instagram_service import InstagramService

logger = logging.getLogger(__name__)

_ig_service = InstagramService()


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class PostingHistoryInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=50, description="Number of recent posts to fetch.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def get_posting_history(limit: int = 20) -> list[dict]:
    """Fetch recent Instagram posts to check what's been posted recently."""
    try:
        posts = await _ig_service.get_recent_media(limit=limit)
        return posts
    except Exception as e:
        logger.warning(f"Could not fetch Instagram history: {e}")
        return []


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_content_strategist_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="get_posting_history",
            description="Fetch recent Instagram posts to check what's been posted. Use BEFORE selecting a topic to avoid repetition.",
            input_model=PostingHistoryInput,
            func=get_posting_history,
        ),
    ]
