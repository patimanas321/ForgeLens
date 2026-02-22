"""
Content Pipeline — MAF sequential workflow with human-in-the-loop.

Chains specialist agents in order:
  Trend Scout → Content Strategist → Media Generator → Copywriter → [HIL] → Publisher

After the Copywriter finishes (media generated, caption written, hashtags done),
the workflow pauses for human review via `with_request_info()`.  The human can:
  • **Approve** — the Publisher will post to Instagram.
  • **Provide feedback** — the Copywriter re-runs with the revision notes.
"""

import logging

from agent_framework import SequentialBuilder, WorkflowAgent

from shared.base_agent import BaseAgent

logger = logging.getLogger(__name__)


def build_content_pipeline(
    specialist_agents: list[BaseAgent],
    account_name: str,
    display_name: str,
) -> WorkflowAgent:
    """Build a sequential content-creation workflow with HIL before publishing."""

    # Index specialists by class name for clarity
    by_type = {type(a).__name__: a for a in specialist_agents}

    trend_scout = by_type["TrendScoutAgent"]
    content_strategist = by_type["ContentStrategistAgent"]
    media_generator = by_type["MediaGeneratorAgent"]
    copywriter = by_type["CopywriterAgent"]
    publisher = by_type["PublisherAgent"]

    # Sequential pipeline — HIL pause BEFORE Publisher runs
    workflow = (
        SequentialBuilder()
        .participants([
            trend_scout.agent,
            content_strategist.agent,
            media_generator.agent,
            copywriter.agent,
            publisher.agent,
        ])
        .with_request_info(agents=[publisher.agent])
        .build()
    )

    pipeline_agent = WorkflowAgent(
        workflow,
        id=f"pipeline-{account_name}",
        name=f"{display_name} — Content Pipeline",
        description=(
            f"End-to-end content creation pipeline for {display_name}. "
            "Discovers trends → plans content → generates media → writes caption → "
            "pauses for human review → publishes to Instagram."
        ),
    )

    logger.info(
        f"[workflow] Built content pipeline for {display_name} "
        f"(5 agents, HIL before Publisher)"
    )
    return pipeline_agent
