"""Deterministic, fail-closed policy engine.

The engine answers one question: *may this request proceed under the configured
prototype policy?* It never performs the business action. It returns ALLOW,
BLOCK, or ESCALATE with a reason and a policy identifier.

Default policy rules (documented and versioned here so they can be reviewed and
later replaced by a real authorization system):

1. Only configured actors may submit requests. Unknown actors are blocked.
2. READ_DATA and ANALYZE_DATA are allowed for authorised actors. They are
   read-only analysis, not business execution.
3. PROPOSE_ACTION is allowed for authorised actors **only when evidence
   references are supplied**. A recommendation is not execution authority.
4. EXECUTE_ACTION requires evidence and is escalated for human approval. The
   prototype has no approval mechanism, so it is never auto-allowed.
5. FINANCIAL_ADJUSTMENT requires evidence and is escalated for human approval.
   It is never auto-allowed and never executed by this package.
6. Explicit evidence conflict blocks the request.
7. Unknown or unsupported actions are blocked (fail closed).
8. Missing evidence for an evidence-required action is blocked.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from governed_multiagent.contracts.common import utc_now
from governed_multiagent.contracts.decisions import DecisionOutcome, PolicyDecision
from governed_multiagent.contracts.requests import ActionType, PolicyRequest

# Policy identifiers are stable strings so audit records can be traced back to
# a documented rule.
POLICY_ACTOR_AUTHORIZATION = "POL-ACTOR-AUTH-v1"
POLICY_READ_ONLY_ANALYSIS = "POL-READ-ANALYSIS-v1"
POLICY_PROPOSE_ACTION = "POL-PROPOSE-v1"
POLICY_EVIDENCE_REQUIRED = "POL-EVIDENCE-v1"
POLICY_CONTRADICTORY_EVIDENCE = "POL-EVIDENCE-CONFLICT-v1"
POLICY_EXECUTE_APPROVAL = "POL-EXECUTE-APPROVAL-v1"
POLICY_FINANCIAL_APPROVAL = "POL-FINANCIAL-APPROVAL-v1"
POLICY_UNKNOWN_ACTION = "POL-UNKNOWN-ACTION-v1"


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    """Small, explicit prototype policy configuration.

    Actor names are role labels used by the research prototype; they are not
    real user identities or production permissions.
    """

    allowed_actors: frozenset[str] = field(
        default_factory=lambda: frozenset({"research-analyst", "finance-controller", "auditor"})
    )
    read_only_actions: frozenset[ActionType] = field(
        default_factory=lambda: frozenset({ActionType.READ_DATA, ActionType.ANALYZE_DATA})
    )
    evidence_required_actions: frozenset[ActionType] = field(
        default_factory=lambda: frozenset(
            {ActionType.PROPOSE_ACTION, ActionType.EXECUTE_ACTION, ActionType.FINANCIAL_ADJUSTMENT}
        )
    )
    policy_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.allowed_actors:
            raise ValueError("allowed_actors must not be empty")
        for actor in self.allowed_actors:
            if not isinstance(actor, str) or not actor.strip():
                raise ValueError("allowed_actors must contain non-empty strings")
        if not self.read_only_actions <= set(ActionType):
            raise ValueError("read_only_actions must contain known ActionType values")
        if not self.evidence_required_actions <= set(ActionType):
            raise ValueError("evidence_required_actions must contain known ActionType values")


DEFAULT_POLICY_CONFIG = PolicyConfig()


class PolicyEvaluationError(RuntimeError):
    """Raised when the engine is asked to evaluate something that is not a request."""


class PolicyEngine:
    """Evaluate :class:`PolicyRequest` objects against :class:`PolicyConfig`."""

    def __init__(
        self,
        config: PolicyConfig | None = None,
        *,
        clock: Callable[[], datetime] = utc_now,
        decision_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._config = config or DEFAULT_POLICY_CONFIG
        self._clock = clock
        self._decision_id_factory = decision_id_factory or (lambda: uuid.uuid4().hex)

    @property
    def config(self) -> PolicyConfig:
        return self._config

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Return a decision for ``request`` without executing any action."""

        if not isinstance(request, PolicyRequest):
            raise PolicyEvaluationError("evaluate() requires a validated PolicyRequest")

        action = request.action
        if not isinstance(action, ActionType):
            return self._decide(
                request,
                DecisionOutcome.BLOCK,
                f"Unsupported action '{action}'; governance fails closed.",
                POLICY_UNKNOWN_ACTION,
                metadata={"action": str(action)},
            )

        if request.actor not in self._config.allowed_actors:
            return self._decide(
                request,
                DecisionOutcome.BLOCK,
                f"Actor '{request.actor}' is not authorised under the prototype policy.",
                POLICY_ACTOR_AUTHORIZATION,
            )

        if request.context.get("evidence_conflict") is True:
            return self._decide(
                request,
                DecisionOutcome.BLOCK,
                "Contradictory evidence was supplied; the configured safe outcome is BLOCK.",
                POLICY_CONTRADICTORY_EVIDENCE,
            )

        if action in self._config.evidence_required_actions and not request.evidence_refs:
            return self._decide(
                request,
                DecisionOutcome.BLOCK,
                f"Action {action.value} requires at least one evidence reference.",
                POLICY_EVIDENCE_REQUIRED,
            )

        if action in self._config.read_only_actions:
            return self._decide(
                request,
                DecisionOutcome.ALLOW,
                "Read-only analysis is authorised; no business action is executed.",
                POLICY_READ_ONLY_ANALYSIS,
            )

        if action is ActionType.PROPOSE_ACTION:
            return self._decide(
                request,
                DecisionOutcome.ALLOW,
                "Recommendation is authorised, but it is not authorisation to execute.",
                POLICY_PROPOSE_ACTION,
            )

        if action is ActionType.EXECUTE_ACTION:
            return self._decide(
                request,
                DecisionOutcome.ESCALATE,
                "Execution requires human approval; no approval mechanism is implemented in this milestone.",
                POLICY_EXECUTE_APPROVAL,
                requires_human_approval=True,
            )

        if action is ActionType.FINANCIAL_ADJUSTMENT:
            return self._decide(
                request,
                DecisionOutcome.ESCALATE,
                "Financial adjustment requires human approval and is never auto-executed.",
                POLICY_FINANCIAL_APPROVAL,
                requires_human_approval=True,
            )

        # Defensive fail-closed branch; should be unreachable for known actions.
        return self._decide(
            request,
            DecisionOutcome.BLOCK,
            f"No policy rule matched action '{action.value}'; failing closed.",
            POLICY_UNKNOWN_ACTION,
        )

    def _decide(
        self,
        request: PolicyRequest,
        outcome: DecisionOutcome,
        reason: str,
        policy_id: str,
        *,
        requires_human_approval: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        payload: dict[str, Any] = {
            "action": request.action_name,
            "actor": request.actor,
            "resource": request.resource,
            "policy_version": self._config.policy_version,
        }
        if metadata:
            payload.update(metadata)
        return PolicyDecision(
            decision_id=self._decision_id_factory(),
            request_id=request.request_id,
            outcome=outcome,
            reason=reason,
            policy_id=policy_id,
            evaluated_at=self._clock(),
            requires_human_approval=requires_human_approval,
            metadata=payload,
        )
