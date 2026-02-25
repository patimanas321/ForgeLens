from __future__ import annotations

from config.settings import settings
from services.fal_ai_service import FalAIService


class VideoGeneratorService:
    def __init__(self, fal_service: FalAIService | None = None) -> None:
        self._fal = fal_service or FalAIService()

    async def generate(
        self,
        *,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "9:16",
    ) -> dict:
        selected_model = settings.VIDEO_GENERATION_MODEL.strip()
        if not selected_model:
            selected_model = settings.VIDEO_GENERATION_MODEL

        return await self._fal.submit_video_generation(
            prompt=prompt,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            model_id=selected_model,
        )
