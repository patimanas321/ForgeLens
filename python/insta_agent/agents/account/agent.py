"""
InstaAccountAgent — a self-contained Instagram account agent.

Each instance manages one Instagram persona.  It delegates work to
specialist child agents (Trend Scout, Content Strategist, Media Generator,
Copywriter, Review Queue, Publisher) rather than owning tools directly.

Created dynamically from account profile JSON files in data/accounts/.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient

from shared.account_profile import AccountProfile
from shared.base_agent import BaseAgent

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompt_template.md"


class InstaAccountAgent:
    """One agent per Instagram account persona."""

    def __init__(
        self,
        chat_client: AzureOpenAIResponsesClient,
        profile: AccountProfile,
        child_agents: list[BaseAgent] | None = None,
    ) -> None:
        self._profile = profile
        self._chat_client = chat_client
        self._child_agents = child_agents or []

        prompt = self._render_prompt()

        # Specialist child agents exposed as callable tools
        tools = [c.as_tool() for c in self._child_agents]

        self._agent = ChatAgent(
            chat_client=chat_client,
            instructions=prompt,
            id=f"account-{profile.account_name}",
            name=profile.display_name,
            description=f"Instagram account agent for {profile.display_name}. "
                        f"Manages content creation and publishing for @{profile.account_name}.",
            tools=tools,
        )

        logger.info(
            f"[account] Created agent: {profile.display_name} "
            f"({profile.account_name}) with {len(tools)} specialist tools"
        )

    def _render_prompt(self) -> str:
        """Render the prompt template with account-specific values."""
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
        p = self._profile
        persona = p.persona
        rules = p.content_rules
        media = p.media_defaults

        # Build theme and avoid lists as markdown
        themes_list = "\n".join(f"- {t}" for t in persona.themes)
        avoid_list = "\n".join(f"- {a}" for a in persona.avoid)

        return template.format(
            display_name=p.display_name,
            persona_identity=persona.identity,
            persona_appearance=persona.appearance,
            persona_voice=persona.voice,
            persona_tone=persona.tone,
            persona_audience=persona.audience,
            themes_list=themes_list,
            avoid_list=avoid_list,
            visual_style=rules.visual_style,
            caption_style=rules.caption_style,
            image_aspect_ratio=media.image_aspect_ratio,
            reel_aspect_ratio=media.reel_aspect_ratio,
            carousel_aspect_ratio=media.carousel_aspect_ratio,
            video_duration=media.video_duration,
            hashtag_min=rules.hashtag_count.get("min", 15),
            hashtag_max=rules.hashtag_count.get("max", 25),
        )

    @property
    def agent(self) -> ChatAgent:
        return self._agent

    @property
    def profile(self) -> AccountProfile:
        return self._profile
