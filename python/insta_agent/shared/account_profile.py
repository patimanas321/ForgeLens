"""
Account Profiles — loads persona configurations from data/accounts/*.json.

Each JSON file defines one Instagram account persona. The profile includes:
  - Instagram account mapping (links to Key Vault secret)
  - Persona (identity, voice, tone, themes)
  - Content rules (formats, cadence, hashtag policy)
  - Media defaults (aspect ratios, resolution)

Adding a new account = drop a new JSON file + add the KV secret.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

ACCOUNTS_DIR = Path(__file__).parent.parent / "data" / "accounts"


@dataclass
class AccountPersona:
    identity: str
    appearance: str
    voice: str
    tone: str
    audience: str
    themes: list[str]
    avoid: list[str]


@dataclass
class ContentRules:
    formats: list[str]
    posting_cadence: str
    hashtag_count: dict[str, int]
    caption_style: str
    visual_style: str
    content_type_frequency: dict[str, str] = field(default_factory=dict)


@dataclass
class MediaDefaults:
    image_aspect_ratio: str = "4:5"
    reel_aspect_ratio: str = "9:16"
    carousel_aspect_ratio: str = "1:1"
    image_resolution: str = "1K"
    video_duration: int = 5


@dataclass
class AccountProfile:
    account_name: str
    display_name: str
    instagram_account_key: str  # maps to KV secret instagram-account-{key}
    persona: AccountPersona
    content_rules: ContentRules
    media_defaults: MediaDefaults


def _parse_profile(data: dict) -> AccountProfile:
    """Parse a raw JSON dict into a typed AccountProfile."""
    return AccountProfile(
        account_name=data["account_name"],
        display_name=data["display_name"],
        instagram_account_key=data["instagram_account_key"],
        persona=AccountPersona(**data["persona"]),
        content_rules=ContentRules(**data["content_rules"]),
        media_defaults=MediaDefaults(**data.get("media_defaults", {})),
    )


def load_all_profiles() -> dict[str, AccountProfile]:
    """Load all account profiles from data/accounts/*.json."""
    profiles: dict[str, AccountProfile] = {}
    if not ACCOUNTS_DIR.exists():
        logger.warning(f"Accounts directory not found: {ACCOUNTS_DIR}")
        return profiles

    for path in sorted(ACCOUNTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profile = _parse_profile(data)
            profiles[profile.account_name] = profile
            logger.info(f"[account] Loaded profile: {profile.display_name} ({profile.account_name})")
        except Exception as e:
            logger.error(f"[account] Failed to load {path.name}: {e}")

    return profiles


def load_profile(name: str) -> AccountProfile:
    """Load a single account profile by name."""
    path = ACCOUNTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Account profile not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_profile(data)
