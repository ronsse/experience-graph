"""Store initialization and access for the CLI."""

from __future__ import annotations

from pathlib import Path

import structlog
import typer

from xpgraph.stores.document import DocumentStore, SQLiteDocumentStore
from xpgraph.stores.event_log import EventLog, SQLiteEventLog
from xpgraph.stores.graph import GraphStore, SQLiteGraphStore
from xpgraph.stores.trace import SQLiteTraceStore, TraceStore
from xpgraph_cli.config import XPGConfig, get_data_dir

logger = structlog.get_logger(__name__)


def _stores_dir() -> Path:
    """Resolve the stores directory from config."""
    config = XPGConfig.load()
    data_dir = Path(config.data_dir) if config.data_dir else get_data_dir()
    return data_dir / "stores"


def _require_init(stores_dir: Path) -> None:
    """Raise typer.Exit if stores are not initialized."""
    if not stores_dir.exists():
        from rich.console import Console  # noqa: PLC0415

        Console().print(
            "[red]Stores not initialized. Run 'xpg admin init' first.[/red]"
        )
        raise typer.Exit(code=1)


def get_trace_store() -> TraceStore:
    """Open (or create) the trace store."""
    sd = _stores_dir()
    _require_init(sd)
    return SQLiteTraceStore(sd / "traces.db")


def get_document_store() -> DocumentStore:
    """Open (or create) the document store."""
    sd = _stores_dir()
    _require_init(sd)
    return SQLiteDocumentStore(sd / "documents.db")


def get_event_log() -> EventLog:
    """Open (or create) the event log."""
    sd = _stores_dir()
    _require_init(sd)
    return SQLiteEventLog(sd / "events.db")


def get_graph_store() -> GraphStore:
    """Open (or create) the graph store."""
    sd = _stores_dir()
    _require_init(sd)
    return SQLiteGraphStore(sd / "graph.db")
