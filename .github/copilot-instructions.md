# ForgeLens — Copilot Instructions

## What is ForgeLens?

ForgeLens is a **multi-agent Instagram automation system** built on **Microsoft Agent Framework (MAF)**.
It uses a hierarchical pattern where per-account persona agents delegate to shared specialist agents.
Media generation is decoupled from agents — it runs as a background worker triggered by Service Bus.

**Entry point:** `main.py` → discovers profiles from `insta_profiles/*.json`, creates agents, launches MAF DevServer at `http://127.0.0.1:8080`.

**Run command:** `source .venv/bin/activate && python main.py`

---

## Architecture

### Agent Hierarchy

```
Account Agent (per-profile persona)
├── delegates to → Trend Scout
├── delegates to → Communicator
├── interacts with → Approver (human-in-the-loop)
└── interacts with → Publisher (queue-triggered)
```

### Media Generation (Queue-Based, No Agent)

Media generation is **not an agent**. The account agent's `generate_image`/`generate_video` tools:

1. Create a DB record with `generation_status='queued'`
2. Send a message to the `media-generation` Service Bus queue
3. Return the `content_id` immediately to the user

The **MediaGenerationWorker** (background thread) has two concurrent loops:

- **Queue listener** — consumes `media-generation` messages, reads DB, submits async fal.ai request, updates DB to `generation_status='submitted'` with `fal_request_id`
- **Progress poller** — queries DB for `generation_status='submitted'`, checks fal.ai status, on completion: downloads → uploads to Blob → updates DB → enqueues to `review-pending`

### Content Pipeline (Sequential Workflow)

`agents/account/workflow.py` runs **Trend Scout** via MAF `SequentialBuilder` for automated trend discovery.

### Queue-Triggered Workers

- **Media Generation Worker** — listens on Service Bus `media-generation` queue, processes fal.ai generation
- **Communicator** — listens on Service Bus `review-pending` queue, sends email reminders
- **Publisher** — listens on Service Bus `review-approved` queue, publishes to Instagram

All three are started as background workers in `main.py`.

---

## Agents Reference

| Agent                    | ID             | Source                         | Prompt                              | Tools                                                          |
| ------------------------ | -------------- | ------------------------------ | ----------------------------------- | -------------------------------------------------------------- |
| **Account Agent** (Oreo) | per-profile    | `agents/account/agent.py`      | `agents/account/prompt_template.md` | `agents/account/tools.py` + `agents/account/internal_tools.py` |
| **Trend Scout**          | `trend-scout`  | `agents/trend_scout/agent.py`  | `agents/trend_scout/prompt.md`      | `agents/trend_scout/tools.py` (Tavily search/extract)          |
| **Approver**             | `review-queue` | `agents/approver/agent.py`     | `agents/approver/prompt.md`         | `agents/approver/tools.py` (approve/reject/view/request edits) |
| **Communicator**         | `communicator` | `agents/communicator/agent.py` | `agents/communicator/prompt.md`     | `agents/communicator/tools.py` (email via ACS)                 |
| **Publisher**            | `publisher`    | `agents/publisher/agent.py`    | `agents/publisher/prompt.md`        | `agents/publisher/tools.py` (Instagram Graph API publish)      |

### Background Workers (Not Agents)

| Worker                       | Source                                        | Trigger                  | Purpose                                         |
| ---------------------------- | --------------------------------------------- | ------------------------ | ----------------------------------------------- |
| **Media Generation Worker**  | `shared/services/media_generation_worker.py`  | `media-generation` queue | Submit to fal.ai, poll status, upload to Blob   |
| **Generation Queue Service** | `shared/services/generation_queue_service.py` | Called by account tools  | Creates DB record + enqueues generation request |

### Agent Registry

`agent_registry.py` is the **single source of truth** for all agent identities, descriptions, and `as_tool()` routing metadata. Every agent reads its own identity from here.

### Base Agent Pattern

`shared/base_agent.py` — Abstract base. Subclasses set `agent_id`, optionally override `_build_tools()`. Prompt auto-loaded from `prompt.md` in the subclass's directory. Account agent is special — uses `prompt_template.md` with Jinja-style profile injection.

---

## Key Directories

| Path                        | Purpose                                                           |
| --------------------------- | ----------------------------------------------------------------- |
| `agents/`                   | All agent implementations (one subfolder per agent)               |
| `shared/config/settings.py` | Centralized configuration (Key Vault secrets + defaults)          |
| `shared/config/keyvault.py` | Azure Key Vault client for secrets                                |
| `shared/services/`          | Azure service clients (Blob, Cosmos, Service Bus, ACS, Instagram) |
| `shared/account_profile.py` | Loads persona JSON profiles into dataclasses                      |
| `insta_profiles/`           | Per-account persona JSON configs (drop a new file = new account)  |
| `agent_registry.py`         | Central agent identity + routing metadata                         |
| `main.py`                   | Entry point — wires everything together, starts DevServer         |

---

## Azure Backend Services

| Service                          | Purpose                                  | Config Keys                                                                              |
| -------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Azure OpenAI**                 | LLM backbone (gpt5-mini)                 | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`                                       |
| **Azure Key Vault**              | Secrets (IG tokens, fal key, Tavily key) | `AZURE_KEYVAULT_URL`                                                                     |
| **Azure Blob Storage**           | Media asset storage                      | `AZURE_STORAGE_ACCOUNT_URL`, container: `insta-media`                                    |
| **Azure Cosmos DB**              | Media metadata & content records         | `COSMOS_ENDPOINT`, db: `insta-agent`, container: `media-metadata`                        |
| **Azure Service Bus**            | Queue messaging                          | `SERVICEBUS_NAMESPACE` (queues: `media-generation`, `review-pending`, `review-approved`) |
| **Azure Communication Services** | Email notifications to reviewers         | `ACS_ENDPOINT`, `ACS_SENDER_EMAIL`                                                       |
| **Application Insights**         | Telemetry & tracing                      | `APPLICATIONINSIGHTS_CONNECTION_STRING`                                                  |

---

## Account Profiles

Profiles live in `insta_profiles/*.json`. Each defines:

- `account_name` / `display_name` — mapping to KV secret for IG token
- `persona` — identity, appearance, voice, tone, audience, themes, avoid-list
- `content_rules` — formats, cadence, hashtag policy, caption style, visual style, content type frequency
- `media_defaults` — aspect ratios, resolution, video duration

**Current profile:** `insta_profiles/oreo.json` — "Oreo the Golden", an AI golden retriever influencer with luxury/celebrity lifestyle theme.

Adding a new account = drop a new JSON file in `insta_profiles/` + add the corresponding KV secret.

---

## Tech Stack

- **Python 3.12+**
- **Microsoft Agent Framework (MAF)** — `agent_framework` package
- **Azure OpenAI Responses API** — `AzureOpenAIResponsesClient`
- **Azure Identity** — `DefaultAzureCredential` with managed identity
- **fal.ai** — image generation (Nano Banana Pro) and video generation (Kling O3 / Sora 2)
- **Tavily** — web search and content extraction
- **uvicorn** — ASGI server for MAF DevServer

---

## Conventions

- Agent prompts are Markdown files (`prompt.md` or `prompt_template.md`) co-located with the agent code.
- Tools are defined as `FunctionTool` instances in `tools.py` files per agent.
- All secrets go through Key Vault (`shared/config/keyvault.py`) — no env var fallback for secrets.
- The `Settings` singleton (`shared/config/settings.py`) is the single config access point.
- Content IDs flow through the pipeline: generate (queue) → fal.ai (worker) → blob upload → queue for review → approve → publish.
- Service Bus queues connect the async parts: media-generation triggers the worker, review-pending triggers Communicator, review-approved triggers Publisher.
