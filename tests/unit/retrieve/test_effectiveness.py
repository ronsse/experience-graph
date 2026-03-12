"""Tests for context effectiveness analysis."""
from __future__ import annotations

from pathlib import Path

import pytest

from xpgraph.retrieve.effectiveness import analyze_effectiveness
from xpgraph.stores.base.event_log import EventType
from xpgraph.stores.sqlite.event_log import SQLiteEventLog


@pytest.fixture
def event_log(tmp_path: Path):
    log = SQLiteEventLog(tmp_path / "events.db")
    yield log
    log.close()


def test_empty_analysis(event_log):
    report = analyze_effectiveness(event_log, days=30)
    assert report.total_packs == 0
    assert report.total_feedback == 0
    assert report.success_rate == 0.0
    assert report.item_scores == []
    assert report.noise_candidates == []


def test_packs_without_feedback(event_log):
    event_log.emit(
        EventType.PACK_ASSEMBLED,
        source="test",
        entity_id="pack-1",
        entity_type="pack",
        payload={"injected_item_ids": ["item-a", "item-b"]},
    )
    report = analyze_effectiveness(event_log, days=30)
    assert report.total_packs == 1
    assert report.total_feedback == 0


def test_effectiveness_with_feedback(event_log):
    # Pack 1 with items a, b - successful
    event_log.emit(
        EventType.PACK_ASSEMBLED,
        source="test",
        entity_id="pack-1",
        entity_type="pack",
        payload={"injected_item_ids": ["item-a", "item-b"]},
    )
    event_log.emit(
        EventType.FEEDBACK_RECORDED,
        source="test",
        entity_id="pack-1",
        entity_type="pack",
        payload={"pack_id": "pack-1", "success": True},
    )

    # Pack 2 with items a, c - failed
    event_log.emit(
        EventType.PACK_ASSEMBLED,
        source="test",
        entity_id="pack-2",
        entity_type="pack",
        payload={"injected_item_ids": ["item-a", "item-c"]},
    )
    event_log.emit(
        EventType.FEEDBACK_RECORDED,
        source="test",
        entity_id="pack-2",
        entity_type="pack",
        payload={"pack_id": "pack-2", "success": False},
    )

    report = analyze_effectiveness(event_log, days=30, min_appearances=1)
    assert report.total_packs == 2
    assert report.total_feedback == 2
    assert report.success_rate == 0.5

    # item-a appears in both packs: 1 success, 1 failure = 50%
    item_a = next(i for i in report.item_scores if i["item_id"] == "item-a")
    assert item_a["appearances"] == 2
    assert item_a["success_rate"] == 0.5

    # item-b only in successful pack
    item_b = next(i for i in report.item_scores if i["item_id"] == "item-b")
    assert item_b["success_rate"] == 1.0

    # item-c only in failed pack
    item_c = next(i for i in report.item_scores if i["item_id"] == "item-c")
    assert item_c["success_rate"] == 0.0


def test_noise_candidates(event_log):
    # Create 3 packs all with item-noise, all failed
    for i in range(3):
        pack_id = f"pack-{i}"
        event_log.emit(
            EventType.PACK_ASSEMBLED,
            source="test",
            entity_id=pack_id,
            entity_type="pack",
            payload={"injected_item_ids": ["item-noise"]},
        )
        event_log.emit(
            EventType.FEEDBACK_RECORDED,
            source="test",
            entity_id=pack_id,
            entity_type="pack",
            payload={"pack_id": pack_id, "success": False},
        )

    report = analyze_effectiveness(event_log, days=30, min_appearances=2)
    assert "item-noise" in report.noise_candidates


def test_to_dict(event_log):
    report = analyze_effectiveness(event_log, days=30)
    d = report.to_dict()
    assert "total_packs" in d
    assert "total_feedback" in d
    assert "success_rate" in d
    assert "item_scores" in d
    assert "noise_candidates" in d


def test_min_appearances_filter(event_log):
    # One pack with item-rare, one feedback
    event_log.emit(
        EventType.PACK_ASSEMBLED,
        source="test",
        entity_id="pack-1",
        entity_type="pack",
        payload={"injected_item_ids": ["item-rare"]},
    )
    event_log.emit(
        EventType.FEEDBACK_RECORDED,
        source="test",
        entity_id="pack-1",
        entity_type="pack",
        payload={"pack_id": "pack-1", "success": True},
    )

    # min_appearances=2 should filter out item-rare (only 1 appearance)
    report = analyze_effectiveness(event_log, days=30, min_appearances=2)
    assert len(report.item_scores) == 0

    # min_appearances=1 should include it
    report = analyze_effectiveness(event_log, days=30, min_appearances=1)
    assert len(report.item_scores) == 1
