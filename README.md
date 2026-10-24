# Governed Multi-Agent AI for Autonomous E-Commerce and Accounting Operations

Research prototype exploring a **governance-first** multi-agent architecture for
e-commerce and accounting operations, grounded in two public, read-only datasets:

- Olist Brazilian E-Commerce dataset (`datasets/olist/`, 9 CSV files)
- UCI Online Retail II (`datasets/online_retail_ii/online_retail_II.xlsx`)

## Implementation status (read this first)

This repository currently contains:

1. A tested **dataset-analysis pipeline** (CSV/JSON profiling, validation, figures).
2. A **dataset inspector** (standard library, independent reader).
3. Four LaTeX/PDF reports under `reports/`.
4. **New in this milestone:** typed governance contracts, a deterministic policy
   engine, an append-only JSON Lines audit logger, artifact validation, and tests.

It does **not** contain an orchestrator or any of the seven proposed business
agents. There is no payment integration, no ledger posting, no approval UI, and
no live system connection. The system must not be described as an operational
multi-agent system.

## Repository layout

```
src/governed_multiagent/
  contracts/          # ActionType, PolicyRequest, PolicyDecision, AuditEvent
  governance/         # PolicyEngine + GovernanceService (evaluate + audit)
  audit/              # AuditLogger (JSONL, append-only behaviour)
  validation/         # post-generation artifact validation
tests/
  unit/               # contracts, policy engine, audit logger, parser, artifacts
  integration/        # governance -> audit workflow
  fixtures/           # small representative CSV fixture
examples/
  governance_audit_demo.py
reports/
  dataset_selection_table/   # Deliverable 1 (project/dataset overview)
  dataset_report/            # Deliverable 2 (analysis package + outputs)
  Agents reports/            # Agent design report
  code_report/               # Code/implementation report
datasets/                    # READ-ONLY source data (never modified)
```

The existing analysis package remains at `reports/dataset_report/analysis/`.
It was **not** moved to `src/` because doing so would break its documented
`python -m analysis` entry point and the report reproduction commands. The new
governance package is independent and importable from `src/`.

## Environment

Verified during this milestone:

- Python 3.10.11
- pandas 2.3.3, numpy 1.26.4, matplotlib 3.10.7, seaborn 0.13.2, openpyxl 3.1.5
- pytest 9.1.0

`pyproject.toml` declares the runtime dependencies and a `dev` extra for pytest.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

The editable install makes `governed_multiagent` importable without modifying
`sys.path` manually.

## Tests

From the repository root:

```powershell
python -m pytest
```

Pytest is configured in `pyproject.toml` with the paths needed to import both
the new package and the existing analysis package. The existing analysis tests
are preserved and are included in the same run.

Measured result on this machine: **67 passed** (54 governance/validation tests,
including 4 parser regression tests, plus the 13 existing analysis tests).
Artifact validation also reports **40 artifacts checked, 0 errors, 0 warnings**.

## Data pipeline

Run the existing, unchanged data analysis from its package directory:

```powershell
Set-Location reports\dataset_report
python -m analysis
Set-Location ..\..
```

It reads the raw datasets read-only and writes 26 CSV files, `summary.json`, and
13 PNG figures under `reports/dataset_report/`.

### Artifact validation

Validate the generated outputs after a pipeline run:

```powershell
python -m governed_multiagent.validation --results reports/dataset_report/analysis_results
```

or, after installation:

```powershell
validate-artifacts --results reports/dataset_report/analysis_results
```

Validation is artifact-specific: it checks required files, per-file expected
columns, non-finite numeric values, key/reconciliation consistency, the
`summary.json` structure and cross-file dimensions, and that each expected PNG
is a readable, non-empty PNG. It returns a non-zero exit code when errors exist.

### Olist review-count correction

The inspector previously reported **99,250** Olist review rows. The cause was
`csv.Sniffer` inferring `doublequote=False` for
`olist_order_reviews_dataset.csv`. Literal quotes inside quoted review comments
are encoded as `""`; with `doublequote=False` the parser misread record
boundaries and produced 26 extra logical records.

The inspector now uses an explicit dialect (`quotechar='"'`,
`doublequote=True`, `QUOTE_MINIMAL`) and uses the sniffer only to choose the
delimiter. It reports raw/parsed/rejected counts separately and rejects
width-mismatched records explicitly instead of silently skipping them.

Verified result on the real file: **raw records 99,224, parsed 99,224,
rejected 0**. Pandas and the default `csv.DictReader` agree. The original CSV is
unchanged. The Olist portions of `dataset_inventory.csv`,
`data_quality_summary.csv`, `primary_key_checks.csv`, and
`inspection_summary.json` were refreshed with the fixed parser. Workbook-derived
sections were preserved from the previous run because a full 1M-row OOXML scan
is long-running; they are unaffected by this bug. The LaTeX/PDF reports still
display the old 99,250 value until they are recompiled.

## Governance and audit

### Request/decision/audit contracts

`PolicyRequest` contains a request ID, actor, action, resource, JSON-safe
context, evidence references, and a UTC-aware timestamp. Invalid requests raise
`PolicyContractError` (a `ValueError`).

Actions are categories, not permissions:

`READ_DATA`, `ANALYZE_DATA`, `PROPOSE_ACTION`, `EXECUTE_ACTION`,
`FINANCIAL_ADJUSTMENT`.

Decisions have exactly three outcomes: `ALLOW`, `BLOCK`, `ESCALATE`. Every
decision carries a decision ID, request ID, reason, policy ID, UTC evaluation
timestamp, human-approval flag, and metadata. `ESCALATE` always requires human
approval; it does **not** mean approval was granted.

### Default policy rules

| Scenario | Action / actor | Outcome | Rule |
| --- | --- | --- | --- |
| A | `READ_DATA` or `ANALYZE_DATA`, authorised actor | `ALLOW` | Read-only analysis is permitted |
| B | `FINANCIAL_ADJUSTMENT`, unauthorised actor | `BLOCK` | Unknown/unconfigured actor fails closed |
| C | `EXECUTE_ACTION` or `FINANCIAL_ADJUSTMENT`, authorised actor + evidence | `ESCALATE` | Human approval required; never auto-executed |
| D | Unknown action string | `BLOCK` | Unsupported actions fail closed |
| E | Evidence-required action without evidence | `BLOCK` | Missing evidence blocks |
| - | Explicit `context.evidence_conflict = true` | `BLOCK` | Contradictory evidence uses the safe outcome |
| - | `PROPOSE_ACTION`, authorised actor + evidence | `ALLOW` | A recommendation is not execution authority |

Authorised actor labels are prototype configuration only
(`research-analyst`, `finance-controller`, `auditor`). They are not real
identities or production permissions. The policy is deliberately small and
versioned (`POL-*-v1`) so it can be replaced by a real authorization system.

### Audit log

`AuditLogger` appends one deterministic JSON object per line (`.jsonl`) with:
`event_id`, `timestamp` (UTC ISO-8601), `correlation_id`, `event_type`,
`actor`, `action`, `outcome`, `reason`, `policy_id`, `decision_id`, `metadata`.

- Events are validated before writing.
- Writes are synchronised with an in-process lock and a best-effort lock file.
- Credential-like metadata keys and bulk dataset-row keys are rejected.
- `read_events(request_id=...)` filters by correlation ID.
- A failed write raises `AuditWriteError`; `GovernanceService.evaluate` then
  propagates the failure and returns no result, so a decision is never claimed
  as audited when it was not.

**Limitations:** the log is append-only by application behaviour, not immutable
or tamper-proof. It has no cryptographic hash chain. A stale `.lock` file can
remain after a crash and must be removed manually if no writer is active.
Concurrent writers are best-effort, not a database-grade guarantee. Audit
records store identifiers, decisions, reasons, and evidence references; they do
not store raw dataset rows or secrets.

## Demo

```powershell
python examples/governance_audit_demo.py --audit-file examples/audit_events.jsonl
```

The script evaluates four sample requests (allowed read-only analysis, blocked
financial adjustment, escalated sensitive action requiring review, and a
rejected unsupported action), writes the corresponding audit events, and prints
the request ID, action, decision, reason, and audit event ID. It does not
simulate approval and does not execute any business action.

## Reports

- `reports/dataset_selection_table/main.pdf` — dataset selection and suitability
- `reports/dataset_report/dataset_report.pdf` — dataset analysis
- `reports/Agents reports/Agent_Report.pdf` — seven-agent design (proposed)
- `reports/code_report/Code_Report.pdf` — code/implementation audit

Existing reports and analysis outputs are preserved. Reports are not rewritten
by this milestone.

## Current limitations

- No agent classes, orchestrator, messaging layer, or real business execution.
- No human-approval mechanism; `ESCALATE` only records that review is required.
- No persistent task state beyond the JSONL audit file.
- No tamper-evident audit guarantee.
- Dataset limitations remain: no stock-on-hand history, no general ledger, no
  verified fraud labels, and the two datasets must not be record-level merged.
- The analysis package and the inspector remain two readers of the same corpus;
  the review-count parser is now explicitly corrected in the inspector.

## Next milestone

Implement the governance chokepoint in front of a minimal Orchestrator: typed
task/message contracts, deterministic task dispatch for read-only analysis, and
scenario tests that show every agent action is preceded by an audited policy
decision. Do not add autonomous execution until an approval mechanism exists.
