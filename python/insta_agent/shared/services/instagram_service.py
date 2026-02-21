"""
Instagram Graph API service — handles publishing posts and reading insights.

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api
"""

import logging
from shared.config.settings import settings
from shared.services import BaseService

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class InstagramService(BaseService):
    """Client for the Instagram Graph API (via Meta's Graph API)."""

    def __init__(self) -> None:
        super().__init__(
            base_url=GRAPH_API_BASE,
            bearer_token=settings.INSTAGRAM_ACCESS_TOKEN,
        )
        self.ig_account_id = settings.INSTAGRAM_BUSINESS_ACCOUNT_ID

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def create_image_container(self, image_url: str, caption: str) -> str:
        """
        Step 1 of publishing: create a media container for a single image post.
        Returns the container/creation ID.
        """
        url = f"{self.base_url}/{self.ig_account_id}/media"
        data = await self._request(
            url,
            method="POST",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )
        container_id = data["id"]
        logger.info(f"[OK] Created image container: {container_id}")
        return container_id

    async def create_video_container(self, video_url: str, caption: str) -> str:
        """Create a media container for a reel/video."""
        url = f"{self.base_url}/{self.ig_account_id}/media"
        data = await self._request(
            url,
            method="POST",
            params={
                "video_url": video_url,
                "caption": caption,
                "media_type": "REELS",
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )
        container_id = data["id"]
        logger.info(f"[OK] Created video container: {container_id}")
        return container_id

    async def create_carousel_container(
        self, children_ids: list[str], caption: str
    ) -> str:
        """Create a carousel container from child media IDs."""
        url = f"{self.base_url}/{self.ig_account_id}/media"
        data = await self._request(
            url,
            method="POST",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )
        return data["id"]

    async def publish_container(self, container_id: str) -> str:
        """
        Step 2: Publish a previously created media container.
        Returns the published media ID.
        """
        url = f"{self.base_url}/{self.ig_account_id}/media_publish"
        data = await self._request(
            url,
            method="POST",
            params={
                "creation_id": container_id,
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )
        media_id = data["id"]
        logger.info(f"[OK] Published media: {media_id}")
        return media_id

    async def check_container_status(self, container_id: str) -> dict:
        """Check the upload/processing status of a media container."""
        url = f"{self.base_url}/{container_id}"
        return await self._request(
            url,
            params={
                "fields": "status_code,status",
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )

    # ------------------------------------------------------------------
    # Insights / Analytics
    # ------------------------------------------------------------------

    async def get_media_insights(self, media_id: str) -> dict:
        """Get engagement metrics for a specific post."""
        url = f"{self.base_url}/{media_id}/insights"
        return await self._request(
            url,
            params={
                "metric": "impressions,reach,engagement,saved,shares",
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )

    async def get_account_insights(self, period: str = "day", days: int = 7) -> dict:
        """Get account-level insights (followers, reach, impressions)."""
        url = f"{self.base_url}/{self.ig_account_id}/insights"
        return await self._request(
            url,
            params={
                "metric": "impressions,reach,follower_count,profile_views",
                "period": period,
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )

    async def get_recent_media(self, limit: int = 25) -> list[dict]:
        """Fetch recent posts for the account (for history/dedup)."""
        url = f"{self.base_url}/{self.ig_account_id}/media"
        data = await self._request(
            url,
            params={
                "fields": "id,caption,timestamp,media_type,permalink,like_count,comments_count",
                "limit": str(limit),
                "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            },
        )
        return data.get("data", [])
