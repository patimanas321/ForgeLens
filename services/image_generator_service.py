from __future__ import annotations

from config.settings import settings
from services.dalle_image_service import DalleImageService
from services.fal_ai_service import FalAIService


class ImageGeneratorService:
    def __init__(
        self,
        fal_service: FalAIService | None = None,
        dalle_service: DalleImageService | None = None,
    ) -> None:
        self._fal = fal_service or FalAIService()
        self._dalle = dalle_service or DalleImageService()

    async def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        output_format: str = "png",
        resolution: str = "1K",
    ) -> dict:
        model_id = settings.IMAGE_GENERATION_MODEL.strip() or settings.AZURE_OPENAI_IMAGE_DEPLOYMENT

        if model_id.lower().startswith("fal-ai/"):
            return await self._fal.submit_image_generation(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                output_format=output_format,
                resolution=resolution,
                model_id=model_id,
            )

        size = self._aspect_ratio_to_dalle_size(aspect_ratio)
        return await self._dalle.generate_image(
            prompt=prompt,
            size=size,
            quality="standard",
            style="vivid",
            model_id=model_id,
        )

    @staticmethod
    def _aspect_ratio_to_dalle_size(aspect_ratio: str) -> str:
        normalized = (aspect_ratio or "1:1").strip()
        if normalized in {"1:1", "1x1"}:
            return "1024x1024"
        if normalized in {"9:16", "portrait"}:
            return "1024x1792"
        if normalized in {"16:9", "landscape"}:
            return "1792x1024"
        if normalized in {"4:5"}:
            return "1024x1792"
        return "1024x1024"
