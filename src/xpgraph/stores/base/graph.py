"""GraphStore — abstract interface for graph storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class GraphStore(ABC):
    """Abstract interface for graph storage.

    Stores nodes (entities) and edges (relationships) with
    metadata and provenance tracking.

    Supports SCD Type 2 temporal versioning via ``valid_from``/``valid_to``
    columns.  Pass ``as_of`` to read methods to time-travel.
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

        When updating an existing (current) node, the old version is
        closed (``valid_to`` set) and a new version row is inserted.

        Returns:
            The node ID.
        """

    @abstractmethod
    def get_node(
        self,
        node_id: str,
        as_of: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Get a node by ID.

        Args:
            node_id: Logical entity ID.
            as_of: If set, return the version that was valid at this time.
                   If ``None``, return the current (``valid_to IS NULL``)
                   version.

        Returns:
            Node dict ``{node_id, node_type, properties, created_at,
            updated_at, valid_from, valid_to}`` or ``None``.
        """

    @abstractmethod
    def get_nodes_bulk(
        self,
        node_ids: list[str],
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Batch get nodes by IDs.

        Args:
            node_ids: Logical entity IDs.
            as_of: Optional point-in-time filter.
        """

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
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get edges for a node.

        Args:
            node_id: The node ID.
            direction: ``"outgoing"``, ``"incoming"``, or ``"both"``.
            edge_type: Optional filter by edge type.
            as_of: Optional point-in-time filter.
        """

    @abstractmethod
    def get_subgraph(
        self,
        seed_ids: list[str],
        depth: int = 2,
        edge_types: list[str] | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        """Get subgraph via BFS traversal.

        Args:
            seed_ids: Starting node IDs.
            depth: Max traversal depth.
            edge_types: Optional edge type filter.
            as_of: Optional point-in-time filter.

        Returns:
            Dict with ``nodes`` and ``edges`` lists.
        """

    @abstractmethod
    def query(
        self,
        node_type: str | None = None,
        properties: dict[str, Any] | None = None,
        limit: int = 50,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Query nodes by type and/or properties.

        Args:
            node_type: Optional node type filter.
            properties: Optional property filters.
            limit: Max results.
            as_of: Optional point-in-time filter.
        """

    @abstractmethod
    def get_node_history(self, node_id: str) -> list[dict[str, Any]]:
        """Retrieve all versions of a node, ordered by valid_from DESC.

        Returns:
            List of node version dicts, newest first.
        """

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
        """Total current node count (valid_to IS NULL)."""

    @abstractmethod
    def count_edges(self) -> int:
        """Total current edge count (valid_to IS NULL)."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
