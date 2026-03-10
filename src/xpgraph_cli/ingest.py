"""Ingest commands -- import traces and evidence into the experience graph."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from xpgraph.schemas.evidence import Evidence
from xpgraph.schemas.trace import Trace

ingest_app = typer.Typer(no_args_is_help=True)
console = Console()


@ingest_app.command("trace")
def ingest_trace(
    file: str = typer.Argument(None, help="Path to trace JSON file, or '-' for stdin"),
    output_format: str = typer.Option(
        "text", "--format", help="Output format: text or json"
    ),
) -> None:
    """Ingest a trace from a JSON file or stdin."""
    # Read input
    if file == "-" or file is None:
        raw = sys.stdin.read()
    else:
        path = Path(file)
        if not path.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(code=1)
        raw = path.read_text()

    # Parse and validate
    try:
        data = json.loads(raw)
        trace = Trace.model_validate(data)
    except Exception as exc:
        if output_format == "json":
            console.print(json.dumps({"status": "error", "message": str(exc)}))
        else:
            console.print(f"[red]Invalid trace: {exc}[/red]")
        raise typer.Exit(code=1) from None

    # Output result (store write deferred to when stores are wired up)
    if output_format == "json":
        console.print(
            json.dumps({
                "status": "accepted",
                "trace_id": trace.trace_id,
                "source": trace.source,
                "intent": trace.intent,
            })
        )
    else:
        console.print(f"[green]Trace accepted[/green]: {trace.trace_id}")
        console.print(f"  Source: {trace.source}")
        console.print(f"  Intent: {trace.intent}")


@ingest_app.command("evidence")
def ingest_evidence(
    file: str = typer.Argument(..., help="Path to evidence JSON file"),
    output_format: str = typer.Option(
        "text", "--format", help="Output format: text or json"
    ),
) -> None:
    """Ingest evidence from a JSON file."""
    path = Path(file)
    if not path.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(code=1)

    try:
        data = json.loads(path.read_text())
        evidence = Evidence.model_validate(data)
    except Exception as exc:
        if output_format == "json":
            console.print(json.dumps({"status": "error", "message": str(exc)}))
        else:
            console.print(f"[red]Invalid evidence: {exc}[/red]")
        raise typer.Exit(code=1) from None

    if output_format == "json":
        console.print(
            json.dumps({
                "status": "accepted",
                "evidence_id": evidence.evidence_id,
                "evidence_type": evidence.evidence_type,
            })
        )
    else:
        console.print(f"[green]Evidence accepted[/green]: {evidence.evidence_id}")
        console.print(f"  Type: {evidence.evidence_type}")
