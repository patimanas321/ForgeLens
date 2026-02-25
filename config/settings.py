"""Centralized configuration.

Secrets (API keys, tokens) come from Azure Key Vault.
Non-secret config (endpoints, model names, container names) is defined here.
"""

from config.keyvault import kv


class Settings:
    # --- Managed Identity (for Azure-hosted deployments) ---
    AZURE_CLIENT_ID: str = "02911707-a3a0-49b8-8ab0-4a8f0c9a5830"

    # --- Azure Key Vault ---
    AZURE_KEYVAULT_URL: str = "https://forgelens-kv.vault.azure.net/"

    # --- Azure OpenAI ---
    AZURE_OPENAI_ENDPOINT: str = "https://forgelens-openai.openai.azure.com"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt5-mini"
    AZURE_OPENAI_API_VERSION: str = "2025-03-01-preview"
    AZURE_OPENAI_IMAGE_DEPLOYMENT: str = "dall-e-3"

    # --- fal.ai Media Generation (secret from KV) ---
    @property
    def FAL_KEY(self) -> str:
        return kv.get("fal-key") or ""

    IMAGE_GENERATION_MODEL: str = "dall-e-3"
    VIDEO_GENERATION_MODEL: str = "fal-ai/kling-video/o3/standard/text-to-video"

    # --- Instagram Graph API (secrets from KV) ---
    @property
    def INSTAGRAM_ACCESS_TOKEN(self) -> str:
        return kv.get("instagram-access-token") or ""

    @property
    def INSTAGRAM_BUSINESS_ACCOUNT_ID(self) -> str:
        """Default account ID — first one discovered in KV."""
        _, account_id = kv.default_instagram_account
        return account_id or ""

    @property
    def INSTAGRAM_ACCOUNTS(self) -> dict[str, str]:
        """All IG accounts: {name: account_id}. For multi-account publishing."""
        return kv.instagram_accounts

    # --- Web Search / Tavily (secret from KV) ---
    @property
    def TAVILY_API_KEY(self) -> str:
        return kv.get("tavily-api-key") or ""

    @property
    def TAVILY_MCP_URL(self) -> str:
        """Build MCP URL from KV api key."""
        key = self.TAVILY_API_KEY
        if key:
            return f"https://mcp.tavily.com/mcp/?tavilyApiKey={key}"
        return ""

    # --- Azure Blob Storage ---
    AZURE_STORAGE_ACCOUNT_URL: str = "https://forgelensstorage.blob.core.windows.net/"
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER_NAME: str = "insta-media"

    # --- Azure Cosmos DB (NoSQL) ---
    COSMOS_ENDPOINT: str = "https://forgelens-cosmos.documents.azure.com:443/"
    COSMOS_DATABASE: str = "insta-agent"
    COSMOS_CONTAINER: str = "media-metadata"

    # --- Azure Service Bus (Review Queue) ---
    SERVICEBUS_NAMESPACE: str = "forgelens-bus.servicebus.windows.net"

    # --- Azure AI Content Safety ---
    CONTENT_SAFETY_ENDPOINT: str = "https://forgelens-content-safety.cognitiveservices.azure.com/"

    # --- Azure Communication Services (Email Notifications) ---
    ACS_ENDPOINT: str = "https://forgelens-acs.unitedstates.communication.azure.com"
    ACS_CONNECTION_STRING: str = ""
    ACS_SENDER_EMAIL: str = "DoNotReply@fb2ec383-bc71-4a88-8364-623654d619d0.azurecomm.net"
    REVIEWER_EMAIL: str = "forgelensimages@gmail.com,patimanas321@gmail.com"

    # --- Notifications (fallback) ---
    SLACK_WEBHOOK_URL: str = ""

    # --- Server ---
    PORT: int = 8080

    # --- Telemetry ---
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = ""


settings = Settings()
