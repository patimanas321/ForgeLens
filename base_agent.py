"""
BaseAgent — Abstract base class for all agents in the system.

Handles ChatAgent creation, prompt loading, and as_tool() wrapping
using metadata from the central agent registry.
"""

import inspect
from abc import ABC
from pathlib import Path

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient

from agent_registry import AGENT_REGISTRY, Agent


class BaseAgent(ABC):
    """
    Subclasses must set `agent_id` and optionally override `_build_tools()`.

    The prompt is loaded automatically from `prompt.md` in the subclass's directory.
    """

    agent_id: Agent

    def __init__(self, chat_client: AzureOpenAIResponsesClient) -> None:
        self._chat_client = chat_client
        entry = AGENT_REGISTRY[self.agent_id]

        self._agent = ChatAgent(
            chat_client=chat_client,
            instructions=self._load_prompt(),
            id=self.agent_id.value,
            name=entry.name,
            description=entry.description,
            tools=self._build_tools(),
        )

    def _load_prompt(self) -> str:
        """Load prompt.md from the subclass's directory."""
        subclass_dir = Path(inspect.getfile(type(self))).parent
        return (subclass_dir / "prompt.md").read_text(encoding="utf-8")

    def _build_tools(self) -> list:
        """Override to return FunctionTool or MCP tool instances."""
        return []

    @property
    def agent(self) -> ChatAgent:
        return self._agent

    def as_tool(self) -> object:
        """Wrap this agent as a callable tool using registry metadata."""
        entry = AGENT_REGISTRY[self.agent_id]
        return self._agent.as_tool(
            name=entry.tool_name,
            description=entry.description,
            arg_name=entry.arg_name,
            arg_description=entry.arg_description,
        )
