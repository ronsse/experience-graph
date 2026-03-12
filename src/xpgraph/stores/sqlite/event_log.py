"""SQLiteEventLog — SQLite-backed append-only event log."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from xpgraph.stores.base.event_log import Event, EventLog, EventType

logger = structlog.get_logger(__name__)


_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    entity_id TEXT,
    entity_type TEXT,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    schema_version TEXT
)"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)",
]


class SQLiteEventLog(EventLog):
    """SQLite-backed append-only event log.

    Note: Uses ``check_same_thread=False`` for compatibility with async
    frameworks but provides no internal locking. Callers must synchronise
    access when sharing a single instance across threads.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info("event_log.opened", db_path=str(self._db_path))

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(_CREATE_TABLE)
        for idx_sql in _CREATE_INDEXES:
            cur.execute(idx_sql)
        self._conn.commit()

    # -- mutations -----------------------------------------------------------

    def append(self, event: Event) -> None:
        """Append event (immutable, no updates)."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO events "
            "(event_id, event_type, source, entity_id, entity_type, "
            "occurred_at, recorded_at, payload_json, metadata_json, schema_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                str(event.event_type),
                event.source,
                event.entity_id,
                event.entity_type,
                event.occurred_at.isoformat(),
                event.recorded_at.isoformat(),
                json.dumps(event.payload),
                json.dumps(event.metadata),
                event.schema_version,
            ),
        )
        self._conn.commit()
        logger.debug(
            "event_log.appended",
            event_id=event.event_id,
            event_type=str(event.event_type),
        )

    # -- queries -------------------------------------------------------------

    def get_events(
        self,
        *,
        event_type: EventType | None = None,
        entity_id: str | None = None,
        source: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query events with filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(str(event_type))
        if entity_id is not None:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if source is not None:
            clauses.append("source = ?")
            params.append(source)
        if since is not None:
            clauses.append("occurred_at >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("occurred_at <= ?")
            params.append(until.isoformat())

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM events WHERE {where} ORDER BY occurred_at ASC LIMIT ?"
        params.append(limit)

        cur = self._conn.cursor()
        cur.execute(sql, params)
        return [self._row_to_event(row) for row in cur.fetchall()]

    def count(
        self,
        *,
        event_type: EventType | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count events with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(str(event_type))
        if since is not None:
            clauses.append("occurred_at >= ?")
            params.append(since.isoformat())

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT COUNT(*) FROM events WHERE {where}"

        cur = self._conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("event_log.closed", db_path=str(self._db_path))

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            event_id=row["event_id"],
            event_type=EventType(row["event_type"]),
            source=row["source"],
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            payload=json.loads(row["payload_json"]),
            metadata=json.loads(row["metadata_json"]),
            schema_version=row["schema_version"],
        )
