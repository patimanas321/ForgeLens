"""
Web search service — wraps Tavily API for trend discovery.

Tavily is purpose-built for AI agents (returns clean text, not HTML).
Fallback: can swap for SerpAPI or Brave Search.
"""

import logging
from shared.config.settings import settings
from shared.services import BaseService

logger = logging.getLogger(__name__)


class WebSearchService(BaseService):
    """Tavily Search API client."""

    def __init__(self) -> None:
        super().__init__(base_url="https://api.tavily.com")
        self._api_key = settings.TAVILY_API_KEY

    async def search(
        self,
        query: str,
        *,
        search_depth: str = "advanced",
        max_results: int = 10,
        include_images: bool = True,
        topic: str = "general",
    ) -> dict:
        """
        Run a web search and return structured results.

        Args:
            query: Search query string.
            search_depth: "basic" or "advanced" (deeper extraction).
            max_results: Number of results to return.
            include_images: Whether to include image URLs.
            topic: "general" or "news" for recency-focused results.
        """
        url = f"{self.base_url}/search"
        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_images": include_images,
            "topic": topic,
        }
        result = await self._request(url, method="POST", json=payload)
        logger.info(f"[OK] Tavily search returned {len(result.get('results', []))} results for: {query}")
        return result

    async def search_trending(self, niche: str, days: int = 1) -> dict:
        """Search for trending topics in a specific niche."""
        query = f"trending {niche} topics today viral content {days} day"
        return await self.search(query, topic="news", max_results=15)

    async def search_competitor(self, account_handle: str) -> dict:
        """Analyze a competitor Instagram account's recent activity."""
        query = f"Instagram @{account_handle} recent posts popular content"
        return await self.search(query, max_results=10)

    async def search_hashtags(self, topic: str) -> dict:
        """Find trending hashtags for a topic."""
        query = f"trending Instagram hashtags for {topic} 2026"
        return await self.search(query, max_results=10)
