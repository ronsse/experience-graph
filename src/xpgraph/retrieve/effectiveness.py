"""Context effectiveness analysis -- measures pack item success correlation."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from xpgraph.stores.base.event_log import EventLog, EventType

logger = structlog.get_logger(__name__)

# Thresholds for classification
_SUCCESS_RATING_THRESHOLD = 0.5
_NOISE_RATE_THRESHOLD = 0.3


class EffectivenessReport:
    """Report on context pack effectiveness."""

    def __init__(
        self,
        total_packs: int,
        total_feedback: int,
        success_rate: float,
        item_scores: list[dict[str, Any]],
        noise_candidates: list[str],
    ) -> None:
        self.total_packs = total_packs
        self.total_feedback = total_feedback
        self.success_rate = success_rate
        self.item_scores = item_scores
        self.noise_candidates = noise_candidates

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_packs": self.total_packs,
            "total_feedback": self.total_feedback,
            "success_rate": self.success_rate,
            "item_scores": self.item_scores,
            "noise_candidates": self.noise_candidates,
        }


def analyze_effectiveness(
    event_log: EventLog,
    *,
    days: int = 30,
    min_appearances: int = 2,
) -> EffectivenessReport:
    """Analyze which injected context items correlate with task success.

    Joins PACK_ASSEMBLED events with FEEDBACK_RECORDED events to compute
    per-item success rates.

    Args:
        event_log: The event log to query.
        days: How many days of history to analyze.
        min_appearances: Minimum times an item must appear to be scored.

    Returns:
        EffectivenessReport with per-item success rates and noise candidates.
    """
    since = datetime.now(tz=UTC) - timedelta(days=days)

    # Get all pack assembly events
    pack_events = event_log.get_events(
        event_type=EventType.PACK_ASSEMBLED,
        since=since,
        limit=1000,
    )

    # Get all feedback events
    feedback_events = event_log.get_events(
        event_type=EventType.FEEDBACK_RECORDED,
        since=since,
        limit=1000,
    )

    # Build pack_id -> injected_item_ids mapping
    pack_items: dict[str, list[str]] = {}
    for event in pack_events:
        pack_id = event.entity_id
        if pack_id:
            pack_items[pack_id] = event.payload.get("injected_item_ids", [])

    # Build pack_id -> feedback mapping
    pack_feedback: dict[str, bool] = {}
    for event in feedback_events:
        pack_id = event.payload.get("pack_id") or event.entity_id
        if pack_id and pack_id in pack_items:
            rating = event.payload.get("rating", 0.0)
            pack_feedback[pack_id] = event.payload.get(
                "success", rating >= _SUCCESS_RATING_THRESHOLD
            )

    # Calculate per-item success rates
    item_successes: dict[str, int] = defaultdict(int)
    item_failures: dict[str, int] = defaultdict(int)
    item_appearances: dict[str, int] = defaultdict(int)

    for pack_id, items in pack_items.items():
        if pack_id not in pack_feedback:
            continue
        success = pack_feedback[pack_id]
        for item_id in items:
            item_appearances[item_id] += 1
            if success:
                item_successes[item_id] += 1
            else:
                item_failures[item_id] += 1

    # Build scored items list
    item_scores: list[dict[str, Any]] = []
    noise_candidates: list[str] = []

    for item_id, count in item_appearances.items():
        if count < min_appearances:
            continue
        successes = item_successes[item_id]
        failures = item_failures[item_id]
        rate = successes / count if count > 0 else 0.0

        item_scores.append({
            "item_id": item_id,
            "appearances": count,
            "successes": successes,
            "failures": failures,
            "success_rate": round(rate, 3),
        })

        # Flag items that appear frequently but correlate with failure
        if rate < _NOISE_RATE_THRESHOLD and count >= min_appearances:
            noise_candidates.append(item_id)

    item_scores.sort(key=lambda x: x["success_rate"], reverse=True)

    # Overall success rate
    total_feedback = len(pack_feedback)
    total_successes = sum(1 for v in pack_feedback.values() if v)
    overall_rate = total_successes / total_feedback if total_feedback > 0 else 0.0

    return EffectivenessReport(
        total_packs=len(pack_events),
        total_feedback=total_feedback,
        success_rate=round(overall_rate, 3),
        item_scores=item_scores,
        noise_candidates=noise_candidates,
    )
