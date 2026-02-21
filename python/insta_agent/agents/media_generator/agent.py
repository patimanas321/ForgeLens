"""Media Generator agent — creates images and videos for Instagram."""

from agent_registry import Agent
from shared.base_agent import BaseAgent
from .tools import build_media_generator_tools


class MediaGeneratorAgent(BaseAgent):
    agent_id = Agent.MEDIA_GENERATOR

    def _build_tools(self) -> list:
        return build_media_generator_tools()
