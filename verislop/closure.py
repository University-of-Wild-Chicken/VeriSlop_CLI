"""`verislop verify`: frozen closure, two isolated clean builds, provenance and the report.

Closure sequence (specification §10.2): re-verify frozen inputs and imported certificates,
perform two isolated clean builds, compare declared reproducible outputs, check that every
required claim resolves to current registered evidence over frozen inputs, check the semantic
boundary (endpoint) and the configured review gate, record closure evidence, and emit the
authoritative `report.json`. VERIFIED is always qualified by the tier and the trust boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import canonical, contract as C, dsl, fsutil, leanbridge, schemas
from .claimcheck import evaluate_claim
from .capabilities import normalize_endpoint
from .errors import Diagnostic, InfrastructureError
from .events import EventSink
from .export import reconstruct, verified_ir
from .lifecycle import MILESTONES, claim_id
from .package import Package
from .stage import StageResult
from .targets import python_target as pt
from .verifiers import VERIFIERS, registry_snapshot

VERIFIER = "verislop.closure"
NONDETERMINISTIC_FIELDS = ["recorded_at", "time", "wall_ms", "frozen_at", "staged candidate module path"]
FINAL_CLAIMS = {
    "CLOSURE:clean-builds": "CLEAN_BUILD_FAILURE",
    "CLOSURE:determinism": "NONDETERMINISM",
    "CLOSURE:provenance": "STALE_OR_UNBOUND_EVIDENCE",
    "CLOSURE:endpoint": "UNSUPPORTED_CAPABILITY",
}


def closure_manifest(pkg: Package) -> dict[str, Any] | None:
    from .backends import registry as backend_registry

    backend, dispatch_diags = backend_registry.frozen_backend(pkg)
    if dispatch_diags:
        return None
    if backend and backend["id"] == backend_registry.VSCORE_ID:
        from .backends import vscore_closure

        return vscore_closure.closure_manifest(pkg)
    files: dict[str, Path] = {}
    needed = {
        "claims.json": pkg.path("claims"),
        "closure/implementation-claims.json": pkg.path("closure") / "implementation-claims.json",
        "accepted/acceptance.json": pkg.path("accepted") / "acceptance.json",
        "accepted/accepted-ir.json": pkg.path("accepted_ir"),
        "bridges/bindings.json": pkg.path("bridges") / "bindings.json",
        "contract/challenge/challenge.json": C.challenge_dir(pkg) / "challenge.json",
    }
    if not all(p.is_file() for p in needed.values()):
        return None
    files.update(needed)
    campaign = pkg.path("tests") / "campaign.json"
    if campaign.is_file():
        files["tests/campaign.json"] = campaign
    monitors = pkg.path("bridges") / "tier1"
    if monitors.is_dir():
        for rel in fsutil.list_files(monitors):
            files[f"bridges/tier1/{rel}"] = monitors / rel
    impl = pkg.path("implementation")
    if impl.is_dir():
        for rel in fsutil.list_files(impl):
            files[f"implementation/{rel}"] = impl / rel
    return fsutil.manifest_for(files)


def closure_input_root(pkg: Package) -> str | None:
    from .backends import registry as backend_registry

    backend, dispatch_diags = backend_registry.frozen_backend(pkg)
    if dispatch_diags:
        return None
    if backend and backend["id"] == backend_registry.VSCORE_ID:
        from .backends import vscore_closure

        return vscore_closure.closure_input_root(pkg)
    m = closure_manifest(pkg)
    if m is None:
        return None
    return canonical.digest_json({
        "manifest_root": fsutil.manifest_root(m),
        "verifier_registry": canonical.digest_json(registry_snapshot()),
        "schemas": canonical.digest_json(schemas.all_schema_hashes()),
    })


def clean_build(pkg: Package, label: str, cert: dict[str, Any], cert_hash: str, irj: dict[str, Any],
                impl_claims: dict[str, Any], link: dict[str, Any] | None, run_tests: bool) -> dict[str, Any]:
    """One isolated build of every declared reproducible output, from frozen bytes only."""
    from . import accept, testing

    out: dict[str, Any] = {"build": label, "ok": True, "errors": []}
    pol = C.frozen_json(pkg, "policy.json")
    form = C.frozen_json(pkg, "formalization.json")
    claims = canonical.load_file(pkg.path("claims"))
    active = [r for r in claims["obligations"] if not r["blocked_by"]]
    tc = leanbridge.resolve_toolchain(cert["toolchain"]["pin"])
    with fsutil.temporary_directory(prefix=f"verislop-build-{label}-") as tmp:
        tmpd = Path(tmp)
        src = (pkg.root / cert["artifacts"]["source"]["path"]).read_bytes()
        comp = leanbridge.compile_module(tc, src, tmpd / "contract", timeout=pol["build_timeout_seconds"],
                                         memory_mb=pol["memory_mb"], require_network_isolation=pol["require_network_isolation"])
        if not comp.ok:
            out["ok"] = False
            out["errors"].append("contract build failed: " + "; ".join(comp.errors[:3]))
        else:
            olean = comp.olean.read_bytes()
            out["olean"] = canonical.digest(olean)
            exp = leanbridge.run_kernel_tool(tc, comp.olean, accept.kernel_request(form, active),
                                             timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                             require_network_isolation=pol["require_network_isolation"])
            out["environment_export"] = canonical.digest(canonical.dumps(exp))
            ir, _files, _reif, rdiags = reconstruct(pkg, cert, cert_hash, exp, olean)
            if ir is None:
                out["ok"] = False
                out["errors"].extend(d.message for d in rdiags[:3])
            else:
                out["accepted_ir"] = canonical.digest(canonical.dumps(ir))
        impl = pkg.path("implementation")
        impl_copy = tmpd / "implementation"
        files = fsutil.list_files(impl)
        fsutil.copy_files(impl, impl_copy, files)
        bc = pt.byte_compile(impl_copy, files, tmpd / "pyc")
        out["pyc"] = bc["pyc"]
        if not bc["ok"]:
            out["ok"] = False
            out["errors"].append("implementation byte compilation failed: " + "; ".join(bc["errors"][:3]))
        if run_tests and link is not None and (pkg.path("tests") / "campaign.json").is_file():
            cfg = canonical.load_file(pkg.path("tests") / "campaign.json")
            profile = dsl.Profile.from_json(C.frozen_json(pkg, "profile.json"))
            res = testing.execute(impl_copy, link, impl_claims, irj, profile, cfg, pkg.path("accepted") / "expressions", {})
            out["tests"] = {oid: {"outcome": r["outcome"], "codes": r["codes"], "counts": r["detail"].get("counts")}
                            for oid, r in sorted(res["obligations"].items())}
    return out


def _lifecycle_code(entry: dict[str, Any], milestone: str) -> str:
    outcome = entry["outcome"]
    if outcome == "PENDING":
        return "VERIFIER_NOT_RUN"
    if outcome == "STALE":
        return "STALE_OR_UNBOUND_EVIDENCE"
    if outcome == "UNSUPPORTED":
        return "UNSUPPORTED_SEMANTICS"
    return {"PROVED": "PROOF_UNRESOLVED", "TESTED": "TEST_FAILURE", "LINKED": "UNMAPPED_IMPLEMENTATION_OBJECT",
            "IMPLEMENTED": "CANDIDATE_BUILD_FAILURE", "TYPECHECKED": "STATEMENT_MISMATCH",
            "FORMALIZED": "STATEMENT_MISMATCH", "INTERPRETED": "INTERPRETATION_UNRESOLVED",
            "END_TO_END_VERIFIED": "NON_MECHANICAL_CORRESPONDENCE"}[milestone]


def run(pkg: Package, events: EventSink, *, endpoint: str | None = None, require_state: str | None = None,
        config: Path | None = None) -> StageResult:
    from .backends import registry as backend_registry

    backend, dispatch_diags = backend_registry.frozen_backend(pkg)
    if dispatch_diags:
        return StageResult("verify", "BLOCKED", "registered frozen backend", diagnostics=dispatch_diags,
                           summary={"terminal_status": "BLOCKED", "mechanical_status": "BLOCKED"})
    if backend and backend["id"] == backend_registry.VSCORE_ID:
        from .backends import vscore_closure

        return vscore_closure.run(pkg, events, endpoint=endpoint, require_state=require_state, config=config)
    from . import report as reportmod, view

    events.emit("stage_started", "verify", "frozen closure: clean builds, determinism, provenance")
    diags: list[Diagnostic] = []
    builds: list[dict[str, Any]] = []
    determinism: dict[str, Any] = {"compared": [], "mismatches": [], "excluded_nondeterministic_fields": NONDETERMINISTIC_FIELDS}
    impl_claims_p = pkg.path("closure") / "implementation-claims.json"
    impl_claims = canonical.load_file(impl_claims_p) if impl_claims_p.is_file() else None
    params = impl_claims["parameters"] if impl_claims else {}
    requested_ep = normalize_endpoint(endpoint, params.get("tier", 0)) if endpoint else params.get("endpoint")
    req_state = require_state or params.get("require_state")

    # -- 1. frozen inputs and imports -------------------------------------------------------------
    ch, fdiags = C.load_frozen(pkg)
    diags.extend(fdiags)
    irj, ir_hash, cert, idiags = verified_ir(pkg) if ch else (None, None, None, [])
    diags.extend(idiags)
    from .bridges.prepare import verify_preparations

    checked_preparations, preparation_diags = verify_preparations(pkg)
    preparation_results = [{**checked.summary, "status": checked.status, "gate": checked.gate}
                           for checked in checked_preparations]
    diags.extend(preparation_diags)
    if impl_claims is None:
        diags.append(Diagnostic("VERIFIER_NOT_RUN", "the implementation phase has not started (no frozen implementation claims)"))
    elif irj is not None and impl_claims["bound_to"].get("accepted_ir") != ir_hash:
        diags.append(Diagnostic("STALE_OR_UNBOUND_EVIDENCE", "implementation claims are bound to a different accepted IR"))
    if impl_claims and requested_ep and requested_ep != params["endpoint"]:
        diags.append(Diagnostic("UNSUPPORTED_CAPABILITY",
                                f"the requested endpoint {requested_ep} is not established by the frozen Tier {params['tier']} bridge "
                                f"(endpoint {params['endpoint']}); a source-level or test result cannot satisfy a different endpoint"))
    if req_state == "END_TO_END_VERIFIED" and params.get("tier", 0) < 2:
        diags.append(Diagnostic("UNSUPPORTED_CAPABILITY", f"END_TO_END_VERIFIED is required but Tier {params.get('tier', 0)} is ineligible"))

    # -- 2. two isolated clean builds --------------------------------------------------------------
    link_p = pkg.path("bridges") / "link.json"
    link = canonical.load_file(link_p) if link_p.is_file() else None
    if irj is not None and cert is not None and impl_claims is not None and not any(d.code == "INPUT_MUTATION" for d in diags):
        cert_bytes = (pkg.path("accepted") / "acceptance.json").read_bytes()
        cert_hash = canonical.digest(cert_bytes)
        run_tests = any(c["milestone"] == "TESTED" and c["required"] for c in impl_claims["claims"])
        for label in ("A", "B"):
            events.emit("progress", "verify", f"isolated clean build {label}")
            try:
                builds.append(clean_build(pkg, label, cert, cert_hash, irj, impl_claims, link, run_tests))
            except InfrastructureError as exc:
                diags.extend(exc.diagnostics)
                builds.append({"build": label, "ok": False, "errors": [exc.message]})
        for b in builds:
            if not b["ok"]:
                diags.append(Diagnostic("CLEAN_BUILD_FAILURE", f"clean build {b['build']} failed: {'; '.join(b['errors'][:3])}"))
        if len(builds) == 2 and all(b["ok"] for b in builds):
            a, b = builds
            stored_tests = {}
            for c in impl_claims["claims"]:
                if c["milestone"] == "TESTED" and c["applicable"]:
                    checked = evaluate_claim(c, pkg.evidence.for_claim(c["claim_id"]), pkg.roots(), "test_root")
                    if checked.authorized and not checked.diagnostics and checked.evidence.status in ("PASS", "BLOCK"):
                        stored_tests[c["obligation"]] = {"outcome": checked.evidence.result.get("milestone_outcome"),
                                                         "codes": checked.evidence.result.get("codes", []),
                                                         "counts": checked.evidence.result.get("counts")}
            expected = {
                "olean": cert["artifacts"]["olean"]["sha256"],
                "environment_export": cert["artifacts"]["environment_export"]["sha256"],
                "accepted_ir": ir_hash,
                "pyc": None,
                "tests": stored_tests if run_tests else None,
            }
            for key, want in expected.items():
                if key not in a and key not in b:
                    continue
                determinism["compared"].append(key)
                if canonical.dumps(a.get(key)) != canonical.dumps(b.get(key)):
                    determinism["mismatches"].append({"output": key, "build_A": a.get(key), "build_B": b.get(key)})
                    diags.append(Diagnostic("NONDETERMINISM", f"declared reproducible output {key} differs between clean builds"))
                elif want is not None and canonical.dumps(a.get(key)) != canonical.dumps(want):
                    determinism["mismatches"].append({"output": key, "builds": a.get(key), "accepted": want})
                    diags.append(Diagnostic("NONDETERMINISM", f"clean builds reproduce {key} differently from the accepted/recorded value"))

    # -- 3. roots, closure evidence for the endpoint -----------------------------------------------
    root = closure_input_root(pkg)
    if impl_claims and irj is not None and root:
        for c in impl_claims["claims"]:
            if c["milestone"] != "END_TO_END_VERIFIED" or not c["applicable"]:
                continue
            pkg.evidence.record(
                claim_id=c["claim_id"], verifier_id=VERIFIER, status="BLOCK",
                scope=[f"closure root {root}", f"endpoint {params['endpoint']}"], input_root=root,
                result={"milestone_outcome": "UNSUPPORTED", "codes": ["UNSUPPORTED_CAPABILITY"],
                        "reason": f"Tier {params['tier']} ({params['endpoint']}) is ineligible for END_TO_END_VERIFIED: "
                                  "no semantic correspondence to an implementation endpoint is established"},
                invocation=["verislop", "verify"])

    # -- 4. provenance: every required claim resolves to current registered evidence ---------------
    roots = {**pkg.roots(), "closure_root": root, "contract_candidate_root": pkg.meta().get("contract_candidate_root")}
    v = view.derive(pkg, roots)
    for prob in v["evidence_integrity_problems"]:
        diags.append(Diagnostic("STALE_OR_UNBOUND_EVIDENCE", f"evidence {prob['evidence_id']} fails integrity checks: {prob['problems'][0]}"))
    request_assessment = evaluate_claim(
        {"claim_id": "INTERPRETATION:request", "verifier": "verislop.interpretation-recorder",
         "result_predicate": "interpretation-coverage/0.1"},
        pkg.evidence.for_claim("INTERPRETATION:request"), roots, "interpretation_root")
    if request_assessment.outcome != "PASS":
        diags.extend(request_assessment.diagnostics or [Diagnostic(
            "UNCOVERED_SOURCE_CLAUSE", "the recorded interpretation did not pass its checks")])
    all_claims: list[dict[str, Any]] = []
    derived_obligations: set[str] = set()
    if pkg.path("claims").is_file():
        contract_claims = canonical.load_file(pkg.path("claims"))
        all_claims += contract_claims["claims"]
        derived_obligations = {r["id"] for r in contract_claims["obligations"] if r["origin"] == "derived"}
    if impl_claims:
        all_claims += impl_claims["claims"]
    provenance: list[dict[str, Any]] = []
    final_claims: dict[str, dict[str, Any]] = {}
    seen_claims: set[str] = set()
    for c in all_claims:
        if c["claim_id"] in seen_claims:
            diags.append(Diagnostic("ORPHAN_CLAIM", f"duplicate frozen claim {c['claim_id']}", claims=[c["claim_id"]]))
            continue
        seen_claims.add(c["claim_id"])
        if c["verifier"] not in VERIFIERS:
            diags.append(Diagnostic("ORPHAN_CLAIM", f"claim {c['claim_id']} names unregistered verifier {c['verifier']}", claims=[c["claim_id"]]))
            continue
        if not c["required"]:
            continue
        cid = c["claim_id"]
        if cid in FINAL_CLAIMS:
            # These exact supervisor-owned claims are produced only after their inputs have
            # been checked. They must not depend on their own not-yet-created evidence.
            if c["verifier"] != VERIFIER or c["obligation"] is not None or c["milestone"] is not None or not c["applicable"]:
                diags.append(Diagnostic("ORPHAN_CLAIM", f"invalid finalization claim {cid}", claims=[cid]))
            elif cid in final_claims:
                diags.append(Diagnostic("ORPHAN_CLAIM", f"duplicate finalization claim {cid}", claims=[cid]))
            else:
                final_claims[cid] = c
            continue
        if cid.startswith("CLOSURE:"):
            diags.append(Diagnostic("ORPHAN_CLAIM", f"unknown closure finalization claim {cid}", claims=[cid]))
            continue
        if c["obligation"] is None or c["milestone"] is None:
            # Internal bridge claims are required just like obligation milestones. There is
            # no blanket exemption for null obligation IDs or the closure verifier issuer.
            internal = dict(c)
            internal.setdefault("result_predicate", "unregistered-internal-claim/0.1")
            checked = evaluate_claim(internal, pkg.evidence.for_claim(cid), roots, "closure_root")
            entry = checked.entry()
            provenance.append({"claim_id": cid, "outcome": entry["outcome"], "evidence": entry["evidence_refs"],
                               "verifier": c["verifier"], "reason": entry["reason"]})
            if checked.outcome != "PASS":
                diags.extend(checked.diagnostics or [Diagnostic(
                    "NON_MECHANICAL_CORRESPONDENCE", f"{cid}: {checked.outcome} — {checked.reason}", claims=[cid])])
            continue
        rec = v["obligations"].get(c["obligation"])
        if rec is None:
            diags.append(Diagnostic("ORPHAN_CLAIM", f"claim {c['claim_id']} refers to an obligation absent from the view", claims=[c["claim_id"]]))
            continue
        if c["milestone"] not in MILESTONES or cid != claim_id(c["milestone"], c["obligation"], rec["revision"]):
            diags.append(Diagnostic("ORPHAN_CLAIM", f"claim {cid} does not name its exact obligation milestone/revision", claims=[cid]))
            continue
        entry = rec["lifecycle"][c["milestone"]]
        provenance.append({"claim_id": c["claim_id"], "outcome": entry["outcome"], "evidence": entry["evidence_refs"],
                           "verifier": c["verifier"], "reason": entry["reason"]})
        root_kind = ("contract_input_root" if c["milestone"] == "INTERPRETED" and c["obligation"] in derived_obligations
                     else view.DEFAULT_BINDING[c["milestone"]])
        checked = evaluate_claim(c, pkg.evidence.for_claim(cid), roots, root_kind)
        claim_infra = [d for d in checked.diagnostics if d.severity == "infrastructure"]
        diags.extend(claim_infra)
        if entry["outcome"] != "PASS":
            if claim_infra:
                # PENDING is the lifecycle projection of a failed execution service, not
                # evidence that this assigned verifier has never run.
                continue
            code = _lifecycle_code(entry, c["milestone"])
            if "blocked by unresolved ambiguity" in entry["reason"]:
                code = "INTERPRETATION_UNRESOLVED"
            diags.append(Diagnostic(code, f"{c['claim_id']}: {entry['outcome']} — {entry['reason']}",
                                    obligations=[c["obligation"]], claims=[c["claim_id"]]))
    for cid in FINAL_CLAIMS.keys() - final_claims.keys():
        diags.append(Diagnostic("ORPHAN_CLAIM", f"required finalization claim {cid} is absent or invalid", claims=[cid]))

    # -- 5. review gate ------------------------------------------------------------------------------
    review_info: dict[str, Any] = {"configured": False}
    cfg_path = Path(config) if config else (pkg.path("closure") / "review-config.json")
    if cfg_path.is_file():
        from . import review

        review_info = review.gate(pkg, cfg_path)
        diags.extend(review_info.pop("diagnostics", []))

    # -- 6. closure evidence ---------------------------------------------------------------------------
    infra = [d for d in diags if d.severity == "infrastructure"]
    if root:
        builds_ok = len(builds) == 2 and all(b.get("ok") for b in builds)
        checks = {
            "CLOSURE:clean-builds": not any(d.code == "CLEAN_BUILD_FAILURE" for d in diags) and builds_ok,
            "CLOSURE:determinism": not determinism["mismatches"] and builds_ok,
            "CLOSURE:provenance": (request_assessment.outcome == "PASS"
                                   and all(p["outcome"] == "PASS" for p in provenance)
                                   and not any(d.code in ("VERIFIER_NOT_RUN", "STALE_OR_UNBOUND_EVIDENCE", "ORPHAN_CLAIM")
                                               for d in diags)),
            "CLOSURE:endpoint": not any(d.code == "UNSUPPORTED_CAPABILITY" for d in diags),
        }
        for cid, ok in checks.items():
            if cid not in final_claims:
                continue
            pkg.evidence.record(
                claim_id=cid, verifier_id=VERIFIER, status="PASS" if ok else ("INFRASTRUCTURE_FAILURE" if infra and not ok else "BLOCK"),
                scope=[f"closure root {root}"], input_root=root,
                result={"milestone_outcome": "PASS" if ok else "FAIL", "builds": builds, "determinism": determinism},
                invocation=["verislop", "verify"])
            checked = evaluate_claim(final_claims[cid], pkg.evidence.for_claim(cid), roots, "closure_root")
            entry = checked.entry()
            provenance.append({"claim_id": cid, "outcome": entry["outcome"], "evidence": entry["evidence_refs"],
                               "verifier": VERIFIER, "reason": entry["reason"]})
            if checked.outcome != "PASS":
                diags.extend(checked.diagnostics or [Diagnostic(
                    FINAL_CLAIMS[cid], f"{cid}: {checked.outcome} — {checked.reason}", claims=[cid])])
    elif final_claims:
        diags.append(Diagnostic("VERIFIER_NOT_RUN", "closure inputs are incomplete; finalization claims cannot be checked",
                                claims=sorted(final_claims)))
    blocking = [d for d in diags if d.severity == "blocking"]
    infra = [d for d in diags if d.severity == "infrastructure"]
    terminal = "INFRASTRUCTURE_FAILURE" if infra else ("BLOCKED" if blocking else "VERIFIED")
    fsutil.write_json(pkg.path("view"), v, pretty=True)
    rep = reportmod.build(pkg, v, terminal, diags, builds, determinism, params, requested_ep, req_state, root,
                          provenance, review_info, ir_hash, bridge_preparations=preparation_results)
    issues = schemas.validate("report", rep)
    if issues:
        raise RuntimeError(f"internal report failed schema validation: {issues[0]}")
    fsutil.write_json(pkg.path("report"), rep, pretty=True)
    events.emit("run_finished", "verify", rep["qualified_result"], outcome=terminal)
    result = StageResult("verify", {"VERIFIED": "PASS", "BLOCKED": "BLOCKED", "INFRASTRUCTURE_FAILURE": "INFRASTRUCTURE_FAILURE"}[terminal],
                         "closure VERIFIED under the declared trust boundary")
    result.diagnostics = diags
    result.artifacts = {"report": pkg.rel(pkg.path("report")), "obligation_view": pkg.rel(pkg.path("view"))}
    result.summary = {"terminal_status": terminal, "qualified_result": rep["qualified_result"], "closure_root": root}
    result.lines = reportmod.render_lines(rep)
    return result
