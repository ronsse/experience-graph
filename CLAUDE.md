# Experience Graph

A structured experience store for AI agents. Agents record traces of their work, build a shared knowledge graph of entities and evidence, and retrieve context packs before starting new tasks. The system provides governed mutations, immutable audit logging, and policy-based access control.

## Agent Guide

Operational reference for interacting with the experience graph lives in `docs/agent-guide/`:

| Document | What It Covers |
|----------|----------------|
| [trace-format.md](docs/agent-guide/trace-format.md) | Constructing and ingesting valid trace JSON |
| [schemas.md](docs/agent-guide/schemas.md) | All Pydantic schemas with fields, types, and examples |
| [operations.md](docs/agent-guide/operations.md) | Full CLI and Python mutation API reference |
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
xpg ingest trace <file>
xpg retrieve search "<query>"
xpg curate promote <trace_id> --title "..." --description "..."
```

## Key Files

| Path | Purpose |
|------|---------|
| `src/xpgraph/schemas/` | All Pydantic data models |
| `src/xpgraph/mutate/commands.py` | Operation enum, Command/CommandResult schemas |
| `src/xpgraph/mutate/executor.py` | Governed mutation pipeline |
| `src/xpgraph/retrieve/pack_builder.py` | Context pack assembly |
| `src/xpgraph/retrieve/strategies.py` | Search strategies (keyword, semantic, graph) |
| `src/xpgraph/stores/` | SQLite-backed persistence (documents, graph, traces, vectors, events) |
| `src/xpgraph_cli/` | CLI commands (ingest, curate, retrieve, admin) |
| `src/xpgraph_workers/` | Curation workers (enrichment, learning, maintenance) |
| `integrations/obsidian/` | Obsidian vault indexer |

## Packages

| Package | Purpose |
|---------|---------|
| `xpgraph` | Core library -- schemas, stores, mutation executor, retrieval |
| `xpgraph_cli` | CLI (`xpg`) -- ingest, curate, retrieve, admin |
| `xpgraph_workers` | Curation workers -- enrichment, learning, thinking engine |
