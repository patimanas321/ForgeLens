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
    INSTA_ACCOUNT = "insta-account"
    TREND_SCOUT = "trend-scout"
    REVIEW_QUEUE = "review-queue"
    CONTENT_REVIEWER = "content-reviewer"
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

    # ---- Instagram Account Agent (per-profile, template entry) ----
    Agent.INSTA_ACCOUNT: AgentEntry(
        name="Instagram Account",
        description=(
            "Per-profile Instagram account agent. Manages content creation, "
            "trend discovery, media generation, and review workflow for a "
            "single Instagram persona."
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

    # ---- Content Reviewer ----
    Agent.CONTENT_REVIEWER: AgentEntry(
        name="Content Reviewer",
        description=(
            "Safety and quality gate for all content. Reviews text plans "
            "(prompts, captions, hashtags) before generation, and reviews "
            "generated images/videos after generation. Uses Azure Content "
            "Safety for hard moderation and LLM vision for nuanced review."
        ),
        tool_name="call_content_reviewer",
        arg_description=(
            "A review request — e.g. 'Review content plan <content_id>', "
            "'Review generated image <content_id>', 'Check this caption for safety'."
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
