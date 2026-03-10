"""Admin commands for Experience Graph CLI."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from xpgraph_cli.config import XPGConfig, get_config_dir, get_data_dir

admin_app = typer.Typer(no_args_is_help=True)
console = Console()


@admin_app.command()
def init(
    data_dir: str = typer.Option(None, help="Custom data directory path"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
    output_format: str = typer.Option(
        "text", "--format", help="Output format: text or json"
    ),
) -> None:
    """Initialize Experience Graph stores and configuration."""
    config_dir = get_config_dir()
    config_path = config_dir / "config.yaml"

    if config_path.exists() and not force:
        if output_format == "json":
            console.print(
                json.dumps({"status": "exists", "config_dir": str(config_dir)})
            )
        else:
            console.print(
                f"[yellow]Config already exists at {config_path}."
                " Use --force to overwrite.[/yellow]"
            )
        raise typer.Exit(code=0)

    # Set up data directory
    actual_data_dir = Path(data_dir) if data_dir else get_data_dir()
    actual_data_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for stores
    (actual_data_dir / "stores").mkdir(exist_ok=True)

    # Save config
    config = XPGConfig(data_dir=str(actual_data_dir))
    config.save()

    if output_format == "json":
        console.print(
            json.dumps(
                {
                    "status": "initialized",
                    "config_dir": str(config_dir),
                    "data_dir": str(actual_data_dir),
                }
            )
        )
    else:
        console.print("[green]Initialized Experience Graph[/green]")
        console.print(f"  Config: {config_path}")
        console.print(f"  Data:   {actual_data_dir}")


@admin_app.command()
def health(
    output_format: str = typer.Option(
        "text", "--format", help="Output format: text or json"
    ),
) -> None:
    """Check health of Experience Graph stores."""
    config = XPGConfig.load()
    data_dir = Path(config.data_dir) if config.data_dir else get_data_dir()
    stores_dir = data_dir / "stores"

    checks: dict[str, bool] = {
        "config": get_config_dir().exists(),
        "data_dir": data_dir.exists(),
        "stores_dir": stores_dir.exists(),
    }

    # Check for store files
    store_files = [
        "documents.db",
        "graph.db",
        "vectors.db",
        "events.db",
        "traces.db",
    ]
    for sf in store_files:
        checks[sf] = (stores_dir / sf).exists()

    if output_format == "json":
        console.print(json.dumps(checks))
    else:
        table = Table(title="Experience Graph Health")
        table.add_column("Component", style="cyan")
        table.add_column("Status")
        for name, ok in checks.items():
            status = "[green]OK[/green]" if ok else "[red]MISSING[/red]"
            table.add_row(name, status)
        console.print(table)
