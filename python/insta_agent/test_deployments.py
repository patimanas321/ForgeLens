"""Test Responses API for gpt-4o vs gpt5-mini."""
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import httpx, time

cred = DefaultAzureCredential(managed_identity_client_id="02911707-a3a0-49b8-8ab0-4a8f0c9a5830")
token_provider = get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default")
token = token_provider()

endpoint = "https://forgelens-openai.openai.azure.com"
ver = "2025-04-01-preview"

for deployment in ["gpt-4o", "gpt-4o-mini", "gpt5-mini"]:
    url = f"{endpoint}/openai/deployments/{deployment}/responses?api-version={ver}"
    try:
        r = httpx.post(
            url,
            json={"input": "Say hi in 3 words", "model": deployment},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"{deployment}: OK ✓")
        else:
            err = r.json().get("error", {}).get("message", "unknown")[:120]
            print(f"{deployment}: {r.status_code} — {err}")
    except Exception as e:
        print(f"{deployment}: ERROR — {e}")
    time.sleep(2)
