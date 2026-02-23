"""Centralized configuration loaded from environment variables + Azure Key Vault.

Secrets (API keys, tokens) come from Key Vault with env-var fallback for local dev.
Non-secret config (endpoints, model names, container names) stays in env vars.
"""

import logging
import os

logger = logging.getLogger(__name__)


class Settings:
    # --- Managed Identity (for Azure-hosted deployments) ---
    AZURE_CLIENT_ID: str = "02911707-a3a0-49b8-8ab0-4a8f0c9a5830"

    # --- Azure Key Vault ---
    AZURE_KEYVAULT_URL: str = os.environ.get("AZURE_KEYVAULT_URL", "https://forgelens-kv.vault.azure.net/")

    # --- Azure OpenAI ---
    AZURE_OPENAI_ENDPOINT: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://forgelens-openai.openai.azure.com")
    AZURE_OPENAI_DEPLOYMENT: str = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt5-mini")
    AZURE_OPENAI_API_VERSION: str = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
    AZURE_OPENAI_IMAGE_DEPLOYMENT: str = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT", "dall-e-3")

    # --- fal.ai Media Generation (secret from KV) ---
    @property
    def FAL_KEY(self) -> str:
        from shared.config.keyvault import kv
        return kv.get("fal-key") or ""

    FAL_IMAGE_MODEL: str = os.environ.get("FAL_IMAGE_MODEL", "fal-ai/nano-banana-pro")
    FAL_VIDEO_MODEL: str = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/kling-video/o3/standard/text-to-video")
    FAL_VIDEO_MODEL_ALT: str = os.environ.get("FAL_VIDEO_MODEL_ALT", "fal-ai/sora-2/text-to-video")

    # --- Instagram Graph API (secrets from KV) ---
    @property
    def INSTAGRAM_ACCESS_TOKEN(self) -> str:
        from shared.config.keyvault import kv
        return kv.get("instagram-access-token") or ""

    @property
    def INSTAGRAM_BUSINESS_ACCOUNT_ID(self) -> str:
        """Default account ID — first one discovered in KV, or env var fallback."""
        from shared.config.keyvault import kv
        _, account_id = kv.default_instagram_account
        return account_id or os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

    @property
    def INSTAGRAM_ACCOUNTS(self) -> dict[str, str]:
        """All IG accounts: {name: account_id}. For multi-account publishing."""
        from shared.config.keyvault import kv
        accounts = kv.instagram_accounts
        # Fallback: if KV has nothing, use the single env var
        if not accounts:
            single = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
            if single:
                accounts = {"default": single}
        return accounts

    # --- Web Search / Tavily (secret from KV) ---
    @property
    def TAVILY_API_KEY(self) -> str:
        from shared.config.keyvault import kv
        return kv.get("tavily-api-key") or ""

    @property
    def TAVILY_MCP_URL(self) -> str:
        """Build MCP URL from KV api key, or fall back to env var."""
        key = self.TAVILY_API_KEY
        if key:
            return f"https://mcp.tavily.com/mcp/?tavilyApiKey={key}"
        return os.environ.get("TAVILY_MCP_URL", "")

    # --- Azure Blob Storage ---
    AZURE_STORAGE_ACCOUNT_URL: str = os.environ.get("AZURE_STORAGE_ACCOUNT_URL", "https://forgelensstorage.blob.core.windows.net/")
    AZURE_STORAGE_CONNECTION_STRING: str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_CONTAINER_NAME: str = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "insta-media")

    # --- Azure Cosmos DB (NoSQL) ---
    COSMOS_ENDPOINT: str = os.environ.get("COSMOS_ENDPOINT", "https://forgelens-cosmos.documents.azure.com:443/")
    COSMOS_DATABASE: str = os.environ.get("COSMOS_DATABASE", "insta-agent")
    COSMOS_CONTAINER: str = os.environ.get("COSMOS_CONTAINER", "media-metadata")

    # --- Azure Service Bus (Review Queue) ---
    SERVICEBUS_NAMESPACE: str = os.environ.get("SERVICEBUS_NAMESPACE", "forgelens-bus.servicebus.windows.net")

    # --- Azure Communication Services (Email Notifications) ---
    ACS_ENDPOINT: str = os.environ.get("ACS_ENDPOINT", "https://forgelens-acs.unitedstates.communication.azure.com")
    ACS_CONNECTION_STRING: str = os.environ.get("ACS_CONNECTION_STRING", "")
    ACS_SENDER_EMAIL: str = os.environ.get("ACS_SENDER_EMAIL", "DoNotReply@fb2ec383-bc71-4a88-8364-623654d619d0.azurecomm.net")
    REVIEWER_EMAIL: str = os.environ.get("REVIEWER_EMAIL", "forgelensimages@gmail.com,patimanas321@gmail.com")

    # --- Notifications (fallback) ---
    SLACK_WEBHOOK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")

    # --- Server ---
    PORT: int = int(os.environ.get("PORT", "8080"))

    # --- Telemetry ---
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")


settings = Settings()
