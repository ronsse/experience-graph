# Playbooks

Structured operational procedures for common agent tasks. Each playbook has a trigger condition, numbered steps with exact commands, expected output, and error handling.

---

## Playbook 1: After Completing a Task

**When to use:** After finishing any meaningful unit of work (tool call, code change, deployment, review, investigation).

### Steps

1. Construct the trace JSON. Include at minimum: `source`, `intent`, `context`, and one or more `steps`. Add `outcome` if the result is known.

```bash
cat <<'EOF' > /tmp/trace.json
{
  "source": "agent",
  "intent": "Migrated user table to add email_verified column",
  "steps": [
    {
      "step_type": "tool_call",
      "name": "run_migration",
      "args": {"migration": "003_add_email_verified.sql"},
      "result": {"rows_affected": 0, "status": "applied"},
      "duration_ms": 3200
    },
    {
      "step_type": "tool_call",
      "name": "run_tests",
      "args": {"suite": "unit"},
      "result": {"passed": 127, "failed": 0},
      "duration_ms": 8500
    }
  ],
  "outcome": {
    "status": "success",
    "summary": "Migration applied, all tests pass"
  },
  "context": {
    "agent_id": "code-orchestrator",
    "domain": "backend",
    "started_at": "2026-03-10T14:00:00Z",
    "ended_at": "2026-03-10T14:05:00Z"
  }
}
EOF
```

2. Ingest the trace.

```bash
xpg ingest trace /tmp/trace.json --format json
```

3. Verify the output contains `"status": "ingested"` and capture the `trace_id`.

**Expected output:**

```json
{"status": "ingested", "trace_id": "01JRK5N7QF8GHTM2XVZP3CWD9E", "source": "agent", "intent": "Migrated user table to add email_verified column"}
```

4. (Optional) Record feedback if quality is known.

```bash
xpg curate feedback 01JRK5N7QF8GHTM2XVZP3CWD9E 0.95 --comment "Clean migration, zero-downtime" --format json
```

### If It Fails

- **Validation error:** Fix the JSON according to the error message. See [trace-format.md](trace-format.md) for field requirements.
- **Store not initialized:** Run `xpg admin init` first.
- **File not found:** Check the file path. Use `-` for stdin if piping.

---

## Playbook 2: Before Starting Work

**When to use:** Before beginning any non-trivial task. Assemble context from the experience graph to avoid repeating past mistakes and to reuse known patterns.

### Steps

1. Search for prior art related to the task.

```bash
xpg retrieve search "database migration email_verified" --limit 10 --format json
```

2. Check for applicable precedents.

```bash
xpg retrieve precedents --domain backend --format json
```

3. Assemble a context pack if the task is complex.

```bash
xpg retrieve pack --intent "Add email_verified column to user table" --domain backend --max-items 20 --format json
```

4. Review the returned items. Look for:
   - Traces of similar past work (check outcome status)
   - Precedents with applicable patterns
   - Evidence documents with relevant guidelines

5. Incorporate relevant findings into the task plan before starting.

### If It Fails

- **Zero results:** Try broader search terms. Remove the `--domain` filter.
- **Store not initialized:** Run `xpg admin init`.

---

## Playbook 3: Discovering a Reusable Pattern

**When to use:** When a trace contains a pattern worth reusing -- a successful approach to a recurring problem, a non-obvious configuration, or a hard-won debugging technique.

### Steps

1. Identify the source trace ID. If just completed, it was returned by `xpg ingest trace`.

2. Retrieve the trace to confirm it is worth promoting.

```bash
xpg retrieve trace 01JRK5N7QF8GHTM2XVZP3CWD9E --format json
```

3. Promote the trace to a precedent.

```bash
xpg curate promote 01JRK5N7QF8GHTM2XVZP3CWD9E \
  --title "Zero-downtime column addition pattern" \
  --description "When adding a nullable column to a large table: use ALTER TABLE ADD COLUMN with DEFAULT NULL, deploy code that handles both states, then backfill in batches of 1000 rows" \
  --by code-orchestrator \
  --format json
```

4. Verify the output contains `"status": "success"` and note the `created_id`.

**Expected output:**

```json
{
  "status": "success",
  "command_id": "01JRK7A3QF8GHTM2XVZP3CWD9E",
  "operation": "precedent.promote",
  "message": "Precedent promoted",
  "created_id": "01JRK7A4QF8GHTM2XVZP3CWD9E"
}
```

5. (Optional) Link the precedent to related entities.

```bash
xpg curate link 01JRK7A4QF8GHTM2XVZP3CWD9E user_service_entity_id \
  --kind precedent_applies_to \
  --format json
```

### If It Fails

- **Trace not found:** Confirm the trace was ingested. Use `xpg retrieve trace <id>` to check.
- **Policy rejection:** The mutation executor may reject the operation if policies forbid it. Check the `message` field in the response.

---

## Playbook 4: Recording Feedback

**When to use:** After observing the outcome of a traced action -- either your own evaluation or a human review.

### Steps

1. Determine the target ID (trace or precedent) and the quality rating.

2. Record the feedback.

```bash
xpg curate feedback 01JRK5N7QF8GHTM2XVZP3CWD9E 0.4 \
  --comment "Migration succeeded but caused 30s of increased latency during backfill" \
  --format json
```

**Expected output:**

```json
{
  "status": "success",
  "command_id": "01JRKAB1QF8GHTM2XVZP3CWD9E",
  "operation": "feedback.record",
  "message": "Feedback recorded",
  "created_id": null
}
```

### Rating Guidelines

| Rating | Meaning |
|--------|---------|
| 0.0 - 0.2 | Harmful or incorrect -- caused problems |
| 0.2 - 0.4 | Poor -- significant issues |
| 0.4 - 0.6 | Acceptable -- worked but with notable problems |
| 0.6 - 0.8 | Good -- achieved goals with minor issues |
| 0.8 - 1.0 | Excellent -- clean execution, reusable pattern |

### If It Fails

- **Validation error:** Ensure `rating` is a valid float.
- **No handler:** The feedback handler may not be registered. This is a system configuration issue.

---

## Playbook 5: Building the Knowledge Graph

**When to use:** When you need to register a new system, service, person, concept, or other entity and connect it to existing knowledge.

### Steps

1. Create the entity (Python API only -- not yet available as CLI command).

```python
from xpgraph.mutate.commands import Command, Operation
from xpgraph.mutate.executor import MutationExecutor
from xpgraph_cli.stores import get_event_log

event_log = get_event_log()
executor = MutationExecutor(event_log=event_log)

cmd = Command(
    operation=Operation.ENTITY_CREATE,
    args={
        "entity_type": "service",
        "name": "payment-gateway",
        "properties": {"language": "go", "team": "payments", "tier": "critical"},
    },
    requested_by="code-orchestrator",
)
result = executor.execute(cmd)
entity_id = result.created_id
event_log.close()
```

2. Link the entity to related entities.

```bash
xpg curate link <new_entity_id> <related_entity_id> --kind entity_depends_on --format json
```

3. Add labels for quick filtering.

```bash
xpg curate label <new_entity_id> production --format json
xpg curate label <new_entity_id> tier-1 --format json
```

4. Attach supporting evidence if available.

```bash
# First ingest the evidence
cat <<'EOF' > /tmp/arch-doc.json
{
  "evidence_type": "document",
  "content": "Payment gateway architecture: uses Stripe as primary processor with fallback to Adyen...",
  "source_origin": "manual",
  "uri": "https://wiki.internal/payment-gateway-arch"
}
EOF

xpg ingest evidence /tmp/arch-doc.json --format json
```

5. Link the evidence to the entity.

```python
cmd = Command(
    operation=Operation.EVIDENCE_ATTACH,
    args={
        "evidence_id": "<evidence_id_from_step_4>",
        "target_id": "<entity_id_from_step_1>",
        "target_type": "entity",
    },
    requested_by="code-orchestrator",
)
result = executor.execute(cmd)
```

### If It Fails

- **Missing required args:** `entity.create` requires `entity_type` and `name`. Check `EntityType` enum for valid types: `person`, `system`, `service`, `team`, `document`, `concept`, `domain`, `file`, `project`, `tool`.

---

## Playbook 6: Searching for Prior Art

**When to use:** Before starting new work, investigating a problem, or making a design decision. Search the experience graph to find what has been done before.

### Steps

1. Start with a keyword search.

```bash
xpg retrieve search "payment retry logic" --limit 10 --format json
```

2. If results are sparse, try broader terms or remove domain filters.

```bash
xpg retrieve search "retry" --limit 20 --format json
```

3. Check for precedents in the relevant domain.

```bash
xpg retrieve precedents --domain payments --format json
```

4. If you find a relevant trace, retrieve its full details.

```bash
xpg retrieve trace 01JRK5N7QF8GHTM2XVZP3CWD9E --format json
```

5. If you find a relevant entity, look at its connections.

```bash
xpg retrieve entity 01JRK5N7QF --format json
```

6. For complex tasks, assemble a full context pack.

```bash
xpg retrieve pack \
  --intent "Implement payment retry with exponential backoff" \
  --domain payments \
  --max-items 15 \
  --format json
```

7. Review the results. Key signals:
   - **Traces with `outcome.status: success`** -- reusable approaches
   - **Traces with `outcome.status: failure`** -- pitfalls to avoid
   - **Precedents** -- distilled institutional knowledge
   - **Evidence** -- supporting documentation and guidelines

### If It Fails

- **Empty results:** The graph may not have relevant data yet. Proceed with the task and ingest a trace when done (Playbook 1).
- **Too many results:** Add `--domain` filter or more specific search terms. Reduce `--limit`.

---

## Playbook 7: Using MCP Macro Tools

**When to use:** When an AI agent needs context from XPG through an MCP-compatible IDE (Cursor, Cline, Claude Code).

### Steps

1. Ensure the MCP server is running:

```bash
xpg-mcp
```

2. Use `get_context` to retrieve relevant context before starting work:

```
Tool: get_context
Args: {"intent": "implement payment retry with backoff", "domain": "backend", "max_tokens": 1500}
```

3. After completing work, save the experience:

```
Tool: save_experience
Args: {"trace_json": "{\"source\": \"agent\", \"intent\": \"...\", ...}"}
```

4. Record whether the task succeeded:

```
Tool: record_feedback
Args: {"trace_id": "01JRK5N7QF", "success": true, "notes": "Clean implementation, all tests pass"}
```

### Key Points

- All tools return **markdown**, not JSON — ready for LLM consumption
- Use `max_tokens` to control response size (default: 2000)
- `get_context` searches documents, graph, and traces simultaneously
- `search` is for targeted queries; `get_context` is for broad task context

---

## Playbook 8: Using the Python SDK

**When to use:** When integrating XPG into an orchestrator (LangGraph, CrewAI) or custom agent code.

### Steps

1. Create a client:

```python
from xpgraph_sdk import XPGClient

# Local mode (no server needed)
client = XPGClient()

# Remote mode (against REST API)
client = XPGClient(base_url="http://localhost:8420")
```

2. Get pre-summarized context for a task:

```python
from xpgraph_sdk.skills import get_context_for_task

context_md = get_context_for_task(
    client, "implement payment retry", domain="backend", max_tokens=1500
)
# context_md is a markdown string — inject directly into the LLM prompt
```

3. Ingest a trace after completing work:

```python
trace_id = client.ingest_trace({
    "source": "agent",
    "intent": "Implemented payment retry with exponential backoff",
    "steps": [...],
    "outcome": {"status": "success", "summary": "All tests pass"},
    "context": {"agent_id": "orchestrator", "domain": "backend"},
})
```

4. Always close the client when done:

```python
client.close()
```

### If It Fails

- **ConnectionError (remote mode):** Ensure the API server is running (`xpg admin serve`).
- **Store not initialized (local mode):** Run `xpg admin init`.

---

## Playbook 9: Importing External Data

**When to use:** When you want to populate the knowledge graph from dbt lineage or OpenLineage events.

### dbt Manifest

1. Run dbt to generate the manifest:

```bash
cd my-dbt-project
dbt compile  # or dbt run
```

2. Import the manifest:

```bash
xpg ingest dbt-manifest target/manifest.json --format json
```

3. Verify entities were created:

```bash
xpg retrieve search "my_model_name" --format json
```

### OpenLineage Events

1. Collect OpenLineage events (JSON array or newline-delimited JSON):

```bash
xpg ingest openlineage lineage-events.json --format json
```

2. The worker creates:
   - **Dataset entities** for each input/output dataset
   - **Job entities** for each job
   - **`reads_from`** edges from jobs to input datasets
   - **`writes_to`** edges from jobs to output datasets

### Key Points

- Both commands are **idempotent** — re-running produces the same graph
- dbt descriptions are indexed in the document store for full-text search
- Use `xpg retrieve entity <id>` to explore the imported graph

---

## Playbook 10: Analyzing Context Quality

**When to use:** Periodically (weekly or after a batch of tasks) to improve retrieval quality.

### Steps

1. Check context effectiveness:

```bash
xpg analyze context-effectiveness --days 30 --format json
```

2. Review the report:
   - **Success rate** — overall ratio of positive feedback
   - **Item scores** — which items correlate with success or failure
   - **Noise candidates** — items that appear frequently but correlate with failure

3. Check token usage:

```bash
xpg analyze token-usage --days 7 --format json
```

4. Review for over-budget responses — tools consistently exceeding their token budget may need lower limits or content trimming.

### If It Fails

- **No feedback recorded:** Use `xpg curate feedback` or `POST /api/v1/packs/{pack_id}/feedback` to record outcomes. The analysis requires feedback events to be meaningful.

---

## Playbook 11: OpenClaw Integration

**When to use:** When setting up Experience Graph as a structured memory backend for OpenClaw agents.

### Steps

1. Install Experience Graph and initialize stores.

```bash
pip install experience-graph
xpg admin init
```

2. Verify the MCP server starts.

```bash
xpg-mcp
```

Press Ctrl+C after confirming it starts without errors.

3. Add XPG to your `openclaw.json`:

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

4. Restart OpenClaw. The agent now has access to 8 macro tools.

5. Verify the agent can use XPG tools by asking it to run:

```
get_context(intent="test connection", max_tokens=500)
```

### Usage Patterns

**Retrieve before acting:** Before starting non-trivial work, have the agent call `get_context` with the task intent. This returns relevant traces, precedents, and evidence.

**Record after success:** After completing meaningful work, have the agent call `save_experience` with a trace of what it did, then `record_feedback` with the outcome.

**Build the knowledge graph:** When the agent discovers or creates important entities (services, concepts, patterns), use `save_knowledge` to add them to the graph with typed relationships.

### When to Use XPG vs Built-in Memory

- **Built-in memory:** Daily notes, session context, quick personal reminders.
- **XPG:** Structured traces of work, reusable precedents, knowledge graph entities with typed relationships, temporal versioning, cross-agent institutional knowledge.

### If It Fails

- **MCP server won't start:** Run `xpg admin health` to check store status. Run `xpg admin init` if stores are missing.
- **Agent doesn't see tools:** Ensure `openclaw.json` has the correct `mcpServers` entry and OpenClaw has been restarted.
- **Tools return empty results:** The graph is likely empty. Ingest some traces first (see Playbook 1) or use `save_memory` to seed documents.
