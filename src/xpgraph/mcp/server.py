"""MCP Macro Tools server — high-level, token-efficient tools for AI agents."""

from __future__ import annotations

from typing import Any

import structlog
from fastmcp import FastMCP

from xpgraph.retrieve.formatters import (
    format_lessons_as_markdown,
    format_pack_as_markdown,
    format_subgraph_as_markdown,
)
from xpgraph.retrieve.token_tracker import estimate_tokens, track_token_usage
from xpgraph.schemas.trace import Trace
from xpgraph.stores.base.event_log import EventType
from xpgraph.stores.registry import StoreRegistry

logger = structlog.get_logger(__name__)

mcp = FastMCP(
    "xpgraph",
    instructions=(
        "Experience Graph — structured memory and learning for AI agents. "
        "All responses are concise markdown optimized for LLM context windows."
    ),
)


def _get_registry() -> StoreRegistry:
    """Get or create a StoreRegistry."""
    return StoreRegistry.from_config_dir()


# ---------------------------------------------------------------------------
# Macro Tool 1: get_context
# ---------------------------------------------------------------------------


@mcp.tool()
def get_context(
    intent: str,
    domain: str | None = None,
    max_tokens: int = 2000,
) -> str:
    """Get relevant context from the experience graph for a task or question.

    Searches documents, knowledge graph, and past traces, then returns
    a summarized markdown pack optimized for your context window.

    Args:
        intent: What you're trying to do or learn about.
        domain: Optional domain scope (e.g., "platform", "data").
        max_tokens: Maximum response size in tokens (default 2000).
    """
    if not intent or not intent.strip():
        return "Error: intent must not be empty"

    registry = _get_registry()
    items: list[dict[str, Any]] = []

    # Search documents
    try:
        filters: dict[str, Any] = {}
        if domain:
            filters["domain"] = domain
        doc_results = registry.document_store.search(
            intent, limit=10, filters=filters
        )
        items.extend(
            {
                "item_id": doc["doc_id"],
                "item_type": "document",
                "excerpt": doc.get("content", "")[:500],
                "relevance_score": abs(doc.get("rank", 0.0)),
            }
            for doc in doc_results
        )
    except Exception:
        logger.exception("get_context_doc_search_failed")

    # Search graph
    try:
        nodes = registry.graph_store.query(limit=20)
        q_lower = intent.lower()
        for node in nodes:
            props = node.get("properties", {})
            name = str(props.get("name", "")).lower()
            desc = str(props.get("description", "")).lower()
            if q_lower in name or q_lower in desc:
                items.append(
                    {
                        "item_id": node["node_id"],
                        "item_type": "entity",
                        "excerpt": props.get("name", "")
                        or props.get("description", ""),
                        "relevance_score": 0.5,
                    }
                )
    except Exception:
        logger.exception("get_context_graph_search_failed")

    # Recent traces
    try:
        traces = registry.trace_store.query(domain=domain, limit=5)
        items.extend(
            {
                "item_id": t.trace_id,
                "item_type": "trace",
                "excerpt": t.intent[:300],
                "relevance_score": 0.3,
            }
            for t in traces
        )
    except Exception:
        logger.exception("get_context_trace_search_failed")

    # Deduplicate and sort
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        if item["item_id"] not in seen:
            seen.add(item["item_id"])
            unique.append(item)
    unique.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

    if not unique:
        return f"No context found for: {intent}"

    result = format_pack_as_markdown(unique, intent, max_tokens=max_tokens)
    try:
        track_token_usage(
            registry.event_log,
            layer="mcp",
            operation="get_context",
            response_tokens=estimate_tokens(result),
            budget_tokens=max_tokens,
        )
    except Exception:
        logger.debug("token_tracking_failed", operation="get_context")
    return result


# ---------------------------------------------------------------------------
# Macro Tool 2: save_experience
# ---------------------------------------------------------------------------


@mcp.tool()
def save_experience(trace_json: str) -> str:
    """Save an experience trace to the graph.

    Args:
        trace_json: JSON string conforming to the Trace schema.
    """
    if not trace_json or not trace_json.strip():
        return "Error: trace_json must not be empty"

    try:
        trace = Trace.model_validate_json(trace_json)
    except Exception as exc:
        return f"Error: Invalid trace JSON — {exc}"

    try:
        registry = _get_registry()
        trace_id = registry.trace_store.append(trace)
    except Exception as exc:
        return f"Error: Failed to store trace — {exc}"

    return f"Trace saved: {trace_id}"


# ---------------------------------------------------------------------------
# Macro Tool 3: save_knowledge
# ---------------------------------------------------------------------------


@mcp.tool()
def save_knowledge(
    name: str,
    entity_type: str = "concept",
    properties: dict[str, Any] | None = None,
    relates_to: str | None = None,
    edge_kind: str = "entity_related_to",
) -> str:
    """Create an entity in the knowledge graph, optionally linking it.

    Args:
        name: Entity name.
        entity_type: Type (e.g., "concept", "person", "system").
            Default: "concept".
        properties: Optional additional properties.
        relates_to: Optional entity ID to create a relationship to.
        edge_kind: Relationship type if relates_to is set.
            Default: "entity_related_to".
    """
    if not name or not name.strip():
        return "Error: name must not be empty"

    props = dict(properties or {})
    props["name"] = name

    registry = _get_registry()
    node_id = registry.graph_store.upsert_node(
        node_id=None,
        node_type=entity_type,
        properties=props,
    )

    result = f"Entity created: {node_id} ({entity_type}: {name})"

    if relates_to:
        if registry.graph_store.get_node(relates_to) is None:
            result += (
                f"\nWarning: target entity not found:"
                f" {relates_to} — edge not created"
            )
        else:
            edge_id = registry.graph_store.upsert_edge(
                source_id=node_id,
                target_id=relates_to,
                edge_type=edge_kind,
            )
            result += f"\nEdge created: {edge_id} --[{edge_kind}]--> {relates_to}"

    return result


# ---------------------------------------------------------------------------
# Macro Tool 4: save_memory
# ---------------------------------------------------------------------------


@mcp.tool()
def save_memory(
    content: str,
    metadata: dict[str, Any] | None = None,
    doc_id: str | None = None,
) -> str:
    """Store a document in the experience graph memory.

    Args:
        content: Document content to store.
        metadata: Optional metadata (tags, source, domain, etc.).
        doc_id: Optional document ID. Auto-generated if not provided.
    """
    if not content or not content.strip():
        return "Error: content must not be empty"

    registry = _get_registry()
    stored_id = registry.document_store.put(
        doc_id, content, metadata=metadata or {}
    )
    return f"Memory saved: {stored_id}"


# ---------------------------------------------------------------------------
# Macro Tool 5: get_lessons
# ---------------------------------------------------------------------------


@mcp.tool()
def get_lessons(
    domain: str | None = None,
    limit: int = 10,
    max_tokens: int = 2000,
) -> str:
    """Get lessons learned (promoted precedents) from past experiences.

    Args:
        domain: Optional domain filter.
        limit: Maximum lessons to return (default 10).
        max_tokens: Maximum response size in tokens (default 2000).
    """
    registry = _get_registry()
    events = registry.event_log.get_events(
        event_type=EventType.PRECEDENT_PROMOTED,
        limit=limit,
    )

    if domain:
        events = [e for e in events if e.payload.get("domain") == domain]

    lessons = [
        {
            "title": e.payload.get("title", "Untitled"),
            "description": e.payload.get("description", ""),
            "domain": e.payload.get("domain"),
            "occurred_at": e.occurred_at.isoformat(),
        }
        for e in events
    ]

    result = format_lessons_as_markdown(lessons, max_tokens=max_tokens)
    try:
        track_token_usage(
            registry.event_log,
            layer="mcp",
            operation="get_lessons",
            response_tokens=estimate_tokens(result),
            budget_tokens=max_tokens,
        )
    except Exception:
        logger.debug("token_tracking_failed", operation="get_lessons")
    return result


# ---------------------------------------------------------------------------
# Macro Tool 6: get_graph
# ---------------------------------------------------------------------------


@mcp.tool()
def get_graph(
    entity_id: str,
    depth: int = 1,
    max_tokens: int = 2000,
) -> str:
    """Get an entity and its neighborhood from the knowledge graph.

    Args:
        entity_id: The entity ID to explore.
        depth: How many relationship hops to traverse (default 1).
        max_tokens: Maximum response size in tokens (default 2000).
    """
    if not entity_id or not entity_id.strip():
        return "Error: entity_id must not be empty"

    registry = _get_registry()
    node = registry.graph_store.get_node(entity_id)
    if node is None:
        return f"Entity not found: {entity_id}"

    subgraph = registry.graph_store.get_subgraph(
        seed_ids=[entity_id], depth=depth
    )
    result = format_subgraph_as_markdown(node, subgraph, max_tokens=max_tokens)
    try:
        track_token_usage(
            registry.event_log,
            layer="mcp",
            operation="get_graph",
            response_tokens=estimate_tokens(result),
            budget_tokens=max_tokens,
        )
    except Exception:
        logger.debug("token_tracking_failed", operation="get_graph")
    return result


# ---------------------------------------------------------------------------
# Macro Tool 7: record_feedback
# ---------------------------------------------------------------------------


@mcp.tool()
def record_feedback(
    trace_id: str,
    success: bool,
    notes: str | None = None,
) -> str:
    """Record whether a task succeeded, to improve future context quality.

    Args:
        trace_id: The trace ID to give feedback on.
        success: Whether the task succeeded.
        notes: Optional notes about what worked or didn't.
    """
    if not trace_id or not trace_id.strip():
        return "Error: trace_id must not be empty"

    registry = _get_registry()
    registry.event_log.emit(
        EventType.FEEDBACK_RECORDED,
        "mcp",
        entity_id=trace_id,
        entity_type="trace",
        payload={
            "success": success,
            "notes": notes or "",
            "rating": 1.0 if success else 0.0,
        },
    )

    status = "positive" if success else "negative"
    return f"Feedback recorded ({status}) for trace: {trace_id}"


# ---------------------------------------------------------------------------
# Macro Tool 8: search
# ---------------------------------------------------------------------------


@mcp.tool()
def search(
    query: str,
    limit: int = 10,
    max_tokens: int = 2000,
) -> str:
    """Search the experience graph for documents and entities.

    Args:
        query: Search query.
        limit: Maximum results (default 10).
        max_tokens: Maximum response size in tokens (default 2000).
    """
    if not query or not query.strip():
        return "Error: query must not be empty"

    registry = _get_registry()

    # Search documents
    doc_results = registry.document_store.search(query, limit=limit)
    items: list[dict[str, Any]] = [
        {
            "item_id": doc["doc_id"],
            "item_type": "document",
            "excerpt": doc.get("content", "")[:300],
            "relevance_score": abs(doc.get("rank", 0.0)),
        }
        for doc in doc_results
    ]

    # Search graph nodes
    all_nodes = registry.graph_store.query(limit=limit * 2)
    q_lower = query.lower()
    for node in all_nodes:
        props = node.get("properties", {})
        name = str(props.get("name", "")).lower()
        desc = str(props.get("description", "")).lower()
        if q_lower in name or q_lower in desc:
            items.append(
                {
                    "item_id": node["node_id"],
                    "item_type": "entity",
                    "excerpt": props.get("name", "")
                    or props.get("description", ""),
                    "relevance_score": 0.5,
                }
            )

    if not items:
        return f"No results found for: {query}"

    items.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
    result = format_pack_as_markdown(
        items[:limit], f"Search: {query}", max_tokens=max_tokens
    )
    try:
        track_token_usage(
            registry.event_log,
            layer="mcp",
            operation="search",
            response_tokens=estimate_tokens(result),
            budget_tokens=max_tokens,
        )
    except Exception:
        logger.debug("token_tracking_failed", operation="search")
    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Macro Tools MCP server."""
    mcp.run()
