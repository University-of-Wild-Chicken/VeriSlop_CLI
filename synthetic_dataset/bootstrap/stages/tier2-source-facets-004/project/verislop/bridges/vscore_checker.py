"""Registered semantic checker `verislop.vscore-checker` for `vscore.reference_refinement/0.1` edges.

For one frozen edge from the accepted contract to a `restricted_source` VSCore node it:

1. reads only frozen, manifest-bound bytes of a prepared bridge bundle (the preparation itself is
   re-verified first, including a fresh replay of the accepted contract);
2. derives the bridge goal from the accepted IR, accepted profile registry and accepted formula
   packages (`targets/vscore_target.py`); the candidate supplies source bytes, symbol↔entry
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

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import canonical, fsutil, leanbridge, policy as policymod
from ..errors import Diagnostic, VeriSlopError
from ..events import EventSink
from ..evidence import EvidenceStore
from ..exprjson import name_str
from ..package import Package
from ..stage import StageResult, status_from
from ..targets import vscore_target as T
from ..verifiers import verifier_hash
from .check import _schema, semantic_edge_root
from .manifest import InvalidPackage, PackageReader
from .registry import relation_checker

VERIFIER = "verislop.vscore-checker"
GATE = "VSCore exact-source parse/typing, reference refinement and obligation transfer (two kernel replays)"
SCOPE = ["restricted_source; vscore/0.1", "template vscore.reference_refinement/0.1",
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
            if rec["formal"]["representation"] != "contract_dsl":
                raise _fail("UNSUPPORTED_CAPABILITY",
                            f"{ob['id']} is not a contract-DSL statement; {T.TEMPLATE} has no transfer rule for it", cid)
            digest = rec["formal"]["formula_ref"].rsplit("@", 1)[-1]
            package = None
            for a in slots.values():
                if a["sha256"] == digest and a["path"].endswith("/expressions/" + digest[7:] + ".json"):
                    package = _artifact(reader, slots, a["slot_id"], json=True)
            if not isinstance(package, dict) or package.get("encoding") != "verislop.contract-dsl/0.1" or \
                    package.get("semantic_profile") != accepted_profile.get("profile_id"):
                raise _fail("STATEMENT_MISMATCH", f"{ob['id']}: accepted formula package is missing or foreign", cid)
            obligations[ob["id"]] = {"formula": package["formula"], "lean_symbol": rec["formal"]["lean_symbol"],
                                     "statement_hash": rec["formal"]["statement_hash"], "revision": rec["revision"]}
        if not obligations:
            raise _fail("ORPHAN_CLAIM", "the edge is required by no accepted obligation", cid)
        reader.recheck()
        return EdgeContext(bridge_id, plan, plan_snap.sha256, manifest_snap.sha256, edge, claim, slots, relation,
                           inputs, accepted_ir, acceptance, accepted_profile, prof_ref["sha256"], contract_module,
                           dict(matches[0]), obligations)
    except InvalidPackage as exc:
        raise _fail(exc.code, str(exc)) from None
    finally:
        reader.close()


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
        return T.build_goal(ctx.inputs["source"][1], ctx.relation, ctx.accepted_profile, ctx.obligations)
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


def _parts_digest(parts: dict[str, bytes]) -> str:
    return canonical.digest_json({suffix: canonical.digest(data) for suffix, data in sorted(parts.items())})


def run_build(tc: leanbridge.Toolchain, ctx: EdgeContext, spec: T.GoalSpec, *, with_proof: bool = True) -> Build:
    """One isolated build. Without the proof, only the library, contract and goal are replayed."""
    cid = ctx.claim["claim_id"]
    pol = ctx.policy
    opts = {"timeout": pol["build_timeout_seconds"], "memory_mb": pol["memory_mb"],
            "require_network_isolation": pol["require_network_isolation"],
            "require_filesystem_isolation": pol["require_filesystem_isolation"]}
    compiles: dict[str, dict] = {}
    with fsutil.temporary_directory(prefix="verislop-vscore-build-") as tmp:
        root = Path(tmp)
        lib, contract, goal, proof = (root / d for d in ("lib", "contract", "goal", "proof"))
        modules: dict[str, dict[str, bytes]] = {}
        deps: dict[str, dict[str, str]] = {}
        for m, source in T.library_sources().items():
            res, parts = leanbridge.compile_named_module(tc, lib, m, source, dict(deps), read_only=[], **opts)
            compiles[m] = {"ok": res.ok, "errors": res.errors[:20], "sorries": len(res.sorry_positions)}
            if not res.ok or res.sorry_positions:
                raise _fail("VERIFIER_FAILURE", f"verifier-owned library module {m} failed to build: {res.errors[:3]}",
                            cid, "infrastructure")
            modules[m] = parts
            deps[m] = {s: str(lib / (leanbridge.module_relpath(m) + s)) for s in parts}
        contract.mkdir()
        staged = contract / "bundle"
        staged.write_bytes(ctx.contract_module)
        leanbridge._stage_module(staged, contract)
        staged.unlink()
        modules[T.CONTRACT_MODULE] = leanbridge.module_parts(contract, T.CONTRACT_MODULE)
        deps[T.CONTRACT_MODULE] = {s: str(contract / (T.CONTRACT_MODULE + s)) for s in modules[T.CONTRACT_MODULE]}
        res, parts = leanbridge.compile_named_module(tc, goal, T.GOAL_MODULE, spec.text.encode(), dict(deps),
                                                     read_only=[lib, contract], **opts)
        compiles[T.GOAL_MODULE] = {"ok": res.ok, "errors": res.errors[:20], "sorries": len(res.sorry_positions)}
        if not res.ok or res.sorry_positions:
            raise _fail("UNSUPPORTED_CAPABILITY",
                        "the derived bridge goal could not be established for this program and contract "
                        f"(parse/typing equations, adapters or transfer proofs): {res.errors[:3]}", cid)
        modules[T.GOAL_MODULE] = parts
        deps[T.GOAL_MODULE] = {s: str(goal / (T.GOAL_MODULE + s)) for s in parts}
        isolation = res.isolation
        if with_proof:
            res, parts = leanbridge.compile_named_module(tc, proof, T.PROOF_MODULE, ctx.inputs["proof_source"][1],
                                                         dict(deps), read_only=[lib, contract, goal], **opts)
            compiles[T.PROOF_MODULE] = {"ok": res.ok, "errors": res.errors[:20], "sorries": len(res.sorry_positions),
                                        "timed_out": res.timed_out}
            if not res.ok:
                raise _fail("CANDIDATE_BUILD_FAILURE", f"candidate proof module failed to elaborate: {res.errors[:3]}", cid)
            modules[T.PROOF_MODULE] = parts
            isolation = res.isolation
        for m, ps in modules.items():
            # The candidate compile could only read these artifacts; rebind them after it ran.
            if m != T.PROOF_MODULE:
                base = {T.CONTRACT_MODULE: contract, T.GOAL_MODULE: goal}.get(m, lib)
                if leanbridge.module_parts(base, m) != ps:
                    raise _fail("INPUT_MUTATION", f"dependency module {m} changed during the candidate build", cid)
        # The build directory is fresh for every invocation. Preserve every isolation
        # property while replacing only that explicitly volatile directory prefix.
        isolation = dict(isolation)
        isolation["read_only_paths"] = [
            "<build>/" + str(Path(path).relative_to(root)) if Path(path).is_relative_to(root) else path
            for path in isolation.get("read_only_paths", [])
        ]
    root_module = T.PROOF_MODULE if with_proof else T.GOAL_MODULE
    resp = leanbridge.run_kernel_tool_modules(tc, modules, root_module, {"export": True, "axioms": True},
                                              timeout=pol["kernel_timeout_seconds"], memory_mb=pol["memory_mb"],
                                              require_network_isolation=pol["require_network_isolation"],
                                              require_filesystem_isolation=pol["require_filesystem_isolation"])
    return _audit(tc, ctx, spec, resp, modules, compiles, isolation, with_proof)


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
        if (n.startswith(T.GOAL_MODULE + ".") or n.startswith("VSCore.")) and c["kind"] != "theorem":
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
        "format": "verislop.vscore-build/0.1",
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
    }
    return Build(observation, decls, modules, prop_hash, ir_body, axioms)


DETERMINISTIC = ("format", "lean_toolchain", "kernel_tool_hash", "kernel_tool_version", "toolchain_olean_closure",
                 "compiles", "modules", "replayed_constants", "export_digest", "proposition_hash",
                 "proposition_closure_size", "edge_axioms", "implementation_ir_digest", "isolation")


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


def _semantic_descriptor(ctx: EdgeContext, spec: T.GoalSpec, axioms: list[str]) -> dict:
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
    return {"schema_version": "0.1", "format": "verislop.vscore-edge-certificate/0.1",
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


def _certificate_descriptor(cert: dict) -> dict:
    """All certificate fields except the time-dependent evidence reference.

    Evidence records include a recorded_at timestamp. Build observations normalize
    their temporary directory prefix before hashing; no semantic field is omitted.
    """
    return {key: value for key, value in cert.items() if key != "evidence"}


def _evidence_result(cert: dict) -> dict:
    return {"bridge_id": cert["bridge_id"], "edge_id": cert["edge_id"], "plan_hash": cert["plan_hash"],
            "artifacts_hash": cert["artifacts_hash"], "semantic_edge_root": cert["semantic_edge_root"],
            "template": cert["template"], "proposition_hash": cert["proposition_hash"],
            "proof_symbol": cert["theorem"]["symbol"], "edge_axioms": cert["theorem"]["axioms"],
            "inputs": cert["inputs"], "accepted_modules": cert["accepted_modules"],
            "obligations": [o["id"] for o in cert["obligations"]],
            "implementation_ir_hash": cert["implementation_ir"]["sha256"],
            "builds": [b["sha256"] for b in cert["builds"]],
            "certificate_descriptor_hash": canonical.digest_json(_certificate_descriptor(cert)),
            "semantic_acceptance": True, "assigns_end_to_end_verified": False}


def outputs(ctx: EdgeContext, spec: T.GoalSpec, a: Build, b: Build, run_id: str, stage: Path) -> dict[str, bytes]:
    """Certificate, IR, all accepted module parts, build records and bound evidence."""
    files: dict[str, bytes] = {"goal/VeriSlopBridgeGoal.lean": spec.text.encode()}
    accepted = []
    for m in (T.GOAL_MODULE, T.PROOF_MODULE):
        for suffix, data in sorted(a.modules[m].items()):
            path = f"accepted/{m}{suffix}"
            files[path] = data
            accepted.append({"module": m, "path": path, "sha256": canonical.digest(data)})
    ir = {"schema_version": "0.1", "format": T.IR_FORMAT, "language": T.LANGUAGE, "semantics": T.SEMANTICS,
          "bridge_id": ctx.bridge_id, "edge_id": ctx.edge["edge_id"], "claim_id": ctx.claim["claim_id"],
          "source": {"slot_id": ctx.inputs["source"][0], "size": len(spec.source_bytes),
                     "sha256": canonical.digest(spec.source_bytes)},
          "accepted_ir": ctx.plan["accepted_ir"], "acceptance_certificate": ctx.plan["acceptance_certificate"],
          "proposition_hash": a.proposition_hash,
          "accepted_modules": [{"module": x["module"], "sha256": x["sha256"]}
                               for x in accepted if x["path"].endswith(".olean")],
          **a.ir, "exporter": {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)}}
    _schema("vscore-implementation-ir", ir)
    files[IR_FILE] = canonical.dumps(ir)
    for label, build in (("A", a), ("B", b)):
        files[f"builds/{label}.json"] = canonical.dumps(build.observation)
    cert = {**_semantic_descriptor(ctx, spec, a.axioms),
            "accepted_modules": accepted,
            "implementation_ir": {"path": IR_FILE, "sha256": canonical.digest(files[IR_FILE])},
            "builds": [{"path": f"builds/{x}.json", "sha256": canonical.digest(files[f"builds/{x}.json"])} for x in "AB"]}
    evidence = EvidenceStore(stage, run_id).record(
        claim_id=ctx.claim["claim_id"], verifier_id=VERIFIER, status="PASS", scope=SCOPE,
        input_root=cert["semantic_edge_root"], result=_evidence_result(cert),
        invocation=["verislop", "bridge", "accept", "--bridge-id", ctx.bridge_id])
    ev_path = f"evidence/{evidence.id}.json"
    files[ev_path] = (stage / ev_path).read_bytes()
    files[evidence.record["raw_result_ref"]] = (stage / evidence.record["raw_result_ref"]).read_bytes()
    cert["evidence"] = {"path": ev_path, "sha256": canonical.digest(files[ev_path])}
    _schema("vscore-edge-certificate", cert)
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
    if observations[0] != observations[1]:
        raise _fail("NONDETERMINISM", "published build observations disagree", cid)

    ir, _ = reader.json(IR_FILE)
    _schema("vscore-implementation-ir", ir)
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
            _schema("vscore-edge-certificate", cert)
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
                             *(m["path"] for m in cert["accepted_modules"])):
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
            obligations: list[str] | None = None) -> tuple[T.GoalSpec, Build, dict]:
    """Derive the goal for an accepted run and build it once (with the proof when given).

    This is a convenience for candidate authors; it publishes nothing and is never evidence.
    The registered checker repeats every step from the frozen bundle during `bridge accept`.
    """
    from ..export import verified_ir
    from ..lifecycle import applicability

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
    obls = {}
    for oid in chosen:
        rec = ir["obligations"].get(oid)
        if rec is None:
            raise _fail("ORPHAN_CLAIM", f"unknown accepted obligation {oid}")
        if rec["formal"]["representation"] != "contract_dsl":
            raise _fail("UNSUPPORTED_CAPABILITY", f"{oid} is not a contract-DSL statement")
        digest = rec["formal"]["formula_ref"].rsplit("@", 1)[-1]
        package = canonical.load_file(pkg.path("accepted") / "expressions" / (digest[7:] + ".json"))
        obls[oid] = {"formula": package["formula"], "lean_symbol": rec["formal"]["lean_symbol"],
                     "statement_hash": rec["formal"]["statement_hash"], "revision": rec["revision"]}
    profile_ref = cert["artifacts"]["profile"]
    accepted_profile = canonical.load_file(pkg.root / profile_ref["path"])
    ctx = EdgeContext("preview", {}, "", "", {"edge_id": "preview", "expected_proposition_hash": None},
                      {"claim_id": "PREVIEW"}, {}, relation,
                      {"source": (SLOTS["source"], source), "relation": (SLOTS["relation"], relation_bytes),
                       "proof_source": (SLOTS["proof"], proof or b""),
                       "model": (SLOTS["model"], canonical.dumps(T.model_descriptor(cert["toolchain"]["pin"]))),
                       "profile": (SLOTS["profile"], canonical.dumps(T.profile_descriptor(accepted_profile, profile_ref["sha256"])))},
                      ir, cert, accepted_profile, profile_ref["sha256"],
                      (pkg.root / cert["artifacts"]["olean"]["path"]).read_bytes(), dict(matches[0]), obls)
    spec = derive_goal(ctx)
    tc = leanbridge.resolve_toolchain(cert["toolchain"]["pin"])
    build = run_build(tc, ctx, spec, with_proof=proof is not None)
    info = {"proposition_hash": build.proposition_hash, "obligations": sorted(obls), "required_obligations": required,
            "symbols": [{"symbol": s.symbol, "entry": s.entry, "lean_decl": s.lean_decl} for s in spec.symbols],
            "proof_checked": proof is not None, "edge_axioms": build.axioms,
            "model": ctx.inputs["model"][1], "profile": ctx.inputs["profile"][1]}
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
             "description": "The delivered artifact is the VSCore source; its meaning is the verifier-owned VSCore 0.1 "
                            "Lean semantics. Executing it with any host interpreter or compiler is outside this edge."},
            {"id": "lean-kernel", "kind": "logic",
             "description": "Lean 4 kernel of the pinned toolchain and the axioms allowed by the accepted policy."}],
    }
    return {"proposal.json": canonical.dumps_pretty(proposal), FILES["source"]: source, FILES["relation"]: relation,
            FILES["proof"]: proof, FILES["model"]: info["model"], FILES["profile"]: info["profile"]}
