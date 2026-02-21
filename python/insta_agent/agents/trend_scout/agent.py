"""Trend Scout agent — discovers trends and viral content via Tavily MCP server."""

from agent_framework import MCPStreamableHTTPTool

from agent_registry import Agent
from shared.base_agent import BaseAgent
from shared.config.settings import settings


class TrendScoutAgent(BaseAgent):
    agent_id = Agent.TREND_SCOUT

    def _build_tools(self) -> list:
        """Connect to Tavily's remote MCP server — auto-discovers search/extract/crawl tools."""
        tavily_mcp = MCPStreamableHTTPTool(name="tavily", url=settings.TAVILY_MCP_URL)
        return [tavily_mcp]
