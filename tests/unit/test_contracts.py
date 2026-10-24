"""Unit tests for the typed governance contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from governed_multiagent.contracts import (
    ActionType,
    AuditEvent,
    AuditEventType,
    DecisionOutcome,
    PolicyContractError,
    PolicyDecision,
    PolicyRequest,
    canonical_json,
)


def test_policy_request_defaults_and_normalisation():
    request = PolicyRequest(actor="research-analyst", action="read_data", resource="olist/orders")
    assert request.action is ActionType.READ_DATA
    assert request.timestamp.tzinfo is timezone.utc
    assert request.request_id
    assert request.evidence_refs == ()
    assert request.context == {}


def test_policy_request_keeps_unknown_action_for_engine_to_block():
    request = PolicyRequest(actor="research-analyst", action="DELETE_LEDGER", resource="ledger")
    assert request.is_known_action is False
    assert request.action_name == "DELETE_LEDGER"


def test_policy_request_rejects_invalid_fields():
    with pytest.raises(PolicyContractError):
        PolicyRequest(actor="   ", action=ActionType.READ_DATA, resource="x")
    with pytest.raises(PolicyContractError):
        PolicyRequest(actor="a", action=ActionType.READ_DATA, resource="")
    with pytest.raises(PolicyContractError):
        PolicyRequest(
            actor="a",
            action=ActionType.READ_DATA,
            resource="x",
            timestamp=datetime(2024, 1, 1),
        )
    with pytest.raises(PolicyContractError):
        PolicyRequest(actor="a", action=ActionType.READ_DATA, resource="x", evidence_refs=("",))
    with pytest.raises(PolicyContractError):
        PolicyRequest(
            actor="a",
            action=ActionType.READ_DATA,
            resource="x",
            context={"when": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        )


def test_policy_request_roundtrip():
    request = PolicyRequest(
        actor="finance-controller",
        action=ActionType.FINANCIAL_ADJUSTMENT,
        resource="ledger/accounts/1",
        context={"amount": 10.5},
        evidence_refs=("doc-1",),
    )
    restored = PolicyRequest.from_dict(request.to_dict())
    assert restored.to_dict() == request.to_dict()


def test_policy_request_from_dict_normalises_single_string_evidence():
    payload = {
        "request_id": "req-1",
        "actor": "research-analyst",
        "action": "READ_DATA",
        "resource": "olist/orders",
        "context": {},
        "evidence_refs": "doc-1",
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    request = PolicyRequest.from_dict(payload)
    assert request.evidence_refs == ("doc-1",)

    payload["evidence_refs"] = None
    assert PolicyRequest.from_dict(payload).evidence_refs == ()


def test_decision_requires_valid_outcome_and_escalation_approval():
    allowed = PolicyDecision(request_id="r1", outcome=DecisionOutcome.ALLOW, reason="ok")
    assert allowed.requires_human_approval is False
    assert allowed.evaluated_at.tzinfo is timezone.utc

    with pytest.raises(PolicyContractError):
        PolicyDecision(request_id="r1", outcome="MAYBE", reason="bad")
    with pytest.raises(PolicyContractError):
        PolicyDecision(request_id="r1", outcome=DecisionOutcome.ESCALATE, reason="review")
    escalated = PolicyDecision(
        request_id="r1",
        outcome=DecisionOutcome.ESCALATE,
        reason="review",
        requires_human_approval=True,
    )
    assert escalated.outcome is DecisionOutcome.ESCALATE


def test_audit_event_serialisation_is_deterministic_and_roundtrips():
    event = AuditEvent(
        correlation_id="req-1",
        event_type=AuditEventType.POLICY_DECISION,
        actor="auditor",
        action="READ_DATA",
        outcome=DecisionOutcome.ALLOW,
        reason="ok",
        policy_id="POL-1",
        decision_id="dec-1",
        metadata={"b": 2, "a": 1},
        event_id="evt-1",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    line = event.to_json_line()
    assert "\n" not in line
    assert line == canonical_json(event.to_dict())
    restored = AuditEvent.from_json_line(line)
    assert restored.to_dict() == event.to_dict()
    assert restored.timestamp.tzinfo is timezone.utc


def test_audit_event_rejects_credentials_and_bulk_rows():
    with pytest.raises(PolicyContractError):
        AuditEvent(
            correlation_id="req-1",
            event_type="POLICY_DECISION",
            actor="a",
            action="READ_DATA",
            outcome="ALLOW",
            reason="ok",
            metadata={"api_key": "not-a-real-key"},
        )
    with pytest.raises(PolicyContractError):
        AuditEvent(
            correlation_id="req-1",
            event_type="POLICY_DECISION",
            actor="a",
            action="READ_DATA",
            outcome="ALLOW",
            reason="ok",
            metadata={"raw_row": {"order_id": "x"}},
        )
    with pytest.raises(PolicyContractError):
        AuditEvent(
            correlation_id="req-1",
            event_type="POLICY_DECISION",
            actor="a",
            action="READ_DATA",
            outcome="ALLOW",
            reason="ok",
            metadata={"bad": object()},
        )


def test_audit_event_for_decision_links_request_and_decision():
    request = PolicyRequest(
        actor="research-analyst",
        action=ActionType.READ_DATA,
        resource="olist/orders",
        evidence_refs=("evidence-1",),
    )
    decision = PolicyDecision(
        request_id=request.request_id,
        outcome=DecisionOutcome.ALLOW,
        reason="ok",
        policy_id="POL-READ-ANALYSIS-v1",
    )
    event = AuditEvent.for_decision(request, decision)
    assert event.correlation_id == request.request_id
    assert event.decision_id == decision.decision_id
    assert event.outcome is DecisionOutcome.ALLOW
    assert event.timestamp == decision.evaluated_at
    assert event.metadata["evidence_refs"] == ["evidence-1"]
    assert event.metadata["resource"] == "olist/orders"
