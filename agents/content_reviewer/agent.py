"""Content Reviewer agent — safety and quality gate for all content."""

from agent_registry import Agent
from base_agent import BaseAgent
from .tools import build_content_reviewer_tools


class ContentReviewerAgent(BaseAgent):
    agent_id = Agent.CONTENT_REVIEWER

    def _build_tools(self) -> list:
        return build_content_reviewer_tools()
