"""Typed, privacy-aware audit events.

Audit events capture *what was decided, by whom, and why*, together with
references to evidence. They must not contain credentials, tokens, or complete
source dataset rows. This module enforces that at construction time.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .common import (
    PolicyContractError,
    canonical_json,
    copy_jsonable_mapping,
    ensure_utc,
    optional_text,
    require_text,
    utc_now,
)
from .decisions import DecisionOutcome, PolicyDecision
from .requests import PolicyRequest

#: Substrings that identify credential-like metadata keys. Keys are matched
#: case-insensitively. The goal is to refuse accidental secret logging.
SENSITIVE_KEY_PATTERNS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
    "client_secret",
    "session_cookie",
)

#: Keys that would amount to dumping a raw dataset record into the audit log.
BULK_DATA_KEY_PATTERNS: tuple[str, ...] = (
    "raw_row",
    "raw_record",
    "full_row",
    "dataset_row",
    "dataframe",
)

MAX_METADATA_BYTES = 16 * 1024


class AuditEventType(str, Enum):
    """Stable event categories used by the prototype."""

    POLICY_DECISION = "POLICY_DECISION"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ACTION_BLOCKED = "ACTION_BLOCKED"
    ESCALATION_REQUESTED = "ESCALATION_REQUESTED"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    SYSTEM = "SYSTEM"


def _assert_safe_metadata(value: Any, path: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(pattern in lowered for pattern in SENSITIVE_KEY_PATTERNS):
                raise PolicyContractError(f"{path}.{key} looks like a credential and must not be audited")
            if any(pattern in lowered for pattern in BULK_DATA_KEY_PATTERNS):
                raise PolicyContractError(f"{path}.{key} looks like bulk dataset content and must not be audited")
            _assert_safe_metadata(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_metadata(item, f"{path}[{index}]")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One append-only audit record.

    ``correlation_id`` is the request identifier used for filtering. The event
    identifier is independent so multiple events may describe one request.
    """

    correlation_id: str
    event_type: AuditEventType | str
    actor: str
    action: str
    outcome: DecisionOutcome | str
    reason: str
    policy_id: str | None = None
    decision_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", require_text(self.event_id, "event_id"))
        object.__setattr__(self, "correlation_id", require_text(self.correlation_id, "correlation_id"))
        object.__setattr__(self, "actor", require_text(self.actor, "actor"))
        object.__setattr__(self, "action", require_text(self.action, "action"))
        object.__setattr__(self, "reason", require_text(self.reason, "reason"))
        object.__setattr__(self, "policy_id", optional_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "decision_id", optional_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "timestamp", ensure_utc(self.timestamp, "timestamp"))

        event_type = self.event_type
        if isinstance(event_type, AuditEventType):
            pass
        elif isinstance(event_type, str) and event_type.strip():
            raw = event_type.strip()
            try:
                event_type = AuditEventType(raw.upper())
            except ValueError:
                event_type = raw
        else:
            raise PolicyContractError("event_type must be an AuditEventType or non-empty string")
        object.__setattr__(self, "event_type", event_type)

        outcome = self.outcome
        if isinstance(outcome, DecisionOutcome):
            pass
        elif isinstance(outcome, str) and outcome.strip():
            raw = outcome.strip().upper()
            try:
                outcome = DecisionOutcome(raw)
            except ValueError:
                outcome = raw
        else:
            raise PolicyContractError("outcome must be a DecisionOutcome or non-empty string")
        object.__setattr__(self, "outcome", outcome)

        metadata = copy_jsonable_mapping(self.metadata, "metadata")
        _assert_safe_metadata(metadata)
        serialised = canonical_json(metadata)
        if len(serialised.encode("utf-8")) > MAX_METADATA_BYTES:
            raise PolicyContractError(
                f"metadata exceeds {MAX_METADATA_BYTES} bytes; audit identifiers and references, not bulk data"
            )
        object.__setattr__(self, "metadata", metadata)

    @property
    def event_type_name(self) -> str:
        return self.event_type.value if isinstance(self.event_type, AuditEventType) else str(self.event_type)

    @property
    def outcome_name(self) -> str:
        return self.outcome.value if isinstance(self.outcome, DecisionOutcome) else str(self.outcome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "event_type": self.event_type_name,
            "actor": self.actor,
            "action": self.action,
            "outcome": self.outcome_name,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "decision_id": self.decision_id,
            "metadata": dict(self.metadata),
        }

    def to_json_line(self) -> str:
        """Deterministic single-line JSON with no trailing newline."""

        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AuditEvent":
        if not isinstance(payload, Mapping):
            raise PolicyContractError("audit event payload must be a mapping")
        timestamp = payload.get("timestamp")
        return cls(
            event_id=payload.get("event_id"),  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp,  # type: ignore[arg-type]
            correlation_id=payload.get("correlation_id"),  # type: ignore[arg-type]
            event_type=payload.get("event_type"),  # type: ignore[arg-type]
            actor=payload.get("actor"),  # type: ignore[arg-type]
            action=payload.get("action"),  # type: ignore[arg-type]
            outcome=payload.get("outcome"),  # type: ignore[arg-type]
            reason=payload.get("reason"),  # type: ignore[arg-type]
            policy_id=payload.get("policy_id"),
            decision_id=payload.get("decision_id"),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_json_line(cls, line: str) -> "AuditEvent":
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyContractError(f"invalid audit JSON line: {exc}") from exc
        return cls.from_dict(payload)

    @classmethod
    def for_decision(
        cls,
        request: PolicyRequest,
        decision: PolicyDecision,
        *,
        event_type: AuditEventType = AuditEventType.POLICY_DECISION,
        timestamp: datetime | None = None,
        event_id: str | None = None,
    ) -> "AuditEvent":
        """Build the audit record for a governance decision."""

        metadata: dict[str, Any] = {
            "resource": request.resource,
            "evidence_refs": list(request.evidence_refs),
            "requires_human_approval": decision.requires_human_approval,
            "action": request.action_name,
        }
        kwargs: dict[str, Any] = {}
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        else:
            kwargs["timestamp"] = decision.evaluated_at
        if event_id is not None:
            kwargs["event_id"] = event_id
        return cls(
            correlation_id=request.request_id,
            event_type=event_type,
            actor=request.actor,
            action=request.action_name,
            outcome=decision.outcome_name,
            reason=decision.reason,
            policy_id=decision.policy_id,
            decision_id=decision.decision_id,
            metadata=metadata,
            **kwargs,
        )
