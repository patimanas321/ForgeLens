"""
ForgeLens — Per-account Instagram automation agents.

Entry point: discovers account profiles from data/accounts/*.json,
creates one InstaAccountAgent per profile, and starts the MAF DevServer.

Usage:
    python main.py
    → Opens DevUI at http://127.0.0.1:8080
    → Each Instagram account appears as its own agent
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
from shared.account_profile import load_all_profiles
from agents.account.agent import InstaAccountAgent
from agents.account.workflow import build_content_pipeline
from agents.trend_scout.agent import TrendScoutAgent
from agents.insta_post_generator.agent import InstaPostGeneratorAgent
from agents.approver.agent import ReviewQueueAgent
from agents.communicator.agent import CommunicatorAgent
from agents.publisher.agent import PublisherAgent
from shared.services.media_metadata_service import ensure_cosmos_resources
from shared.services.review_queue_service import ensure_servicebus_queues
from shared.services.communicator_trigger_service import start_communicator_queue_trigger_worker
from shared.services.publisher_trigger_service import start_publisher_queue_trigger_worker

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forgelens")


def main():
    logger.info("Starting ForgeLens...")

    # --- Ensure Cosmos DB database + container exist ---
    if settings.COSMOS_ENDPOINT:
        asyncio.run(ensure_cosmos_resources())
        from shared.services import media_metadata_service
        media_metadata_service._client = None
        media_metadata_service._credential = None
        logger.info("Cosmos DB resources verified")
    else:
        logger.warning("COSMOS_ENDPOINT not set — media metadata will NOT be persisted")

    # --- Ensure Service Bus queues exist ---
    if settings.SERVICEBUS_NAMESPACE:
        asyncio.run(ensure_servicebus_queues())
        logger.info("Service Bus queues verified")
    else:
        logger.warning("SERVICEBUS_NAMESPACE not set — review queue will not work")

    # --- Azure OpenAI client ---
    credential = DefaultAzureCredential(managed_identity_client_id=settings.AZURE_CLIENT_ID)
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    base_url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/"
    ai_client = AzureOpenAIResponsesClient(
        base_url=base_url,
        deployment_name=settings.AZURE_OPENAI_DEPLOYMENT,
        ad_token_provider=token_provider,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    # --- Create delegable specialist agents (shared across all accounts) ---
    trend_scout_agent = TrendScoutAgent(ai_client)
    insta_post_generator_agent = InstaPostGeneratorAgent(ai_client)
    approver_agent = ReviewQueueAgent(ai_client)
    communicator_agent = CommunicatorAgent(ai_client)

    # Publisher is standalone: queue listener + content_id publisher
    publisher_agent = PublisherAgent(ai_client)

    # --- Discover account profiles and create one agent per account ---
    profiles = load_all_profiles()
    if not profiles:
        logger.error("No account profiles found in data/accounts/*.json — nothing to start")
        return

    account_agents: list[InstaAccountAgent] = []
    pipeline_agents = []

    for name, profile in profiles.items():
        # Account agent — conversational persona with specialist tools
        agent = InstaAccountAgent(
            ai_client,
            profile,
            child_agents=[
                trend_scout_agent,
                insta_post_generator_agent,
                communicator_agent,
            ],
        )
        account_agents.append(agent)

        # Content pipeline — MAF sequential workflow with HIL before publishing
        pipeline = build_content_pipeline(
            trend_scout=trend_scout_agent,
            insta_post_generator=insta_post_generator_agent,
            account_name=profile.account_name,
            display_name=profile.display_name,
        )
        pipeline_agents.append(pipeline)

    logger.info(f"Created {len(account_agents)} account agent(s): {[a.profile.display_name for a in account_agents]}")
    logger.info(f"Created {len(pipeline_agents)} content pipeline(s)")

    if settings.SERVICEBUS_NAMESPACE:
        start_communicator_queue_trigger_worker(
            poll_interval_seconds=20,
            communicator_agent=communicator_agent.agent,
        )
        start_publisher_queue_trigger_worker(
            poll_interval_seconds=20,
            publisher_agent=publisher_agent.agent,
        )

    # --- Build and start server ---
    all_entities = (
        [a.agent for a in account_agents]   # Account persona agents
        + pipeline_agents                    # Content pipeline workflows
        + [
            trend_scout_agent.agent,
            insta_post_generator_agent.agent,
            communicator_agent.agent,
            approver_agent.agent,
        ]
        + [publisher_agent.agent]            # Standalone publisher agent
    )
    server = DevServer(port=settings.PORT, host="127.0.0.1", ui_enabled=True)
    server.register_entities(all_entities)

    url = f"http://127.0.0.1:{settings.PORT}"
    logger.info(f"ForgeLens DevUI: {url}")
    logger.info("Select an account in the UI to start creating content")

    threading.Timer(1.5, webbrowser.open, args=[url]).start()

    uvicorn.run(server.get_app(), host="127.0.0.1", port=settings.PORT)


if __name__ == "__main__":
    main()
