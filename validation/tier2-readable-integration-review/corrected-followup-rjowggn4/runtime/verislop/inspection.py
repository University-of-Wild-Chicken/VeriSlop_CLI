"""`verislop inspect`, `explain-block`, `status` and `diff` — read-only views.

All of them derive from the package's artifacts and evidence; none writes evidence. `inspect
obligation` resolves the chain public claim -> claim ID -> evidence -> registered verifier ->
frozen inputs -> declared trust.
"""

from __future__ import annotations

from typing import Any

from . import canonical, view as viewmod
from .errors import Diagnostic, UsageError
from .lifecycle import MILESTONES, claim_id
from .package import Package
from .stage import StageResult

REMEDIATION = {
    "INTERPRETATION_UNRESOLVED": "resolve the ambiguity (`--resolve ID=ALT` or interactively) and re-interpret in a new run",
    "UNCOVERED_SOURCE_CLAUSE": "give every request clause a disposition in the interpretation ledger",
    "INPUT_MUTATION": "frozen inputs changed; restore them or start a new run package",
    "CLAIM_MUTATION": "claims/tier/policy changed after freeze; start a new run package",
    "STATEMENT_MISMATCH": "the proof candidate changed a frozen statement or definition; repair proofs only",
    "INADMISSIBLE_AXIOM": "remove sorry/native_decide/custom axioms from the proofs",
    "PROOF_UNRESOLVED": "supply proofs (`verislop prove --candidate FILE` or a prover agent) and re-run `verislop accept`",
    "MISSING_WITNESS": "prove non-vacuity with concrete witnesses (e.g. `refine ⟨1, 0, ?_⟩`)",
    "UNSUPPORTED_SEMANTICS": "use the DSL fragment or accept that opaque statements cannot be tested",
    "UNSUPPORTED_CAPABILITY": "choose a supported tier/target/endpoint (`verislop capabilities`)",
    "VERIFIER_NOT_RUN": "run the missing pipeline stage",
    "STALE_OR_UNBOUND_EVIDENCE": "re-run the stage whose inputs or verifier changed (a new run if frozen inputs changed)",
    "UNMAPPED_IMPLEMENTATION_OBJECT": "bind every public implementation object or declare it a helper",
    "AMBIGUOUS_CORRESPONDENCE": "keep exactly one binding per symbol and per object",
    "TEST_FAILURE": "fix the implementation; the counterexample is in the TESTED evidence",
    "EMPTY_TEST_CAMPAIGN": "the campaign had too few effective cases; inspect antecedents/generators",
    "NONDETERMINISM": "remove nondeterminism from the target or the build",
    "CLEAN_BUILD_FAILURE": "make the accepted contract and implementation build from frozen inputs",
    "REVIEW_NOT_RUN": "run `verislop review --checkpoint ...` with the configured hierarchy",
    "REVIEW_REJECTED": "address the review findings with a new candidate; review restarts at the first tier",
}


def _recorded_vscore(pkg: Package, result: StageResult) -> StageResult:
    """Inspection reads recorded evidence; only verify performs a fresh mechanical gate."""
    from .backends import registry

    claims_error = None
    try:
        frozen = registry.frozen_claims(pkg)
    except (OSError, ValueError) as exc:
        frozen, claims_error = None, exc

    def is_vscore_report(value):
        return (isinstance(value, dict) and value.get("schema_version") == "0.2"
                and (value.get("target") == "vscore" or value.get("backend") in (registry.VSCORE_ID, registry.VSCORE3_ID)))

    recorded = registry.claims_format(frozen) == "0.2" or is_vscore_report(result.summary)
    if not recorded and callable(getattr(pkg, "path", None)):
        # The report remains historical even when the claims that once selected its
        # backend are absent or damaged. This fallback identifies a display only.
        try:
            stored = pkg.path("report")
            recorded = stored.is_file() and is_vscore_report(canonical.load_file(stored))
        except (OSError, ValueError):
            pass
    if recorded:
        result.summary = {**result.summary, "freshness": "recorded_execution_only"}
        result.lines.insert(0, "Recorded VSCore execution only; run verify for a fresh mechanical and release gate.")
        if claims_error is not None or (frozen is not None and registry.claims_format(frozen) == "unsupported"):
            result.diagnostics.append(Diagnostic("INVALID_CANDIDATE", "frozen implementation claims are unreadable or unsupported; the displayed VSCore execution is historical"))
            result.status = "BLOCKED"
    elif claims_error is not None:
        raise claims_error
    return result


def inspect(pkg: Package, kind: str, ident: str | None) -> StageResult:
    res = StageResult("inspect", "PASS", "read-only inspection")
    if kind == "obligation":
        if not ident:
            raise UsageError("inspect obligation needs an obligation ID")
        v = viewmod.derive(pkg)
        rec = v["obligations"].get(ident)
        if rec is None:
            raise UsageError(f"unknown obligation {ident}")
        chain = []
        for m in MILESTONES:
            entry = rec["lifecycle"][m]
            for ref in entry["evidence_refs"]:
                e = pkg.evidence.by_id(ref.split(":", 1)[1])
                if e:
                    chain.append({"milestone": m, "outcome": entry["outcome"], "claim_id": e.claim_id, "evidence_id": e.id,
                                  "verifier": e.record["verifier_id"], "verifier_hash": e.record["verifier_hash"],
                                  "verifier_current": e.verifier_current, "input_root": e.record["input_root_hash"],
                                  "scope": e.record["scope"], "trusted_dependencies": e.record["trusted_dependencies"]})
        res.summary = {"obligation": rec, "provenance_chain": chain}
        res.lines = [f"{ident} ({rec['role']}, {rec['kind']}) state {rec['state']}: {rec['statement']}"]
        for m in MILESTONES:
            e = rec["lifecycle"][m]
            res.lines.append(f"  {m:<20} {e['outcome']:<15} {e['reason']}")
        if rec.get("formal"):
            res.lines.append(f"  formal: {rec['formal']['representation']} {rec['formal']['lean_symbol']} {rec['formal']['statement_hash']}")
        return _recorded_vscore(pkg, res)
    if kind == "evidence":
        if not ident:
            res.summary = {"evidence": [{"id": e.id, "claim": e.claim_id, "status": e.status, "verifier": e.record.get("verifier_id"),
                                         "valid": e.valid, "verifier_current": e.verifier_current} for e in pkg.evidence.load()]}
            res.lines = [f"{e.id} {e.claim_id:<28} {e.status:<8} {e.record.get('verifier_id')}" + ("" if e.valid else " INVALID") +
                         ("" if e.verifier_current else " (verifier changed)") for e in pkg.evidence.load()]
            return _recorded_vscore(pkg, res)
        e = pkg.evidence.by_id(ident.removeprefix("evidence:"))
        if e is None:
            raise UsageError(f"unknown evidence {ident}")
        res.summary = {"record": e.record, "result": e.result, "problems": e.problems, "verifier_current": e.verifier_current}
        res.lines = [canonical.dumps_pretty(res.summary).decode()]
        return _recorded_vscore(pkg, res)
    paths = {"report": pkg.path("report"), "certificate": pkg.path("accepted") / "acceptance.json", "ir": pkg.path("accepted_ir")}
    p = paths[kind]
    if not p.is_file():
        raise UsageError(f"no {kind} in {pkg.root}")
    res.summary = canonical.load_file(p)
    res.lines = [f"{kind}: {pkg.rel(p)} ({canonical.digest(p.read_bytes())})"]
    return _recorded_vscore(pkg, res)


def status(pkg: Package) -> StageResult:
    v = viewmod.write(pkg)
    res = StageResult("status", "PASS", "derived obligation view written (no gate)")
    res.summary = v
    sym = {"PASS": "✓", "FAIL": "✗", "PENDING": "·", "STALE": "s", "UNSUPPORTED": "u", "NOT_APPLICABLE": "–"}
    res.lines = ["       " + " ".join(m[:4] for m in MILESTONES)]
    for oid, rec in v["obligations"].items():
        res.lines.append(f"{oid:<6} " + "    ".join(sym[rec["lifecycle"][m]["outcome"]] for m in MILESTONES) + f"    {rec['role']}")
    for prob in v["evidence_integrity_problems"]:
        res.diagnostics.append(Diagnostic("STALE_OR_UNBOUND_EVIDENCE", f"evidence {prob['evidence_id']}: {prob['problems'][0]}", severity="warning"))
    res.artifacts["obligation_view"] = pkg.rel(pkg.path("view"))
    return _recorded_vscore(pkg, res)


def explain_block(pkg: Package) -> StageResult:
    res = StageResult("explain-block", "PASS", "explanation produced (no gate)")
    rp = pkg.path("report")
    if rp.is_file():
        rep = canonical.load_file(rp)
        reasons = rep["blocking_reasons"] + rep["infrastructure_errors"]
        res.summary = {"terminal_status": rep["terminal_status"], "qualified_result": rep["qualified_result"],
                       "reasons": [{**r, "remediation": REMEDIATION.get(r["code"], "see the diagnostic")} for r in reasons]}
        res.lines = [f"{rep['terminal_status']}: {rep['qualified_result']}"]
    else:
        v = viewmod.derive(pkg)
        reasons = []
        for oid, rec in v["obligations"].items():
            for m in MILESTONES:
                e = rec["lifecycle"][m]
                if e["outcome"] in ("FAIL", "STALE", "UNSUPPORTED"):
                    reasons.append({"code": e["outcome"], "obligations": [oid], "message": f"{m}: {e['reason']}", "claims": [claim_id(m, oid, rec["revision"])]})
        res.summary = {"terminal_status": None, "note": "no report.json yet; showing failing milestones from the derived view",
                       "reasons": reasons}
        res.lines = ["no report.json yet (run `verislop verify`); failing milestones from the derived view:"]
    for r in res.summary["reasons"]:
        where = f" [{', '.join(r.get('obligations', []))}]" if r.get("obligations") else ""
        res.lines.append(f"  {r['code']}{where}: {r['message']}")
        if r.get("remediation"):
            res.lines.append(f"      -> {r['remediation']}")
    if not res.summary["reasons"]:
        res.lines.append("  nothing is blocked")
    return _recorded_vscore(pkg, res)


def diff(a: Package, b: Package) -> StageResult:
    res = StageResult("diff", "PASS", "comparison produced (no gate)")
    va, vb = viewmod.derive(a), viewmod.derive(b)
    ra, rb = va["roots"], vb["roots"]
    roots = {k: {"from": ra.get(k), "to": rb.get(k), "changed": ra.get(k) != rb.get(k)} for k in sorted(set(ra) | set(rb))}
    obl: dict[str, Any] = {}
    for oid in sorted(set(va["obligations"]) | set(vb["obligations"])):
        x, y = va["obligations"].get(oid), vb["obligations"].get(oid)
        if x is None or y is None:
            obl[oid] = {"change": "added" if x is None else "removed"}
            continue
        ch: dict[str, Any] = {}
        if x["revision"] != y["revision"]:
            ch["revision"] = [x["revision"], y["revision"]]
        sx, sy = (x.get("formal") or {}).get("statement_hash"), (y.get("formal") or {}).get("statement_hash")
        if sx != sy:
            ch["statement_hash"] = [sx, sy]
        for m in MILESTONES:
            if x["lifecycle"][m]["outcome"] != y["lifecycle"][m]["outcome"]:
                ch.setdefault("lifecycle", {})[m] = [x["lifecycle"][m]["outcome"], y["lifecycle"][m]["outcome"]]
        if ch:
            obl[oid] = ch
    status = {}
    for side, pkg in (("from", a), ("to", b)):
        rp = pkg.path("report")
        status[side] = canonical.load_file(rp)["terminal_status"] if rp.is_file() else None
    res.summary = {"roots": roots, "obligations": obl, "terminal_status": status}
    res.lines = [f"terminal status: {status['from']} -> {status['to']}"]
    res.lines += [f"root {k}: {'CHANGED' if v['changed'] else 'same'}" for k, v in roots.items()]
    for oid, ch in obl.items():
        res.lines.append(f"{oid}: {ch}")
    return res
