"""Registered semantic checker `verislop.vscore3-checker` for `vscore.reference_refinement/0.3` edges.

For one frozen edge from the accepted contract to a `restricted_source` VSCore node it:

1. reads only frozen, manifest-bound bytes of a prepared bridge bundle (the preparation itself is
   re-verified first, including a fresh replay of the accepted contract);
2. derives the bridge goal from the accepted IR, accepted profile registry and accepted formula
   packages (`targets/vscore3_target.py`); the candidate supplies source bytes, symbol↔entry
   bindings and a proof module, nothing else;
3. performs two isolated builds. Each compiles the verifier-owned VSCore library, binds the exact
   accepted contract module, compiles the goal, then compiles the candidate proof in the sandbox
   with read-only access to those artifacts only, and replays every non-toolchain declaration in
   the trusted kernel tool;
4. checks the replayed environment: import closure, no candidate axioms, the exact type of
   `VeriSlopBridgeProof.edge`, its transitive axioms against the accepted policy, statement
   identity of every derived definition, the proposition hash frozen in the plan, and re-exports
   `implementation-ir.json` from the accepted goal declarations;
5. requires both builds to agree on module bytes, proposition, environment export and IR, then
   publishes a certificate and evidence under `bridges/<bridge-id>/semantic/<edge-key>/`.

Accepting an edge never assigns an obligation milestone; END_TO_END_VERIFIED needs closure.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import canonical, fsutil, leanbridge, policy as policymod, source_contract
from ..errors import Diagnostic, VeriSlopError
from ..events import EventSink
from ..evidence import EvidenceStore
from ..exprjson import name_str
from ..package import Package
from ..stage import StageResult, status_from
from ..targets import vscore3_target as T
from ..targets import vscore3_readable as R
from ..verifiers import verifier_hash
from .check import _schema, semantic_edge_root
from .manifest import InvalidPackage, PackageReader
from .registry import relation_checker
from . import vscore3_readable_support as RS

READABLE_SELECTION_PATH = R.SELECTION_PATH
READABLE_SELECTION_SLOT = R.SELECTION_SLOT
readable_candidate_metadata = RS.candidate_metadata
readable_artifact_refs = RS.artifact_refs

VERIFIER = "verislop.vscore3-checker"
GATE = "VSCore exact-source parse/typing, reference refinement and obligation transfer (two kernel replays)"
SCOPE = ["restricted_source; vscore/0.3", "template vscore.reference_refinement/0.3",
         "parse/typing equations, input coverage, refinement and transfer of the covered accepted obligations"]
SEMANTIC_DIR = "semantic"
CERTIFICATE = "certificate.json"
IR_FILE = "implementation-ir.json"


class EdgeFailure(Exception):
    def __init__(self, diagnostics: list[Diagnostic]):
        super().__init__("; ".join(d.message for d in diagnostics))
        self.diagnostics = diagnostics


def _fail(code: str, message: str, claim: str | None = None, severity: str = "blocking") -> EdgeFailure:
    return EdgeFailure([Diagnostic(code, message, severity=severity, claims=[claim] if claim else [])])


def edge_key(edge_id: str) -> str:
    return "edge-" + canonical.sha256_hex(edge_id.encode())[:24]


@dataclass
class EdgeContext:
    bridge_id: str
    plan: dict
    plan_hash: str
    artifacts_hash: str
    edge: dict
    claim: dict
    slots: dict[str, dict]
    relation: dict
    inputs: dict[str, tuple[str, bytes]]
    accepted_ir: dict
    acceptance: dict
    accepted_profile: dict
    accepted_profile_hash: str
    contract_module: bytes
    policy: dict
    obligations: dict[str, dict]
    readable_selection: bytes | None = None
    readable_diagnostics: dict[str, bytes] = field(default_factory=dict)


# ------------------------------------------------------------------------------------------
# frozen inputs
# ------------------------------------------------------------------------------------------

def _artifact(reader: PackageReader, slots: dict[str, dict], slot: str, *, json: bool = False) -> Any:
    a = slots.get(slot)
    if a is None:
        raise _fail("UNDECLARED_DEPENDENCY", f"undeclared artifact slot {slot}")
    if json:
        value, snap = reader.json(a["path"])
    else:
        snap = reader.read(a["path"], keep=True)
        value = snap.data
    if snap.sha256 != a["sha256"]:
        raise _fail("INPUT_MUTATION", f"artifact {slot} changed after preparation")
    return value


def _by_path(slots: dict[str, dict], path: str) -> dict:
    for a in slots.values():
        if a["path"] == path:
            return a
    raise _fail("UNDECLARED_DEPENDENCY", f"accepted artifact {path} is not in the frozen manifest")


def load_context(bundle: Path, bridge_id: str, edge_id: str) -> EdgeContext:
    reader = PackageReader(bundle)
    try:
        plan, plan_snap = reader.json("plan.json")
        manifest, manifest_snap = reader.json("artifacts.json")
        _schema("bridge-plan", plan)
        _schema("bridge-artifacts", manifest)
        if manifest["plan_hash"] != plan_snap.sha256 or plan["bridge_id"] != bridge_id:
            raise _fail("INPUT_MUTATION", "bridge plan/manifest binding changed")
        slots = {a["slot_id"]: a for a in manifest["artifacts"]}
        edges = {e["edge_id"]: e for e in plan["edges"]}
        claims = {c["claim_id"]: c for c in plan["claims"]}
        nodes = {n["node_id"]: n for n in plan["nodes"]}
        edge = edges.get(edge_id)
        if edge is None:
            raise _fail("ORPHAN_CLAIM", f"unknown edge {edge_id}")
        claim = claims[edge["claim_id"]]
        cid = claim["claim_id"]
        if claim["verifier_id"] != VERIFIER:
            raise _fail("ORPHAN_CLAIM", f"edge {edge_id} is not assigned to {VERIFIER}", cid)
        structure = "BRIDGE:structure:" + bridge_id
        if claim["premises"] != [structure]:
            raise _fail("UNSUPPORTED_CAPABILITY",
                        f"{T.TEMPLATE} edges have no premises besides the structural preparation claim", cid)
        if plan["tier"] != 2 or plan["endpoint"] != T.ENDPOINT:
            raise _fail("UNSUPPORTED_CAPABILITY", f"{T.TEMPLATE} serves only Tier 2 restricted_source bridges", cid)
        source_node, target_node = nodes[edge["source_node"]], nodes[edge["target_node"]]
        if source_node["kind"] != "accepted_contract" or target_node["kind"] != T.ENDPOINT:
            raise _fail("UNSUPPORTED_CAPABILITY", "the edge must lead from the accepted contract to the restricted_source node", cid)
        relation_bytes = _artifact(reader, slots, edge["relation"]["id"])
        if relation_checker(relation_bytes) != VERIFIER:
            raise _fail("ORPHAN_CLAIM", "relation artifact no longer names the registered template", cid)
        try:
            relation = T.load_relation(relation_bytes)
        except T.BridgeInvalid as exc:
            raise _fail(exc.code, str(exc), cid) from None
        inputs: dict[str, tuple[str, bytes]] = {"relation": (edge["relation"]["id"], relation_bytes)}
        for name, slot, role in (("source", relation["source_slot"], T.SOURCE_ROLE),
                                 ("proof_source", relation["proof_slot"], T.PROOF_ROLE)):
            slot_rec = next((s for s in plan["artifact_slots"] if s["slot_id"] == slot), None)
            if slot_rec is None or slot_rec["role"] != role or slot_rec["node_id"] != target_node["node_id"]:
                raise _fail("UNMAPPED_IMPLEMENTATION_OBJECT",
                            f"relation {name} slot {slot} must be a {role} artifact of node {target_node['node_id']}", cid)
            inputs[name] = (slot, _artifact(reader, slots, slot))
        inputs["model"] = (target_node["model_ref"]["id"], _artifact(reader, slots, target_node["model_ref"]["id"]))
        inputs["profile"] = (target_node["profile_ref"]["id"], _artifact(reader, slots, target_node["profile_ref"]["id"]))
        if len(inputs["proof_source"][1]) > T.MAX_PROOF_BYTES:
            raise _fail("UNSUPPORTED_CAPABILITY", "proof module exceeds the frozen size budget", cid)
        ir_slot = next(s for s, a in slots.items() if a["role"] == "accepted_ir")
        cert_slot = next(s for s, a in slots.items() if a["role"] == "acceptance_certificate")
        accepted_ir = _artifact(reader, slots, ir_slot, json=True)
        acceptance = _artifact(reader, slots, cert_slot, json=True)
        if accepted_ir.get("acceptance_certificate_ref") != slots[cert_slot]["path"] or \
                plan["accepted_ir"] != slots[ir_slot]["sha256"] or plan["acceptance_certificate"] != slots[cert_slot]["sha256"]:
            raise _fail("STATEMENT_MISMATCH", "accepted IR and acceptance certificate are not the frozen pair", cid)
        prof_ref = acceptance["artifacts"]["profile"]
        olean_ref = acceptance["artifacts"]["olean"]
        prof_art, olean_art = _by_path(slots, prof_ref["path"]), _by_path(slots, olean_ref["path"])
        if prof_art["sha256"] != prof_ref["sha256"] or olean_art["sha256"] != olean_ref["sha256"]:
            raise _fail("INPUT_MUTATION", "accepted profile/module bytes differ from the acceptance certificate")
        accepted_profile = _artifact(reader, slots, prof_art["slot_id"], json=True)
        contract_module = _artifact(reader, slots, olean_art["slot_id"])
        matches = [p for p in policymod.POLICIES.values()
                   if p["id"] == acceptance["policy"]["id"] and policymod.policy_hash(p) == acceptance["policy"]["hash"]]
        if len(matches) != 1 or acceptance["gate"] != "accepted_and_proved":
            raise _fail("STATEMENT_MISMATCH", "accepted contract does not use one exact registered strict policy")
        obligations = {}
        for ob in plan["obligations"]:
            if edge["claim_id"] not in ob["required_claims"]:
                continue
            rec = accepted_ir["obligations"].get(ob["id"])
            if rec is None or rec["revision"] != ob["revision"] or rec["formal"]["statement_hash"] != ob["accepted_statement_hash"]:
                raise _fail("STATEMENT_MISMATCH", f"{ob['id']} differs from the accepted IR", cid)
            if rec["formal"]["representation"] not in {"contract_dsl", "source_facets"}:
                raise _fail("UNSUPPORTED_CAPABILITY",
                            f"{ob['id']} is not a contract-DSL statement; {T.TEMPLATE} has no transfer rule for it", cid)
            digest = rec["formal"]["formula_ref"].rsplit("@", 1)[-1]
            package = None
            for a in slots.values():
                if a["sha256"] == digest and a["path"].endswith("/expressions/" + digest[7:] + ".json"):
                    package = _artifact(reader, slots, a["slot_id"], json=True)
            obligations[ob["id"]] = _obligation_from_package(ob["id"], rec, package, accepted_profile, cid)
        if not obligations:
            raise _fail("ORPHAN_CLAIM", "the edge is required by no accepted obligation", cid)
        selection = None
        diagnostic_map = {}
        if R.SELECTION_SLOT in slots:
            sr = slots[R.SELECTION_SLOT]
            declared=next((s for s in plan["artifact_slots"] if s["slot_id"]==R.SELECTION_SLOT),None)
            if declared is None or declared["role"]!=R.SELECTION_ROLE or declared["node_id"]!=target_node["node_id"] or sr["role"] != R.SELECTION_ROLE or sr["path"] != "candidate-inputs/"+R.SELECTION_PATH:
                raise _fail("INVALID_CANDIDATE", "readable selection has a redirected role/node/path", cid)
            selection = _artifact(reader, slots, R.SELECTION_SLOT)
            metadata = readable_candidate_metadata(selection, lambda p: reader.read("candidate-inputs/"+p, keep=True).data)
            for i, (path, data) in enumerate((p,d) for p,d in metadata.items() if p != R.SELECTION_PATH):
                row = slots.get(f"vscore-readable-diagnostic-{i}")
                declared=next((s for s in plan["artifact_slots"] if s["slot_id"]==f"vscore-readable-diagnostic-{i}"),None)
                if declared is None or declared["role"]!="readable_diagnostic" or declared["node_id"]!=target_node["node_id"] or row is None or row["role"] != "readable_diagnostic" or row["path"] != "candidate-inputs/"+path or row["sha256"] != canonical.digest(data):
                    raise _fail("INPUT_MUTATION", "readable diagnostic is not an exact frozen slot", cid)
                diagnostic_map[path] = data
        elif any(s["role"] in (R.SELECTION_ROLE,"readable_diagnostic") for s in slots.values()):
            raise _fail("INVALID_CANDIDATE", "readable metadata must use the exact selection slot", cid)
        reader.recheck()
        return EdgeContext(bridge_id, plan, plan_snap.sha256, manifest_snap.sha256, edge, claim, slots, relation,
                           inputs, accepted_ir, acceptance, accepted_profile, prof_ref["sha256"], contract_module,
                           dict(matches[0]), obligations, selection, diagnostic_map)
    except InvalidPackage as exc:
        raise _fail(exc.code, str(exc)) from None
    finally:
        reader.close()


def _obligation_from_package(oid: str, rec: dict, package: dict, profile: dict, cid: str | None = None) -> dict:
    encodings = {"verislop.contract-dsl/0.1", "verislop.contract-dsl/0.2"}
    representation = rec["formal"]["representation"]
    if not isinstance(package, dict) or package.get("semantic_profile") != profile.get("profile_id") or \
            (representation == "contract_dsl" and package.get("encoding") not in encodings) or \
            (representation == "source_facets" and package.get("encoding") != source_contract.ENCODING):
        raise _fail("STATEMENT_MISMATCH", f"{oid}: accepted formula package is missing or foreign", cid)
    value = source_contract.value_package(package)
    if value is not None and (not isinstance(value, dict) or value.get("encoding") not in encodings or \
                             value.get("semantic_profile") != profile.get("profile_id")):
        raise _fail("STATEMENT_MISMATCH", f"{oid}: accepted value facet is foreign", cid)
    facets = source_contract.source_facets(package)
    if representation == "source_facets" and not facets:
        raise _fail("STATEMENT_MISMATCH", f"{oid}: accepted source facet is missing", cid)
    return {"formula": value["formula"] if value else None, "source_facets": facets,
            "lean_symbol": rec["formal"]["lean_symbol"], "statement_hash": rec["formal"]["statement_hash"],
            "revision": rec["revision"]}


def derive_goal(ctx: EdgeContext) -> T.GoalSpec:
    """Check the node's model/profile copies and derive the goal from accepted inputs only."""
    cid = ctx.claim["claim_id"]
    pin = ctx.acceptance["toolchain"]["pin"]
    model = canonical.dumps(T.model_descriptor(pin))
    profile = canonical.dumps(T.profile_descriptor(ctx.accepted_profile, ctx.accepted_profile_hash))
    if ctx.inputs["model"][1] != model:
        raise _fail("STATEMENT_MISMATCH", "node model is not the registered VSCore semantic model descriptor", cid)
    if ctx.inputs["profile"][1] != profile:
        raise _fail("STATEMENT_MISMATCH", "node profile is not the representation profile derived from the accepted registry", cid)
    try:
        spec = T.build_goal(ctx.inputs["source"][1], ctx.relation, ctx.accepted_profile, ctx.obligations)
        if ctx.readable_selection is not None:
            selection = RS.checked_json("vscore-readable-selection", ctx.readable_selection)
            if selection["selected_mode"] == "CHECKED":
                try:
                    spec = T.enrich_readable(spec)
                except R.Unavailable as exc:
                    raise _fail("INPUT_MUTATION", f"frozen CHECKED renderer unavailable: {exc}", cid) from None
            spec.readable_selection = ctx.readable_selection
        return spec
    except T.BridgeUnsupported as exc:
        raise _fail("UNSUPPORTED_CAPABILITY", str(exc), cid) from None
    except T.BridgeInvalid as exc:
        raise _fail(exc.code, str(exc), cid) from None


# ------------------------------------------------------------------------------------------
# one isolated build
# ------------------------------------------------------------------------------------------

@dataclass
class Build:
    observation: dict
    decls: dict[str, dict]
    modules: dict[str, dict[str, bytes]]
    proposition_hash: str
    ir: dict
    axioms: list[str]
    # Actual process observations are hash-bound in raw evidence, not compared
    # across clean builds or included in the semantic certificate descriptor.
    process_evidence: dict[str, dict] = field(default_factory=dict)
    readable_support: dict | None = None
    readable_artifacts: dict[str, bytes] = field(default_factory=dict)


def _parts_digest(parts: dict[str, bytes]) -> str:
    return canonical.digest_json({suffix: canonical.digest(data) for suffix, data in sorted(parts.items())})


def _attach_build_process_evidence(exc: EdgeFailure | VeriSlopError, inventory: dict):
    for diagnostic in exc.diagnostics:
        diagnostic.details = {**diagnostic.details, "build_process_evidence": copy.deepcopy(inventory)}
    return exc


def _compile_failure(code: str, message: str, ctx: EdgeContext, spec: T.GoalSpec,
                     module: str, source: bytes, result: leanbridge.CompileResult,
                     *, severity: str = "blocking", process_inventory: dict | None = None) -> EdgeFailure:
    """Preserve every reported error before the isolated build is removed."""
    details = {"format": "verislop.vscore-compile-diagnostics/1", "module": module,
               "module_source_hash": canonical.digest(source), "goal_hash": canonical.digest(spec.text.encode()),
               "input_hashes": {name: canonical.digest(data) for name, (_, data) in sorted(ctx.inputs.items())},
               "error_count": len(result.errors), "errors": result.errors, "messages": result.messages,
               "sorry_positions": result.sorry_positions, "timed_out": result.timed_out,
               "stderr": result.raw_stderr,
               "stderr_retention": {"tail_only_max_chars": 4000, "may_be_truncated": True},
               "process_evidence": leanbridge.compile_process_details(result)}
    if process_inventory is not None:
        details["build_process_evidence"] = copy.deepcopy(process_inventory)
    return EdgeFailure([Diagnostic(code, f"{message} ({len(result.errors)} reported errors; full inventory in details)",
                                   severity=severity, claims=[ctx.claim["claim_id"]], details=details)])


def _run_build_once(tc: leanbridge.Toolchain, ctx: EdgeContext, spec: T.GoalSpec, *, with_proof: bool = True) -> Build:
    """One isolated build. Without the proof, only the library, contract and goal are replayed."""
    cid = ctx.claim["claim_id"]
    pol = ctx.policy
    opts = {"timeout": pol["build_timeout_seconds"], "memory_mb": pol["memory_mb"],
            "require_network_isolation": pol["require_network_isolation"],
            "require_filesystem_isolation": pol["require_filesystem_isolation"]}
    compiles: dict[str, dict] = {}
    processes: dict[str, dict] = {}

    def compile_once(directory: Path, module: str, source: bytes, dependencies: dict, *, read_only: list[Path]):
        try:
            result, parts = leanbridge.compile_named_module(tc, directory, module, source, dependencies,
                                                           read_only=read_only, **opts)
        except VeriSlopError as exc:
            for diagnostic in exc.diagnostics:
                if "process_evidence" in diagnostic.details:
                    processes[module] = copy.deepcopy(diagnostic.details["process_evidence"])
            raise _attach_build_process_evidence(exc, processes)
        processes[module] = leanbridge.compile_process_details(result)
        if getattr(spec,"readable_view",None) is not None and module == T.GOAL_MODULE:
            record=processes[module].get("record",{})
            if any(record.get(stream,{}).get("byte_count",0)>R.BUDGETS["optional_"+stream+"_bytes"] for stream in ("stdout","stderr")):
                raise _compile_failure("UNSUPPORTED_CAPABILITY","optional readable compiler output budget exceeded",
                    ctx,spec,module,source,result,process_inventory=processes)
        return result, parts

    with fsutil.temporary_directory(prefix="verislop-vscore-build-") as tmp:
        root = Path(tmp)
        lib, contract, goal, proof = (root / d for d in ("lib", "contract", "goal", "proof"))
        modules: dict[str, dict[str, bytes]] = {}
        deps: dict[str, dict[str, str]] = {}
        for m, source in T.library_sources().items():
            res, parts = compile_once(lib, m, source, dict(deps), read_only=[])
            compiles[m] = {"ok": res.ok, "errors": res.errors, "sorries": len(res.sorry_positions)}
            if not res.ok or res.sorry_positions:
                raise _compile_failure("VERIFIER_FAILURE", f"verifier-owned library module {m} failed to build",
                                       ctx, spec, m, source, res, severity="infrastructure", process_inventory=processes)
            modules[m] = parts
            deps[m] = {s: str(lib / (leanbridge.module_relpath(m) + s)) for s in parts}
        contract.mkdir()
        staged = contract / "bundle"
        staged.write_bytes(ctx.contract_module)
        try:
            leanbridge._stage_module(staged, contract)
            staged.unlink()
            modules[T.CONTRACT_MODULE] = leanbridge.module_parts(contract, T.CONTRACT_MODULE)
        except VeriSlopError as exc:
            raise _attach_build_process_evidence(exc, processes)
        deps[T.CONTRACT_MODULE] = {s: str(contract / (T.CONTRACT_MODULE + s)) for s in modules[T.CONTRACT_MODULE]}
        res, parts = compile_once(goal, T.GOAL_MODULE, spec.text.encode(), dict(deps), read_only=[lib, contract])
        compiles[T.GOAL_MODULE] = {"ok": res.ok, "errors": res.errors, "sorries": len(res.sorry_positions)}
        if not res.ok or res.sorry_positions:
            raise _compile_failure("UNSUPPORTED_CAPABILITY",
                                   "the derived bridge goal could not be established for this program and contract "
                                   "(parse/typing equations, adapters or transfer proofs)",
                                   ctx, spec, T.GOAL_MODULE, spec.text.encode(), res, process_inventory=processes)
        modules[T.GOAL_MODULE] = parts
        deps[T.GOAL_MODULE] = {s: str(goal / (T.GOAL_MODULE + s)) for s in parts}
        isolation = res.isolation
        if with_proof:
            res, parts = compile_once(proof, T.PROOF_MODULE, ctx.inputs["proof_source"][1], dict(deps),
                                      read_only=[lib, contract, goal])
            compiles[T.PROOF_MODULE] = {"ok": res.ok, "errors": res.errors, "sorries": len(res.sorry_positions),
                                        "timed_out": res.timed_out}
            if not res.ok:
                raise _compile_failure("CANDIDATE_BUILD_FAILURE", "candidate proof module failed to elaborate",
                                       ctx, spec, T.PROOF_MODULE, ctx.inputs["proof_source"][1], res,
                                       process_inventory=processes)
            modules[T.PROOF_MODULE] = parts
            isolation = res.isolation
        for m, ps in modules.items():
            # The candidate compile could only read these artifacts; rebind them after it ran.
            if m != T.PROOF_MODULE:
                base = {T.CONTRACT_MODULE: contract, T.GOAL_MODULE: goal}.get(m, lib)
                try:
                    current_parts = leanbridge.module_parts(base, m)
                except VeriSlopError as exc:
                    raise _attach_build_process_evidence(exc, processes)
                if current_parts != ps:
                    raise _attach_build_process_evidence(
                        _fail("INPUT_MUTATION", f"dependency module {m} changed during the candidate build", cid), processes)
        # The build directory is fresh for every invocation. Preserve every isolation
        # property while replacing only that explicitly volatile directory prefix.
        isolation = dict(isolation)
        isolation["read_only_paths"] = [
            "<build>/" + str(Path(path).relative_to(root)) if Path(path).is_relative_to(root) else path
            for path in isolation.get("read_only_paths", [])
        ]
    root_module = T.PROOF_MODULE if with_proof else T.GOAL_MODULE
    try:
        resp = leanbridge.run_kernel_tool_modules(tc, modules, root_module, {"export": True, "axioms": True},
                                                  timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                                  require_network_isolation=pol["require_network_isolation"],
                                                  require_filesystem_isolation=pol["require_filesystem_isolation"])
        if getattr(spec,"readable_view",None) is not None and len(canonical.dumps(resp))>R.BUDGETS["optional_kernel_response_bytes"]:
            raise _fail("UNSUPPORTED_CAPABILITY","optional readable kernel response budget exceeded",cid)
        build = _audit(tc, ctx, spec, resp, modules, compiles, isolation, with_proof)
    except (EdgeFailure, VeriSlopError) as exc:
        raise _attach_build_process_evidence(exc, processes)
    build.process_evidence = processes
    return build


def _audit(tc: leanbridge.Toolchain, ctx: EdgeContext, spec: T.GoalSpec, resp: dict,
           modules: dict[str, dict[str, bytes]], compiles: dict, isolation: dict, with_proof: bool) -> Build:
    cid = ctx.claim["claim_id"]
    pol = ctx.policy
    pin = ctx.acceptance["toolchain"]["pin"]
    imp, rep = resp.get("import", {}), resp.get("replay", {})
    if not imp.get("ok"):
        raise _fail("KERNEL_REJECTION", f"kernel tool could not import the module set: {imp.get('error')}", cid)
    if not rep.get("ok"):
        raise _fail("KERNEL_REJECTION", f"kernel replay rejected the module set: {rep.get('error')}", cid)
    staged = {".".join(str(c) for c in m["name"]) for m in imp["modules"] if m.get("staged")}
    if staged != set(modules):
        raise _fail("UNDECLARED_DEPENDENCY", "imported staged modules differ from the bound module set", cid)
    toolchain_modules = [m for m in imp["modules"] if not m.get("staged")]
    for m in toolchain_modules:
        root = str(m["name"][0]) if m["name"] else ""
        if root not in pol["allowed_import_roots"]:
            raise _fail("UNDECLARED_DEPENDENCY", f"import {name_str(m['name'])} is outside the allowed toolchain roots", cid)
    closure_id, diags = leanbridge.olean_closure_identity(tc, toolchain_modules)
    if diags:
        raise EdgeFailure([Diagnostic(d.code, d.message, claims=[cid]) for d in diags])
    if with_proof and T.GOAL_MODULE not in {name_str(n) for n in imp.get("direct_imports", [])}:
        raise _fail("UNDECLARED_DEPENDENCY", "the proof module must import the generated goal module", cid)
    skipped: set[str] = set()
    for n in rep.get("not_replayed_unsafe_or_partial", []):
        # Compiler auxiliaries of structural recursion are unsafe by construction and never
        # replayed; kernel terms cannot mention them (the axiom walk reports unresolved names).
        if not (isinstance(n[-1], str) and n[-1] == "_unsafe_rec"):
            raise _fail("KERNEL_REJECTION", f"unsafe or partial declaration {name_str(n)} was not replayed", cid)
        skipped.add(name_str(n))
    decls: dict[str, dict] = {}
    for c in resp.get("constants", []):
        n = name_str(c["name"])
        if c.get("kind") == "missing_after_replay" and n in skipped:
            continue
        if "export_error" in c or c.get("kind") == "missing_after_replay":
            raise _fail("KERNEL_REJECTION", f"declaration {n} could not be exported after replay", cid)
        decls[n] = c
    proof_decls = {n: c for n, c in decls.items() if c.get("module") == [T.PROOF_MODULE]}
    goal_decls = {n: c for n, c in decls.items() if c.get("module") == [T.GOAL_MODULE]}
    if pol["forbid_module_axioms"] and any(c["kind"] == "axiom" for c in proof_decls.values()):
        raise _fail("INADMISSIBLE_AXIOM", "the candidate proof module declares an axiom", cid)
    for n, c in proof_decls.items():
        if c.get("safety") != "safe":
            raise _fail("INADMISSIBLE_AXIOM", f"the candidate proof module declares a non-safe declaration {n}", cid)
    for n, c in proof_decls.items():
        # Lean adds equation lemmas (theorems) for library definitions on first use; anything
        # else in a verifier-owned namespace is rejected as hygiene (names cannot be replaced).
        if (n.startswith(T.GOAL_MODULE + ".") or n.startswith(("VSCore.", "VSCore3."))) and c["kind"] != "theorem":
            raise _fail("STATEMENT_MISMATCH", f"the candidate proof module declares {n} in a verifier-owned namespace", cid)
    axioms: list[str] = []
    if with_proof:
        edge = proof_decls.get(T.EDGE_THEOREM)
        if edge is None or edge["kind"] != "theorem" or edge.get("level_params"):
            raise _fail("PROOF_UNRESOLVED", f"no theorem {T.EDGE_THEOREM} in the candidate proof module", cid)
        if not T.same_expr(edge["type"], T.const(T.EDGE_PROP)):
            raise _fail("STATEMENT_MISMATCH", f"{T.EDGE_THEOREM} does not have the frozen type {T.EDGE_PROP}", cid)
        if edge.get("unresolved_constants"):
            raise _fail("UNDECLARED_DEPENDENCY", f"{T.EDGE_THEOREM} depends on unresolved constants", cid)
        axioms = sorted(name_str(a) for a in edge.get("axioms", []))
        for ax in axioms:
            kind = policymod.classify_axiom(ax, pol)
            if kind == "sorry":
                raise _fail("PROOF_UNRESOLVED", f"{T.EDGE_THEOREM} depends on sorry", cid)
            if kind != "allowed":
                raise _fail("INADMISSIBLE_AXIOM", f"{T.EDGE_THEOREM} depends on {kind} axiom {ax}", cid)
    bad = T.statement_mismatches(spec, goal_decls)
    if bad:
        raise _fail("STATEMENT_MISMATCH", f"replayed goal statements differ from the derived statements: {', '.join(bad)}", cid)
    for ob in spec.obligations:
        thm = goal_decls.get(f"{T.GOAL_MODULE}.transfer_{ob.oid}")
        if thm is None or thm["kind"] != "theorem" or ob.lean_symbol not in {name_str(n) for n in thm.get("value_constants", [])}:
            raise _fail("STATEMENT_MISMATCH", f"{ob.oid}: transfer theorem is not derived from the accepted theorem", cid)
    nonproof = {n: c for n, c in decls.items() if c.get("module") != [T.PROOF_MODULE]}
    prop_hash, closure = T.proposition_hash(nonproof, pin)
    try:
        ir_body = T.reexport(spec, goal_decls)
    except T.BridgeInvalid as exc:
        raise _fail(exc.code, str(exc), cid) from None
    if canonical.dumps(ir_body["program"]) != spec.source_bytes:
        raise _fail("IR_REIFICATION_MISMATCH", "re-exported program does not re-encode to the exact source bytes", cid)
    export_digest = canonical.digest_json([{k: v for k, v in c.items()} for c in resp.get("constants", [])])
    observation = {
        "format": "verislop.vscore-build/0.3",
        "lean_toolchain": tc.identity(), "kernel_tool_hash": leanbridge.kernel_tool_hash(),
        "kernel_tool_version": resp.get("tool_version"),
        "toolchain_olean_closure": closure_id,
        "compiles": compiles,
        "modules": {m: _parts_digest(p) for m, p in sorted(modules.items())},
        "replayed_constants": rep.get("constants"),
        "export_digest": export_digest,
        "proposition_hash": prop_hash,
        "proposition_closure_size": len(closure),
        "edge_axioms": axioms,
        "implementation_ir_digest": canonical.digest_json(ir_body),
        "isolation": isolation,
        "readable_support": None,
    }
    return Build(observation, decls, modules, prop_hash, ir_body, axioms)


DETERMINISTIC = ("format", "lean_toolchain", "kernel_tool_hash", "kernel_tool_version", "toolchain_olean_closure",
                 "compiles", "modules", "replayed_constants", "export_digest", "proposition_hash",
                 "proposition_closure_size", "edge_axioms", "implementation_ir_digest", "isolation", "readable_support")


def _phase_processes(base: Build, selected: Build | None = None, failure=None) -> dict:
    later = selected.process_evidence if selected else {}
    if failure:
        for d in failure.diagnostics:
            later.update(d.details.get("build_process_evidence", {}))
    return {**{"BASE::"+m:r for m,r in base.process_evidence.items()},
            **{"SELECTED::"+m:r for m,r in later.items()}}


def run_build(tc: leanbridge.Toolchain, ctx: EdgeContext, spec: T.GoalSpec, *, with_proof: bool = True) -> Build:
    """Admit base first, then replay frozen optional support without downgrading."""
    if getattr(spec,"readable_selection",None) is None:
        return _run_build_once(tc,ctx,spec,with_proof=with_proof)
    base_spec = T.build_goal(spec.source_bytes,ctx.relation,ctx.accepted_profile,ctx.obligations)
    selection = RS.checked_json("vscore-readable-selection",spec.readable_selection)
    if selection["selected_mode"] == "BASE":
        if spec.text != base_spec.text:
            raise _fail("INPUT_MUTATION","frozen BASE readable selection has enriched goal text")
        base = _run_build_once(tc,ctx,base_spec,with_proof=with_proof)
        return RS.attach(ctx,spec,base,base,spec.readable_selection)
    base = _run_build_once(tc,ctx,base_spec,with_proof=False)
    RS.validate_binding(ctx,spec,base,spec.readable_selection)
    expected = T.enrich_readable(base_spec)
    if spec.text != expected.text or spec.expected != expected.expected:
        raise _fail("INPUT_MUTATION","selected readable goal differs from exact source regeneration")
    try:
        selected = _run_build_once(tc,ctx,spec,with_proof=with_proof)
        audited = RS.audit(ctx,spec,base,selected)
        selected = RS.attach(ctx,spec,base,selected,spec.readable_selection,audited)
    except (EdgeFailure,VeriSlopError) as exc:
        raise _attach_build_process_evidence(exc,_phase_processes(base,failure=exc))
    selected.process_evidence = _phase_processes(base,selected)
    return selected


def _select_readable(tc, ctx, spec):
    """Source preview only: optional failure returns exactly the admitted base."""
    base = _run_build_once(tc,ctx,spec,with_proof=False)
    candidate, selected, audited, failure = spec, None, None, None
    reasons, diagnostics, diagnostic_bytes = [], [], {}
    try:
        candidate = T.enrich_readable(spec)
        selected = _run_build_once(tc,ctx,candidate,with_proof=False)
        audited = RS.audit(ctx,candidate,base,selected)
    except R.Unavailable as exc:
        reasons=[{"code":exc.code,"stage":"rendering","source_path":None,"message":str(exc),
                  "reported_error_count":0,"diagnostic_artifact":None,"diagnostic_complete":True}]
    except (EdgeFailure,VeriSlopError) as exc:
        failure=exc
        hard = {"INPUT_MUTATION", "SANDBOX_UNAVAILABLE", "TOOLCHAIN_UNAVAILABLE"}
        if any(d.code in hard or (d.severity=="infrastructure" and d.details.get("module") != T.GOAL_MODULE) for d in exc.diagnostics):
            raise _attach_build_process_evidence(exc,_phase_processes(base,failure=exc))
        path="support/readable/diagnostics/0.json"
        data=canonical.dumps({"format":"verislop.readable-optional-diagnostics/1",
             "source_hash":canonical.digest(spec.source_bytes),"selected_goal_hash":canonical.digest(candidate.text.encode()),
             "proposed_goal":candidate.text,
             "proposed_source_block":candidate.readable_view.block.decode() if candidate.readable_view else None,
             "proposed_correspondence":candidate.readable_correspondence.decode() if candidate.readable_correspondence else None,
             "diagnostics":[d.to_json() for d in exc.diagnostics]})
        diagnostic_bytes[path]=data
        a=RS.ref(path,data)
        diagnostics=[{"slot_id":"vscore-readable-diagnostic-0","role":"readable_diagnostic","artifact":a}]
        reasons=[{"code":"OPTIONAL_UNAVAILABLE","stage":"compile" if any(d.details.get("module")==T.GOAL_MODULE for d in exc.diagnostics) else "audit",
             "source_path":None,"message":"; ".join(d.message for d in exc.diagnostics),
             "reported_error_count":sum(d.details.get("error_count",0) for d in exc.diagnostics),
             "diagnostic_artifact":a,"diagnostic_complete":True}]
    if not audited:
        candidate,selected=spec,base
    record=RS.selection_record(ctx,candidate,base,audit=audited,reasons=reasons,diagnostics=diagnostics)
    selection=canonical.dumps(record); RS.checked_json("vscore-readable-selection",selection)
    ctx.readable_selection,ctx.readable_diagnostics=selection,diagnostic_bytes
    candidate.readable_selection=selection
    selected=RS.attach(ctx,candidate,base,selected,selection,audited)
    if audited or failure:
        selected.process_evidence=_phase_processes(base,selected if audited else None,failure)
    return candidate,selected


# ------------------------------------------------------------------------------------------
# acceptance
# ------------------------------------------------------------------------------------------

def check_edge(tc: leanbridge.Toolchain, ctx: EdgeContext) -> tuple[T.GoalSpec, Build, Build]:
    cid = ctx.claim["claim_id"]
    spec = derive_goal(ctx)
    a = run_build(tc, ctx, spec)
    if a.proposition_hash != ctx.edge["expected_proposition_hash"]:
        raise _fail("STATEMENT_MISMATCH", "the frozen expected proposition hash is not the derived bridge goal "
                    f"(derived {a.proposition_hash}); prepare a new bridge with the hash printed by `verislop vscore goal`", cid)
    b = run_build(tc, ctx, spec)
    differ = [k for k in DETERMINISTIC if a.observation[k] != b.observation[k]]
    if differ:
        raise _fail("NONDETERMINISM", f"isolated builds disagree on {', '.join(differ)}", cid)
    return spec, a, b


def _semantic_descriptor(ctx: EdgeContext, spec: T.GoalSpec, axioms: list[str], readable_support: dict | None = None) -> dict:
    """Certificate identities derived from frozen inputs, never from certificate metadata.

    The axiom inventory is a checked-build result; callers validating an existing
    certificate also bind it to both stored observations and the policy.
    """
    root = semantic_edge_root(ctx.plan_hash, ctx.artifacts_hash, ctx.edge)
    inputs = {k: {"slot_id": slot, "sha256": canonical.digest(data)} for k, (slot, data) in ctx.inputs.items()}
    obligations = [{"id": ob.oid, "revision": ctx.obligations[ob.oid]["revision"],
                    "accepted_statement_hash": ob.statement_hash, "accepted_theorem": ob.lean_symbol,
                    "transfer": f"{T.GOAL_MODULE}.Transfer_{ob.oid}", "transfer_theorem": f"{T.GOAL_MODULE}.transfer_{ob.oid}"}
                   for ob in spec.obligations]
    descriptor = {"schema_version": "0.3", "format": "verislop.vscore-edge-certificate/0.3",
            "bridge_id": ctx.bridge_id, "edge_id": ctx.edge["edge_id"], "claim_id": ctx.claim["claim_id"],
            "template": T.TEMPLATE, "tier": 2, "endpoint": T.ENDPOINT, "language": T.LANGUAGE, "semantics": T.SEMANTICS,
            "plan_hash": ctx.plan_hash, "artifacts_hash": ctx.artifacts_hash, "semantic_edge_root": root,
            "accepted_ir": ctx.plan["accepted_ir"], "acceptance_certificate": ctx.plan["acceptance_certificate"],
            "inputs": inputs, "proposition_hash": ctx.edge["expected_proposition_hash"],
            "theorem": {"module": T.PROOF_MODULE, "symbol": T.EDGE_THEOREM, "proposition": T.EDGE_PROP, "axioms": axioms},
            "statement_identity": sorted(f"{T.GOAL_MODULE}.{n}" for n in spec.expected),
            "symbols": [{"symbol": s.symbol, "entry": s.entry, "lean_decl": s.lean_decl} for s in spec.symbols],
            "obligations": obligations,
            "goal": {"path": "goal/VeriSlopBridgeGoal.lean", "sha256": canonical.digest(spec.text.encode())},
            "checker": {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)},
            "kernel_tool_hash": leanbridge.kernel_tool_hash(), "lean_toolchain": ctx.acceptance["toolchain"]["pin"],
            "semantic_acceptance": True, "assigns_end_to_end_verified": False}
    if readable_support is not None:
        descriptor["readable_support"] = readable_support
    return descriptor


def _certificate_descriptor(cert: dict) -> dict:
    """All certificate fields except the time-dependent evidence reference.

    Evidence records include a recorded_at timestamp. Build observations normalize
    their temporary directory prefix before hashing; no semantic field is omitted.
    """
    return {key: value for key, value in cert.items() if key != "evidence"}


def _evidence_result(cert: dict) -> dict:
    result = {"bridge_id": cert["bridge_id"], "edge_id": cert["edge_id"], "plan_hash": cert["plan_hash"],
            "artifacts_hash": cert["artifacts_hash"], "semantic_edge_root": cert["semantic_edge_root"],
            "template": cert["template"], "proposition_hash": cert["proposition_hash"],
            "proof_symbol": cert["theorem"]["symbol"], "edge_axioms": cert["theorem"]["axioms"],
            "inputs": cert["inputs"], "accepted_modules": cert["accepted_modules"],
            "obligations": [o["id"] for o in cert["obligations"]],
            "implementation_ir_hash": cert["implementation_ir"]["sha256"],
            "builds": [b["sha256"] for b in cert["builds"]],
            "certificate_descriptor_hash": canonical.digest_json(_certificate_descriptor(cert)),
            "semantic_acceptance": True, "assigns_end_to_end_verified": False}
    if "readable_support" in cert:
        result["readable_support"] = cert["readable_support"]
    return result


def outputs(ctx: EdgeContext, spec: T.GoalSpec, a: Build, b: Build, run_id: str, stage: Path) -> dict[str, bytes]:
    """Certificate, IR, all accepted module parts, build records and bound evidence."""
    files: dict[str, bytes] = {"goal/VeriSlopBridgeGoal.lean": spec.text.encode(), **a.readable_artifacts}
    if a.readable_artifacts != b.readable_artifacts or a.readable_support != b.readable_support:
        raise _fail("NONDETERMINISM","clean builds disagree on complete readable support artifacts")
    accepted = []
    for m in (T.GOAL_MODULE, T.PROOF_MODULE):
        for suffix, data in sorted(a.modules[m].items()):
            path = f"accepted/{m}{suffix}"
            files[path] = data
            accepted.append({"module": m, "path": path, "sha256": canonical.digest(data)})
    ir = {"schema_version": "0.3", "format": T.IR_FORMAT, "language": T.LANGUAGE, "semantics": T.SEMANTICS,
          "bridge_id": ctx.bridge_id, "edge_id": ctx.edge["edge_id"], "claim_id": ctx.claim["claim_id"],
          "source": {"slot_id": ctx.inputs["source"][0], "size": len(spec.source_bytes),
                     "sha256": canonical.digest(spec.source_bytes)},
          "accepted_ir": ctx.plan["accepted_ir"], "acceptance_certificate": ctx.plan["acceptance_certificate"],
          "proposition_hash": a.proposition_hash,
          "accepted_modules": [{"module": x["module"], "sha256": x["sha256"]}
                               for x in accepted if x["path"].endswith(".olean")],
          **a.ir, "exporter": {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)}}
    if a.readable_support is not None:
        ir["readable_support"] = a.readable_support
    _schema("vscore-implementation-ir-v3", ir)
    files[IR_FILE] = canonical.dumps(ir)
    for label, build in (("A", a), ("B", b)):
        files[f"builds/{label}.json"] = canonical.dumps(build.observation)
    cert = {**_semantic_descriptor(ctx, spec, a.axioms,a.readable_support),
            "accepted_modules": accepted,
            "implementation_ir": {"path": IR_FILE, "sha256": canonical.digest(files[IR_FILE])},
            "builds": [{"path": f"builds/{x}.json", "sha256": canonical.digest(files[f"builds/{x}.json"])} for x in "AB"]}
    evidence = EvidenceStore(stage, run_id).record(
        claim_id=ctx.claim["claim_id"], verifier_id=VERIFIER, status="PASS", scope=SCOPE,
        input_root=cert["semantic_edge_root"],
        result={**_evidence_result(cert), "compile_process_evidence": {
            "format": "verislop.vscore-compile-process-inventory/1",
            "builds": {"A": a.process_evidence, "B": b.process_evidence}}},
        invocation=["verislop", "bridge", "accept", "--bridge-id", ctx.bridge_id])
    ev_path = f"evidence/{evidence.id}.json"
    files[ev_path] = (stage / ev_path).read_bytes()
    files[evidence.record["raw_result_ref"]] = (stage / evidence.record["raw_result_ref"]).read_bytes()
    cert["evidence"] = {"path": ev_path, "sha256": canonical.digest(files[ev_path])}
    _schema("vscore-edge-certificate-v3", cert)
    files[CERTIFICATE] = canonical.dumps(cert)
    return files


def assigned_edges(plan: dict) -> list[dict]:
    claims = {c["claim_id"]: c for c in plan["claims"]}
    return [e for e in plan["edges"] if claims[e["claim_id"]]["verifier_id"] == VERIFIER]


def _bundle(pkg: Package, bridge_id: str) -> Path:
    from .prepare import _bridge_id

    return pkg.root / "bridges" / _bridge_id(bridge_id)


def _summary(result: StageResult, accepted: list[dict], pending: list[str]) -> None:
    result.summary.update({"semantic_certificates": accepted, "semantic_acceptance": bool(accepted) and not pending,
                           "pending_semantic_claims": pending, "assigns_end_to_end_verified": False})


def accept(pkg: Package, bridge_id: str, events: EventSink | None = None) -> StageResult:
    """Run the registered checker on every assigned edge of a prepared bundle and publish results."""
    from .prepare import verify_preparation
    from .publish import publish_into

    result = StageResult("bridge accept", "PASS", GATE, summary={"bridge_id": bridge_id})
    prepared = verify_preparation(pkg, bridge_id)
    if prepared.status != "PASS":
        result.status, result.diagnostics = prepared.status, prepared.diagnostics
        return result
    bundle = _bundle(pkg, bridge_id)
    try:
        plan = canonical.load_file(bundle / "plan.json")
        edges = assigned_edges(plan)
        accepted: list[dict] = []
        pending = sorted(c["claim_id"] for c in plan["claims"]
                         if c["result_predicate"] == "bridge-semantic-edge/0.1" and c["verifier_id"] != VERIFIER)
        if not edges:
            result.diagnostics.append(Diagnostic("UNSUPPORTED_CAPABILITY",
                                                 "no edge of this bridge uses a registered relation template"))
        tc = None
        for edge in edges:
            key = edge_key(edge["edge_id"])
            if os.path.lexists(bundle / SEMANTIC_DIR / key):
                result.diagnostics.append(Diagnostic("INPUT_MUTATION",
                    f"edge {edge['edge_id']} already has a published acceptance; use `bridge verify`",
                    claims=[edge["claim_id"]]))
                pending.append(edge["claim_id"])
                continue
            try:
                ctx = load_context(bundle, bridge_id, edge["edge_id"])
                tc = tc or leanbridge.resolve_toolchain(ctx.acceptance["toolchain"]["pin"])
                spec, a, b = check_edge(tc, ctx)
                with fsutil.temporary_directory(prefix="verislop-vscore-accept-") as tmp:
                    files = outputs(ctx, spec, a, b, pkg.run_id, Path(tmp))
                    publish_into(pkg.root, ["bridges", bridge_id, SEMANTIC_DIR], key, files)
                rel = f"bridges/{bridge_id}/{SEMANTIC_DIR}/{key}"
                accepted.append({"edge_id": edge["edge_id"], "claim_id": edge["claim_id"],
                                 "certificate": f"{rel}/{CERTIFICATE}", "proposition_hash": a.proposition_hash,
                                 "obligations": sorted(ctx.obligations)})
                if events:
                    events.emit("verifier_decision", "bridge accept",
                                f"{bridge_id}: {edge['edge_id']} accepted by {VERIFIER}", outcome="PASS",
                                evidence_ref=f"{rel}/{canonical.loads(files[CERTIFICATE])['evidence']['path']}")
            except EdgeFailure as exc:
                result.diagnostics.extend(exc.diagnostics)
                pending.append(edge["claim_id"])
        for claim in pending:
            if not any(d.claims == [claim] for d in result.diagnostics):
                result.diagnostics.append(Diagnostic("UNSUPPORTED_CAPABILITY",
                    f"{claim}: no registered relation checker accepts this edge", claims=[claim]))
        _summary(result, accepted, sorted(set(pending)))
    except (InvalidPackage, OSError) as exc:
        result.diagnostics.append(Diagnostic(getattr(exc, "code", "VERIFIER_FAILURE"), str(exc),
                                             severity="blocking" if isinstance(exc, InvalidPackage) else "infrastructure"))
    except VeriSlopError as exc:
        result.diagnostics.extend(exc.diagnostics or [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")])
    result.status = status_from(result.diagnostics)
    return result


def _check_descriptor(ctx: EdgeContext, spec: T.GoalSpec, cert: dict, reader: PackageReader) -> None:
    """Check the complete stored description, including without a fresh proof build."""
    cid = ctx.claim["claim_id"]
    axioms = cert["theorem"]["axioms"]
    if axioms != sorted(set(axioms)) or any(policymod.classify_axiom(ax, ctx.policy) != "allowed" for ax in axioms):
        raise _fail("INADMISSIBLE_AXIOM", "published theorem has an inadmissible axiom inventory", cid)
    for key, expected in _semantic_descriptor(ctx, spec, axioms).items():
        if cert[key] != expected:
            raise _fail("STATEMENT_MISMATCH", f"semantic certificate {key} differs from the derived descriptor", cid)
    if ctx.readable_selection is None:
        if "readable_support" in cert:
            raise _fail("STATEMENT_MISMATCH","legacy BASE acceptance cannot claim readable support",cid)
    else:
        if "readable_support" not in cert:
            raise _fail("STATEMENT_MISMATCH","selected readable metadata is absent from certificate",cid)
        refs=readable_artifact_refs(cert["readable_support"],lambda p:reader.read(p,keep=True).data)
        if reader.read(R.SELECTION_PATH,keep=True).data != ctx.readable_selection:
            raise _fail("INPUT_MUTATION","published readable selection differs from frozen candidate",cid)
        if reader.read("readable/selected-goal.lean",keep=True).data!=spec.text.encode() or reader.read("readable/base-goal.lean",keep=True).data!=(spec.base_text or spec.text).encode():
            raise _fail("INPUT_MUTATION","published readable goals differ from regeneration",cid)
    if cert["implementation_ir"]["path"] != IR_FILE or [b["path"] for b in cert["builds"]] != [
            "builds/A.json", "builds/B.json"]:
        raise _fail("STATEMENT_MISMATCH", "semantic certificate redirects a supervisor artifact", cid)

    # Bind every part to its actual file and to the complete module digest reported
    # by both builds. Main .olean hashes alone do not describe module-system files.
    parts: dict[str, dict[str, bytes]] = {m: {} for m in (T.GOAL_MODULE, T.PROOF_MODULE)}
    for artifact in cert["accepted_modules"]:
        module, path = artifact["module"], artifact["path"]
        prefix = f"accepted/{module}"
        suffix = path[len(prefix):] if path.startswith(prefix) else ""
        if module not in parts or suffix not in leanbridge.MODULE_SUFFIXES or suffix in parts[module]:
            raise _fail("STATEMENT_MISMATCH", "semantic certificate has an invalid or duplicate module part", cid)
        snapshot = reader.read(path, keep=True)
        if snapshot.sha256 != artifact["sha256"]:
            raise _fail("INPUT_MUTATION", f"published semantic artifact {path} changed", cid)
        parts[module][suffix] = snapshot.data
    ordered = [{"module": m, "path": f"accepted/{m}{suffix}", "sha256": canonical.digest(data)}
               for m, ps in parts.items() for suffix, data in sorted(ps.items())]
    if ordered != cert["accepted_modules"] or any(".olean" not in ps for ps in parts.values()):
        raise _fail("STATEMENT_MISMATCH", "semantic certificate has an incomplete or unordered module inventory", cid)

    for ref in [cert["goal"], cert["implementation_ir"], *cert["builds"]]:
        if reader.read(ref["path"]).sha256 != ref["sha256"]:
            raise _fail("INPUT_MUTATION", f"published semantic artifact {ref['path']} changed", cid)
    observations = [reader.json(ref["path"])[0] for ref in cert["builds"]]
    expected_modules = set(T.library_sources()) | {T.CONTRACT_MODULE, T.GOAL_MODULE, T.PROOF_MODULE}
    for observation in observations:
        if not isinstance(observation, dict) or set(observation) != set(DETERMINISTIC):
            raise _fail("STATEMENT_MISMATCH", "published build has an incomplete observation inventory", cid)
        if not isinstance(observation["modules"], dict) or set(observation["modules"]) != expected_modules:
            raise _fail("STATEMENT_MISMATCH", "published build has a different module inventory", cid)
        for module, ps in parts.items():
            if observation["modules"][module] != _parts_digest(ps):
                raise _fail("INPUT_MUTATION", f"published parts of {module} differ from the checked build", cid)
        if (observation["proposition_hash"] != cert["proposition_hash"] or
                observation["edge_axioms"] != axioms or observation["kernel_tool_hash"] != cert["kernel_tool_hash"]):
            raise _fail("STATEMENT_MISMATCH", "published build describes a different proposition, policy or kernel tool", cid)
        if observation["readable_support"] != cert.get("readable_support"):
            raise _fail("STATEMENT_MISMATCH","build readable inventory differs from certificate",cid)
    if ctx.readable_selection is not None:
        selected=RS.checked_json("vscore-readable-selection",ctx.readable_selection)
        manifest=RS.checked_json("vscore-readable-view",reader.read(R.MANIFEST_PATH,keep=True).data)
        for key,value in (("inputs",RS.bindings(ctx,spec,Build(observations[0],{}, {},cert["proposition_hash"],{},axioms))),
                          ("renderer",RS.renderer()),("budgets",R.BUDGETS),
                          ("base_goal_hash",canonical.digest((spec.base_text or spec.text).encode())),
                          ("base_proposition_hash",cert["proposition_hash"])):
            if selected[key]!=value:
                raise _fail("INPUT_MUTATION",f"published readable {key} is stale",cid)
        if selected["selected_mode"]=="CHECKED" and selected["checked_descriptor"]["goal_module_parts_hash"]!=_parts_digest(parts[T.GOAL_MODULE]):
            raise _fail("INPUT_MUTATION","published readable proof module binding differs",cid)
    if observations[0] != observations[1]:
        raise _fail("NONDETERMINISM", "published build observations disagree", cid)

    ir, _ = reader.json(IR_FILE)
    _schema("vscore-implementation-ir-v3", ir)
    if ir.get("readable_support") != cert.get("readable_support"):
        raise _fail("STATEMENT_MISMATCH","implementation IR readable support differs from certificate",cid)
    expected_ir = {key: cert[key] for key in ("bridge_id", "edge_id", "claim_id", "accepted_ir",
                                              "acceptance_certificate", "proposition_hash")}
    expected_ir.update({
        "source": {"slot_id": ctx.inputs["source"][0], "size": len(spec.source_bytes),
                   "sha256": canonical.digest(spec.source_bytes)},
        "accepted_modules": [{"module": m, "sha256": canonical.digest(ps[".olean"])} for m, ps in parts.items()],
        "exporter": cert["checker"],
    })
    for key, expected in expected_ir.items():
        if ir[key] != expected:
            raise _fail("STATEMENT_MISMATCH", f"published implementation IR {key} differs from the certificate", cid)
    body = {key: ir[key] for key in ("program", "signatures", "enums", "bindings")}
    if observations[0]["implementation_ir_digest"] != canonical.digest_json(body):
        raise _fail("IR_REIFICATION_MISMATCH", "published implementation IR differs from the checked build", cid)


def verify_published(pkg: Package, bridge_id: str, *, rebuild: bool) -> tuple[list[dict], list[str], list[Diagnostic]]:
    """Check stored acceptances: bindings always; with `rebuild`, re-run the checker and compare outputs."""
    from ..claimcheck import evaluate_claim
    from .check import _evidence

    bundle = _bundle(pkg, bridge_id)
    plan = canonical.load_file(bundle / "plan.json")
    diags: list[Diagnostic] = []
    accepted, pending = [], []
    tc = None
    for edge in assigned_edges(plan):
        cid = edge["claim_id"]
        rel = f"{SEMANTIC_DIR}/{edge_key(edge['edge_id'])}"
        if not os.path.lexists(bundle / rel):
            pending.append(cid)
            continue
        reader: PackageReader | None = None
        try:
            ctx = load_context(bundle, bridge_id, edge["edge_id"])
            reader = PackageReader(bundle / rel)
            cert, _ = reader.json(CERTIFICATE)
            _schema("vscore-edge-certificate-v3", cert)
            root = semantic_edge_root(ctx.plan_hash, ctx.artifacts_hash, ctx.edge)
            if (cert["bridge_id"], cert["edge_id"], cert["claim_id"], cert["plan_hash"], cert["artifacts_hash"],
                    cert["semantic_edge_root"]) != (bridge_id, edge["edge_id"], cid, ctx.plan_hash, ctx.artifacts_hash, root):
                raise _fail("STALE_OR_UNBOUND_EVIDENCE", "semantic certificate is bound to a different frozen edge", cid)
            if cert["checker"] != {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)}:
                raise _fail("STALE_OR_UNBOUND_EVIDENCE", "semantic certificate was issued by a stale or different checker", cid)
            if cert["proposition_hash"] != edge["expected_proposition_hash"]:
                raise _fail("STATEMENT_MISMATCH", "semantic certificate proves a different proposition", cid)
            inputs = {k: {"slot_id": slot, "sha256": canonical.digest(data)} for k, (slot, data) in ctx.inputs.items()}
            if cert["inputs"] != inputs:
                raise _fail("INPUT_MUTATION", "semantic certificate inputs differ from the frozen bundle", cid)
            spec = derive_goal(ctx)
            _check_descriptor(ctx, spec, cert, reader)
            ev = _evidence(reader, cert["evidence"])
            if ev.record["verifier_id"] != VERIFIER:
                raise _fail("STALE_OR_UNBOUND_EVIDENCE", "semantic evidence was issued by a different verifier", cid)
            assessment = evaluate_claim(ctx.claim, [ev], {"semantic_edge": root}, "semantic_edge")
            if assessment.outcome != "PASS":
                raise EdgeFailure(assessment.diagnostics or [Diagnostic("STALE_OR_UNBOUND_EVIDENCE",
                                                                        f"{cid}: {assessment.reason}", claims=[cid])])
            for k, v in _evidence_result(cert).items():
                if ev.result.get(k) != v:
                    raise _fail("STALE_OR_UNBOUND_EVIDENCE", f"semantic evidence {k} does not bind the certificate", cid)
            if rebuild:
                tc = tc or leanbridge.resolve_toolchain(ctx.acceptance["toolchain"]["pin"])
                spec, a, b = check_edge(tc, ctx)
                with fsutil.temporary_directory(prefix="verislop-vscore-verify-") as tmp:
                    fresh = outputs(ctx, spec, a, b, pkg.run_id, Path(tmp))
                fresh_cert = canonical.loads(fresh[CERTIFICATE])
                if _certificate_descriptor(cert) != _certificate_descriptor(fresh_cert):
                    raise _fail("NONDETERMINISM", "fresh builds do not reproduce the complete semantic certificate", cid)
                for path in (IR_FILE, "goal/VeriSlopBridgeGoal.lean", "builds/A.json", "builds/B.json",
                             *(m["path"] for m in cert["accepted_modules"]),
                             *(readable_artifact_refs(cert["readable_support"],lambda p:reader.read(p,keep=True).data) if "readable_support" in cert else [])):
                    if fresh[path] != reader.read(path, keep=True).data:
                        raise _fail("NONDETERMINISM", f"fresh re-check does not reproduce published {path}", cid)
            reader.recheck()
            accepted.append({"edge_id": edge["edge_id"], "claim_id": cid,
                             "certificate": f"bridges/{bridge_id}/{rel}/{CERTIFICATE}",
                             "proposition_hash": cert["proposition_hash"],
                             "obligations": sorted(o["id"] for o in cert["obligations"]), "rechecked": rebuild})
        except EdgeFailure as exc:
            diags.extend(exc.diagnostics)
            pending.append(cid)
        except InvalidPackage as exc:
            diags.append(Diagnostic(exc.code, str(exc), claims=[cid]))
            pending.append(cid)
        finally:
            if reader is not None:
                reader.close()
    return accepted, pending, diags


# ------------------------------------------------------------------------------------------
# candidate-side helper (advisory): derive the goal and its proposition hash from a run
# ------------------------------------------------------------------------------------------

NODE = "vscore-program"
SLOTS = {"source": "vscore-source", "model": "vscore-model", "profile": "vscore-profile",
         "relation": "vscore-relation", "proof": "vscore-proof"}
FILES = {"source": "program.vscore.json", "model": "model.json", "profile": "profile.json",
         "relation": "relation.json", "proof": "Proof.lean"}


def preview(pkg: Package, source: bytes, relation_bytes: bytes, proof: bytes | None = None,
            obligations: list[str] | None = None, *, readable_selection: bytes | None = None,
            select_readable: bool = False, readable_diagnostics: dict[str, bytes] | None = None) -> tuple[T.GoalSpec, Build, dict]:
    """Derive the goal for an accepted run and build it once (with the proof when given).

    This is a convenience for candidate authors; it publishes nothing and is never evidence.
    The registered checker repeats every step from the frozen bundle during `bridge accept`.
    """
    from ..export import verified_ir
    from ..lifecycle import applicability

    if select_readable and (readable_selection is not None or proof is not None or readable_diagnostics):
        raise _fail("INVALID_CANDIDATE","readable selection requires the first proof-free source preview")
    if readable_selection is None and readable_diagnostics:
        raise _fail("INVALID_CANDIDATE","readable diagnostics require exact selection bytes")

    ir, ir_hash, cert, diags = verified_ir(pkg)
    if diags or ir is None or cert is None:
        raise EdgeFailure(diags or [Diagnostic("VERIFIER_NOT_RUN", "no accepted IR")])
    matches = [p for p in policymod.POLICIES.values()
               if p["id"] == cert["policy"]["id"] and policymod.policy_hash(p) == cert["policy"]["hash"]]
    if len(matches) != 1:
        raise _fail("STATEMENT_MISMATCH", "accepted contract does not use one exact registered policy")
    try:
        relation = T.load_relation(relation_bytes)
    except T.BridgeInvalid as exc:
        raise _fail(exc.code, str(exc)) from None
    if (relation["source_slot"], relation["proof_slot"]) != (SLOTS["source"], SLOTS["proof"]):
        raise _fail("INVALID_CANDIDATE", f"relation slots must be {SLOTS['source']} and {SLOTS['proof']} for this helper")
    required = sorted(oid for oid, r in ir["obligations"].items()
                      if r["required"] and r["role"] == "guarantee" and applicability(r)["END_TO_END_VERIFIED"][0])
    chosen = sorted(obligations) if obligations else required
    profile_ref = cert["artifacts"]["profile"]
    accepted_profile = canonical.load_file(pkg.root / profile_ref["path"])
    obls = {}
    for oid in chosen:
        rec = ir["obligations"].get(oid)
        if rec is None:
            raise _fail("ORPHAN_CLAIM", f"unknown accepted obligation {oid}")
        if rec["formal"]["representation"] not in {"contract_dsl", "source_facets"}:
            raise _fail("UNSUPPORTED_CAPABILITY", f"{oid} has no registered value/source transfer")
        digest = rec["formal"]["formula_ref"].rsplit("@", 1)[-1]
        package = canonical.load_file(pkg.path("accepted") / "expressions" / (digest[7:] + ".json"))
        obls[oid] = _obligation_from_package(oid, rec, package, accepted_profile)
    ctx = EdgeContext("preview", {}, "", "", {"edge_id": "preview", "expected_proposition_hash": None},
                      {"claim_id": "PREVIEW"}, {}, relation,
                      {"source": (SLOTS["source"], source), "relation": (SLOTS["relation"], relation_bytes),
                       "proof_source": (SLOTS["proof"], proof or b""),
                       "model": (SLOTS["model"], canonical.dumps(T.model_descriptor(cert["toolchain"]["pin"]))),
                       "profile": (SLOTS["profile"], canonical.dumps(T.profile_descriptor(accepted_profile, profile_ref["sha256"])))},
                      ir, cert, accepted_profile, profile_ref["sha256"],
                      (pkg.root / cert["artifacts"]["olean"]["path"]).read_bytes(), dict(matches[0]), obls,
                      readable_selection, dict(readable_diagnostics or {}))
    spec = derive_goal(ctx)
    tc = leanbridge.resolve_toolchain(cert["toolchain"]["pin"])
    if select_readable:
        spec,build = _select_readable(tc,ctx,spec)
    else:
        build = run_build(tc, ctx, spec, with_proof=proof is not None)
    info = {"proposition_hash": build.proposition_hash, "obligations": sorted(obls), "required_obligations": required,
            "symbols": [{"symbol": s.symbol, "entry": s.entry, "lean_decl": s.lean_decl} for s in spec.symbols],
            "proof_checked": proof is not None, "edge_axioms": build.axioms,
            "model": ctx.inputs["model"][1], "profile": ctx.inputs["profile"][1],
            "compile_process_evidence": copy.deepcopy(build.process_evidence),
            "readable_selection": spec.readable_selection,
            "readable_artifacts": dict(build.readable_artifacts),
            "readable_candidate_artifacts": (readable_candidate_metadata(spec.readable_selection,
                 lambda p:ctx.readable_diagnostics[p]) if spec.readable_selection is not None else {}),
            "readable_source_view": _readable_packet(spec,build)}
    return spec, build, info


def candidate_files(bridge_id: str, info: dict, source: bytes, relation: bytes, proof: bytes) -> dict[str, bytes]:
    """A complete candidate directory for `verislop bridge prepare` (proposal plus artifacts)."""
    claim = f"BRIDGE:{bridge_id}:vscore-refinement"
    proposal = {
        "schema_version": "0.1", "format": "verislop.bridge-proposal/0.1", "bridge_id": bridge_id,
        "tier": 2, "endpoint": T.ENDPOINT,
        "nodes": [{"node_id": NODE, "kind": T.ENDPOINT, "model_slot": SLOTS["model"], "profile_slot": SLOTS["profile"]}],
        "artifacts": [{"slot_id": SLOTS[k], "role": role, "node_id": NODE, "path": FILES[k]}
                      for k, role in (("source", T.SOURCE_ROLE), ("model", "model"), ("profile", "profile"),
                                      ("relation", "relation"), ("proof", T.PROOF_ROLE))],
        "edges": [{"edge_id": "reference-to-vscore", "claim_id": claim, "source_node": "accepted-contract",
                   "target_node": NODE, "relation_slot": SLOTS["relation"],
                   "expected_proposition_hash": info["proposition_hash"], "premises": []}],
        "obligations": [{"id": oid, "required_claims": [claim]} for oid in info["obligations"]],
        "reproducible_slots": sorted(SLOTS.values()),
        "declared_trust": [
            {"id": "vscore-semantics", "kind": "semantics",
             "description": "The delivered artifact is the VSCore source; its meaning is the verifier-owned VSCore 0.3 "
                            "Lean semantics. Executing it with any host interpreter or compiler is outside this edge."},
            {"id": "lean-kernel", "kind": "logic",
             "description": "Lean 4 kernel of the pinned toolchain and the axioms allowed by the accepted policy."}],
    }
    metadata = dict(info.get("readable_candidate_artifacts", {}))
    if info.get("readable_selection") is not None:
        exact = readable_candidate_metadata(info["readable_selection"],lambda p:metadata[p])
        if metadata != exact:
            raise _fail("INVALID_CANDIDATE","returned readable candidate metadata differs from exact frozen selection")
        selection = RS.checked_json("vscore-readable-selection",info["readable_selection"])
        proposal["artifacts"].append({"slot_id":R.SELECTION_SLOT,"role":R.SELECTION_ROLE,"node_id":NODE,"path":R.SELECTION_PATH})
        proposal["artifacts"].extend({"slot_id":d["slot_id"],"role":d["role"],"node_id":NODE,"path":d["artifact"]["path"]} for d in selection["diagnostic_inputs"])
        proposal["reproducible_slots"] = sorted(proposal["reproducible_slots"]+[R.SELECTION_SLOT]+[d["slot_id"] for d in selection["diagnostic_inputs"]])
    elif metadata:
        raise _fail("INVALID_CANDIDATE","readable candidate files require frozen selection bytes")
    return {"proposal.json": canonical.dumps_pretty(proposal), FILES["source"]: source, FILES["relation"]: relation,
            FILES["proof"]: proof, FILES["model"]: info["model"], FILES["profile"]: info["profile"], **metadata}


def _readable_packet(spec, build):
    if spec.readable_selection is None: return None
    s=RS.checked_json("vscore-readable-selection",spec.readable_selection)
    packet={"mode":s["selected_mode"],"status":s["status"],"selection_hash":canonical.digest(spec.readable_selection),
        "manifest":build.readable_support["manifest"],"reasons":s["reasons"],"proof_identity":"MODULE_BOUND_PROOF",
        "universal_only":True,"accepted_refinement_proved":False,"error_inventory":[]}
    if spec.readable_view:
        block=spec.readable_view.block.decode()
        packet.update(source_block=block[:65536],source_block_complete=len(block)<=65536,
            source_block_artifact=RS.ref("readable/source-block.lean",spec.readable_view.block),
            functions=spec.readable_view.functions)
    for d in s["diagnostic_inputs"]:
        raw=canonical.loads(build.readable_artifacts[d["artifact"]["path"]])
        for diagnostic in raw.get("diagnostics",[]):
            details=diagnostic.get("details",{})
            for i,error in enumerate(details.get("errors",[])):
                packet["error_inventory"].append({"index":i,"module":details.get("module"),
                    "excerpt":str(error)[:R.BUDGETS["diagnostic_display_chars_per_row"]],"full_artifact":d["artifact"]})
    return packet
