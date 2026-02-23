# Building Multi-Agent Systems with Microsoft Agent Framework (Python)

A practical guide to building **multi-agent AI systems** using [Microsoft Agent Framework (MAF)](https://learn.microsoft.com/en-us/agent-framework/) and Azure OpenAI. This document covers the patterns, architecture, and reusable code needed to build an orchestrator that routes user requests to specialized child agents — each with its own tools.

> **Prerequisites:** Familiarity with Python, Azure OpenAI, and basic agent concepts. See the [official MAF get-started guide](https://learn.microsoft.com/en-us/agent-framework/get-started/) for introductory material.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running Locally](#running-locally)
- [Core Concepts](#core-concepts)
  - [Orchestrator + Specialist Pattern](#orchestrator--specialist-pattern)
  - [Agent Registry](#agent-registry)
  - [Base Agent](#base-agent)
  - [Tools](#tools)
    - [Function Tools (Local)](#function-tools-local)
    - [MCP Tools (Remote)](#mcp-tools-remote)
  - [Hosting with DevServer](#hosting-with-devserver)
- [Patterns & Recipes](#patterns--recipes)
  - [Agent-as-Tool Routing](#agent-as-tool-routing)
  - [Authenticated Service Layer](#authenticated-service-layer)
  - [MCP with On-Behalf-Of Auth](#mcp-with-on-behalf-of-auth)
  - [ContextVar Propagation in ASGI](#contextvar-propagation-in-asgi)
  - [Prompt Engineering for Multi-Agent](#prompt-engineering-for-multi-agent)
- [Adding a New Agent](#adding-a-new-agent)
- [API Endpoints](#api-endpoints)
- [Deployment to Azure App Service](#deployment-to-azure-app-service)
- [Telemetry](#telemetry)
- [Design Decisions & Gotchas](#design-decisions--gotchas)
- [Dependencies](#dependencies)
- [Further Reading](#further-reading)

---

## Architecture

A multi-agent system built with MAF follows a **hierarchical orchestrator pattern**:

```
┌─────────────────────────────────────────────────────────────────┐
│                       Your Application                          │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Orchestrator Agent                            │ │
│  │                                                            │ │
│  │  Tools:                                                    │ │
│  │    call_agent_a  →  Agent A  (specialist)                  │ │
│  │    call_agent_b  →  Agent B  (specialist)                  │ │
│  │    call_agent_c  →  Agent C  (specialist)                  │ │
│  └──────┬──────────────────┬──────────────────┬───────────────┘ │
│         │                  │                  │                  │
│   ┌─────▼──────┐    ┌─────▼──────┐    ┌──────▼─────┐          │
│   │  Agent A   │    │  Agent B   │    │  Agent C   │          │
│   │  N tools   │    │  M tools   │    │  K tools   │          │
│   └─────┬──────┘    └─────┬──────┘    └──────┬─────┘          │
│         │                 │                  │                  │
│   ┌─────▼──────┐   ┌─────▼──────────────────▼──────┐          │
│   │ REST APIs  │   │  MCP Servers / Other backends  │          │
│   └────────────┘   └───────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

**How it works:**

1. The **Orchestrator** receives the user's question and decides which specialist to invoke.
2. Each **Specialist Agent** is exposed to the orchestrator as a callable tool via MAF's `ChatAgent.as_tool()`.
3. When the LLM routes a query (e.g., `call_agent_a(request="...")`), it triggers a full sub-conversation with that specialist and its tools.
4. Each specialist has its own tools — either **local function tools** (calling REST APIs directly) or **MCP tools** (calling remote MCP servers).

---

## Project Structure

A recommended structure for a multi-agent MAF application:

```
my-multi-agent-app/
├── main.py                        # Entry point — wiring, server startup
├── agent_registry.py              # Agent enum + metadata registry
├── requirements.txt
├── agents/
│   ├── __init__.py
│   ├── orchestrator/
│   │   ├── agent.py               # Orchestrator agent class
│   │   └── prompt.md              # System prompt (routing rules)
│   ├── agent_a/
│   │   ├── agent.py               # Specialist agent class
│   │   ├── tools.py               # Local FunctionTool definitions
│   │   └── prompt.md              # System prompt (tool selection rules)
│   └── agent_b/
│       ├── agent.py               # Specialist — uses MCP tools
│       └── prompt.md
└── shared/
    ├── base_agent.py              # Abstract base agent
    ├── config/
    │   ├── settings.py            # Environment-based settings
    │   └── auth.py                # Auth configuration
    ├── auth/
    │   ├── factory.py             # Auth provider factory
    │   └── providers/             # OBO, CLI, MI auth providers
    ├── middlewares/
    │   └── user_context.py        # ASGI middleware for user tokens
    ├── services/
    │   ├── base_service.py        # Authenticated HTTP base class
    │   └── your_service.py        # Domain-specific API client
    └── mcp/
        ├── __init__.py            # MCP tool loader
        ├── cached_tools.py        # Cached MCP schemas + OBO wrapper
        └── tool_cache/            # Pre-discovered MCP tool schemas (JSON)
```

**Key conventions:**
- Each agent lives in its own directory under `agents/` with an `agent.py` and `prompt.md`.
- Shared infrastructure (auth, services, config) lives under `shared/`.
- An **agent registry** at the project root defines all agent identities and routing metadata.

---

## Getting Started

### Installation

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

Minimal `requirements.txt`:

```
agent-framework[azure,devui]==1.0.0b260130
azure-identity>=1.19.0
python-dotenv>=1.0.0
httpx>=0.27.0
pydantic>=2.0.0
```

### Configuration

Create a `.env` file:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2025-04-01-preview
PORT=8080
```

Load settings from environment:

```python
# shared/config/settings.py
import os

class Settings:
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    PORT = int(os.environ.get("PORT", "8080"))

settings = Settings()
```

### Running Locally

```bash
python main.py
```

The MAF DevUI opens at `http://127.0.0.1:8080` — select any registered agent to start chatting.

---

## Core Concepts

### Orchestrator + Specialist Pattern

The orchestrator doesn't call tools directly. Instead, each specialist agent is wrapped as a tool via `ChatAgent.as_tool()`. When the LLM decides to route a query, it invokes the specialist, which runs its own sub-conversation with its own tools and prompt.

```python
from agent_framework import ChatAgent

# Create specialist agents
agent_a = ChatAgent(chat_client=client, instructions="...", name="Agent A", tools=[...])
agent_b = ChatAgent(chat_client=client, instructions="...", name="Agent B", tools=[...])

# Create orchestrator — specialists become callable tools
orchestrator = ChatAgent(
    chat_client=client,
    instructions="Route user questions to the right specialist.",
    name="Orchestrator",
    tools=[
        agent_a.as_tool(
            name="call_agent_a",
            description="Handles domain A questions.",
            arg_name="request",
            arg_description="The user's question to forward.",
        ),
        agent_b.as_tool(
            name="call_agent_b",
            description="Handles domain B questions.",
            arg_name="request",
            arg_description="The user's question to forward.",
        ),
    ],
)
```

This is the MAF equivalent of the [Using an Agent as a Function Tool](https://learn.microsoft.com/en-us/agent-framework/agents/tools/#using-an-agent-as-a-function-tool) pattern from the official docs.

### Agent Registry

To avoid scattering agent metadata across multiple files, define a **single registry**:

```python
# agent_registry.py
from dataclasses import dataclass, field
from enum import Enum


class Agent(str, Enum):
    """Canonical agent identifiers."""
    ORCHESTRATOR = "orchestrator"
    AGENT_A = "agent-a"
    AGENT_B = "agent-b"


@dataclass(frozen=True)
class AgentEntry:
    """Metadata for a single agent."""
    name: str
    description: str
    tool_name: str = ""           # e.g. "call_agent_a"
    arg_name: str = field(default="request")
    arg_description: str = ""


AGENT_REGISTRY: dict[Agent, AgentEntry] = {
    Agent.ORCHESTRATOR: AgentEntry(
        name="Orchestrator",
        description="Routes user queries to the right specialist.",
    ),
    Agent.AGENT_A: AgentEntry(
        name="Agent A",
        description="Handles domain A questions.",
        tool_name="call_agent_a",
        arg_description="The user's question about domain A.",
    ),
    Agent.AGENT_B: AgentEntry(
        name="Agent B",
        description="Handles domain B questions.",
        tool_name="call_agent_b",
        arg_description="The user's question about domain B.",
    ),
}
```

Both the base agent (for `ChatAgent` identity) and the orchestrator (for `as_tool()` metadata) read from the same registry — one place to update.

### Base Agent

An abstract base class keeps agent boilerplate in one place:

```python
# shared/base_agent.py
import inspect
from abc import ABC
from pathlib import Path

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient
from agent_registry import AGENT_REGISTRY, Agent


class BaseAgent(ABC):
    """Abstract base — subclasses declare agent_id and optionally override _build_tools()."""

    agent_id: Agent
    mcp_servers: list[str] = []

    def __init__(self, chat_client: AzureOpenAIResponsesClient) -> None:
        self._chat_client = chat_client
        entry = AGENT_REGISTRY[self.agent_id]

        self._agent = ChatAgent(
            chat_client=chat_client,
            instructions=self._load_prompt(),
            id=self.agent_id.value,
            name=entry.name,
            description=entry.description,
            tools=self._build_tools(),
        )

    def _load_prompt(self) -> str:
        """Load prompt.md from the subclass's directory."""
        subclass_dir = Path(inspect.getfile(type(self))).parent
        return (subclass_dir / "prompt.md").read_text(encoding="utf-8")

    def _build_tools(self) -> list:
        """Override to return FunctionTool instances or MCP tools."""
        return []

    @property
    def agent(self) -> ChatAgent:
        return self._agent

    def as_tool(self) -> object:
        """Wrap this agent as a callable tool using registry metadata."""
        entry = AGENT_REGISTRY[self.agent_id]
        return self._agent.as_tool(
            name=entry.tool_name,
            description=entry.description,
            arg_name=entry.arg_name,
            arg_description=entry.arg_description,
        )
```

A specialist agent is then minimal:

```python
# agents/agent_a/agent.py
from agent_registry import Agent
from shared.base_agent import BaseAgent
from .tools import build_agent_a_tools


class AgentA(BaseAgent):
    agent_id = Agent.AGENT_A

    def _build_tools(self) -> list:
        return build_agent_a_tools()
```

And the orchestrator wraps children:

```python
# agents/orchestrator/agent.py
from agent_registry import Agent
from shared.base_agent import BaseAgent


class Orchestrator(BaseAgent):
    agent_id = Agent.ORCHESTRATOR

    def __init__(self, chat_client, child_agents):
        self._child_agents = child_agents
        super().__init__(chat_client)

    def _build_tools(self) -> list:
        return [child.as_tool() for child in self._child_agents]
```

### Tools

MAF supports several [tool types](https://learn.microsoft.com/en-us/agent-framework/agents/tools/). For multi-agent systems, two are most common:

#### Function Tools (Local)

Use `FunctionTool` when you want to call a REST API or run custom logic directly. Define a Pydantic model for the input schema and an async function:

```python
# agents/agent_a/tools.py
from agent_framework import FunctionTool
from pydantic import BaseModel, Field


class ItemIdInput(BaseModel):
    item_id: int = Field(..., ge=1, description="Item identifier")


async def get_item_details(item_id: int) -> dict:
    """Fetch item details from your API."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.example.com/items/{item_id}")
        resp.raise_for_status()
        return resp.json()


def build_agent_a_tools() -> list[FunctionTool]:
    return [
        FunctionTool(
            name="get_item_details",
            description="Get metadata about an item.",
            input_model=ItemIdInput,
            func=get_item_details,
        ),
    ]
```

> **Important:** MAF's `FunctionTool` decomposes the Pydantic model via `model.model_dump()` and calls `func(**kwargs)`. Your function must accept **keyword arguments matching the model fields** — not the model instance itself.

#### MCP Tools (Remote)

For agents that connect to [MCP (Model Context Protocol)](https://learn.microsoft.com/en-us/agent-framework/agents/tools/) servers, MAF provides built-in support:

```python
from agent_framework import MCPStreamableHTTPTool

# Auto-discovers tools from the MCP server at startup
mcp_tool = MCPStreamableHTTPTool(url="https://my-mcp-server.com/mcp")
```

For MCP servers **requiring per-user authentication**, see the [MCP with On-Behalf-Of Auth](#mcp-with-on-behalf-of-auth) pattern below.

### Hosting with DevServer

MAF's `DevServer` provides a built-in web UI for testing and an SSE-based API endpoint:

```python
# main.py
from agent_framework.azure import AzureOpenAIResponsesClient
from agent_framework.devui import DevServer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import uvicorn

from shared.config import settings
from agents.orchestrator.agent import Orchestrator
from agents.agent_a.agent import AgentA
from agents.agent_b.agent import AgentB


def main():
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )

    chat_client = AzureOpenAIResponsesClient(
        endpoint=settings.AZURE_OPENAI_ENDPOINT,
        deployment_name=settings.AZURE_OPENAI_DEPLOYMENT,
        ad_token_provider=token_provider,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

    # Create agents
    agent_a = AgentA(chat_client)
    agent_b = AgentB(chat_client)
    orchestrator = Orchestrator(chat_client, child_agents=[agent_a, agent_b])

    # Build server
    server = DevServer(port=settings.PORT, host="127.0.0.1", ui_enabled=True)
    server.register_entities([orchestrator.agent, agent_a.agent, agent_b.agent])

    uvicorn.run(server.get_app(), host="127.0.0.1", port=settings.PORT)


if __name__ == "__main__":
    main()
```

> **Note:** `AzureOpenAIResponsesClient` uses `endpoint=` (not `azure_endpoint=`) and `ad_token_provider=` (not `azure_ad_token_provider=`). These differ from the standard Azure OpenAI SDK.

---

## Patterns & Recipes

### Agent-as-Tool Routing

The orchestrator's prompt should include routing rules so the LLM knows which specialist to invoke:

```markdown
## Routing Rules

- Questions about items, inventory → call_agent_a
- Questions about analytics, reports → call_agent_b
- If unclear, ask the user to clarify
```

The `as_tool()` method creates a `FunctionTool` wrapper around the specialist. When invoked, it runs a full conversation turn with the specialist's LLM, prompt, and tools — then returns the result to the orchestrator.

### Authenticated Service Layer

For agents calling REST APIs that require Bearer tokens, create a base service class:

```python
# shared/services/base_service.py
import httpx
import logging

logger = logging.getLogger(__name__)


class BaseService:
    def __init__(self, base_url: str, auth_provider=None, scope: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self._auth_provider = auth_provider
        self._scope = scope

    async def _get_headers(self) -> dict[str, str]:
        if self._auth_provider and self._scope:
            token = await self._auth_provider.acquire_access_token(self._scope)
            return {"Authorization": f"Bearer {token.access_token}"}
        return {}

    async def _make_request(self, url: str, *, method: str = "GET", json=None) -> dict:
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, headers=headers, json=json)
            resp.raise_for_status()
            return resp.json()
```

Then create domain-specific services:

```python
# shared/services/my_service.py
from shared.services.base_service import BaseService


class MyService(BaseService):
    def __init__(self):
        super().__init__(
            base_url="https://api.example.com",
            scope="api://your-app-id/.default",
        )

    async def get_item(self, item_id: int) -> dict:
        return await self._make_request(f"{self.base_url}/items/{item_id}")
```

### MCP with On-Behalf-Of Auth

When MCP servers require per-user authentication, there's a **chicken-and-egg problem**: tool discovery needs a token, but at startup there's no user request.

**Solution: Cache MCP tool schemas offline, authenticate at call time.**

1. **Discover tools offline** (using your `az login` credential):
   ```bash
   curl -X POST https://mcp-server.example.com/mcp \
     -H "Authorization: Bearer <your-token>" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
   ```

2. **Save the response** as a JSON file (e.g., `shared/mcp/tool_cache/my-server.json`):
   ```json
   {
     "server_url": "https://mcp-server.example.com/mcp",
     "scope": "api://mcp-app-id/.default",
     "tools": [
       {
         "name": "my_tool",
         "description": "Does something useful.",
         "inputSchema": {
           "type": "object",
           "properties": { "id": { "type": "integer" } },
           "required": ["id"]
         }
       }
     ]
   }
   ```

3. **At startup**, create `FunctionTool` wrappers from the cached schemas — no network calls needed.

4. **At runtime**, when the LLM invokes a tool:
   - Read the user's token from a `ContextVar` (set by middleware).
   - Exchange it for a downstream token via OBO.
   - Send a JSON-RPC `tools/call` request to the MCP server with the exchanged token.

### ContextVar Propagation in ASGI

When building ASGI apps that use `ContextVar` with streaming responses (SSE, WebSockets):

> **Always use pure ASGI middleware.** Starlette's `BaseHTTPMiddleware` runs response streaming in a separate asyncio `Task`, which means `ContextVar` values set in `dispatch()` are invisible during SSE streaming.

```python
# ❌ BROKEN — ContextVar lost during SSE streaming
from starlette.middleware.base import BaseHTTPMiddleware

class MyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        my_var.set("value")
        return await call_next(request)  # streams in different task!
```

```python
# ✅ CORRECT — ContextVar survives through SSE
class MyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract context from headers...
            token = my_var.set("value")
            try:
                await self.app(scope, receive, send)  # same task!
            finally:
                my_var.reset(token)
        else:
            await self.app(scope, receive, send)
```

This is critical for multi-agent systems where tool calls happen during LLM response streaming and need access to the user's auth token.

### Prompt Engineering for Multi-Agent

Each agent should have a `prompt.md` with:

| Section | Purpose |
|---------|---------|
| **Role definition** | "You are [Agent Name], responsible for..." |
| **Tool catalog** | Table of available tools with purpose and when to use each |
| **Tool selection rules** | Numbered rules mapping user intent → specific tools |
| **Response format** | Tables, status indicators, brevity expectations |
| **Error handling** | Fallback instructions when a tool fails |

The **orchestrator prompt** additionally needs **routing rules** — mapping domains to specialist agents.

Prompts are loaded automatically by the base agent from `prompt.md` adjacent to the subclass:

```python
# BaseAgent._load_prompt()
subclass_dir = Path(inspect.getfile(type(self))).parent
return (subclass_dir / "prompt.md").read_text(encoding="utf-8")
```

---

## Adding a New Agent

1. **Register in `agent_registry.py`:**
   ```python
   class Agent(str, Enum):
       # ... existing ...
       MY_AGENT = "my-agent"

   AGENT_REGISTRY[Agent.MY_AGENT] = AgentEntry(
       name="My Agent",
       description="Handles domain X questions.",
       tool_name="call_my_agent",
       arg_description="The user's question about domain X.",
   )
   ```

2. **Create the agent directory:**
   ```
   agents/my_agent/
   ├── agent.py
   ├── tools.py       # if using local tools
   └── prompt.md
   ```

3. **Define the agent class:**
   ```python
   # agents/my_agent/agent.py
   from agent_registry import Agent
   from shared.base_agent import BaseAgent
   from .tools import build_my_tools

   class MyAgent(BaseAgent):
       agent_id = Agent.MY_AGENT

       def _build_tools(self) -> list:
           return build_my_tools()
   ```

4. **Write `prompt.md`** with role, tools, selection rules, and formatting.

5. **Wire into `main.py`:**
   ```python
   from agents.my_agent.agent import MyAgent

   my = MyAgent(chat_client)
   orchestrator = Orchestrator(chat_client, child_agents=[..., my])
   server.register_entities([..., my.agent])
   ```

6. **Update the orchestrator's `prompt.md`** with routing rules for the new agent.

---

## API Endpoints

The MAF `DevServer` exposes an **OpenAI Responses API**-compatible endpoint. This means any OpenAI-compatible client library can talk to your multi-agent system out of the box.

### Main Endpoint

#### `POST /v1/responses`

Send a user message to a specific agent and receive a response (optionally streamed via SSE).

```http
POST /v1/responses
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "input": "Your question here",
  "stream": true,
  "metadata": {
    "entity_id": "orchestrator"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `input` | Yes | The user's question or message |
| `metadata.entity_id` | Yes | Which agent to invoke (must match an `id` from `ChatAgent`) |
| `stream` | No | `true` for SSE streaming (recommended for real-time UX) |
| `conversation` | No | Conversation ID for multi-turn context |

The `entity_id` corresponds to the `id` field set on each `ChatAgent` — typically the `Agent` enum value (e.g., `"orchestrator"`, `"agent-a"`).

### Discovery Endpoint

#### `GET /v1/entities`

Returns metadata for all registered agents (name, description, id). Useful for building dynamic UIs.

### Conversations

#### `POST /v1/conversations`

Create a new conversation session:

```json
{ "entity_id": "orchestrator" }
```

Returns a conversation ID that you can pass in subsequent `/v1/responses` requests to maintain multi-turn context.

### Health Check

#### `GET /health`

Returns `200 OK` when the server is running.

### SSE Streaming

When `stream: true`, the response is an SSE stream. Key event types:

| Event Type | Description |
|------------|-------------|
| `response.text_delta` | Incremental text chunk from the agent |
| `response.completed` | Final event — response is complete |
| `[DONE]` | Stream termination signal |

### Client Libraries

Since the API follows the OpenAI Responses format, you can use standard OpenAI SDKs:

```javascript
// JavaScript — OpenAI SDK
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://your-app.azurewebsites.net/v1",
  apiKey: accessToken,
  dangerouslyAllowBrowser: true,
});

const stream = await client.responses.create({
  input: "Your question",
  model: "orchestrator",  // ignored server-side, but required by SDK
  stream: true,
  metadata: { entity_id: "orchestrator" },
});

for await (const event of stream) {
  if (event.type === "response.text_delta") {
    process.stdout.write(event.delta);
  }
}
```

```python
# Python — httpx
import httpx, json

async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST", "https://your-app.azurewebsites.net/v1/responses",
        headers={"Authorization": f"Bearer {token}"},
        json={"input": "Your question", "stream": True, "metadata": {"entity_id": "orchestrator"}},
    ) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]": break
                event = json.loads(data)
                if event.get("type") == "response.text_delta":
                    print(event["delta"], end="")
```

### Authentication for Production

When deployed behind Azure AD (EasyAuth/MISE), callers must send a **delegated (user) access token** in the `Authorization` header. Client-credentials (S2S) tokens will not work if MCP tools require user-level OBO auth downstream.

---

## Deployment to Azure App Service

For production deployment on Azure App Service with Python:

1. **Runtime:** Python 3.12 with Oryx build (`SCM_DO_BUILD_DURING_DEPLOYMENT=true`).
2. **Startup command:** `python main.py`.
3. **Authentication:** Use [EasyAuth/MISE](https://learn.microsoft.com/en-us/azure/app-service/overview-authentication-authorization) for AAD login gating. The middleware reads `x-ms-*` headers injected by EasyAuth.
4. **Managed Identity:** User-assigned MI for Azure OpenAI access and OBO client assertions.
5. **DevUI:** Disable in production — set `ui_enabled = not is_azure`.

**Key environment variables for Azure:**

| Variable | Purpose |
|----------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name |
| `AZURE_OPENAI_API_VERSION` | API version |
| `AZURE_TENANT_ID` | AAD tenant ID |
| `AZURE_CLIENT_ID` | App registration client ID (for OBO) |
| `AZURE_MI_CLIENT_ID` | User-assigned Managed Identity client ID |
| `PORT` / `WEBSITES_PORT` | Server port (e.g., `8080`) |

**Deploy via zip push:**

```powershell
az webapp deploy --resource-group <rg> --name <app> --src-path app.zip --type zip
```

Oryx detects `requirements.txt` and runs `pip install` during deployment automatically.

---

## Telemetry

Initialize Azure Monitor **before any other imports** so OpenTelemetry auto-instruments FastAPI, httpx, and logging:

```python
# top of main.py
connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
if connection_string:
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(
        connection_string=connection_string,
        enable_live_metrics=True,
    )
```

This auto-instruments:
- HTTP requests (FastAPI/Starlette inbound, httpx outbound)
- Python `logging` → App Insights traces
- Live metrics streaming

When the connection string is empty (local dev), telemetry is silently disabled.

---

## Design Decisions & Gotchas

### 1. Local tools vs. MCP for APIs you own
For REST APIs you control, calling them directly via `FunctionTool` + an HTTP service layer is simpler and faster than routing through an MCP server. Use MCP for third-party integrations where you don't own the API.

### 2. `FunctionTool` calling convention
MAF decomposes the Pydantic `input_model` to kwargs and calls `func(**model.model_dump())`. Your function must accept keyword arguments matching the model fields — **not** the model instance. A wrapper like `def my_tool(params: MyModel)` will silently fail.

### 3. `AzureOpenAIResponsesClient` parameter names
Uses `endpoint=` (not `azure_endpoint=`) and `ad_token_provider=` (not `azure_ad_token_provider=`). These differ from the standard Azure OpenAI SDK.

### 4. Pure ASGI middleware for ContextVars
`BaseHTTPMiddleware` loses `ContextVar` values during SSE streaming. Always implement user-context middleware as a raw ASGI app. See [ContextVar Propagation](#contextvar-propagation-in-asgi).

### 5. `DefaultAzureCredential` with Managed Identity
On App Service with multiple managed identities, always pass `managed_identity_client_id` explicitly to `DefaultAzureCredential()` — otherwise it may pick the wrong identity.

### 6. MCP cache staleness
Cached MCP tool schemas must be refreshed manually when the MCP server adds or changes tools. Commit the cache to source control so the app starts without network calls.

### 7. `AzureCliCredential` scope requirements
`AzureCliCredential.get_token()` only supports `/.default` scopes (resource-level). Delegated scopes like `/access_as_user` will fail. Keep this in mind for local development.

### 8. Telemetry import order
`configure_azure_monitor()` must run before any imports that create HTTP clients or loggers. Moving it later means missed instrumentation.

### 9. Unicode in Windows logging
Emoji characters in `logger.info()` cause `UnicodeEncodeError` on Windows with non-UTF-8 codepages. Use ASCII tags (`[OK]`, `[FAIL]`) in log messages instead.

### 10. kwargs filtering for MCP tool calls
MAF may inject extra kwargs (like `AgentThread`) into tool function calls. When forwarding to an MCP server, filter kwargs to match the tool's `inputSchema.properties` only.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `agent-framework[azure,devui]` | MAF — ChatAgent, FunctionTool, MCP tools, DevServer |
| `azure-identity` | `DefaultAzureCredential`, `ManagedIdentityCredential`, `AzureCliCredential` |
| `msal` | OBO token exchange via `ConfidentialClientApplication` |
| `python-dotenv` | `.env` file loading for local dev |
| `httpx` | Async HTTP client for REST API calls and MCP requests |
| `pydantic` | Input model validation for `FunctionTool` definitions |
| `azure-monitor-opentelemetry` | Azure Monitor + OpenTelemetry auto-instrumentation |

---

## Further Reading

- [Microsoft Agent Framework — Get Started](https://learn.microsoft.com/en-us/agent-framework/get-started/)
- [MAF Tools Overview](https://learn.microsoft.com/en-us/agent-framework/agents/tools/) — function tools, MCP, code interpreter
- [Using an Agent as a Function Tool](https://learn.microsoft.com/en-us/agent-framework/agents/tools/#using-an-agent-as-a-function-tool)
- [MAF Hosting](https://learn.microsoft.com/en-us/agent-framework/get-started/hosting) — DevServer, A2A, Azure Functions
- [MAF GitHub Samples](https://github.com/microsoft/agent-framework)
- [Azure App Service Python Deployment](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
