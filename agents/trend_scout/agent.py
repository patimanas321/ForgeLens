"""Trend Scout agent — discovers trends and viral content via Tavily web search."""

from agent_registry import Agent
from shared.base_agent import BaseAgent
from .tools import build_trend_scout_tools


class TrendScoutAgent(BaseAgent):
    agent_id = Agent.TREND_SCOUT

    def _build_tools(self) -> list:
        """Return Tavily search/extract tools via Python SDK (no MCP session needed)."""
        return build_trend_scout_tools()
