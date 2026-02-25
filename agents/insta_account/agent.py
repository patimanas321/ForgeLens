"""
InstaAccountAgent — a per-profile Instagram account agent.

Each instance manages one Instagram persona. It delegates work to
specialist child agents (Trend Scout, Content Reviewer), while handling
strategy/copywriting and account-scoped queue operations internally.

Created dynamically from account profile JSON files in insta_profiles/.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agent_framework.azure import AzureOpenAIResponsesClient

from account_profile import AccountProfile
from agent_registry import Agent
from config.settings import settings
from agents.base_agent import BaseAgent
from .tools import build_account_tools

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompt_template.md"


class InstaAccountAgent(BaseAgent):
    """One agent per Instagram account persona."""

    agent_id = Agent.INSTA_ACCOUNT

    def __init__(
        self,
        chat_client: AzureOpenAIResponsesClient,
        profile: AccountProfile,
        child_agents: list[BaseAgent] | None = None,
    ) -> None:
        self._profile = profile
        # BaseAgent.__init__ calls _build_tools(), _load_prompt(),
        # and the _agent_config_*() hooks — all of which read self._profile.
        super().__init__(chat_client, child_agents=child_agents)

        logger.info(
            "[account] Created agent: %s (%s) with %d total tools",
            profile.display_name,
            profile.account_name,
            len(self._agent.tools),
        )

    # ------------------------------------------------------------------
    # BaseAgent overrides
    # ------------------------------------------------------------------

    def _agent_config_id(self) -> str:
        return f"account-{self._profile.account_name}"

    def _agent_config_name(self) -> str:
        return self._profile.display_name

    def _agent_config_description(self) -> str:
        return (
            f"Instagram account agent for {self._profile.display_name}. "
            f"Manages content creation and publishing for @{self._profile.account_name}."
        )

    def _load_prompt(self) -> str:
        """Render the prompt template with account-specific values."""
        template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
        p = self._profile
        persona = p.persona
        rules = p.content_rules
        media = p.media_defaults

        themes_list = "\n".join(f"- {t}" for t in persona.themes)
        avoid_list = "\n".join(f"- {a}" for a in persona.avoid)
        frequency_map = rules.content_type_frequency or {}
        content_type_frequency_list = (
            "\n".join(f"- {k}: {v}" for k, v in frequency_map.items())
            if frequency_map
            else "- Not configured"
        )

        return template.format(
            display_name=p.display_name,
            persona_identity=persona.identity,
            persona_appearance=persona.appearance,
            persona_voice=persona.voice,
            persona_tone=persona.tone,
            persona_audience=persona.audience,
            themes_list=themes_list,
            avoid_list=avoid_list,
            content_type_frequency_list=content_type_frequency_list,
            visual_style=rules.visual_style,
            caption_style=rules.caption_style,
            image_aspect_ratio=media.image_aspect_ratio,
            reel_aspect_ratio=media.reel_aspect_ratio,
            carousel_aspect_ratio=media.carousel_aspect_ratio,
            video_duration=media.video_duration,
            hashtag_min=rules.hashtag_count.get("min", 15),
            hashtag_max=rules.hashtag_count.get("max", 25),
        )

    def _build_tools(self) -> list:
        account_id = settings.INSTAGRAM_ACCOUNTS.get(self._profile.account_name, "")
        return build_account_tools(
            self._profile,
            target_account_id=account_id,
            frequency_targets=self._profile.content_rules.content_type_frequency,
        )

    @property
    def profile(self) -> AccountProfile:
        return self._profile
