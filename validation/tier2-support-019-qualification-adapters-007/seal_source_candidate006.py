"""Seal this source-only package after registered development controls."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "validation/tier2-support-019-qualification-adapters-005"


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def record(path):
    data = path.read_bytes()
    return {"sha256": sha(data), "byte_count": len(data)}


def main():
    if (HERE / "hash-manifest.json").exists() or (HERE / "SEAL.sha256").exists():
        raise ValueError("existing seal cannot be mutated")
    receipt = json.loads((HERE / "source-controls-actual-receipt-006.json").read_text())
    registration_path = ROOT / receipt["registration"]["path"]
    if sha(registration_path.read_bytes()) != receipt["registration"]["sha256"]:
        raise ValueError("development registration mutation")
    registration = json.loads(registration_path.read_text())
    if type(receipt["exit_code"]) is not int or receipt["exit_code"] != 0 or receipt["status"] != "SOURCE_CONTROLS_EXIT_ZERO" or registration["test_count"] != 15 or receipt["before"] != receipt["after"] != {}:
        raise ValueError("source control receipt required")
    for path, expected in receipt["after"].items():
        if sha((ROOT / path).read_bytes()) != expected:
            raise ValueError("bound source changed after development controls: " + path)
    for entry in receipt["logs"].values():
        if record(ROOT / entry["path"]) != {key: entry[key] for key in ("sha256", "byte_count")}:
            raise ValueError("raw log mutation")
    for name in ("predicate-reader-specification.json", "reconciliation-specification.json", "additional-witness-contract.json"):
        if (HERE / name).read_bytes() != (OLD / name).read_bytes():
            raise ValueError("full claim source changed")
    for name in ("runtime-contract.json",):
        if json.loads((HERE / name).read_text())["additional_claims"] != json.loads((OLD / name).read_text())["additional_claims"]:
            raise ValueError("additional claim objects changed")
    core = ("predicate_reader.py", "additional_predicates.py", "assemble_ancillary_indexes.py", "current_root_reconcile.py", "materialize_adapter_configuration.py", "author_protocol_reconstruction.py")
    patch = []
    for name in core:
        before = (OLD / name).read_text().splitlines(keepends=True) if (OLD / name).exists() else []
        after = (HERE / name).read_text().splitlines(keepends=True)
        patch.extend(difflib.unified_diff(before, after, fromfile=str((OLD / name).relative_to(ROOT)) if before else "/dev/null", tofile=str((HERE / name).relative_to(ROOT))))
    (HERE / "exact-source-diff-005-to-006.patch").write_text("".join(patch))
    write("source-only-actual-tool-observations-006.json", {
        "format": "verislop.support019-source-development-tool-observations/1",
        "qualification_authority": False, "execution_scope": "UNRELATED_SOURCE_DEVELOPMENT_ONLY",
        "successful_registration": {"actual_tool_chunk_id": "215069", "actual_numeric_exit_code": 0, "exposed_output": "{\"registered_tests\": 15, \"bound_source_inputs\": 93, \"sealed005_and_carrier004_authentic\": true, \"current_production004_exact\": true}\n"},
        "successful_control_runner": {"actual_tool_chunk_id": "64c177", "actual_numeric_exit_code": 0, "actual_child_pid": receipt["actual_child_pid"], "receipt_path": str((HERE / "source-controls-actual-receipt-006.json").relative_to(ROOT))},
        "earlier_metadata_precheck_failure": {"actual_tool_chunk_id": "7236b1", "actual_numeric_exit_code": 1, "concrete_error": "FileNotFoundError: [Errno 2] No such file or directory: '/home/augustus/VeriSlop_CLI/CANDIDATE_STATUS.json'", "reason": "Sealed004 uses package-relative keys; metadata precheck used repo-relative base", "test_process_created": False},
        "earlier_runner_without_registration": {"actual_tool_chunk_id": "2e3d4a", "actual_numeric_exit_code": 1, "concrete_error": "FileNotFoundError: [Errno 2] No such file or directory: '/home/augustus/VeriSlop_CLI/validation/tier2-support-019-qualification-adapters-006/source-controls-registration-006.json'", "test_process_created": False},
        "source_guard_count": len(receipt["after"]), "registered_test_count": 15, "runtime_claims_evaluated": 0,
        "actual_models": 0, "actual_VIEWs": 0, "actual_Lean_runs": 0, "actual_task_runs": 0, "actual_qualification_verifier_runs": 0,
        "hidden_outer_tool_envelope": "UNAVAILABLE", "semantic_consumption": "UNATTESTED", "model_identity": "UNATTESTED"
    })
    old_observations = {name: json.loads((HERE / name).read_text()) for name in ("predicate-reader-source-manifest.json", "reconciler-hash-manifest.json", "candidate-source-bindings.json")}
    for name, value in old_observations.items():
        value["final_manifest_sealed"] = True
        if name == "predicate-reader-source-manifest.json":
            value.update({"actual_tests_run": 15, "actual_controls_run": 15, "actual_reader_runs": 0, "actual_models_called": 0, "review_scope": "Unrelated generic source development controls only; no actual task/evaluator expected answer, proof or qualification verifier inputs inspected"})
        write(name, value)
    historical = sorted(path.name for path in HERE.iterdir() if path.is_file() and (OLD / path.name).is_file() and path.read_bytes() == (OLD / path.name).read_bytes())
    write("historical-source-documents-006.json", {"format": "verislop.support019-historical-source-copy-index/1", "files": historical, "authority": "Byte-preserved005 source inputs/documents; old observations/statuses refer only to their recorded roots, never current006 runtime evidence", "qualification_authority": False})
    reader_manifest = json.loads((HERE / "predicate-reader-source-manifest.json").read_text())
    reader_names = [Path(path).name for path in reader_manifest["files"]] + ["author-checkpoint-amendment-006.json", "source-fidelity-006.json", "source-controls-registration-006.json", "source-controls-actual-receipt-006.json", "exact-source-diff-005-to-006.patch"]
    reader_manifest["files"] = {str((HERE / name).relative_to(ROOT)): record(HERE / name) for name in sorted(set(reader_names))}
    write("predicate-reader-source-manifest.json", reader_manifest)
    reconciler = json.loads((HERE / "reconciler-hash-manifest.json").read_text())
    reconciler["files"] = {str(path.relative_to(ROOT)): record(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name not in {"reconciler-hash-manifest.json", "candidate-source-bindings.json", "hash-manifest.json", "SEAL.sha256"}}
    write("reconciler-hash-manifest.json", reconciler)
    candidate = json.loads((HERE / "candidate-source-bindings.json").read_text())
    candidate["files"] = {str(path.relative_to(ROOT)): record(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name not in {"candidate-source-bindings.json", "hash-manifest.json", "SEAL.sha256"}}
    write("candidate-source-bindings.json", candidate)
    manifest = {"format": "verislop.support019-adapter-current-source-manifest/1", "source_revision": "adapters006", "status": "SOURCE_ONLY_SEALED_RUNTIME_UNQUALIFIED", "input_root": None, "source_root": None, "execution_authority": False, "qualification_authority": False, "runtime_claims_evaluated": 0, "files": {str(path.relative_to(ROOT)): record(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name not in {"hash-manifest.json", "SEAL.sha256"}}}
    write("hash-manifest.json", manifest)
    manifest_digest = hashlib.sha256((HERE / "hash-manifest.json").read_bytes()).hexdigest()
    (HERE / "SEAL.sha256").write_text(manifest_digest + "  hash-manifest.json\n")
    print(json.dumps({"status": "SOURCE_ONLY_SEALED_RUNTIME_UNQUALIFIED", "manifest_sha256": "sha256:" + manifest_digest, "seal_file_sha256": sha((HERE / "SEAL.sha256").read_bytes()), "file_count": len(manifest["files"]), "runtime_claims_evaluated": 0}))


if __name__ == "__main__":
    main()
