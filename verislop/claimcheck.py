"""Supervisor-owned evidence authorization for frozen claims.

A registered producer is not automatically authorized to satisfy every claim.  The claim
chooses its issuer, root kind and result predicate; none of these can be selected by the
candidate's raw result.  This module checks evidence bindings, not theorem soundness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .errors import Diagnostic
from .evidence import Evidence
from .lifecycle import milestone_entry
from .verifiers import VERIFIERS, verifier_hash


@dataclass
class ClaimAssessment:
    outcome: str
    reason: str
    evidence: Evidence | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    authorized: bool = False  # binding/integrity only, never semantic acceptance

    def entry(self) -> dict[str, Any]:
        return milestone_entry(
            self.outcome, self.reason,
            [f"evidence:{self.evidence.id}"] if self.evidence else [],
            self.evidence.record.get("scope", []) if self.evidence else [],
        )


def evaluate_claim(claim: Mapping[str, Any], evidence: Iterable[Evidence],
                   roots: Mapping[str, str | None], default_root_kind: str) -> ClaimAssessment:
    """Evaluate the latest current, correctly bound result from the assigned issuer.

    ``claim`` and ``default_root_kind`` must come from the supervisor's frozen inventory or
    registered legacy phase rules.  ``binding_root`` in raw evidence is only a consistency
    assertion.  Old-root/other-issuer records never replace a current authorized failure.
    A malformed latest authorized result cannot expose an earlier PASS.
    """
    cid = claim.get("claim_id", "?")
    issuer = claim.get("verifier_id", claim.get("verifier"))
    root_kind = claim.get("root_kind", default_root_kind)
    authorized = False

    def assessment(outcome: str, reason: str, ev: Evidence | None = None,
                   code: str | None = None, severity: str = "blocking") -> ClaimAssessment:
        diagnostics = [Diagnostic(code, f"{cid}: {reason}", severity=severity, claims=[cid])] if code else []
        return ClaimAssessment(outcome, reason, ev, diagnostics, authorized)

    if claim.get("verifier") is not None and claim.get("verifier_id") is not None and claim["verifier"] != issuer:
        return assessment("FAIL", "frozen claim has conflicting assigned verifiers", code="ORPHAN_CLAIM")
    if not isinstance(issuer, str) or issuer not in VERIFIERS:
        return assessment("FAIL", f"claim names unregistered verifier {issuer!r}", code="ORPHAN_CLAIM")
    if not isinstance(root_kind, str) or not root_kind:
        return assessment("FAIL", "frozen claim has no valid root kind", code="ORPHAN_CLAIM")
    expected_root = roots.get(root_kind)
    records = [e for e in evidence if e.record.get("claim_id") == cid]
    if not records:
        return assessment("PENDING", "no registered verifier has evaluated this claim", code="VERIFIER_NOT_RUN")
    # EvidenceStore supplies sequence ordering. Preserve input order for equal sequence values.
    def sequence(e: Evidence) -> int:
        n = e.result.get("sequence", 0)
        return n if type(n) is int and n >= 0 else 0

    records.sort(key=sequence)
    issued = [e for e in records if e.record.get("verifier_id") == issuer]
    if not issued:
        return assessment("STALE", "evidence was not produced by the claim's assigned verifier", records[-1],
                          "STALE_OR_UNBOUND_EVIDENCE")
    current = [e for e in issued if e.record.get("verifier_hash") == verifier_hash(issuer)]
    if not current:
        return assessment("STALE", "the assigned verifier that produced this evidence has changed", issued[-1],
                          "STALE_OR_UNBOUND_EVIDENCE")
    bound = [e for e in current if expected_root and e.record.get("input_root_hash") == expected_root]
    if not bound:
        return assessment("STALE", f"prior evidence does not bind to the current {root_kind}", current[-1],
                          "STALE_OR_UNBOUND_EVIDENCE")
    ev = bound[-1]
    if not ev.valid:
        return assessment("STALE", "evidence fails integrity checks: " + "; ".join(ev.problems), ev,
                          "STALE_OR_UNBOUND_EVIDENCE")
    if "binding_root" in ev.result and ev.result["binding_root"] != root_kind:
        return assessment("STALE", f"raw result claims a different root kind than frozen {root_kind}", ev,
                          "STALE_OR_UNBOUND_EVIDENCE")
    authorized = True
    if ev.status == "INFRASTRUCTURE_FAILURE":
        return assessment("PENDING", "verifier infrastructure failure; not evaluated", ev,
                          "VERIFIER_FAILURE", "infrastructure")
    if ev.status == "BLOCK":
        outcome = ev.result.get("milestone_outcome")
        outcome = outcome if outcome in ("FAIL", "UNSUPPORTED") else "FAIL"
        codes = ev.result.get("codes") or [d.get("code") for d in ev.result.get("diagnostics", []) if isinstance(d, dict)]
        reason = ev.result.get("reason") or ("blocked: " + ", ".join(c for c in codes if isinstance(c, str)) if codes else "verifier blocked the claim")
        return assessment(outcome, reason, ev)
    if ev.status != "PASS":
        return assessment("FAIL", "evidence has an unknown execution status", ev, "STALE_OR_UNBOUND_EVIDENCE")
    if type(ev.record.get("exit_code")) is not int or ev.record["exit_code"] != 0:
        return assessment("FAIL", "PASS evidence has a nonzero or invalid exit code", ev, "STALE_OR_UNBOUND_EVIDENCE")
    predicate = claim.get("result_predicate", "milestone-pass/0.1")
    if predicate == "bridge-structural/0.1":
        if ev.result.get("structural_acceptance") is not True or ev.result.get("semantic_acceptance") is not False:
            return assessment("FAIL", "PASS evidence does not satisfy the structural-only bridge predicate", ev,
                              "STALE_OR_UNBOUND_EVIDENCE")
    elif predicate == "bridge-semantic-edge/0.1":
        from .bridges.registry import SEMANTIC_CHECKERS

        if issuer not in {entry["verifier_id"] for entry in SEMANTIC_CHECKERS.values()}:
            return assessment("UNSUPPORTED", "semantic-edge claims are satisfied only by a registered relation checker",
                              ev, "UNSUPPORTED_SEMANTICS")
        if (ev.result.get("semantic_acceptance") is not True or ev.result.get("assigns_end_to_end_verified") is not False
                or ev.result.get("semantic_edge_root") != expected_root
                or not isinstance(ev.result.get("proposition_hash"), str)):
            return assessment("FAIL", "PASS evidence does not satisfy the typed semantic-edge predicate", ev,
                              "STALE_OR_UNBOUND_EVIDENCE")
    elif predicate in ("milestone-pass/0.1", "interpretation-coverage/0.1"):
        if ev.result.get("milestone_outcome") != "PASS":
            return assessment("FAIL", "PASS evidence does not satisfy the typed milestone PASS predicate", ev,
                              "STALE_OR_UNBOUND_EVIDENCE")
        if predicate == "interpretation-coverage/0.1":
            coverage = ev.result.get("coverage")
            if not isinstance(coverage, dict) or coverage.get("uncovered_segments") != []:
                return assessment("FAIL", "interpretation evidence lacks complete clause coverage", ev,
                                  "UNCOVERED_SOURCE_CLAUSE")
    else:
        return assessment("UNSUPPORTED", f"unregistered result predicate {predicate!r}", ev, "UNSUPPORTED_SEMANTICS")
    return assessment("PASS", ev.result.get("reason") or f"registered evidence from {issuer}", ev)
