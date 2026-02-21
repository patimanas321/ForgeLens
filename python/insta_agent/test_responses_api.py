"""Test Responses API endpoint with gpt5-mini."""
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import httpx, time

cred = DefaultAzureCredential(managed_identity_client_id="02911707-a3a0-49b8-8ab0-4a8f0c9a5830")
token_provider = get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default")
token = token_provider()

endpoint = "https://forgelens-openai.openai.azure.com"

# Test the Responses API endpoint (what AzureOpenAIResponsesClient actually uses)
for ver in ["2025-04-01-preview", "2025-03-01-preview", "2024-12-01-preview"]:
    url = f"{endpoint}/openai/deployments/gpt5-mini/responses?api-version={ver}"
    try:
        r = httpx.post(
            url,
            json={"input": "Say hi", "model": "gpt5-mini"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"Responses API {ver}: OK ✓")
        else:
            err = r.json().get("error", {}).get("message", "unknown")[:100]
            print(f"Responses API {ver}: {r.status_code} — {err}")
    except Exception as e:
        print(f"Responses API {ver}: ERROR — {e}")
    time.sleep(2)
