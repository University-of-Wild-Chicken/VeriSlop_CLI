"""Supervisor-owned VSCore acquisition, exact-byte materialization and structural linking.

The source inventory comes from a proof-free kernel replay, never from candidate lifecycle
fields or a successfully elaborated candidate proof. Semantic acceptance remains a separate
registered bridge check; this module never publishes END_TO_END_VERIFIED.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from .. import canonical, contract as C, fsutil, leanbridge, schemas
from ..errors import Diagnostic, UsageError, VeriSlopError
from ..events import EventSink
from ..lifecycle import IMPLEMENTATION_MILESTONES, PREREQUISITES, applicability, claim_id
from ..package import Package
from ..stage import StageResult, status_from
from ..bridges import prepare, vscore3_checker as checker
from ..bridges.manifest import InvalidPackage, PackageReader
from ..targets import vscore3_target as T
from . import vscore3_admission as admission, registry

SELECTION_FILE = "selection.json"
INVENTORY_FILE = "materialization.json"
SOURCE_FILE = "program.vscore.json"
MATERIALIZER = "verislop.vscore3-materializer"
LINKER = "verislop.vscore3-linker"
FINAL_CLAIMS = {
    "CLOSURE:clean-builds": "closure-clean-builds/0.2",
    "CLOSURE:determinism": "closure-determinism/0.2",
    "CLOSURE:provenance": "closure-provenance/0.2",
    "CLOSURE:endpoint": "closure-endpoint/0.2",
}
PREDICATES = {"IMPLEMENTED": "vscore-materialized/0.3", "LINKED": "vscore-linked/0.3",
              "TESTED": "vscore-campaign/0.3", "END_TO_END_VERIFIED": "vscore-end-to-end/0.3"}
ROOT_KINDS = {"IMPLEMENTED": "implementation_root", "LINKED": "link_root",
              "TESTED": "test_root", "END_TO_END_VERIFIED": "closure_root"}


def _require(condition: bool, message: str, code: str = "INPUT_MUTATION") -> None:
    if not condition:
        raise checker.EdgeFailure([Diagnostic(code, message)])


def _schema(name: str, obj: dict) -> None:
    issues = schemas.validate(name, obj)
    _require(not issues, f"{name}: {issues[0] if issues else ''}", "INVALID_CANDIDATE")


def _frozen_json(pkg: Package, path: Path) -> dict:
    reader = PackageReader(pkg.root)
    try:
        obj, _ = reader.json(pkg.rel(path))
        reader.recheck()
        return obj
    finally:
        reader.close()


def _diagnostics(exc: Exception) -> list[Diagnostic]:
    if isinstance(exc, checker.EdgeFailure):
        return exc.diagnostics
    if isinstance(exc, InvalidPackage):
        return [Diagnostic(exc.code, str(exc))]
    if isinstance(exc, VeriSlopError):
        return exc.diagnostics or [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")]
    if isinstance(exc, (T.BridgeInvalid, T.BridgeUnsupported)):
        return [Diagnostic(getattr(exc, "code", "UNSUPPORTED_CAPABILITY"), str(exc))]
    if isinstance(exc, (OSError, KeyError, TypeError, ValueError)):
        return [Diagnostic("INVALID_CANDIDATE", f"invalid VSCore implementation inputs: {type(exc).__name__}: {exc}")]
    return [Diagnostic("VERIFIER_FAILURE", f"VSCore implementation infrastructure failure: {type(exc).__name__}", severity="infrastructure")]


def source_symbols(pkg: Package, rec: dict, profile: dict) -> list[str]:
    """Direct called symbols; declarations use their explicit accepted binding inventory.

    Internal reference definitions are covered by total refinement, and therefore do not need
    invented implementation entries merely because they occur in a reference's closure.
    """
    package = admission.formula_package(pkg, rec) or {}
    if rec["role"] == "declaration":
        bound = package.get("bindings", {})
        return sorted(sid for sid, spec in profile["symbols"].items() if spec["lean_decl"] in bound)
    if rec["formal"]["representation"] == "source_facets":
        from .. import source_contract
        from ..dsl import calls
        value = source_contract.value_package(package)
        return sorted(source_contract.symbols(package) | (calls(value["formula"]) if value else set()))
    if rec["formal"]["representation"] == "contract_dsl":
        from ..dsl import calls
        return sorted(calls(package.get("formula", {})))
    return []


def implementation_claims(pkg: Package, ir: dict, ir_hash: str, cert_hash: str, params: dict,
                          profile: dict, ledger: dict, plan: dict | None = None) -> dict:
    """Complete typed claim inventory; required unsupported guarantees stay applicable."""
    assumptions = {a["id"]: a for a in ledger.get("assumptions", [])}
    obligations = [{**{k: rec[k] for k in C.RECORD_FIELDS},
                    "origin": "derived" if rec["kind"] == "non_vacuity" else "interpreted",
                    "record_digest": C.record_digest(rec), "blocked_by": []}
                   for _, rec in sorted(ir["obligations"].items())]
    claims: list[dict] = []
    scope = ["restricted_source; vscore/0.3", "vscore-semantics/0.3"]
    contract_claims = canonical.load_file(pkg.path("claims")) if pkg.path("claims").is_file() else {"claims": []}
    for c in contract_claims["claims"]:
        oid, milestone = c["obligation"], c["milestone"]
        rec = ir["obligations"].get(oid)
        _require(rec is not None, f"contract claim {c['claim_id']} has no accepted obligation", "ORPHAN_CLAIM")
        root = "interpretation_root" if milestone == "INTERPRETED" and rec["kind"] != "non_vacuity" else "contract_input_root"
        claims.append({**c, "revision": rec["revision"], "accepted_statement_hash": rec["formal"]["statement_hash"], "root_kind": root,
                       "result_predicate": "milestone-pass/0.1",
                       "premises": [claim_id(m, oid, rec["revision"]) for m in PREREQUISITES[milestone]],
                       "scope": list(rec["scope"]), "trusted_dependencies": ["accepted-contract-policy"]})
    required_decl_ids = [oid for oid, rec in sorted(ir["obligations"].items())
                         if rec["required"] and rec["role"] == "declaration"]
    edge_claim = plan["edges"][0]["claim_id"] if plan else None
    for oid, rec in sorted(ir["obligations"].items()):
        app = applicability(rec, assumptions)
        for milestone in IMPLEMENTATION_MILESTONES:
            applicable, reason = app[milestone]
            required = bool(rec["required"] and applicable)
            if milestone == "TESTED" and applicable:
                required = required and params["require_tests"]
                reason = "test campaign required by frozen policy" if required else "campaign not required by frozen policy"
            elif milestone == "END_TO_END_VERIFIED" and applicable:
                reason = "complete required restricted_source endpoint closure" if required else "optional guarantees are outside selected coverage"
            premises = [claim_id(m, oid, rec["revision"]) for m in PREREQUISITES[milestone]] if applicable else []
            if milestone == "END_TO_END_VERIFIED" and required:
                premises += [claim_id(m, did, ir["obligations"][did]["revision"])
                             for did in required_decl_ids for m in ("IMPLEMENTED", "LINKED")]
                premises += list(FINAL_CLAIMS)
                if edge_claim:
                    premises.append(edge_claim)
                if params["require_tests"]:
                    premises.append(claim_id("TESTED", oid, rec["revision"]))
            claims.append({"claim_id": claim_id(milestone, oid, rec["revision"]), "obligation": oid,
                           "revision": rec["revision"], "accepted_statement_hash": rec["formal"]["statement_hash"], "milestone": milestone, "required": required,
                           "applicable": applicable, "verifier": registry.VSCORE3_PRODUCERS[milestone],
                           "pass_predicate": PREDICATES[milestone], "result_predicate": PREDICATES[milestone],
                           "root_kind": ROOT_KINDS[milestone], "premises": sorted(set(premises)),
                           "scope": scope, "trusted_dependencies": ["lean-kernel", "accepted-contract-policy"],
                           "severity": "blocking" if required else "advisory", "reason": reason})
    if plan:
        for c in plan["claims"]:
            claims.append({"claim_id": c["claim_id"], "obligation": None, "revision": None, "accepted_statement_hash": None, "milestone": None,
                           "required": True, "applicable": True, "verifier": c["verifier_id"],
                           "root_kind": c["root_kind"], "result_predicate": c["result_predicate"],
                           "pass_predicate": c["result_predicate"], "premises": c["premises"], "scope": scope,
                           "trusted_dependencies": ["lean-kernel", "accepted-contract-policy"],
                           "severity": "blocking", "reason": "selected direct bridge premise"})
    for cid, predicate in FINAL_CLAIMS.items():
        claims.append({"claim_id": cid, "obligation": None, "revision": None, "accepted_statement_hash": None, "milestone": None,
                       "required": True, "applicable": True, "verifier": "verislop.closure",
                       "root_kind": "closure_root", "result_predicate": predicate, "pass_predicate": predicate,
                       "premises": [], "scope": scope,
                       "trusted_dependencies": ["lean-kernel", "accepted-contract-policy"],
                       "severity": "blocking", "reason": "terminal closure verifier claim"})
    return {"schema_version": "0.2", "format": "verislop.implementation-claims/0.2",
            "artifact_kind": "implementation_claims", "backend": registry.VSCORE3_ID,
            "bound_to": {"accepted_ir": ir_hash, "certificate": cert_hash, "contract_input_root": ir["contract_input_root"]},
            "parameters": params, "obligations": obligations, "claims": sorted(claims, key=lambda c: c["claim_id"])}


def _scope_context(pkg: Package, bridge_id: str, expected: list[str]) -> checker.EdgeContext:
    bundle = pkg.path("bridges") / prepare._bridge_id(bridge_id)
    plan = canonical.load_file(bundle / "plan.json")
    _require(plan["tier"] == 2 and plan["endpoint"] == T.ENDPOINT, "selected bridge has the wrong tier/endpoint", "SCOPE_LEAK")
    _require(len(plan["nodes"]) == 2 and len(plan["edges"]) == 1,
             "VSCore pipeline requires one accepted node, one restricted_source node and one direct edge", "UNSUPPORTED_CAPABILITY")
    ctx = checker.load_context(bundle, bridge_id, plan["edges"][0]["edge_id"])
    _require(sorted(ctx.obligations) == sorted(expected), "selected bridge must cover exactly every required guarantee", "ORPHAN_CLAIM")
    _require(len(ctx.plan["claims"]) == 2, "selected bridge contains additional or competing claims", "ORPHAN_CLAIM")
    _require(all(ob["required_claims"] == [ctx.claim["claim_id"]] for ob in plan["obligations"]),
             "every covered guarantee must select the same direct edge", "ORPHAN_CLAIM")
    return ctx


def selection_record(pkg: Package, ctx: checker.EdgeContext, params: dict, descriptor: dict) -> dict:
    inputs = {}
    for role, (slot, data) in ctx.inputs.items():
        row = ctx.slots[slot]
        inputs[role] = {"slot_id": slot, "path": pkg.rel(pkg.path("bridges") / ctx.bridge_id / row["path"]),
                        "sha256": canonical.digest(data)}
    return {"schema_version": "0.2", "format": "verislop.implementation-selection/0.2",
            "backend": descriptor, "backend_descriptor_hash": registry.descriptor_hash(descriptor),
            "bridge_id": ctx.bridge_id, "source_node": ctx.edge["source_node"], "endpoint_node": ctx.edge["target_node"],
            "edge_id": ctx.edge["edge_id"], "edge_claim_id": ctx.claim["claim_id"],
            "plan_hash": ctx.plan_hash, "artifacts_hash": ctx.artifacts_hash,
            "accepted_ir_hash": ctx.plan["accepted_ir"], "acceptance_certificate_hash": ctx.plan["acceptance_certificate"],
            "profile_hash": ctx.accepted_profile_hash,
            "statements_hash": ctx.acceptance["artifacts"]["statements"]["sha256"],
            "covered": [{"id": oid, "revision": ob["revision"], "accepted_statement_hash": ob["statement_hash"]}
                        for oid, ob in sorted(ctx.obligations.items())],
            "inputs": inputs, "test_policy": {"require_tests": params["require_tests"], "require_state": params["require_state"]},
            "build_policy": {"builds": 2, "total_timeout_seconds": 1800, **{key: ctx.policy[key] for key in ("build_timeout_seconds", "kernel_timeout_seconds", "memory_mb", "require_network_isolation", "require_filesystem_isolation")}}}


def selection(pkg: Package) -> dict:
    """Revalidate the frozen supervisor selection against current exact bytes and descriptor."""
    path = pkg.path("closure") / SELECTION_FILE
    _require(path.is_file(), "no frozen implementation selection", "VERIFIER_NOT_RUN")
    frozen = _frozen_json(pkg, path)
    _schema("implementation-selection-v3", frozen)
    claims = _frozen_json(pkg, pkg.path("closure") / "implementation-claims.json")
    _schema("implementation-claims-v3", claims)
    params = claims["parameters"]
    current_ir = _frozen_json(pkg, pkg.path("accepted_ir"))
    _require(canonical.digest_file(pkg.path("accepted_ir")) == frozen["accepted_ir_hash"] and
             canonical.digest_file(pkg.root / current_ir["acceptance_certificate_ref"]) == frozen["acceptance_certificate_hash"],
             "selected accepted contract no longer matches the current run")
    descriptor = registry.select(params["tier"], params["target"], params["endpoint"], params.get("backend_version"))
    _require(descriptor is not None and params["backend"] == descriptor["id"], "frozen backend tuple is not registered", "UNSUPPORTED_CAPABILITY")
    _require(params["bridge_id"] == frozen["bridge_id"], "implementation selection changed bridge identity", "CLAIM_MUTATION")
    ctx = _scope_context(pkg, frozen["bridge_id"], [ob["id"] for ob in frozen["covered"]])
    features, reasons = admission.features(pkg, current_ir, ctx.accepted_profile)
    _require(not admission.unsupported(features), "current accepted records no longer satisfy frozen VSCore admission", "UNSUPPORTED_CAPABILITY")
    _require(sorted(ctx.obligations) == sorted(admission.covered(features)),
             "selected edge no longer covers every required implementation guarantee", "ORPHAN_CLAIM")
    _require(frozen == selection_record(pkg, ctx, params, descriptor), "frozen selection no longer matches registered inputs", "INPUT_MUTATION")
    expected_claims = implementation_claims(pkg, current_ir, frozen["accepted_ir_hash"], frozen["acceptance_certificate_hash"],
                                            params, ctx.accepted_profile, canonical.load_file(pkg.path("interpretation")), ctx.plan)
    _require(claims == expected_claims, "frozen claim graph differs from supervisor reconstruction", "CLAIM_MUTATION")
    source = pkg.path("implementation") / SOURCE_FILE
    _require(source.is_file() and source.read_bytes() == ctx.inputs["source"][1], "delivered source differs from selected bridge source")
    expected_files = [SOURCE_FILE, INVENTORY_FILE] if (pkg.path("implementation") / INVENTORY_FILE).is_file() else [SOURCE_FILE]
    _require(fsutil.list_files(pkg.path("implementation")) == sorted(expected_files),
             "VSCore endpoint allows one executable source and the declared materialization inventory", "UNDECLARED_DEPENDENCY")
    return frozen


def roots(pkg: Package) -> dict[str, str | None]:
    """Normative byte roots, intentionally independent of output link records."""
    selection_path = pkg.path("closure") / SELECTION_FILE
    claims_path = pkg.path("closure") / "implementation-claims.json"
    delivered = pkg.path("implementation") / SOURCE_FILE
    if not all(p.is_file() for p in (selection_path, claims_path, delivered)):
        return {"implementation_root": None, "link_root": None}
    descriptor = registry.select(2, "vscore", "restricted_source", "0.3")
    root = canonical.digest_json({"format": "verislop.vscore-materialization-root/0.3",
                                  "selection_hash": canonical.digest_file(selection_path),
                                  "implementation_claims_hash": canonical.digest_file(claims_path),
                                  "delivered_source_hash": canonical.digest_file(delivered),
                                  "backend_descriptor_hash": registry.descriptor_hash(descriptor)})
    bpath = pkg.path("bridges") / "bindings.json"
    inventory = pkg.path("implementation") / INVENTORY_FILE
    link = canonical.digest_json({"format": "verislop.vscore-link-root/0.3", "implementation_root": root,
                                  "bindings_hash": canonical.digest_file(bpath),
                                  "materialization_inventory_hash": canonical.digest_file(inventory)}) if bpath.is_file() and inventory.is_file() else None
    return {"implementation_root": root, "link_root": link}


def implementation_root(pkg: Package) -> str | None:
    return roots(pkg)["implementation_root"]


def link_root(pkg: Package) -> str | None:
    return roots(pkg)["link_root"]


def materialization_inventory(ctx: checker.EdgeContext, spec: T.GoalSpec, build: checker.Build) -> dict:
    """Re-export from sourceBytes/rawProgram/signatures/profile, without a candidate theorem."""
    from ..exprjson import decl_hash
    replayed = T.reexport(spec, build.decls)
    _require(replayed == build.ir, "kernel inventory differs from reconstructed build IR", "IR_REIFICATION_MISMATCH")
    adapters = []
    for adapter in spec.adapters:
        name = T.GOAL_MODULE + "." + adapter.name
        decl = build.decls.get(name)
        _require(decl is not None, f"replay has no adapter {name}", "IR_REIFICATION_MISMATCH")
        adapters.append({"name": name, "sort": adapter.sort, "decl_hash": decl_hash(decl)})
    return {"schema_version": "0.3", "format": "verislop.vscore-materialization/0.3", "backend": registry.VSCORE3_ID,
            "bridge_id": ctx.bridge_id, "source_hash": canonical.digest(spec.source_bytes),
            "decoded_program_hash": canonical.digest_json(replayed["program"]),
            "program": replayed["program"], "signatures": replayed["signatures"], "enums": replayed["enums"],
            "bindings": replayed["bindings"], "adapters": adapters,
            "profile_hash": canonical.digest(ctx.inputs["profile"][1]), "proposition_hash": build.proposition_hash,
            "proof_checked": False}


def _binding_proposal(ctx: checker.EdgeContext) -> dict:
    return {"schema_version": "0.2", "format": "verislop.implementation-bindings/0.2",
            "artifact_kind": "implementation_bindings", "backend": registry.VSCORE3_ID,
            "accepted_ir": ctx.plan["accepted_ir"], "bridge_id": ctx.bridge_id,
            "source_slot": ctx.inputs["source"][0],
            "bindings": [{"binding_id": "entry-" + canonical.sha256_hex((b["symbol"] + "\0" + b["entry"]).encode())[:24], **b}
                         for b in ctx.relation["bindings"]]}


def _declaration_objects(pkg: Package, rec: dict, ctx: checker.EdgeContext, inventory: dict) -> list[dict]:
    package = admission.formula_package(pkg, rec) or {}
    objects = []
    for decl, digest in sorted(package.get("bindings", {}).items()):
        enum = next(((eid, e) for eid, e in ctx.accepted_profile.get("enums", {}).items()
                     if decl == e["lean_decl"] or decl in e.get("lean_constructors", [])), None)
        symbol = next(((sid, s) for sid, s in ctx.accepted_profile["symbols"].items() if decl == s["lean_decl"]), None)
        record = next(((rid, r) for rid, r in ctx.accepted_profile.get("records", {}).items()
                       if decl in [r["lean_decl"], r["lean_constructor"], *(f["lean_projection"] for f in r["fields"])]), None)
        if enum:
            eid, e = enum
            objects.append({"kind": "accepted_enum" if decl == e["lean_decl"] else "accepted_constructor",
                            "lean_decl": decl, "decl_hash": digest, "enum": eid,
                            "constructors": list(e["lean_constructors"]), "profile_hash": inventory["profile_hash"]})
        elif symbol:
            sid, sym = symbol
            objects.append({"kind": "accepted_function_type", "lean_decl": decl, "decl_hash": digest,
                            "symbol": sid, "args": sym["args"], "result": sym["result"],
                            "profile_hash": inventory["profile_hash"]})
        elif record:
            rid, row = record
            from ..targets import vscore3_source
            expected = {"id": rid, "tag": "record", "fields": [
                {"id": field["name"], "type": vscore3_source.ty_json(T.sort_ty(field["sort"]))}
                for field in row["fields"]]}
            if expected not in inventory["program"]["declarations"]:
                continue
            objects.append({"kind": "accepted_record", "lean_decl": decl, "decl_hash": digest,
                            "record": rid, "registry": row, "profile_hash": inventory["profile_hash"]})
    return objects


def _materialize(pkg: Package, events: EventSink, ctx: checker.EdgeContext, claims: dict) -> list[Diagnostic]:
    selection(pkg)
    spec = checker.derive_goal(ctx)
    tc = leanbridge.resolve_toolchain(ctx.acceptance["toolchain"]["pin"])
    build = checker.run_build(tc, ctx, spec, with_proof=False)
    _require(build.proposition_hash == ctx.edge["expected_proposition_hash"], "derived proposition differs from selected bridge", "STATEMENT_MISMATCH")
    inventory = materialization_inventory(ctx, spec, build)
    _schema("vscore-materialization-v3", inventory)
    path = pkg.path("implementation") / INVENTORY_FILE
    fsutil.write_json(path, inventory, once=True)
    root = roots(pkg)["implementation_root"]
    inventory_hash = canonical.digest_file(path)
    diagnostics: list[Diagnostic] = []
    for c in claims["claims"]:
        if c["milestone"] != "IMPLEMENTED" or not c["applicable"]:
            continue
        rec = ctx.accepted_ir["obligations"][c["obligation"]]
        syms = source_symbols(pkg, rec, ctx.accepted_profile)
        bound = {b["symbol"] for b in inventory["bindings"]}
        declarations = _declaration_objects(pkg, rec, ctx, inventory) if rec["role"] == "declaration" else []
        if rec["role"] == "declaration":
            # Internal pure reference functions need accepted type objects, not target entries.
            syms = [symbol for symbol in syms if symbol in bound]
        declaration_bindings = (admission.formula_package(pkg, rec) or {}).get("bindings", {})
        ok = all(s in bound for s in syms) and (rec["role"] != "declaration" or
             bool(declarations) and len(declarations) == len(declaration_bindings))
        if not rec["required"] and rec["role"] == "guarantee":
            # Optional guarantees are visible but have no selected implementation claim.
            continue
        ev = pkg.evidence.record(claim_id=c["claim_id"], verifier_id=MATERIALIZER, status="PASS" if ok else "BLOCK",
                                 scope=c["scope"], input_root=root,
                                 result={"milestone_outcome": "PASS" if ok else "FAIL", "materialized": ok,
                                         "inventory_hash": inventory_hash, "proof_checked": False, "symbols": syms,
                                         "objects": declarations, "source_hash": inventory["source_hash"],
                                         "codes": [] if ok else ["UNMAPPED_IMPLEMENTATION_OBJECT"]},
                                 invocation=["verislop", "generate"])
        if not ok:
            diagnostics.append(Diagnostic("UNMAPPED_IMPLEMENTATION_OBJECT", f"{rec['id']}: accepted interface object has no materialized entry or representation", obligations=[rec["id"]]))
        events.emit("verifier_decision", "generate", f"{rec['id']} IMPLEMENTED {'PASS' if ok else 'FAIL'}",
                    obligation_id=rec["id"], milestone="IMPLEMENTED", outcome="PASS" if ok else "FAIL", evidence_ref=f"evidence:{ev.id}")
    return diagnostics


def _candidate_readable_metadata(reader: PackageReader) -> tuple[bytes | None, dict[str, bytes]]:
    """Read the frozen non-executable selection and its exact declared diagnostics."""
    path = checker.READABLE_SELECTION_PATH
    if not os.path.lexists(reader.root / path):
        return None, {}
    selection_bytes = reader.read(path, keep=True).data
    metadata = checker.readable_candidate_metadata(selection_bytes, lambda name: reader.read(name, keep=True).data)
    return selection_bytes, metadata


def _context_readable_metadata(ctx: checker.EdgeContext) -> dict[str, bytes]:
    selection_bytes = getattr(ctx, "readable_selection", None)
    if selection_bytes is None:
        return {}
    return checker.readable_candidate_metadata(selection_bytes, lambda name: ctx.readable_diagnostics[name])


def generate(pkg: Package, events: EventSink, ir: dict, ir_hash: str, cert: dict, params: dict,
             *, candidate: Path | None = None, bridge_id: str | None = None, bindings: Path | None = None,
             agent: Callable | None = None) -> StageResult:
    result = StageResult("generate", "PASS", "kernel-checked VSCore source materialized; refinement remains a separate bridge check")
    try:
        if bindings is not None:
            raise UsageError("VSCore bindings come from relation.json; --bindings is a Python-only binding proposal")
        profile = C.frozen_json(pkg, "profile.json")
        ledger = canonical.load_file(pkg.path("interpretation"))
        fs, reasons = admission.features(pkg, ir, profile)
        decision = admission.admit(2, params["require_state"], "require_tests" if params["require_tests"] else "no_tests", fs)
        claims_path = pkg.path("closure") / "implementation-claims.json"
        if decision[0] != "admitted":
            inv = implementation_claims(pkg, ir, ir_hash, canonical.digest_file(pkg.root / ir["acceptance_certificate_ref"]), params, profile, ledger)
            _schema("implementation-claims-v3", inv)
            fsutil.write_json(claims_path, inv, once=True)
            result.diagnostics = admission.admission_diagnostics(decision, reasons)
            result.status = "BLOCKED"
            return result
        if claims_path.is_file():
            frozen = canonical.load_file(claims_path)
            _require(frozen.get("parameters") == params, "changing frozen implementation parameters requires a new run", "CLAIM_MUTATION")
            selected = selection(pkg)
            _require(bridge_id is None or bridge_id == selected["bridge_id"], "cannot select a new bridge in a frozen run", "CLAIM_MUTATION")
            ctx = _scope_context(pkg, selected["bridge_id"], decision[2])
            if candidate is not None:
                reader = PackageReader(Path(candidate))
                try:
                    for role, filename in (("source", SOURCE_FILE), ("relation", "relation.json"), ("proof_source", "Proof.lean")):
                        _require(reader.read(filename, keep=True).data == ctx.inputs[role][1],
                                 "changing frozen source/proof/relation requires a new run", "CLAIM_MUTATION")
                    _, metadata = _candidate_readable_metadata(reader)
                    _require(metadata == _context_readable_metadata(ctx),
                             "changing frozen readable selection or diagnostics requires a new run", "CLAIM_MUTATION")
                    reader.recheck()
                finally:
                    reader.close()
            result.diagnostics.extend(_materialize(pkg, events, ctx, frozen))
        else:
            if candidate is None and bridge_id is None and agent is None:
                raise UsageError("VSCore generate needs --candidate DIR or an explicitly selected prepared --bridge-id ID")
            bid = prepare._bridge_id(bridge_id or "implementation")
            params = {**params, "bridge_id": bid}
            if candidate is not None or (agent is not None and bridge_id is None):
                if candidate is not None:
                    reader = PackageReader(Path(candidate))
                    try:
                        source = reader.read(SOURCE_FILE, keep=True).data
                        relation = reader.read("relation.json", keep=True).data
                        proof = reader.read("Proof.lean", keep=True).data
                        readable_selection, readable_metadata = _candidate_readable_metadata(reader)
                        proposal_path = Path(candidate) / "proposal.json"
                        supplied = reader.json("proposal.json")[0] if proposal_path.is_file() else None
                        reader.recheck()
                    finally:
                        reader.close()
                else:
                    files, proposed = agent({"ir": ir, "profile": profile, "parameters": params, "required_obligations": decision[2]})
                    source, relation, proof = files[SOURCE_FILE], files["relation.json"], files["Proof.lean"]
                    readable_selection = files.get(checker.READABLE_SELECTION_PATH)
                    readable_metadata = (checker.readable_candidate_metadata(readable_selection, files.__getitem__)
                                         if readable_selection is not None else {})
                    supplied = proposed if proposed and proposed.get("format") == "verislop.bridge-proposal/0.1" else None
                # Never check the candidate proof here: source materialization is independent.
                # Missing sidecar is legacy BASE. A returned source selection is replayed
                # exactly, including unavailable diagnostics; packaging never selects anew.
                preview_opts = ({} if readable_selection is None else {
                    "readable_selection": readable_selection, "select_readable": False,
                    "readable_diagnostics": {name: data for name, data in readable_metadata.items()
                                             if name != checker.READABLE_SELECTION_PATH}})
                _, _, info = checker.preview(pkg, source, relation, proof=None, **preview_opts)
                _require(info.get("readable_selection") == readable_selection and
                         info.get("readable_candidate_artifacts", {}) == readable_metadata,
                         "proof-free replay changed frozen readable selection or diagnostics", "INPUT_MUTATION")
                files = checker.candidate_files(bid, info, source, relation, proof)
                _require(all(files.get(name) == data for name, data in readable_metadata.items()),
                         "candidate packaging changed frozen readable selection or diagnostics", "INPUT_MUTATION")
                expected_proposal = canonical.loads(files["proposal.json"])
                _require(supplied is None or supplied == expected_proposal,
                         "supplied selected proposal conflicts with supervisor-derived complete bridge", "CLAIM_MUTATION")
                with fsutil.temporary_directory(prefix="verislop-vscore-candidate-") as temp:
                    stage = Path(temp)
                    for name, data in files.items():
                        fsutil.atomic_write(stage / name, data)
                    prepared = prepare.run(pkg, events, Path("proposal.json"), stage, expected_tier=2, expected_endpoint=T.ENDPOINT)
                if prepared.status != "PASS":
                    result.status, result.diagnostics = prepared.status, prepared.diagnostics
                    return result
            else:
                prepared = prepare.verify_preparation(pkg, bid, events, semantic="skip")
                if prepared.status != "PASS":
                    result.status, result.diagnostics = prepared.status, prepared.diagnostics
                    return result
            ctx = _scope_context(pkg, bid, decision[2])
            selected = selection_record(pkg, ctx, params, registry.select(2, "vscore", T.ENDPOINT, "0.3"))
            inv = implementation_claims(pkg, ir, ir_hash, ctx.plan["acceptance_certificate"], params, profile, ledger, ctx.plan)
            _schema("implementation-claims-v3", inv)
            _schema("implementation-selection-v3", selected)
            proposal = _binding_proposal(ctx)
            _schema("implementation-bindings-v3", proposal)
            impl = pkg.path("implementation")
            _require(not impl.exists() or not fsutil.list_files(impl), "an implementation artifact already exists before VSCore selection", "INPUT_MUTATION")
            fsutil.write_once(impl / SOURCE_FILE, ctx.inputs["source"][1])
            fsutil.write_json(pkg.path("bridges") / "bindings.json", proposal, once=True)
            fsutil.write_json(claims_path, inv, once=True)
            fsutil.write_json(pkg.path("closure") / SELECTION_FILE, selected, once=True)
            result.diagnostics.extend(_materialize(pkg, events, ctx, inv))
        result.status = status_from(result.diagnostics)
        result.artifacts = {"implementation": pkg.rel(pkg.path("implementation")), "implementation_claims": pkg.rel(claims_path),
                            "selection": pkg.rel(pkg.path("closure") / SELECTION_FILE), "bindings": pkg.rel(pkg.path("bridges") / "bindings.json")}
        result.summary = {"parameters": params, **roots(pkg), "files": [SOURCE_FILE], "bridge_id": params["bridge_id"], "proof_checked": False}
        result.lines = [f"tier 2 -> restricted_source (vscore/0.3, vscore-semantics/0.3)"]
        from .. import view
        view.write(pkg)
    except UsageError:
        raise
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, T.BridgeInvalid, T.BridgeUnsupported, OSError, KeyError, TypeError, ValueError) as exc:
        result.diagnostics = _diagnostics(exc)
        result.status = status_from(result.diagnostics)
    return result


def _link_record(pkg: Package, ctx: checker.EdgeContext, inv: dict, proposal: dict) -> dict:
    _require(proposal == _binding_proposal(ctx), "binding proposal differs from the selected relation", "CLAIM_MUTATION")
    profile = ctx.accepted_profile
    spec = checker.derive_goal(ctx)
    expected_signatures = [{"id": s["id"], "params": [T.src.ty_json(t) for t in s["params"]],
                            "result": T.src.ty_json(s["result"])} for s in spec.signatures]
    expected_bindings = [{"symbol": sym.symbol, "entry": sym.entry, "lean_decl": sym.lean_decl,
                          "args": sym.arg_sorts, "result": sym.result_sort} for sym in spec.symbols]
    _require(canonical.dumps(inv["program"]) == ctx.inputs["source"][1] and
             inv["decoded_program_hash"] == canonical.digest_json(inv["program"]) and
             inv["signatures"] == expected_signatures and inv["bindings"] == expected_bindings,
             "materialization inventory source/signatures/bindings differ from selected interface", "IR_REIFICATION_MISMATCH")
    _require(inv["profile_hash"] == canonical.digest(ctx.inputs["profile"][1]) and
             inv["proposition_hash"] == ctx.edge["expected_proposition_hash"] and inv["bridge_id"] == ctx.bridge_id,
             "materialization inventory no longer binds the selected profile, proposition and bridge", "INPUT_MUTATION")
    expected_adapters = [{"name": T.GOAL_MODULE + "." + adapter.name, "sort": adapter.sort} for adapter in spec.adapters]
    _require([{k: adapter[k] for k in ("name", "sort")} for adapter in inv["adapters"]] == expected_adapters,
             "materialization adapters differ from actual selected argument/result representations", "IR_REIFICATION_MISMATCH")
    statements = _frozen_json(pkg, pkg.root / ctx.acceptance["artifacts"]["statements"]["path"])
    hashes = statements["declaration_hashes"]
    records = []
    for b in proposal["bindings"]:
        sym = profile["symbols"][b["symbol"]]
        signature = next((s for s in inv["signatures"] if s["id"] == b["entry"]), None)
        _require(signature is not None, f"no kernel-replayed entry {b['entry']}", "UNMAPPED_IMPLEMENTATION_OBJECT")
        covered = [{"id": oid, "revision": ob["revision"], "accepted_statement_hash": ob["statement_hash"]}
                   for oid, ob in sorted(ctx.obligations.items()) if b["symbol"] in source_symbols(pkg, ctx.accepted_ir["obligations"][oid], profile)]
        records.append({**b, "accepted_declaration": {"lean_decl": sym["lean_decl"], "decl_hash": hashes[sym["lean_decl"]],
                                                    "args": sym["args"], "result": sym["result"]},
                        "implementation_object": {"kind": "vscore_entry", "source_path": pkg.rel(pkg.path("implementation") / SOURCE_FILE),
                                                  "source_hash": inv["source_hash"], "entry": b["entry"], "signature": signature},
                        "adapters": inv["adapters"], "profile_hash": inv["profile_hash"], "covered": covered})
    declarations = [{"id": oid, "revision": rec["revision"], "objects": _declaration_objects(pkg, rec, ctx, inv)}
                    for oid, rec in sorted(ctx.accepted_ir["obligations"].items()) if rec["role"] == "declaration" and rec["required"]]
    return {"schema_version": "0.2", "format": "verislop.link-record/0.2", "artifact_kind": "link_record",
            "backend": registry.VSCORE3_ID, "accepted_ir": ctx.plan["accepted_ir"], "implementation_root": roots(pkg)["implementation_root"],
            "source": {"path": pkg.rel(pkg.path("implementation") / SOURCE_FILE), "sha256": inv["source_hash"]},
            "decoded_program_hash": inv["decoded_program_hash"], "materialization_inventory_hash": canonical.digest_file(pkg.path("implementation") / INVENTORY_FILE),
            "bridge_id": ctx.bridge_id, "source_node": ctx.edge["source_node"], "endpoint_node": ctx.edge["target_node"],
            "edge_id": ctx.edge["edge_id"], "edge_claim_id": ctx.claim["claim_id"], "plan_hash": ctx.plan_hash, "artifacts_hash": ctx.artifacts_hash,
            "profile_hash": inv["profile_hash"], "bindings": sorted(records, key=lambda r: r["binding_id"]), "declarations": declarations,
            "covered": [{"id": oid, "revision": ob["revision"], "accepted_statement_hash": ob["statement_hash"]} for oid, ob in sorted(ctx.obligations.items())],
            "correspondence": "structural"}


def checked_link(pkg: Package) -> tuple[dict | None, list[Diagnostic]]:
    """Reconstruct linking without publication; closure additionally replays its inventory."""
    try:
        selected = selection(pkg)
        ctx = _scope_context(pkg, selected["bridge_id"], [o["id"] for o in selected["covered"]])
        inv = _frozen_json(pkg, pkg.path("implementation") / INVENTORY_FILE)
        _schema("vscore-materialization-v3", inv)
        _require(inv["source_hash"] == canonical.digest(ctx.inputs["source"][1]) and not inv["proof_checked"], "materialization source binding changed")
        proposal = _frozen_json(pkg, pkg.path("bridges") / "bindings.json")
        _schema("implementation-bindings-v3", proposal)
        record = _link_record(pkg, ctx, inv, proposal)
        _schema("link-record-v3", record)
        path = pkg.path("bridges") / "link.json"
        _require(path.is_file() and _frozen_json(pkg, path) == record, "stored link record differs from reconstructed correspondence")
        return record, []
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, KeyError, TypeError, ValueError) as exc:
        return None, _diagnostics(exc)


def link(pkg: Package, events: EventSink) -> StageResult:
    result = StageResult("link", "PASS", "unique structural bindings connect the delivered VSCore source to the accepted interface")
    try:
        selected = selection(pkg)
        ctx = _scope_context(pkg, selected["bridge_id"], [o["id"] for o in selected["covered"]])
        claims = _frozen_json(pkg, pkg.path("closure") / "implementation-claims.json")
        inv_path = pkg.path("implementation") / INVENTORY_FILE
        _require(inv_path.is_file(), "source has no kernel materialization inventory", "VERIFIER_NOT_RUN")
        inv = _frozen_json(pkg, inv_path)
        _schema("vscore-materialization-v3", inv)
        # Reconstruct from a fresh proof-free replay so forged materialization outputs cannot link.
        spec = checker.derive_goal(ctx)
        build = checker.run_build(leanbridge.resolve_toolchain(ctx.acceptance["toolchain"]["pin"]), ctx, spec, with_proof=False)
        _require(inv == materialization_inventory(ctx, spec, build), "materialization inventory differs from fresh kernel replay", "IR_REIFICATION_MISMATCH")
        proposal = _frozen_json(pkg, pkg.path("bridges") / "bindings.json")
        _schema("implementation-bindings-v3", proposal)
        record = _link_record(pkg, ctx, inv, proposal)
        _schema("link-record-v3", record)
        path = pkg.path("bridges") / "link.json"
        fsutil.write_json(path, record, once=True)
        from .. import view
        current = view.derive(pkg)["obligations"]
        root = roots(pkg)["link_root"]
        for c in claims["claims"]:
            if c["milestone"] != "LINKED" or not c["applicable"]:
                continue
            rec = ctx.accepted_ir["obligations"][c["obligation"]]
            if not rec["required"] and rec["role"] == "guarantee":
                continue
            missing = [m for m in ("IMPLEMENTED", "TYPECHECKED") if current.get(rec["id"], {}).get("lifecycle", {}).get(m, {}).get("outcome") != "PASS"]
            _require(not missing, f"{rec['id']}: LINKED requires {', '.join(missing)}", "VERIFIER_NOT_RUN")
            ev = pkg.evidence.record(claim_id=c["claim_id"], verifier_id=LINKER, status="PASS", scope=c["scope"], input_root=root,
                                     result={"milestone_outcome": "PASS", "structural_linked": True, "link_record_hash": canonical.digest_file(path),
                                             "inventory_hash": canonical.digest_file(inv_path), "symbols": source_symbols(pkg, rec, ctx.accepted_profile),
                                             "correspondence": "structural", "semantic_acceptance": False}, invocation=["verislop", "link"])
            events.emit("verifier_decision", "link", f"{rec['id']} LINKED PASS", obligation_id=rec["id"], milestone="LINKED", outcome="PASS", evidence_ref=f"evidence:{ev.id}")
        view.write(pkg)
        result.artifacts = {"link": pkg.rel(path)}
        result.summary = {"link_root": root, "bindings": [{"symbol": r["symbol"], "object": implementation_ref(r["implementation_object"])} for r in record["bindings"]]}
    except (checker.EdgeFailure, InvalidPackage, VeriSlopError, OSError, KeyError, TypeError, ValueError) as exc:
        result.diagnostics = _diagnostics(exc)
        result.status = status_from(result.diagnostics)
    return result


def implementation_ref(obj: dict) -> str:
    return f"vscore:{quote(obj['source_path'], safe='/')}#entry/{quote(obj['entry'], safe='')}@{obj['source_hash']}"


def implementation_reference_objects(record: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for binding in record["bindings"]:
        obj = binding["implementation_object"]
        ref = {"binding_id": binding["binding_id"], "ref": implementation_ref(obj), **obj}
        for ob in binding["covered"]:
            result.setdefault(ob["id"], []).append(ref)
    for decl in record["declarations"]:
        result.setdefault(decl["id"], []).extend(decl["objects"])
    return result


def implementation_refs(record: dict) -> dict[str, list[str]]:
    """Display references retain the existing obligation-view string format."""
    result: dict[str, list[str]] = {}
    for oid, objects in implementation_reference_objects(record).items():
        refs = []
        for obj in objects:
            if "ref" in obj:
                refs.append(obj["ref"])
            else:
                refs.append(f"accepted:{quote(obj['lean_decl'], safe='')}@{obj['decl_hash']}")
                refs.append(f"vscore-profile:{obj['profile_hash']}")
        result[oid] = sorted(set(refs))
    return result
