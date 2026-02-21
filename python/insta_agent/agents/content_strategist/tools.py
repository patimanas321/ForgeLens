"""
Tools for the Content Strategist agent — posting history and content calendar.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agent_framework import FunctionTool
from pydantic import BaseModel, Field

from shared.services.instagram_service import InstagramService

logger = logging.getLogger(__name__)

_ig_service = InstagramService()

CALENDAR_DIR = Path(__file__).parent.parent.parent / "data" / "content_calendar"
CALENDAR_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class PostingHistoryInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=50, description="Number of recent posts to fetch.")


class SaveContentPlanInput(BaseModel):
    topic: str = Field(..., description="The selected topic for today's content.")
    format: str = Field(..., description="Content format: 'image', 'carousel', 'reel', or 'story'.")
    visual_direction: str = Field(..., description="Description of the visual style and elements.")
    caption_direction: str = Field(..., description="Tone, hook idea, and CTA guidance for the copywriter.")
    hashtag_themes: str = Field(default="", description="Themes for hashtag research.")
    reasoning: str = Field(default="", description="Why this topic was selected over alternatives.")


class GetCalendarInput(BaseModel):
    days: int = Field(default=7, ge=1, le=30, description="Number of past days to show.")


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
        # Fall back to local calendar
        return await get_content_calendar(days=14)


async def save_content_plan(
    topic: str,
    format: str,
    visual_direction: str,
    caption_direction: str,
    hashtag_themes: str = "",
    reasoning: str = "",
) -> dict:
    """Save today's content plan to the local calendar."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plan = {
        "date": today,
        "topic": topic,
        "format": format,
        "visual_direction": visual_direction,
        "caption_direction": caption_direction,
        "hashtag_themes": hashtag_themes,
        "reasoning": reasoning,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = CALENDAR_DIR / f"{today}.json"
    path.write_text(json.dumps(plan, indent=2))
    logger.info(f"[OK] Saved content plan for {today}: {topic}")
    return plan


async def get_content_calendar(days: int = 7) -> list[dict]:
    """Read the content calendar for the last N days."""
    plans = []
    for path in sorted(CALENDAR_DIR.glob("*.json"), reverse=True)[:days]:
        plans.append(json.loads(path.read_text()))
    return plans


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
        FunctionTool(
            name="save_content_plan",
            description="Save the selected content plan (topic, format, visual direction) to the calendar.",
            input_model=SaveContentPlanInput,
            func=save_content_plan,
        ),
        FunctionTool(
            name="get_content_calendar",
            description="View the content plan for recent days. Use to check what's been planned or posted.",
            input_model=GetCalendarInput,
            func=get_content_calendar,
        ),
    ]
