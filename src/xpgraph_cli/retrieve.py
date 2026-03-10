"""Retrieve commands — search and fetch from the experience graph."""

from __future__ import annotations

import json

import typer
from rich.console import Console

retrieve_app = typer.Typer(no_args_is_help=True)
console = Console()


@retrieve_app.command()
def pack(
    intent: str = typer.Option(..., help="Intent for pack assembly"),
    domain: str = typer.Option(None, help="Domain scope"),
    agent: str = typer.Option(None, "--agent", help="Agent ID scope"),
    max_items: int = typer.Option(50, help="Maximum items in pack"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Assemble a retrieval pack for a given intent."""
    request: dict[str, object] = {
        "intent": intent,
        "domain": domain,
        "agent_id": agent,
        "max_items": max_items,
    }
    if output_format == "json":
        console.print(json.dumps({"status": "request", **request}))
    else:
        console.print("[cyan]Pack request[/cyan]:")
        console.print(f"  Intent: {intent}")
        if domain:
            console.print(f"  Domain: {domain}")
        if agent:
            console.print(f"  Agent: {agent}")
        console.print(f"  Max items: {max_items}")
        console.print(
            "[yellow]Note: Pack assembly requires initialized stores"
            " (xpg admin init)[/yellow]"
        )


@retrieve_app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(20, help="Maximum results"),
    domain: str = typer.Option(None, help="Domain scope"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Search the experience graph."""
    request: dict[str, object] = {"query": query, "limit": limit, "domain": domain}
    if output_format == "json":
        console.print(json.dumps({"status": "request", **request}))
    else:
        console.print(f"[cyan]Search[/cyan]: {query}")
        if domain:
            console.print(f"  Domain: {domain}")
        console.print(f"  Limit: {limit}")
        console.print(
            "[yellow]Note: Search requires initialized stores"
            " (xpg admin init)[/yellow]"
        )


@retrieve_app.command()
def trace(
    trace_id: str = typer.Argument(..., help="Trace ID to retrieve"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Retrieve a specific trace by ID."""
    if output_format == "json":
        console.print(json.dumps({"status": "request", "trace_id": trace_id}))
    else:
        console.print(f"[cyan]Retrieve trace[/cyan]: {trace_id}")
        console.print(
            "[yellow]Note: Requires initialized stores (xpg admin init)[/yellow]"
        )


@retrieve_app.command()
def entity(
    entity_id: str = typer.Argument(..., help="Entity ID to retrieve"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Retrieve a specific entity by ID."""
    if output_format == "json":
        console.print(json.dumps({"status": "request", "entity_id": entity_id}))
    else:
        console.print(f"[cyan]Retrieve entity[/cyan]: {entity_id}")
        console.print(
            "[yellow]Note: Requires initialized stores (xpg admin init)[/yellow]"
        )


@retrieve_app.command()
def precedents(
    domain: str = typer.Option(None, help="Domain scope"),
    limit: int = typer.Option(20, help="Maximum results"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """List precedents, optionally scoped by domain."""
    request: dict[str, object] = {"domain": domain, "limit": limit}
    if output_format == "json":
        console.print(json.dumps({"status": "request", **request}))
    else:
        console.print("[cyan]List precedents[/cyan]")
        if domain:
            console.print(f"  Domain: {domain}")
        console.print(f"  Limit: {limit}")
        console.print(
            "[yellow]Note: Requires initialized stores (xpg admin init)[/yellow]"
        )
