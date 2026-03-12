"""Pre-built skill functions for orchestrators.

Each function returns a concise markdown string suitable for injecting
directly into an LLM's context window.
"""

from __future__ import annotations

from typing import Any

from xpgraph.retrieve.formatters import (
    format_pack_as_markdown,
    format_traces_as_markdown,
)
from xpgraph_sdk.client import XPGClient


def get_context_for_task(
    client: XPGClient,
    intent: str,
    *,
    domain: str | None = None,
    max_tokens: int = 1500,
) -> str:
    """Get relevant context for a task as a markdown summary.

    Args:
        client: XPGClient instance.
        intent: What you're trying to do.
        domain: Optional domain scope.
        max_tokens: Token budget for the response.

    Returns:
        Markdown string summarizing relevant context.
    """
    pack = client.assemble_pack(intent, domain=domain, max_items=20)
    items = pack.get("items", [])
    if not items:
        return f"No relevant context found for: {intent}"
    return format_pack_as_markdown(items, intent, max_tokens=max_tokens)


def get_latest_successful_trace(
    client: XPGClient,
    task_type: str,
    *,
    domain: str | None = None,
) -> str:
    """Get the most recent successful trace matching a task type.

    Args:
        client: XPGClient instance.
        task_type: Keyword to search for in trace intents.
        domain: Optional domain filter.

    Returns:
        Markdown summary of the trace, or a "not found" message.
    """
    traces = client.list_traces(domain=domain, limit=20)

    # Filter for matching and successful traces
    matching = [
        t
        for t in traces
        if task_type.lower() in t.get("intent", "").lower()
        and t.get("outcome") == "success"
    ]

    if not matching:
        return f"No successful traces found for: {task_type}"

    trace = matching[0]
    full = client.get_trace(trace["trace_id"])
    if full is None:
        return f"Trace {trace['trace_id']} not found"

    intent = full.get("intent", "")
    outcome = full.get("outcome", {})
    summary = outcome.get("summary", "") if isinstance(outcome, dict) else ""
    steps = full.get("steps", [])

    lines = [
        f"# Successful Trace: {intent[:100]}",
        f"**ID:** {trace['trace_id']}",
        f"**Domain:** {trace.get('domain', 'general')}",
        f"**Created:** {trace.get('created_at', '')[:10]}",
    ]
    if summary:
        lines.append(f"**Summary:** {summary[:300]}")
    if steps:
        lines.append(f"**Steps:** {len(steps)}")
        for step in steps[:5]:
            name = step.get("name", "unnamed")
            lines.append(f"  - {name}")
        if len(steps) > 5:
            lines.append(f"  - ... and {len(steps) - 5} more")

    return "\n".join(lines)


def save_trace_and_extract_lessons(
    client: XPGClient,
    trace: dict[str, Any],
) -> str:
    """Ingest a trace and return a summary.

    Args:
        client: XPGClient instance.
        trace: Trace dict to ingest.

    Returns:
        Markdown summary confirming ingestion.
    """
    trace_id = client.ingest_trace(trace)
    intent = trace.get("intent", "unknown")
    outcome = trace.get("outcome", {})
    status = (
        outcome.get("status", "unknown") if isinstance(outcome, dict) else "unknown"
    )

    return (
        f"Trace ingested: **{trace_id}**\n"
        f"- Intent: {intent}\n"
        f"- Outcome: {status}\n"
    )


def get_recent_activity(
    client: XPGClient,
    *,
    domain: str | None = None,
    limit: int = 10,
    max_tokens: int = 1500,
) -> str:
    """Get a summary of recent activity.

    Args:
        client: XPGClient instance.
        domain: Optional domain filter.
        limit: Max traces to include.
        max_tokens: Token budget.

    Returns:
        Markdown summary of recent traces.
    """
    traces = client.list_traces(domain=domain, limit=limit)
    if not traces:
        return "No recent activity found."
    return format_traces_as_markdown(traces, max_tokens=max_tokens)
