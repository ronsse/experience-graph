# Schema Catalog

Machine-readable reference for all Experience Graph Pydantic schemas. All models use `extra="forbid"` -- unrecognized fields cause validation errors.

Base schema version: `0.1.0`

---

## Trace

Immutable record of an agent or workflow execution.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `trace_id` | `string` | No | ULID | Unique identifier |
| `source` | `TraceSource` | **Yes** | -- | Producer type |
| `intent` | `string` | **Yes** | -- | What this trace accomplished |
| `steps` | `list[TraceStep]` | No | `[]` | Steps executed |
| `evidence_used` | `list[EvidenceRef]` | No | `[]` | Evidence consumed |
| `artifacts_produced` | `list[ArtifactRef]` | No | `[]` | Artifacts created |
| `outcome` | `Outcome` or `null` | No | `null` | Execution outcome |
| `feedback` | `list[Feedback]` | No | `[]` | Quality feedback |
| `context` | `TraceContext` | **Yes** | -- | Execution context |
| `metadata` | `dict` | No | `{}` | Arbitrary key-value pairs |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

Related: TraceStep, Outcome, Feedback, TraceContext, EvidenceRef, ArtifactRef

```json
{
  "source": "agent",
  "intent": "Fix broken import in auth module",
  "steps": [
    {"step_type": "tool_call", "name": "edit_file", "args": {"file": "auth.py"}, "result": {"status": "applied"}, "duration_ms": 150}
  ],
  "outcome": {"status": "success", "summary": "Import fixed"},
  "context": {"agent_id": "code-orchestrator", "domain": "backend"}
}
```

---

## TraceStep

A single step within a trace.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `step_type` | `string` | **Yes** | -- | Step category (e.g., `tool_call`, `llm_call`, `decision`, `observation`) |
| `name` | `string` | **Yes** | -- | Step name |
| `args` | `dict` | No | `{}` | Input arguments |
| `result` | `dict` | No | `{}` | Output result |
| `error` | `string` or `null` | No | `null` | Error message if failed |
| `duration_ms` | `int` or `null` | No | `null` | Duration in milliseconds |
| `started_at` | `datetime` | No | UTC now | When step started |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{
  "step_type": "tool_call",
  "name": "search_codebase",
  "args": {"query": "database pool", "file_pattern": "*.py"},
  "result": {"matches": 5, "files": ["db/pool.py", "db/config.py"]},
  "duration_ms": 320
}
```

---

## Outcome

Outcome of a trace execution.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `status` | `OutcomeStatus` | No | `"unknown"` | Outcome status |
| `metrics` | `dict` | No | `{}` | Quantitative metrics |
| `summary` | `string` or `null` | No | `null` | Brief summary |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{
  "status": "partial",
  "metrics": {"tests_passed": 18, "tests_failed": 2},
  "summary": "Deployed but 2 smoke tests failed"
}
```

---

## Feedback

Quality feedback on a trace or precedent.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `feedback_id` | `string` | No | ULID | Unique identifier |
| `rating` | `float` or `null` | No | `null` | Quality score (0.0 to 1.0 by convention) |
| `label` | `string` or `null` | No | `null` | Categorical label |
| `comment` | `string` or `null` | No | `null` | Free-text comment |
| `given_by` | `string` | No | `"unknown"` | Who provided feedback |
| `given_at` | `datetime` | No | UTC now | When feedback was given |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{
  "rating": 0.85,
  "label": "good",
  "comment": "Clean approach, well-tested",
  "given_by": "tech-lead"
}
```

---

## TraceContext

Context in which a trace was executed.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `agent_id` | `string` or `null` | No | `null` | Agent identifier |
| `team` | `string` or `null` | No | `null` | Team or group |
| `domain` | `string` or `null` | No | `null` | Domain scope |
| `workflow_id` | `string` or `null` | No | `null` | Workflow identifier |
| `parent_trace_id` | `string` or `null` | No | `null` | Parent trace for nesting |
| `started_at` | `datetime` | No | UTC now | Execution start |
| `ended_at` | `datetime` or `null` | No | `null` | Execution end |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{
  "agent_id": "code-orchestrator",
  "domain": "backend",
  "team": "platform",
  "started_at": "2026-03-10T14:00:00Z",
  "ended_at": "2026-03-10T14:05:00Z"
}
```

---

## EvidenceRef

Reference to evidence used or produced by a trace.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `evidence_id` | `string` | **Yes** | -- | Evidence identifier |
| `role` | `string` | No | `"input"` | Role (e.g., `input`, `reference`, `context`) |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"evidence_id": "01JRK6M3QF8GHTM2XVZP3CWD9E", "role": "input"}
```

---

## ArtifactRef

Reference to an artifact produced by a trace.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `artifact_id` | `string` | **Yes** | -- | Artifact identifier |
| `artifact_type` | `string` | **Yes** | -- | Type (e.g., `file`, `pr`, `note`, `entity`, `deployment`) |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"artifact_id": "pr_847", "artifact_type": "pr"}
```

---

## Entity

A named entity in the experience graph.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `entity_id` | `string` | No | ULID | Unique identifier |
| `entity_type` | `EntityType` | **Yes** | -- | Entity type |
| `name` | `string` | **Yes** | -- | Display name |
| `properties` | `dict` | No | `{}` | Arbitrary properties |
| `source` | `EntitySource` or `null` | No | `null` | Origin information |
| `metadata` | `dict` | No | `{}` | Arbitrary metadata |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

```json
{
  "entity_type": "service",
  "name": "auth-service",
  "properties": {"language": "python", "team": "platform", "tier": "critical"},
  "source": {"origin": "manual", "detail": "Registered during onboarding"}
}
```

---

## EntitySource

Origin information for an entity.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `origin` | `string` | **Yes** | -- | Where this entity came from (e.g., `manual`, `trace`, `ingestion`) |
| `detail` | `string` or `null` | No | `null` | Additional detail |
| `trace_id` | `string` or `null` | No | `null` | Trace that created this entity |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"origin": "trace", "trace_id": "01JRK5N7QF8GHTM2XVZP3CWD9E"}
```

---

## Evidence

A piece of evidence supporting traces, precedents, or entities. The `content_hash` is auto-computed from `content` if not provided.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `evidence_id` | `string` | No | ULID | Unique identifier |
| `evidence_type` | `EvidenceType` | **Yes** | -- | Type of evidence |
| `content` | `string` or `null` | No | `null` | Text content |
| `uri` | `string` or `null` | No | `null` | URI or file path |
| `content_hash` | `string` | No | `""` (auto-computed) | SHA-256 hash prefix of content |
| `source_origin` | `string` | **Yes** | -- | Where this evidence came from (`trace`, `manual`, `ingestion`) |
| `source_trace_id` | `string` or `null` | No | `null` | Trace that produced this evidence |
| `attached_to` | `list[AttachmentRef]` | No | `[]` | What this evidence is attached to |
| `metadata` | `dict` | No | `{}` | Arbitrary metadata |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

Related: AttachmentRef

```json
{
  "evidence_type": "snippet",
  "content": "Max connection pool size should be 20 per process with 30s idle timeout",
  "source_origin": "manual",
  "uri": "https://wiki.internal/db-guidelines#connection-pooling"
}
```

---

## AttachmentRef

Reference linking evidence to a target object.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_id` | `string` | **Yes** | -- | Target object ID |
| `target_type` | `string` | **Yes** | -- | Target type (`trace`, `entity`, `precedent`) |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"target_id": "01JRK5N7QF8GHTM2XVZP3CWD9E", "target_type": "trace"}
```

---

## Precedent

Reusable institutional knowledge distilled from one or more traces.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `precedent_id` | `string` | No | ULID | Unique identifier |
| `source_trace_ids` | `list[string]` | No | `[]` | Traces this was derived from |
| `title` | `string` | **Yes** | -- | Precedent title |
| `description` | `string` | **Yes** | -- | Detailed description of the pattern |
| `pattern` | `string` or `null` | No | `null` | Formal pattern description |
| `applicability` | `list[string]` | No | `[]` | Where this precedent applies |
| `confidence` | `float` | No | `0.0` | Confidence score (0.0 to 1.0) |
| `promoted_by` | `string` | **Yes** | -- | Who promoted this precedent |
| `evidence_refs` | `list[string]` | No | `[]` | Supporting evidence IDs |
| `feedback` | `list[Feedback]` | No | `[]` | Quality feedback |
| `metadata` | `dict` | No | `{}` | Arbitrary metadata |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

```json
{
  "title": "Zero-downtime column addition pattern",
  "description": "Add nullable column with DEFAULT NULL, deploy code handling both states, backfill in batches",
  "source_trace_ids": ["01JRK5N7QF8GHTM2XVZP3CWD9E"],
  "applicability": ["database", "migration", "production"],
  "confidence": 0.9,
  "promoted_by": "code-orchestrator"
}
```

---

## Pack

A context pack assembled for an agent or workflow.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `pack_id` | `string` | No | ULID | Unique identifier |
| `intent` | `string` | **Yes** | -- | Intent for pack assembly |
| `items` | `list[PackItem]` | No | `[]` | Included items |
| `retrieval_report` | `RetrievalReport` | No | Default report | How items were retrieved |
| `policies_applied` | `list[string]` | No | `[]` | Policies that were applied |
| `budget` | `PackBudget` | No | Default budget | Budget constraints |
| `domain` | `string` or `null` | No | `null` | Domain scope |
| `agent_id` | `string` or `null` | No | `null` | Agent scope |
| `assembled_at` | `datetime` | No | UTC now | When pack was assembled |
| `metadata` | `dict` | No | `{}` | Arbitrary metadata |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

Related: PackItem, PackBudget, RetrievalReport

```json
{
  "intent": "Deploy checklist for staging",
  "domain": "platform",
  "agent_id": "deploy-agent",
  "budget": {"max_items": 20, "max_tokens": 8000},
  "items": [
    {"item_id": "01JRK5N7QF", "item_type": "precedent", "excerpt": "Always run smoke tests after deploy", "relevance_score": 0.95}
  ],
  "retrieval_report": {"queries_run": 2, "candidates_found": 15, "items_selected": 8, "strategies_used": ["keyword", "semantic"]}
}
```

---

## PackItem

A single item in a context pack.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `item_id` | `string` | **Yes** | -- | Item identifier |
| `item_type` | `string` | **Yes** | -- | Type (`trace`, `evidence`, `precedent`, `entity`, `document`, `vector`) |
| `excerpt` | `string` | No | `""` | Text excerpt |
| `relevance_score` | `float` | No | `0.0` | Relevance score |
| `metadata` | `dict` | No | `{}` | Additional metadata |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"item_id": "01JRK5N7QF", "item_type": "trace", "excerpt": "Fixed auth import issue", "relevance_score": 0.87}
```

---

## PackBudget

Budget constraints for a context pack.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_items` | `int` | No | `50` | Maximum items |
| `max_tokens` | `int` | No | `8000` | Maximum estimated tokens |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"max_items": 20, "max_tokens": 4000}
```

---

## RetrievalReport

Report on how pack items were retrieved.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `queries_run` | `int` | No | `0` | Number of queries executed |
| `candidates_found` | `int` | No | `0` | Total candidates before filtering |
| `items_selected` | `int` | No | `0` | Items that made it into the pack |
| `duration_ms` | `int` | No | `0` | Total retrieval time |
| `strategies_used` | `list[string]` | No | `[]` | Strategy names used (e.g., `keyword`, `semantic`, `graph`) |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"queries_run": 3, "candidates_found": 42, "items_selected": 12, "duration_ms": 150, "strategies_used": ["keyword", "semantic", "graph"]}
```

---

## Edge

A directed edge in the experience graph.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `edge_id` | `string` | No | ULID | Unique identifier |
| `source_id` | `string` | **Yes** | -- | Source node ID |
| `target_id` | `string` | **Yes** | -- | Target node ID |
| `edge_kind` | `EdgeKind` | **Yes** | -- | Relationship type |
| `properties` | `dict` | No | `{}` | Arbitrary properties |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

```json
{
  "source_id": "01JRK5N7QF",
  "target_id": "01JRK6M3QF",
  "edge_kind": "entity_depends_on",
  "properties": {"strength": "hard"}
}
```

---

## Policy

Governance policy controlling operations in the experience graph.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `policy_id` | `string` | No | ULID | Unique identifier |
| `policy_type` | `PolicyType` | **Yes** | -- | Policy type |
| `scope` | `PolicyScope` | **Yes** | -- | Where the policy applies |
| `rules` | `list[PolicyRule]` | No | `[]` | Policy rules |
| `enforcement` | `Enforcement` | No | `"enforce"` | Enforcement level |
| `metadata` | `dict` | No | `{}` | Arbitrary metadata |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |
| `created_at` | `datetime` | No | UTC now | Creation timestamp |
| `updated_at` | `datetime` | No | UTC now | Update timestamp |

Related: PolicyScope, PolicyRule

```json
{
  "policy_type": "mutation",
  "scope": {"level": "domain", "value": "production"},
  "rules": [
    {"operation": "entity.create", "condition": "always", "action": "require_approval"}
  ],
  "enforcement": "enforce"
}
```

---

## PolicyScope

Scope at which a policy applies.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `level` | `string` | **Yes** | -- | Scope level (`global`, `domain`, `team`, `entity_type`) |
| `value` | `string` or `null` | No | `null` | Scope value (e.g., domain name) |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"level": "domain", "value": "payments"}
```

---

## PolicyRule

A single rule within a policy.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `operation` | `string` | **Yes** | -- | Operation to match (e.g., `precedent.promote`, `*`) |
| `condition` | `string` | No | `"always"` | When the rule applies |
| `action` | `string` | No | `"allow"` | What to do (`allow`, `deny`, `require_approval`, `warn`) |
| `params` | `dict` | No | `{}` | Additional parameters |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{"operation": "entity.create", "condition": "always", "action": "require_approval"}
```

---

## Command

A mutation command submitted to the governed write pipeline.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `command_id` | `string` | No | ULID | Unique identifier |
| `operation` | `Operation` | **Yes** | -- | Mutation operation |
| `target_id` | `string` or `null` | No | `null` | Target object ID |
| `target_type` | `string` or `null` | No | `null` | Target object type |
| `args` | `dict` | No | `{}` | Operation arguments |
| `requested_by` | `string` | No | `"unknown"` | Who requested the mutation |
| `idempotency_key` | `string` or `null` | No | `null` | Key for deduplication |
| `metadata` | `dict` | No | `{}` | Arbitrary metadata |
| `created_at` | `datetime` | No | UTC now | When command was created |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{
  "operation": "entity.create",
  "args": {"entity_type": "service", "name": "auth-service"},
  "requested_by": "code-orchestrator",
  "idempotency_key": "create_auth_20260310"
}
```

---

## CommandResult

Result of executing a command through the mutation pipeline.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `command_id` | `string` | **Yes** | -- | Command that was executed |
| `status` | `CommandStatus` | **Yes** | -- | Outcome status |
| `operation` | `Operation` | **Yes** | -- | Operation that was executed |
| `target_id` | `string` or `null` | No | `null` | Target object ID |
| `created_id` | `string` or `null` | No | `null` | Newly created object ID |
| `message` | `string` | No | `""` | Result message |
| `warnings` | `list[string]` | No | `[]` | Policy warnings |
| `metadata` | `dict` | No | `{}` | Additional metadata |
| `executed_at` | `datetime` | No | UTC now | When command was executed |
| `schema_version` | `string` | No | `"0.1.0"` | Schema version |

```json
{
  "command_id": "01JRK7A3QF8GHTM2XVZP3CWD9E",
  "status": "success",
  "operation": "entity.create",
  "created_id": "01JRK7A4QF8GHTM2XVZP3CWD9E",
  "message": "Entity created"
}
```

---

## Enums

### TraceSource

| Value | Description |
|-------|-------------|
| `agent` | AI agent execution |
| `human` | Human action |
| `workflow` | Automated workflow |
| `system` | System-level operation |

### OutcomeStatus

| Value | Description |
|-------|-------------|
| `success` | All goals achieved |
| `failure` | Goals not achieved |
| `partial` | Some goals achieved |
| `unknown` | Outcome not determined |

### EntityType

| Value | Description |
|-------|-------------|
| `person` | Human individual |
| `system` | Software system |
| `service` | Microservice or API |
| `team` | Team or group |
| `document` | Document or specification |
| `concept` | Abstract concept |
| `domain` | Business domain |
| `file` | File or path |
| `project` | Project |
| `tool` | Tool or utility |

### EvidenceType

| Value | Description |
|-------|-------------|
| `document` | Full document |
| `snippet` | Text excerpt |
| `link` | URL reference |
| `config` | Configuration data |
| `image` | Image file |
| `file_pointer` | File path reference |

### PolicyType

| Value | Description |
|-------|-------------|
| `mutation` | Controls write operations |
| `access` | Controls read access |
| `retention` | Controls data lifecycle |
| `redaction` | Controls content redaction |

### Enforcement

| Value | Description |
|-------|-------------|
| `enforce` | Block violations |
| `warn` | Allow but emit warning |
| `audit_only` | Log only, no enforcement |

### EdgeKind

| Value | Description |
|-------|-------------|
| `trace_used_evidence` | Trace consumed this evidence |
| `trace_produced_artifact` | Trace created this artifact |
| `trace_touched_entity` | Trace interacted with this entity |
| `trace_promoted_to_precedent` | Trace was promoted to this precedent |
| `entity_related_to` | General entity relationship |
| `entity_part_of` | Entity is a component of another |
| `entity_depends_on` | Entity depends on another |
| `evidence_attached_to` | Evidence is attached to a target |
| `evidence_supports` | Evidence supports a claim |
| `precedent_applies_to` | Precedent applies to a domain or entity |
| `precedent_derived_from` | Precedent was derived from a source |

### Operation

| Value | Category | Description |
|-------|----------|-------------|
| `trace.ingest` | Ingest | Ingest a full trace |
| `trace.append_step` | Ingest | Append a step to a trace |
| `trace.record_outcome` | Ingest | Record a trace outcome |
| `evidence.ingest` | Ingest | Ingest evidence |
| `evidence.attach` | Ingest | Attach evidence to a target |
| `precedent.promote` | Curate | Promote trace to precedent |
| `precedent.update` | Curate | Update a precedent |
| `entity.create` | Curate | Create an entity |
| `entity.update` | Curate | Update an entity |
| `entity.merge` | Curate | Merge two entities |
| `link.create` | Curate | Create a graph edge |
| `link.remove` | Curate | Remove a graph edge |
| `label.add` | Curate | Add a label |
| `label.remove` | Curate | Remove a label |
| `feedback.record` | Curate | Record feedback |
| `redaction.apply` | Maintain | Redact content |
| `retention.prune` | Maintain | Run retention pruning |
| `pack.publish` | Maintain | Publish a context pack |
| `pack.invalidate` | Maintain | Invalidate a pack |

### CommandStatus

| Value | Description |
|-------|-------------|
| `success` | Command executed successfully |
| `rejected` | Policy gate rejected the command |
| `failed` | Execution failed (validation or handler error) |
| `duplicate` | Idempotency key already seen |

### BatchStrategy

| Value | Description |
|-------|-------------|
| `sequential` | Execute all commands in order |
| `stop_on_error` | Stop on first failure or rejection |
| `continue_on_error` | Execute all, collect all results |
