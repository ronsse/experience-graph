"""Curate commands — promote, link, label, feedback, entity."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from xpgraph.mutate.commands import Command, CommandStatus, Operation
from xpgraph.mutate.executor import MutationExecutor
from xpgraph_cli.stores import get_event_log, get_graph_store

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
    store = get_graph_store()
    try:
        # Verify both nodes exist
        source = store.get_node(source_id)
        target = store.get_node(target_id)
        if source is None:
            msg = f"Source node not found: {source_id}"
            if output_format == "json":
                console.print(json.dumps({"status": "error", "message": msg}))
            else:
                console.print(f"[red]{msg}[/red]")
            raise typer.Exit(code=1)
        if target is None:
            msg = f"Target node not found: {target_id}"
            if output_format == "json":
                console.print(json.dumps({"status": "error", "message": msg}))
            else:
                console.print(f"[red]{msg}[/red]")
            raise typer.Exit(code=1)

        edge_id = store.upsert_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_kind,
        )
    finally:
        store.close()

    if output_format == "json":
        console.print(json.dumps({
            "status": "ok",
            "edge_id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_kind": edge_kind,
        }))
    else:
        console.print(f"[green]\u2713 Link created[/green]: {edge_id}")
        console.print(f"  {source_id} --[{edge_kind}]--> {target_id}")


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
def entity(
    entity_type: str = typer.Argument(
        ..., help="Entity type (concept, person, system, etc.)"
    ),
    name: str = typer.Argument(..., help="Entity name"),
    properties: str = typer.Option(
        None,
        "--properties",
        "-p",
        help='JSON properties dict, e.g. \'{"k": "v"}\'',
    ),
    output_format: str = typer.Option("text", "--format", help="Output format"),
) -> None:
    """Create an entity node in the knowledge graph."""
    props: dict[str, object] = {}
    if properties:
        try:
            props = json.loads(properties)
        except json.JSONDecodeError as exc:
            if output_format == "json":
                console.print(json.dumps({
                    "status": "error",
                    "message": f"Invalid JSON for --properties: {exc}",
                }))
            else:
                console.print(f"[red]Invalid JSON for --properties[/red]: {exc}")
            raise typer.Exit(code=1) from exc

    props["name"] = name

    store = get_graph_store()
    try:
        node_id = store.upsert_node(
            node_id=None,
            node_type=entity_type,
            properties=props,
        )
    finally:
        store.close()

    if output_format == "json":
        console.print(json.dumps({
            "status": "ok",
            "node_id": node_id,
            "entity_type": entity_type,
            "name": name,
            "properties": props,
        }))
    else:
        console.print(f"[green]\u2713 Entity created[/green]: {node_id}")
        console.print(f"  Type: {entity_type}")
        console.print(f"  Name: {name}")
        if properties:
            console.print(f"  Properties: {props}")


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
