"""The eight obligation milestones, six outcomes, prerequisites and display state.

Normative source: docs/obligation-states.md. Outcomes are derived only from registered
evidence bound to current roots; candidate-supplied lifecycle fields never carry authority.
"""

from __future__ import annotations

from typing import Any

MILESTONES = (
    "INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED",
    "IMPLEMENTED", "LINKED", "TESTED", "END_TO_END_VERIFIED",
)
OUTCOMES = ("PASS", "PENDING", "FAIL", "STALE", "UNSUPPORTED", "NOT_APPLICABLE")
DISPLAY_PRECEDENCE = (
    "END_TO_END_VERIFIED", "TESTED", "LINKED", "IMPLEMENTED",
    "PROVED", "TYPECHECKED", "FORMALIZED", "INTERPRETED",
)
PREREQUISITES: dict[str, tuple[str, ...]] = {
    "INTERPRETED": (),
    "FORMALIZED": ("INTERPRETED",),
    "TYPECHECKED": ("FORMALIZED",),
    "PROVED": ("TYPECHECKED",),
    "IMPLEMENTED": ("INTERPRETED",),
    "LINKED": ("TYPECHECKED", "IMPLEMENTED"),
    "TESTED": ("IMPLEMENTED", "TYPECHECKED"),
    "END_TO_END_VERIFIED": ("PROVED", "IMPLEMENTED", "LINKED"),
}
CONTRACT_MILESTONES = ("INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED")
IMPLEMENTATION_MILESTONES = ("IMPLEMENTED", "LINKED", "TESTED", "END_TO_END_VERIFIED")

ROLES = ("guarantee", "assumption", "declaration", "exclusion", "open_question")
DRAFT_CATEGORIES = {
    "entities": "entity",
    "preconditions": "precondition",
    "postconditions": "postcondition",
    "invariants": "invariant",
    "safety_properties": "safety_property",
    "liveness_properties": "liveness_property",
    "resource_constraints": "resource_constraint",
    "error_semantics": "error_semantics",
    "explicit_non_goals": "explicit_non_goal",
    "ambiguities": "ambiguity",
}


def claim_id(milestone: str, obligation_id: str, revision: int) -> str:
    return f"{milestone}:{obligation_id}@{revision}"


def applicability(record: dict[str, Any], ledger_assumptions: dict[str, dict] | None = None) -> dict[str, tuple[bool, str]]:
    """Base applicability by frozen role and kind: {milestone: (applicable, reason)}.

    Required guarantee milestones are never marked NOT_APPLICABLE to obtain a passing report.
    """
    role = record["role"]
    kind = record["kind"]
    na = lambda reason: (False, reason)  # noqa: E731
    yes = (True, "applicable by role")
    out: dict[str, tuple[bool, str]] = {m: yes for m in MILESTONES}
    if role == "guarantee":
        if kind == "non_vacuity":
            reason = "non-vacuity is a contract-level witness obligation, not an implementation claim"
            for m in IMPLEMENTATION_MILESTONES:
                out[m] = na(reason)
        return out
    if role == "assumption":
        supplier = (ledger_assumptions or {}).get(record["id"], {})
        where = supplier.get("discharged_at", "an obligation outside this contract")
        out["PROVED"] = na("an assumption is a hypothesis; it is not proved by the theorems that use it")
        for m in IMPLEMENTATION_MILESTONES:
            out[m] = na(f"assumption is supplied by {supplier.get('supplied_by', 'its declared supplier')} and discharged at {where}")
        return out
    if role == "declaration":
        out["PROVED"] = na("a declaration carries no proposition to prove")
        out["TESTED"] = na("declarations have no proposition to test; their adapters are exercised by guarantee campaigns")
        out["END_TO_END_VERIFIED"] = na("declarations carry no end-to-end correctness claim")
        return out
    # exclusion / open_question
    reason = {
        "exclusion": "an explicit exclusion is retained as metadata and prohibits stronger claims",
        "open_question": "resolving a question is not proving a theorem",
    }[role]
    for m in ("PROVED", *IMPLEMENTATION_MILESTONES):
        out[m] = na(reason)
    return out


def derive_state(lifecycle: dict[str, dict[str, Any]]) -> str:
    """Display projection (presentation order, not an assurance ranking)."""
    for m in DISPLAY_PRECEDENCE:
        if lifecycle[m]["outcome"] == "PASS":
            return m
    return "INTERPRETED"


def milestone_entry(outcome: str, reason: str, evidence_refs: list[str] | None = None, scope: list[str] | None = None) -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError(outcome)
    return {
        "outcome": outcome,
        "evidence_refs": sorted(set(evidence_refs or [])),
        "reason": reason,
        "scope": list(scope or []),
    }
