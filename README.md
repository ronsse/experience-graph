# Experience Graph

An org-scale context graph and experience store for AI agents and teams. Agents read from and write to a shared knowledge layer — structured traces, entities, evidence, precedents, and policies — so teams build institutional memory instead of starting from scratch.

## Core Concepts

- **Traces** — structured records of agent/human actions with outcomes
- **Entities** — nodes in a shared knowledge graph
- **Evidence** — provenance-tracked artifacts (snippets, logs, files)
- **Precedents** — curated institutional knowledge extracted from traces
- **Policies** — governance rules for the write pipeline
- **Packs** — retrieval bundles assembled for specific tasks

## Architecture

```
xpg CLI ──► Mutation Executor (governed write pipeline)
               │
               ├── Validate (schema + operation registry)
               ├── Policy Check (pluggable gates)
               ├── Idempotency Check (event log-backed)
               ├── Execute (operation handlers)
               └── Emit Event (append-only audit log)

xpg CLI ──► Retrieval (pack assembly, search strategies)
               │
               ├── Document Store (full-text search)
               ├── Graph Store (nodes, edges, traversal)
               ├── Trace Store (immutable append-only)
               └── Vector Store (embeddings, similarity)
```

**Three packages:**

| Package | Purpose |
|---|---|
| `xpgraph` | Core library — schemas, stores (SQLite), mutation executor, retrieval |
| `xpgraph_cli` | CLI (`xpg`) — ingest, curate, retrieve, admin commands |
| `xpgraph_workers` | Curation workers — enrichment, learning, thinking engine, maintenance |

**Integration:** `integrations/obsidian/` — index Obsidian vault notes into the graph.

## Install

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
```

## CLI

```bash
xpg admin init                    # Initialize stores
xpg admin health                  # Check store health

xpg ingest trace trace.json       # Ingest a trace
xpg ingest evidence evidence.json # Ingest evidence

xpg curate promote TRACE_ID --title "..." --description "..."
xpg curate link SOURCE_ID TARGET_ID
xpg curate label ENTITY_ID important
xpg curate feedback TRACE_ID 0.9

xpg retrieve trace TRACE_ID       # Fetch a trace
xpg retrieve search "query"       # Search documents
xpg retrieve entity ENTITY_ID     # Fetch an entity
xpg retrieve precedents           # List precedents
xpg retrieve pack --intent "..."  # Assemble a retrieval pack
```

All commands support `--format json` for machine-readable output.

## Development

```bash
pytest                            # Run all tests (345+)
pytest tests/unit/ -v             # Unit tests only
ruff check src/ tests/            # Lint
mypy src/                         # Type check
```

## License

MIT — see [LICENSE](LICENSE).
