"""
Orchestrator agent — coordinates the entire Instagram content pipeline.

The Orchestrator doesn't have its own tools. Instead, each specialist agent
is wrapped as a tool via `ChatAgent.as_tool()`. The LLM decides which
specialist to invoke based on user intent and the pipeline state.
"""

from agent_registry import Agent
from shared.base_agent import BaseAgent


class OrchestratorAgent(BaseAgent):
    agent_id = Agent.ORCHESTRATOR

    def __init__(self, chat_client, child_agents: list[BaseAgent]) -> None:
        self._child_agents = child_agents
        super().__init__(chat_client)

    def _build_tools(self) -> list:
        """Each child agent becomes a callable tool for the orchestrator."""
        return [child.as_tool() for child in self._child_agents]
