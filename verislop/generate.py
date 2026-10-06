"""`verislop generate`: materialize an implementation candidate for a selected bridge tier.

Before any implementation work is handed to an agent (or an existing candidate is ingested),
this stage verifies the accepted IR's reconstruction binding and the certificate, checks the
requested tier/target/endpoint against published capabilities (requested tiers are never
silently downgraded), and freezes the implementation-phase claim inventory. Existing code is
ingested as a candidate implementation, never treated as linked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import SCHEMA_VERSION, canonical, contract as C, fsutil, materialize, schemas
from .capabilities import ENDPOINT_TIER, capability, normalize_endpoint
from .errors import Diagnostic, UsageError
from .events import EventSink
from .export import verified_ir
from .lifecycle import IMPLEMENTATION_MILESTONES, applicability, claim_id
from .package import Package
from .stage import StageResult, status_from

MILESTONE_VERIFIER = {
    "IMPLEMENTED": "verislop.python-materializer",
    "LINKED": "verislop.python-linker",
    "TESTED": "verislop.python-tier0-campaign",
    "END_TO_END_VERIFIED": "verislop.closure",
}
PASS_PREDICATE = {
    "IMPLEMENTED": "every implementation symbol the statement depends on has an existing, byte-compiling object",
    "LINKED": "a unique structural binding connects obligation, accepted declaration and implementation objects",
    "TESTED": "the frozen target campaign ran on the exact artifact with effective cases and no counterexample",
    "END_TO_END_VERIFIED": "checked semantic correspondence to the requested endpoint plus all closure obligations",
}
CLOSURE_CLAIMS = [
    ("CLOSURE:clean-builds", "two isolated clean builds of the accepted contract and the implementation succeed"),
    ("CLOSURE:determinism", "declared reproducible outputs (proof inventory, IR, objects, claim outcomes) are identical across builds"),
    ("CLOSURE:provenance", "every required claim resolves to current registered evidence over frozen inputs"),
    ("CLOSURE:endpoint", "the requested endpoint is established by the selected tier"),
]


def implementation_claims(ir: dict[str, Any], ir_hash: str, cert_hash: str, params: dict[str, Any],
                          profile: dict[str, Any], statements: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    assumptions = {a["id"]: a for a in ledger.get("assumptions", [])}
    tier = params["tier"]
    obligations = []
    claims = []
    for oid, rec in sorted(ir["obligations"].items()):
        obligations.append({
            **{k: rec[k] for k in C.RECORD_FIELDS}, "origin": "derived" if rec["kind"] == "non_vacuity" else "interpreted",
            "record_digest": C.record_digest(rec), "blocked_by": [],
        })
        app = applicability(rec, assumptions)
        syms = materialize.symbols_for(oid, ir, profile, statements)
        for m in IMPLEMENTATION_MILESTONES:
            applicable, reason = app[m]
            if applicable and not syms:
                applicable, reason = False, "the accepted statement depends on no implementation symbol"
            required = bool(rec["required"] and applicable)
            if m == "TESTED" and applicable:
                required = required and params["require_tests"]
                reason = "the release policy requires the target test campaign" if required else "tests not required by the release policy"
            if m == "END_TO_END_VERIFIED" and applicable:
                required = required and params["require_state"] == "END_TO_END_VERIFIED"
                reason = (f"Tier {tier} ({params['endpoint']}) is ineligible for END_TO_END_VERIFIED"
                          if tier < 2 else f"required endpoint {params['endpoint']}")
            claims.append({
                "claim_id": claim_id(m, oid, rec["revision"]), "obligation": oid, "milestone": m,
                "required": required, "applicable": applicable, "verifier": MILESTONE_VERIFIER[m],
                "pass_predicate": PASS_PREDICATE[m], "severity": "blocking" if required else "advisory",
                "reason": reason,
            })
    for cid, pred in CLOSURE_CLAIMS:
        claims.append({"claim_id": cid, "obligation": None, "milestone": None, "required": True, "applicable": True,
                       "verifier": "verislop.closure", "pass_predicate": pred, "severity": "blocking",
                       "reason": "closure obligation of every run"})
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "implementation_claims",
        "bound_to": {"accepted_ir": ir_hash, "certificate": cert_hash, "contract_input_root": ir["contract_input_root"]},
        "parameters": params,
        "obligations": obligations,
        "claims": claims,
    }


def resolve_parameters(pkg: Package, tier: int | None, target: str | None, endpoint: str | None, require_state: str | None,
                       require_tests: bool | None, tests_flag: str | None = None, bridge_id: str | None = None) -> tuple[dict[str, Any], list[Diagnostic]]:
    diags: list[Diagnostic] = []
    req = canonical.load_file(pkg.path("request")) if pkg.path("request").is_file() else {}
    default_applied = False
    if target is None:
        frozen_path = pkg.path("closure") / "implementation-claims.json"
        target = canonical.load_file(frozen_path)["parameters"]["target"] if frozen_path.is_file() else "python"
    if tier is None:
        tier = req.get("tier")
    if tier is None:
        tier, default_applied = 0, True
    ep = normalize_endpoint(endpoint or req.get("endpoint"), tier)
    if ep not in ENDPOINT_TIER:
        raise UsageError(f"unknown endpoint {ep!r}; known: {', '.join(ENDPOINT_TIER)}")
    ok, why = capability(tier, target, ep)
    if not ok:
        diags.append(Diagnostic("UNSUPPORTED_CAPABILITY", f"{why}; requested tiers are never silently downgraded",
                                details={"requested": {"tier": tier, "target": target, "endpoint": ep}}))
    if require_state == "END_TO_END_VERIFIED" and tier < 2:
        diags.append(Diagnostic("UNSUPPORTED_CAPABILITY",
                                f"END_TO_END_VERIFIED was required but Tier {tier} ({ep}) is ineligible for it by definition"))
    if target == "vscore":
        from .backends import admission, registry
        flag = tests_flag or ("omitted" if require_tests is None else "require_tests" if require_tests else "no_tests")
        err, resolved = admission.resolve_params(tier, target, ep, "0.1", require_state, flag)
        if err:
            diags.append(Diagnostic(err, "requested VSCore backend/state/test policy is unsupported; no implementation work was invoked"))
        params = {"tier": tier, "target": target, "endpoint": ep, "backend": registry.VSCORE_ID,
                  "language": "vscore/0.1", "semantics": "vscore-semantics/0.1",
                  "require_state": resolved["state"] if resolved else admission.resolve_state(tier, require_state),
                  "require_tests": resolved["require_tests"] if resolved else admission.resolve_tests(tier, require_state, flag)[1],
                  "bridge_id": bridge_id or "implementation", "tier_default_applied": default_applied}
        return params, diags
    from .backends import admission
    flag = tests_flag or ("omitted" if require_tests is None else "require_tests" if require_tests else "no_tests")
    test_error, require_tests = admission.resolve_tests(tier, require_state, flag)
    if test_error:
        diags.append(Diagnostic(test_error, "--no-tests contradicts --require-state TESTED; a requested campaign cannot be dropped"))
    params = {"tier": tier, "target": target, "endpoint": ep, "require_state": require_state,
              "require_tests": bool(require_tests or tier == 0), "serialization_profile": "python-v0_1",
              "tier_default_applied": default_applied}
    return params, diags


def run(pkg: Package, events: EventSink, *, ir: Path | None = None, tier: int | None = None, target: str | None = None,
        endpoint: str | None = None, require_state: str | None = None, candidate: Path | None = None,
        bindings: Path | None = None, agent: Callable[[dict[str, Any]], tuple[dict[str, bytes], dict[str, Any]]] | None = None,
        require_tests: bool | None = None, tests_flag: str | None = None, bridge_id: str | None = None) -> StageResult:
    events.emit("stage_started", "generate", "verifying the accepted contract before implementation work")
    result = StageResult("generate", "PASS", "implementation candidate materialized for the frozen tier")
    if ir is not None:
        pkg.set_path("accepted_ir", ir)
    irj, ir_hash, cert, diags = verified_ir(pkg)
    if diags:
        result.diagnostics = diags
        result.status = status_from(diags)
        return result
    assert irj is not None and ir_hash and cert is not None
    claims_path = pkg.path("closure") / "implementation-claims.json"
    if claims_path.is_file() and tier is None and endpoint is None and require_state is None:
        # Resume replays frozen bytes; explicit policy changes cannot be ignored.
        params, pdiags = canonical.load_file(claims_path)["parameters"], []
        if target is not None and target != params["target"]:
            pdiags.append(Diagnostic("CLAIM_MUTATION", "changing the frozen implementation target requires a new run package"))
        if require_tests is not None or tests_flag not in (None, "omitted"):
            from .backends import admission
            flag = tests_flag or ("require_tests" if require_tests else "no_tests")
            err, requested_tests = admission.resolve_tests(params["tier"], params["require_state"], flag)
            if err or requested_tests != params["require_tests"]:
                pdiags.append(Diagnostic(err or "CLAIM_MUTATION", "changing the frozen test policy requires a new run package"))
        if bridge_id is not None and params.get("bridge_id") != bridge_id:
            pdiags.append(Diagnostic("CLAIM_MUTATION", "changing the frozen bridge selection requires a new run package"))
    else:
        params, pdiags = resolve_parameters(pkg, tier, target, endpoint, require_state, require_tests, tests_flag, bridge_id)
    if pdiags:
        result.diagnostics = pdiags
        result.status = "BLOCKED"
        result.summary = {"capability": params}
        return result
    if params.get("backend") == "verislop.backend.vscore/0.1":
        from .backends import vscore
        return vscore.generate(pkg, events, irj, ir_hash, cert, params, candidate=candidate,
                               bridge_id=bridge_id, bindings=bindings, agent=agent)
    if bridge_id is not None:
        raise UsageError("--bridge-id selects only the VSCore implementation backend")
    if params["tier_default_applied"]:
        result.diagnostics.append(Diagnostic("UNSUPPORTED_CAPABILITY", "no tier was specified: Tier 0 applies; its outcome is test evidence, not implementation proof", severity="info"))
    profile = C.frozen_json(pkg, "profile.json")
    statements = C.frozen_json(pkg, "statements.json")["statements"]
    ledger = canonical.load_file(pkg.path("interpretation"))
    claims = implementation_claims(irj, ir_hash, canonical.digest((pkg.path("accepted") / "acceptance.json").read_bytes()), params, profile, statements, ledger)
    issues = schemas.validate("claims", claims)
    if issues:
        raise UsageError(f"internal implementation claims failed schema validation: {issues[0]}")
    if claims_path.is_file():
        prev = canonical.load_file(claims_path)
        if prev["parameters"] != claims["parameters"] or prev["bound_to"] != claims["bound_to"]:
            result.diagnostics.append(Diagnostic(
                "CLAIM_MUTATION",
                f"implementation claims are frozen with {prev['parameters']} for {prev['bound_to']['accepted_ir'][:19]}…; "
                "changing tier, endpoint, target or contract after freeze starts a new candidate in a new run package"))
            result.status = "BLOCKED"
            return result
    else:
        fsutil.write_json(claims_path, claims, once=True)

    # -- obtain the candidate ---------------------------------------------------------------------
    impl = pkg.path("implementation")
    if candidate is not None:
        src = Path(candidate)
        if not src.is_dir():
            raise UsageError(f"--candidate {src} must be a directory of implementation sources")
        bpath = Path(bindings) if bindings else src / "bindings.json"
        if not bpath.is_file():
            raise UsageError("an implementation candidate needs a binding proposal (--bindings or bindings.json in the candidate directory)")
        proposal = canonical.load_file(bpath)
        files = {rel: (src / rel).read_bytes() for rel in fsutil.list_files(src) if rel.endswith(".py")}
        source = {"kind": "candidate_dir", "path": str(src)}
    elif agent is not None:
        files, proposal = agent({"ir": irj, "profile": profile, "statements": statements, "parameters": params})
        source = {"kind": "agent", "role": "implementer"}
    else:
        raise UsageError("no implementer available: configure an `implementer` role with --config, or pass --candidate DIR --bindings FILE")
    events.emit("candidate_proposal", "generate", f"implementation candidate with {len(files)} file(s)", details=source)
    bissues = schemas.validate("implementation-bindings", proposal)
    if bissues:
        result.diagnostics.extend(Diagnostic("INVALID_CANDIDATE", f"binding proposal: {i}") for i in bissues[:10])
        result.status = "BLOCKED"
        return result
    if impl.exists():
        fsutil.remove_tree(impl)
    for rel, data in sorted(files.items()):
        fsutil.check_relpath(rel)
        fsutil.atomic_write(impl / rel, data)
    if not files:
        impl.mkdir(parents=True, exist_ok=True)
    fsutil.write_json(pkg.path("bridges") / "bindings.json", proposal, pretty=True)
    result.artifacts.update({"implementation": pkg.rel(impl), "bindings": pkg.rel(pkg.path("bridges") / "bindings.json"),
                             "implementation_claims": pkg.rel(claims_path)})
    diags = materialize.run(pkg, events, irj, profile, statements, claims, proposal)
    if params["tier"] == 1:
        from . import monitors

        diags.extend(monitors.generate(pkg, events, irj, profile, statements, proposal))
    result.diagnostics.extend(diags)
    result.status = status_from(result.diagnostics)
    result.summary = {"parameters": params, "implementation_root": pkg.implementation_root(), "files": sorted(files)}
    result.lines.append(f"tier {params['tier']} -> {params['endpoint']} ({params['target']}, {params['serialization_profile']})")
    return result
