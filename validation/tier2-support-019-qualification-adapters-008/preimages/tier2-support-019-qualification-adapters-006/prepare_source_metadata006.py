"""Refresh source-candidate metadata only; no runtime materialization or execution."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "validation/tier2-support-019-qualification-adapters-005"
CARRIER = ROOT / "validation/tier2-carrier-context-support-019-implementation-004"
CURRENT = "validation/tier2-support-019-qualification-adapters-006/"
PREVIOUS = "validation/tier2-support-019-qualification-adapters-005/"


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n")


def ref(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "sha256": "sha256:" + hashlib.sha256(data).hexdigest(), "byte_count": len(data)}


def update(value):
    if isinstance(value, str):
        return value.replace(PREVIOUS, CURRENT)
    if isinstance(value, list):
        return [update(item) for item in value]
    if isinstance(value, dict):
        result = {update(key): update(item) for key, item in value.items()}
        if {"path", "sha256"} <= set(result) and result["path"].startswith(CURRENT):
            actual = ref(ROOT / result["path"])
            result["sha256"] = actual["sha256"]
            if "byte_count" in result:
                result["byte_count"] = actual["byte_count"]
        return result
    return value


def methods(path):
    tree = ast.parse(path.read_text())
    result = {}
    for item in tree.body:
        if isinstance(item, ast.ClassDef):
            for child in item.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[item.name + "." + child.name] = ast.dump(child, include_attributes=False)
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[item.name] = ast.dump(item, include_attributes=False)
    return result


def main():
    active = ("runtime-configuration-template.json", "runtime-contract.json", "predicate-reader-runtime-interface.json", "finalizer-registration-template.json")
    for name in active:
        value = update(json.loads((OLD / name).read_text()))
        value["bounded006_checkpoint_binding"] = "Source-only carrier004 explicit author FIRST/NEXT/CONFIRM/HASH reconstruction; no runtime authority or inherited PASS"
        if "candidate_status" in value:
            value["candidate_status"] = "SOURCE_ONLY_SEALED_RUNTIME_UNQUALIFIED"
        write(name, value)
    config = json.loads((HERE / active[0]).read_text())
    config["interface_revision"] = "UNQUALIFIED adapters006 checkpoint reconstruction, preserving F010 and all27 full claim objects"
    config["adapters"]["capture_factory"] = str((CARRIER / "capture-amendment-003/collector_templates.py").relative_to(ROOT))
    config["adapters"]["predicate_reader_carrier_literals"] = CURRENT + "predicate-reader-carrier-literals.json"
    config["adapters"]["predicate_reader_capture_literals"] = CURRENT + "predicate-reader-capture-literals.json"
    config["source_registration_obligations"].append("register author_protocol.reconstruction_source exact path/SHA and carrier004 constants/all18 function AST hashes before any helper import; current installed source hash must be frozen")
    write(active[0], config)
    protocol_ref = ref(HERE / "author_protocol_reconstruction.py")
    carrier_ref = ref(CARRIER / "bootstrap_tier2_carrier_view.py")
    capture_ref = ref(CARRIER / "capture-amendment-003/collector_templates.py")
    amendment = {
        "format": "verislop.support019-author-checkpoint-reconstruction-amendment/1",
        "status": "SOURCE_ONLY_RUNTIME_UNQUALIFIED", "execution_authority": False, "qualification_authority": False,
        "source_root": None, "input_root": None, "new_top_level_runtime_configuration_keys": [],
        "source": carrier_ref, "capture": capture_ref, "reconstruction_source": protocol_ref,
        "registered_support_dependency": "Shared independent verifier support, source-authenticated before import; never producer API execution; trust is explicit, no algorithmic independence claim",
        "source_literals": {"constants": 6, "function_ast_hashes": 18, "author_recipe_names": ["author_first", "author_next", "confirm", "hash"]},
        "main_legacy_recipe": "Reader.recipe AST unchanged; legacy FIRST/NEXT reader bytes unchanged",
        "own_pending_vs_collector": "Authenticate static observer source, not quoted own reference data; exact whole agent_message reconstruction required; no collector observer source admitted",
        "confirmation_and_hash": "Literal executable zero-VIEW templates independently reconstructed; no stored callable/eval/dynamic function loading; fixed own strict scalar UTF8 JavaScript SHA only",
        "marker_metadata": "Only preregistered immutable002-to003 label transform; marker count/order/suffix unchanged",
        "installed_source_binding": "Additional.carrier_pure equals exact frozen synthetic_dataset/tools/bootstrap_tier2_carrier_view.py SHA; all old30 IDs/semantics unchanged",
        "runtime_boundary": "No author/model/view/native/Lean/task/materializer/qualification process executed here; all27 claims unresolved until fresh whole-root qualification"
    }
    write("author-checkpoint-amendment-006.json", amendment)
    for name in ("runtime-contract.json", "predicate-reader-runtime-interface.json"):
        value = json.loads((HERE / name).read_text())
        value["author_checkpoint_protocol"] = {"amendment": ref(HERE / "author-checkpoint-amendment-006.json"), "reconstruction_source": protocol_ref, "carrier_source": carrier_ref, "capture_source": capture_ref}
        write(name, value)
    source_files = ("predicate_reader.py", "additional_predicates.py", "assemble_ancillary_indexes.py", "current_root_reconcile.py", "materialize_adapter_configuration.py")
    delta = {}
    for name in source_files:
        before = methods(OLD / name); after = methods(HERE / name)
        delta[name] = {"changed": sorted(key for key in before.keys() & after.keys() if before[key] != after[key]), "added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()), "unchanged_count": sum(before[key] == after[key] for key in before.keys() & after.keys()), "byte_identical": (OLD / name).read_bytes() == (HERE / name).read_bytes()}
    status = {"format": "verislop.support019-checkpoint-adapter-source-candidate/1", "source_revision": "adapters006", "status": "SOURCE_ONLY_SEALED_RUNTIME_UNQUALIFIED", "source_root": None, "input_root": None, "execution_authority": False, "qualification_authority": False, "actual_models": 0, "actual_VIEWs": 0, "actual_Lean_runs": 0, "actual_task_runs": 0, "actual_qualification_verifier_runs": 0, "semantic_consumption": "UNATTESTED", "model_identity": "UNATTESTED", "all27_runtime_claims": "UNRESOLVED_NO_RUNTIME_QUALIFICATION", "sealed005_unchanged_required": True, "sealed_carrier004_unchanged_required": True, "source_changes": delta, "full_claim_documents_byte_identical": ["predicate-reader-specification.json", "reconciliation-specification.json", "additional-witness-contract.json"], "fresh_runtime_required": True, "source_development_test_count": 15}
    write("CANDIDATE_STATUS.json", status)
    write("source-fidelity-006.json", {**status, "scope": "Finite source AST and generic string/schema controls only; no runtime claim discharge", "baseline": ref(OLD / "hash-manifest.json"), "carrier_manifest": ref(CARRIER / "hash-manifest.json")})
    historical = sorted(path.name for path in HERE.iterdir() if path.is_file() and (OLD / path.name).is_file() and path.read_bytes() == (OLD / path.name).read_bytes())
    write("historical-source-documents-006.json", {"format": "verislop.support019-historical-source-copy-index/1", "files": historical, "authority": "Byte-preserved005 source inputs/documents; old observations/statuses refer only to their recorded roots, never current006 runtime evidence", "qualification_authority": False})
    (HERE / "README.md").write_text("# Adapters006 source candidate\n\nThis sealed source-only candidate extends sealed005 with exact independent reconstruction of carrier004 author FIRST/NEXT/CONFIRM/HASH and the whole original author message. Existing legacy main VIEW recipes and all27 full claim objects stay unchanged. No runtime qualification result is inherited.\n\nThe only existing method changes are Reader.recipe_literals/fresh_author and AdditionalPredicates.carrier_pure/fresh_author. Reader.author_protocol_module/author_message and the registered stdlib-only author_protocol_reconstruction.py support are added. The assembler, materializer and reconciler remain byte-identical to005. Current installed carrier SHA is read from the frozen map; all old30 pure controls retain their predicates.\n\nSee SPECIFICATION_BEFORE_SOURCE.md, PROTOCOL_RECONSTRUCTION_BEFORE_SOURCE.md and METADATA_AND_CONTROLS_BEFORE_SOURCE.md for prior source authority; author-checkpoint-amendment-006.json for exact bindings; source-fidelity-006.json for the AST delta; source-controls-registration-006.json and source-controls-actual-receipt-006.json for unrelated development checks. The historical-source-documents index classifies preserved older documents and observations.\n\nThe carrier literal profile names the exact source004 and reconstruction-source dependency. Both paths and hashes, the capture003 factory and profiles, and installed production SHA must be included in a new complete frozen source map before any import or actual call. No new top-level configuration key is needed. Requested Sol/none, one author, raw task_name schema, unchanged literal FINAL, exact markers/roots/totals/EOF and current-root guards are preserved. Semantic consumption and model identity remain UNATTESTED.\n\nStatus: SOURCE_ONLY_SEALED_RUNTIME_UNQUALIFIED. A separate review and fresh complete qualification are required. No production installation, model, VIEW, materializer, Lean, native/task or qualification verifier was executed by this candidate preparation.\n")
    for name in ("predicate-reader-source-manifest.json", "reconciler-hash-manifest.json", "candidate-source-bindings.json"):
        value = update(json.loads((OLD / name).read_text()))
        value.update({"source_revision": "adapters006", "status": "SOURCE_ONLY_SEALED_RUNTIME_UNQUALIFIED", "execution_authority": False, "qualification_authority": False, "input_root": None, "source_root": None, "final_manifest_sealed": False, "bounded006_checkpoint_binding": "Actual006 source controls only; no27 runtime claims evaluated"})
        value["files"] = {path: {key: entry[key] for key in ("sha256", "byte_count")} for path in value["files"] for entry in [ref(ROOT / path)]}
        if name == "predicate-reader-source-manifest.json":
            value["checks"] = "Registered15 unrelated source reconstruction/schema/AST controls only; no reader/qualification/model/view/task execution"
            value["files"][protocol_ref["path"]] = {key: protocol_ref[key] for key in ("sha256", "byte_count")}
        write(name, value)


if __name__ == "__main__":
    main()
