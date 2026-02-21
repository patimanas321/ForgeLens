"""Centralized configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Managed Identity (for Azure-hosted deployments) ---
    AZURE_CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "02911707-a3a0-49b8-8ab0-4a8f0c9a5830")

    # --- Azure OpenAI ---
    AZURE_OPENAI_ENDPOINT: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://forgelens-openai.openai.azure.com")
    AZURE_OPENAI_DEPLOYMENT: str = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt5-mini")
    AZURE_OPENAI_DEPLOYMENT_STRONG: str = os.environ.get("AZURE_OPENAI_DEPLOYMENT_STRONG", "gpt5-mini")
    AZURE_OPENAI_API_VERSION: str = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
    AZURE_OPENAI_IMAGE_DEPLOYMENT: str = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT", "dall-e-3")

    # --- fal.ai Media Generation ---
    FAL_KEY: str = os.environ.get("FAL_KEY", "0a432dc9-87cc-42ad-9f6d-3643e910872e:b4a84c015bcb64b30a999b54b1f5a0a9")
    FAL_IMAGE_MODEL: str = os.environ.get("FAL_IMAGE_MODEL", "fal-ai/nano-banana-pro")
    FAL_VIDEO_MODEL: str = os.environ.get("FAL_VIDEO_MODEL", "fal-ai/kling-video/o3/standard/text-to-video")
    FAL_VIDEO_MODEL_ALT: str = os.environ.get("FAL_VIDEO_MODEL_ALT", "fal-ai/sora-2/text-to-video")

    # --- Instagram Graph API ---
    INSTAGRAM_BUSINESS_ACCOUNT_ID: str = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    INSTAGRAM_ACCESS_TOKEN: str = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

    # --- Web Search (Tavily MCP) ---
    TAVILY_MCP_URL: str = os.environ.get("TAVILY_MCP_URL", "https://mcp.tavily.com/mcp/?tavilyApiKey=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")

    # --- Azure Blob Storage ---
    AZURE_STORAGE_ACCOUNT_URL: str = os.environ.get("AZURE_STORAGE_ACCOUNT_URL", "https://forgelensstorage.blob.core.windows.net/")
    AZURE_STORAGE_CONNECTION_STRING: str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    AZURE_STORAGE_CONTAINER_NAME: str = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "insta-media")

    # --- Azure Cosmos DB (NoSQL) ---
    COSMOS_ENDPOINT: str = os.environ.get("COSMOS_ENDPOINT", "https://forgelens-cosmos.documents.azure.com:443/")
    COSMOS_DATABASE: str = os.environ.get("COSMOS_DATABASE", "insta-agent")
    COSMOS_CONTAINER: str = os.environ.get("COSMOS_CONTAINER", "media-metadata")

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
