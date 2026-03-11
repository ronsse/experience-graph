"""Document Store — raw content storage with full-text search."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog

from xpgraph.core.base import utc_now
from xpgraph.core.ids import generate_ulid

logger = structlog.get_logger(__name__)


class DocumentStore(ABC):
    """Abstract interface for document storage.

    Documents are raw content items (notes, files, transcripts, etc.)
    with metadata and optional full-text search.
    """

    @abstractmethod
    def put(
        self,
        doc_id: str | None,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store or update a document.

        Auto-generates an ID if *doc_id* is ``None``.

        Returns:
            The document ID.
        """

    @abstractmethod
    def get(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve a document by ID.

        Returns:
            Document dict ``{doc_id, content, content_hash, metadata,
            created_at, updated_at}`` or ``None``.
        """

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Delete a document.  Returns ``True`` if it existed."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text search with optional metadata filters.

        Returns a list of matching documents with a ``rank`` key.
        """

    @abstractmethod
    def list_documents(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Paginated listing of documents."""

    @abstractmethod
    def count(self) -> int:
        """Total number of stored documents."""

    @abstractmethod
    def get_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        """Get a document by its content hash (for deduplication)."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------


def _content_hash(content: str) -> str:
    """Return a truncated SHA-256 hex digest (16 chars)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class SQLiteDocumentStore(DocumentStore):
    """SQLite-backed document store with FTS5 full-text search.

    Note: Uses ``check_same_thread=False`` for compatibility with async
    frameworks but provides no internal locking. Callers must synchronise
    access when sharing a single instance across threads.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info("sqlite_document_store_initialized", db_path=str(self._db_path))

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_hash TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                doc_id,
                content
            );

            CREATE INDEX IF NOT EXISTS idx_documents_created
                ON documents(created_at);

            CREATE INDEX IF NOT EXISTS idx_documents_hash
                ON documents(content_hash);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def put(
        self,
        doc_id: str | None,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if doc_id is None:
            doc_id = generate_ulid()

        now = utc_now().isoformat()
        metadata = metadata or {}
        metadata_json = json.dumps(metadata)
        chash = _content_hash(content)

        existing = self.get(doc_id)
        if existing:
            self._conn.execute(
                """
                UPDATE documents
                SET content = ?, content_hash = ?, metadata_json = ?, updated_at = ?
                WHERE doc_id = ?
                """,
                (content, chash, metadata_json, now, doc_id),
            )
            self._conn.execute(
                "DELETE FROM documents_fts WHERE doc_id = ?", (doc_id,)
            )
            self._conn.execute(
                "INSERT INTO documents_fts (doc_id, content) VALUES (?, ?)",
                (doc_id, content),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO documents
                    (doc_id, content, content_hash,
                     metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, content, chash, metadata_json, now, now),
            )
            self._conn.execute(
                "INSERT INTO documents_fts (doc_id, content) VALUES (?, ?)",
                (doc_id, content),
            )

        self._conn.commit()
        logger.debug("document_stored", doc_id=doc_id)
        return doc_id

    def get(self, doc_id: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def delete(self, doc_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM documents WHERE doc_id = ?", (doc_id,)
        )
        self._conn.execute(
            "DELETE FROM documents_fts WHERE doc_id = ?", (doc_id,)
        )
        self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("document_deleted", doc_id=doc_id)
        return deleted

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        sanitized = self._sanitize_fts_query(query)
        if not sanitized:
            return []

        # Split filters into SQL-pushable vs complex
        filter_conditions: list[str] = []
        filter_params: list[Any] = []
        complex_filters: dict[str, Any] = {}

        if filters:
            for key, value in filters.items():
                if isinstance(value, bool):
                    filter_conditions.append(
                        f"json_extract(d.metadata_json, '$.{key}') = ?"
                    )
                    filter_params.append(1 if value else 0)
                elif isinstance(value, (str, int, float)):
                    filter_conditions.append(
                        f"json_extract(d.metadata_json, '$.{key}') = ?"
                    )
                    filter_params.append(value)
                else:
                    complex_filters[key] = value

        where_parts = ["documents_fts MATCH ?"]
        sql_params: list[Any] = [sanitized]

        if filter_conditions:
            where_parts.extend(filter_conditions)
            sql_params.extend(filter_params)

        sql_params.append(limit)
        where_clause = " AND ".join(where_parts)

        sql = (
            "SELECT d.*, bm25(documents_fts) as rank"
            " FROM documents d"
            " JOIN documents_fts fts ON d.doc_id = fts.doc_id"
            f" WHERE {where_clause}"
            " ORDER BY rank"
            " LIMIT ?"
        )
        cursor = self._conn.execute(sql, sql_params)

        results: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            doc = self._row_to_dict(row, include_rank=True)
            if complex_filters:
                metadata = doc["metadata"]
                if not all(metadata.get(k) == v for k, v in complex_filters.items()):
                    continue
            results.append(doc)
        return results

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Sanitize a query string for FTS5 MATCH."""
        if not query or not query.strip():
            return ""

        sanitized = query.replace("\n", " ").replace("\t", " ")
        words = re.findall(r"[a-zA-Z0-9]+", sanitized)
        if not words:
            return ""

        return " OR ".join(f'"{w}"' for w in words[:20])

    # ------------------------------------------------------------------
    # Listing / counting
    # ------------------------------------------------------------------

    def list_documents(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            """
            SELECT * FROM documents
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM documents")
        row = cursor.fetchone()
        assert row is not None
        return int(row["cnt"])

    # ------------------------------------------------------------------
    # Hash lookup
    # ------------------------------------------------------------------

    def get_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
        logger.info("sqlite_document_store_closed")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(
        row: sqlite3.Row, *, include_rank: bool = False
    ) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "doc_id": row["doc_id"],
            "content": row["content"],
            "content_hash": row["content_hash"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_rank:
            doc["rank"] = row["rank"]
        return doc
