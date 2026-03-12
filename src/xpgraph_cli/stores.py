"""Store initialization and access for the CLI."""

from __future__ import annotations

from pathlib import Path

import structlog
import typer

from xpgraph.stores.base import DocumentStore, EventLog, GraphStore, TraceStore
from xpgraph.stores.registry import StoreRegistry
from xpgraph_cli.config import XPGConfig, get_data_dir

logger = structlog.get_logger(__name__)


def _get_registry() -> StoreRegistry:
    """Create a StoreRegistry from CLI config."""
    config = XPGConfig.load()
    data_dir = Path(config.data_dir) if config.data_dir else get_data_dir()
    stores_dir = data_dir / "stores"
    if not stores_dir.exists():
        from rich.console import Console  # noqa: PLC0415

        Console().print(
            "[red]Stores not initialized. Run 'xpg admin init' first.[/red]"
        )
        raise typer.Exit(code=1)
    return StoreRegistry(stores_dir=stores_dir)


def get_trace_store() -> TraceStore:
    """Open (or create) the trace store."""
    return _get_registry().trace_store


def get_document_store() -> DocumentStore:
    """Open (or create) the document store."""
    return _get_registry().document_store


def get_event_log() -> EventLog:
    """Open (or create) the event log."""
    return _get_registry().event_log


def get_graph_store() -> GraphStore:
    """Open (or create) the graph store."""
    return _get_registry().graph_store
