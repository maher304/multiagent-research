"""Unit tests for the append-only JSON Lines audit logger."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from governed_multiagent.audit import AuditLogger, AuditReadError, AuditWriteError
from governed_multiagent.contracts import AuditEvent, AuditEventType, DecisionOutcome


def _event(request_id: str = "req-1", event_id: str | None = None) -> AuditEvent:
    kwargs = {"event_id": event_id} if event_id else {}
    return AuditEvent(
        correlation_id=request_id,
        event_type=AuditEventType.POLICY_DECISION,
        actor="auditor",
        action="READ_DATA",
        outcome=DecisionOutcome.ALLOW,
        reason="allowed",
        policy_id="POL-READ-ANALYSIS-v1",
        decision_id="dec-1",
        metadata={"resource": "olist/orders"},
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        **kwargs,
    )


def test_append_and_read_event(tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    event = _event()
    logger.append_event(event)

    stored = logger.read_events()
    assert len(stored) == 1
    assert stored[0].to_dict() == event.to_dict()
    assert stored[0].timestamp.tzinfo is timezone.utc
    assert not (tmp_path / "audit.jsonl.lock").exists()


def test_read_filters_by_request_id(tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    logger.append_event(_event("req-a"))
    logger.append_event(_event("req-b"))
    logger.append_event(_event("req-a"))

    assert len(logger.read_events()) == 3
    assert len(logger.read_events("req-a")) == 2
    assert len(logger.read_events("req-b")) == 1
    assert logger.read_events("missing") == []


def test_previous_events_are_preserved_on_append(tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    logger.append_event(_event("req-1", event_id="evt-1"))
    first_content = logger.path.read_text(encoding="utf-8")
    logger.append_event(_event("req-2", event_id="evt-2"))
    second_content = logger.path.read_text(encoding="utf-8")

    assert second_content.startswith(first_content)
    assert len(second_content.splitlines()) == 2
    assert [event.event_id for event in logger.read_events()] == ["evt-1", "evt-2"]


def test_malformed_line_raises_clear_read_error(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"not": "an event"}\n', encoding="utf-8")
    logger = AuditLogger(path)
    with pytest.raises(AuditReadError) as excinfo:
        logger.read_events()
    assert "audit.jsonl:1" in str(excinfo.value)


def test_unwritable_destination_raises_write_error(tmp_path):
    logger = AuditLogger(tmp_path)  # a directory is not a writable file
    with pytest.raises(AuditWriteError):
        logger.append_event(_event())


def test_append_rejects_non_event(tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl")
    with pytest.raises(AuditWriteError):
        logger.append_event({"event": "not typed"})  # type: ignore[arg-type]


def test_missing_file_reads_as_empty(tmp_path):
    logger = AuditLogger(tmp_path / "does-not-exist.jsonl")
    assert logger.read_events() == []


def test_concurrent_appends_are_not_interleaved(tmp_path):
    logger = AuditLogger(tmp_path / "audit.jsonl", lock_timeout=5.0)

    def write(index: int) -> None:
        logger.append_event(_event(f"req-{index}", event_id=f"evt-{index}"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(20)))

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    for line in lines:
        payload = json.loads(line)
        assert payload["event_id"].startswith("evt-")
        assert "correlation_id" in payload
    assert len(logger.read_events()) == 20
