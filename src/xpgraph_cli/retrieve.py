"""Retrieve commands — search and fetch from the experience graph."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from xpgraph.stores.event_log import EventType
from xpgraph_cli.stores import (
    get_document_store,
    get_event_log,
    get_graph_store,
    get_trace_store,
)

retrieve_app = typer.Typer(no_args_is_help=True)
console = Console()


@retrieve_app.command()
def pack(
    intent: str = typer.Option(..., help="Intent for pack assembly"),
    domain: str = typer.Option(None, help="Domain scope"),
    agent: str = typer.Option(None, "--agent", help="Agent ID scope"),
    max_items: int = typer.Option(50, help="Maximum items in pack"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress Rich formatting"),
) -> None:
    """Assemble a retrieval pack for a given intent."""
    import sys

    store = get_document_store()
    try:
        filters = {}
        if domain:
            filters["domain"] = domain
        results = store.search(query=intent, limit=max_items, filters=filters)
    finally:
        store.close()

    if output_format == "json":
        payload = json.dumps({
            "status": "ok",
            "intent": intent,
            "domain": domain,
            "agent_id": agent,
            "count": len(results),
            "items": [r["doc_id"] for r in results],
        })
        if quiet:
            sys.stdout.write(payload + "\n")
        else:
            console.print(payload)
    else:
        if quiet:
            for r in results:
                sys.stdout.write(r["doc_id"] + "\n")
        else:
            console.print(f"[green]Pack assembled[/green] ({len(results)} items)")
            console.print(f"  Intent: {intent}")
            if domain:
                console.print(f"  Domain: {domain}")
            if agent:
                console.print(f"  Agent: {agent}")
            for r in results:
                console.print(f"  - {r['doc_id']}")


@retrieve_app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, help="Maximum results"),
    domain: str = typer.Option(None, help="Domain scope"),
    output_format: str = typer.Option("text", "--format", help="Output format: text, json, jsonl, tsv"),
    fields: str = typer.Option(None, "--fields", help="Comma-separated fields to include"),
    truncate: int = typer.Option(None, "--truncate", help="Max characters for text fields"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress Rich formatting"),
) -> None:
    """Search the experience graph."""
    import sys

    from xpgraph_cli.output import format_output

    store = get_document_store()
    try:
        filters = {}
        if domain:
            filters["domain"] = domain
        results = store.search(query=query, limit=limit, filters=filters)
    finally:
        store.close()

    if output_format in ("json", "jsonl", "tsv"):
        if output_format == "json" and not fields:
            # Preserve backward-compatible JSON structure
            from xpgraph_cli.output import truncate_values

            out_items = truncate_values(results, truncate)
            payload = json.dumps({
                "status": "ok",
                "query": query,
                "count": len(out_items),
                "results": out_items,
            })
        else:
            payload = format_output(
                results,
                output_format,
                fields=fields,
                truncate=truncate,
                wrapper={"status": "ok", "query": query} if output_format == "json" else None,
            )
        if quiet:
            sys.stdout.write(payload + "\n")
        else:
            console.print(payload)
    else:
        trunc = truncate or 80
        if not quiet:
            console.print(f"[green]Search results[/green] ({len(results)} found)")
        for r in results:
            snippet = r.get("snippet", "")[:trunc]
            if quiet:
                sys.stdout.write(f"{r['doc_id']}: {snippet}\n")
            else:
                console.print(f"  - {r['doc_id']}: {snippet}")


@retrieve_app.command()
def trace(
    trace_id: str = typer.Argument(..., help="Trace ID to retrieve"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Retrieve a specific trace by ID."""
    store = get_trace_store()
    try:
        result = store.get(trace_id)
    finally:
        store.close()

    if result is None:
        if output_format == "json":
            console.print(
                json.dumps({"status": "not_found", "trace_id": trace_id})
            )
        else:
            console.print(f"[yellow]Trace not found[/yellow]: {trace_id}")
        raise typer.Exit(code=1)

    if output_format == "json":
        console.print(result.model_dump_json())
    else:
        console.print(f"[green]Trace[/green]: {result.trace_id}")
        console.print(f"  Source: {result.source}")
        console.print(f"  Intent: {result.intent}")
        if result.outcome:
            console.print(f"  Outcome: {result.outcome.status}")


@retrieve_app.command()
def entity(
    entity_id: str = typer.Argument(..., help="Entity ID to retrieve"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Retrieve a specific entity by ID."""
    store = get_graph_store()
    try:
        result = store.get_node(entity_id)
    finally:
        store.close()

    if result is None:
        if output_format == "json":
            console.print(
                json.dumps({"status": "not_found", "entity_id": entity_id})
            )
        else:
            console.print(f"[yellow]Entity not found[/yellow]: {entity_id}")
        raise typer.Exit(code=1)

    if output_format == "json":
        console.print(json.dumps(result))
    else:
        console.print(f"[green]Entity[/green]: {entity_id}")
        console.print(f"  Type: {result.get('node_type', 'unknown')}")
        props = result.get("properties", {})
        for k, v in props.items():
            console.print(f"  {k}: {v}")


@retrieve_app.command()
def traces(
    limit: int = typer.Option(20, help="Maximum traces to return"),
    domain: str = typer.Option(None, help="Domain scope"),
    agent: str = typer.Option(None, "--agent", help="Agent ID filter"),
    output_format: str = typer.Option("text", "--format", help="Output format: text, json, jsonl, tsv"),
    fields: str = typer.Option(None, "--fields", help="Comma-separated fields to include"),
    truncate: int = typer.Option(None, "--truncate", help="Max characters for text fields"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress Rich formatting"),
) -> None:
    """List recent traces."""
    import sys

    from xpgraph_cli.output import format_output

    store = get_trace_store()
    try:
        results = store.query(domain=domain, agent_id=agent, limit=limit)
        total = store.count(domain=domain)
    finally:
        store.close()

    items = [
        {
            "trace_id": t.trace_id,
            "source": t.source.value,
            "intent": t.intent,
            "outcome": (
                t.outcome.status.value if t.outcome else None
            ),
            "domain": (
                t.context.domain if t.context else None
            ),
            "agent_id": (
                t.context.agent_id if t.context else None
            ),
            "created_at": t.created_at.isoformat(),
        }
        for t in results
    ]

    if output_format in ("json", "jsonl", "tsv"):
        if output_format == "json" and not fields:
            # Preserve backward-compatible JSON structure
            from xpgraph_cli.output import truncate_values

            out_items = truncate_values(items, truncate)
            payload = json.dumps({
                "status": "ok",
                "total": total,
                "count": len(out_items),
                "traces": out_items,
            })
        else:
            payload = format_output(
                items,
                output_format,
                fields=fields,
                truncate=truncate,
                wrapper={"status": "ok", "total": total} if output_format == "json" else None,
            )
        if quiet:
            sys.stdout.write(payload + "\n")
        else:
            console.print(payload)
    else:
        trunc = truncate or 60
        if not quiet:
            console.print(f"[green]Traces[/green] ({len(results)} of {total})")
        for t in results:
            outcome = t.outcome.status.value if t.outcome else "unknown"
            intent = t.intent[:trunc]
            line = (
                f"  - {t.trace_id[:12]}... [{t.source.value}] {intent}"
                f" ({outcome})"
            )
            if quiet:
                sys.stdout.write(line.strip() + "\n")
            else:
                console.print(line)


@retrieve_app.command()
def precedents(
    domain: str = typer.Option(None, help="Domain scope"),
    limit: int = typer.Option(20, help="Maximum results"),
    output_format: str = typer.Option("text", "--format", help="Output format: text, json, jsonl, tsv"),
    fields: str = typer.Option(None, "--fields", help="Comma-separated fields to include"),
    truncate: int = typer.Option(None, "--truncate", help="Max characters for text fields"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress Rich formatting"),
) -> None:
    """List precedents, optionally scoped by domain."""
    import sys

    from xpgraph_cli.output import format_output

    event_log = get_event_log()
    try:
        events = event_log.get_events(
            event_type=EventType.PRECEDENT_PROMOTED,
            limit=limit,
        )
    finally:
        event_log.close()

    # Filter by domain if specified
    if domain:
        events = [
            e for e in events
            if e.payload.get("domain") == domain
        ]

    items = [
        {
            "event_id": e.event_id,
            "entity_id": e.entity_id,
            "payload": e.payload,
        }
        for e in events
    ]

    if output_format in ("json", "jsonl", "tsv"):
        output = format_output(
            items,
            output_format,
            fields=fields,
            truncate=truncate,
            wrapper={"status": "ok"} if output_format == "json" else None,
        )
        if quiet:
            sys.stdout.write(output + "\n")
        else:
            console.print(output)
    else:
        if not quiet:
            console.print(f"[green]Precedents[/green] ({len(events)} found)")
        for e in events:
            title = e.payload.get("title", e.entity_id or "unknown")
            line = f"  - {title} ({e.entity_id})"
            if quiet:
                sys.stdout.write(line.strip() + "\n")
            else:
                console.print(line)
