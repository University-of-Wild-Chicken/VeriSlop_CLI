#!/usr/bin/env python3
"""Future write-once registration only. Never executes tests/models/builds/probes.

NOT RUN in this preparation. Requires reviewed installed sources and supplied
fresh nonexecuting preflight/config/authorization artifacts. This materializer
uses the current producer's canonical source inventory, never a predicted root.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

from registration_lib import digest, file_map, load, need, regular, verify_map, write_once

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXPECTED_CARRIER = "sha256:9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366"
EXPECTED_EQUALITY = "sha256:e539b2c7ab0c6aa2295dad45dc361481240106c678cc0aefbe08eeff6e7b6828"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--installation-review", required=True)
    parser.add_argument("--qualification-root", required=True)
    args = parser.parse_args()
    config = load(regular(ROOT, args.config))
    preflight = load(regular(ROOT, args.preflight))
    review = load(regular(ROOT, args.installation_review))
    floor = load(HERE / "mandatory-floor.json")
    controls = load(HERE / "control-registration.json")
    claims = load(HERE / "claims.json")
    need(review["status"] == "ROOT_REVIEWED_INSTALLED" and
         review["oldstage018_scope_audit_resolved"] is True and
         review["capture_amendment_reviewed_frozen"] is True,
         "ROOT_INSTALLATION_OR_CAPTURE_REVIEW_PENDING")
    capture = config["final_capture_amendment"]
    need(capture["revision"] == "002" and capture["status"] == "ROOT_SOURCE_REVIEWED_FROZEN" and
         review["final_capture_sha256"] == capture["sha256"] and
         digest(regular(ROOT, capture["path"]).read_bytes()) == capture["sha256"],
         "FINAL_CAPTURE002_REVIEW_AND_HASH_PENDING")
    need(config["capture002_weird_path_control_ids"] and
         review["capture002_weird_path_control_ids"] == config["capture002_weird_path_control_ids"],
         "CAPTURE002_WEIRD_PATH_CONTROLS_UNREGISTERED")
    need(review["candidate_hashes"] == {"carrier": EXPECTED_CARRIER, "equality": EXPECTED_EQUALITY},
         "REVIEWED_CANDIDATE_HASH_MISMATCH")
    need(digest(regular(ROOT, "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py").read_bytes()) == EXPECTED_CARRIER
         and digest(regular(ROOT, "verislop/contract_refutation.py").read_bytes()) == EXPECTED_EQUALITY,
         "REVIEWED_SOURCES_NOT_INSTALLED")
    # These imports happen only during a later explicitly authorized materialization.
    # No import/test collection is performed by this preparation task.
    sys.path.insert(0, str(ROOT))
    from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
    from verislop import canonical
    sources = bootstrap.source_inventory()
    tests = file_map(ROOT, [p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("*.py")])
    source_root = canonical.digest_json(sources)
    need(preflight["format"] in ("verislop.support018-suite-preflight/1", "verislop.support019-suite-preflight/1")
         and preflight["tests_executed"] == preflight["model_calls"] == 0
         and preflight["task_inputs"] is False and preflight["source_files"] == sources
         and preflight["test_sources"] == tests and preflight["source_root"] == source_root,
         "PREFLIGHT_NOT_CURRENT_NONEXECUTING_INVENTORY")
    ids, modules = preflight["test_ids"], preflight["test_modules"]
    need(len(ids) == len(set(ids)) == preflight["test_count"] and
         set(floor["registered_test_ids"]).issubset(ids) and
         set(floor["test_modules"]).issubset(modules) and len(modules) == len(set(modules)),
         "MANDATORY_EXACT180_OR15_MODULE_FLOOR_OMITTED")
    added = set(ids) - set(floor["registered_test_ids"])
    need(added == set(config["newly_registered_test_ids"]) and
         config["reviewed_regression_inventory_complete"] is True and
         set(review["required_new_test_ids"]).issubset(added), "NEW_REGRESSION_REGISTRATION_INCOMPLETE")
    need(config["core_model_calls"] == 0 and config["ancillary_fresh_author_calls"] == 1 and
         config["fresh_author"]["requested_model"] == "gpt-6.1-sol" and
         config["fresh_author"]["fork_turns"] == "none" and
         config["fresh_author"]["model_identity"] == "UNATTESTED" and
         config["fresh_author"]["semantic_consumption"] == "UNATTESTED",
         "MODEL_COUNT_OR_UNATTESTED_BOUNDARY_CHANGED")
    need(config["inference_timeout"] is None and config["retrieval_timeout"] is None and
         config["review_timeout"] is None and config["strict_implementation_proof_release_unchanged"] is True,
         "POLICY_OR_DEADLINE_DELTA")
    need([p["id"] for p in config["execution_phases"]] == floor["phase_order"],
         "FOUR_ORIGINAL_PHASES_OMITTED_OR_REORDERED")
    mandatory_gates = load(HERE / "registration-template.json")["mandatory_additional_process_gates"]
    need([p["id"] for p in config["additional_processes"]] == mandatory_gates,
         "ADDITIONAL_ACTUAL_PROCESSES_NOT_REGISTERED")
    need(config["equality_original44"] == controls["equality_original44"] and
         config["equality_new11"] == controls["equality_new11"] and
         config["improved_grouped_binding_registered"] is True, "EQUALITY_REQUIREMENTS_WEAKENED")
    expected_claims = [c["id"] for c in claims["original_claims"] + claims["additional_claims"]]
    need(list(config["independent_claim_checks"]) == expected_claims and
         all(config["independent_claim_checks"][cid]["predicate_implementation_reviewed"] is True
             for cid in expected_claims), "INDEPENDENT_PREDICATE_IMPLEMENTATIONS_UNBOUND")
    need(config["claims_sha256"] == digest((HERE / "claims.json").read_bytes()), "CLAIM_MUTATION")
    target = Path(args.qualification_root)
    need(not target.is_absolute() and ".." not in target.parts and target.parent == Path("validation")
         and target.name.startswith("tier2-support-019-qualification-") and not (ROOT / target).exists(),
         "QUALIFICATION_DESTINATION_NOT_NEW")
    combined = config["prospective_gate_sharing"]
    need(combined["declared_before_any_actual_or_model_call"] is True and
         combined["prior_development_outcomes_reusable"] is False and
         combined["single_current_root_author_only"] is True, "POSTHOC_OR_DUPLICATE_MODEL_GATE_SHARING")
    all_names = set(config["verification_input_paths"]) | set(sources) | set(tests)
    all_names.update(p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file())
    all_names.update([args.config, args.preflight, args.installation_review])
    all_names.add(capture["path"])
    adapters = load(HERE / "predicate-reader-adaptation-specification.json")
    need(set(adapters["planned_sources"].values()).issubset(config["required_verifier_paths"]),
         "NAMED_RAW_PREDICATE_ADAPTER_SOURCES_MISSING")
    definitions = load(HERE / "specification-before-implementation.json")["baseline_definitions"]
    definitions += load(HERE / "audit-evidence-contract.json")["amendments"]
    definitions += adapters["source_templates"]
    for definition in definitions:
        need(digest(regular(ROOT, definition["path"]).read_bytes()) == definition["sha256"],
             "REGISTERED_GENERIC_REFERENCE_MUTATION")
        all_names.add(definition["path"])
    need(set(preflight["required_collection_inputs"]).issubset(all_names), "COLLECTION_INPUT_OMISSION")
    need(set(config["required_verifier_paths"]).issubset(all_names), "VERIFIER_INPUT_OMISSION")
    need(config["toolchain"]["pin"] and config["toolchain"]["version"] and config["toolchain"]["githash"],
         "TOOLCHAIN_NOT_REGISTERED")
    from verislop import leanbridge, policy
    need(config["toolchain"] == leanbridge.resolve_toolchain().identity() and
         config["kernel_tool_hash"] == leanbridge.kernel_tool_hash() and
         config["policy_hash"] == policy.policy_hash(policy.get("strict")),
         "CURRENT_LEAN_KERNEL_POLICY_BINDING_MISMATCH")
    baseline = load(regular(ROOT, "validation/tier2-support-018-qualification-002/qualification-specification.json"))
    need(config["policy_hash"] == baseline["policy_hash"] and
         config["kernel_tool_hash"] == baseline["kernel_tool_hash"] and
         config["toolchain"] == baseline["toolchain"], "STRICT_POLICY_OR_PINNED_TOOLCHAIN_CHANGED")
    for entry in config["execution_phases"] + config["additional_processes"]:
        need(type(entry["accepted_exit_code"]) is int and entry["accepted_exit_code"] == 0 and
             entry["argv"] and isinstance(entry["environment"], dict) and entry["outputs"],
             "PROCESS_COMMAND_OUTPUT_OR_EXIT_REGISTRATION_MISSING")
        need(entry["producer_path"] in all_names and
             entry["producer_path"] in config["required_verifier_paths"], "PROCESS_PRODUCER_NOT_FROZEN")
    for key in ("actual_process_output_index", "actual_channel_evidence", "actual_author_evidence"):
        path = Path(config[key + "_path"])
        need(not path.is_absolute() and ".." not in path.parts and
             path.is_relative_to(target), "EVIDENCE_INDEX_NOT_IN_FRESH_ROOT")
    need(config["fresh_evidence_prefixes"] and target.as_posix() in config["fresh_evidence_prefixes"] and
         all(name.startswith("validation/") and "/runs/run001" not in name and
             "tier2-support-018-qualification-002" not in name and
             "tier2-support-018-independent-audit" not in name for name in config["fresh_evidence_prefixes"]),
         "STALE_EVIDENCE_PREFIX_ADMITTED")
    for path, expected in config["external_runtime_files"].items():
        p = Path(path)
        need(p.is_absolute() and p.is_file() and not p.is_symlink() and digest(p.read_bytes()) == expected,
             "EXTERNAL_RUNTIME_HASH_MISMATCH:" + path)
    copies = config["pre_freeze_copies"]
    need(isinstance(copies, list) and copies, "PREFREEZE_COPY_PLAN_MISSING")
    generated = set()
    for entry in copies:
        need(isinstance(entry, dict) and set(entry) == {"source", "target", "sha256"}, "PREFREEZE_COPY_SCHEMA")
        destination = Path(entry["target"])
        need(not destination.is_absolute() and ".." not in destination.parts and
             destination.as_posix() == entry["target"] and destination.is_relative_to(target / "original-channel") and
             destination != target / "original-channel" and entry["target"] not in generated,
             "PREFREEZE_COPY_TARGET_NOT_NEW_CANONICAL_ORIGINAL_CHANNEL")
        need(entry["source"] in all_names and digest(regular(ROOT, entry["source"]).read_bytes()) == entry["sha256"],
             "PREFREEZE_COPY_SOURCE_UNBOUND")
        generated.add(entry["target"])
        all_names.add(entry["target"])
    verification_path = config["verification_source_manifest_path"]
    need(verification_path == (target / "verification-source-manifest.json").as_posix(),
         "VERIFICATION_SOURCE_MANIFEST_PATH_NOT_EXACT")
    generated.add(verification_path)
    all_names.add(verification_path)
    initial_hashes = file_map(ROOT, sorted(all_names - generated))
    verify_map(ROOT, sources)
    verify_map(ROOT, tests)
    when = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (ROOT / target).mkdir()
    for entry in copies:
        raw = regular(ROOT, entry["source"]).read_bytes()
        need(digest(raw) == entry["sha256"] == initial_hashes[entry["source"]], "PREFREEZE_COPY_SOURCE_MUTATION")
        destination = ROOT / entry["target"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        need(destination.resolve() == destination.absolute() and not destination.exists(), "PREFREEZE_COPY_TARGET_INDIRECT_OR_EXISTING")
        with destination.open("xb") as stream:
            stream.write(raw)
    verify_map(ROOT, initial_hashes)
    hashes = file_map(ROOT, sorted(all_names - {verification_path}))
    write_once(ROOT / verification_path, {"files": hashes})
    hashes[verification_path] = digest((ROOT / verification_path).read_bytes())
    frozen = {"format": "verislop.support019-source-freeze/1", "source_root": source_root,
              "source_files": sources, "test_sources": tests, "created_at_utc": when,
              "generation_started": False, "activation_authority": False}
    write_once(ROOT / target / "source-freeze.json", frozen)
    spec = dict(config)
    spec.update({"format": "verislop.support019-whole-current-root-qualification/1", "source_root": source_root,
                 "registered_test_ids": ids, "registered_test_count": len(ids), "test_modules": modules,
                 "test_sources": tests, "required_collection_inputs": preflight["required_collection_inputs"],
                 "task_inputs": False, "prior_pass_inheritance": False, "activation_authority": False,
                 "final_registration_status": "REGISTERED_NOT_EXECUTED", "created_utc": when})
    write_once(ROOT / target / "qualification-specification.json", spec)
    for name in ("source-freeze.json", "qualification-specification.json"):
        key = (target / name).as_posix()
        hashes[key] = digest((ROOT / key).read_bytes())
    hashes = dict(sorted(hashes.items()))
    input_root = canonical.digest_json(hashes)
    manifest = {"format": "verislop.support019-qualification-inputs/1", "source_hashes": hashes,
                "source_root": source_root, "input_root": input_root}
    write_once(ROOT / target / "qualification-inputs.json", manifest)
    prereg = {"format": "verislop.support019-final-preregistration/1", "closure_id": config["closure_id"],
              "source_root": source_root, "input_root": input_root, "created_utc": when,
              "generation_started": False, "execution_phases": config["execution_phases"],
              "external_bindings": {name: digest((ROOT / target / name).read_bytes()) for name in
                                    ("source-freeze.json", "qualification-specification.json", "qualification-inputs.json")},
              "materializer_sha256": digest(Path(__file__).read_bytes()), "actual_calls": 0,
              "activation_authority": False, "prior_pass_inheritance": False}
    write_once(ROOT / target / "preregistration.json", prereg)
    verify_map(ROOT, hashes)
    need(bootstrap.source_inventory() == sources and file_map(ROOT, list(tests)) == tests, "INPUT_MUTATION")
    print("REGISTERED_NOT_EXECUTED", target.as_posix(), source_root, input_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
