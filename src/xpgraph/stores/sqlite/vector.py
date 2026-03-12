"""SQLiteVectorStore — SQLite-backed vector store with cosine similarity."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import structlog

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from xpgraph.stores.base.vector import VectorStore

logger = structlog.get_logger(__name__)


class SQLiteVectorStore(VectorStore):
    """SQLite-backed vector store with brute-force cosine similarity.

    Note: Uses ``check_same_thread=False`` for compatibility with async
    frameworks but provides no internal locking. Callers must synchronise
    access when sharing a single instance across threads.
    """

    def __init__(self, db_path: str | Path) -> None:
        if not HAS_NUMPY:
            msg = (
                "numpy is required for SQLiteVectorStore. "
                "Install it with: pip install numpy"
            )
            raise ImportError(msg)

        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info("sqlite_vector_store_initialized", db_path=str(self._db_path))

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                item_id TEXT PRIMARY KEY,
                vector_blob BLOB NOT NULL,
                dimensions INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_vectors_created
                ON vectors(created_at);
            """
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(
        self,
        item_id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        blob = np.array(vector, dtype=np.float32).tobytes()
        dimensions = len(vector)
        meta_json = json.dumps(metadata or {})

        self._conn.execute(
            "INSERT OR REPLACE INTO vectors "
            "(item_id, vector_blob, dimensions, metadata_json) "
            "VALUES (?, ?, ?, ?)",
            (item_id, blob, dimensions, meta_json),
        )
        self._conn.commit()
        logger.debug("vector_upserted", item_id=item_id, dimensions=dimensions)

    def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_vec = np.array(vector, dtype=np.float32)
        query_norm = float(np.linalg.norm(query_vec))
        if query_norm == 0.0:
            return []

        rows = self._conn.execute(
            "SELECT item_id, vector_blob, metadata_json FROM vectors"
        ).fetchall()

        scored: list[dict[str, Any]] = []
        for row in rows:
            stored_vec = np.frombuffer(row["vector_blob"], dtype=np.float32)
            stored_norm = float(np.linalg.norm(stored_vec))
            if stored_norm == 0.0:
                continue

            score = float(np.dot(query_vec, stored_vec) / (query_norm * stored_norm))
            meta = json.loads(row["metadata_json"])

            # Apply metadata filters
            if filters and not self._matches_filters(meta, filters):
                continue

            scored.append(
                {
                    "item_id": row["item_id"],
                    "score": score,
                    "metadata": meta,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get(self, item_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT item_id, vector_blob, dimensions, metadata_json "
            "FROM vectors WHERE item_id = ?",
            (item_id,),
        ).fetchone()

        if row is None:
            return None

        vec = np.frombuffer(row["vector_blob"], dtype=np.float32)
        return {
            "item_id": row["item_id"],
            "vector": vec.tolist(),
            "dimensions": row["dimensions"],
            "metadata": json.loads(row["metadata_json"]),
        }

    def delete(self, item_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM vectors WHERE item_id = ?",
            (item_id,),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM vectors").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()
        logger.info("sqlite_vector_store_closed", db_path=str(self._db_path))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_filters(meta: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if metadata matches all filter conditions."""
        for key, value in filters.items():
            if key not in meta or meta[key] != value:
                return False
        return True
