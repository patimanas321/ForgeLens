from __future__ import annotations

from fal_client.client import AsyncClient as FalAsyncClient

from config.settings import settings


class FalAIService:
    def __init__(self) -> None:
        self._client = FalAsyncClient(key=settings.FAL_KEY)

    async def submit_image_generation(
        self,
        *,
        prompt: str,
        aspect_ratio: str = "1:1",
        output_format: str = "png",
        resolution: str = "1K",
        model_id: str | None = None,
    ) -> dict:
        selected_model = model_id or settings.IMAGE_GENERATION_MODEL
        arguments = {
            "prompt": prompt,
            "num_images": 1,
            "aspect_ratio": aspect_ratio,
            "output_format": output_format,
            "resolution": resolution,
            "safety_tolerance": "4",
        }
        handle = await self._client.submit(selected_model, arguments=arguments)
        return {
            "provider": "fal",
            "mode": "async",
            "model_id": selected_model,
            "request_id": handle.request_id,
        }

    async def submit_video_generation(
        self,
        *,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "9:16",
        model_id: str | None = None,
    ) -> dict:
        selected_model, arguments = self._build_video_arguments(
            prompt=prompt,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            model_id=model_id,
        )
        handle = await self._client.submit(selected_model, arguments=arguments)
        return {
            "provider": "fal",
            "mode": "async",
            "model_id": selected_model,
            "request_id": handle.request_id,
        }

    async def status(self, model_id: str, request_id: str):
        return await self._client.status(model_id, request_id)

    async def result(self, model_id: str, request_id: str) -> dict:
        return await self._client.result(model_id, request_id)

    def _build_video_arguments(
        self,
        *,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
        model_id: str | None,
    ) -> tuple[str, dict]:
        selected_model = (model_id or settings.VIDEO_GENERATION_MODEL).strip() or settings.VIDEO_GENERATION_MODEL
        normalized_model = selected_model.lower()
        is_sora = "sora" in normalized_model
        is_kling = "kling" in normalized_model

        if is_sora:
            sora_duration = min([d for d in [4, 8, 12] if d >= duration_seconds], default=12)
            sora_aspect = aspect_ratio if aspect_ratio in ("9:16", "16:9") else "9:16"
            return selected_model, {
                "prompt": prompt,
                "duration": str(sora_duration),
                "aspect_ratio": sora_aspect,
                "resolution": "720p",
                "delete_video": False,
            }

        if is_kling:
            kling_duration = max(3, min(duration_seconds, 15))
            kling_aspect = aspect_ratio if aspect_ratio in ("9:16", "16:9", "1:1") else "9:16"
            return selected_model, {
                "prompt": prompt,
                "duration": str(kling_duration),
                "aspect_ratio": kling_aspect,
                "negative_prompt": "blur, distort, and low quality",
                "generate_audio": True,
            }

        return selected_model, {
            "prompt": prompt,
            "duration": str(duration_seconds),
            "aspect_ratio": aspect_ratio,
        }
