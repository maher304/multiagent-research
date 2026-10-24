"""Governed multi-agent research prototype.

This package currently implements the *governance and audit foundation* that
must exist before any autonomous agent is allowed to act:

* typed contracts (:mod:`governed_multiagent.contracts`),
* a deterministic policy engine (:mod:`governed_multiagent.governance`),
* an append-only JSON Lines audit logger (:mod:`governed_multiagent.audit`),
* artifact validation for the existing data pipeline
  (:mod:`governed_multiagent.validation`).

It does **not** implement an orchestrator or any of the seven business agents.
Those remain proposed; see ``README.md`` for the accurate status.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
