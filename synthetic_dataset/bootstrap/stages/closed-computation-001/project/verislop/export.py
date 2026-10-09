"""`verislop export`: reconstruct the authoritative obligation IR (specification §7).

Only the acceptance certificate's checked environment export, verified declaration set and
accepted `.olean` are opened; candidate plugins are never loaded and the original draft is never
read. The IR (`accepted-ir.json`) is the immutable semantic payload in canonical bytes; the
lifecycle overlay lives in the separate, derived `obligation-view.json`. Re-export from
identical accepted inputs is byte-identical.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, canonical, contract as C, dsl, fsutil, leanbridge, schemas
from .claimcheck import evaluate_claim
from .errors import Diagnostic
from .events import EventSink
from .package import Package
from .stage import StageResult, status_from
from .lifecycle import claim_id
from .verifiers import verifier_hash

VERIFIER = "verislop.reifier"
KNOWN_KINDS = {"entity", "precondition", "postcondition", "invariant", "safety_property", "liveness_property",
               "resource_constraint", "error_semantics", "explicit_non_goal", "ambiguity", "non_vacuity"}


def verify_certificate(pkg: Package, cert_path: Path) -> tuple[dict[str, Any] | None, str | None, list[Diagnostic]]:
    """Verify a certificate's bytes, artifacts, root and its binding to registered evidence."""
    diags: list[Diagnostic] = []
    if not cert_path.is_file():
        return None, None, [Diagnostic("VERIFIER_NOT_RUN", f"no acceptance certificate at {cert_path}; run `verislop accept`")]
    data = cert_path.read_bytes()
    try:
        cert = canonical.loads(data)
    except canonical.CanonicalJSONError as exc:
        return None, None, [Diagnostic("INPUT_MUTATION", f"certificate is not canonical JSON: {exc}")]
    if not isinstance(cert, dict) or cert.get("artifact_kind") != "acceptance_certificate":
        return None, None, [Diagnostic("INVALID_CANDIDATE", f"{cert_path} is not an acceptance certificate (raw drafts and IR are rejected where an accepted artifact is required)")]
    for issue in schemas.validate("acceptance-certificate", cert)[:5]:
        diags.append(Diagnostic("INPUT_MUTATION", f"certificate schema: {issue}"))
    if diags:
        return None, None, diags
    cert_hash = canonical.digest(data)
    for name, art in cert["artifacts"].items():
        p = pkg.root / art["path"]
        if not p.is_file() or canonical.digest(p.read_bytes()) != art["sha256"]:
            diags.append(Diagnostic("INPUT_MUTATION", f"accepted artifact {name} ({art['path']}) was mutated or removed; the certificate is invalid"))
    current_root = pkg.contract_input_root()
    if current_root != cert["contract_input_root"]:
        diags.append(Diagnostic("INPUT_MUTATION", "the frozen challenge no longer matches the certificate's contract input root"))
    _challenge, frozen_diags = C.load_frozen(pkg)
    diags.extend(frozen_diags)
    inventory = canonical.load_file(pkg.path("claims")) if pkg.path("claims").is_file() else None
    if inventory is None or schemas.validate("claims", inventory):
        diags.append(Diagnostic("STALE_OR_UNBOUND_EVIDENCE", "acceptance certificate has no valid frozen claim inventory"))
        return cert, cert_hash, diags
    records = {r["id"]: r for r in inventory["obligations"]}
    if len(records) != len(inventory["obligations"]) or set(records) != set(cert["obligations"]):
        diags.append(Diagnostic("STATEMENT_MISMATCH", "acceptance certificate does not exactly cover the frozen obligations"))
    for oid, r in records.items():
        accepted = cert["obligations"].get(oid)
        if accepted is None:
            continue
        if any(accepted[k] != r[k] for k in ("revision", "kind", "role")):
            diags.append(Diagnostic("STATEMENT_MISMATCH", f"acceptance certificate changes {oid}'s identity", obligations=[oid]))
            continue
        if r["blocked_by"]:
            continue
        for milestone, field in (("TYPECHECKED", "typechecked"), ("PROVED", "proved")):
            outcome = accepted[field]
            if outcome == "NOT_APPLICABLE" and milestone == "PROVED" and r["role"] != "guarantee":
                continue
            cid = claim_id(milestone, oid, r["revision"])
            checked = evaluate_claim({"claim_id": cid, "verifier": "verislop.lean-acceptance"},
                                     pkg.evidence.for_claim(cid), {"contract_input_root": current_root}, "contract_input_root")
            ev = checked.evidence
            if (not checked.authorized or checked.diagnostics or checked.outcome != outcome or ev is None or
                    ev.status != {"PASS": "PASS", "FAIL": "BLOCK"}.get(outcome) or
                    ev.result.get("milestone_outcome") != outcome or
                    ev.result.get("certificate_hash") != cert_hash or
                    ev.result.get("statement_hash") != accepted["statement_hash"] or
                    ev.result.get("axioms") != accepted["axioms"] or ev.result.get("policy") != cert["policy"]["id"]):
                diags.extend(checked.diagnostics or [Diagnostic(
                    "STALE_OR_UNBOUND_EVIDENCE", f"{cid}: no exact assigned acceptance evidence binds this certificate and result",
                    obligations=[oid], claims=[cid])])
    return cert, cert_hash, diags


def verified_ir(pkg: Package, ir_path: Path | None = None) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None, list[Diagnostic]]:
    """Import check used before any implementation work: the IR must be the exporter's output
    for the currently valid certificate (never a raw draft or a hand-edited file)."""
    path = Path(ir_path) if ir_path else pkg.path("accepted_ir")
    if not path.is_file():
        return None, None, None, [Diagnostic("VERIFIER_NOT_RUN", "no accepted IR; run `verislop export` first")]
    data = path.read_bytes()
    try:
        ir = canonical.loads(data)
    except canonical.CanonicalJSONError as exc:
        return None, None, None, [Diagnostic("INPUT_MUTATION", f"accepted IR is not strict JSON: {exc}")]
    if not isinstance(ir, dict) or ir.get("artifact_kind") != "accepted_semantic_ir":
        return None, None, None, [Diagnostic("INVALID_CANDIDATE", f"{path} is not accepted IR; raw drafts are rejected where an accepted artifact is required")]
    diags = [Diagnostic("INPUT_MUTATION", f"accepted IR schema: {i}") for i in schemas.validate("accepted-ir", ir)[:5]]
    ir_hash = canonical.digest(data)
    if diags:
        return ir, ir_hash, None, diags
    cert_path = pkg.root / ir.get("acceptance_certificate_ref", "")
    cert, cert_hash, cdiags = verify_certificate(pkg, cert_path)
    diags.extend(cdiags)
    if cert is not None and cert["gate"] != "accepted_and_proved":
        diags.append(Diagnostic("PROOF_UNRESOLVED", "the contract acceptance gate has not passed"))
    if diags:
        return ir, ir_hash, cert, diags
    if cert is not None:
        if (ir["contract_input_root"] != cert["contract_input_root"] or
                ir["accepted_environment_hash"] != cert["artifacts"]["environment_export"]["sha256"] or
                ir["lean_toolchain"] != cert["toolchain"]["pin"] or ir["exporter_id"] != VERIFIER or
                ir["exporter_hash"] != verifier_hash(VERIFIER)):
            diags.append(Diagnostic("STALE_OR_UNBOUND_EVIDENCE", "accepted IR has stale or inconsistent certificate/exporter bindings"))
        inventory = canonical.load_file(pkg.path("claims"))
        expected = {r["id"]: r for r in inventory["obligations"] if not r["blocked_by"]}
        if set(ir["obligations"]) != set(expected):
            diags.append(Diagnostic("IR_REIFICATION_MISMATCH", "accepted IR does not exactly cover active frozen obligations"))
        for oid, rec in ir["obligations"].items():
            accepted = cert["obligations"].get(oid)
            if (oid not in expected or accepted is None or rec["id"] != oid or
                    any(rec[k] != expected[oid][k] for k in ("revision", "kind", "role")) or
                    any(rec["formal"][k] != accepted[k] for k in ("statement_hash", "lean_symbol", "representation"))):
                diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"{oid}: accepted IR identity differs from its certificate", obligations=[oid]))
                continue
            cid = f"REIFIED:{oid}@{rec['revision']}"
            checked = evaluate_claim({"claim_id": cid, "verifier": VERIFIER}, pkg.evidence.for_claim(cid),
                                     {"acceptance_certificate": cert_hash}, "acceptance_certificate")
            ev = checked.evidence
            check = ev.result.get("check", {}) if ev else {}
            if (checked.outcome != "PASS" or ev is None or ev.result.get("ir_hash") != ir_hash or
                    not isinstance(check, dict) or check.get("certificate") != cert_hash or
                    check.get("statement_hash") != rec["formal"]["statement_hash"] or
                    ev.result.get("reification_ref") != rec["formal"]["reification_evidence_ref"]):
                diags.extend(checked.diagnostics or [Diagnostic(
                    "STALE_OR_UNBOUND_EVIDENCE", f"{cid}: no exact assigned reifier evidence binds these IR bytes",
                    obligations=[oid], claims=[cid])])
    return ir, ir_hash, cert, diags


def mechanical_dependencies(oid: str, st: dict[str, Any], statements: dict[str, dict[str, Any]],
                            cert_obl: dict[str, Any], registry_entry: dict[str, Any],
                            witnesses_for: dict[str, list[str]]) -> list[dict[str, str]]:
    deps: set[tuple[str, str]] = set()
    for h in st["hypotheses"]:
        deps.add((h, "assumes"))
        for w, covers in witnesses_for.items():
            if h in covers:
                deps.add((w, "requires_witness"))
    closure = set(st["semantic_closure"])
    for other, ost in statements.items():
        if other == oid or ost["role"] not in ("declaration", "assumption"):
            continue
        if set(ost["bindings"]) & closure:
            if ost["role"] == "declaration" or oid in witnesses_for:
                deps.add((other, "uses_definition"))
    for u in cert_obl.get("uses_proof", []):
        deps.add((u, "uses_proof"))
    for d in registry_entry["dependencies"]:
        if d["relation"] in ("refines", "requires_bridge"):
            deps.add((d["id"], d["relation"]))
    order = ["assumes", "uses_definition", "uses_proof", "requires_witness", "refines", "requires_bridge"]
    return [{"id": i, "relation": r} for i, r in sorted(deps, key=lambda x: (order.index(x[1]), x[0]))]


def reconstruct(pkg: Package, cert: dict[str, Any], cert_hash: str, export: dict[str, Any], olean_bytes: bytes
                ) -> tuple[dict[str, Any] | None, dict[str, bytes], dict[str, dict[str, Any]], list[Diagnostic]]:
    """Pure reconstruction of the IR from an environment export (no files written).

    Used by `export` on the certificate's artifacts and by the closure verifier on clean rebuilds.
    """
    diags: list[Diagnostic] = []
    pol = C.frozen_json(pkg, "policy.json")
    form = C.frozen_json(pkg, "formalization.json")
    frozen_st = C.frozen_json(pkg, "statements.json")
    claims = canonical.load_file(pkg.path("claims"))
    records = claims["obligations"]
    profile_json = canonical.load_file(pkg.root / cert["artifacts"]["profile"]["path"])
    profile = dsl.Profile.from_json(profile_json)
    env = C.Env.from_export(export, pol, "accepted environment")
    diags.extend(env.diagnostics)

    # 2. enumerate the accepted typed obligation registry
    try:
        registry = C.decode_registry(env.decls)
    except C.RegistryError as exc:
        diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"accepted registry cannot be decoded: {exc}"))
        registry = []
    reg: dict[str, dict[str, Any]] = {}
    for e in registry:
        if e["id"] in reg:
            diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"duplicate registry ID {e['id']}", obligations=[e["id"]]))
        if e["kind"] not in KNOWN_KINDS:
            diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"unknown obligation kind {e['kind']!r}", obligations=[e["id"]]))
        reg[e["id"]] = e
    for r in records:
        if r["blocked_by"]:
            continue
        e = reg.get(r["id"])
        if e is None:
            diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"required registry entry {r['id']} is missing", obligations=[r["id"]]))
        elif e["revision"] != r["revision"]:
            diags.append(Diagnostic("CLAIM_MUTATION", f"{r['id']} revision changed ({r['revision']} -> {e['revision']})", obligations=[r["id"]]))

    # 3-6. resolve symbols, reify statements, round trip, kernel denotation check
    analysis = C.analyze(env, records, form, pol, cert["toolchain"]["pin"], "accepted environment")
    diags.extend(d for d in analysis.diagnostics if d.severity != "warning")
    if analysis.profile is not None and canonical.dumps(analysis.profile) != canonical.dumps(profile_json):
        diags.append(Diagnostic("IR_REIFICATION_MISMATCH", "the profile reconstructed from accepted declarations differs from its bound artifact"))
    for oid, st in analysis.statements.items():
        want = cert["obligations"].get(oid, {}).get("statement_hash")
        if st["statement_hash"] != want or st["statement_hash"] != frozen_st["statements"].get(oid, {}).get("statement_hash"):
            diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"{oid}: reconstructed statement hash differs from the certificate/frozen challenge", obligations=[oid]))
    defeq: list[dict[str, Any]] = []
    if analysis.defeq_requests and not diags:
        tc = leanbridge.resolve_toolchain(cert["toolchain"]["pin"])
        with fsutil.temporary_directory(prefix="verislop-export-") as tmp:
            op = Path(tmp) / "VeriSlopContract.olean"
            op.write_bytes(olean_bytes)
            resp = leanbridge.run_kernel_tool(tc, op, {"defeq": analysis.defeq_requests},
                                              timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                              require_network_isolation=pol["require_network_isolation"])
        defeq = resp.get("defeq", [])
        diags.extend(C.defeq_diagnostics(resp, "accepted environment"))
    if any(d.severity in ("blocking", "infrastructure") for d in diags):
        return None, {}, {}, diags

    # 7-8. dependencies, canonical packages, IR
    acc = pkg.path("accepted")
    env_ref = f"artifact:accepted-environment@{cert['artifacts']['environment_export']['sha256']}"
    witnesses_for = {i["id"]: i["witnesses_for"] for i in form["internal_obligations"]}
    obligations: dict[str, Any] = {}
    reification: dict[str, dict[str, Any]] = {}
    files: dict[str, bytes] = {}
    for r in records:
        if r["blocked_by"]:
            continue
        oid = r["id"]
        st = analysis.statements[oid]
        e = reg[oid]
        if st["representation"] in ("contract_dsl", "contract_facets"):
            package = st["formula_package"]
        elif st["representation"] == "lean_expr":
            closure_bytes = canonical.dumps({"toolchain": cert["toolchain"]["pin"], "declarations": st["semantic_closure"]})
            closure_hash = canonical.digest(closure_bytes)
            files[f"expressions/{closure_hash.split(':')[1]}.closure.json"] = closure_bytes
            package = {
                "encoding": dsl.OPAQUE_ENCODING,
                "lean_toolchain": cert["toolchain"]["pin"],
                "export_format": "verislop.kernel-expr-json",
                "export_format_version": "0.1",
                "environment_ref": env_ref,
                "declaration": st["lean_symbol"],
                "component": "type",
                "dependency_closure_ref": f"artifact:accepted-expressions/{oid}.closure@{closure_hash}",
            }
        else:
            package = {"encoding": "verislop.typed-metadata/0.1", "semantic_profile": profile.profile_id,
                       "registry_entry": f"{C.REGISTRY_NS}.{oid}",
                       "bindings": {n: env.hashes[n] for n in st["bindings"]}}
        pkg_bytes = canonical.dumps(package)
        pkg_hash = canonical.digest(pkg_bytes)
        files[f"expressions/{pkg_hash.split(':')[1]}.json"] = pkg_bytes
        check = {"certificate": cert_hash, "statement_hash": st["statement_hash"], "package": pkg_hash,
                 "round_trip": st["representation"] in ("contract_dsl", "contract_facets"),
                 "denotation_defeq": next((d["result"] for d in defeq if d["id"] == oid), None)}
        check_ref = f"reification:{oid}@{canonical.digest_json(check)}"
        reification[oid] = {"ref": check_ref, "check": check}
        cert_obl = cert["obligations"][oid]
        obligations[oid] = {
            "id": oid, "revision": e["revision"], "kind": e["kind"], "role": e["role"],
            "statement": e["statement"], "required": e["required"], "source_refs": e["source_refs"],
            "scope": e["scope"],
            "dependencies": mechanical_dependencies(oid, st, analysis.statements, cert_obl, e, witnesses_for),
            "acceptance_criteria": e["acceptance_criteria"],
            "formal": {
                "lean_symbol": st["lean_symbol"],
                "representation": st["representation"],
                "formula_ref": f"artifact:accepted-expressions/{oid}@{pkg_hash}",
                "statement_hash": st["statement_hash"],
                "semantic_closure_hash": st["semantic_closure_hash"],
                "hypotheses": st["hypotheses"],
                "axioms": cert_obl["axioms"],
                "reification_evidence_ref": check_ref,
            },
        }
    ir = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "accepted_semantic_ir",
        "contract_input_root": cert["contract_input_root"],
        "accepted_environment_hash": cert["artifacts"]["environment_export"]["sha256"],
        "acceptance_certificate_ref": f"{pkg.rel(acc)}/certificates/{cert_hash.split(':')[1]}.json",
        "exporter_id": VERIFIER,
        "exporter_hash": verifier_hash(VERIFIER),
        "lean_toolchain": cert["toolchain"]["pin"],
        "semantic_profile": profile.profile_id,
        "obligations": obligations,
    }
    issues = schemas.validate("accepted-ir", ir)
    if issues:
        diags.append(Diagnostic("IR_REIFICATION_MISMATCH", f"IR failed schema validation: {issues[0]}"))
        return None, {}, {}, diags
    return ir, files, reification, diags


def run(pkg: Package, events: EventSink, *, accepted: Path | None = None, out: Path | None = None) -> StageResult:
    events.emit("stage_started", "export", "reconstructing accepted IR from the accepted environment")
    result = StageResult("export", "PASS", "accepted IR reconstructed and validated from the certified environment")
    cert_path = Path(accepted) if accepted else pkg.path("accepted") / "acceptance.json"
    if out is not None:
        pkg.set_path("accepted_ir", out)
    cert, cert_hash, diags = verify_certificate(pkg, cert_path)
    if cert is not None and cert["gate"] != "accepted_and_proved":
        diags.append(Diagnostic("PROOF_UNRESOLVED", f"certificate gate is {cert['gate']}; only accepted-and-proved contracts are exported for implementation"))
    if diags:
        result.diagnostics = diags
        result.status = status_from(diags)
        return result
    assert cert is not None and cert_hash is not None
    export = canonical.load_file(pkg.root / cert["artifacts"]["environment_export"]["path"])
    olean_bytes = (pkg.root / cert["artifacts"]["olean"]["path"]).read_bytes()
    ir, files, reification, rdiags = reconstruct(pkg, cert, cert_hash, export, olean_bytes)
    if ir is None:
        result.diagnostics = rdiags
        result.status = status_from(rdiags)
        return result
    acc = pkg.path("accepted")
    for rel, data in files.items():
        fsutil.write_once(acc / rel, data)
    obligations = ir["obligations"]
    ir_bytes = canonical.dumps(ir)
    ir_hash = canonical.digest(ir_bytes)
    ir_path = pkg.path("accepted_ir")
    prior = ir_path.read_bytes() if ir_path.is_file() else None
    fsutil.atomic_write(ir_path, ir_bytes, readonly=True)
    fsutil.write_once(acc / "ir" / f"{ir_hash.split(':')[1]}.json", ir_bytes)
    for oid, rinfo in reification.items():
        rec = obligations[oid]
        pkg.evidence.record(
            claim_id=f"REIFIED:{oid}@{rec['revision']}", verifier_id=VERIFIER, status="PASS",
            scope=[f"certificate {cert_hash}", "artifact-to-IR correspondence under the declared trust boundary"],
            input_root=cert_hash,
            result={"milestone_outcome": "PASS", "reification_ref": rinfo["ref"], "check": rinfo["check"], "ir_hash": ir_hash},
            invocation=["verislop", "export"])
    events.emit("verifier_decision", "export", f"accepted IR {ir_hash[:19]}… ({len(obligations)} obligations)")
    from . import view

    view.write(pkg)
    result.artifacts.update({"accepted_ir": pkg.rel(ir_path), "obligation_view": pkg.rel(pkg.path("view"))})
    result.summary = {"ir_hash": ir_hash, "byte_identical_to_previous": prior == ir_bytes if prior is not None else None,
                      "obligations": {k: v["formal"]["representation"] for k, v in obligations.items()}}
    result.lines.append(f"IR {ir_hash} ({'byte-identical re-export' if prior == ir_bytes else 'written'})")
    return result
