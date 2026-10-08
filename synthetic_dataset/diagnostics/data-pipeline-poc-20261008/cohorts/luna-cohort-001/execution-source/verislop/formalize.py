"""`verislop formalize`: formal statement checking and freezing of the Lean challenge.

The formalizer (agent or candidate directory) proposes a Lean file and obligation bindings.
This stage composes the challenge with the generated registry, elaborates it in the sandbox,
replays it through the kernel tool, checks bindings/registry/profile/statements, verifies
each DSL denotation by kernel definitional equality, enforces the witness policy, and only then
freezes the interpreted claim set and the formal challenge. After freezing, statements,
preconditions, non-goals, the target boundary and allowed axioms cannot change inside this run:
a different statement needs a new run package.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from . import SCHEMA_VERSION, canonical, contract, fsutil, leanbridge, policy as policymod, schemas
from .claimcheck import evaluate_claim
from .draft import blocked_obligations
from .errors import Diagnostic, UsageError
from .events import EventSink
from .exprjson import parse_name
from .lifecycle import CONTRACT_MILESTONES, applicability, claim_id
from .package import Package
from .stage import StageResult, status_from
from .verifiers import verifier_hash

VERIFIER = "verislop.formal-statement-checker"
SUPPORTED_TOOLCHAINS = ("leanprover/lean4:v4.34.1",)
MILESTONE_VERIFIER = {
    "INTERPRETED": "verislop.interpretation-recorder",
    "FORMALIZED": VERIFIER,
    "TYPECHECKED": "verislop.lean-acceptance",
    "PROVED": "verislop.lean-acceptance",
}
PASS_PREDICATE = {
    "INTERPRETED": "interpretation recorded with provenance, schema and coverage checks bound to the request bytes",
    "FORMALIZED": "a typed formal binding exists and its statement is checked against the frozen challenge",
    "TYPECHECKED": "kernel replay accepts the declaration and it matches the frozen challenge",
    "PROVED": "an admissible proof of the exact frozen statement passes axiom, statement and witness audits",
}


def require_interpretation(pkg: Package) -> tuple[dict[str, Any], dict[str, Any], list[Diagnostic]]:
    draft_p, ledger_p = pkg.path("draft"), pkg.path("interpretation")
    if not (draft_p.is_file() and ledger_p.is_file()):
        raise UsageError("no recorded interpretation in this package; run `verislop interpret` first")
    root = pkg.interpretation_root()
    diags: list[Diagnostic] = []
    checked = evaluate_claim(
        {"claim_id": "INTERPRETATION:request", "verifier": "verislop.interpretation-recorder",
         "result_predicate": "interpretation-coverage/0.1"},
        pkg.evidence.for_claim("INTERPRETATION:request"), {"interpretation_root": root}, "interpretation_root")
    if checked.outcome != "PASS":
        diags.extend(checked.diagnostics or [Diagnostic(
            "INTERPRETATION_UNRESOLVED", "the recorded interpretation did not pass its checks; see `verislop inspect evidence`")])
    return canonical.load_file(draft_p), canonical.load_file(ledger_p), diags


def load_candidate_dir(path: Path) -> tuple[bytes, dict[str, Any]]:
    fpath = path / "formalization.json"
    if not fpath.is_file():
        raise UsageError(f"{path} must contain formalization.json")
    form = canonical.load_file(fpath)
    lean_file = form.get("lean_file", "Contract.lean") if isinstance(form, dict) else "Contract.lean"
    lpath = path / str(lean_file)
    if not fsutil.inside(path, lpath) or not lpath.is_file():
        raise UsageError(f"candidate Lean file {lean_file!r} not found in {path}")
    return lpath.read_bytes(), form


def validate_candidate(form: Any, records: list[dict[str, Any]]) -> list[Diagnostic]:
    diags = schemas.require_valid("formalization-candidate", form, "formalization candidate")
    if diags:
        if isinstance(form, dict) and isinstance(form.get("error"), str):
            diags.insert(0, Diagnostic("INVALID_CANDIDATE", form["error"]))
        return diags
    by_id = {r["id"]: r for r in records}
    seen: set[str] = set()
    for b in form["bindings"]:
        oid = b["obligation"]
        if oid not in by_id:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"binding for unknown obligation {oid}"))
        if oid in seen:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"duplicate binding for {oid}", obligations=[oid]))
        seen.add(oid)
        if sum(k in b for k in ("theorem", "predicate", "declarations")) > 1:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: bind exactly one of theorem/predicate/declarations", obligations=[oid]))
        for n in ([b.get("theorem")] if "theorem" in b else []) + ([b.get("predicate")] if "predicate" in b else []) + b.get("declarations", []):
            try:
                parse_name(n)
            except ValueError as exc:
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{oid}: {exc}", obligations=[oid]))
    for r in records:
        if r["origin"] == "interpreted" and not r["blocked_by"] and r["id"] not in seen:
            diags.append(Diagnostic("STATEMENT_MISMATCH", f"no formal binding proposed for {r['id']}", obligations=[r["id"]]))
        if r["blocked_by"] and r["id"] in seen:
            diags.append(Diagnostic("INTERPRETATION_UNRESOLVED", f"{r['id']} is blocked by {', '.join(r['blocked_by'])} and must not be formalized until resolved", obligations=[r["id"]]))
    ids = {r["id"] for r in records if r["origin"] == "interpreted"}
    for item in form["internal_obligations"]:
        if item["id"] in ids:
            diags.append(Diagnostic("INVALID_CANDIDATE", f"internal obligation {item['id']} reuses an existing ID"))
        ids.add(item["id"])
        for aid in item["witnesses_for"]:
            if by_id.get(aid, {}).get("role") != "assumption":
                diags.append(Diagnostic("INVALID_CANDIDATE", f"{item['id']} witnesses {aid}, which is not an assumption record"))
    if form["lean_toolchain"].strip() not in SUPPORTED_TOOLCHAINS:
        diags.append(Diagnostic("UNSUPPORTED_CAPABILITY", f"Lean toolchain {form['lean_toolchain']!r} is not supported; supported: {', '.join(SUPPORTED_TOOLCHAINS)}"))
    return diags


def contract_claims(records: list[dict[str, Any]], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    assumptions = {a["id"]: a for a in ledger.get("assumptions", [])}
    out = []
    for r in records:
        app = applicability(r, assumptions)
        for m in CONTRACT_MILESTONES:
            applicable, reason = app[m]
            out.append({
                "claim_id": claim_id(m, r["id"], r["revision"]),
                "obligation": r["id"],
                "milestone": m,
                "required": bool(r["required"] and applicable),
                "applicable": applicable,
                "verifier": (VERIFIER if m == "INTERPRETED" and r["origin"] == "derived"
                             else MILESTONE_VERIFIER[m]),
                "pass_predicate": PASS_PREDICATE[m],
                "severity": "blocking" if r["required"] and applicable else "advisory",
                "reason": reason if not applicable else ("blocked by " + ", ".join(r["blocked_by"]) if r["blocked_by"] else "required by role and interpretation"),
            })
    return out


def attempt(tc: leanbridge.Toolchain, pol: dict[str, Any], records: list[dict[str, Any]], source: bytes,
            form: dict[str, Any], events: EventSink, frontend: Any = None) -> dict[str, Any]:
    """One statement-check attempt. Returns a dict with diagnostics and, on success, artifacts."""
    out: dict[str, Any] = {"diagnostics": []}
    if frontend is not None and (frontend.source != source or frontend.formalization != form):
        out["diagnostics"].append(Diagnostic("IR_REIFICATION_MISMATCH", "typed compiler artifacts changed before statement checking"))
        return out
    active = [r for r in records if not r["blocked_by"]]
    registry = contract.registry_lean(active, contract.binding_names(form))
    composed, imports, problems = contract.compose_challenge(source, registry)
    out["composed"] = composed
    for p in problems:
        out["diagnostics"].append(Diagnostic("INVALID_CANDIDATE", p))
    for imp in imports:
        if imp.split(".")[0] not in pol["allowed_import_roots"]:
            out["diagnostics"].append(Diagnostic("UNDECLARED_DEPENDENCY", f"import {imp} is outside the allowed toolchain roots"))
    if out["diagnostics"]:
        return out
    with fsutil.temporary_directory(prefix="verislop-formalize-") as tmp:
        events.emit("progress", "formalize", "elaborating the composed challenge in the sandbox")
        comp = leanbridge.compile_module(tc, composed, Path(tmp) / "build", timeout=pol["build_timeout_seconds"],
                                         memory_mb=pol["memory_mb"], require_network_isolation=pol["require_network_isolation"])
        out["compile"] = {"ok": comp.ok, "errors": comp.errors[:50], "sorry_positions": comp.sorry_positions,
                          "isolation": comp.isolation, "wall_ms": int(comp.wall_seconds * 1000)}
        if not comp.ok:
            out["diagnostics"].append(Diagnostic("CANDIDATE_BUILD_FAILURE", "the challenge does not elaborate: " + "; ".join(comp.errors[:5])))
            return out
        if frontend is not None:
            from .formal_frontend import kernel_audit_requests
            requests = kernel_audit_requests(frontend)
            events.emit("progress", "formalize", f"kernel audit of {len(requests)} typed-proposal denotations")
            resp = leanbridge.run_kernel_tool(tc, comp.olean, {"defeq": requests},
                                             timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                             require_network_isolation=pol["require_network_isolation"])
            out["frontend_defeq"] = resp.get("defeq", [])
            out["diagnostics"].extend(contract.defeq_diagnostics(resp, "typed formalizer compiler"))
            if any(d.severity in ("blocking", "infrastructure") for d in out["diagnostics"]):
                return out
        events.emit("progress", "formalize", "kernel replay and export of the challenge")
        export = leanbridge.run_kernel_tool(tc, comp.olean, {"export": True, "axioms": True},
                                            timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                            require_network_isolation=pol["require_network_isolation"])
        env = contract.Env.from_export(export, pol, "challenge")
        out["diagnostics"].extend(env.diagnostics)
        if any(d.severity == "blocking" for d in env.diagnostics):
            return out
        closure_id, cdiags = leanbridge.olean_closure_identity(tc, export["import"]["modules"])
        out["diagnostics"].extend(cdiags)
        out["olean_closure"] = closure_id
        analysis = contract.analyze(env, records, form, pol, form["lean_toolchain"].strip(), "challenge")
        out["diagnostics"].extend(analysis.diagnostics)
        out["analysis"] = analysis
        out["export"] = export
        out["decl_hashes"] = env.hashes
        if any(d.severity == "blocking" for d in out["diagnostics"]):
            return out
        if analysis.defeq_requests:
            events.emit("progress", "formalize", f"kernel definitional-equality check of {len(analysis.defeq_requests)} DSL denotations")
            resp = leanbridge.run_kernel_tool(tc, comp.olean, {"defeq": analysis.defeq_requests},
                                              timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                              require_network_isolation=pol["require_network_isolation"])
            out["diagnostics"].extend(contract.defeq_diagnostics(resp, "challenge"))
            out["defeq"] = resp.get("defeq", [])
    return out


def _records(draft: dict[str, Any], ledger: dict[str, Any], form: dict[str, Any] | None) -> list[dict[str, Any]]:
    blocked = blocked_obligations(draft, ledger)
    recs = contract.interpreted_records(draft, blocked)
    if isinstance(form, dict) and isinstance(form.get("internal_obligations"), list):
        by_id = {r["id"]: r for r in recs}
        for item in form["internal_obligations"]:
            if isinstance(item, dict) and all(a in by_id for a in item.get("witnesses_for", [])) and item.get("witnesses_for"):
                recs.append(contract.derived_non_vacuity(item, by_id))
    return recs


def _structurally_trivial(formula: Any) -> bool:
    """Recognize a few output-independent tautologies without unfolding definitions.

    This is proposal readiness, not a complete tautology or NL-equivalence checker.
    In particular, ``solve x = primitive_pipeline x`` remains meaningful even when
    Lean can prove it by reflexivity after unfolding the model definition.
    """
    if not isinstance(formula, dict):
        return False
    tag = formula.get("tag")
    if tag == "true":
        return True
    if tag in ("eq", "iff"):
        return formula.get("left") == formula.get("right")
    if tag == "forall":
        return _structurally_trivial(formula.get("body"))
    if tag == "and":
        return _structurally_trivial(formula.get("left")) and _structurally_trivial(formula.get("right"))
    if tag == "or":
        return _structurally_trivial(formula.get("left")) or _structurally_trivial(formula.get("right"))
    if tag == "implies":
        return (formula.get("left") == formula.get("right")
                or formula.get("left") == {"tag": "false"}
                or _structurally_trivial(formula.get("right")))
    return tag == "not" and formula.get("body") == {"tag": "false"}


def executable_readiness(records: list[dict[str, Any]], analysis: contract.Analysis,
                         requested: dict[str, Any]) -> list[Diagnostic]:
    """Repair opaque agent proposals before freezing a requested Python campaign.

    This is candidate selection, not a relaxation of acceptance or a source rewrite.
    Explicit candidates and standalone formalization retain opaque Lean support.
    Applicability and implementation-symbol coverage match the later claim inventory.
    """
    if not requested or requested.get("target") not in (None, "python"):
        return []
    from .capabilities import normalize_endpoint

    tier = requested.get("tier") if requested.get("tier") is not None else 0
    if tier not in (0, 1):
        return []
    endpoint = normalize_endpoint(requested.get("endpoint"), tier)
    if requested.get("require_state") != "TESTED" and endpoint != "test_campaign":
        return []
    declarations = {s["lean_decl"] for s in (analysis.profile or {}).get("symbols", {}).values()}
    diags = []
    for rec in records:
        oid = rec["id"]
        if not rec["required"] or rec["blocked_by"] or not applicability(rec)["TESTED"][0]:
            continue
        statement = analysis.statements[oid]
        if not declarations.intersection(statement["semantic_closure"]):
            diags.append(Diagnostic(
                "INVALID_CANDIDATE",
                f"{oid}: the requested Python TESTED/test_campaign needs an executable guarantee about an "
                "admitted implementation symbol, but this candidate has no such symbol in its semantic closure. "
                "Repair the exact previous source and binding manifest to model the requested operation and "
                "its observable behavior faithfully. A constant True predicate, reflexive input equality or "
                "unbound opaque predicate cannot substitute for the requested behavior. Do not weaken, remove "
                "or make this guarantee optional. If the domain cannot be represented, report that capability gap.",
                obligations=[oid], details={"representation": statement["representation"],
                                           "missing_implementation_symbol": True, "requested": requested}))
        if statement["representation"] == "contract_dsl":
            if _structurally_trivial(statement.get("formula_package", {}).get("formula")):
                diags.append(Diagnostic(
                    "INVALID_CANDIDATE", f"{oid}: this executable guarantee is structurally tautological and "
                    "cannot constrain an implementation. State the requested observable result against fixed "
                    "primitives, retaining all guards and requirements; do not compare an expression with itself.",
                    obligations=[oid], details={"structurally_trivial_guarantee": True}))
            continue
        reason = statement.get("opaque_reason") or "the accepted expression is outside the executable contract DSL"
        diags.append(Diagnostic(
            "INVALID_CANDIDATE",
            f"{oid}: the requested Python TESTED/test_campaign needs an executable contract_dsl statement, "
            f"but this candidate reifies as {statement['representation']}: {reason}. Repair the exact previous source and binding "
            "manifest with a faithful equivalent statement in the supported DSL; preserve every requirement, "
            "quantifier, branch guard and dependency. Do not weaken, remove or make this guarantee optional. "
            "For an inline conditional value, equivalent guarded branch implications may avoid the unsupported term.",
            obligations=[oid], details={"representation": statement["representation"], "opaque_reason": reason,
                                       "requested": requested}))
    return diags


def run(
    pkg: Package,
    events: EventSink,
    *,
    draft_path: Path | None = None,
    out: Path | None = None,
    candidate: Path | None = None,
    policy_name: str = "strict",
    agent: Callable[[dict[str, Any]], tuple[bytes, dict[str, Any]]] | None = None,
    max_attempts: int = 3,
    recovery_feedback: list[str] | None = None,
    previous_candidate: dict[str, Any] | None = None,
) -> StageResult:
    pol = policymod.get(policy_name)
    if draft_path is not None:
        pkg.set_path("draft", draft_path)
    if out is not None:
        pkg.set_path("contract", out)
    events.emit("stage_started", "formalize", "formalizing the interpreted claims")
    result = StageResult("formalize", "PASS", "statement-checked challenge frozen before proof search")
    draft, ledger, idiags = require_interpretation(pkg)
    if idiags:
        result.diagnostics.extend(idiags)
        result.status = status_from(result.diagnostics)
        return result

    existing = contract.challenge_dir(pkg) / "challenge.json"
    if existing.is_file():
        ch, fdiags = contract.load_frozen(pkg)
        if fdiags:
            result.diagnostics.extend(fdiags)
            result.status = "BLOCKED"
            return result
        if candidate is None and agent is None:
            result.lines.append("challenge already frozen; nothing to do")
            result.summary["contract_input_root"] = ch["contract_input_root"]
            return result
        src, form = load_candidate_dir(candidate) if candidate else (None, None)
        frozen_form = contract.frozen_json(pkg, "formalization.json")
        if candidate and canonical.dumps(form) == canonical.dumps(frozen_form):
            result.lines.append("identical candidate; the frozen challenge is unchanged")
            result.summary["contract_input_root"] = ch["contract_input_root"]
            return result
        result.diagnostics.append(Diagnostic(
            "CLAIM_MUTATION",
            "a challenge is already frozen in this run; a changed statement starts a new candidate in a new run package "
            "(the frozen run is preserved)"))
        result.status = "BLOCKED"
        return result

    tc = leanbridge.resolve_toolchain(leanbridge.DEFAULT_TOOLCHAIN)
    feedback: list[str] = list(recovery_feedback or [])
    prior_candidate = previous_candidate
    last: dict[str, Any] = {}
    form: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    candidate_origin: dict[str, Any] | None = None
    attempts = 1 if candidate else max(1, max_attempts)
    source_kind = "candidate_dir" if candidate else "agent"
    for n in range(attempts):
        if candidate:
            source, form = load_candidate_dir(candidate)
        elif agent:
            records = _records(draft, ledger, None)
            source, form = agent({"draft": draft, "ledger": ledger, "records": records, "feedback": feedback,
                                  "attempt": n + 1, "previous_candidate": prior_candidate,
                                  "requested": dict(pkg.meta().get("requested", {}))})
            candidate_origin = getattr(agent, "last_origin", None)
        else:
            raise UsageError("no formalizer available: configure a `formalizer` role with --config, or pass --candidate DIR")
        events.emit("candidate_proposal", "formalize", f"formalization candidate (attempt {n + 1})", details={"source": source_kind})
        records = _records(draft, ledger, form)
        cdiags = validate_candidate(form, records)
        if cdiags:
            last = {"diagnostics": cdiags}
        else:
            frontend = getattr(agent, "last_compiled", None) if candidate is None else None
            last = (attempt(tc, pol, records, source, form, events, frontend=frontend) if frontend is not None
                    else attempt(tc, pol, records, source, form, events))
        if candidate is None and not any(d.severity in ("blocking", "infrastructure") for d in last["diagnostics"]):
            last["diagnostics"].extend(executable_readiness(records, last["analysis"], pkg.meta().get("requested", {})))
        if not any(d.severity in ("blocking", "infrastructure") for d in last["diagnostics"]):
            break
        feedback = [d.message for d in last["diagnostics"] if d.severity != "warning"]
        prior_candidate = {"lean_source": source.decode("utf-8"), "formalization": form}
        if candidate_origin is not None:
            prior_candidate["typed_proposal"] = candidate_origin["proposal"]
        if any(d.severity == "infrastructure" for d in last["diagnostics"]):
            break

    diags: list[Diagnostic] = last["diagnostics"]
    ok = not any(d.severity in ("blocking", "infrastructure") for d in diags)
    cand_dir = pkg.path("contract") / "candidate"
    # Keep the generator's exact input separately from the supervisor-composed registry.
    # Recovery in a new package must not accidentally resubmit the generated registry.
    fsutil.atomic_write(cand_dir / "proposal.lean", source)
    if "composed" in last:
        fsutil.atomic_write(cand_dir / "Contract.lean", last["composed"])
    if isinstance(form, dict):
        fsutil.write_json(cand_dir / "formalization.json", form)
    for name in ("typed-proposal.json", "compiler-origin.json"):
        (cand_dir / name).unlink(missing_ok=True)
    if candidate_origin is not None:
        fsutil.write_json(cand_dir / "typed-proposal.json", candidate_origin["proposal"])
        fsutil.write_json(cand_dir / "compiler-origin.json", candidate_origin["receipt"])
    fsutil.write_json(cand_dir / "statement-check.json", {
        "diagnostics": [d.to_json() for d in diags],
        "compile": last.get("compile"),
        "defeq": last.get("defeq"),
        "frontend_defeq": last.get("frontend_defeq"),
    }, pretty=True)
    result.artifacts["candidate"] = pkg.rel(cand_dir)

    if not ok:
        cand_root = fsutil.manifest_root(fsutil.manifest_tree(cand_dir, pkg.rel(cand_dir)))
        failed = sorted({o for d in diags for o in d.obligations}) or [r["id"] for r in records if not r["blocked_by"]]
        by_id = {r["id"]: r for r in records}
        for oid in failed:
            r = by_id.get(oid)
            if r is None:
                continue
            pkg.evidence.record(
                claim_id=claim_id("FORMALIZED", oid, r["revision"]), verifier_id=VERIFIER, status="BLOCK",
                scope=["formal statement check of a rejected formalization candidate"], input_root=cand_root,
                result={"milestone_outcome": "FAIL", "binding_root": "contract_candidate_root",
                        "diagnostics": [d.to_json() for d in diags if oid in d.obligations or not d.obligations]},
                invocation=["verislop", "formalize"])
        pkg.set_meta("contract_candidate_root", cand_root)
        result.diagnostics.extend(diags)
        result.status = status_from(diags)
        return result

    # ---- freeze -----------------------------------------------------------------------------
    analysis: contract.Analysis = last["analysis"]
    chdir = contract.challenge_dir(pkg)
    chdir.mkdir(parents=True, exist_ok=True)
    statements = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "frozen_statements",
        "profile_registry_hash": canonical.digest_json(analysis.profile),
        "challenge_environment_hash": canonical.digest_json(last["export"]),
        "olean_closure": last["olean_closure"],
        "declaration_hashes": dict(sorted(last["decl_hashes"].items())),
        "statements": analysis.statements,
    }
    verifiers = {
        "kernel_tool": leanbridge.kernel_tool_hash(),
        "verislop.formal-statement-checker": verifier_hash(VERIFIER),
        "verislop.lean-acceptance": verifier_hash("verislop.lean-acceptance"),
        "verislop.reifier": verifier_hash("verislop.reifier"),
        "schemas": schemas.all_schema_hashes(),
    }
    fsutil.write_once(chdir / "Contract.lean", last["composed"])
    fsutil.write_json(chdir / "formalization.json", form, once=True)
    fsutil.write_json(chdir / "profile.json", analysis.profile, once=True)
    fsutil.write_json(chdir / "statements.json", statements, once=True)
    fsutil.write_json(chdir / "policy.json", pol, once=True)
    fsutil.write_once(chdir / "lean-toolchain", (form["lean_toolchain"].strip() + "\n").encode())
    fsutil.write_json(chdir / "verifiers.json", verifiers, once=True)
    claims = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "contract_claims",
        "bound_to": {"interpretation_root": pkg.interpretation_root(), "request": pkg.file_digest("prompt")},
        "parameters": {"policy": pol["id"], "profile_id": form["profile_id"], "lean_toolchain": form["lean_toolchain"].strip()},
        "obligations": records,
        "claims": contract_claims(records, ledger),
    }
    issues = schemas.validate("claims", claims)
    if issues:
        raise UsageError(f"internal claims inventory failed schema validation: {issues[0]}")
    fsutil.write_json(pkg.path("claims"), claims, once=True)
    manifest = fsutil.manifest_for(contract.challenge_inputs(pkg))
    root = fsutil.manifest_root(manifest)
    fsutil.write_json(chdir / "challenge.json", {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "frozen_challenge",
        "manifest": manifest,
        "contract_input_root": root,
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "toolchain": tc.identity(),
        "sandbox": last["compile"]["isolation"],
    }, once=True)
    fsutil.make_readonly_tree(chdir)
    events.emit("verifier_decision", "formalize", f"challenge frozen; contract input root {root[:19]}…")

    for r in records:
        if r["blocked_by"]:
            continue
        if r["origin"] == "derived":
            # Derived obligations carry derived provenance recorded by the registered rule.
            pkg.evidence.record(
                claim_id=claim_id("INTERPRETED", r["id"], r["revision"]), verifier_id=VERIFIER, status="PASS",
                scope=["derived provenance (registered rule verislop.non-vacuity/0.1); not user-stated, not proof"],
                input_root=root,
                result={"milestone_outcome": "PASS", "binding_root": "contract_input_root",
                        "reason": "derived by registered formalization rule verislop.non-vacuity/0.1",
                        "record_digest": r["record_digest"]},
                invocation=["verislop", "formalize"])
        st = analysis.statements[r["id"]]
        ev = pkg.evidence.record(
            claim_id=claim_id("FORMALIZED", r["id"], r["revision"]), verifier_id=VERIFIER, status="PASS",
            scope=[f"contract input root {root}", "formal statement bound and checked; not proved"],
            input_root=root,
            result={"milestone_outcome": "PASS", "binding_root": "contract_input_root",
                    "representation": st["representation"], "lean_symbol": st["lean_symbol"],
                    "statement_hash": st["statement_hash"], "bindings": st["bindings"]},
            invocation=["verislop", "formalize", "--policy", policy_name])
        events.emit("verifier_decision", "formalize", f"{r['id']} FORMALIZED ({st['representation']})",
                    obligation_id=r["id"], milestone="FORMALIZED", outcome="PASS", evidence_ref=f"evidence:{ev.id}")
    result.diagnostics.extend(diags)
    for r in records:
        if r["blocked_by"]:
            result.diagnostics.append(Diagnostic(
                "INTERPRETATION_UNRESOLVED", f"{r['id']} was not formalized: blocked by {', '.join(r['blocked_by'])}",
                obligations=[r["id"]]))
    result.status = status_from(result.diagnostics)
    result.artifacts.update({"challenge": pkg.rel(chdir), "claims": pkg.rel(pkg.path("claims"))})
    result.summary.update({
        "contract_input_root": root,
        "statements": {k: {"representation": v["representation"], "display": v.get("display"),
                           "hypotheses": v["hypotheses"]} for k, v in analysis.statements.items()},
    })
    for k, v in analysis.statements.items():
        if v.get("display"):
            result.lines.append(f"{k}: {v['display']}")
        elif v["representation"] == "lean_expr":
            result.lines.append(f"{k}: opaque Lean statement ({v.get('opaque_reason')})")
    return result
