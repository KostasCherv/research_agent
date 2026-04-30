# Research Agent

A multi-step AI research pipeline built with **LangGraph**, **Tavily**, and **LangChain** that automates web research and produces structured markdown reports.
![Kapture 2026-03-05 at 14 08 29](https://github.com/user-attachments/assets/08d4fcf9-855f-410c-8520-76a376f774fd)

## Architecture

```mermaid
flowchart LR
    userQuery["User query"] --> search["search (Tavily)"]
    search -->|"continue"| retrieve["retrieve (httpx + BeautifulSoup)"]
    search -->|"abort on error"| abortNode["abort"]
    retrieve -->|"ok"| memoryContext["memory_context (Pinecone search)"]
    retrieve -->|"empty"| emptyNode["empty"]
    memoryContext --> summarize["summarize (LLM)"]
    summarize --> report["report (LLM markdown)"]
    report --> vectorStore["vector_store (optional Pinecone persist)"]
    vectorStore --> endNode["END"]
    abortNode --> endNode
    emptyNode --> endNode
```

Each node is a pure function that receives and returns a `ResearchState` TypedDict. Conditional edges handle error cases and empty result sets without crashing the pipeline.

RAG ingestion now uses an outbox + dispatcher pattern for reliability:

```mermaid
flowchart LR
    user["User uploads file"] --> api["FastAPI /api/rag/resources/upload"]
    api --> tx["Atomic DB RPC\ncreate_resource_job_and_outbox"]
    tx --> resource["rag_resources"]
    tx --> job["rag_ingestion_jobs (queued)"]
    tx --> outbox["event_outbox (pending)"]

    dispatcher["rag-dispatch-outbox"] --> claim["Claim outbox row\npending -> dispatching"]
    claim --> inngestSend["Send event to Inngest"]
    inngestSend --> inngestFn["Inngest function\nrag/ingestion.requested"]
    inngestFn --> jobClaim["Claim job\nqueued -> running"]
    jobClaim --> ingest["RAG ingest from Supabase signed URL"]
    ingest --> artifacts["rag_sidecar_artifacts"]
    ingest --> ready["rag_ingestion_jobs -> succeeded\nrag_resources -> ready"]

    claim -->|send error| retry["Backoff + retry / fail"]
    jobClaim -->|already claimed/terminal| noop["No-op (idempotent)"]
```

Reliability patterns used:
- Transactional write: resource + ingestion job + outbox row created in one DB transaction.
- Durable outbox: events are persisted before external dispatch.
- Concurrent-safe dispatch: outbox rows are atomically claimed before send.
- Idempotent execution: ingestion job is atomically claimed (`queued` only), duplicate events no-op.
- Recovery: stuck `dispatching` outbox rows are reset and retried.

## Tech Stack

| Area | Technologies / Tools |
|---|---|
| Language | Python 3.11+, TypeScript |
| Orchestration | LangGraph |
| LLM Layer | LangChain, OpenAI, Ollama |
| Web Research | Tavily |
| Retrieval & Parsing | httpx, BeautifulSoup4 |
| API | FastAPI, Uvicorn, SSE |
| CLI | Typer, Rich |
| Vector Memory | Pinecone |
| Frontend | React 19, Vite, react-markdown, lucide-react |
| Code Quality | Pytest, Ruff, mypy, ESLint |

## Features

| Feature | Detail |
|---|---|
| LangGraph State Machine | TypedDict state, conditional edges |
| Multi-LLM support | OpenAI or Ollama — switched by env var |
| Retry logic | Exponential back-off on search and fetch |
| Streaming API | FastAPI SSE endpoint for real-time progress |
| CLI | Typer + Rich for beautiful terminal output |
| Vector storage | Pinecone for persisting and searching reports |
| Research sessions | Supabase Postgres session store tracks runs and conversation history |
| Strict user isolation | All session endpoints are auth-protected and scoped per authenticated user |
| Session management UX | Left sidebar with past sessions, LLM-generated titles, rename (double-click), delete (right-click) |
| Follow-up chat | ChatGPT-style chat grounded to the same sources as the research report |
| Per-run source chunks | Source passages are chunked, stored, and retrieved per run for grounded answers |
| LangSmith observability | Full workflow tracing: root runs, node spans, external calls, and failure context |

## Quick Start

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and TAVILY_API_KEY
```

### 3. Run the CLI

```bash
# Run a research query
python -m src.main search "What is LangGraph?"

# Save report to file
python -m src.main search "What is LangGraph?" --output report.md

# Also persist to Pinecone
python -m src.main search "What is LangGraph?" --vector-store

# Start the API server
python -m src.main serve --reload
```

### 4. Run the demo script

```bash
bash scripts/demo.sh "How does retrieval-augmented generation work?"
```

## UI (Frontend)

The `ui/` app provides a browser interface for:
- entering research queries
- streaming node-by-node progress from the backend
- rendering the final markdown report
- follow-up chat grounded to the same sources (ChatGPT-style, requires sessions)

Install and run:

```bash
cd ui
npm install
npm run dev
```

Build and preview production assets:

```bash
cd ui
npm run build
npm run preview
```

Frontend API configuration:
- The UI reads `VITE_API_BASE_URL`.
- If unset, it defaults to `http://localhost:8000`.
- The UI also requires Supabase auth vars for Google sign-in:
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`

Session UX:
- Clicking **Run research** always creates a new session.
- The left sidebar lists the authenticated user's past sessions.
- Double-click a session title to rename it.
- Right-click a session entry to open the context menu (rename/delete).

Run everything together (local):

```bash
# Terminal 1: API server
python -m src.main serve --reload

# Terminal 2: frontend
cd ui
npm run dev

# Terminal 3: Inngest dev server (routes events to local API)
npx --ignore-scripts=false inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery

# Terminal 4: outbox dispatcher loop (dev)
while true; do python -m src.main rag-dispatch-outbox --limit 100; sleep 2; done
```

Single-run dispatcher command:

```bash
python -m src.main rag-dispatch-outbox
python -m src.main rag-dispatch-outbox --limit 100
```

## API

Start the server:

```bash
python -m src.main serve
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Liveness probe |
| `/research` | `POST` | Run pipeline with SSE streaming (sessionless) |
| `/sessions` | `POST` | Create a new auth-scoped research session (supports title suggestion from `query`) |
| `/sessions` | `GET` | List auth-scoped session summaries (`session_id`, `title`, `created_at`) |
| `/sessions/{id}` | `GET` | Get session state and conversation history |
| `/sessions/{id}` | `PATCH` | Rename a session (`title`) |
| `/sessions/{id}` | `DELETE` | Delete a session |
| `/sessions/{id}/research` | `POST` | Run pipeline within a session (SSE); returns `X-Run-Id` header |
| `/sessions/{id}/followup` | `POST` | Ask a follow-up question grounded to a run's sources (SSE) |

Example — sessionless research:

```bash
curl -N -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What is LangGraph?", "use_vector_store": false}'
```

Example — session-based research + follow-up:

```bash
# 1. Create session
# (TOKEN should come from Supabase Auth sign-in)
SESSION=$(curl -s -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is LangGraph?"}' | jq -r '.session_id')

# 2. Run research (note X-Run-Id response header)
curl -N -X POST http://localhost:8000/sessions/$SESSION/research \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -D - \
  -d '{"query": "What is LangGraph?", "use_vector_store": true}'

# 3. Ask a follow-up (uses the latest run by default)
curl -N -X POST http://localhost:8000/sessions/$SESSION/followup \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Can it work without LangChain?"}'
```

SSE event types:

```json
{"type": "node",      "node": "search",  "status": "running"}
{"type": "node",      "node": "report",  "status": "completed", "data": {"report": "# Report ..."}}
{"type": "chunk",     "text": "token..."}
{"type": "citations", "citations": [{"source_url": "...", "source_title": "..."}]}
{"type": "done"}
{"type": "error",     "error": "message"}
```

## LangSmith Observability

The pipeline includes end-to-end LangSmith instrumentation, so you can track the entire multi-step flow in one place.

- A single **root run** is created per workflow execution (CLI or API).
- Every graph node (`search`, `retrieve`, `memory_context`, `summarize`, `report`, `vector_store`) is traced as a child span.
- External operations are traced as nested spans (Tavily search, URL fetch, LLM calls, Pinecone reads/writes).
- Routing and terminal outcomes are visible (`continue`, `abort`, `empty`) with status and timing context.
- Redaction-by-default protects sensitive payloads while preserving useful debugging metadata.

You get full observability from input to final report: where time is spent, where failures happen, and how data moves through the workflow.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `ollama` |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `EMBEDDING_PROVIDER` | `openai` | Embedding provider: `openai` or `ollama` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `EMBEDDING_BASE_URL` | `http://localhost:11434` | Base URL for Ollama embeddings |
| `EMBEDDING_DIMENSIONS` | `1536` | Expected vector size for the configured embedding model/index |
| `TAVILY_API_KEY` | — | Required for web search |
| `PINECONE_API_KEY` | — | Pinecone API key |
| `PINECONE_INDEX_NAME` | `research-agent-openai-small` | Pinecone index name for the active embedding model |
| `MAX_SEARCH_RESULTS` | `5` | Number of Tavily results |
| `LANGSMITH_TRACING` | `false` | Enable LangSmith tracing (`true`/`false`) |
| `LANGSMITH_PROJECT` | `research-agent` | LangSmith project name |
| `LANGSMITH_API_KEY` | — | LangSmith API key |
| `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` | LangSmith API endpoint |
| `LANGSMITH_REDACTION_MODE` | `redacted_default` | `full_payloads`, `redacted_default`, or `metadata_only` |
| `LANGSMITH_SAMPLING_RATE` | `1.0` | Fraction of workflow runs to trace (0.0-1.0) |
| `SUPABASE_URL` | — | Supabase project URL (used for PostgREST + JWKS defaults) |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Backend key for session persistence operations |
| `SUPABASE_JWKS_URL` | — | Optional explicit JWKS URL for token verification |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected audience in Supabase access tokens |
| `SUPABASE_JWT_SECRET` | — | Optional HS256 verification secret used as fallback path |
| `RAG_STORAGE_BUCKET` | `rag-resources` | Supabase Storage private bucket for uploaded RAG files |
| `RAG_SIGNED_URL_TTL_SECONDS` | `600` | Signed URL TTL used to pull uploads during ingestion |
| `INNGEST_DEV` | — | Set to `1` for local dev (disables signing key requirement) |
| `INNGEST_EVENT_KEY` | — | Inngest event key (required in production) |

Embedding index guidance:
- Use one Pinecone index per embedding provider/model combination.
- Do not mix vectors from different embedding models in the same index.
- If you switch `EMBEDDING_PROVIDER` or `EMBEDDING_MODEL`, also switch `PINECONE_INDEX_NAME`.
- Existing vectors must be re-embedded into the new index if you want them searchable after a model switch.

Example configs:

```bash
# OpenAI embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
PINECONE_INDEX_NAME=research-agent-openai-small
```

```bash
# Ollama embeddings
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_DIMENSIONS=768
PINECONE_INDEX_NAME=research-agent-ollama-nomic
```

Session endpoints now require a bearer token from Supabase Auth. The recommended UI flow is Google OAuth via Supabase on the frontend, then forwarding `Authorization: Bearer <access_token>` for session endpoints.
Session persistence is intentionally a hard requirement: server startup validates Supabase configuration and fails fast if required vars are missing.

When `LANGSMITH_TRACING=true`, workflow runs and per-node spans are sent to LangSmith with redaction-by-default payload handling.

## Development

```bash
# Run tests
pytest -v

# Lint
ruff check src

# Type check
mypy src
```
