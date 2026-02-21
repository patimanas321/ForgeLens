"""Test alternative Responses API paths for Azure OpenAI."""
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import httpx, time

cred = DefaultAzureCredential(managed_identity_client_id="02911707-a3a0-49b8-8ab0-4a8f0c9a5830")
token_provider = get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default")
token = token_provider()

endpoint = "https://forgelens-openai.openai.azure.com"
headers = {"Authorization": f"Bearer {token}"}
body = {"input": "Say hi", "model": "gpt5-mini"}

paths = [
    # deployment-scoped
    "/openai/deployments/gpt5-mini/responses",
    "/openai/deployments/gpt-4o/responses",
    # non-deployment-scoped (model in body)
    "/openai/responses",
    # v1 prefix
    "/v1/responses",
]

versions = ["2025-04-01-preview", "2025-03-01-preview", "2024-12-01-preview"]

for path in paths:
    for ver in versions:
        url = f"{endpoint}{path}?api-version={ver}"
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=10)
            status = r.status_code
            if status == 200:
                print(f"{path} @ {ver}: OK ✓")
            elif status == 429:
                print(f"{path} @ {ver}: 429 RATE LIMITED (endpoint exists!)")
            else:
                err = r.json().get("error", {}).get("message", "?")[:80]
                print(f"{path} @ {ver}: {status} — {err}")
        except Exception as e:
            print(f"{path} @ {ver}: ERROR — {e}")
        time.sleep(1)
    print()
