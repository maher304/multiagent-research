"""Typed policy decisions."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .common import (
    PolicyContractError,
    copy_jsonable_mapping,
    ensure_utc,
    optional_text,
    require_text,
    utc_now,
)


class DecisionOutcome(str, Enum):
    """The only three outcomes the governance layer can return."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """The result of evaluating a :class:`PolicyRequest`.

    A decision answers *whether* an action may proceed under policy. It never
    executes the action itself.
    """

    request_id: str
    outcome: DecisionOutcome | str
    reason: str
    policy_id: str | None = None
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    evaluated_at: datetime = field(default_factory=utc_now)
    requires_human_approval: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_text(self.request_id, "request_id"))
        object.__setattr__(self, "reason", require_text(self.reason, "reason"))
        object.__setattr__(self, "policy_id", optional_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "evaluated_at", ensure_utc(self.evaluated_at, "evaluated_at"))

        outcome = self.outcome
        if isinstance(outcome, DecisionOutcome):
            pass
        elif isinstance(outcome, str):
            try:
                outcome = DecisionOutcome(outcome.strip().upper())
            except ValueError as exc:
                raise PolicyContractError(
                    f"outcome must be one of {[item.value for item in DecisionOutcome]}"
                ) from exc
        else:
            raise PolicyContractError("outcome must be a DecisionOutcome or string")
        object.__setattr__(self, "outcome", outcome)

        if not isinstance(self.requires_human_approval, bool):
            raise PolicyContractError("requires_human_approval must be a bool")
        if outcome is DecisionOutcome.ESCALATE and not self.requires_human_approval:
            raise PolicyContractError("ESCALATE decisions must require human approval")

        object.__setattr__(self, "metadata", copy_jsonable_mapping(self.metadata, "metadata"))

    @property
    def outcome_name(self) -> str:
        return self.outcome.value if isinstance(self.outcome, DecisionOutcome) else str(self.outcome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "outcome": self.outcome_name,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "requires_human_approval": self.requires_human_approval,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PolicyDecision":
        if not isinstance(payload, Mapping):
            raise PolicyContractError("decision payload must be a mapping")
        evaluated_at = payload.get("evaluated_at")
        return cls(
            decision_id=payload.get("decision_id"),  # type: ignore[arg-type]
            request_id=payload.get("request_id"),  # type: ignore[arg-type]
            outcome=payload.get("outcome"),  # type: ignore[arg-type]
            reason=payload.get("reason"),  # type: ignore[arg-type]
            policy_id=payload.get("policy_id"),
            requires_human_approval=payload.get("requires_human_approval", False),
            metadata=payload.get("metadata", {}),
            evaluated_at=datetime.fromisoformat(evaluated_at)
            if isinstance(evaluated_at, str)
            else evaluated_at,  # type: ignore[arg-type]
        )
