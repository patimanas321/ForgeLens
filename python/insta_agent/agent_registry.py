"""
Agent Registry — Single source of truth for all agent identities and routing metadata.

Every agent in the system is registered here. The orchestrator reads this to build
`as_tool()` wrappers, and each BaseAgent reads it for its own ChatAgent identity.
"""

from dataclasses import dataclass, field
from enum import Enum


class Agent(str, Enum):
    """Canonical agent identifiers — used as ChatAgent.id values."""
    ORCHESTRATOR = "orchestrator"
    TREND_SCOUT = "trend-scout"
    CONTENT_STRATEGIST = "content-strategist"
    INSTA_POST_GENERATOR = "insta-post-generator"
    REVIEW_QUEUE = "review-queue"
    PUBLISHER = "publisher"


@dataclass(frozen=True)
class AgentEntry:
    """Metadata for a single agent."""
    name: str
    description: str
    tool_name: str = ""
    arg_name: str = field(default="request")
    arg_description: str = ""


AGENT_REGISTRY: dict[Agent, AgentEntry] = {
    # ---- Orchestrator (no tool_name — it IS the top-level agent) ----
    Agent.ORCHESTRATOR: AgentEntry(
        name="Orchestrator",
        description=(
            "Main coordinator that runs the daily Instagram workflow: "
            "discover trends → plan content → generate media → write copy → "
            "queue for human review → publish upon approval → track analytics."
        ),
    ),

    # ---- Trend Scout ----
    Agent.TREND_SCOUT: AgentEntry(
        name="Trend Scout",
        description=(
            "Searches the web for viral trends, trending hashtags, competitor content, "
            "and emerging topics relevant to the Instagram account's niche."
        ),
        tool_name="call_trend_scout",
        arg_description=(
            "What to search for — e.g. 'trending topics in tech this week', "
            "'competitor analysis for @account', 'viral reels in fitness niche'."
        ),
    ),

    # ---- Content Strategist ----
    Agent.CONTENT_STRATEGIST: AgentEntry(
        name="Content Strategist",
        description=(
            "Plans the content calendar, selects the best topic from trends, "
            "avoids repetition by checking posting history, and decides the "
            "content format (image post, carousel, reel, story)."
        ),
        tool_name="call_content_strategist",
        arg_description=(
            "Trend data and context to plan content from — e.g. "
            "'Here are today's top 5 trends: ... Pick the best one for our "
            "fitness account and suggest a format.'"
        ),
    ),

    # ---- Insta Post Generator ----
    Agent.INSTA_POST_GENERATOR: AgentEntry(
        name="Insta Post Generator",
        description=(
            "Generates Instagram-ready media and copy assets. "
            "Creates images/videos, supports caption and hashtag tooling, "
            "and returns generated asset metadata."
        ),
        tool_name="call_insta_post_generator",
        arg_description=(
            "A detailed post brief describing what to generate or write — "
            "e.g. 'Generate a 9:16 reel about morning fitness and draft a caption.'"
        ),
    ),

    # ---- Approver (Human-in-the-Loop) ----
    Agent.REVIEW_QUEUE: AgentEntry(
        name="Approver",
        description=(
            "Manages approval decisions in the human-in-the-loop workflow. "
            "Reviews pending items, approves/rejects/requests edits, and "
            "provides approval visibility and history."
        ),
        tool_name="call_approver",
        arg_description=(
            "The approval action to perform — e.g. 'Approve item <id>', "
            "'Reject item <id>', 'Show pending items', 'View approval history'."
        ),
    ),

    # ---- Publisher ----
    Agent.PUBLISHER: AgentEntry(
        name="Publisher",
        description=(
            "Publishes approved content to Instagram by content ID only. "
            "Consumes approved queue items, verifies DB approval state, "
            "and records publish history in Cosmos DB."
        ),
        tool_name="call_publisher",
        arg_description=(
            "A publishing action such as: 'Publish content_id=<id>', "
            "'Publish next approved item', or 'Show pending-to-publish history'."
        ),
    ),
}
