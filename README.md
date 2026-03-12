# Experience Graph

A structured context graph and experience store for AI agents. Agents read from and write to a shared knowledge layer — traces, entities, evidence, precedents, and policies — so teams build institutional memory instead of starting from scratch.

## Core Concepts

- **Traces** — structured records of agent/human actions with outcomes
- **Entities** — nodes in a shared knowledge graph (with SCD Type 2 temporal versioning)
- **Evidence** — provenance-tracked artifacts (snippets, logs, files)
- **Precedents** — curated institutional knowledge extracted from traces
- **Policies** — governance rules for the write pipeline
- **Packs** — retrieval bundles assembled for specific tasks, token-budgeted for LLM context windows

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │          Integration Layers          │
                    │                                      │
                    │  MCP Macro Tools (8 tools, markdown) │
                    │  REST API (FastAPI, /api/v1/*)       │
                    │  Python SDK (XPGClient, skills)      │
                    │  CLI (xpg)                           │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       Governed Mutation Pipeline      │
                    │  Validate → Policy → Idempotency     │
                    │  → Execute → Emit Event              │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────────────────▼────────────────────────┐
          │              Pluggable Store Layer               │
          │                                                  │
          │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
          │  │  SQLite   │  │ Postgres │  │ S3 Blob  │      │
          │  │ (default) │  │ pgvector │  │ (cloud)  │      │
          │  └──────────┘  └──────────┘  └──────────┘      │
          │                                                  │
          │  Stores: Trace, Document, Graph, Vector,        │
          │          Event Log, Blob                         │
          └─────────────────────────────────────────────────┘
```

**Five packages:**

| Package | Purpose |
|---|---|
| `xpgraph` | Core library — schemas, pluggable stores, mutation executor, retrieval, formatters |
| `xpgraph_cli` | CLI (`xpg`) — ingest, curate, retrieve, analyze, admin |
| `xpgraph_api` | REST API (`xpg-api`) — FastAPI server with OpenAPI spec |
| `xpgraph_sdk` | Python SDK — `XPGClient` with local/remote modes, skill functions |
| `xpgraph_workers` | Workers — enrichment, learning, ingestion (dbt, OpenLineage), maintenance |

**Integration:** `integrations/obsidian/` — index Obsidian vault notes into the graph.

## Install

Requires Python 3.11+.

```bash
# Core (SQLite backends)
pip install -e ".[dev]"

# With cloud backends (Postgres, pgvector, S3)
pip install -e ".[dev,cloud]"

# With vector support (numpy, lancedb)
pip install -e ".[dev,vectors]"
```

## Quick Start

```bash
xpg admin init                    # Initialize stores
xpg admin health                  # Check store health
```

## CLI

```bash
# Ingest
xpg ingest trace trace.json       # Ingest a trace
xpg ingest evidence evidence.json # Ingest evidence
xpg ingest dbt-manifest manifest.json   # Import dbt lineage graph
xpg ingest openlineage events.json      # Import OpenLineage events

# Curate
xpg curate promote TRACE_ID --title "..." --description "..."
xpg curate link SOURCE_ID TARGET_ID
xpg curate label ENTITY_ID important
xpg curate feedback TRACE_ID 0.9

# Retrieve
xpg retrieve trace TRACE_ID       # Fetch a trace
xpg retrieve search "query"       # Search documents
xpg retrieve entity ENTITY_ID     # Fetch an entity
xpg retrieve precedents           # List precedents
xpg retrieve pack --intent "..."  # Assemble a retrieval pack

# Analyze
xpg analyze context-effectiveness # Which context items correlate with success
xpg analyze token-usage           # Token budget tracking across layers

# Admin
xpg admin stats                   # Store counts
xpg admin serve --port 8420       # Start REST API server
```

All commands support `--format json` for machine-readable output. List commands also support `--format jsonl`, `--format tsv`, `--fields`, `--truncate`, and `--quiet`.

## REST API

Start the API server:

```bash
xpg admin serve --port 8420
# or
xpg-api
```

Key endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/traces` | Ingest a trace |
| GET | `/api/v1/search?q=...` | Full-text search |
| POST | `/api/v1/packs` | Assemble context pack |
| GET | `/api/v1/entities/{id}` | Get entity with neighborhood |
| POST | `/api/v1/precedents` | Promote trace to precedent |
| POST | `/api/v1/feedback` | Record feedback |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/stats` | Store statistics |
| GET | `/api/v1/effectiveness` | Context effectiveness report |

Full OpenAPI spec available at `/docs` when the server is running.

## MCP Server

8 high-level Macro Tools returning token-budgeted markdown (not raw JSON):

```bash
xpg-mcp   # Start the MCP server
```

| Tool | Purpose |
|------|---------|
| `get_context` | Search docs + graph + traces, return summarized markdown pack |
| `save_experience` | Ingest a trace |
| `save_knowledge` | Create entity + optional relationship |
| `save_memory` | Store a document |
| `get_lessons` | List precedents as markdown |
| `get_graph` | Entity + neighborhood as markdown |
| `record_feedback` | Record task success/failure |
| `search` | Combined doc + graph search as markdown |

All tools accept `max_tokens` (default 2000) for context window budgeting.

## Python SDK

```python
from xpgraph_sdk import XPGClient

# Local mode (direct store access)
client = XPGClient()

# Remote mode (via REST API)
client = XPGClient(base_url="http://localhost:8420")

# Operations
results = client.search("database migration", limit=5)
trace_id = client.ingest_trace(trace_dict)
entity_id = client.create_entity("auth-service", entity_type="service")
pack = client.assemble_pack("deploy checklist for staging")
```

Skill functions return pre-summarized markdown strings for direct LLM injection:

```python
from xpgraph_sdk.skills import get_context_for_task, get_recent_activity

context = get_context_for_task(client, "implement retry logic", domain="backend")
activity = get_recent_activity(client, domain="backend", max_tokens=1500)
```

## Pluggable Storage

Store backends are selected via `~/.xpg/config.yaml`:

```yaml
stores:
  graph:
    backend: postgres
    dsn: postgresql://user:pass@host/db
  vector:
    backend: pgvector
    dsn: postgresql://user:pass@host/db
  blob:
    backend: s3
    bucket: xpg-artifacts
    region: us-east-1
  # trace, document, event_log default to sqlite
```

Available backends:

| Store | SQLite (default) | Postgres | Other |
|-------|:-:|:-:|:-:|
| Trace | `sqlite` | `postgres` | |
| Document | `sqlite` | `postgres` | |
| Graph | `sqlite` | `postgres` | |
| Vector | `sqlite` | `pgvector` | |
| Event Log | `sqlite` | `postgres` | |
| Blob | `local` | | `s3` |

Graph stores support SCD Type 2 temporal versioning — query historical state with `as_of` parameter.

## Ingestion Workers

Auto-populate the knowledge graph from external data tools:

```bash
# Import dbt lineage (models, sources, dependencies)
xpg ingest dbt-manifest target/manifest.json

# Import OpenLineage events (datasets, jobs, reads/writes)
xpg ingest openlineage lineage-events.json
```

## Development

```bash
pytest                            # Run all tests (440+)
pytest tests/unit/ -v             # Unit tests only
pytest -m postgres                # Postgres integration tests
ruff check src/ tests/            # Lint
mypy src/                         # Type check
```

## License

MIT — see [LICENSE](LICENSE).
