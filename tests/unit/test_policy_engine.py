"""Unit tests for the deterministic policy engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from governed_multiagent.contracts import ActionType, DecisionOutcome, PolicyRequest
from governed_multiagent.governance import PolicyEngine, PolicyEvaluationError
from governed_multiagent.governance.policy_engine import (
    POLICY_ACTOR_AUTHORIZATION,
    POLICY_CONTRADICTORY_EVIDENCE,
    POLICY_EVIDENCE_REQUIRED,
    POLICY_EXECUTE_APPROVAL,
    POLICY_FINANCIAL_APPROVAL,
    POLICY_PROPOSE_ACTION,
    POLICY_READ_ONLY_ANALYSIS,
    POLICY_UNKNOWN_ACTION,
)

FIXED_TIME = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)


def _engine() -> tuple[PolicyEngine, list[str]]:
    ids: list[str] = []

    def next_id() -> str:
        ids.append(f"dec-{len(ids) + 1}")
        return ids[-1]

    return PolicyEngine(clock=lambda: FIXED_TIME, decision_id_factory=next_id), ids


def _request(action, actor="research-analyst", evidence=(), context=None):
    return PolicyRequest(
        actor=actor,
        action=action,
        resource="olist/orders",
        evidence_refs=evidence,
        context=context or {},
    )


def test_scenario_a_read_only_analysis_allowed():
    engine, _ = _engine()
    decision = engine.evaluate(_request(ActionType.READ_DATA))
    assert decision.outcome is DecisionOutcome.ALLOW
    assert decision.policy_id == POLICY_READ_ONLY_ANALYSIS
    assert decision.requires_human_approval is False
    assert decision.evaluated_at == FIXED_TIME


def test_analyze_data_is_also_allowed():
    engine, _ = _engine()
    decision = engine.evaluate(_request(ActionType.ANALYZE_DATA))
    assert decision.outcome is DecisionOutcome.ALLOW
    assert decision.policy_id == POLICY_READ_ONLY_ANALYSIS


def test_scenario_b_unauthorized_financial_adjustment_blocked():
    engine, _ = _engine()
    decision = engine.evaluate(
        _request(ActionType.FINANCIAL_ADJUSTMENT, actor="untrusted-actor", evidence=("e1",))
    )
    assert decision.outcome is DecisionOutcome.BLOCK
    assert decision.policy_id == POLICY_ACTOR_AUTHORIZATION


def test_unknown_actor_cannot_read_data():
    engine, _ = _engine()
    decision = engine.evaluate(_request(ActionType.READ_DATA, actor="intruder"))
    assert decision.outcome is DecisionOutcome.BLOCK
    assert decision.policy_id == POLICY_ACTOR_AUTHORIZATION


def test_scenario_c_sensitive_action_escalates_for_human_approval():
    engine, _ = _engine()
    decision = engine.evaluate(_request(ActionType.EXECUTE_ACTION, evidence=("e1",)))
    assert decision.outcome is DecisionOutcome.ESCALATE
    assert decision.policy_id == POLICY_EXECUTE_APPROVAL
    assert decision.requires_human_approval is True


def test_financial_adjustment_with_authorization_and_evidence_escalates_only():
    engine, _ = _engine()
    decision = engine.evaluate(
        _request(ActionType.FINANCIAL_ADJUSTMENT, actor="finance-controller", evidence=("ledger-ref",))
    )
    assert decision.outcome is DecisionOutcome.ESCALATE
    assert decision.policy_id == POLICY_FINANCIAL_APPROVAL
    assert decision.requires_human_approval is True


def test_financial_adjustment_is_never_allowed():
    engine, _ = _engine()
    for actor in ("research-analyst", "finance-controller", "auditor"):
        decision = engine.evaluate(
            _request(ActionType.FINANCIAL_ADJUSTMENT, actor=actor, evidence=("e1",))
        )
        assert decision.outcome is not DecisionOutcome.ALLOW


def test_scenario_d_unknown_action_is_blocked():
    engine, _ = _engine()
    decision = engine.evaluate(_request("DELETE_LEDGER"))
    assert decision.outcome is DecisionOutcome.BLOCK
    assert decision.policy_id == POLICY_UNKNOWN_ACTION
    assert "Unsupported action" in decision.reason


def test_scenario_e_missing_evidence_blocks():
    engine, _ = _engine()
    decision = engine.evaluate(_request(ActionType.FINANCIAL_ADJUSTMENT, actor="finance-controller"))
    assert decision.outcome is DecisionOutcome.BLOCK
    assert decision.policy_id == POLICY_EVIDENCE_REQUIRED


def test_propose_action_requires_evidence_and_is_not_execution():
    engine, _ = _engine()
    blocked = engine.evaluate(_request(ActionType.PROPOSE_ACTION))
    assert blocked.outcome is DecisionOutcome.BLOCK
    assert blocked.policy_id == POLICY_EVIDENCE_REQUIRED

    allowed = engine.evaluate(_request(ActionType.PROPOSE_ACTION, evidence=("analysis-1",)))
    assert allowed.outcome is DecisionOutcome.ALLOW
    assert allowed.policy_id == POLICY_PROPOSE_ACTION
    assert "not authorisation to execute" in allowed.reason
    assert allowed.requires_human_approval is False


def test_contradictory_evidence_blocks_even_read_only_action():
    engine, _ = _engine()
    decision = engine.evaluate(_request(ActionType.READ_DATA, context={"evidence_conflict": True}))
    assert decision.outcome is DecisionOutcome.BLOCK
    assert decision.policy_id == POLICY_CONTRADICTORY_EVIDENCE


def test_decisions_are_deterministic_with_injected_clock_and_ids():
    engine, ids = _engine()
    request = _request(ActionType.READ_DATA)
    first = engine.evaluate(request)
    second = engine.evaluate(request)
    assert first.decision_id == "dec-1"
    assert second.decision_id == "dec-2"
    assert ids == ["dec-1", "dec-2"]
    assert first.evaluated_at == second.evaluated_at == FIXED_TIME


def test_engine_rejects_untyped_input():
    engine, _ = _engine()
    with pytest.raises(PolicyEvaluationError):
        engine.evaluate({"action": "READ_DATA"})  # type: ignore[arg-type]


def test_engine_does_not_mutate_or_execute_request():
    engine, _ = _engine()
    request = _request(ActionType.EXECUTE_ACTION, evidence=("e1",))
    before = request.to_dict()
    engine.evaluate(request)
    assert request.to_dict() == before
