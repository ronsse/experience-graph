"""Experience Graph CLI — xpg."""

from __future__ import annotations

import typer

from xpgraph_cli.admin import admin_app
from xpgraph_cli.curate import curate_app
from xpgraph_cli.ingest import ingest_app
from xpgraph_cli.retrieve import retrieve_app

app = typer.Typer(
    name="xpg",
    help="Experience Graph — shared experience store for AI agents and teams.",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(admin_app, name="admin", help="Administration and setup")

analyze_app = typer.Typer(help="Analyze the experience graph", no_args_is_help=True)
worker_app = typer.Typer(help="Run curation workers", no_args_is_help=True)

app.add_typer(ingest_app, name="ingest")
app.add_typer(curate_app, name="curate")
app.add_typer(retrieve_app, name="retrieve")
app.add_typer(analyze_app, name="analyze")
app.add_typer(worker_app, name="worker")


if __name__ == "__main__":
    app()
