"""Trace Store — immutable append-only storage for trace records."""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import structlog

from xpgraph.errors import StoreError
from xpgraph.schemas.trace import Trace

logger = structlog.get_logger(__name__)


class TraceStore(ABC):
    """Abstract interface for immutable trace storage."""

    @abstractmethod
    def append(self, trace: Trace) -> str:
        """Store a trace (immutable).

        Returns trace_id. Raises if trace_id already exists.
        """

    @abstractmethod
    def get(self, trace_id: str) -> Trace | None:
        """Get trace by ID."""

    @abstractmethod
    def query(
        self,
        *,
        source: str | None = None,
        domain: str | None = None,
        agent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Trace]:
        """Query traces with filters."""

    @abstractmethod
    def count(self, *, source: str | None = None, domain: str | None = None) -> int:
        """Count traces with optional filters."""

    @abstractmethod
    def close(self) -> None:
        """Cleanup."""


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------


class SQLiteTraceStore(TraceStore):
    """SQLite-backed immutable trace store.

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
        logger.info("sqlite_trace_store_initialized", db_path=str(self._db_path))

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                intent TEXT NOT NULL,
                domain TEXT,
                agent_id TEXT,
                outcome_status TEXT,
                trace_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_traces_source ON traces(source);
            CREATE INDEX IF NOT EXISTS idx_traces_domain ON traces(domain);
            CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_id);
            CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at);
            CREATE INDEX IF NOT EXISTS idx_traces_outcome ON traces(outcome_status);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def append(self, trace: Trace) -> str:
        domain = trace.context.domain if trace.context else None
        agent_id = trace.context.agent_id if trace.context else None
        outcome_status = (
            trace.outcome.status.value if trace.outcome else None
        )

        try:
            self._conn.execute(
                """
                INSERT INTO traces
                    (trace_id, source, intent, domain, agent_id,
                     outcome_status, trace_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id,
                    trace.source.value,
                    trace.intent,
                    domain,
                    agent_id,
                    outcome_status,
                    trace.model_dump_json(),
                    trace.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            msg = f"Trace {trace.trace_id} already exists"
            raise StoreError(msg) from exc

        logger.debug("trace_appended", trace_id=trace.trace_id)
        return trace.trace_id

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get(self, trace_id: str) -> Trace | None:
        cursor = self._conn.execute(
            "SELECT trace_json FROM traces WHERE trace_id = ?", (trace_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Trace.model_validate_json(row["trace_json"])

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        *,
        source: str | None = None,
        domain: str | None = None,
        agent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Trace]:
        conditions: list[str] = []
        params: list[str | int] = []

        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if domain is not None:
            conditions.append("domain = ?")
            params.append(domain)
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if since is not None:
            conditions.append("created_at >= ?")
            params.append(since.isoformat())
        if until is not None:
            conditions.append("created_at <= ?")
            params.append(until.isoformat())

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        params.append(limit)

        sql = f"SELECT trace_json FROM traces {where} ORDER BY created_at DESC LIMIT ?"
        cursor = self._conn.execute(sql, params)
        return [
            Trace.model_validate_json(row["trace_json"]) for row in cursor.fetchall()
        ]

    # ------------------------------------------------------------------
    # Count
    # ------------------------------------------------------------------

    def count(self, *, source: str | None = None, domain: str | None = None) -> int:
        conditions: list[str] = []
        params: list[str] = []

        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if domain is not None:
            conditions.append("domain = ?")
            params.append(domain)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        cursor = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM traces {where}", params
        )
        row = cursor.fetchone()
        assert row is not None
        return int(row["cnt"])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
        logger.info("sqlite_trace_store_closed")
