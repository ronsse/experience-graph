# Operations Reference

Complete CLI and Python API reference for the Experience Graph.

All CLI commands support `--format json` for machine-readable output. Use `--format json` when calling from scripts or agent tool adapters.

---

## Admin Commands

### `xpg admin init`

Initialize Experience Graph stores and configuration.

```bash
xpg admin init [--data-dir PATH] [--force] [--format text|json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--data-dir` | Platform default | Custom data directory path |
| `--force` | `false` | Overwrite existing config |
| `--format` | `text` | Output format |

**JSON output (success):**

```json
{"status": "initialized", "config_dir": "/home/user/.config/xpgraph", "data_dir": "/home/user/.local/share/xpgraph"}
```

**JSON output (already exists):**

```json
{"status": "exists", "config_dir": "/home/user/.config/xpgraph"}
```

### `xpg admin health`

Check health of Experience Graph stores.

```bash
xpg admin health [--format text|json]
```

**JSON output:**

```json
{
  "config": true,
  "data_dir": true,
  "stores_dir": true,
  "documents.db": true,
  "graph.db": true,
  "vectors.db": false,
  "events.db": true,
  "traces.db": true
}
```

A value of `false` means the store file does not exist. Run `xpg admin init` to create missing stores.

### `xpg admin stats`

Show store counts.

```bash
xpg admin stats [--format text|json]
```

**JSON output:**

```json
{"traces": 42, "documents": 15, "nodes": 23, "edges": 31, "events": 127}
```

### `xpg admin serve`

Start the REST API server.

```bash
xpg admin serve [--port PORT] [--host HOST] [--format text|json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `8420` | Port to listen on |
| `--host` | `0.0.0.0` | Host to bind to |

---

## Ingest Commands

### `xpg ingest trace`

Ingest a trace from a JSON file or stdin.

```bash
xpg ingest trace <file> [--format text|json]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `file` | No | Path to trace JSON file. Use `-` or omit for stdin. |

**From file:**

```bash
xpg ingest trace /tmp/my-trace.json --format json
```

**From stdin:**

```bash
cat <<'EOF' | xpg ingest trace - --format json
{
  "source": "agent",
  "intent": "Refactored database connection pooling",
  "steps": [
    {
      "step_type": "tool_call",
      "name": "edit_file",
      "args": {"file": "src/db/pool.py"},
      "result": {"status": "applied"},
      "duration_ms": 200
    }
  ],
  "outcome": {"status": "success", "summary": "Replaced manual connections with pool"},
  "context": {"agent_id": "code-orchestrator", "domain": "backend"}
}
EOF
```

**JSON output (success):**

```json
{"status": "ingested", "trace_id": "01JRK5N7QF8GHTM2XVZP3CWD9E", "source": "agent", "intent": "Refactored database connection pooling"}
```

**JSON output (validation error):**

```json
{"status": "error", "message": "1 validation error for Trace\nsource\n  Field required"}
```

**Error cases:**
- File not found: exit code 1, prints error message
- Invalid JSON: exit code 1, prints parse error
- Schema validation failure: exit code 1, prints Pydantic validation error

### `xpg ingest evidence`

Ingest evidence from a JSON file.

```bash
xpg ingest evidence <file> [--format text|json]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `file` | **Yes** | Path to evidence JSON file |

**Example:**

```bash
cat <<'EOF' > /tmp/evidence.json
{
  "evidence_type": "snippet",
  "content": "The connection pool should use a max of 20 connections per process.",
  "source_origin": "manual",
  "uri": "https://wiki.internal/db-guidelines"
}
EOF

xpg ingest evidence /tmp/evidence.json --format json
```

**JSON output (success):**

```json
{"status": "ingested", "evidence_id": "01JRK6M3QF8GHTM2XVZP3CWD9E", "evidence_type": "snippet"}
```

### `xpg ingest dbt-manifest`

Import a dbt manifest into the knowledge graph.

```bash
xpg ingest dbt-manifest <manifest-path> [--format text|json]
```

Creates entities for models, seeds, snapshots, sources, and tests. Creates `depends_on` edges from the manifest's dependency graph. Indexes descriptions into the document store.

**JSON output:**

```json
{"status": "ok", "nodes_created": 12, "edges_created": 8}
```

### `xpg ingest openlineage`

Import OpenLineage events into the knowledge graph.

```bash
xpg ingest openlineage <events-path> [--format text|json]
```

Reads a JSON array or newline-delimited JSON file of OpenLineage events. Creates dataset and job entities with `reads_from` and `writes_to` edges.

**JSON output:**

```json
{"status": "ok", "nodes_created": 6, "edges_created": 4}
```

---

## Curate Commands

### `xpg curate promote`

Promote a trace to a precedent (reusable institutional knowledge).

```bash
xpg curate promote <trace_id> --title <title> --description <description> [--by <who>] [--format text|json]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `trace_id` | **Yes** | -- | Trace ID to promote |
| `--title` | **Yes** | -- | Title for the precedent |
| `--description` | **Yes** | -- | Description of the pattern |
| `--by` | No | `"cli"` | Who is promoting |
| `--format` | No | `text` | Output format |

**Example:**

```bash
xpg curate promote 01JRK5N7QF8GHTM2XVZP3CWD9E \
  --title "Database pool configuration pattern" \
  --description "When configuring connection pools, use max 20 connections per process with 30s idle timeout" \
  --by code-orchestrator \
  --format json
```

**JSON output (success):**

```json
{
  "status": "success",
  "command_id": "01JRK7A3QF8GHTM2XVZP3CWD9E",
  "operation": "precedent.promote",
  "message": "Precedent promoted",
  "created_id": "01JRK7A4QF8GHTM2XVZP3CWD9E"
}
```

### `xpg curate link`

Create a directed edge between two entities.

```bash
xpg curate link <source_id> <target_id> [--kind <edge_kind>] [--format text|json]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `source_id` | **Yes** | -- | Source node ID |
| `target_id` | **Yes** | -- | Target node ID |
| `--kind` | No | `entity_related_to` | Edge kind (see EdgeKind enum below) |
| `--format` | No | `text` | Output format |

**EdgeKind values:**

| Value | Meaning |
|-------|---------|
| `trace_used_evidence` | Trace consumed this evidence |
| `trace_produced_artifact` | Trace created this artifact |
| `trace_touched_entity` | Trace interacted with this entity |
| `trace_promoted_to_precedent` | Trace was promoted to this precedent |
| `entity_related_to` | General entity relationship |
| `entity_part_of` | Entity is part of another |
| `entity_depends_on` | Entity depends on another |
| `evidence_attached_to` | Evidence is attached to a target |
| `evidence_supports` | Evidence supports a claim |
| `precedent_applies_to` | Precedent applies to this domain/entity |
| `precedent_derived_from` | Precedent was derived from this source |

**Example:**

```bash
xpg curate link 01JRK5N7QF auth_service --kind entity_depends_on --format json
```

**JSON output (success):**

```json
{
  "status": "success",
  "command_id": "01JRK8B2QF8GHTM2XVZP3CWD9E",
  "operation": "link.create",
  "message": "Link created",
  "created_id": "01JRK8B3QF8GHTM2XVZP3CWD9E"
}
```

### `xpg curate label`

Add a label to an entity.

```bash
xpg curate label <target_id> <label> [--format text|json]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `target_id` | **Yes** | Entity ID to label |
| `label` | **Yes** | Label string to add |

**Example:**

```bash
xpg curate label 01JRK5N7QF critical-path --format json
```

**JSON output (success):**

```json
{
  "status": "success",
  "command_id": "01JRK9C1QF8GHTM2XVZP3CWD9E",
  "operation": "label.add",
  "message": "Label added",
  "created_id": null
}
```

### `xpg curate feedback`

Record feedback (rating and optional comment) on a trace or precedent.

```bash
xpg curate feedback <target_id> <rating> [--comment <text>] [--format text|json]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `target_id` | **Yes** | -- | Trace or precedent ID |
| `rating` | **Yes** | -- | Rating as float (0.0 to 1.0 by convention) |
| `--comment` | No | `null` | Optional text comment |
| `--format` | No | `text` | Output format |

**Example:**

```bash
xpg curate feedback 01JRK5N7QF 0.9 --comment "Solid pattern, well-documented" --format json
```

**JSON output (success):**

```json
{
  "status": "success",
  "command_id": "01JRKAB1QF8GHTM2XVZP3CWD9E",
  "operation": "feedback.record",
  "message": "Feedback recorded",
  "created_id": null
}
```

---

## Retrieve Commands

### `xpg retrieve trace`

Retrieve a specific trace by ID.

```bash
xpg retrieve trace <trace_id> [--format text|json]
```

**JSON output (found):** Full trace JSON as defined in [trace-format.md](trace-format.md).

**JSON output (not found):**

```json
{"status": "not_found", "trace_id": "01JRK5N7QF8GHTM2XVZP3CWD9E"}
```

Exit code 1 when not found.

### `xpg retrieve traces`

List recent traces.

```bash
xpg retrieve traces [--domain DOMAIN] [--limit N] [--fields FIELDS] [--truncate N] [--quiet] [--format text|json|jsonl|tsv]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--domain` | `null` | Domain filter |
| `--limit` | `20` | Maximum results |
| `--fields` | all | Comma-separated field list |
| `--truncate` | `null` | Max chars per text field |
| `--quiet` | `false` | Suppress Rich formatting |
| `--format` | `text` | Output format |

### `xpg retrieve search`

Full-text search across the document store.

```bash
xpg retrieve search <query> [--limit N] [--domain DOMAIN] [--format text|json]
```

| Argument/Option | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `query` | **Yes** | -- | Search query string |
| `--limit` | No | `20` | Maximum results |
| `--domain` | No | `null` | Domain scope filter |
| `--format` | No | `text` | Output format |

**Example:**

```bash
xpg retrieve search "connection pool configuration" --limit 5 --format json
```

**JSON output:**

```json
{
  "status": "ok",
  "query": "connection pool configuration",
  "count": 3,
  "results": [
    {"doc_id": "01JRK5N7QF", "content": "...", "snippet": "...", "metadata": {}}
  ]
}
```

### `xpg retrieve entity`

Retrieve a specific entity by ID.

```bash
xpg retrieve entity <entity_id> [--format text|json]
```

**JSON output (found):**

```json
{
  "node_id": "01JRK5N7QF",
  "node_type": "service",
  "properties": {"name": "auth-service", "domain": "platform"}
}
```

**JSON output (not found):**

```json
{"status": "not_found", "entity_id": "01JRK5N7QF"}
```

### `xpg retrieve precedents`

List precedents, optionally filtered by domain.

```bash
xpg retrieve precedents [--domain DOMAIN] [--limit N] [--format text|json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--domain` | `null` | Filter by domain |
| `--limit` | `20` | Maximum results |
| `--format` | `text` | Output format |

**JSON output:**

```json
{
  "status": "ok",
  "count": 2,
  "items": [
    {
      "event_id": "01JRKBC1QF",
      "entity_id": "01JRKBC2QF",
      "payload": {"title": "Database pool configuration pattern", "domain": "backend"}
    }
  ]
}
```

### `xpg retrieve pack`

Assemble a retrieval pack for a given intent.

```bash
xpg retrieve pack --intent <text> [--domain DOMAIN] [--agent AGENT_ID] [--max-items N] [--format text|json]
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--intent` | **Yes** | -- | Intent for context assembly |
| `--domain` | No | `null` | Domain scope |
| `--agent` | No | `null` | Agent ID scope |
| `--max-items` | No | `50` | Maximum items |
| `--format` | No | `text` | Output format |

**Example:**

```bash
xpg retrieve pack --intent "deploy checklist for staging" --domain platform --max-items 10 --format json
```

**JSON output:**

```json
{
  "status": "ok",
  "intent": "deploy checklist for staging",
  "domain": "platform",
  "agent_id": null,
  "count": 5,
  "items": ["01JRK5N7QF", "01JRK6M3QF", "01JRK7A3QF", "01JRK8B2QF", "01JRK9C1QF"]
}
```

---

## Python-Only Mutation API

The following operations exist in the `MutationExecutor` and `OperationRegistry` but are not yet exposed as CLI commands. Use them via the Python API.

### Operations

All operations go through the governed mutation pipeline: validate, policy check, idempotency check, execute, emit event.

```python
from xpgraph.mutate.commands import Command, Operation
from xpgraph.mutate.executor import MutationExecutor

executor = MutationExecutor(event_log=event_log)
result = executor.execute(command)
```

### Trace Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `trace.ingest` | `trace` (dict) | Ingest a full trace via the mutation pipeline |
| `trace.append_step` | `trace_id`, `step` (dict) | Append a step to an existing trace |
| `trace.record_outcome` | `trace_id`, `outcome` (dict) | Record the outcome of a trace |

**Example -- append step:**

```python
cmd = Command(
    operation=Operation.TRACE_APPEND_STEP,
    args={
        "trace_id": "01JRK5N7QF8GHTM2XVZP3CWD9E",
        "step": {
            "step_type": "tool_call",
            "name": "run_tests",
            "result": {"passed": 42, "failed": 0},
            "duration_ms": 15000,
        },
    },
    target_id="01JRK5N7QF8GHTM2XVZP3CWD9E",
    target_type="trace",
    requested_by="code-orchestrator",
)
result = executor.execute(cmd)
```

### Evidence Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `evidence.ingest` | `evidence` (dict) | Ingest evidence via the mutation pipeline |
| `evidence.attach` | `evidence_id`, `target_id`, `target_type` | Attach evidence to a trace, entity, or precedent |

### Entity Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `entity.create` | `entity_type`, `name` | Create a new entity |
| `entity.update` | `entity_id` | Update entity properties |
| `entity.merge` | `source_id`, `target_id` | Merge two entities |

**Example -- create entity:**

```python
cmd = Command(
    operation=Operation.ENTITY_CREATE,
    args={
        "entity_type": "service",
        "name": "auth-service",
        "properties": {"language": "python", "team": "platform"},
    },
    requested_by="code-orchestrator",
)
result = executor.execute(cmd)
# result.created_id contains the new entity ID
```

### Precedent Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `precedent.promote` | `trace_id`, `title`, `description` | Promote a trace to a precedent (also available via CLI) |
| `precedent.update` | `precedent_id` | Update an existing precedent |

### Link Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `link.create` | `source_id`, `target_id`, `edge_kind` | Create a directed edge (also available via CLI) |
| `link.remove` | `edge_id` | Remove an edge |

### Label Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `label.add` | `target_id`, `label` | Add a label (also available via CLI) |
| `label.remove` | `target_id`, `label` | Remove a label |

### Feedback Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `feedback.record` | `target_id`, `rating` | Record feedback (also available via CLI) |

### Maintenance Operations

| Operation | Required Args | Description |
|-----------|---------------|-------------|
| `redaction.apply` | `target_id`, `reason` | Redact content from a target |
| `retention.prune` | (none) | Run retention pruning |
| `pack.publish` | `pack` (dict) | Publish a context pack |
| `pack.invalidate` | `pack_id` | Invalidate a published pack |

### Batch Execution

Execute multiple commands as a batch:

```python
from xpgraph.mutate.commands import CommandBatch, BatchStrategy

batch = CommandBatch(
    commands=[cmd1, cmd2, cmd3],
    strategy=BatchStrategy.STOP_ON_ERROR,
    requested_by="code-orchestrator",
)
results = executor.execute_batch(batch)
```

| Strategy | Behavior |
|----------|----------|
| `sequential` | Execute all commands in order |
| `stop_on_error` | Stop on first failure or rejection |
| `continue_on_error` | Execute all, collect all results |

### CommandResult

Every mutation returns a `CommandResult`:

| Field | Type | Description |
|-------|------|-------------|
| `command_id` | `string` | ID of the executed command |
| `status` | `CommandStatus` | `success`, `rejected`, `failed`, or `duplicate` |
| `operation` | `string` | The operation that was executed |
| `target_id` | `string` or `null` | Target entity ID |
| `created_id` | `string` or `null` | ID of newly created object |
| `message` | `string` | Human-readable result message |
| `warnings` | `list[string]` | Policy warnings |
| `metadata` | `dict` | Additional metadata |
| `executed_at` | `datetime` | When the command was executed |

### Idempotency

Set `idempotency_key` on a `Command` to prevent duplicate execution:

```python
cmd = Command(
    operation=Operation.ENTITY_CREATE,
    args={"entity_type": "service", "name": "auth-service"},
    idempotency_key="create_auth_service_20260310",
    requested_by="code-orchestrator",
)
```

If the same key has been seen before (in-memory or in the event log), the executor returns `CommandStatus.DUPLICATE` without re-executing.

---

## Analyze Commands

### `xpg analyze context-effectiveness`

Analyze which context items correlate with task success.

```bash
xpg analyze context-effectiveness [--days N] [--min-appearances N] [--format text|json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | `30` | Days of history to analyze |
| `--min-appearances` | `2` | Minimum item appearances to include |

Shows per-item success rates and flags noise candidates (items correlating with failure).

### `xpg analyze token-usage`

Analyze token usage across CLI, MCP, and SDK layers.

```bash
xpg analyze token-usage [--days N] [--format text|json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | `7` | Days of history to analyze |

Shows total tokens, average per response, breakdown by layer and operation, and over-budget alerts.

---

## REST API

Start with `xpg admin serve` or `xpg-api`. Base path: `/api/v1/`.

### Ingest

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/traces` | Trace JSON | Ingest a trace |
| POST | `/evidence` | Evidence JSON | Ingest evidence |

### Retrieve

| Method | Endpoint | Params/Body | Description |
|--------|----------|-------------|-------------|
| GET | `/search` | `?q=...&domain=...&limit=20` | Full-text search |
| POST | `/packs` | `{intent, domain?, max_items?, max_tokens?}` | Assemble context pack |
| GET | `/entities/{id}` | — | Get entity with subgraph |
| GET | `/traces` | `?domain=...&limit=20` | List traces |
| GET | `/traces/{id}` | — | Get trace by ID |
| GET | `/precedents` | `?domain=...&limit=20` | List precedents |

### Curate

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/precedents` | `{trace_id, title, description}` | Promote trace |
| POST | `/links` | `{source_id, target_id, edge_kind?}` | Create edge |
| POST | `/entities` | `{entity_type, name, properties?}` | Create entity |
| POST | `/feedback` | `{target_id, rating, comment?}` | Record feedback |
| POST | `/packs/{pack_id}/feedback` | `{rating, success?, notes?}` | Pack-specific feedback |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/stats` | Store statistics |
| GET | `/effectiveness` | Context effectiveness report |

---

## MCP Macro Tools

Start with `xpg-mcp`. 8 tools returning token-budgeted markdown.

| Tool | Args | Returns |
|------|------|---------|
| `get_context` | `intent`, `domain?`, `max_tokens?` | Markdown pack from docs + graph + traces |
| `save_experience` | `trace_json` | Confirmation with trace_id |
| `save_knowledge` | `name`, `entity_type?`, `properties?`, `relates_to?`, `edge_kind?` | Confirmation with entity_id |
| `save_memory` | `content`, `metadata?`, `doc_id?` | Confirmation with doc_id |
| `get_lessons` | `domain?`, `limit?`, `max_tokens?` | Markdown list of precedents |
| `get_graph` | `entity_id`, `depth?`, `max_tokens?` | Markdown subgraph |
| `record_feedback` | `trace_id`, `success`, `notes?` | Confirmation |
| `search` | `query`, `limit?`, `max_tokens?` | Markdown search results |

All read tools track token usage in the event log for observability.

### OpenClaw Setup

OpenClaw has native MCP client support. Add XPG to your `openclaw.json`:

```json
{
  "mcpServers": {
    "experience-graph": {
      "command": "xpg-mcp",
      "args": []
    }
  }
}
```

Or install via ClawHub:

```bash
clawhub install experience-graph
```

After restarting OpenClaw, the agent has access to all 8 macro tools above. See [`integrations/openclaw/`](../../integrations/openclaw/) for the full setup guide and skill definition.

---

## Python SDK

```python
from xpgraph_sdk import XPGClient

# Local mode (no server needed)
client = XPGClient()

# Remote mode (via REST API)
client = XPGClient(base_url="http://localhost:8420")
```

### Client Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `ingest_trace(trace: dict)` | `str` (trace_id) | Ingest a trace |
| `search(query, domain?, limit?)` | `list[dict]` | Search documents |
| `get_trace(trace_id)` | `dict \| None` | Get trace by ID |
| `list_traces(domain?, limit?)` | `list[dict]` | List recent traces |
| `assemble_pack(intent, **kwargs)` | `dict` | Assemble context pack |
| `get_entity(entity_id)` | `dict \| None` | Get entity |
| `create_entity(name, entity_type?, properties?)` | `str` (node_id) | Create entity |
| `create_link(source_id, target_id, edge_kind?)` | `str` (edge_id) | Create edge |
| `close()` | — | Release resources |

### Skill Functions

Pre-summarized markdown for LLM context injection:

```python
from xpgraph_sdk.skills import (
    get_context_for_task,
    get_latest_successful_trace,
    save_trace_and_extract_lessons,
    get_recent_activity,
)

context = get_context_for_task(client, "implement retry logic", domain="backend")
```

All skill functions return `str` (markdown), not data objects.
