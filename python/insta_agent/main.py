"""
InstaAgent — Multi-agent Instagram automation system.

Entry point: wires up all agents, creates the orchestrator, and starts the MAF DevServer.

Usage:
    python main.py
    → Opens DevUI at http://127.0.0.1:8080
    → Select "Orchestrator" to start the daily content pipeline
"""

import os
import asyncio
import logging
import webbrowser
import threading

# --- Telemetry (must be before other imports) ---
connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
if connection_string:
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(
        connection_string=connection_string,
        enable_live_metrics=True,
    )

from dotenv import load_dotenv

load_dotenv()

from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework.devui import DevServer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import uvicorn

from shared.config.settings import settings
from agents.orchestrator.agent import OrchestratorAgent
from agents.trend_scout.agent import TrendScoutAgent
from agents.content_strategist.agent import ContentStrategistAgent
from agents.media_generator.agent import MediaGeneratorAgent
from agents.copywriter.agent import CopywriterAgent
from agents.review_queue.agent import ReviewQueueAgent
from agents.publisher.agent import PublisherAgent
from shared.services.media_metadata_service import ensure_cosmos_resources

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("insta_agent")


def main():
    logger.info("Starting InstaAgent multi-agent system...")

    # --- Ensure Cosmos DB database + container exist ---
    if settings.COSMOS_ENDPOINT:
        asyncio.run(ensure_cosmos_resources())
        # Reset the cached Cosmos client — asyncio.run() used a temporary event loop
        # that is now closed. The client will be lazily recreated on uvicorn's loop.
        from shared.services import media_metadata_service
        media_metadata_service._client = None
        media_metadata_service._credential = None
        logger.info("Cosmos DB resources verified")
    else:
        logger.warning("COSMOS_ENDPOINT not set — media metadata will NOT be persisted")

    # --- Azure OpenAI clients (two-tier: strong + lite) ---
    credential = DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID)
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    # gpt5-mini — for orchestrator + complex reasoning (content strategist, media generator)
    # base_url overrides the SDK's hardcoded /openai/v1/ path — the Responses API lives at /openai/
    base_url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/"
    strong_client = AzureOpenAIResponsesClient(
        base_url=base_url,
        deployment_name=settings.AZURE_OPENAI_DEPLOYMENT_STRONG,
        ad_token_provider=token_provider,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    # gpt5-mini — fast & cheap for lighter agents
    lite_client = AzureOpenAIResponsesClient(
        base_url=base_url,
        deployment_name=settings.AZURE_OPENAI_DEPLOYMENT,
        ad_token_provider=token_provider,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    # --- Create specialist agents ---
    # Strong client: content strategist (planning), media generator (prompt engineering)
    # Lite client: trend scout (search), copywriter (text), review queue (routing), publisher (API calls)
    trend_scout = TrendScoutAgent(lite_client)
    content_strategist = ContentStrategistAgent(strong_client)
    media_generator = MediaGeneratorAgent(strong_client)
    copywriter = CopywriterAgent(lite_client)
    review_queue = ReviewQueueAgent(lite_client)
    publisher = PublisherAgent(lite_client)

    logger.info("Specialist agents created (gpt-4o: strategist, media | gpt-4o-mini: scout, copy, review, publish)")

    # --- Create orchestrator (wraps all specialists as tools) ---
    orchestrator = OrchestratorAgent(
        strong_client,
        child_agents=[
            trend_scout,
            content_strategist,
            media_generator,
            copywriter,
            review_queue,
            publisher,
        ],
    )
    logger.info("Orchestrator created with 6 specialist agents as tools")

    # --- Build and start server ---
    server = DevServer(port=settings.PORT, host="127.0.0.1", ui_enabled=True)
    server.register_entities([
        orchestrator.agent,
        trend_scout.agent,
        content_strategist.agent,
        media_generator.agent,
        copywriter.agent,
        review_queue.agent,
        publisher.agent,
    ])

    url = f"http://127.0.0.1:{settings.PORT}"
    logger.info(f"InstaAgent DevUI: {url}")
    logger.info("Select 'Orchestrator' in the UI to start the daily content pipeline")
    logger.info("Or select individual agents to test them directly")

    # Auto-open browser after a short delay (gives uvicorn time to bind)
    threading.Timer(1.5, webbrowser.open, args=[url]).start()

    uvicorn.run(server.get_app(), host="127.0.0.1", port=settings.PORT)


if __name__ == "__main__":
    main()
