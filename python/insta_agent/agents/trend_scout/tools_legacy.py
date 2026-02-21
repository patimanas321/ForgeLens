"""
Tools for the Trend Scout agent — web search and trend discovery.
"""

from agent_framework import FunctionTool
from pydantic import BaseModel, Field
from shared.services.web_search_service import WebSearchService

_search_service = WebSearchService()


# ------------------------------------------------------------------
# Input schemas
# ------------------------------------------------------------------

class SearchWebInput(BaseModel):
    query: str = Field(..., description="Search query to find relevant content and trends.")


class SearchTrendingInput(BaseModel):
    niche: str = Field(..., description="The niche/topic area to find trends for (e.g. 'fitness', 'tech', 'food').")
    days: int = Field(default=1, ge=1, le=7, description="How many days back to look for trends.")


class SearchCompetitorInput(BaseModel):
    account_handle: str = Field(..., description="Instagram handle of the competitor (without @).")


class SearchHashtagsInput(BaseModel):
    topic: str = Field(..., description="Topic to find trending Instagram hashtags for.")


# ------------------------------------------------------------------
# Tool functions
# ------------------------------------------------------------------

async def search_web(query: str) -> dict:
    """Run a general web search and return structured results."""
    return await _search_service.search(query)


async def search_trending_topics(niche: str, days: int = 1) -> dict:
    """Search for trending topics in a specific niche."""
    return await _search_service.search_trending(niche, days)


async def search_competitor(account_handle: str) -> dict:
    """Analyze a competitor Instagram account's recent content."""
    return await _search_service.search_competitor(account_handle)


async def search_hashtags(topic: str) -> dict:
    """Find trending Instagram hashtags for a given topic."""
    return await _search_service.search_hashtags(topic)


# ------------------------------------------------------------------
# Build tools list
# ------------------------------------------------------------------

def build_trend_scout_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="search_web",
            description="Run a general web search. Use for broad queries, news, or when other tools don't fit.",
            input_model=SearchWebInput,
            func=search_web,
        ),
        FunctionTool(
            name="search_trending_topics",
            description="Find trending topics in a specific niche (e.g. fitness, tech, fashion). Returns recent viral content.",
            input_model=SearchTrendingInput,
            func=search_trending_topics,
        ),
        FunctionTool(
            name="search_competitor",
            description="Analyze a competitor's recent Instagram activity and popular content.",
            input_model=SearchCompetitorInput,
            func=search_competitor,
        ),
        FunctionTool(
            name="search_hashtags",
            description="Find trending Instagram hashtags for a topic.",
            input_model=SearchHashtagsInput,
            func=search_hashtags,
        ),
    ]
