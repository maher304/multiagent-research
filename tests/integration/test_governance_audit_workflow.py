"""Integration tests for the governance -> audit workflow."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from governed_multiagent.audit import AuditLogger, AuditWriteError
from governed_multiagent.contracts import ActionType, DecisionOutcome, PolicyRequest
from governed_multiagent.governance import (
    ExecutionNotPermitted,
    GovernanceService,
    PolicyEngine,
)
from governed_multiagent.governance.policy_engine import (
    POLICY_ACTOR_AUTHORIZATION,
    POLICY_EVIDENCE_REQUIRED,
    POLICY_FINANCIAL_APPROVAL,
    POLICY_READ_ONLY_ANALYSIS,
    POLICY_UNKNOWN_ACTION,
)

FIXED_TIME = datetime(2024, 6, 1, 9, 30, tzinfo=timezone.utc)


@pytest.fixture()
def service(tmp_path):
    engine = PolicyEngine(clock=lambda: FIXED_TIME, decision_id_factory=lambda: "dec-fixed")
    logger = AuditLogger(tmp_path / "audit.jsonl")
    return GovernanceService(engine, logger), logger


def _request(action, actor="research-analyst", evidence=()):
    return PolicyRequest(
        actor=actor,
        action=action,
        resource="olist/orders",
        evidence_refs=evidence,
    )


def test_allowed_analysis_is_decided_and_audited(service):
    governance, logger = service
    request = _request(ActionType.READ_DATA)
    result = governance.evaluate(request)

    assert result.outcome is DecisionOutcome.ALLOW
    assert result.decision.policy_id == POLICY_READ_ONLY_ANALYSIS
    assert result.analysis_permitted is True
    assert result.business_execution_permitted is False

    stored = logger.read_events(request.request_id)
    assert len(stored) == 1
    assert stored[0].event_id == result.audit_event.event_id
    assert stored[0].decision_id == result.decision.decision_id
    assert stored[0].outcome is DecisionOutcome.ALLOW
    assert stored[0].timestamp == FIXED_TIME


def test_blocked_financial_adjustment_is_audited(service):
    governance, logger = service
    request = _request(ActionType.FINANCIAL_ADJUSTMENT, actor="untrusted", evidence=("e1",))
    result = governance.evaluate(request)

    assert result.outcome is DecisionOutcome.BLOCK
    assert result.decision.policy_id == POLICY_ACTOR_AUTHORIZATION
    assert result.business_execution_permitted is False
    with pytest.raises(ExecutionNotPermitted):
        result.assert_business_execution_permitted()

    stored = logger.read_events(request.request_id)
    assert len(stored) == 1
    assert stored[0].outcome is DecisionOutcome.BLOCK


def test_escalated_action_requires_review_and_is_not_executable(service):
    governance, logger = service
    request = _request(ActionType.FINANCIAL_ADJUSTMENT, actor="finance-controller", evidence=("ledger-1",))
    result = governance.evaluate(request)

    assert result.outcome is DecisionOutcome.ESCALATE
    assert result.decision.policy_id == POLICY_FINANCIAL_APPROVAL
    assert result.decision.requires_human_approval is True
    assert result.business_execution_permitted is False
    assert result.analysis_permitted is False
    with pytest.raises(ExecutionNotPermitted):
        result.assert_business_execution_permitted()

    stored = logger.read_events(request.request_id)
    assert len(stored) == 1
    assert stored[0].metadata["requires_human_approval"] is True


def test_missing_evidence_blocks_and_logs(service):
    governance, logger = service
    request = _request(ActionType.FINANCIAL_ADJUSTMENT, actor="finance-controller")
    result = governance.evaluate(request)
    assert result.outcome is DecisionOutcome.BLOCK
    assert result.decision.policy_id == POLICY_EVIDENCE_REQUIRED
    assert len(logger.read_events(request.request_id)) == 1


def test_unknown_action_fails_closed_and_logs(service):
    governance, logger = service
    request = _request("DROP_ALL_TABLES")
    result = governance.evaluate(request)
    assert result.outcome is DecisionOutcome.BLOCK
    assert result.decision.policy_id == POLICY_UNKNOWN_ACTION
    assert len(logger.read_events(request.request_id)) == 1


def test_audit_failure_prevents_a_successful_result(tmp_path):
    engine = PolicyEngine(clock=lambda: FIXED_TIME)
    # A directory cannot be opened as an append target.
    logger = AuditLogger(tmp_path)
    governance = GovernanceService(engine, logger)
    with pytest.raises(AuditWriteError):
        governance.evaluate(_request(ActionType.READ_DATA))


def test_events_from_multiple_requests_are_independently_filterable(service):
    governance, logger = service
    first = _request(ActionType.READ_DATA)
    second = _request(ActionType.PROPOSE_ACTION, evidence=("evidence-1",))
    governance.evaluate(first)
    governance.evaluate(second)

    assert len(logger.read_events()) == 2
    assert len(logger.read_events(first.request_id)) == 1
    assert len(logger.read_events(second.request_id)) == 1
