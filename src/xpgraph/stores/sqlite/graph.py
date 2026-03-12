"""SQLiteGraphStore — SQLite-backed graph store with SCD Type 2 versioning."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from xpgraph.core.base import utc_now
from xpgraph.core.ids import generate_ulid
from xpgraph.stores.base.graph import GraphStore

logger = structlog.get_logger(__name__)


class SQLiteGraphStore(GraphStore):
    """SQLite-backed graph store with recursive CTE subgraph traversal.

    Supports SCD Type 2 temporal versioning: each mutation creates a new
    version row and closes the previous one by setting ``valid_to``.

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
        logger.info("sqlite_graph_store_initialized", db_path=str(self._db_path))

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        # Check whether the schema already has temporal columns by
        # inspecting the nodes table (if it exists).
        needs_migration = False
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'"
        )
        if cursor.fetchone() is not None:
            col_cursor = self._conn.execute("PRAGMA table_info(nodes)")
            col_names = {row["name"] for row in col_cursor.fetchall()}
            if "version_id" not in col_names:
                needs_migration = True

        if needs_migration:
            self._migrate_to_v2()
        else:
            self._create_v2_schema()

    def _create_v2_schema(self) -> None:
        """Create temporal (v2) schema from scratch."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                version_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS edges (
                version_id TEXT PRIMARY KEY,
                edge_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT DEFAULT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_node_id ON nodes(node_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_nodes_valid ON nodes(valid_from, valid_to);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_current
                ON nodes(node_id) WHERE valid_to IS NULL;

            CREATE INDEX IF NOT EXISTS idx_edges_edge_id ON edges(edge_id);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
            CREATE INDEX IF NOT EXISTS idx_edges_valid ON edges(valid_from, valid_to);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_current
                ON edges(edge_id) WHERE valid_to IS NULL;
        """)
        self._conn.commit()

    def _migrate_to_v2(self) -> None:
        """Migrate v1 (node_id PK) tables to v2 (version_id PK, temporal)."""
        logger.info("migrating_graph_schema_to_v2")
        self._conn.executescript("""
            -- Nodes migration
            CREATE TABLE nodes_v2 (
                version_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT DEFAULT NULL
            );

            INSERT INTO nodes_v2 (version_id, node_id, node_type, properties_json,
                                  created_at, updated_at, valid_from, valid_to)
            SELECT node_id, node_id, node_type, properties_json,
                   created_at, updated_at, created_at, NULL
            FROM nodes;

            DROP TABLE nodes;
            ALTER TABLE nodes_v2 RENAME TO nodes;

            -- Edges migration
            CREATE TABLE edges_v2 (
                version_id TEXT PRIMARY KEY,
                edge_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT DEFAULT NULL
            );

            INSERT INTO edges_v2 (version_id, edge_id, source_id, target_id,
                                  edge_type, properties_json, created_at,
                                  valid_from, valid_to)
            SELECT edge_id, edge_id, source_id, target_id,
                   edge_type, properties_json, created_at, created_at, NULL
            FROM edges;

            DROP TABLE edges;
            ALTER TABLE edges_v2 RENAME TO edges;

            -- Recreate indices
            CREATE INDEX idx_nodes_node_id ON nodes(node_id);
            CREATE INDEX idx_nodes_type ON nodes(node_type);
            CREATE INDEX idx_nodes_valid ON nodes(valid_from, valid_to);
            CREATE UNIQUE INDEX idx_nodes_current
                ON nodes(node_id) WHERE valid_to IS NULL;

            CREATE INDEX idx_edges_edge_id ON edges(edge_id);
            CREATE INDEX idx_edges_source ON edges(source_id);
            CREATE INDEX idx_edges_target ON edges(target_id);
            CREATE INDEX idx_edges_type ON edges(edge_type);
            CREATE INDEX idx_edges_valid ON edges(valid_from, valid_to);
            CREATE UNIQUE INDEX idx_edges_current
                ON edges(edge_id) WHERE valid_to IS NULL;
        """)
        self._conn.commit()
        logger.info("graph_schema_migration_complete")

    # ------------------------------------------------------------------
    # Temporal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _temporal_filter(as_of: datetime | None, table_alias: str = "") -> str:
        """Return a SQL WHERE fragment for temporal filtering.

        When *as_of* is ``None`` only current rows (``valid_to IS NULL``)
        are matched.  When set, returns the version valid at that instant.
        """
        prefix = f"{table_alias}." if table_alias else ""
        if as_of is None:
            return f"{prefix}valid_to IS NULL"
        return (
            f"{prefix}valid_from <= ? AND "
            f"({prefix}valid_to IS NULL OR {prefix}valid_to > ?)"
        )

    @staticmethod
    def _temporal_params(as_of: datetime | None) -> list[str]:
        """Return bind parameters for :func:`_temporal_filter`."""
        if as_of is None:
            return []
        iso = as_of.isoformat()
        return [iso, iso]

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def upsert_node(
        self,
        node_id: str | None,
        node_type: str,
        properties: dict[str, Any],
    ) -> str:
        if node_id is None:
            node_id = generate_ulid()

        now = utc_now()
        now_iso = now.isoformat()
        properties_json = json.dumps(properties)

        existing = self.get_node(node_id)
        if existing:
            # Close the current version
            self._conn.execute(
                """
                UPDATE nodes SET valid_to = ?
                WHERE node_id = ? AND valid_to IS NULL
                """,
                (now_iso, node_id),
            )
            # Insert new version
            version_id = generate_ulid()
            self._conn.execute(
                """
                INSERT INTO nodes
                    (version_id, node_id, node_type, properties_json,
                     created_at, updated_at, valid_from, valid_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    version_id,
                    node_id,
                    node_type,
                    properties_json,
                    existing["created_at"],
                    now_iso,
                    now_iso,
                ),
            )
        else:
            version_id = generate_ulid()
            self._conn.execute(
                """
                INSERT INTO nodes
                    (version_id, node_id, node_type, properties_json,
                     created_at, updated_at, valid_from, valid_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    version_id,
                    node_id,
                    node_type,
                    properties_json,
                    now_iso,
                    now_iso,
                    now_iso,
                ),
            )

        self._conn.commit()
        logger.debug("node_upserted", node_id=node_id, node_type=node_type)
        return node_id

    def get_node(
        self,
        node_id: str,
        as_of: datetime | None = None,
    ) -> dict[str, Any] | None:
        temporal = self._temporal_filter(as_of)
        params: list[Any] = [node_id, *self._temporal_params(as_of)]
        cursor = self._conn.execute(
            f"SELECT * FROM nodes WHERE node_id = ? AND {temporal}",
            params,
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._node_row_to_dict(row)

    def get_nodes_bulk(
        self,
        node_ids: list[str],
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        if not node_ids:
            return []
        placeholders = ",".join("?" for _ in node_ids)
        temporal = self._temporal_filter(as_of)
        params: list[Any] = list(node_ids) + self._temporal_params(as_of)
        cursor = self._conn.execute(
            f"SELECT * FROM nodes WHERE node_id IN ({placeholders}) AND {temporal}",
            params,
        )
        return [self._node_row_to_dict(row) for row in cursor.fetchall()]

    def get_node_history(self, node_id: str) -> list[dict[str, Any]]:
        """Return all versions of *node_id*, newest first."""
        cursor = self._conn.execute(
            "SELECT * FROM nodes WHERE node_id = ? ORDER BY valid_from DESC",
            (node_id,),
        )
        return [self._node_row_to_dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        # Check if a current edge already exists by (source, target, type)
        cursor = self._conn.execute(
            """
            SELECT edge_id FROM edges
            WHERE source_id = ? AND target_id = ? AND edge_type = ?
              AND valid_to IS NULL
            """,
            (source_id, target_id, edge_type),
        )
        row = cursor.fetchone()

        now = utc_now()
        now_iso = now.isoformat()
        properties_json = json.dumps(properties or {})

        if row:
            edge_id: str = row["edge_id"]
            # Close current version
            self._conn.execute(
                """
                UPDATE edges SET valid_to = ?
                WHERE edge_id = ? AND valid_to IS NULL
                """,
                (now_iso, edge_id),
            )
            # Insert new version
            version_id = generate_ulid()
            self._conn.execute(
                """
                INSERT INTO edges
                    (version_id, edge_id, source_id, target_id, edge_type,
                     properties_json, created_at, valid_from, valid_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    version_id,
                    edge_id,
                    source_id,
                    target_id,
                    edge_type,
                    properties_json,
                    now_iso,
                    now_iso,
                ),
            )
        else:
            edge_id = generate_ulid()
            version_id = generate_ulid()
            self._conn.execute(
                """
                INSERT INTO edges
                    (version_id, edge_id, source_id, target_id, edge_type,
                     properties_json, created_at, valid_from, valid_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    version_id,
                    edge_id,
                    source_id,
                    target_id,
                    edge_type,
                    properties_json,
                    now_iso,
                    now_iso,
                ),
            )

        self._conn.commit()
        logger.debug(
            "edge_upserted",
            edge_id=edge_id,
            source=source_id,
            target=target_id,
            type=edge_type,
        )
        return edge_id

    def get_edges(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: str | None = None,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []

        if direction in ("outgoing", "both"):
            conditions.append("source_id = ?")
            params.append(node_id)
        if direction in ("incoming", "both"):
            conditions.append("target_id = ?")
            params.append(node_id)

        where_clause = " OR ".join(conditions)

        if edge_type:
            where_clause = f"({where_clause}) AND edge_type = ?"
            params.append(edge_type)

        temporal = self._temporal_filter(as_of)
        where_clause = f"({where_clause}) AND {temporal}"
        params.extend(self._temporal_params(as_of))

        cursor = self._conn.execute(
            f"SELECT * FROM edges WHERE {where_clause}",
            params,
        )
        return [self._edge_row_to_dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Subgraph (recursive CTE)
    # ------------------------------------------------------------------

    def get_subgraph(
        self,
        seed_ids: list[str],
        depth: int = 2,
        edge_types: list[str] | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        if not seed_ids:
            return {"nodes": [], "edges": []}

        # Temporal filter fragments
        node_temporal = self._temporal_filter(as_of, "n")
        node_temporal_params = self._temporal_params(as_of)
        edge_temporal = self._temporal_filter(as_of, "e")
        edge_temporal_params = self._temporal_params(as_of)

        # Build edge type filter
        edge_filter = ""
        edge_params: list[Any] = []
        if edge_types:
            placeholders = ",".join("?" for _ in edge_types)
            edge_filter = f"AND e.edge_type IN ({placeholders})"
            edge_params = list(edge_types)

        seed_placeholders = ",".join("?" for _ in seed_ids)

        # Recursive CTE to collect reachable node IDs within depth
        query = f"""
        WITH RECURSIVE traversal(node_id, depth) AS (
            -- Base case: seed nodes at depth 0
            SELECT n.node_id, 0 FROM nodes n
            WHERE n.node_id IN ({seed_placeholders})
              AND {node_temporal}

            UNION

            -- Recursive case: follow edges up to max depth
            SELECT
                CASE
                    WHEN e.source_id = t.node_id THEN e.target_id
                    ELSE e.source_id
                END AS node_id,
                t.depth + 1
            FROM traversal t
            JOIN edges e ON (e.source_id = t.node_id OR e.target_id = t.node_id)
                AND {edge_temporal}
                {edge_filter}
            WHERE t.depth < ?
        ),
        unique_nodes AS (
            SELECT node_id, MIN(depth) AS min_depth
            FROM traversal
            GROUP BY node_id
        )
        SELECT
            n.version_id,
            n.node_id,
            n.node_type,
            n.properties_json,
            n.created_at,
            n.updated_at,
            n.valid_from,
            n.valid_to,
            un.min_depth
        FROM unique_nodes un
        JOIN nodes n ON n.node_id = un.node_id AND {node_temporal}
        ORDER BY un.min_depth, n.node_id
        """

        params: list[Any] = (
            list(seed_ids)
            + node_temporal_params  # base case temporal
            + edge_temporal_params  # recursive case temporal
            + edge_params
            + [depth]
            + node_temporal_params  # final JOIN temporal
        )
        cursor = self._conn.execute(query, params)

        collected_nodes: list[dict[str, Any]] = []
        node_id_set: set[str] = set()
        for row in cursor.fetchall():
            node_id_set.add(row["node_id"])
            collected_nodes.append(self._node_row_to_dict(row))

        # Fetch all edges between collected nodes
        collected_edges: list[dict[str, Any]] = []
        if node_id_set:
            node_list = list(node_id_set)
            np_ = ",".join("?" for _ in node_list)
            edge_temporal_frag = self._temporal_filter(as_of)

            edge_query = f"""
            SELECT * FROM edges
            WHERE source_id IN ({np_})
              AND target_id IN ({np_})
              AND {edge_temporal_frag}
            """
            eq_params: list[Any] = (
                node_list + node_list + self._temporal_params(as_of)
            )
            if edge_types:
                etp = ",".join("?" for _ in edge_types)
                edge_query += f" AND edge_type IN ({etp})"
                eq_params += list(edge_types)

            cursor = self._conn.execute(edge_query, eq_params)
            collected_edges = [
                self._edge_row_to_dict(row) for row in cursor.fetchall()
            ]

        logger.debug(
            "subgraph_fetched",
            seed_count=len(seed_ids),
            depth=depth,
            nodes_found=len(collected_nodes),
            edges_found=len(collected_edges),
        )

        return {"nodes": collected_nodes, "edges": collected_edges}

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        node_type: str | None = None,
        properties: dict[str, Any] | None = None,
        limit: int = 50,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        temporal = self._temporal_filter(as_of)
        conditions = [temporal]
        params: list[Any] = list(self._temporal_params(as_of))

        if node_type:
            conditions.append("node_type = ?")
            params.append(node_type)

        # Push simple property filters to SQL via json_extract
        complex_filters: dict[str, Any] = {}
        if properties:
            for key, value in properties.items():
                if isinstance(value, bool):
                    conditions.append(
                        f"json_extract(properties_json, '$.{key}') = ?"
                    )
                    params.append(1 if value else 0)
                elif isinstance(value, (str, int, float)):
                    conditions.append(
                        f"json_extract(properties_json, '$.{key}') = ?"
                    )
                    params.append(value)
                elif value is None:
                    conditions.append(
                        f"json_extract(properties_json, '$.{key}') IS NULL"
                    )
                else:
                    complex_filters[key] = value

        where_clause = " AND ".join(conditions)
        params.append(limit)

        cursor = self._conn.execute(
            f"""
            SELECT * FROM nodes
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        )

        results: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            node = self._node_row_to_dict(row)
            # Apply complex filters Python-side
            if complex_filters:
                props = node["properties"]
                if not all(props.get(k) == v for k, v in complex_filters.items()):
                    continue
            results.append(node)
        return results

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_node(self, node_id: str) -> bool:
        # Cascade: delete all edge versions referencing this node
        self._conn.execute(
            "DELETE FROM edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )
        cursor = self._conn.execute(
            "DELETE FROM nodes WHERE node_id = ?", (node_id,)
        )
        self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("node_deleted", node_id=node_id)
        return deleted

    def delete_edge(self, edge_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM edges WHERE edge_id = ?", (edge_id,)
        )
        self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("edge_deleted", edge_id=edge_id)
        return deleted

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    def count_nodes(self) -> int:
        cursor = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM nodes WHERE valid_to IS NULL"
        )
        row = cursor.fetchone()
        assert row is not None
        return int(row["cnt"])

    def count_edges(self) -> int:
        cursor = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM edges WHERE valid_to IS NULL"
        )
        row = cursor.fetchone()
        assert row is not None
        return int(row["cnt"])

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
        logger.info("sqlite_graph_store_closed")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _node_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "node_id": row["node_id"],
            "node_type": row["node_type"],
            "properties": json.loads(row["properties_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
        }

    @staticmethod
    def _edge_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "edge_id": row["edge_id"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "edge_type": row["edge_type"],
            "properties": json.loads(row["properties_json"]),
            "created_at": row["created_at"],
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
        }
