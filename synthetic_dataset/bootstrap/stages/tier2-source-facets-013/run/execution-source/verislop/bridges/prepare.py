"""Prepare a frozen bridge bundle from an actually replayed accepted run.

Only structural evidence is produced. Expected bridge propositions, candidate
models and relations remain proposals; no semantic backend or milestone is enabled.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

from .. import canonical, fsutil
from ..claimcheck import evaluate_claim
from ..errors import Diagnostic, VeriSlopError
from ..events import EventSink
from ..evidence import EvidenceStore
from ..lifecycle import applicability
from ..package import Package
from ..stage import StageResult, status_from
from ..verifiers import verifier_hash
from .check import _evidence, _index, _require, _schema, validate_package
from .import_contract import BridgeImportError, ImportedContract, import_contract
from .manifest import InvalidPackage, PackageReader, MAX_COLLECTION_ITEMS, safe_relative
from .publish import publish, record_preparation
from .registry import SEMANTIC_CHECKERS, relation_checker

VERIFIER = "verislop.bridge-preparation"
SEMANTIC_VERIFIER = "verislop.bridge-semantic-unavailable"
GATE = "replayed contract import and frozen bridge preparation; no semantic acceptance"
SEMANTIC_GATE = "replayed contract import, frozen bridge preparation and re-executed registered semantic-edge checks"
SEMANTIC_BINDING_GATE = "replayed contract import, frozen bridge preparation and registered semantic-edge evidence bindings"
CERTIFICATE = "preparation-certificate.json"
RECEIPT = "import-receipt.json"


def _bridge_id(value: str) -> str:
    _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,127}", value) is not None,
             "bridge_id must be one safe path component (letters, digits, dot, underscore or hyphen)")
    return value


def _base_summary() -> dict[str, Any]:
    return {"structural_acceptance": False, "semantic_acceptance": False,
            "assigns_end_to_end_verified": False, "accepted_semantic_certificates": [],
            "expected_targets_semantically_checked": False, "status": "PENDING"}


def _import_identity(imported: ImportedContract) -> dict[str, str]:
    return {"source_contract_root": imported.ir["contract_input_root"],
            "source_ir_hash": canonical.digest(imported.files[imported.ir_path]),
            "source_certificate_hash": canonical.digest(imported.files[imported.certificate_path]),
            "receipt_sha256": canonical.digest_json(imported.replay_receipt)}


def _source_unchanged(root: Path, imported: ImportedContract) -> None:
    reader = PackageReader(root)
    try:
        for path, data in imported.files.items():
            observed = reader.read(path)
            _require(observed.sha256 == canonical.digest(data),
                     f"accepted source input changed during preparation: {path}", "INPUT_MUTATION")
        reader.recheck()
    finally:
        reader.close()


def _destination_free(root: Path, bridge_id: str) -> None:
    reader = PackageReader(root)
    try:
        meta, _ = reader.json("package.json")
        _require(isinstance(meta, dict) and isinstance(meta.get("run_id"), str), "source is not a run package")
        registered = meta.get("bridge_preparations", {})
        _require(isinstance(registered, dict), "invalid bridge preparation bookkeeping")
        for key, value in registered.items():
            _bridge_id(key)
            _require(value == f"bridges/{key}", "bridge preparation bookkeeping redirects outside its assigned bundle")
        _require(bridge_id not in registered, "bridge attempt is already registered; verify it or choose a fresh bridge_id", "INPUT_MUTATION")
        try:
            parent = os.open("bridges", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=reader.fd)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise InvalidPackage("unsafe bridge publication parent") from exc
        try:
            try:
                os.stat(bridge_id, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            raise InvalidPackage("bridge attempt already exists; verify it or choose a fresh bridge_id", "INPUT_MUTATION")
        finally:
            os.close(parent)
    finally:
        reader.close()


def _assemble(imported: ImportedContract, proposal: dict, proposal_bytes: bytes,
              candidates: dict[str, bytes]) -> tuple[dict[str, bytes], dict, dict]:
    """Compute all roots, accepted statements and issuer assignments as supervisor."""
    files: dict[str, bytes] = {}
    slots: dict[str, dict] = {}
    artifacts: dict[str, dict] = {}
    folded: set[str] = set()

    def add(slot: str, role: str, owner: str, path: str, data: bytes) -> None:
        safe_relative(path)
        _require(slot not in slots and path.casefold() not in folded,
                 "duplicate or reserved artifact identity/path", "AMBIGUOUS_CORRESPONDENCE")
        folded.add(path.casefold())
        files[path] = data
        slots[slot] = {"slot_id": slot, "role": role, "node_id": owner}
        artifacts[slot] = {"slot_id": slot, "role": role, "path": path,
                           "size": len(data), "sha256": canonical.digest(data)}

    imported_paths = {
        imported.ir_path: ("accepted-ir", "accepted_ir"),
        imported.certificate_path: ("acceptance-certificate", "acceptance_certificate"),
    }
    for name, slot, role in (("source", "contract-model", "model"), ("profile", "contract-profile", "profile"),
                            ("olean", "accepted-module", "accepted_module"),
                            ("environment_export", "accepted-environment", "environment_export"),
                            ("statements", "accepted-statements", "statements")):
        imported_paths[imported.certificate["artifacts"][name]["path"]] = (slot, role)
    for path, data in sorted(imported.files.items()):
        head = path.split("/", 1)[0].casefold()
        _require(head not in {"plan.json", "artifacts.json", CERTIFICATE, RECEIPT, "proposal.json",
                              "evidence", "candidate-inputs"},
                 f"accepted input collides with reserved preparation output: {path}", "INVALID_CANDIDATE")
        slot, role = imported_paths.get(path, ("import-" + canonical.sha256_hex(path.encode())[:24], "contract_input"))
        add(slot, role, "accepted-contract", path, data)
    add("import-receipt", "contract_import", "accepted-contract", RECEIPT, canonical.dumps(imported.replay_receipt))
    add("bridge-proposal", "bridge_proposal", "accepted-contract", "proposal.json", proposal_bytes)
    for item in proposal["artifacts"]:
        add(item["slot_id"], item["role"], item["node_id"], "candidate-inputs/" + item["path"], candidates[item["path"]])

    def ref(slot: str) -> dict:
        _require(slot in artifacts, f"undeclared artifact slot {slot}", "UNDECLARED_DEPENDENCY")
        return {"id": slot, "sha256": artifacts[slot]["sha256"]}

    nodes = [{"node_id": "accepted-contract", "kind": "accepted_contract",
              "artifact_slots": sorted(s for s, a in slots.items() if a["node_id"] == "accepted-contract"),
              "model_ref": ref("contract-model"), "profile_ref": ref("contract-profile")}]
    for node in proposal["nodes"]:
        nodes.append({"node_id": node["node_id"], "kind": node["kind"],
                      "artifact_slots": sorted(s for s, a in slots.items() if a["node_id"] == node["node_id"]),
                      "model_ref": ref(node["model_slot"]), "profile_ref": ref(node["profile_slot"])})
    node_index = _index(nodes, "node_id", "node")
    structure = "BRIDGE:structure:" + proposal["bridge_id"]
    claims = [{"claim_id": structure, "verifier_id": VERIFIER, "root_kind": "bridge_artifacts",
               "result_predicate": "bridge-structural/0.1", "premises": []}]
    edges = []
    for edge in proposal["edges"]:
        _require(edge["claim_id"] != structure, "candidate cannot assign the supervisor structural claim", "ORPHAN_CLAIM")
        _require(edge["source_node"] in node_index and edge["target_node"] in node_index, "edge has an unknown node")
        source, target = node_index[edge["source_node"]], node_index[edge["target_node"]]
        def refs(key):
            values = {n[key]["id"]: n[key] for n in (source, target)}
            return [values[k] for k in sorted(values)]
        relation = ref(edge["relation_slot"])
        # The supervisor assigns a registered checker only from the relation's named template;
        # every other relation stays with the unavailable semantic verifier (pending forever).
        verifier = relation_checker(files[artifacts[relation["id"]]["path"]]) or SEMANTIC_VERIFIER
        claims.append({"claim_id": edge["claim_id"], "verifier_id": verifier,
                       "root_kind": "semantic_edge", "result_predicate": "bridge-semantic-edge/0.1",
                       "premises": sorted(set(edge["premises"]) | {structure})})
        edges.append({"edge_id": edge["edge_id"], "claim_id": edge["claim_id"],
                      "source_node": edge["source_node"], "target_node": edge["target_node"],
                      "model_refs": refs("model_ref"), "profile_refs": refs("profile_ref"),
                      "relation": relation,
                      "expected_proposition_hash": edge["expected_proposition_hash"]})
    coverage = _index(proposal["obligations"], "id", "coverage obligation")
    required = {oid: r for oid, r in imported.ir["obligations"].items()
                if r["required"] and r["role"] == "guarantee" and applicability(r)["END_TO_END_VERIFIED"][0]}
    _require(set(coverage) == set(required),
             "proposal must cover exactly the required implementation-applicable accepted guarantees", "ORPHAN_CLAIM")
    plan = {"schema_version": "0.1", "format": "verislop.bridge-plan/0.1",
            "bridge_id": proposal["bridge_id"], "tier": proposal["tier"], "endpoint": proposal["endpoint"],
            "accepted_ir": ref("accepted-ir")["sha256"], "acceptance_certificate": ref("acceptance-certificate")["sha256"],
            "nodes": nodes, "artifact_slots": [slots[s] for s in sorted(slots)], "claims": claims,
            "obligations": [{"id": oid, "revision": required[oid]["revision"],
                              "accepted_statement_hash": required[oid]["formal"]["statement_hash"],
                              "required_claims": coverage[oid]["required_claims"]} for oid in sorted(required)],
            "edges": edges, "reproducible_slots": proposal["reproducible_slots"], "declared_trust": proposal["declared_trust"]}
    files["plan.json"] = canonical.dumps(plan)
    manifest = {"schema_version": "0.1", "format": "verislop.bridge-artifacts/0.1",
                "bridge_id": plan["bridge_id"], "plan_hash": canonical.digest(files["plan.json"]),
                "artifacts": [artifacts[s] for s in sorted(artifacts)]}
    files["artifacts.json"] = canonical.dumps(manifest)
    return files, plan, manifest


def _write_stage(stage: Path, files: dict[str, bytes]) -> None:
    for path, data in files.items():
        dest = stage / safe_relative(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _summary(check: StageResult, imported: ImportedContract, relative: str) -> dict:
    return {**check.summary, "accepted_contract_replayed": True, "expected_targets_semantically_checked": False,
            "preparation_certificate": relative + "/" + CERTIFICATE,
            "contract_import": _import_identity(imported), "status": "PASS"}


def _failure(result: StageResult, exc: Exception) -> StageResult:
    result.summary["structural_acceptance"] = False
    if isinstance(exc, BridgeImportError):
        result.diagnostics.extend(exc.diagnostics)
        result.status = exc.status
    elif isinstance(exc, InvalidPackage):
        result.diagnostics.append(Diagnostic(exc.code, str(exc)))
        result.status = "BLOCKED"
    elif isinstance(exc, VeriSlopError):
        result.diagnostics.extend(exc.diagnostics or [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")])
        result.status = status_from(result.diagnostics)
    else:
        result.diagnostics.append(Diagnostic("VERIFIER_FAILURE", f"bridge preparation infrastructure failure: {type(exc).__name__}",
                                             severity="infrastructure"))
        result.status = "INFRASTRUCTURE_FAILURE"
    result.summary["status"] = result.status
    return result


def run(pkg: Package, events: EventSink, proposal: Path, candidate_root: Path, *,
        expected_tier: int | None = None, expected_endpoint: str | None = None) -> StageResult:
    result = StageResult("bridge prepare", "PASS", GATE, summary=_base_summary())
    candidate_reader: PackageReader | None = None
    try:
        candidate_reader = PackageReader(candidate_root)
        proposed, proposal_snapshot = candidate_reader.json(proposal)
        _schema("bridge-proposal", proposed)
        bid = _bridge_id(proposed["bridge_id"])
        result.summary.update(bridge_id=bid, tier=proposed["tier"], endpoint=proposed["endpoint"])
        _require(expected_tier is None or proposed["tier"] == expected_tier, "proposal tier differs from requested run scope", "SCOPE_LEAK")
        _require(expected_endpoint is None or proposed["endpoint"] == expected_endpoint, "proposal endpoint differs from requested run scope", "SCOPE_LEAK")
        _destination_free(pkg.root, bid)
        candidates = {}
        for item in proposed["artifacts"]:
            _require(item["path"] not in candidates, "candidate artifacts must name distinct paths", "AMBIGUOUS_CORRESPONDENCE")
            snapshot = candidate_reader.read(item["path"], keep=True)
            candidates[item["path"]] = snapshot.data
        imported = import_contract(pkg.root)
        files, plan, manifest = _assemble(imported, proposed, proposal_snapshot.data, candidates)
        with fsutil.temporary_directory(prefix="verislop-bridge-prepare-") as temporary:
            stage = Path(temporary)
            _write_stage(stage, files)
            check = validate_package(stage, Path("plan.json"), Path("artifacts.json"))
            if check.status != "PASS":
                result.status, result.diagnostics = check.status, check.diagnostics
                result.summary["status"] = result.status
                return result
            candidate_reader.recheck()
            _source_unchanged(pkg.root, imported)
            structure = "BRIDGE:structure:" + bid
            roots = {"plan_hash": canonical.digest(files["plan.json"]), "artifacts_hash": canonical.digest(files["artifacts.json"])}
            identity = _import_identity(imported)
            raw = {**roots, "bridge_id": bid, "binding_root": "bridge_artifacts",
                   "structural_acceptance": True, "semantic_acceptance": False,
                   "assigns_end_to_end_verified": False, "contract_import": identity,
                   "pending_semantic_claims": check.summary["pending_semantic_claims"]}
            evidence = EvidenceStore(stage, pkg.run_id).record(
                claim_id=structure, verifier_id=VERIFIER, status="PASS", scope=[GATE],
                input_root=roots["artifacts_hash"], result=raw, invocation=["verislop", "bridge", "prepare"])
            evidence_path = f"evidence/{evidence.id}.json"
            certificate = {"schema_version": "0.1", "format": "verislop.bridge-preparation-certificate/0.1",
                           "bridge_id": bid, **roots, "accepted_ir_hash": plan["accepted_ir"],
                           "acceptance_certificate_hash": plan["acceptance_certificate"],
                           "checker": {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)},
                           "evidence": {"path": evidence_path, "sha256": canonical.digest_file(stage / evidence_path)},
                           "contract_import": identity, "pending_semantic_claims": raw["pending_semantic_claims"],
                           "structural_acceptance": True, "semantic_acceptance": False, "assigns_end_to_end_verified": False}
            _schema("bridge-preparation-certificate", certificate)
            _require(not ({evidence_path, evidence.record["raw_result_ref"], CERTIFICATE} & files.keys()),
                     "preparation output collides with frozen input", "INPUT_MUTATION")
            files[evidence_path] = (stage / evidence_path).read_bytes()
            files[evidence.record["raw_result_ref"]] = (stage / evidence.record["raw_result_ref"]).read_bytes()
            files[CERTIFICATE] = canonical.dumps(certificate)
            (stage / CERTIFICATE).write_bytes(files[CERTIFICATE])
            final_check = validate_package(stage, Path("plan.json"), Path("artifacts.json"))
            _require(final_check.status == "PASS", "final preparation outputs altered a frozen input", "INPUT_MUTATION")
            publish(pkg.root, bid, files)
            relative = f"bridges/{bid}"
            result.artifacts = {"bridge_bundle": relative, "preparation_certificate": relative + "/" + CERTIFICATE}
        record_preparation(pkg.root, bid, pkg.run_id)
        pkg._meta = None
        relative = f"bridges/{bid}"
        result.summary = _summary(check, imported, relative)
        result.artifacts = {"bridge_bundle": relative, "preparation_certificate": relative + "/" + CERTIFICATE}
        events.emit("verifier_decision", "bridge prepare", f"{bid}: structural preparation passed; semantic claims remain pending",
                    outcome="PASS", evidence_ref=relative + "/" + evidence_path)
        return result
    except (InvalidPackage, BridgeImportError, VeriSlopError, OSError) as exc:
        return _failure(result, exc)
    finally:
        if candidate_reader is not None:
            candidate_reader.close()


def verify_preparation(pkg: Package, bridge_id: str, events: EventSink | None = None, *,
                       semantic: str = "bindings") -> StageResult:
    """Fresh replay + byte/claim/evidence checks; existing descriptors are never trusted.

    `semantic` selects how published registered-checker acceptances are rechecked:
    "bindings" (certificate, evidence and byte bindings), "rebuild" (additionally re-run the
    registered checker and require identical outputs) or "skip".
    """
    result = StageResult("bridge verify", "PASS", GATE, summary=_base_summary())
    reader: PackageReader | None = None
    try:
        bid = _bridge_id(bridge_id)
        relative = f"bridges/{bid}"
        reader = PackageReader(pkg.root / relative)
        cert, _ = reader.json(CERTIFICATE)
        _schema("bridge-preparation-certificate", cert)
        plan, plan_snapshot = reader.json("plan.json")
        _schema("bridge-plan", plan)
        manifest, manifest_snapshot = reader.json("artifacts.json")
        _schema("bridge-artifacts", manifest)
        result.summary.update(bridge_id=bid, tier=plan["tier"], endpoint=plan["endpoint"])
        check = validate_package(pkg.root / relative, Path("plan.json"), Path("artifacts.json"))
        if check.status != "PASS":
            result.status, result.diagnostics = check.status, check.diagnostics
            result.summary["status"] = result.status
            return result
        imported = import_contract(pkg.root)
        identity = _import_identity(imported)
        proposed, proposed_snapshot = reader.json("proposal.json")
        _schema("bridge-proposal", proposed)
        _require(proposed["bridge_id"] == bid, "stored proposal identity changed", "CLAIM_MUTATION")
        candidate_bytes = {a["path"]: reader.read("candidate-inputs/" + a["path"], keep=True).data
                           for a in proposed["artifacts"]}
        rebuilt_files, _, _ = _assemble(imported, proposed, proposed_snapshot.data, candidate_bytes)
        _require(rebuilt_files["plan.json"] == plan_snapshot.data and
                 rebuilt_files["artifacts.json"] == manifest_snapshot.data,
                 "frozen plan/manifest differs from supervisor reconstruction", "INPUT_MUTATION")
        _require(cert["bridge_id"] == plan["bridge_id"] == bid and
                 cert["plan_hash"] == plan_snapshot.sha256 and cert["artifacts_hash"] == manifest_snapshot.sha256,
                 "preparation descriptor roots do not match the frozen bundle", "STALE_OR_UNBOUND_EVIDENCE")
        _require(cert["contract_import"] == identity and cert["accepted_ir_hash"] == plan["accepted_ir"] == identity["source_ir_hash"]
                 and cert["acceptance_certificate_hash"] == plan["acceptance_certificate"] == identity["source_certificate_hash"],
                 "prepared bridge no longer matches the replayed accepted source run", "INPUT_MUTATION")
        receipt, receipt_snapshot = reader.json(RECEIPT)
        _require(receipt == imported.replay_receipt and receipt_snapshot.sha256 == identity["receipt_sha256"],
                 "import receipt changed or importer is stale", "STALE_OR_UNBOUND_EVIDENCE")
        inventory = {a["path"]: a for a in manifest["artifacts"]}
        for path, data in imported.files.items():
            _require(path in inventory and inventory[path]["sha256"] == canonical.digest(data),
                     f"frozen import input differs from the source run: {path}", "INPUT_MUTATION")
        _require(cert["checker"] == {"verifier_id": VERIFIER, "verifier_hash": verifier_hash(VERIFIER)},
                 "preparation checker is stale or not the assigned issuer", "STALE_OR_UNBOUND_EVIDENCE")
        structure = "BRIDGE:structure:" + bid
        expected_claim = {"claim_id": structure, "verifier_id": VERIFIER, "root_kind": "bridge_artifacts",
                          "result_predicate": "bridge-structural/0.1", "premises": []}
        claims = {c["claim_id"]: c for c in plan["claims"]}
        _require(claims.get(structure) == expected_claim, "supervisor structural claim was replaced", "ORPHAN_CLAIM")
        registered = {entry["verifier_id"] for entry in SEMANTIC_CHECKERS.values()}
        for claim in plan["claims"]:
            if claim["claim_id"] != structure:
                _require(claim["verifier_id"] in registered | {SEMANTIC_VERIFIER} and structure in claim["premises"],
                         "semantic claim bypasses supervisor preparation assignment", "ORPHAN_CLAIM")
        _require(cert["pending_semantic_claims"] == check.summary["pending_semantic_claims"],
                 "preparation certificate omits pending semantic claims", "ORPHAN_CLAIM")
        evidence = _evidence(reader, cert["evidence"])
        assessment = evaluate_claim(expected_claim, [evidence], {"bridge_artifacts": manifest_snapshot.sha256}, "bridge_artifacts")
        _require(assessment.outcome == "PASS", "preparation evidence does not satisfy its assigned structural claim", "STALE_OR_UNBOUND_EVIDENCE")
        expected_raw = {"plan_hash": plan_snapshot.sha256, "artifacts_hash": manifest_snapshot.sha256,
                        "bridge_id": bid, "contract_import": identity, "assigns_end_to_end_verified": False,
                        "pending_semantic_claims": cert["pending_semantic_claims"]}
        for key, value in expected_raw.items():
            _require(evidence.result.get(key) == value, f"preparation evidence {key} is stale or unbound", "STALE_OR_UNBOUND_EVIDENCE")
        _source_unchanged(pkg.root, imported)
        reader.recheck()
        result.summary = _summary(check, imported, relative)
        result.artifacts = {"bridge_bundle": relative, "preparation_certificate": relative + "/" + CERTIFICATE}
        if semantic != "skip":
            selected_checkers = {claim["verifier_id"] for claim in plan["claims"]
                                 if claim["claim_id"] != structure and claim["verifier_id"] in registered}
            _require(len(selected_checkers) <= 1, "mixed semantic checker versions require separate prepared bridges",
                     "UNSUPPORTED_CAPABILITY")
            if selected_checkers == {"verislop.vscore3-checker"}:
                from .vscore3_checker import verify_published
            else:
                from .vscore_checker import verify_published

            accepted, _, semantic_diags = verify_published(pkg, bid, rebuild=semantic == "rebuild")
            done = {a["claim_id"] for a in accepted}
            pending = sorted(c for c in check.summary["pending_semantic_claims"] if c not in done)
            result.summary.update({"semantic_certificates": accepted, "pending_semantic_claims": pending,
                                   "semantic_acceptance": bool(accepted) and not pending,
                                   "expected_targets_semantically_checked": bool(accepted) and not pending,
                                   "accepted_semantic_certificates": [a["certificate"] for a in accepted]})
            if accepted:
                result.gate = SEMANTIC_GATE if semantic == "rebuild" else SEMANTIC_BINDING_GATE
            if semantic_diags:
                result.diagnostics.extend(semantic_diags)
                result.status = status_from(result.diagnostics)
                result.summary["status"] = result.status
        if events:
            events.emit("verifier_decision", "bridge verify", f"{bid}: preparation rechecked; semantic claims remain pending",
                        outcome="PASS", evidence_ref=relative + "/" + cert["evidence"]["path"])
        return result
    except (InvalidPackage, BridgeImportError, VeriSlopError, OSError) as exc:
        return _failure(result, exc)
    finally:
        if reader is not None:
            reader.close()


def verify_preparations(pkg: Package) -> tuple[list[StageResult], list[Diagnostic]]:
    """Verify the preparation inventory, including bundles omitted from bookkeeping.

    The mutable index is a discovery aid, never authority to erase a required
    preparation. Legacy bindings/link files and a tier1 monitor directory are not
    preparation bundles unless they contain one of the reserved bundle markers.
    Returned diagnostics already include the individual verification diagnostics.
    """
    results: list[StageResult] = []
    diagnostics: list[Diagnostic] = []
    reader: PackageReader | None = None
    try:
        reader = PackageReader(pkg.root)
        meta, _ = reader.json("package.json")
        _require(isinstance(meta, dict), "run package metadata is not an object")
        raw_index = meta.get("bridge_preparations", {})
        if not isinstance(raw_index, dict):
            diagnostics.append(Diagnostic("INVALID_CANDIDATE", "invalid bridge preparation index"))
            raw_index = {}
        indexed: set[str] = set()
        for bid, path in raw_index.items():
            try:
                _bridge_id(bid)
                _require(path == f"bridges/{bid}", "bridge preparation index redirects outside its assigned bundle")
                indexed.add(bid)
            except InvalidPackage as exc:
                diagnostics.append(Diagnostic(exc.code, str(exc)))
        parameters = meta.get("run_parameters", {})
        history = meta.get("stage_history", [])
        completed = meta.get("completed_stages", [])
        _require(isinstance(parameters, dict) and isinstance(history, list) and isinstance(completed, list),
                 "invalid run preparation request/history metadata")
        required = bool(parameters.get("bridge_proposal")) or "bridge:prepare" in completed or any(
            isinstance(row, dict) and row.get("stage") == "bridge:prepare" and row.get("status") == "PASS"
            for row in history)
        if required and not indexed:
            diagnostics.append(Diagnostic("VERIFIER_NOT_RUN", "requested or completed bridge preparation has no registered bundle"))
        try:
            parent = os.open("bridges", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=reader.fd)
        except FileNotFoundError:
            parent = None
        except OSError as exc:
            raise InvalidPackage("unsafe bridge preparation inventory directory") from exc
        if parent is not None:
            try:
                count = 0
                with os.scandir(parent) as entries:
                    for entry in entries:
                        count += 1
                        _require(count <= MAX_COLLECTION_ITEMS, "too many entries in bridge preparation inventory")
                        info = os.stat(entry.name, dir_fd=parent, follow_symlinks=False)
                        _require(not stat.S_ISLNK(info.st_mode), "bridge inventory contains a symbolic link")
                        if not stat.S_ISDIR(info.st_mode):
                            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                                     "bridge inventory contains a linked or special file")
                            continue
                        folder = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                        try:
                            marked = False
                            for marker in (CERTIFICATE, "plan.json", "artifacts.json", "proposal.json"):
                                try:
                                    os.stat(marker, dir_fd=folder, follow_symlinks=False)
                                    marked = True
                                except FileNotFoundError:
                                    pass
                            if marked and entry.name not in indexed:
                                diagnostics.append(Diagnostic("ORPHAN_CLAIM",
                                    f"unindexed bridge preparation bundle: bridges/{entry.name}"))
                        finally:
                            os.close(folder)
            finally:
                os.close(parent)
        for bid in sorted(indexed):
            checked = verify_preparation(pkg, bid)
            results.append(checked)
            diagnostics.extend(checked.diagnostics)
        reader.recheck()
    except InvalidPackage as exc:
        diagnostics.append(Diagnostic(exc.code, str(exc)))
    except OSError as exc:
        diagnostics.append(Diagnostic("VERIFIER_FAILURE",
            f"bridge preparation inventory could not be checked: {type(exc).__name__}", severity="infrastructure"))
    finally:
        if reader is not None:
            reader.close()
    return results, diagnostics
