"""Coordination of policy evaluation and audit recording.

The service keeps three concepts separate and explicit:

* **Evaluation** happens in :class:`PolicyEngine` and produces a decision.
* **Authorisation** is the decision itself (:meth:`GovernanceService.evaluate`).
* **Execution** is outside this package. No business, payment, or ledger action
  is performed here. :class:`GovernanceResult` exposes guards callers must use
  before attempting an action in a future implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from governed_multiagent.audit.audit_logger import AuditLogger
from governed_multiagent.contracts.audit_events import AuditEvent
from governed_multiagent.contracts.decisions import DecisionOutcome, PolicyDecision
from governed_multiagent.contracts.requests import ActionType, PolicyRequest
from governed_multiagent.governance.policy_engine import PolicyEngine


class GovernanceError(RuntimeError):
    """Raised for invalid governance usage."""


class ExecutionNotPermitted(PermissionError):
    """Raised when a caller attempts an action the governance layer did not clear."""


@dataclass(frozen=True, slots=True)
class GovernanceResult:
    """A policy decision together with the audit record that proves it was logged."""

    request: PolicyRequest
    decision: PolicyDecision
    audit_event: AuditEvent

    @property
    def outcome(self) -> DecisionOutcome | str:
        return self.decision.outcome

    @property
    def analysis_permitted(self) -> bool:
        """True when a read-only analysis action may proceed."""

        return (
            self.decision.outcome is DecisionOutcome.ALLOW
            and self.request.action in (ActionType.READ_DATA, ActionType.ANALYZE_DATA)
        )

    @property
    def recommendation_permitted(self) -> bool:
        """True when a recommendation may be recorded (still not execution)."""

        return self.decision.outcome is DecisionOutcome.ALLOW and self.request.action is ActionType.PROPOSE_ACTION

    @property
    def business_execution_permitted(self) -> bool:
        """True only for an explicit ALLOW on an execution action.

        The default policy never auto-allows ``EXECUTE_ACTION`` or
        ``FINANCIAL_ADJUSTMENT``, so this is normally False.
        """

        return self.decision.outcome is DecisionOutcome.ALLOW and self.request.action in (
            ActionType.EXECUTE_ACTION,
            ActionType.FINANCIAL_ADJUSTMENT,
        )

    def assert_business_execution_permitted(self) -> None:
        if not self.business_execution_permitted:
            raise ExecutionNotPermitted(
                f"Request {self.request.request_id} is not authorised for business execution "
                f"(outcome={self.decision.outcome_name}, action={self.request.action_name})."
            )


class GovernanceService:
    """Evaluate a request and persist the corresponding audit event.

    If the audit event cannot be persisted, the exception propagates and **no
    result is returned**. A decision is thus never reported as successfully
    audited when it was not.
    """

    def __init__(self, engine: PolicyEngine, audit_logger: AuditLogger) -> None:
        if not isinstance(engine, PolicyEngine):
            raise GovernanceError("engine must be a PolicyEngine")
        if not isinstance(audit_logger, AuditLogger):
            raise GovernanceError("audit_logger must be an AuditLogger")
        self._engine = engine
        self._audit = audit_logger

    @property
    def engine(self) -> PolicyEngine:
        return self._engine

    @property
    def audit_logger(self) -> AuditLogger:
        return self._audit

    def evaluate(self, request: PolicyRequest) -> GovernanceResult:
        """Evaluate ``request``, audit the decision, and return the result."""

        if not isinstance(request, PolicyRequest):
            raise GovernanceError("evaluate() requires a validated PolicyRequest")

        decision = self._engine.evaluate(request)
        event = AuditEvent.for_decision(request, decision)
        # Deliberately no broad except: an audit failure must not be swallowed.
        self._audit.append_event(event)
        return GovernanceResult(request=request, decision=decision, audit_event=event)
