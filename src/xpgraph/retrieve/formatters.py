"""Response formatters for token-efficient output."""

from __future__ import annotations

from typing import Any


def _estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars per token)."""
    return len(text) // 4 + 1


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token budget."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def format_pack_as_markdown(
    items: list[dict[str, Any]],
    intent: str,
    max_tokens: int = 2000,
) -> str:
    """Format pack items as concise markdown for LLM consumption.

    Args:
        items: List of pack item dicts with item_id, item_type, excerpt,
            relevance_score, metadata.
        intent: The original query intent.
        max_tokens: Maximum token budget for the response.

    Returns:
        Markdown-formatted string within token budget.
    """
    lines = [f"# Context for: {intent}", ""]
    token_budget = max_tokens - _estimate_tokens(lines[0]) - 10  # reserve overhead
    used = 0
    included = 0

    for item in items:
        item_type = item.get("item_type", "item")
        excerpt = item.get("excerpt", "")
        score = item.get("relevance_score", 0.0)
        item_id = item.get("item_id", "")

        # Build item block
        header = f"## [{item_type}] {item_id[:16]}"
        if score > 0:
            header += f" (relevance: {score:.2f})"

        block = f"{header}\n{excerpt}\n"
        block_tokens = _estimate_tokens(block)

        if used + block_tokens > token_budget:
            remaining = len(items) - included
            if remaining > 0:
                lines.append(
                    f"\n*[{remaining} more items omitted"
                    " — use CLI for full results]*"
                )
            break

        lines.append(block)
        used += block_tokens
        included += 1

    if included == 0 and items:
        # At least include a truncated first item
        first = items[0]
        excerpt = _truncate_to_tokens(first.get("excerpt", ""), token_budget - 50)
        lines.append(
            f"## [{first.get('item_type', 'item')}]"
            f" {first.get('item_id', '')[:16]}"
        )
        lines.append(excerpt)
        remaining = len(items) - 1
        if remaining > 0:
            lines.append(f"\n*[{remaining} more items omitted]*")

    return "\n".join(lines)


def format_traces_as_markdown(
    traces: list[dict[str, Any]],
    max_tokens: int = 2000,
) -> str:
    """Format trace summaries as markdown.

    Args:
        traces: List of trace summary dicts.
        max_tokens: Maximum token budget.

    Returns:
        Markdown-formatted string.
    """
    if not traces:
        return "No traces found."

    lines = [f"# Recent Traces ({len(traces)})", ""]
    used = _estimate_tokens(lines[0])
    included = 0

    for t in traces:
        outcome = t.get("outcome", "unknown")
        domain = t.get("domain", "")
        intent = t.get("intent", "")[:120]
        created = t.get("created_at", "")[:10]

        line = f"- **{outcome}** | {domain or 'general'} | {intent} ({created})"
        line_tokens = _estimate_tokens(line)

        if used + line_tokens > max_tokens:
            remaining = len(traces) - included
            lines.append(f"\n*[{remaining} more traces omitted]*")
            break

        lines.append(line)
        used += line_tokens
        included += 1

    return "\n".join(lines)


def format_entities_as_markdown(
    entities: list[dict[str, Any]],
    max_tokens: int = 2000,
) -> str:
    """Format entities as markdown.

    Args:
        entities: List of entity/node dicts.
        max_tokens: Maximum token budget.

    Returns:
        Markdown-formatted string.
    """
    if not entities:
        return "No entities found."

    lines = [f"# Entities ({len(entities)})", ""]
    used = _estimate_tokens(lines[0])
    included = 0

    for e in entities:
        props = e.get("properties", {})
        name = props.get("name", e.get("node_id", "unknown"))
        node_type = e.get("node_type", "unknown")
        desc = props.get("description", "")[:200]

        line = f"- **{name}** ({node_type})"
        if desc:
            line += f": {desc}"

        line_tokens = _estimate_tokens(line)
        if used + line_tokens > max_tokens:
            remaining = len(entities) - included
            lines.append(f"\n*[{remaining} more entities omitted]*")
            break

        lines.append(line)
        used += line_tokens
        included += 1

    return "\n".join(lines)


def format_lessons_as_markdown(
    lessons: list[dict[str, Any]],
    max_tokens: int = 2000,
) -> str:
    """Format precedent/lessons as markdown.

    Args:
        lessons: List of lesson/precedent dicts.
        max_tokens: Maximum token budget.

    Returns:
        Markdown-formatted string.
    """
    if not lessons:
        return "No lessons found."

    lines = [f"# Lessons Learned ({len(lessons)})", ""]
    used = _estimate_tokens(lines[0])
    included = 0

    for lesson in lessons:
        title = lesson.get("title", "Untitled")
        desc = lesson.get("description", "")[:300]
        domain = lesson.get("domain", "")

        block = f"## {title}"
        if domain:
            block += f" [{domain}]"
        block += f"\n{desc}\n"

        block_tokens = _estimate_tokens(block)
        if used + block_tokens > max_tokens:
            remaining = len(lessons) - included
            lines.append(f"\n*[{remaining} more lessons omitted]*")
            break

        lines.append(block)
        used += block_tokens
        included += 1

    return "\n".join(lines)


def format_subgraph_as_markdown(
    entity: dict[str, Any],
    subgraph: dict[str, Any],
    max_tokens: int = 2000,
) -> str:
    """Format an entity and its subgraph neighborhood as markdown.

    Args:
        entity: The root entity dict.
        subgraph: Dict with "nodes" and "edges" lists.
        max_tokens: Maximum token budget.

    Returns:
        Markdown-formatted string.
    """
    props = entity.get("properties", {})
    name = props.get("name", entity.get("node_id", "unknown"))
    node_type = entity.get("node_type", "unknown")

    lines = [f"# {name} ({node_type})", ""]

    # Add entity properties
    for k, v in props.items():
        if k != "name":
            lines.append(f"- **{k}**: {str(v)[:200]}")

    nodes = subgraph.get("nodes", [])
    edges = subgraph.get("edges", [])

    if edges:
        lines.append("")
        lines.append(f"## Relationships ({len(edges)})")
        for edge in edges[:20]:  # cap at 20 edges
            source = edge.get("source_id", "?")[:12]
            target = edge.get("target_id", "?")[:12]
            etype = edge.get("edge_type", "related")
            lines.append(f"- {source}... --[{etype}]--> {target}...")

    if len(nodes) > 1:
        lines.append("")
        lines.append(f"## Neighbors ({len(nodes) - 1})")
        for node in nodes[:15]:
            if node.get("node_id") == entity.get("node_id"):
                continue
            nprops = node.get("properties", {})
            nname = nprops.get("name", node.get("node_id", "?")[:12])
            ntype = node.get("node_type", "?")
            lines.append(f"- **{nname}** ({ntype})")

    result = "\n".join(lines)
    return _truncate_to_tokens(result, max_tokens)
