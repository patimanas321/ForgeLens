"""
Azure Key Vault secret loader.

Reads secrets at startup and caches them in-process.
Supports multi-account Instagram via 'instagram-account-*' naming convention.

Usage:
    from shared.config.keyvault import kv

    token = kv.get("instagram-access-token")
    accounts = kv.instagram_accounts          # {"oreo": "17841448781212376", ...}
"""

import logging
import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)

# Key Vault URL — set in .env or environment
_VAULT_URL = os.environ.get(
    "AZURE_KEYVAULT_URL", "https://forgelens-kv.vault.azure.net/"
)

# Secrets we expect to find in KV
_SECRET_NAMES = [
    "instagram-access-token",
    "fal-key",
    "tavily-api-key",
]

# Prefix for multi-account Instagram Business Account IDs
_IG_ACCOUNT_PREFIX = "instagram-account-"


class KeyVaultStore:
    """Thin cache around Azure Key Vault secrets."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._instagram_accounts: dict[str, str] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Fetch all expected secrets + discover instagram-account-* secrets."""
        if self._loaded:
            return

        try:
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=_VAULT_URL, credential=credential)

            # Load known secrets
            for name in _SECRET_NAMES:
                try:
                    secret = client.get_secret(name)
                    self._cache[name] = secret.value or ""
                    logger.info(f"[KV] Loaded secret: {name}")
                except Exception as exc:
                    logger.warning(f"[KV] Could not load '{name}': {exc}")

            # Discover all instagram-account-* secrets (multi-account)
            for secret_props in client.list_properties_of_secrets():
                if secret_props.name.startswith(_IG_ACCOUNT_PREFIX) and secret_props.enabled:
                    account_name = secret_props.name[len(_IG_ACCOUNT_PREFIX):]
                    secret = client.get_secret(secret_props.name)
                    self._instagram_accounts[account_name] = secret.value or ""
                    self._cache[secret_props.name] = secret.value or ""
                    logger.info(f"[KV] Loaded IG account: {account_name}")

            self._loaded = True
            logger.info(
                f"[KV] Loaded {len(self._cache)} secrets, "
                f"{len(self._instagram_accounts)} IG account(s): "
                f"{list(self._instagram_accounts.keys())}"
            )

        except Exception as exc:
            logger.warning(f"[KV] Key Vault unavailable — falling back to env vars: {exc}")
            self._loaded = True  # Don't retry on every access

    def get(self, name: str, default: str = "") -> str:
        """Get a secret by name (from cache)."""
        self.load()
        return self._cache.get(name, default)

    @property
    def instagram_accounts(self) -> dict[str, str]:
        """Map of account-name → Instagram Business Account ID."""
        self.load()
        return dict(self._instagram_accounts)

    @property
    def default_instagram_account(self) -> tuple[str, str]:
        """Returns (name, account_id) for the first IG account, or ("", "")."""
        self.load()
        if self._instagram_accounts:
            name = next(iter(self._instagram_accounts))
            return name, self._instagram_accounts[name]
        return "", ""


# Module-level singleton — import as `from shared.config.keyvault import kv`
kv = KeyVaultStore()
