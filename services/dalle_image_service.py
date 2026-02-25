from __future__ import annotations

from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.identity import get_bearer_token_provider

from config.settings import settings


class DalleImageService:
    def __init__(self) -> None:
        self._client: AsyncAzureOpenAI | None = None
        self._credential: AsyncDefaultAzureCredential | None = None

    async def _get_client(self) -> AsyncAzureOpenAI:
        if self._client is None:
            self._credential = AsyncDefaultAzureCredential(
                managed_identity_client_id=settings.AZURE_CLIENT_ID
            )
            self._client = AsyncAzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                azure_ad_token_provider=get_bearer_token_provider(
                    self._credential, "https://cognitiveservices.azure.com/.default"
                ),
                api_version=settings.AZURE_OPENAI_API_VERSION,
            )
        return self._client

    async def generate_image(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        model_id: str | None = None,
    ) -> dict:
        selected_model = model_id or settings.AZURE_OPENAI_IMAGE_DEPLOYMENT
        client = await self._get_client()

        response = await client.images.generate(
            model=selected_model,
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=1,
        )

        image_url = ""
        if getattr(response, "data", None):
            first = response.data[0]
            image_url = getattr(first, "url", "") or ""

        return {
            "provider": "dalle",
            "mode": "sync",
            "model_id": selected_model,
            "image_url": image_url,
            "raw_response": response.model_dump() if hasattr(response, "model_dump") else {},
        }
