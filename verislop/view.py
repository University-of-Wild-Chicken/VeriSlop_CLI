"""Derived obligation view: semantic records joined with the registered evidence overlay.

`obligation-view.json` is mutable and derived; it never feeds back into the semantic IR. Every
outcome comes from evidence that (a) passes integrity checks, (b) was produced by the current
registered verifier and (c) binds to the current root for that milestone. Otherwise prior
evidence is STALE. A PASS whose prerequisites have not passed is shown PENDING.
"""

from __future__ import annotations

from typing import Any

from . import SCHEMA_VERSION, canonical, fsutil, schemas
from .claimcheck import evaluate_claim
from .lifecycle import (
    DISPLAY_PRECEDENCE, MILESTONES, PREREQUISITES, IMPLEMENTATION_MILESTONES, applicability, claim_id,
    derive_state, milestone_entry,
)
from .package import Package

DEFAULT_BINDING = {
    "INTERPRETED": "interpretation_root",
    "FORMALIZED": "contract_input_root",
    "TYPECHECKED": "contract_input_root",
    "PROVED": "contract_input_root",
    "IMPLEMENTED": "implementation_root",
    "LINKED": "link_root",
    "TESTED": "test_root",
    "END_TO_END_VERIFIED": "closure_root",
}


def _records(pkg: Package) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """(records, ir obligations by id, claim-record extras by id)."""
    extras: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    ir_obl: dict[str, Any] = {}
    claims_p = pkg.path("claims")
    if claims_p.is_file():
        claims = canonical.load_file(claims_p)
        for r in claims["obligations"]:
            extras[r["id"]] = r
            records.append({k: r[k] for k in ("id", "revision", "kind", "role", "statement", "required",
                                              "source_refs", "scope", "dependencies", "acceptance_criteria")})
    elif pkg.path("draft").is_file():
        from .draft import obligations

        draft = canonical.load_file(pkg.path("draft"))
        if isinstance(draft, dict):
            for r in obligations(draft):
                records.append({k: r[k] for k in ("id", "revision", "kind", "role", "statement", "required",
                                                  "source_refs", "scope", "dependencies", "acceptance_criteria")})
    ir_p = pkg.path("accepted_ir")
    if ir_p.is_file():
        ir = canonical.load_file(ir_p)
        ir_obl = ir.get("obligations", {})
        by_id = {r["id"]: i for i, r in enumerate(records)}
        for oid, rec in ir_obl.items():
            base = {k: v for k, v in rec.items()}
            if oid in by_id:
                records[by_id[oid]] = base
            else:
                records.append(base)
    return records, ir_obl, extras


def implementation_claims(pkg: Package) -> dict[str, Any] | None:
    p = pkg.path("closure") / "implementation-claims.json"
    return canonical.load_file(p) if p.is_file() else None


def derive(pkg: Package, roots: dict[str, str | None] | None = None) -> dict[str, Any]:
    roots = dict(roots or pkg.roots())
    roots.setdefault("contract_candidate_root", pkg.meta().get("contract_candidate_root"))
    if "closure_root" not in roots:
        from .closure import closure_input_root

        roots["closure_root"] = closure_input_root(pkg)
    records, ir_obl, extras = _records(pkg)
    impl = implementation_claims(pkg)
    contract_claims = canonical.load_file(pkg.path("claims")) if pkg.path("claims").is_file() else None
    frozen_claims = {c["claim_id"]: c for inventory in (contract_claims, impl) if inventory
                     for c in inventory["claims"]}
    impl_req: dict[tuple[str, str], dict[str, Any]] = {}
    if impl:
        for c in impl["claims"]:
            if c["obligation"] and c["milestone"]:
                impl_req[(c["obligation"], c["milestone"])] = c
    ledger = canonical.load_file(pkg.path("interpretation")) if pkg.path("interpretation").is_file() else {}
    assumptions = {a["id"]: a for a in ledger.get("assumptions", [])} if isinstance(ledger, dict) else {}
    store = pkg.evidence
    integrity: list[dict[str, Any]] = []
    for e in store.load():
        if not e.valid:
            integrity.append({"evidence_id": e.id, "problems": e.problems})
    impl_refs = _implementation_refs(pkg)

    out: dict[str, Any] = {}
    for rec in records:
        oid, rev = rec["id"], rec["revision"]
        app = applicability(rec, assumptions)
        blocked_by = extras.get(oid, {}).get("blocked_by", [])
        life: dict[str, dict[str, Any]] = {}
        for m in MILESTONES:
            applicable, why = app[m]
            if m in IMPLEMENTATION_MILESTONES and (oid, m) in impl_req:
                c = impl_req[(oid, m)]
                applicable, why = c["applicable"], c["reason"]
            if not applicable:
                life[m] = milestone_entry("NOT_APPLICABLE", why)
                continue
            cid = claim_id(m, oid, rev)
            c = frozen_claims.get(cid)
            root_kind = DEFAULT_BINDING[m]
            if m == "INTERPRETED" and extras.get(oid, {}).get("origin") == "derived":
                root_kind = "contract_input_root"
            if c is None and contract_claims is None and m in ("INTERPRETED", "FORMALIZED"):
                # Before freezing there is no claim inventory. These two producer/phase rules
                # are supervisor-owned; raw evidence cannot choose its own weaker root.
                c = {"claim_id": cid, "verifier": ("verislop.interpretation-recorder" if m == "INTERPRETED"
                                                   else "verislop.formal-statement-checker")}
                if m == "FORMALIZED":
                    root_kind = "contract_candidate_root"
                    # A rejected candidate can display FAIL, but cannot establish a frozen
                    # formalization merely by returning a PASS before claims exist.
                    c["result_predicate"] = "formalization-candidate-failure/0.1"
            if c is None:
                life[m] = milestone_entry("PENDING", "no frozen claim authorizes evidence for this milestone")
                continue
            assessment = evaluate_claim(c, store.for_claim(cid), roots, root_kind)
            if assessment.outcome == "PENDING" and assessment.evidence is None:
                if blocked_by and m != "INTERPRETED":
                    reason = f"blocked by unresolved ambiguity {', '.join(blocked_by)}"
                elif m in IMPLEMENTATION_MILESTONES and impl is None:
                    reason = "implementation phase not started"
                else:
                    reason = "no registered verifier has evaluated this milestone"
                life[m] = milestone_entry("PENDING", reason)
                continue
            life[m] = assessment.entry()
        # Prerequisites: no PASS without PASSing (or not applicable) prerequisites.
        for m in MILESTONES:
            if life[m]["outcome"] != "PASS":
                continue
            missing = [p for p in PREREQUISITES[m] if life[p]["outcome"] not in ("PASS", "NOT_APPLICABLE")]
            if missing:
                life[m] = milestone_entry("PENDING", f"evidence present but prerequisite {', '.join(missing)} has not passed",
                                          life[m]["evidence_refs"])
        view_rec = dict(rec)
        view_rec["state"] = derive_state(life)
        view_rec["lifecycle"] = life
        if oid in ir_obl:
            view_rec["formal"] = ir_obl[oid]["formal"]
        if impl_refs.get(oid):
            view_rec["implementation_refs"] = impl_refs[oid]
        out[oid] = view_rec
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "obligation_view",
        "note": "derived join of semantic records and registered evidence; `state` is a display projection "
                f"in the fixed order {' > '.join(DISPLAY_PRECEDENCE)}, not an assurance ranking",
        "roots": {k: v for k, v in sorted(roots.items()) if v},
        "evidence_integrity_problems": integrity,
        "obligations": out,
    }


def _implementation_refs(pkg: Package) -> dict[str, list[str]]:
    p = pkg.path("bridges") / "link.json"
    if not p.is_file():
        return {}
    link = canonical.load_file(p)
    out: dict[str, list[str]] = {}
    for b in link.get("bindings", []):
        obj = b["implementation_object"]
        ref = f"{obj['file']}#{obj['qualname']}@{obj['source_hash']}"
        for oid in b["obligations"]:
            out.setdefault(oid, []).append(ref)
    return {k: sorted(set(v)) for k, v in out.items()}


def write(pkg: Package, roots: dict[str, str | None] | None = None) -> dict[str, Any]:
    v = derive(pkg, roots)
    for oid, rec in v["obligations"].items():
        issues = schemas.validate("obligation", rec)
        if issues:
            raise RuntimeError(f"derived view record {oid} failed schema validation: {issues[0]}")
    fsutil.write_json(pkg.path("view"), v, pretty=True)
    return v
