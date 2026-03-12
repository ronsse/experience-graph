"""GraphStore — abstract interface for graph storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


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
