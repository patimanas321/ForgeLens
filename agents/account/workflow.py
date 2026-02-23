"""
Content Pipeline — MAF sequential workflow for trend discovery.

Runs the Trend Scout agent to discover trending topics.
Media generation is handled separately by the background worker.
"""

import logging

from agent_framework import SequentialBuilder, WorkflowAgent

from base_agent import BaseAgent

logger = logging.getLogger(__name__)


def build_content_pipeline(
    trend_scout: BaseAgent,
    account_name: str,
    display_name: str,
) -> WorkflowAgent:
    """Build a sequential content-discovery workflow for an account."""

    workflow = (
        SequentialBuilder()
        .participants([
            trend_scout.agent,
        ])
        .build()
    )

    pipeline_agent = WorkflowAgent(
        workflow,
        id=f"pipeline-{account_name}",
        name=f"{display_name} — Content Pipeline",
        description=(
            f"Content discovery pipeline for {display_name}. "
            "Discovers trends via web search. "
            "Media generation is handled by the background worker."
        ),
    )

    logger.info(
        f"[workflow] Built content pipeline for {display_name} "
        f"(1 agent, trend discovery)"
    )
    return pipeline_agent
