"""Maintenance workers — retention pruning, staleness detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from pydantic import Field

from xpgraph.core.base import XPModel, utc_now
from xpgraph.stores.event_log import EventType

logger = structlog.get_logger(__name__)


class RetentionPolicy(XPModel):
    """Configuration for retention pruning."""

    max_age_days: int = 365
    max_traces: int = 10000
    preserve_outcomes: list[str] = Field(
        default_factory=lambda: ["success"],
    )
    dry_run: bool = False


class RetentionReport(XPModel):
    """Report of a retention pruning run."""

    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    traces_scanned: int = 0
    traces_pruned: int = 0
    traces_preserved: int = 0
    dry_run: bool = False
    errors: list[str] = Field(default_factory=list)


class RetentionWorker:
    """Prunes old traces based on retention policy.

    Retention rules:
    - Traces older than max_age_days are candidates for pruning
    - Traces with outcomes in preserve_outcomes are kept regardless
    - Pruning emits events for audit trail
    """

    def __init__(
        self,
        trace_store: Any,  # TraceStore
        event_log: Any | None = None,  # EventLog
    ) -> None:
        self._trace_store = trace_store
        self._event_log = event_log

    def run(self, policy: RetentionPolicy) -> RetentionReport:
        """Execute retention pruning based on policy.

        Args:
            policy: Retention policy configuration.

        Returns:
            RetentionReport with results.
        """
        report = RetentionReport(dry_run=policy.dry_run)
        cutoff = utc_now() - timedelta(days=policy.max_age_days)

        # Query old traces
        old_traces = self._trace_store.query(until=cutoff, limit=policy.max_traces)
        report.traces_scanned = len(old_traces)

        for trace in old_traces:
            # Check if trace should be preserved
            if trace.outcome and trace.outcome.status.value in policy.preserve_outcomes:
                report.traces_preserved += 1
                continue

            if not policy.dry_run:
                try:
                    # TraceStore is append-only, so "pruning" = marking in event log
                    # Real deletion would need store support
                    if self._event_log is not None:
                        self._event_log.emit(
                            EventType.MUTATION_EXECUTED,
                            source="retention_worker",
                            entity_id=trace.trace_id,
                            entity_type="trace",
                            payload={
                                "action": "retention_prune",
                                "reason": f"older than {policy.max_age_days} days",
                                "outcome_status": (
                                    trace.outcome.status.value
                                    if trace.outcome
                                    else "none"
                                ),
                            },
                        )
                except Exception as e:
                    report.errors.append(f"Error pruning {trace.trace_id}: {e}")
                    continue

            report.traces_pruned += 1

        report.completed_at = utc_now()

        logger.info(
            "retention_run_complete",
            scanned=report.traces_scanned,
            pruned=report.traces_pruned,
            preserved=report.traces_preserved,
            dry_run=policy.dry_run,
        )

        return report


class StalenessReport(XPModel):
    """Report of a staleness detection run."""

    checked_at: datetime = Field(default_factory=utc_now)
    total_documents: int = 0
    stale_documents: list[str] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)


class StalenessDetector:
    """Detects stale documents in the document store.

    A document is considered stale if:
    - It references a URI/path that no longer exists
    - It hasn't been updated within the staleness threshold
    """

    def __init__(
        self,
        document_store: Any,  # DocumentStore
        staleness_days: int = 90,
    ) -> None:
        self._document_store = document_store
        self._staleness_days = staleness_days

    def check(self) -> StalenessReport:
        """Check for stale documents.

        Returns:
            StalenessReport with findings.
        """
        report = StalenessReport()
        cutoff = utc_now() - timedelta(days=self._staleness_days)

        all_docs = self._document_store.list_documents(limit=10000)
        report.total_documents = len(all_docs)

        for doc in all_docs:
            doc_data = self._document_store.get(doc["doc_id"])
            if doc_data is None:
                report.missing_documents.append(doc["doc_id"])
                continue

            # Check updated_at
            updated_str = doc_data.get("updated_at")
            if updated_str:
                try:
                    updated_at = datetime.fromisoformat(updated_str)
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=UTC)
                    if updated_at < cutoff:
                        report.stale_documents.append(doc_data["doc_id"])
                except (ValueError, TypeError):
                    pass

        logger.info(
            "staleness_check_complete",
            total=report.total_documents,
            stale=len(report.stale_documents),
            missing=len(report.missing_documents),
        )

        return report
