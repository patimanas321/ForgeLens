"""
BaseAgent — Abstract base class for all agents in the system.

Handles ChatAgent creation, prompt loading, child-agent wiring, and
as_tool() wrapping using metadata from the central agent registry.
"""

from __future__ import annotations

import inspect
import logging
from abc import ABC
from pathlib import Path

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient

from agent_registry import AGENT_REGISTRY, Agent

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Subclasses must set ``agent_id`` and optionally override ``_build_tools()``.

    The prompt is loaded automatically from ``prompt.md`` in the subclass's
    directory.  Pass *child_agents* to expose other agents as callable tools.

    Override ``_agent_config_id()``, ``_agent_config_name()``, or
    ``_agent_config_description()`` for dynamic per-instance identity
    (e.g. one agent per Instagram account).
    """

    agent_id: Agent

    def __init__(
        self,
        chat_client: AzureOpenAIResponsesClient,
        child_agents: list[BaseAgent] | None = None,
    ) -> None:
        self._chat_client = chat_client
        self._child_agents = child_agents or []

        # Own tools + child-agent delegation tools
        tools = self._build_tools() + [c.as_tool() for c in self._child_agents]

        self._agent = ChatAgent(
            chat_client=chat_client,
            instructions=self._load_prompt(),
            id=self._agent_config_id(),
            name=self._agent_config_name(),
            description=self._agent_config_description(),
            tools=tools,
        )

        if self._child_agents:
            logger.info(
                "[%s] Created with %d child agent(s): %s",
                self._agent_config_id(),
                len(self._child_agents),
                [c.agent_id.value for c in self._child_agents],
            )

    # ------------------------------------------------------------------
    # Overridable config — defaults read from the agent registry
    # ------------------------------------------------------------------

    def _agent_config_id(self) -> str:
        """ChatAgent id. Override for dynamic per-instance ids."""
        return self.agent_id.value

    def _agent_config_name(self) -> str:
        """ChatAgent display name. Override for per-instance names."""
        return AGENT_REGISTRY[self.agent_id].name

    def _agent_config_description(self) -> str:
        """ChatAgent description. Override for per-instance descriptions."""
        return AGENT_REGISTRY[self.agent_id].description

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
