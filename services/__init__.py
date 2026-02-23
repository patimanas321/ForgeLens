"""
Base HTTP service with optional Bearer token authentication.
All domain-specific API clients inherit from this.
"""

import httpx
import logging

logger = logging.getLogger(__name__)


class BaseService:
    def __init__(self, base_url: str, bearer_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self._bearer_token = bearer_token

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    async def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        json: dict | None = None,
        params: dict | None = None,
        timeout: float = 30.0,
    ) -> dict:
        headers = self._get_headers()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method, url, headers=headers, json=json, params=params
            )
            resp.raise_for_status()
            return resp.json()

    async def _request_raw(
        self,
        url: str,
        *,
        method: str = "GET",
        json: dict | None = None,
        data: dict | None = None,
        params: dict | None = None,
        timeout: float = 60.0,
    ) -> httpx.Response:
        """Return the raw httpx.Response (for binary/media downloads)."""
        headers = self._get_headers()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method, url, headers=headers, json=json, data=data, params=params
            )
            resp.raise_for_status()
            return resp
