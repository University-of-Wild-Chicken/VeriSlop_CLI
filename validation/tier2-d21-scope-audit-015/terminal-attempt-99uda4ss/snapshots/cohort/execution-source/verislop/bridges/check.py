"""Validate bridge envelope structure and exact artifact bytes, without proving an edge.

All input records, including acceptance certificates and inventories, are untrusted.
This command checks their consistency. It does not run Lean or an implementation,
does not replay the accepted contract, and never assigns an obligation milestone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .. import canonical, schemas
from ..claimcheck import evaluate_claim
from ..errors import Diagnostic
from ..evidence import Evidence
from ..jsonschema_lite import SchemaError
from ..lifecycle import applicability
from ..stage import StageResult, status_from
from ..verifiers import VERIFIERS, verifier_hash
from .manifest import InvalidPackage, PackageReader, safe_relative
from .registry import relation_checker

GATE = "bridge structure and artifact integrity; no semantic acceptance"
MAX_RECORDS = 4096


def semantic_edge_root(plan_hash: str, artifacts_hash: str, edge: dict[str, Any]) -> str:
    """Supervisor-derived root; the two outer hashes bind exact stored file bytes."""
    return canonical.digest_json({"format": "verislop.semantic-edge-root/0.1",
                                  "plan_hash": plan_hash, "artifacts_hash": artifacts_hash,
                                  "edge": edge})


def _require(condition: bool, message: str, code: str = "INVALID_CANDIDATE") -> None:
    if not condition:
        raise InvalidPackage(message, code)


def _schema(name: str, obj: Any) -> None:
    if name.startswith("urn:"):
        registry = schemas.registry()
        schema, base = registry.resolve(name, name.split("#", 1)[0])
        issues: list[Any] = []
        # The package's schema engine exposes fragment resolution separately from
        # its top-level validate entry point. Do not mutate its cached registry.
        registry._validate(obj, schema, base, "$", issues)
    else:
        issues = schemas.validate(name, obj)
    _require(not issues, f"{name}: {issues[0] if issues else ''}")


def _index(items: list[dict], key: str, description: str) -> dict[str, dict]:
    _require(len(items) <= MAX_RECORDS, f"too many {description} records")
    result = {item[key]: item for item in items}
    _require(len(result) == len(items), f"duplicate {description} identity")
    return result


def _ref(ref: dict, role: str, artifacts: dict[str, dict]) -> None:
    artifact = artifacts.get(ref["id"])
    _require(artifact is not None, f"undeclared {role} reference {ref['id']}", "UNDECLARED_DEPENDENCY")
    _require(artifact["role"] == role and artifact["sha256"] == ref["sha256"],
             f"{role} reference {ref['id']} does not identify the declared artifact bytes", "STATEMENT_MISMATCH")


def _ref_set(refs: list[dict]) -> set[tuple[str, str]]:
    values = {(r["id"], r["sha256"]) for r in refs}
    _require(len({r["id"] for r in refs}) == len(refs), "duplicate reference identity")
    return values


def _graph(plan: dict, artifacts: dict[str, dict]) -> tuple[dict, dict, dict]:
    nodes = _index(plan["nodes"], "node_id", "node")
    slots = _index(plan["artifact_slots"], "slot_id", "slot")
    claims = _index(plan["claims"], "claim_id", "claim")
    edges = _index(plan["edges"], "edge_id", "edge")
    obligations = _index(plan["obligations"], "id", "obligation")
    _index(plan["declared_trust"], "id", "trust")
    _require(set(slots) == set(artifacts), "manifest does not exactly cover declared artifact slots", "UNMAPPED_IMPLEMENTATION_OBJECT")
    for sid, slot in slots.items():
        _require(slot["node_id"] in nodes, f"slot {sid} has an unknown owner node")
        _require(slot["role"] == artifacts[sid]["role"], f"slot {sid} role differs from plan", "STATEMENT_MISMATCH")
    for nid, node in nodes.items():
        owned = {sid for sid, slot in slots.items() if slot["node_id"] == nid}
        _require(set(node["artifact_slots"]) == owned, f"node {nid} has incomplete or foreign artifact slots")
        _ref(node["model_ref"], "model", artifacts)
        _ref(node["profile_ref"], "profile", artifacts)
    accepted_slots = [slot for slot in slots.values() if slot["role"] == "accepted_ir"]
    acceptance_slots = [slot for slot in slots.values() if slot["role"] == "acceptance_certificate"]
    _require(len(accepted_slots) == len(acceptance_slots) == 1,
             "one accepted IR and one acceptance certificate slot are required")
    contract_node = accepted_slots[0]["node_id"]
    _require(acceptance_slots[0]["node_id"] == contract_node and nodes[contract_node]["kind"] == "accepted_contract",
             "accepted IR and acceptance certificate must belong to the same accepted_contract node")
    endpoint_nodes = [nid for nid, n in nodes.items() if n["kind"] == plan["endpoint"]]
    _require(len(endpoint_nodes) == 1, "initial bridge profile requires exactly one selected endpoint node")
    endpoint_node = endpoint_nodes[0]
    _require(set(plan["reproducible_slots"]).issubset(slots), "undeclared reproducible slot")
    edge_claims: set[str] = set()
    for eid, edge in edges.items():
        cid = edge["claim_id"]
        _require(cid in claims and cid not in edge_claims, f"edge {eid} must own a unique declared claim", "ORPHAN_CLAIM")
        edge_claims.add(cid)
        _require(claims[cid]["root_kind"] == "semantic_edge" and
                 claims[cid]["result_predicate"] == "bridge-semantic-edge/0.1",
                 f"edge {eid} must use the semantic edge root and predicate", "ORPHAN_CLAIM")
        _require(edge["source_node"] in nodes and edge["target_node"] in nodes,
                 f"edge {eid} has an undeclared node")
        for plural, singular, role in (("model_refs", "model_ref", "model"),
                                        ("profile_refs", "profile_ref", "profile")):
            for ref in edge[plural]:
                _ref(ref, role, artifacts)
            expected = {(nodes[n][singular]["id"], nodes[n][singular]["sha256"])
                        for n in (edge["source_node"], edge["target_node"])}
            _require(_ref_set(edge[plural]) == expected,
                     f"edge {eid} {plural} differ from its two node references", "STATEMENT_MISMATCH")
        _ref(edge["relation"], "relation", artifacts)
    for cid, claim in claims.items():
        _require(claim["verifier_id"] in VERIFIERS, f"claim {cid} assigns an unregistered verifier", "ORPHAN_CLAIM")
        _require(set(claim["premises"]).issubset(claims), f"claim {cid} has an undeclared premise", "ORPHAN_CLAIM")
        if claim["result_predicate"] == "bridge-semantic-edge/0.1":
            _require(cid in edge_claims, f"semantic claim {cid} has no edge", "ORPHAN_CLAIM")
        else:
            _require(claim["root_kind"] in ("bridge_plan", "bridge_artifacts"),
                     f"structural claim {cid} cannot select a semantic edge root", "ORPHAN_CLAIM")
    # Iterative Kahn traversal is bounded by graph size, including hostile deep graphs.
    waiting = {cid: len(c["premises"]) for cid, c in claims.items()}
    children: dict[str, list[str]] = {cid: [] for cid in claims}
    for cid, claim in claims.items():
        for premise in claim["premises"]:
            children[premise].append(cid)
    ready = [cid for cid, count in waiting.items() if count == 0]
    processed = 0
    while ready:
        cid = ready.pop()
        processed += 1
        for child in children[cid]:
            waiting[child] -= 1
            if waiting[child] == 0:
                ready.append(child)
    _require(processed == len(claims), "bridge claim premise graph contains a cycle", "ORPHAN_CLAIM")
    reached: set[str] = set()
    for oid, obligation in obligations.items():
        _require(set(obligation["required_claims"]).issubset(claims),
                 f"obligation {oid} names an undeclared required claim", "ORPHAN_CLAIM")
        pending = list(obligation["required_claims"])
        local: set[str] = set()
        while pending:
            cid = pending.pop()
            if cid not in local:
                local.add(cid)
                pending.extend(claims[cid]["premises"])
        _require(bool(local & edge_claims), f"obligation {oid} has no required semantic edge", "ORPHAN_CLAIM")
        # A declared endpoint cannot be disconnected from the accepted artifact.
        # Use only edges in this obligation's frozen claim/premise closure. This
        # checks graph coverage, never the logical sufficiency of those edges.
        outgoing: dict[str, list[str]] = {}
        for edge in edges.values():
            if edge["claim_id"] in local:
                outgoing.setdefault(edge["source_node"], []).append(edge["target_node"])
        pending_nodes = [contract_node]
        reached_nodes: set[str] = set()
        while pending_nodes:
            nid = pending_nodes.pop()
            if nid not in reached_nodes:
                reached_nodes.add(nid)
                pending_nodes.extend(outgoing.get(nid, []))
        _require(endpoint_node in reached_nodes,
                 f"obligation {oid} has no required edge path from accepted contract to selected endpoint", "ORPHAN_CLAIM")
        reached.update(local)
    _require(reached == set(claims), "plan contains claims outside the required obligation graph", "ORPHAN_CLAIM")
    return claims, edges, obligations


def _accepted_inputs(reader: PackageReader, plan: dict, artifacts: dict, obligations: dict) -> dict:
    by_role: dict[str, list[dict]] = {}
    by_path = {a["path"]: a for a in artifacts.values()}
    for artifact in artifacts.values():
        by_role.setdefault(artifact["role"], []).append(artifact)
    for role in ("accepted_ir", "acceptance_certificate"):
        _require(len(by_role.get(role, [])) == 1, f"exactly one {role} artifact is required")
        _require(by_role[role][0]["sha256"] == plan[role], f"plan {role} hash does not match bytes", "STATEMENT_MISMATCH")
    ir, _ = reader.json(by_role["accepted_ir"][0]["path"])
    cert, _ = reader.json(by_role["acceptance_certificate"][0]["path"])
    _schema("accepted-ir", ir)
    _schema("acceptance-certificate", cert)
    _require(ir["acceptance_certificate_ref"] == by_role["acceptance_certificate"][0]["path"],
             "accepted IR points to a different acceptance certificate", "STATEMENT_MISMATCH")
    _require(ir["contract_input_root"] == cert["contract_input_root"] and
             ir["accepted_environment_hash"] == cert["artifacts"]["environment_export"]["sha256"] and
             ir["lean_toolchain"] == cert["toolchain"]["pin"],
             "accepted IR and acceptance certificate roots/toolchain differ", "STATEMENT_MISMATCH")
    _require(cert["gate"] == "accepted_and_proved", "acceptance certificate does not declare accepted_and_proved")
    for name, ref in cert["artifacts"].items():
        safe_relative(ref["path"])
        artifact = by_path.get(ref["path"])
        _require(artifact is not None and artifact["sha256"] == ref["sha256"],
                 f"acceptance artifact {name} is not covered by the manifest", "UNDECLARED_DEPENDENCY")
    accepted = ir["obligations"]
    required = {oid for oid, record in accepted.items() if record["required"] and record["role"] == "guarantee"
                and applicability(record)["END_TO_END_VERIFIED"][0]}
    _require(set(obligations) == required, "plan must cover exactly all required accepted guarantees", "ORPHAN_CLAIM")
    _require(set(accepted).issubset(cert["obligations"]), "acceptance certificate omits an IR obligation", "STATEMENT_MISMATCH")
    for oid, record in accepted.items():
        _require(record["id"] == oid, f"IR obligation {oid} key and identity differ")
        result = cert["obligations"][oid]
        for key in ("revision", "kind", "role"):
            _require(record[key] == result[key], f"IR/certificate {oid} {key} mismatch", "STATEMENT_MISMATCH")
        for key in ("statement_hash", "lean_symbol", "representation"):
            _require(record["formal"][key] == result[key], f"IR/certificate {oid} {key} mismatch", "STATEMENT_MISMATCH")
        _require(set(record["formal"]["axioms"]) == set(result["axioms"]),
                 f"IR/certificate {oid} axioms differ", "STATEMENT_MISMATCH")
        _require(set(result["axioms"]).issubset(cert["policy"]["allowed_axioms"]),
                 f"accepted obligation {oid} declares inadmissible axioms", "INADMISSIBLE_AXIOM")
        if record["required"] and record["role"] == "guarantee":
            _require(result["typechecked"] == result["proved"] == "PASS", f"required guarantee {oid} has unresolved proof metadata")
        if oid in required:
            _require(obligations[oid]["revision"] == record["revision"] and
                     obligations[oid]["accepted_statement_hash"] == record["formal"]["statement_hash"],
                     f"bridge obligation {oid} differs from the accepted statement", "STATEMENT_MISMATCH")
    return cert


def _inventories(reader: PackageReader, artifacts: dict, accepted_cert: dict) -> dict:
    inventories: dict[str, dict] = {}
    modules: set[str] = set()
    for slot, artifact in artifacts.items():
        if artifact["role"] != "proof_inventory":
            continue
        inventory, _ = reader.json(artifact["path"])
        _schema("urn:verislop:schema:semantic-edge-certificate:0.1#/$defs/proof_inventory", inventory)
        module = artifacts.get(inventory["module_slot"])
        _require(module is not None and module["role"] == "proof_module" and
                 module["sha256"] == inventory["module_hash"], "proof inventory module binding mismatch", "STATEMENT_MISMATCH")
        _require(inventory["module_slot"] not in modules, "multiple inventories declare the same proof module")
        modules.add(inventory["module_slot"])
        entries = _index(inventory["theorems"], "symbol", "proof inventory symbol")
        for entry in entries.values():
            _require(set(entry["axioms"]).issubset(accepted_cert["policy"]["allowed_axioms"]),
                     "proof inventory declares inadmissible axioms", "INADMISSIBLE_AXIOM")
        inventories[slot] = inventory
    _require(modules == {s for s, a in artifacts.items() if a["role"] == "proof_module"},
             "every declared proof module needs exactly one declared inventory", "UNDECLARED_DEPENDENCY")
    return inventories


def _evidence(reader: PackageReader, ref: dict) -> Evidence:
    record, snap = reader.json(ref["path"])
    _require(snap.sha256 == ref["sha256"], "certificate evidence byte hash mismatch", "STALE_OR_UNBOUND_EVIDENCE")
    _schema("evidence", record)
    body = {k: v for k, v in record.items() if k != "evidence_id"}
    expected_id = "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32]
    _require(record["evidence_id"] == expected_id and Path(snap.path).stem == expected_id,
             "evidence content-addressed identity mismatch", "STALE_OR_UNBOUND_EVIDENCE")
    raw, raw_snap = reader.json(safe_relative(record["raw_result_ref"]))
    _require(raw_snap.sha256 == record["raw_result_hash"], "evidence raw result hash mismatch", "STALE_OR_UNBOUND_EVIDENCE")
    _require(isinstance(raw, dict) and raw.get("claim_id") == record["claim_id"],
             "evidence raw result does not bind the assigned claim", "STALE_OR_UNBOUND_EVIDENCE")
    _require(type(raw.get("sequence")) is int and raw["sequence"] >= 0,
             "evidence raw result has no valid sequence", "STALE_OR_UNBOUND_EVIDENCE")
    return Evidence(record, raw, [])


def _certificate(reader: PackageReader, path: Path, plan: dict, plan_hash: str, artifacts_hash: str,
                 artifacts: dict, claims: dict, edges: dict, inventories: dict) -> tuple[dict, list[Diagnostic]]:
    cert, _ = reader.json(path)
    _schema("semantic-edge-certificate", cert)
    _require(cert["bridge_id"] == plan["bridge_id"] and cert["plan_hash"] == plan_hash and
             cert["artifacts_hash"] == artifacts_hash, "certificate binds stale bridge/plan/manifest roots", "STALE_OR_UNBOUND_EVIDENCE")
    edge = edges.get(cert["edge_id"])
    _require(edge is not None, "certificate names an undeclared edge", "ORPHAN_CLAIM")
    for key in ("claim_id", "source_node", "target_node", "relation"):
        _require(cert[key] == edge[key], f"certificate {key} differs from frozen edge", "STATEMENT_MISMATCH")
    for key in ("model_refs", "profile_refs"):
        _require(_ref_set(cert[key]) == _ref_set(edge[key]), f"certificate {key} differs from frozen edge", "STATEMENT_MISMATCH")
    _require(cert["proposition_hash"] == edge["expected_proposition_hash"] == cert["proof"]["type_hash"],
             "certificate proof type differs from the frozen expected proposition", "STATEMENT_MISMATCH")
    claim = claims[edge["claim_id"]]
    _require(set(cert["premise_claims"]) == set(claim["premises"]),
             "certificate premise list differs from frozen claim", "ORPHAN_CLAIM")
    checker = cert["checker"]
    _require(checker["verifier_id"] == claim["verifier_id"] and
             checker["verifier_hash"] == verifier_hash(claim["verifier_id"]),
             "certificate checker is not the current assigned issuer", "STALE_OR_UNBOUND_EVIDENCE")
    proof = cert["proof"]
    inventory = inventories.get(proof["inventory_slot"])
    _require(inventory is not None and inventory["module_slot"] == proof["module_slot"],
             "certificate proof inventory/module is missing or mismatched", "UNDECLARED_DEPENDENCY")
    entries = {item["symbol"]: item for item in inventory["theorems"]}
    _require(proof["symbol"] in entries and entries[proof["symbol"]]["type_hash"] == proof["type_hash"],
             "certificate symbol/type is not in the declared proof inventory", "STATEMENT_MISMATCH")
    ev = _evidence(reader, cert["evidence"])
    _require(ev.record["verifier_id"] == checker["verifier_id"] and
             ev.record["verifier_hash"] == checker["verifier_hash"],
             "evidence issuer differs from certificate assigned checker", "STALE_OR_UNBOUND_EVIDENCE")
    expected_raw = {"edge_id": edge["edge_id"], "plan_hash": plan_hash, "artifacts_hash": artifacts_hash,
                    "proposition_hash": cert["proposition_hash"], "proof_symbol": proof["symbol"],
                    "proof_module_hash": artifacts[proof["module_slot"]]["sha256"],
                    "proof_inventory_hash": artifacts[proof["inventory_slot"]]["sha256"]}
    for key, value in expected_raw.items():
        _require(ev.result.get(key) == value, f"evidence {key} does not bind the declared proof", "STALE_OR_UNBOUND_EVIDENCE")
    roots = {"bridge_plan": plan_hash, "bridge_artifacts": artifacts_hash,
             "semantic_edge": semantic_edge_root(plan_hash, artifacts_hash, edge)}
    assessment = evaluate_claim(claim, [ev], roots, "semantic_edge")
    diagnostics = list(assessment.diagnostics)
    if not assessment.authorized:
        return {"certificate_id": cert["certificate_id"], "edge_id": edge["edge_id"],
                "metadata_valid": False, "evidence_binding_valid": False, "semantic_acceptance": False}, diagnostics
    # Envelope certificates are a separate capability boundary from the generic evidence
    # predicate; even a perfectly self-consistent forged PASS reaches only this unsupported
    # result. Registered relation checkers publish their own outputs via `bridge accept`.
    relation = artifacts[edge["relation"]["id"]]
    backend = relation_checker(reader.read(relation["path"], keep=True).data)
    reason = ("no registered relation-specific semantic checker; actual proof module, inventory completeness, "
              "proposition semantics and premises have not been checked")
    if backend is not None:
        reason = (f"semantic-edge envelope certificates are never accepted; the registered checker {backend} "
                  "runs only through `verislop bridge accept` and is rechecked by `verislop bridge verify`")
    diagnostics.append(Diagnostic("UNSUPPORTED_CAPABILITY", reason, claims=[claim["claim_id"]]))
    return {"certificate_id": cert["certificate_id"], "edge_id": edge["edge_id"],
            "metadata_valid": True, "evidence_binding_valid": True,
            "semantic_acceptance": False, "reason": reason}, diagnostics


def validate_package(package_root: Path, plan_path: Path, artifacts_path: Path,
                     certificate_paths: Iterable[Path] = ()) -> StageResult:
    """Read-only structural gate. Supplying a semantic certificate currently blocks.

    Relative paths are relative to package_root. Plan and manifest hashes identify
    exact file bytes, not a parsed/re-serialized JSON representation. Certificate
    and evidence files are outside the manifest root to avoid circular hashing.
    """
    summary: dict[str, Any] = {"structural_acceptance": False, "semantic_acceptance": False,
                               "assigns_end_to_end_verified": False, "accepted_semantic_certificates": [],
                               "proof_inventory_completeness_checked": False,
                               "accepted_contract_replayed": False, "certificates": []}
    diagnostics: list[Diagnostic] = []
    reader: PackageReader | None = None
    try:
        reader = PackageReader(package_root)
        plan, plan_snap = reader.json(plan_path)
        manifest, manifest_snap = reader.json(artifacts_path)
        _schema("bridge-plan", plan)
        _schema("bridge-artifacts", manifest)
        _require(plan_snap.path != manifest_snap.path, "plan and manifest must be distinct files")
        _require(manifest["plan_hash"] == plan_snap.sha256, "manifest does not bind the exact plan file bytes", "INPUT_MUTATION")
        _require(manifest["bridge_id"] == plan["bridge_id"], "manifest belongs to another bridge", "STATEMENT_MISMATCH")
        artifacts = _index(manifest["artifacts"], "slot_id", "manifest artifact")
        paths: set[str] = set()
        for artifact in artifacts.values():
            path = safe_relative(artifact["path"])
            _require(path.casefold() not in paths, "manifest contains ambiguous or duplicate artifact paths", "AMBIGUOUS_CORRESPONDENCE")
            _require(path not in (plan_snap.path, manifest_snap.path), "manifest cannot inventory its own roots")
            paths.add(path.casefold())
            snap = reader.read(path)
            _require(snap.size == artifact["size"] and snap.sha256 == artifact["sha256"],
                     f"artifact {artifact['slot_id']} size/hash does not match actual bytes", "INPUT_MUTATION")
        claims, edges, obligations = _graph(plan, artifacts)
        accepted_cert = _accepted_inputs(reader, plan, artifacts, obligations)
        inventories = _inventories(reader, artifacts, accepted_cert)
        summary.update({"structural_acceptance": True, "bridge_id": plan["bridge_id"], "tier": plan["tier"],
                        "endpoint": plan["endpoint"], "plan_hash": plan_snap.sha256,
                        "artifacts_hash": manifest_snap.sha256, "artifact_count": len(artifacts),
                        "required_obligations": sorted(obligations), "pending_semantic_claims": sorted(e["claim_id"] for e in edges.values()),
                        "coverage_scope": "all required implementation-applicable accepted guarantees; logical sufficiency not checked"})
        seen_certificates: set[str] = set()
        seen_edges: set[str] = set()
        count = 0
        for path in certificate_paths:
            count += 1
            _require(count <= MAX_RECORDS, "too many certificates")
            result, issues = _certificate(reader, Path(path), plan, plan_snap.sha256, manifest_snap.sha256,
                                          artifacts, claims, edges, inventories)
            _require(result["certificate_id"] not in seen_certificates and result["edge_id"] not in seen_edges,
                     "duplicate certificate or edge certificate identity", "AMBIGUOUS_CORRESPONDENCE")
            seen_certificates.add(result["certificate_id"])
            seen_edges.add(result["edge_id"])
            summary["certificates"].append(result)
            diagnostics.extend(issues)
        reader.recheck()
    except InvalidPackage as exc:
        summary["structural_acceptance"] = False
        diagnostics.append(Diagnostic(exc.code, str(exc)))
    except (OSError, SchemaError) as exc:
        summary["structural_acceptance"] = False
        diagnostics.append(Diagnostic("VERIFIER_FAILURE", f"bridge validator infrastructure failure: {type(exc).__name__}", severity="infrastructure"))
    except RecursionError:
        summary["structural_acceptance"] = False
        diagnostics.append(Diagnostic("INVALID_CANDIDATE", "bridge input exceeds supported nesting limits"))
    finally:
        if reader is not None:
            reader.close()
    return StageResult("bridge check", status_from(diagnostics), GATE, diagnostics,
                       summary=summary,
                       lines=["Metadata and artifact integrity only; no semantic edge or end-to-end verification is accepted."])
