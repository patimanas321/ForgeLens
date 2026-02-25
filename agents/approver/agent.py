"""Approver agent — manages human-in-the-loop approval decisions."""

from agent_registry import Agent
from agents.base_agent import BaseAgent
from .tools import build_review_queue_tools


class ReviewQueueAgent(BaseAgent):
    agent_id = Agent.REVIEW_QUEUE

    def _build_tools(self) -> list:
        return build_review_queue_tools()
