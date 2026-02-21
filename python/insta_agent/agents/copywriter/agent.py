"""Copywriter agent — writes captions, hashtags, and CTAs for Instagram."""

from agent_registry import Agent
from shared.base_agent import BaseAgent
from .tools import build_copywriter_tools


class CopywriterAgent(BaseAgent):
    agent_id = Agent.COPYWRITER

    def _build_tools(self) -> list:
        return build_copywriter_tools()
