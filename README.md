# Experience Graph

A structured context graph and experience store for AI agents. Agents read from and write to a shared knowledge layer — traces, entities, evidence, precedents, and policies — so teams build institutional memory instead of starting from scratch.

## What's In the Graph

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                     THE EXPERIENCE GRAPH                            │
  │                                                                     │
  │  ┌───────────┐  depends_on   ┌───────────┐  part_of  ┌─────────┐  │
  │  │  service:  │──────────────▶│  service:  │─────────▶│  team:  │  │
  │  │  auth-api  │              │  user-db   │          │ platform │  │
  │  └─────┬─────┘              └───────────┘          └─────────┘  │
  │        │ touched_entity                                          │
  │  ┌─────▼──────────────────────────────────────┐                  │
  │  │  trace: "Added rate limiting to auth-api"  │                  │
  │  │  ├─ step: researched existing patterns     │                  │
  │  │  ├─ step: tool_call edit_file gateway.py   │                  │
  │  │  ├─ step: tool_call run_tests (42 passed)  │                  │
  │  │  └─ outcome: success                       │                  │
  │  └─────┬──────────────────────┬───────────────┘                  │
  │        │ used_evidence        │ promoted_to_precedent            │
  │  ┌─────▼─────────┐    ┌──────▼──────────────────────────┐       │
  │  │  evidence:    │    │  precedent: "Rate limiting      │       │
  │  │  "RFC: API    │    │  pattern for API gateways"      │       │
  │  │   guidelines" │    │  confidence: 0.85               │       │
  │  │  uri: s3://…  │    │  applies_to: [auth, payments]   │       │
  │  └───────────────┘    └─────────────────────────────────┘       │
  │                                                                     │
  │  Every node has temporal versions (valid_from / valid_to)          │
  │  — query any past state with as_of                                 │
  └─────────────────────────────────────────────────────────────────────┘
```

The graph captures **what agents did** (traces with steps, tool calls, reasoning, outcomes), **what they knew** (evidence — documents, snippets, file pointers with URIs to local files or S3), **what they learned** (precedents — distilled patterns extracted from successful and failed traces), and **how things relate** (13 edge types: dependencies, provenance, applicability). All nodes carry temporal versions so you can query the state of knowledge at any point in time.

## How It Works

```
  AGENTS & HUMANS                     BACKGROUND WORKERS
  read & write                        analyze & curate
       │                                     │
       │  ┌───────────────────────┐          │
       ├──│ CLI  (xpg)            │          │
       ├──│ MCP  (8 macro tools)  │  Tools   │  ┌─────────────────────┐
       ├──│ API  (REST/FastAPI)   │──Layer──┐ ├──│ Enrichment: auto-   │
       ├──│ SDK  (XPGClient)      │        │ │  │   tag, classify,    │
       │  └───────────────────────┘        │ │  │   score importance  │
       │                                   │ │  ├─────────────────────┤
       │  ┌───────────────────────┐        │ ├──│ Learning: mine      │
       │  │ Context Pack Builder  │◀───────┘ │  │   failure patterns  │
       │  │ ┌─────┐ ┌─────┐      │          │  │   into precedents   │
       │  │ │docs │ │graph│      │          │  ├─────────────────────┤
       │  │ │     │ │     │      │  Retrieval├──│ Ingestion: import   │
       │  │ │FTS  │ │ BFS │      │          │  │   dbt, OpenLineage  │
       │  │ └─────┘ └─────┘      │          │  ├─────────────────────┤
       │  │ ┌─────┐ ┌─────┐      │          ├──│ Maintenance: prune  │
       │  │ │trace│ │vector│     │          │  │   stale data, audit │
       │  │ │     │ │      │     │          │  ├─────────────────────┤
       │  │ │hist.│ │sim.  │     │          └──│ Thinking Engine:    │
       │  │ └─────┘ └─────┘      │             │   cognition tiering │
       │  │                      │             │   (fast→deep)       │
       │  │ → deduplicate        │             └─────────────────────┘
       │  │ → rank by relevance  │
       │  │ → enforce token      │
       │  │   budget             │
       │  │ → emit telemetry     │
       │  └──────────┬───────────┘
       │             │ assembled pack
       │             ▼
       │  ┌──────────────────────────┐
       │  │  Markdown context for    │
       │  │  agent's next task       │
       │  │  (token-budgeted,        │
       │  │   relevance-ranked)      │
       │  └──────────────────────────┘
       │
       │  ┌──────────────────────────────────────┐
       └─▶│      Governed Write Pipeline          │
          │  validate → policy check              │
          │  → idempotency → execute              │
          │  → emit event (immutable audit log)   │
          └──────────────────────┬────────────────┘
                                 │
          ┌──────────────────────▼────────────────┐
          │         Pluggable Storage              │
          │  SQLite (local) │ Postgres (cloud)     │
          │  pgvector       │ S3 (blobs/files)     │
          └────────────────────────────────────────┘
```

**The feedback loop:** agents retrieve context packs before tasks, execute work, ingest traces of what happened, and record whether the task succeeded. Background workers analyze these outcomes to promote successful patterns into precedents and flag noisy context items — so the graph gets smarter over time.

## Install

Requires Python 3.11+.

```bash
# Core (SQLite backends)
pip install -e ".[dev]"

# With cloud backends (Postgres, pgvector, S3)
pip install -e ".[dev,cloud]"

# With vector support (LanceDB, numpy, pyarrow)
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
    backend: lancedb          # serverless, no external DB needed
    # uri: /custom/path       # optional, defaults to data/stores/lancedb/
  blob:
    backend: s3
    bucket: xpg-artifacts
    region: us-east-1
  # trace, document, event_log default to sqlite
```

Available backends:

| Store | SQLite (default) | LanceDB | Postgres | Other |
|-------|:-:|:-:|:-:|:-:|
| Trace | `sqlite` | | `postgres` | |
| Document | `sqlite` | | `postgres` | |
| Graph | `sqlite` | | `postgres` | |
| Vector | `sqlite` | `lancedb` | `pgvector` | |
| Event Log | `sqlite` | | `postgres` | |
| Blob | `local` | | | `s3` |

**LanceDB** is the recommended vector backend for local/single-machine deployments — it's serverless (like SQLite for vectors), uses native ANN indexing with cosine similarity, and stores data as efficient Lance-format files on disk. No external database needed. Use **pgvector** for distributed/multi-server deployments.

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
