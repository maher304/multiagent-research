"""Runnable governance + audit demonstration.

Run from the repository root after installing the package::

    python examples/governance_audit_demo.py --audit-file examples/audit_events.jsonl

The demo evaluates four sample requests and persists every decision to an
append-only JSON Lines audit file. It does not execute any business action and
does not simulate human approval: ESCALATE means "review required", not
"approved".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from governed_multiagent.audit import AuditLogger, AuditWriteError
from governed_multiagent.contracts import ActionType, PolicyRequest
from governed_multiagent.governance import GovernanceService, PolicyEngine

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_FILE = REPO_ROOT / "examples" / "audit_events.jsonl"


def build_requests() -> list[PolicyRequest]:
    return [
        PolicyRequest(
            actor="research-analyst",
            action=ActionType.READ_DATA,
            resource="olist/olist_orders_dataset.csv",
            context={"purpose": "portfolio analysis"},
        ),
        PolicyRequest(
            actor="untrusted-actor",
            action=ActionType.FINANCIAL_ADJUSTMENT,
            resource="ledger/accounts/receivable",
            evidence_refs=("invoice-123",),
            context={"amount": 500.0},
        ),
        PolicyRequest(
            actor="finance-controller",
            action=ActionType.FINANCIAL_ADJUSTMENT,
            resource="ledger/accounts/receivable",
            evidence_refs=("invoice-123", "approval-note-7"),
            context={"amount": 500.0},
        ),
        PolicyRequest(
            actor="research-analyst",
            action="DELETE_LEDGER",
            resource="ledger",
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demonstrate policy evaluation and audit logging.")
    parser.add_argument("--audit-file", default=str(DEFAULT_AUDIT_FILE), help="JSONL audit destination")
    args = parser.parse_args(argv)

    audit_path = Path(args.audit_file)
    governance = GovernanceService(PolicyEngine(), AuditLogger(audit_path))

    print(f"Audit file: {audit_path}")
    print("=" * 100)
    try:
        for index, request in enumerate(build_requests(), start=1):
            result = governance.evaluate(request)
            decision = result.decision
            print(f"[{index}] request_id   : {request.request_id}")
            print(f"    action          : {request.action_name}")
            print(f"    actor           : {request.actor}")
            print(f"    decision        : {decision.outcome_name}")
            print(f"    reason          : {decision.reason}")
            print(f"    policy_id       : {decision.policy_id}")
            print(f"    human approval  : {decision.requires_human_approval}")
            print(f"    audit event_id  : {result.audit_event.event_id}")
            print("-" * 100)
    except AuditWriteError as exc:
        print(f"AUDIT FAILURE: {exc}", file=sys.stderr)
        return 1

    stored = governance.audit_logger.read_events()
    print(f"Persisted {len(stored)} audit event(s).")
    print("No business action was executed and no approval was simulated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
