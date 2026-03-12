"""Store registry — dependency injection for store backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from xpgraph.stores.base import (
    BlobStore,
    DocumentStore,
    EventLog,
    GraphStore,
    TraceStore,
    VectorStore,
)

logger = structlog.get_logger(__name__)

# Backend name -> (module_path, class_name)
_BUILTIN_BACKENDS: dict[str, dict[str, tuple[str, str]]] = {
    "trace": {
        "sqlite": ("xpgraph.stores.sqlite.trace", "SQLiteTraceStore"),
        "postgres": ("xpgraph.stores.postgres.trace", "PostgresTraceStore"),
    },
    "document": {
        "sqlite": ("xpgraph.stores.sqlite.document", "SQLiteDocumentStore"),
        "postgres": ("xpgraph.stores.postgres.document", "PostgresDocumentStore"),
    },
    "graph": {
        "sqlite": ("xpgraph.stores.sqlite.graph", "SQLiteGraphStore"),
        "postgres": ("xpgraph.stores.postgres.graph", "PostgresGraphStore"),
    },
    "vector": {
        "sqlite": ("xpgraph.stores.sqlite.vector", "SQLiteVectorStore"),
        "pgvector": ("xpgraph.stores.pgvector.store", "PgVectorStore"),
        "lancedb": ("xpgraph.stores.lancedb.store", "LanceVectorStore"),
    },
    "event_log": {
        "sqlite": ("xpgraph.stores.sqlite.event_log", "SQLiteEventLog"),
        "postgres": ("xpgraph.stores.postgres.event_log", "PostgresEventLog"),
    },
    "blob": {
        "local": ("xpgraph.stores.local.blob", "LocalBlobStore"),
        "s3": ("xpgraph.stores.s3.blob", "S3BlobStore"),
    },
}


class StoreRegistry:
    """Lazily instantiates and caches store backends based on configuration."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        stores_dir: Path | None = None,
    ) -> None:
        self._config = config or {}
        self._stores_dir = stores_dir
        self._cache: dict[str, Any] = {}

    @classmethod
    def from_config_dir(
        cls,
        config_dir: Path | None = None,
        data_dir: Path | None = None,
    ) -> StoreRegistry:
        """Create a registry from XPG config directory."""
        import os  # noqa: PLC0415

        if config_dir is None:
            config_dir = Path(
                os.environ.get("XPG_CONFIG_DIR", str(Path.home() / ".xpg"))
            )
        if data_dir is None:
            data_dir = Path(
                os.environ.get("XPG_DATA_DIR", str(config_dir / "data"))
            )

        # Try to load store config from config.yaml
        store_config: dict[str, Any] = {}
        config_path = config_dir / "config.yaml"
        if config_path.exists():
            try:
                import yaml  # noqa: PLC0415

                data = yaml.safe_load(config_path.read_text()) or {}
                store_config = data.get("stores", {})
                if data.get("data_dir"):
                    data_dir = Path(data["data_dir"])
            except Exception:
                logger.warning(
                    "registry_config_load_failed", path=str(config_path)
                )

        stores_dir = data_dir / "stores"
        return cls(config=store_config, stores_dir=stores_dir)

    def _resolve_backend(self, store_type: str) -> tuple[str, dict[str, Any]]:
        """Resolve backend name and params for a store type."""
        store_cfg = self._config.get(store_type, {})
        if isinstance(store_cfg, str):
            return store_cfg, {}
        backend = store_cfg.get("backend", self._default_backend(store_type))
        params = {k: v for k, v in store_cfg.items() if k != "backend"}
        return backend, params

    @staticmethod
    def _default_backend(store_type: str) -> str:
        """Return the default backend for a store type."""
        if store_type == "blob":
            return "local"
        return "sqlite"

    def _instantiate(self, store_type: str) -> Any:
        """Create a store instance from config."""
        backend, params = self._resolve_backend(store_type)

        registry = _BUILTIN_BACKENDS.get(store_type, {})
        if backend not in registry:
            msg = f"Unknown backend '{backend}' for store type '{store_type}'"
            raise ValueError(msg)

        module_path, class_name = registry[backend]

        import importlib  # noqa: PLC0415

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        # For sqlite backends, default to stores_dir/<type>.db
        if backend == "sqlite" and "db_path" not in params:
            if self._stores_dir is None:
                msg = (
                    "stores_dir must be set for sqlite backends"
                    " without explicit db_path"
                )
                raise ValueError(msg)
            self._stores_dir.mkdir(parents=True, exist_ok=True)
            db_names = {
                "trace": "traces.db",
                "document": "documents.db",
                "graph": "graph.db",
                "vector": "vectors.db",
                "event_log": "events.db",
            }
            params["db_path"] = self._stores_dir / db_names[store_type]

        # For lancedb backend, default to stores_dir/lancedb/
        if backend == "lancedb" and "uri" not in params:
            if self._stores_dir is None:
                msg = (
                    "stores_dir must be set for lancedb backend"
                    " without explicit uri"
                )
                raise ValueError(msg)
            self._stores_dir.mkdir(parents=True, exist_ok=True)
            params["uri"] = str(self._stores_dir / "lancedb")

        # For local blob backend, default to stores_dir/blobs/
        if backend == "local" and "root_dir" not in params:
            if self._stores_dir is None:
                msg = (
                    "stores_dir must be set for local blob backend"
                    " without explicit root_dir"
                )
                raise ValueError(msg)
            params["root_dir"] = self._stores_dir / "blobs"

        # For postgres backends, default DSN from env
        if backend == "postgres" and "dsn" not in params:
            import os  # noqa: PLC0415

            dsn = os.environ.get("XPG_PG_DSN")
            if not dsn:
                msg = (
                    "dsn must be set for postgres backends"
                    " (config or XPG_PG_DSN env var)"
                )
                raise ValueError(msg)
            params["dsn"] = dsn

        # For pgvector backend, default DSN from env
        if backend == "pgvector" and "dsn" not in params:
            import os  # noqa: PLC0415

            dsn = os.environ.get("XPG_PG_DSN")
            if not dsn:
                msg = (
                    "dsn must be set for pgvector backend"
                    " (config or XPG_PG_DSN env var)"
                )
                raise ValueError(msg)
            params["dsn"] = dsn

        # For s3 backend, default bucket from env
        if backend == "s3" and "bucket" not in params:
            import os  # noqa: PLC0415

            bucket = os.environ.get("XPG_S3_BUCKET")
            if not bucket:
                msg = (
                    "bucket must be set for s3 backend"
                    " (config or XPG_S3_BUCKET env var)"
                )
                raise ValueError(msg)
            params["bucket"] = bucket

        logger.info("store_instantiated", store_type=store_type, backend=backend)
        return cls(**params)

    def _get(self, store_type: str) -> Any:
        if store_type not in self._cache:
            self._cache[store_type] = self._instantiate(store_type)
        return self._cache[store_type]

    @property
    def trace_store(self) -> TraceStore:
        return self._get("trace")

    @property
    def document_store(self) -> DocumentStore:
        return self._get("document")

    @property
    def graph_store(self) -> GraphStore:
        return self._get("graph")

    @property
    def vector_store(self) -> VectorStore:
        return self._get("vector")

    @property
    def event_log(self) -> EventLog:
        return self._get("event_log")

    @property
    def blob_store(self) -> BlobStore:
        return self._get("blob")

    def close(self) -> None:
        """Close all cached stores."""
        for store in self._cache.values():
            try:
                store.close()
            except Exception:
                logger.warning("store_close_failed", store=type(store).__name__)
        self._cache.clear()
