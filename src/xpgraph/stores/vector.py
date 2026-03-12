"""Vector Store — backward-compatible re-exports."""

from xpgraph.stores.base.vector import VectorStore
from xpgraph.stores.sqlite.vector import SQLiteVectorStore

__all__ = ["VectorStore", "SQLiteVectorStore"]
