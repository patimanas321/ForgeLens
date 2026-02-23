"""Content Strategist agent — plans content, picks topics, avoids repetition."""

from agent_registry import Agent
from shared.base_agent import BaseAgent
from .tools import build_content_strategist_tools


class ContentStrategistAgent(BaseAgent):
    agent_id = Agent.CONTENT_STRATEGIST

    def _build_tools(self) -> list:
        return build_content_strategist_tools()
