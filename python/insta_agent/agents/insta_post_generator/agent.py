"""Insta Post Generator agent — creates media and copy assets for Instagram."""

from agent_registry import Agent
from shared.base_agent import BaseAgent
from .tools import build_insta_post_generator_tools


class InstaPostGeneratorAgent(BaseAgent):
    agent_id = Agent.INSTA_POST_GENERATOR

    def _build_tools(self) -> list:
        return build_insta_post_generator_tools()
