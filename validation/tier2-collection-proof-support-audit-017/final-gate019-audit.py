"""Finite read-only audit of the seven preregistered claims; never runs Lean/tests/models."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verislop import canonical, verifiers
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap

AUDIT = Path(__file__).resolve().parent
GATE = ROOT / "validation/tier2-native-boundary-gate-019"
CAPTURE = ROOT / "validation/tier2-proof-support-017-collection-design/qualification/frozen-attempt-egfasmab"
ANNEX = CAPTURE.parent / "retained-check-c7wcbpdr"
PKG = CAPTURE / "package"
checks = []
sha = lambda p: "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())

def check(number, label, condition):
    checks.append({"claim": f"AUD017-{number:02}", "check": label, "matches": bool(condition)})

def unchanged(mapping):
    return all((ROOT / n).is_file() and not (ROOT / n).is_symlink() and sha(ROOT / n) == h for n, h in mapping.items())

binding = load(AUDIT / "final-frozen-binding.json")
check(1, "All final evidence/verifier inputs equal the immutable before-audit binding", unchanged(binding["files"]))
plan = load(AUDIT / "plan.json")
spec = load(GATE / "qualification-specification.json")
manifest = load(GATE / "qualification-inputs.json")
freeze = load(GATE / "source-freeze.json")
prereg = load(AUDIT / "gate019-driver-preregistration.json")
invocation = load(GATE / "invocation.json")
result = load(GATE / "run-result.json")
receipt = load(GATE / "actual-process-receipt.json")
preflight = load(GATE / "preflight-process-receipt.json")
check(1, "Exactly the original seven claims and unchanged acceptance predicates", spec["audit_claims"] == plan["claims"] and len(plan["claims"]) == 7)
check(1, "Current driver/specification exactly match final independent preregistration", sha(GATE / "gate.py") == prereg["driver_script_sha256"] == invocation["driver_script_sha256"] and sha(GATE / "qualification-specification.json") == prereg["qualification_specification_sha256"] == invocation["qualification_specification_sha256"])
check(1, "Actual final gate identities supplied by root", sha(GATE / "actual-process-receipt.json") == "sha256:6cdd23e3066eb6762b32e96d817973f4e4826d8fd401ee02624615c7882a9403" and sha(GATE / "run-result.json") == "sha256:0fec428a78fd52f435214134bf135a66f9d50310909ba7faca78a8aa113a5ddb")
check(1, "All415 qualification input bytes and canonical root match", len(manifest["source_hashes"]) == 415 and unchanged(manifest["source_hashes"]) and canonical.digest_json(manifest["source_hashes"]) == manifest["selected_input_root"])
production = bootstrap.source_inventory(ROOT)
tests = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / "tests").rglob("*.py"))}
check(1, "Exact current full production inventory241 matches before/after roots", production == freeze["source_files"] and len(production) == 241 and canonical.digest_json(production) == freeze["source_root"] == result["source_root_before"] == result["source_root_after"])
check(1, "Exact current full test inventory127 matches before/after roots", tests == load(GATE / "test-sources.json") == result["test_sources"] and len(tests) == 127 and canonical.digest_json(tests) == result["test_root_before"] == result["test_root_after"] and result["test_source_count_before"] == result["test_source_count_after"] == 127)
ids = prereg["registered_test_ids"]
check(1, "Actual loaded/executed exact98 unique ordered suite matches all registrations", len(ids) == len(set(ids)) == 98 and all(x["registered_test_ids"] == ids for x in (manifest, invocation, result, spec["registered_suite"])) and all(x["test_modules"] == prereg["test_modules"] for x in (manifest, invocation, result, spec["registered_suite"])) and all(result[x] == 98 for x in ("expected_test_count", "registered_test_count", "unique_test_count", "tests_run")))
stderr = (GATE / "gate.stderr.log").read_text()
actual_ids = []
for line in stderr.splitlines():
    match = re.fullmatch(r"(test_\w+) \((tests\.[\w.]+)\) \.\.\. ok", line)
    if match:
        actual_ids.append(match[2] + "." + match[1])
check(1, "Actual completed unittest log independently names all98 successful ordered tests", actual_ids == ids and "Ran 98 tests" in stderr and stderr.rstrip().endswith("OK"))
check(1, "Actual terminal process rc0 and zero failures/errors/skips/expected failures/unexpected successes", receipt["actual_returncode"] == 0 and receipt["actual_session_id"] == 93194 and result["status"] == "PASS" and all(result[x] == 0 for x in ("errors", "failures", "skipped", "expected_failures", "unexpected_successes")))
check(1, "Actual result binds unchanged full input inventories and no prior PASS inheritance", all(result[x] is True for x in ("qualification_inputs_unchanged", "source_unchanged", "test_inputs_unchanged", "failfast", "collection_module_first")) and result["prior_pass_inheritance"] is False and result["fresh_model_calls"] == 0)
check(1, "All terminal process log byte/hash observations reconcile", all((GATE / n).stat().st_size == row["bytes"] and sha(GATE / n) == "sha256:" + row["sha256"] for n, row in receipt["logs"].items()))
check(1, "Frozen invocation binds exact manifest/source root and no task inputs", invocation["qualification_inputs_hash"] == sha(GATE / "qualification-inputs.json") and manifest["engineering_freeze_hash"] == sha(GATE / "source-freeze.json") and invocation["source_root"] == freeze["source_root"] and invocation["task_inputs_supplied"] is False)
check(1, "Actual nonexecuting preflight/edit-stop precedes source freeze and invocation", preflight["observed_exit_code"] == 0 and preflight["tests_executed"] == 0 and preflight["production_and_test_edits_stopped"] is True and preflight["independent_preregistration_sha256"] == sha(AUDIT / "gate019-driver-preregistration.json") and datetime.fromisoformat(preflight["completed_at_utc"]) < datetime.fromisoformat(freeze["created_at_utc"]) < datetime.fromisoformat(invocation["started_at_utc"]) < datetime.fromisoformat(receipt["observed_completed_at_utc"]))

prep01 = load(AUDIT / "gate019-prepared-observations-01.json")
prep23 = load(AUDIT / "gate019-prepared-observations-02-03.json")
draft = load(AUDIT / "gate019-prepared-observations-04-06.json")
correction1 = load(AUDIT / "gate019-prepared-observations-04-06-correction-001.json")
correction2 = load(AUDIT / "gate019-prepared-observations-04-06-correction-002.json")
check(1, "All76 prepared original freeze comparisons remain true", prep01["all_prepared_comparisons_match"] and prep01["comparison_count"] == 76 and unchanged(prep01["evidence_bindings"]))
for number in (2, 3):
    check(number, "All231 registered current catalog/name comparisons remain true with exact retained hashes", len(prep23["comparisons"]) == 231 and all(x["matches"] for x in prep23["comparisons"]) and not prep23["concrete_findings"] and unchanged(prep23["evidence_hashes"]))
    check(number, "Prepared reader is exact executed immutable producer", sha(AUDIT / "prepare-gate019-claims-02-03.py") == prep23["producer_sha256"])
corrections = {x["replaces_check"]: x for x in correction1["corrections"]}
check(4, "All12 original representation mismatches preserved and exactly corrected", len(corrections) == 12 and set(corrections) == {x["check"] for x in draft["new_concrete_or_reader_gaps"]} and correction1["initial_draft_sha256"] == sha(AUDIT / "gate019-prepared-observations-04-06.json") and correction2["correction001_sha256"] == sha(AUDIT / "gate019-prepared-observations-04-06-correction-001.json") and all(x["match"] for x in corrections.values()) and correction2["unresolved_required_preparation_findings"] == 0)
for number in (4, 5, 6):
    rows = [x for x in draft["comparisons"] if x["claim"] == f"{number:02}"]
    check(number, "Exact registered prepared comparisons reconcile against frozen unchanged evidence", bool(rows) and all(corrections[x["check"]]["match"] if x["check"] in corrections else x["match"] for x in rows) and unchanged(draft["evidence_bindings"]))
check(4, "Actual accepted Lean type reifications link exact frozen frontend/reifier implementations", correction2["all348_prepared_comparisons_resolved_with_no_target_gap"] and correction2["current_reifier_executed_against_actual_exported_Lean_types"] and unchanged(correction2["current_frozen_production_rule_bindings"]) and correction2["actual_accepted_kernel_export_sha256"] == sha(ROOT / correction2["actual_accepted_kernel_export_path"]))
capture = load(CAPTURE / "capture.json")
captured = {p.relative_to(CAPTURE).as_posix(): sha(p) for p in sorted(CAPTURE.rglob("*")) if p.is_file() and p.name != "capture.json"}
check(4, "Complete fresh1340 capture plus copied415 registered preimages remain exact", captured == capture["files"] and len(captured) == 1340 and capture["source_hashes"] == manifest["source_hashes"] and {n: sha(CAPTURE / "registered-sources" / n) for n in manifest["source_hashes"]} == manifest["source_hashes"])
stdout = (GATE / "gate.stdout.log").read_text()
check(4, "Actual final gate printed the designated fresh collection and retained captures", str(CAPTURE) in stdout and str(ANNEX) in stdout)
READABLE = ROOT / "validation/tier2-readable-view-qualification/selected-pipeline-e__9pwj6"
readable_capture = load(READABLE / "capture.json")
portability = load(ROOT / "validation/tier2-readable-view-qualification/pipeline-portability-45_0rwi9/receipt.json")
check(1, "Current019 additional readable capture binds exact current generic preimages and complete retained inventory", all(manifest["source_hashes"].get(n) == h for n, h in readable_capture["source_hashes"].items()) and all(sha(READABLE / n) == h for n, h in readable_capture["files"].items()) and str(READABLE) in stdout)
check(6, "Current019 readable portability observation identifies the same actual retained capture", portability["capture_hash"] == sha(READABLE / "capture.json") and portability["capture"] == READABLE.relative_to(ROOT).as_posix() and portability["original_temporary_root_removed"] is True and portability["published_check"] == "PASS" and portability["mechanical_status"] == "VERIFIED")
wrong = load(CAPTURE / "concrete-wrong-source-control.json")
check(5, "Optional ground replay remains unresolved/nonqualification, separate from actual universal wrong-source proof rejection", wrong["status"] == "UNRESOLVED_REPLAY_BOUNDARY" and wrong["qualification"] is False)
snapshot = load(CAPTURE / "mechanical-snapshot.json")
report = load(PKG / "report.json")
engineering = load(GATE / "engineering-validation.json")
engineering_receipt = load(GATE / "engineering-process-receipt.json")
check(7, "Actual engineering-record process succeeded and binds designated fresh package and exact record", engineering_receipt["actual_returncode"] == 0 and engineering_receipt["record_sha256"] == sha(GATE / "engineering-validation.json") == "sha256:7a2037fda50ac5515159cab5bdfd48f013d9c2a5fdf15da28d348fda92f7e11d" and engineering_receipt["package"] == str(PKG) and engineering_receipt["fresh_model_calls"] == 0)
# Registered engineering_record only reconstructs retained observations; no kernel/test/model rerun.
actual_engineering = bootstrap.engineering_record(PKG, GATE / "source-freeze.json")
check(7, "Current registered engineering-record reconstruction equals every actual record field", actual_engineering == engineering and len(engineering["package_files"]) == 788 and engineering["package_files_root"] == canonical.digest_json(engineering["package_files"]))
check(6, "Final record and report bind identical actual fresh A/B closure and determinate outputs", engineering["builds"] == snapshot["builds"] == report["builds"] and engineering["determinism"] == snapshot["determinism"] == report["determinism"] and engineering["closure_root"] == snapshot["closure_root"] == report["roots"]["closure_input_root"] and snapshot["builds"][0]["outputs"] == snapshot["builds"][1]["outputs"] and not snapshot["determinism"]["mismatches"])
claims = {x["claim_id"]: x for x in snapshot["claims"]}
required = [x for x in snapshot["claims"] if x["required"]]
check(7, "All62 actual required closure claims PASS with explicit registered provenance", len(required) == 62 and required == engineering["required_claim_observations"] and all(x["outcome"] == "PASS" and x["input_root"] and x["verifier"] and x["evidence_refs"] for x in required))
evidence_gaps = []
for row in required:
    if any(p not in claims or claims[p]["outcome"] != "PASS" for p in row["premises"]):
        evidence_gaps.append([row["claim_id"], "premise"])
    for ref in row["evidence_refs"]:
        evidence = load(PKG / "evidence" / (ref.split(":", 1)[1] + ".json"))
        if evidence["status"] != "PASS" or evidence["verifier_id"] != row["verifier"] or evidence["verifier_hash"] != verifiers.verifier_hash(evidence["verifier_id"]) or evidence["input_root_hash"] != row["input_root"] or sha(PKG / evidence["raw_result_ref"]) != evidence["raw_result_hash"] or not evidence["trusted_dependencies"]:
            evidence_gaps.append([row["claim_id"], ref])
check(7, "Every required evidence/raw result/current verifier hash/root/premise is bound without orphan claims", not evidence_gaps)
tested = [x for x in snapshot["claims"] if x["claim_id"].startswith("TESTED:")]
check(7, "Optional TESTED remains PENDING/NOT_APPLICABLE and is never qualification authority", all(not x["required"] and x["outcome"] in ("PENDING", "NOT_APPLICABLE") for x in tested) and snapshot["parameters"]["require_tests"] is False and snapshot["backend"]["testing"] == "unsupported")
check(7, "Final machine report has no warnings/blockers/infrastructure errors and only restricted-source endpoint", report["mechanical_status"] == report["terminal_status"] == "VERIFIED" and not report["warnings"] and not report["blocking_reasons"] and not report["infrastructure_errors"] and report["endpoint"]["established"] == snapshot["endpoint"] == "restricted_source" and not snapshot["dependencies"]["undeclared"])
surface_text = json.dumps(report["surfaces"])
check(7, "Actual boundary declares toolchain/reifier/controller/axioms/OS trust and compiler/Python/resource/NL exclusions", all(x in surface_text for x in ("pinned toolchain", "reifier", "hashing", "logical axioms", "operating system", "CPython", "native executable", "machine-code", "physical time", "natural-language-to-contract")))
prior = []
for attempt in ("017", "018"):
    old = ROOT / f"validation/tier2-native-boundary-gate-{attempt}"
    old_result = load(old / "run-result.json")
    old_receipt = load(old / "actual-process-receipt.json")
    actual_rc = old_receipt.get("actual_returncode", old_receipt.get("observed_exit_code"))
    observation = load(AUDIT / f"gate{attempt}-failure-observations.json")
    check(7, f"Failed gate{attempt} retained as failure with no qualification inheritance", old_result["status"] == "FAIL" and old_result["tests_run"] == 98 and old_result["failures"] == 1 and actual_rc == 2 and observation["qualification"] is False)
    prior.append({"attempt": "gate" + attempt, "status": "FAIL", "actual_returncode": actual_rc, "qualification_authority": False, "finding": observation.get("finding", observation.get("actual_failure")), "receipt_sha256": sha(old / "actual-process-receipt.json")})
incident = load(ROOT / "validation/tier2-native-boundary-gate-018/auxiliary-checkpoint-read-error.json")
postlaunch = load(ROOT / "validation/tier2-native-boundary-gate-018/post-launch-provenance-observation.json")
check(7, "Prior auxiliary rc1 KeyError truthfully retained without inventing a preexecution checkpoint", incident["actual_auxiliary_command_exit_code"] == 1 and incident["checkpoint_written_before_execution"] is False and postlaunch["observation_is_preexecution_checkpoint"] is False and postlaunch["auxiliary_read_error_sha256"] == sha(ROOT / "validation/tier2-native-boundary-gate-018/auxiliary-checkpoint-read-error.json"))
check(1, "After-audit exact evidence/input bytes still equal before-audit binding", unchanged(binding["files"]) and bootstrap.source_inventory(ROOT) == production and {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / "tests").rglob("*.py"))} == tests)
claim_results = []
for number, claim in enumerate(plan["claims"], 1):
    applicable = [x for x in checks if x["claim"] == f"AUD017-{number:02}"]
    passed = bool(applicable) and all(x["matches"] for x in applicable)
    claim_results.append({"id": claim["id"], "registered_pass_predicate": claim["pass"], "status": "PASS" if passed else "BLOCKED", "observations": applicable})
    print(claim["id"], "PASS" if passed else "BLOCKED", flush=True)
status = "VERIFIED" if all(x["status"] == "PASS" for x in claim_results) else "BLOCKED"
final = {"format": "verislop.independent-seven-claim-audit/1", "audit_id": plan["audit_id"], "qualification_attempt": "gate019", "status": status, "qualification": status == "VERIFIED", "evaluated_at_utc": datetime.now(timezone.utc).isoformat(), "plan_sha256": sha(AUDIT / "plan.json"), "claims_sha256": canonical.digest_json(plan["claims"]), "verifier_sha256": sha(Path(__file__)), "final_frozen_binding_sha256": sha(AUDIT / "final-frozen-binding.json"), "qualification_input_manifest_sha256": sha(GATE / "qualification-inputs.json"), "current_production_root": freeze["source_root"], "current_full415_input_root": manifest["selected_input_root"], "test_root": result["test_root_after"], "gate_actual_returncode": receipt["actual_returncode"], "gate_tests_run": 98, "claims": claim_results, "concrete_unresolved_required_findings": [x for x in checks if not x["matches"]], "retained_preparation_corrections": {"original348_sha256": sha(AUDIT / "gate019-prepared-observations-04-06.json"), "preserved_reader_representation_mismatches": 12, "correction001_sha256": sha(AUDIT / "gate019-prepared-observations-04-06-correction-001.json"), "correction002_sha256": sha(AUDIT / "gate019-prepared-observations-04-06-correction-002.json"), "target_or_predicate_mutations": False}, "prior_failed_attempts": prior, "auxiliary_incident": {"actual_exit_code": 1, "preexecution_checkpoint_written": False, "qualification_authority": False, "observation_path": "validation/tier2-native-boundary-gate-018/post-launch-provenance-observation.json"}, "optional_wrong_source_ground_replay": {"status": wrong["status"], "qualification": False, "kernel_false_proved": False, "tested_claim": False, "interpretation": "Unresolved optional ground replay. Required semantically wrong universal proof was actually rejected by Lean; this unresolved probe supplies no FALSE/PASS/TESTED authority."}, "trust": {"actual_catalog_axioms": prep23["catalog"]["rows"], "actual_contract_axioms": report["axioms"], "actual_report_surfaces": report["surfaces"], "actual_mechanical_boundary": snapshot["boundary"], "explicit_auditor_tcb": ["Pinned Lean kernel/elaborator/standard library and imported toolchain oleans", "Registered exporter, replay/controller, reifier, DSL/goal derivation and codecs", "CPython interpreter/byte compiler running the supervisor and this read-only auditor", "Launcher, bubblewrap, Linux/OS, SHA-256/canonicalization and hardware", "Declared logical axiom uses and recorded natural-language interpretation"]}, "assurance_boundary": "Only these seven frozen generic engineering predicates for the exact restricted VSCore0.3 source semantics. No task/benchmark guarantee, Python execution equivalence, extraction/compiler-chain/machine-code correctness, physical-resource claim, unlisted property, future revision or proof of natural-language interpretation.", "reviewer_execution": {"tests": 0, "lean_builds": 0, "model_calls": 0, "fixture_generation": False, "registered_engineering_reconstruction": "Read-only actual retained-artifact validation; no kernel rerun."}, "finite_stop": "All seven preregistered claims evaluated; no scope expansion."}
out = AUDIT / "final-gate019-audit-report.json"
with out.open("xb") as f:
    f.write(canonical.dumps(final))
out.chmod(0o444)
print(json.dumps({"status": status, "report": out.relative_to(ROOT).as_posix(), "report_sha256": sha(out), "comparison_count": len(checks), "required_unresolved": len(final["concrete_unresolved_required_findings"])}), flush=True)
sys.exit(0 if status == "VERIFIED" else 2)
