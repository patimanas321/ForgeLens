"""Trend Scout tools — Tavily web search via Python SDK (no MCP session management)."""

import json
import logging

from agent_framework import FunctionTool
from pydantic import BaseModel, Field
from tavily import AsyncTavilyClient

from shared.config.settings import settings

logger = logging.getLogger(__name__)

# Lazy Tavily client — avoids crash at import time when Key Vault is unavailable
_client: AsyncTavilyClient | None = None


def _get_client() -> AsyncTavilyClient:
    """Return (and cache) the Tavily client, creating it on first use."""
    global _client
    if _client is None:
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY is not set. Check Key Vault access or set the env var."
            )
        _client = AsyncTavilyClient(api_key=api_key)
    return _client


# ------------------------------------------------------------------
# Input schemas — intentionally minimal so the model doesn't fumble
# ------------------------------------------------------------------

class SearchInput(BaseModel):
    query: str = Field(..., description="The search query.")
    max_results: int = Field(default=5, ge=1, le=20, description="Number of results to return.")
    search_depth: str = Field(default="basic", description="'basic' or 'advanced' for deeper results.")


class ExtractInput(BaseModel):
    url: str = Field(..., description="The URL to extract content from.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def tavily_search(query: str, max_results: int = 5, search_depth: str = "basic") -> str:
    """Search the web using Tavily and return structured results."""
    logger.info("[SEARCH] query=%r max_results=%d depth=%s", query, max_results, search_depth)
    try:
        result = await _get_client().search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_images=True,
        )
        # Return a compact summary the model can reason over
        output = {
            "query": result.get("query", query),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:500],
                }
                for r in result.get("results", [])
            ],
            "images": result.get("images", [])[:5],
        }
        logger.info("[SEARCH] Returned %d results", len(output["results"]))
        return json.dumps(output)
    except Exception as e:
        logger.error("[SEARCH] Failed: %s", e)
        return json.dumps({"error": str(e)})


async def tavily_extract(url: str) -> str:
    """Extract clean content from a URL using Tavily."""
    logger.info("[EXTRACT] url=%r", url)
    try:
        result = await _get_client().extract(urls=[url])
        pages = result.get("results", [])
        if pages:
            page = pages[0]
            output = {
                "url": page.get("url", url),
                "content": page.get("raw_content", "")[:3000],
            }
        else:
            output = {"url": url, "content": "No content extracted."}
        return json.dumps(output)
    except Exception as e:
        logger.error("[EXTRACT] Failed: %s", e)
        return json.dumps({"error": str(e)})


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_trend_scout_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="search",
            description="Search the web for trends, news, competitor info, or any topic. Returns titles, URLs, and snippets.",
            input_model=SearchInput,
            func=tavily_search,
        ),
        FunctionTool(
            name="extract",
            description="Extract the full content from a specific URL. Use after finding interesting URLs via search.",
            input_model=ExtractInput,
            func=tavily_extract,
        ),
    ]
