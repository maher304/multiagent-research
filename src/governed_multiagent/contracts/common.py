"""Shared helpers for the typed governance contracts.

The helpers deliberately use only the standard library. They enforce the
invariants that make decisions and audit records reproducible: UTC-aware
timestamps, non-empty identifiers, and JSON-safe structured metadata.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


class PolicyContractError(ValueError):
    """Raised when a governance contract is constructed with invalid data."""


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def ensure_utc(value: datetime, field: str) -> datetime:
    """Require a timezone-aware datetime and normalise it to UTC."""

    if not isinstance(value, datetime):
        raise PolicyContractError(f"{field} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise PolicyContractError(f"{field} must be timezone-aware (UTC)")
    return value.astimezone(timezone.utc)


def require_text(value: Any, field: str) -> str:
    """Require a non-empty, non-whitespace string and return it stripped."""

    if not isinstance(value, str):
        raise PolicyContractError(f"{field} must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise PolicyContractError(f"{field} must not be empty")
    return stripped


def optional_text(value: Any, field: str) -> str | None:
    """Validate an optional identifier-like field."""

    if value is None:
        return None
    return require_text(value, field)


def ensure_jsonable(value: Any, field: str = "value") -> Any:
    """Validate that a value only contains JSON-compatible primitives.

    ``datetime`` and enum values are intentionally rejected in metadata: callers
    must serialise them explicitly so the audit representation stays stable.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise PolicyContractError(f"{field} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise PolicyContractError(f"{field} keys must be non-empty strings")
            out[key] = ensure_jsonable(item, f"{field}.{key}")
        return out
    if isinstance(value, (list, tuple)):
        return [ensure_jsonable(item, f"{field}[{index}]") for index, item in enumerate(value)]
    raise PolicyContractError(
        f"{field} contains unsupported type {type(value).__name__}; "
        "use JSON primitives (str, int, float, bool, None, list, dict)"
    )


def copy_jsonable_mapping(value: Any, field: str) -> dict[str, Any]:
    """Copy and validate a mapping whose values must be JSON-compatible."""

    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise PolicyContractError(f"{field} must be a mapping, got {type(value).__name__}")
    return ensure_jsonable(dict(value), field)


def canonical_json(payload: Any) -> str:
    """Deterministic JSON used for hashing, tests and audit lines."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
