"""Trace Store — backward-compatible re-exports."""

from xpgraph.stores.base.trace import TraceStore
from xpgraph.stores.sqlite.trace import SQLiteTraceStore

__all__ = ["TraceStore", "SQLiteTraceStore"]
