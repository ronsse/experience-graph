"""Curate commands — promote, link, label, feedback."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from xpgraph.mutate.commands import Command, CommandStatus, Operation
from xpgraph.mutate.executor import MutationExecutor
from xpgraph_cli.stores import get_event_log

curate_app = typer.Typer(no_args_is_help=True)
console = Console()


def _execute_command(cmd: Command, output_format: str) -> None:
    """Submit a command to the MutationExecutor and display the result."""
    event_log = get_event_log()
    try:
        executor = MutationExecutor(event_log=event_log)
        result = executor.execute(cmd)
    finally:
        event_log.close()

    if output_format == "json":
        console.print(json.dumps({
            "status": result.status.value,
            "command_id": result.command_id,
            "operation": result.operation,
            "message": result.message,
            "created_id": result.created_id,
        }))
    else:
        if result.status == CommandStatus.SUCCESS:
            console.print(
                f"[green]\u2713 Command executed[/green]: {result.operation}"
            )
        else:
            console.print(
                f"[red]\u2717 Command {result.status}[/red]: {result.operation}"
            )
        console.print(f"  ID: {result.command_id}")
        console.print(f"  Message: {result.message}")


@curate_app.command()
def promote(
    trace_id: str = typer.Argument(..., help="Trace ID to promote to precedent"),
    title: str = typer.Option(..., help="Precedent title"),
    description: str = typer.Option(..., help="Precedent description"),
    requested_by: str = typer.Option("cli", "--by", help="Who is promoting"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Promote a trace to a precedent."""
    cmd = Command(
        operation=Operation.PRECEDENT_PROMOTE,
        args={"trace_id": trace_id, "title": title, "description": description},
        target_id=trace_id,
        target_type="trace",
        requested_by=requested_by,
    )
    _execute_command(cmd, output_format)


@curate_app.command()
def link(
    source_id: str = typer.Argument(..., help="Source entity/node ID"),
    target_id: str = typer.Argument(..., help="Target entity/node ID"),
    edge_kind: str = typer.Option("entity_related_to", "--kind", help="Edge kind"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Create a link between two entities."""
    cmd = Command(
        operation=Operation.LINK_CREATE,
        args={
            "source_id": source_id,
            "target_id": target_id,
            "edge_kind": edge_kind,
        },
        requested_by="cli",
    )
    _execute_command(cmd, output_format)


@curate_app.command()
def label(
    target_id: str = typer.Argument(..., help="Entity ID to label"),
    label_value: str = typer.Argument(..., help="Label to add"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Add a label to an entity."""
    cmd = Command(
        operation=Operation.LABEL_ADD,
        args={"target_id": target_id, "label": label_value},
        target_id=target_id,
        requested_by="cli",
    )
    _execute_command(cmd, output_format)


@curate_app.command()
def feedback(
    target_id: str = typer.Argument(..., help="Trace or precedent ID"),
    rating: float = typer.Argument(..., help="Rating (0.0 to 1.0)"),
    comment: str = typer.Option(None, help="Optional comment"),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Record feedback on a trace or precedent."""
    args: dict[str, object] = {"target_id": target_id, "rating": rating}
    if comment:
        args["comment"] = comment
    cmd = Command(
        operation=Operation.FEEDBACK_RECORD,
        args=args,
        target_id=target_id,
        requested_by="cli",
    )
    _execute_command(cmd, output_format)
