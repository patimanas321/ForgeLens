"""
Content Pipeline — MAF sequential workflow for content draft generation.

Chains specialist agents in order:
    Trend Scout → Insta Post Generator
"""

import logging

from agent_framework import SequentialBuilder, WorkflowAgent

from shared.base_agent import BaseAgent

logger = logging.getLogger(__name__)


def build_content_pipeline(
    trend_scout: BaseAgent,
    insta_post_generator: BaseAgent,
    account_name: str,
    display_name: str,
) -> WorkflowAgent:
    """Build a sequential content-creation workflow for trend + media generation."""

    # Sequential pipeline — generates content drafts for account-level queueing
    workflow = (
        SequentialBuilder()
        .participants([
            trend_scout.agent,
            insta_post_generator.agent,
        ])
        .build()
    )

    pipeline_agent = WorkflowAgent(
        workflow,
        id=f"pipeline-{account_name}",
        name=f"{display_name} — Content Pipeline",
        description=(
            f"End-to-end content creation pipeline for {display_name}. "
            "Discovers trends → generates media drafts. "
            "Queueing and approval are handled separately."
        ),
    )

    logger.info(
        f"[workflow] Built content pipeline for {display_name} "
        f"(2 agents, trend + media generation)"
    )
    return pipeline_agent
