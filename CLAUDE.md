# Experience Graph

A structured experience store for AI agents. Agents record traces of their work, build a shared knowledge graph of entities and evidence, and retrieve context packs before starting new tasks. The system provides governed mutations, immutable audit logging, and policy-based access control.

## Agent Guide

Operational reference for interacting with the experience graph lives in `docs/agent-guide/`:

| Document | What It Covers |
|----------|----------------|
| [trace-format.md](docs/agent-guide/trace-format.md) | Constructing and ingesting valid trace JSON |
| [schemas.md](docs/agent-guide/schemas.md) | All Pydantic schemas with fields, types, and examples |
| [operations.md](docs/agent-guide/operations.md) | Full CLI, REST API, MCP, and Python mutation API reference |
| [playbooks.md](docs/agent-guide/playbooks.md) | Step-by-step procedures for common tasks |

## Hard Rules

- **Traces are immutable.** Once ingested, a trace cannot be modified or deleted through normal operations.
- **All mutations go through the governed pipeline.** Validate, policy check, idempotency check, execute, emit event. No direct store writes.
- **Use `--format json` for machine output.** All CLI commands support it. Parse JSON output, not human-readable text.
- **Extra fields are forbidden.** All schemas use `extra="forbid"`. Unrecognized fields cause validation errors.
- **Use `structlog` for logging.** Never use `print()` in library code.
- **Type hints on all public APIs.**

## Development Commands

```bash
# Setup
uv pip install -e ".[dev]"
xpg admin init

# Quality
make lint          # ruff check src/ tests/
make format        # ruff format + fix
make typecheck     # mypy src/
make test          # pytest tests/ -v

# CLI
xpg admin health
xpg admin stats
xpg admin serve --port 8420
xpg ingest trace <file>
xpg ingest dbt-manifest <manifest>
xpg ingest openlineage <events>
xpg retrieve search "<query>"
xpg curate promote <trace_id> --title "..." --description "..."
xpg analyze context-effectiveness
xpg analyze token-usage
```

## Key Files

| Path | Purpose |
|------|---------|
| `src/xpgraph/schemas/` | All Pydantic data models |
| `src/xpgraph/mutate/commands.py` | Operation enum, Command/CommandResult schemas |
| `src/xpgraph/mutate/executor.py` | Governed mutation pipeline |
| `src/xpgraph/retrieve/pack_builder.py` | Context pack assembly with telemetry |
| `src/xpgraph/retrieve/strategies.py` | Search strategies (keyword, semantic, graph) |
| `src/xpgraph/retrieve/formatters.py` | Token-budgeted markdown formatters |
| `src/xpgraph/retrieve/effectiveness.py` | Context effectiveness analysis |
| `src/xpgraph/retrieve/token_tracker.py` | Token usage tracking |
| `src/xpgraph/retrieve/token_usage.py` | Token usage analysis and reporting |
| `src/xpgraph/stores/base/` | Store ABCs (TraceStore, DocumentStore, GraphStore, VectorStore, EventLog, BlobStore) |
| `src/xpgraph/stores/registry.py` | StoreRegistry — DI container with config-driven backend selection |
| `src/xpgraph/stores/sqlite/` | SQLite store implementations (default) |
| `src/xpgraph/stores/postgres/` | Postgres store implementations (cloud) |
| `src/xpgraph/stores/pgvector/` | pgvector store (cloud vectors) |
| `src/xpgraph/stores/s3/` | S3 blob store (cloud files) |
| `src/xpgraph/stores/local/` | Local filesystem blob store |
| `src/xpgraph/mcp/server.py` | MCP Macro Tools server (8 tools, markdown responses) |
| `src/xpgraph_cli/` | CLI commands (ingest, curate, retrieve, analyze, admin) |
| `src/xpgraph_api/` | REST API (FastAPI routes, models) |
| `src/xpgraph_sdk/` | Python SDK (XPGClient, skill functions) |
| `src/xpgraph_workers/` | Workers (enrichment, learning, ingestion, maintenance) |
| `integrations/obsidian/` | Obsidian vault indexer |

## Packages

| Package | Purpose |
|---------|---------|
| `xpgraph` | Core library — schemas, pluggable stores, mutation executor, retrieval, formatters |
| `xpgraph_cli` | CLI (`xpg`) — ingest, curate, retrieve, analyze, admin |
| `xpgraph_api` | REST API (`xpg-api`) — FastAPI with OpenAPI auto-generation |
| `xpgraph_sdk` | Python SDK — XPGClient (local/remote), skill functions |
| `xpgraph_workers` | Workers — enrichment, learning, ingestion (dbt, OpenLineage), maintenance |

## Store Backends

Backends are configured via `~/.xpg/config.yaml` or environment variables:

| Store | Default | Cloud | Env Var |
|-------|---------|-------|---------|
| Trace | `sqlite` | `postgres` | `XPG_PG_DSN` |
| Document | `sqlite` | `postgres` | `XPG_PG_DSN` |
| Graph | `sqlite` | `postgres` | `XPG_PG_DSN` |
| Vector | `sqlite` | `pgvector` | `XPG_PG_DSN` |
| Event Log | `sqlite` | `postgres` | `XPG_PG_DSN` |
| Blob | `local` | `s3` | `XPG_S3_BUCKET` |

Graph stores support temporal versioning (SCD Type 2) with `as_of` parameter for time-travel queries.

## Entry Points

| Command | Target |
|---------|--------|
| `xpg` | `xpgraph_cli.main:app` |
| `xpg-mcp` | `xpgraph.mcp.server:main` |
| `xpg-api` | `xpgraph_api.app:main` |
