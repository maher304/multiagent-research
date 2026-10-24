"""Typed policy requests.

A :class:`PolicyRequest` is an *authorisation question*, not a permission and
not an action. The policy engine decides what to do with it.
"""

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
    require_text,
    utc_now,
)


class ActionType(str, Enum):
    """Action categories a component can ask the governance layer to evaluate."""

    READ_DATA = "READ_DATA"
    ANALYZE_DATA = "ANALYZE_DATA"
    PROPOSE_ACTION = "PROPOSE_ACTION"
    EXECUTE_ACTION = "EXECUTE_ACTION"
    FINANCIAL_ADJUSTMENT = "FINANCIAL_ADJUSTMENT"


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    """A validated request for a policy decision.

    ``action`` is typed as ``ActionType | str`` so that an *unsupported* action
    name can reach the policy engine and be blocked explicitly. Known action
    names are normalised to :class:`ActionType`; unknown non-empty strings are
    preserved and will be rejected by the engine with a fail-closed BLOCK.
    """

    actor: str
    action: ActionType | str
    resource: str
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    context: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_text(self.request_id, "request_id"))
        object.__setattr__(self, "actor", require_text(self.actor, "actor"))
        object.__setattr__(self, "resource", require_text(self.resource, "resource"))
        object.__setattr__(self, "timestamp", ensure_utc(self.timestamp, "timestamp"))

        action = self.action
        if isinstance(action, ActionType):
            pass
        elif isinstance(action, str) and action.strip():
            raw = action.strip()
            try:
                action = ActionType(raw.upper())
            except ValueError:
                action = raw
        else:
            raise PolicyContractError("action must be an ActionType or a non-empty string")
        object.__setattr__(self, "action", action)

        object.__setattr__(self, "context", copy_jsonable_mapping(self.context, "context"))

        refs = self.evidence_refs
        if refs is None:
            refs = ()
        if isinstance(refs, str):
            refs = (refs,)
        if not isinstance(refs, (tuple, list)):
            raise PolicyContractError("evidence_refs must be a sequence of strings")
        normalised_refs = tuple(require_text(ref, "evidence_refs[]") for ref in refs)
        object.__setattr__(self, "evidence_refs", normalised_refs)

    @property
    def action_name(self) -> str:
        """Stable serialised action name (works for known and unknown actions)."""

        return self.action.value if isinstance(self.action, ActionType) else str(self.action)

    @property
    def is_known_action(self) -> bool:
        return isinstance(self.action, ActionType)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "actor": self.actor,
            "action": self.action_name,
            "resource": self.resource,
            "context": dict(self.context),
            "evidence_refs": list(self.evidence_refs),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PolicyRequest":
        if not isinstance(payload, Mapping):
            raise PolicyContractError("request payload must be a mapping")
        refs = payload.get("evidence_refs", ())
        if isinstance(refs, str):
            refs = (refs,)
        elif refs is None:
            refs = ()
        else:
            refs = tuple(refs)
        return cls(
            request_id=payload.get("request_id"),  # type: ignore[arg-type]
            actor=payload.get("actor"),  # type: ignore[arg-type]
            action=payload.get("action"),  # type: ignore[arg-type]
            resource=payload.get("resource"),  # type: ignore[arg-type]
            context=payload.get("context", {}),
            evidence_refs=refs,
            timestamp=datetime.fromisoformat(payload["timestamp"])
            if isinstance(payload.get("timestamp"), str)
            else payload.get("timestamp"),  # type: ignore[arg-type]
        )
