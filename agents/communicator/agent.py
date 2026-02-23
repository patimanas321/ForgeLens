"""Communicator agent — sends review reminders and notifications."""

from agent_registry import Agent
from base_agent import BaseAgent
from .tools import build_communicator_tools


class CommunicatorAgent(BaseAgent):
    agent_id = Agent.COMMUNICATOR

    def _build_tools(self) -> list:
        return build_communicator_tools()
