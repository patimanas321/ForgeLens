"""Azure AI Content Safety service — hard moderation for text and images.

Returns structured severity scores (0–6) for categories:
Hate, SelfHarm, Sexual, Violence.

Uses ``DefaultAzureCredential`` for auth (same managed identity).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import (
    AnalyzeImageOptions,
    AnalyzeTextOptions,
    ImageData,
    TextCategory,
    ImageCategory,
)
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential

from config.settings import settings

logger = logging.getLogger(__name__)

# Severity threshold — anything at or above this is a hard block.
# Azure Content Safety uses 0 (safe) to 6 (severe).
SEVERITY_THRESHOLD = 2


@dataclass
class SafetyResult:
    """Outcome of a Content Safety analysis."""
    safe: bool = True
    categories: dict[str, int] = field(default_factory=dict)   # category → severity
    blocked_categories: list[str] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "categories": self.categories,
            "blocked_categories": self.blocked_categories,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: ContentSafetyClient | None = None
_credential: DefaultAzureCredential | None = None


def _get_client() -> ContentSafetyClient:
    global _client, _credential
    if _client is None:
        endpoint = settings.CONTENT_SAFETY_ENDPOINT
        if not endpoint:
            raise RuntimeError("CONTENT_SAFETY_ENDPOINT is not configured")
        _credential = DefaultAzureCredential(
            managed_identity_client_id=settings.AZURE_CLIENT_ID
        )
        _client = ContentSafetyClient(endpoint, _credential)
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_text(text: str) -> SafetyResult:
    """Analyze a text string for harmful content (synchronous).

    Returns a SafetyResult with per-category severity scores.
    """
    if not text or not text.strip():
        return SafetyResult()

    try:
        client = _get_client()
        request = AnalyzeTextOptions(text=text[:10_000])  # API limit: 10 000 chars
        response = client.analyze_text(request)

        categories: dict[str, int] = {}
        blocked: list[str] = []

        for item in (response.categories_analysis or []):
            cat_name = item.category.value if hasattr(item.category, "value") else str(item.category)
            severity = item.severity or 0
            categories[cat_name] = severity
            if severity >= SEVERITY_THRESHOLD:
                blocked.append(cat_name)

        return SafetyResult(
            safe=len(blocked) == 0,
            categories=categories,
            blocked_categories=blocked,
        )

    except Exception as e:
        logger.error("[content-safety] Text analysis failed: %s", e)
        return SafetyResult(safe=True, error=str(e))  # fail-open to avoid blocking pipeline


def analyze_image_from_url(image_url: str) -> SafetyResult:
    """Download an image from URL and analyze it for harmful content (synchronous).

    Azure Content Safety requires raw image bytes (base64), so we download first.
    """
    if not image_url:
        return SafetyResult()

    try:
        # Download image bytes
        with httpx.Client(timeout=30) as http:
            resp = http.get(image_url)
            resp.raise_for_status()
            image_bytes = resp.content

        client = _get_client()
        request = AnalyzeImageOptions(
            image=ImageData(content=image_bytes),
        )
        response = client.analyze_image(request)

        categories: dict[str, int] = {}
        blocked: list[str] = []

        for item in (response.categories_analysis or []):
            cat_name = item.category.value if hasattr(item.category, "value") else str(item.category)
            severity = item.severity or 0
            categories[cat_name] = severity
            if severity >= SEVERITY_THRESHOLD:
                blocked.append(cat_name)

        return SafetyResult(
            safe=len(blocked) == 0,
            categories=categories,
            blocked_categories=blocked,
        )

    except Exception as e:
        logger.error("[content-safety] Image analysis failed: %s", e)
        return SafetyResult(safe=True, error=str(e))  # fail-open
