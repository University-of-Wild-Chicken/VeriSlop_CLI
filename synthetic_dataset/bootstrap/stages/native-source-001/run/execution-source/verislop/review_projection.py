"""Registered deterministic projection of a validated Tier 2 mechanical execution.

Metadata normalization is positional and versioned. The complete semantic payload remains
in the target; identifiers merely named time/id/path/sequence are never recursively removed.
Projection equality does not authorize mechanics: both executions must first validate.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import canonical, fsutil, schemas
from .bridges.manifest import InvalidPackage, PackageReader
from .evidence import EvidenceStore
from .verifiers import verifier_hash

FORMAT = "verislop.review-mechanical-projection/0.1"
EXCLUDED_PATHS = (
    ("record", "evidence_id"), ("record", "raw_result_ref"), ("record", "raw_result_hash"),
    ("raw", "sequence"), ("raw", "recorded_at"),
    *(("execution", k) for k in ("attempt_id", "started_at", "finished_at", "wall_ms", "work_directory")),
)
WRAPPER = {"claim_id", "sequence", "recorded_at"}

# Each alternative is a closed producer result format, before the evidence-store wrapper.
# These explicit legacy adapters preserve every declared field; an unknown field is rejected.
RESULT_FIELDS = {
    "verislop.interpretation-recorder": [
        {"milestone_outcome", "diagnostics", "coverage", "blocked_guarantees", "routing", "candidate_source"},
        {"milestone_outcome", "reason", "record_digest", "blocked_by", "assumption_supplier"}],
    "verislop.formal-statement-checker": [
        {"milestone_outcome", "binding_root", "reason", "record_digest"},
        {"milestone_outcome", "binding_root", "representation", "lean_symbol", "statement_hash", "bindings"}],
    "verislop.lean-acceptance": [
        {"milestone_outcome", "codes", "certificate", "certificate_hash", "axioms", "statement_hash", "binding_root", "policy"}],
    "verislop.reifier": [{"milestone_outcome", "reification_ref", "check", "ir_hash"}],
    "verislop.vscore-materializer": [
        {"milestone_outcome", "materialized", "inventory_hash", "proof_checked", "symbols", "objects", "source_hash", "codes"}],
    "verislop.vscore-linker": [
        {"milestone_outcome", "structural_linked", "link_record_hash", "inventory_hash", "symbols", "correspondence", "semantic_acceptance"}],
    "verislop.bridge-preparation": [
        {"plan_hash", "artifacts_hash", "bridge_id", "binding_root", "structural_acceptance", "semantic_acceptance",
         "assigns_end_to_end_verified", "contract_import", "pending_semantic_claims"}],
    "verislop.vscore-checker": [
        {"bridge_id", "edge_id", "plan_hash", "artifacts_hash", "semantic_edge_root", "template", "proposition_hash",
         "proof_symbol", "edge_axioms", "inputs", "accepted_modules", "obligations", "implementation_ir_hash",
         "builds", "certificate_descriptor_hash", "semantic_acceptance", "assigns_end_to_end_verified"}],
    "verislop.closure": [
        {"format", "milestone_outcome", "binding_root", "predicate_satisfied", "builds", "determinism", "nonfinal_claims",
         "required_claim_ids", "endpoint", "complete_required_coverage", "declared_dependencies",
         "public_provenance_complete", "output_plan_complete"},
        {"format", "milestone_outcome", "binding_root", "endpoint", "language", "semantic_acceptance",
         "complete_mechanical_closure", "obligation", "revision", "accepted_statement_hash", "premises"}],
}
BUILD_FIELDS = {"build", "ok", "errors", "closure_root", "producer", "outputs", "execution"}
OUTPUT_FIELDS = {"contract_receipt", "contract_artifacts", "contract_obligations", "accepted_ir", "semantic_build", "goal",
                 "semantic_certificate", "implementation_ir", "module_parts", "materialization_inventory", "link_record",
                 "nonfinal_outcomes", "provenance_graph"}
CLAIM_ROW_FIELDS = {"claim_id", "outcome", "required", "verifier", "root_kind", "input_root", "premises", "evidence_refs", "reason"}


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise InvalidPackage(message, "STALE_OR_UNBOUND_EVIDENCE")


def _closed(value: Any, fields: set[str], where: str) -> None:
    _require(isinstance(value, dict) and set(value) == fields, f"unknown or missing {where} fields")


def normalizer_registry() -> dict:
    return {"format": "verislop.result-normalizers/0.1", "implementation_hash": canonical.digest_file(Path(__file__)),
            "evidence_schema_hash": canonical.digest_file(schemas.schema_dir() / "evidence.schema.json"),
            "formats": {vid: {"id": vid + ".result-adapter/0.1", "closed_alternatives": [sorted(s) for s in fields]}
                        for vid, fields in sorted(RESULT_FIELDS.items())},
            "build_fields": sorted(BUILD_FIELDS), "output_fields": sorted(OUTPUT_FIELDS),
            "claim_row_fields": sorted(CLAIM_ROW_FIELDS), "excluded_paths": [list(p) for p in EXCLUDED_PATHS],
            "source_mappings": {"verislop.closure": {"/raw/builds/*/execution/wall_ms": "/execution/wall_ms"}}}


def project_envelope(envelope: dict) -> dict:
    _closed(envelope, {"record", "raw", "execution"}, "normalized envelope")
    _require(all(isinstance(envelope[key], dict) for key in ("record", "raw", "execution")),
             "normalized envelope components must be objects")
    _require(set(envelope["execution"]).issubset({p[1] for p in EXCLUDED_PATHS if p[0] == "execution"}),
             "unknown execution metadata")
    for key, value in envelope["execution"].items():
        _require(type(value) is int and value >= 0 if key == "wall_ms" else isinstance(value, str) and bool(value),
                 f"invalid execution metadata {key}")
    out = canonical.loads(canonical.dumps(envelope))
    for parent, key in EXCLUDED_PATHS:
        out[parent].pop(key, None)
    return out


def _builds(builds: list, metadata: list) -> list:
    result = []
    for index, build in enumerate(builds):
        if not build.get("ok"):
            # Failure observations have a separate explicitly closed format.
            _closed(build, {"build", "ok", "errors"}, "failed build")
            result.append(build)
            continue
        _closed(build, BUILD_FIELDS, "build observation")
        _closed(build["execution"], {"wall_ms"}, "build execution")
        _closed(build["outputs"], OUTPUT_FIELDS, "complete build output")
        _require(type(build["execution"]["wall_ms"]) is int and build["execution"]["wall_ms"] >= 0,
                 "invalid build wall_ms")
        metadata.append({"source_path": f"/raw/builds/{index}/execution/wall_ms", "value": build["execution"]["wall_ms"]})
        normalized = project_envelope({"record": {}, "raw": {k: v for k, v in build.items() if k != "execution"},
                                       "execution": build["execution"]})["raw"]
        # Unknown nested semantic data is retained verbatim, including arbitrary map IDs.
        # Complete artifact schemas are validated by the mechanical execution, never filtered.
        result.append(normalized)
    return result


def normalize(record: dict, raw: dict, *, dependency: Any = None) -> tuple[str, dict]:
    issues = schemas.validate("evidence", record)
    _require(not issues, f"invalid evidence record: {issues[:1]}")
    vid = record["verifier_id"]
    formats = RESULT_FIELDS.get(vid)
    _require(formats is not None, f"no registered normalizer for {vid}")
    fields = set(raw) - WRAPPER
    _require(fields in formats and WRAPPER.issubset(raw), f"unknown or missing raw result fields for {vid}")
    _require(raw["claim_id"] == record["claim_id"], "raw result names another claim")
    _require(type(raw["sequence"]) is int and raw["sequence"] >= 1, "invalid raw result sequence")
    _require(isinstance(raw["recorded_at"], str) and bool(raw["recorded_at"]), "invalid raw result timestamp")
    result = canonical.loads(canonical.dumps(raw))
    metadata = []
    if vid == "verislop.closure" and "builds" in result:
        result["builds"] = _builds(result["builds"], metadata)
        for row in result["nonfinal_claims"]:
            _closed(row, CLAIM_ROW_FIELDS, "non-final claim row")
            if dependency is not None:
                row["evidence_refs"] = [dependency(ref, row["claim_id"]) for ref in row["evidence_refs"]]
    envelope = {"record": canonical.loads(canonical.dumps(record)), "raw": result, "execution": {}}
    return vid + ".result-adapter/0.1", project_envelope(envelope)


def build(pkg, snapshot: dict) -> dict:
    """Project one current, validated execution; retain its independently checked raw digest."""
    from .backends import vscore_closure

    _require(not vscore_closure.validate_frozen(pkg), "frozen closure inputs changed before review")
    rel = snapshot["mechanical_result_path"]
    fsutil.check_relpath(rel)
    checked = vscore_closure.validate_execution((pkg.root / rel).parent, expected_root=snapshot["closure_root"])
    _require(checked == {k: v for k, v in snapshot.items() if k != "mechanical_result_path"}, "mechanical snapshot differs from its exact publication")
    manifest = canonical.load_file(pkg.root / "closure/manifest.json")
    reader = PackageReader(pkg.root)
    evidence = {e.id: e for e in pkg.evidence.load()}
    artifacts = []
    try:
        for entry in manifest["entries"]:
            file = reader.read(entry["path"])
            _require(file.sha256 == entry["sha256"] and file.size == entry["size"], "frozen artifact changed during projection")
            artifacts.append({**entry, "producer": "frozen-supervisor-inventory"})
            components = Path(entry["path"]).parts
            if Path(file.path).name.startswith("ev-") and file.path.endswith(".json") and "evidence" in components:
                base = pkg.root.joinpath(*components[:components.index("evidence")])
                ev = EvidenceStore(base, snapshot["closure_id"])._load_one(pkg.root / entry["path"])
                evidence[ev.id] = ev
        reader.recheck()
    finally:
        reader.close()
    definitions = {c["claim_id"]: c for c in vscore_closure._claims(pkg)}
    rows = {c["claim_id"]: c for c in snapshot["claims"]}
    _require(len(rows) == len(snapshot["claims"]) and set(rows) == set(definitions), "projection claim inventory differs from frozen graph")

    def dependency(ref: str, cid: str) -> dict:
        _require(ref.startswith("evidence:"), "unknown dependency reference format")
        ev = evidence.get(ref[len("evidence:"):])
        _require(ev is not None and ev.valid and ev.verifier_current and ev.claim_id == cid, "dependency evidence missing, stale or assigned to another claim")
        row = rows[cid]
        _require(ev.record["verifier_id"] == row["verifier"] and ev.record["input_root_hash"] == row["input_root"], "dependency issuer/root differs")
        return {"claim_id": cid, "verifier": ev.record["verifier_id"], "verifier_hash": ev.record["verifier_hash"],
                "input_root": ev.record["input_root_hash"], "projected_claim": cid}

    projected = []
    for cid, row in sorted(rows.items()):
        _closed(row, CLAIM_ROW_FIELDS, "mechanical claim row")
        claim = definitions[cid]
        payload, fmt = None, None
        if row["evidence_refs"]:
            _require(len(row["evidence_refs"]) == 1, "ambiguous selected claim evidence")
            ref = row["evidence_refs"][0]
            dependency(ref, cid)
            ev = evidence[ref[len("evidence:"):]]
            fmt, payload = normalize(ev.record, ev.result, dependency=dependency)
        elif row["required"]:
            _require(row["outcome"] != "PASS", "required PASS has no actual execution")
        projected.append({"claim_id": cid, "premises": row["premises"], "required": row["required"],
                          "obligation": claim.get("obligation"), "revision": claim.get("revision"),
                          "accepted_statement_hash": claim.get("accepted_statement_hash"),
                          "verifier": row["verifier"], "verifier_hash": verifier_hash(row["verifier"]),
                          "root_kind": row["root_kind"], "input_root": row["input_root"],
                          "result_predicate": claim["result_predicate"], "result_format": fmt,
                          "outcome": row["outcome"], "scope": claim["scope"],
                          "trusted_dependencies": claim["trusted_dependencies"], "envelope": payload})
    metadata = []
    projection = {"format": FORMAT, "closure_id": snapshot["closure_id"], "closure_root": snapshot["closure_root"],
                  "mechanical_status": snapshot["mechanical_status"], "backend": snapshot["backend"], "endpoint": snapshot["endpoint"],
                  "normalizer_registry_hash": canonical.digest_json(normalizer_registry()),
                  "required_claim_ids": sorted(c["claim_id"] for c in projected if c["required"]),
                  "claims": projected, "artifacts": sorted(artifacts, key=lambda a: (a["role"], a["producer"], a["path"])),
                  "builds": _builds(snapshot["builds"], metadata), "determinism": snapshot["determinism"],
                  "dependencies": snapshot["dependencies"], "boundary": snapshot["boundary"]}
    result_path = pkg.root / rel
    raw_inventory = {"format": "verislop.review-execution-inventory/0.1", "mechanical_result_path": rel,
                     "mechanical_result_hash": canonical.digest_file(result_path), "frozen_artifacts": manifest["entries"],
                     "execution_artifacts": snapshot["execution_inventory"]}
    return {"projection": projection, "projection_hash": canonical.digest_json(projection),
            "normalizer_registry_hash": projection["normalizer_registry_hash"],
            "raw_inventory": raw_inventory, "raw_inventory_hash": canonical.digest_json(raw_inventory)}


def review_target(checkpoint: str, closure_root: str, projection_hash: str,
                  reviewer_config_hash: str, model_manifest_hash: str) -> dict:
    return {"format": "verislop.review-target/0.2", "checkpoint": checkpoint, "closure_root": closure_root,
            "mechanical_projection_hash": projection_hash, "reviewer_configuration_hash": reviewer_config_hash,
            "model_resolution_manifest_hash": model_manifest_hash}
