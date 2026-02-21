"""Test the Responses API with the correct path for gpt5-mini."""
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import httpx

cred = DefaultAzureCredential(managed_identity_client_id="02911707-a3a0-49b8-8ab0-4a8f0c9a5830")
token_provider = get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default")
token = token_provider()

endpoint = "https://forgelens-openai.openai.azure.com"
body = {"model": "gpt5-mini", "input": "Say hello in one word."}
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

url = f"{endpoint}/openai/responses?api-version=2025-03-01-preview"
r = httpx.post(url, json=body, headers=headers, timeout=30)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Response ID: {data.get('id')}")
    output = data.get("output", [])
    for item in output:
        if item.get("type") == "message":
            for c in item.get("content", []):
                print(f"Text: {c.get('text', '')}")
else:
    print(r.text[:300])
