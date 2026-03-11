"""Graph Store — node and edge storage with subgraph traversal."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog

from xpgraph.core.base import utc_now
from xpgraph.core.ids import generate_ulid

logger = structlog.get_logger(__name__)


class GraphStore(ABC):
    """Abstract interface for graph storage.

    Stores nodes (entities) and edges (relationships) with
    metadata and provenance tracking.
    """

    @abstractmethod
    def upsert_node(
        self,
        node_id: str | None,
        node_type: str,
        properties: dict[str, Any],
    ) -> str:
        """Insert or update a node.

        Auto-generates an ID if *node_id* is ``None``.

        Returns:
            The node ID.
        """

    @abstractmethod
    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a node by ID.

        Returns:
            Node dict ``{node_id, node_type, properties, created_at,
            updated_at}`` or ``None``.
        """

    @abstractmethod
    def get_nodes_bulk(self, node_ids: list[str]) -> list[dict[str, Any]]:
        """Batch get nodes by IDs."""

    @abstractmethod
    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Insert or update an edge.

        Returns:
            The edge ID.
        """

    @abstractmethod
    def get_edges(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get edges for a node.

        Args:
            node_id: The node ID.
            direction: ``"outgoing"``, ``"incoming"``, or ``"both"``.
            edge_type: Optional filter by edge type.
        """

    @abstractmethod
    def get_subgraph(
        self,
        seed_ids: list[str],
        depth: int = 2,
        edge_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get subgraph via BFS traversal.

        Returns:
            Dict with ``nodes`` and ``edges`` lists.
        """

    @abstractmethod
    def query(
        self,
        node_type: str | None = None,
        properties: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query nodes by type and/or properties."""

    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        """Delete a node and cascade to its edges.

        Returns ``True`` if the node existed.
        """

    @abstractmethod
    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge.

        Returns ``True`` if the edge existed.
        """

    @abstractmethod
    def count_nodes(self) -> int:
        """Total node count."""

    @abstractmethod
    def count_edges(self) -> int:
        """Total edge count."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------


class SQLiteGraphStore(GraphStore):
    """SQLite-backed graph store with recursive CTE subgraph traversal.

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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edges (
                edge_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES nodes(node_id),
                FOREIGN KEY (target_id) REFERENCES nodes(node_id)
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
        """)
        self._conn.commit()

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

        now = utc_now().isoformat()
        properties_json = json.dumps(properties)

        existing = self.get_node(node_id)
        if existing:
            self._conn.execute(
                """
                UPDATE nodes
                SET node_type = ?, properties_json = ?, updated_at = ?
                WHERE node_id = ?
                """,
                (node_type, properties_json, now, node_id),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO nodes
                    (node_id, node_type, properties_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (node_id, node_type, properties_json, now, now),
            )

        self._conn.commit()
        logger.debug("node_upserted", node_id=node_id, node_type=node_type)
        return node_id

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._node_row_to_dict(row)

    def get_nodes_bulk(self, node_ids: list[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []
        placeholders = ",".join("?" for _ in node_ids)
        cursor = self._conn.execute(
            f"SELECT * FROM nodes WHERE node_id IN ({placeholders})",
            node_ids,
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
        # Check if edge already exists by (source, target, type)
        cursor = self._conn.execute(
            """
            SELECT edge_id FROM edges
            WHERE source_id = ? AND target_id = ? AND edge_type = ?
            """,
            (source_id, target_id, edge_type),
        )
        row = cursor.fetchone()

        now = utc_now().isoformat()
        properties_json = json.dumps(properties or {})

        if row:
            edge_id: str = row["edge_id"]
            self._conn.execute(
                "UPDATE edges SET properties_json = ? WHERE edge_id = ?",
                (properties_json, edge_id),
            )
        else:
            edge_id = generate_ulid()
            self._conn.execute(
                """
                INSERT INTO edges
                    (edge_id, source_id, target_id, edge_type,
                     properties_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (edge_id, source_id, target_id, edge_type, properties_json, now),
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
    ) -> dict[str, Any]:
        if not seed_ids:
            return {"nodes": [], "edges": []}

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
            SELECT node_id, 0 FROM nodes
            WHERE node_id IN ({seed_placeholders})

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
                {edge_filter}
            WHERE t.depth < ?
        ),
        unique_nodes AS (
            SELECT node_id, MIN(depth) AS min_depth
            FROM traversal
            GROUP BY node_id
        )
        SELECT
            n.node_id,
            n.node_type,
            n.properties_json,
            n.created_at,
            n.updated_at,
            un.min_depth
        FROM unique_nodes un
        JOIN nodes n ON n.node_id = un.node_id
        ORDER BY un.min_depth, n.node_id
        """

        params: list[Any] = list(seed_ids) + edge_params + [depth]
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
            np = ",".join("?" for _ in node_list)

            edge_query = f"""
            SELECT * FROM edges
            WHERE source_id IN ({np})
              AND target_id IN ({np})
            """
            eq_params: list[Any] = node_list + node_list
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
    ) -> list[dict[str, Any]]:
        conditions = ["1=1"]
        params: list[Any] = []

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
        # Cascade: delete edges first
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
        cursor = self._conn.execute("SELECT COUNT(*) AS cnt FROM nodes")
        row = cursor.fetchone()
        assert row is not None
        return int(row["cnt"])

    def count_edges(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) AS cnt FROM edges")
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
        }
