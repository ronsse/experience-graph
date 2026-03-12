"""Document Store — backward-compatible re-exports."""

from xpgraph.stores.base.document import DocumentStore
from xpgraph.stores.sqlite.document import SQLiteDocumentStore

__all__ = ["DocumentStore", "SQLiteDocumentStore"]
