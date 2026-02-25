"""Publisher agent — posts approved content to Instagram via Graph API."""

from agent_registry import Agent
from agents.base_agent import BaseAgent
from .tools import build_publisher_tools


class PublisherAgent(BaseAgent):
    agent_id = Agent.PUBLISHER

    def _build_tools(self) -> list:
        return build_publisher_tools()
