"""Finite unique-author prerequisite decision; never execute current27 or tools."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).absolute().parents[3]
GATE = ROOT / "validation/tier2-support-019-qualification-005"
OUT = Path(__file__).absolute().parent
EXPECTED_SOURCE = "sha256:9f923c5f6b9868001f302635d82a89f6608b68ad9fc8838558ee6c79336e6fc2"
EXPECTED_INPUT = "sha256:cfea045575155ed985766f07efbdb7199979e6f0200b5bb917f5a0f88485aefe"
SUCCESS_KEYS = {"markers", "field_roots", "field_eof", "field_chars"}


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def ref(path):
    assert path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(raw), "byte_count": len(raw)}


def load(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            assert key not in value, "Duplicate JSON member"
            value[key] = item
        return value
    return json.loads(path.read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def guard(hashes):
    actual = {name: ref(ROOT / name)["sha256"] for name in hashes}
    assert actual == hashes, "Frozen input mutation"
    return actual


def main():
    registration = load(OUT / "registration-before-execution.json")
    for name, expected in registration["source_guards"].items():
        assert ref(ROOT / name) == expected, "Registered evidence/source mutation"
    inputs = load(GATE / "qualification-inputs.json")
    spec = load(GATE / "qualification-specification.json")
    prereg = load(GATE / "preregistration.json")
    assert inputs["source_root"] == spec["source_root"] == prereg["source_root"] == EXPECTED_SOURCE
    assert inputs["input_root"] == prereg["input_root"] == EXPECTED_INPUT
    assert spec["closure_id"] == prereg["closure_id"] == "support019-final-current-root-005"
    frozen = inputs["source_hashes"]
    assert len(frozen) == 1538
    before = guard(frozen)
    write(OUT / "before-input-hashes.json", before)
    author_dir = GATE / "fresh-author"
    literal_ref = ref(author_dir / "literal-final.txt")
    literal = load(author_dir / "literal-final.txt")
    records = load(author_dir / "author-records.json")
    diagnostic = load(author_dir / "diagnostic-evidence.json")
    controller = load(author_dir / "controller-after-transport.json")
    native = load(author_dir / "completion-actual-tool-observation.json")
    assert type(native["exit_code"]) is int and native["exit_code"] == 0 and "session_id" not in native
    observed_process = json.loads(native["output"])
    structural = load(author_dir / "structural-admission-observation.json")
    final_observation = load(author_dir / "controller-final-observation.json")
    assert records["literal_final_ref"] == structural["literal_final_ref"] == final_observation["literal_final_ref"] == literal_ref
    assert diagnostic["literal_final_sha256"] == literal_ref["sha256"]
    assert diagnostic["report"] == literal and diagnostic["success"] is False
    assert diagnostic["trust"] == literal["failure"]["trust"] == "UNATTESTED"
    assert diagnostic["historical_cause"] == structural["historical_cause"] == final_observation["hidden_cause"] == "UNAVAILABLE"
    for filename, identity in observed_process["refs"].items():
        assert ref(author_dir / filename) == identity
    assert observed_process["refs"]["literal-final.txt"] == literal_ref
    assert observed_process["refs"]["diagnostic-evidence.json"] == ref(author_dir / "diagnostic-evidence.json")
    assert observed_process["refs"]["author-records.json"] == ref(author_dir / "author-records.json")
    assert type(structural["observed_controller_process_PID"]) is int
    assert observed_process["controller_process_PID"] == structural["observed_controller_process_PID"]
    assert observed_process["input_guard_count"] == controller["input_guard_count"] == 1538
    assert observed_process["author_success_accepted"] is structural["author_success_accepted"] is False
    assert observed_process["qualification_claims_discharged"] == structural["qualification_claims_discharged"] == []
    assert records["source_root"] == controller["source_root"] == EXPECTED_SOURCE
    assert records["input_root"] == controller["input_root"] == EXPECTED_INPUT
    assert records["spawn_count"] == controller["actual_author_spawn_count"] == 1
    assert len(records["observed_author_requests"]) == 1
    assert controller["followup_author_messages"] == 0
    assert records["replacement_author_or_resampling"] is False
    assert controller["replacement_author_or_resampling"] is False
    assert records["model_identity"] == records["semantic_consumption"] == "UNATTESTED"
    for key in ("spawn_request_ref", "spawn_result_ref"):
        assert ref(ROOT / records[key]["path"]) == records[key]
    for supplied in records["exposed_responses_refs"]:
        assert ref(ROOT / supplied["path"]) == supplied
    roots = literal["field_roots"]
    missing_roots = sorted({"/system", "/user"} - set(roots))
    extra_fields = sorted(set(literal) - SUCCESS_KEYS)
    assert roots == {} and missing_roots == ["/system", "/user"]
    assert literal["field_eof"]["/user"] is False
    assert extra_fields == ["failure"]
    author_index_path = ROOT / spec["actual_author_evidence_path"]
    assert author_index_path == author_dir / "author-index.json"
    assert author_index_path.read_bytes() == (author_dir / "author-records.json").read_bytes()
    assert ref(author_index_path) == observed_process["refs"]["author-index.json"]
    absent_outputs = [spec[key] for key in (
        "actual_process_output_index_path", "actual_equality_evidence_path",
        "actual_pure_evidence_path", "actual_channel_evidence_path")]
    for phase in spec["execution_phases"] + spec["additional_processes"]:
        absent_outputs.extend(phase["outputs"].values())
    absent_outputs = sorted(set(absent_outputs))
    assert all(not (ROOT / name).exists() for name in absent_outputs), "Current main/core output exists"
    assert not (GATE / "actual-channel/calls").exists(), "Main collector was invoked"
    assert not (GATE / "original-channel/capture-index.json").exists(), "Original channel was invoked"
    baseline_path = ROOT / "validation/tier2-support-019-qualification-003/terminal-prerequisite-block-001/report.json"
    baseline = load(baseline_path)
    claim_ids = sorted(baseline["current27_claims"])
    assert len(claim_ids) == 27
    assert claim_ids == [f"Q018-{i:02d}" for i in range(1, 19)] + [f"Q019-{i:02d}" for i in range(1, 10)]
    after = guard(frozen)
    assert before == after
    write(OUT / "after-input-hashes.json", after)
    evidence = {
        "format": "verislop.support019-terminal-prerequisite-checker-evidence/1",
        "scope": registration["scope"], "frozen_input_count": 1538,
        "all_frozen_inputs_unchanged": True,
        "before": ref(OUT / "before-input-hashes.json"),
        "after": ref(OUT / "after-input-hashes.json"),
        "literal_final": literal_ref,
        "author_records": ref(author_dir / "author-records.json"),
        "diagnostic_evidence": ref(author_dir / "diagnostic-evidence.json"),
        "diagnostic_parser": ref(ROOT / "validation/tier2-support019-author-recovery-implementation-006/diagnostic_failure_parser.py"),
        "existing_native_process_observation": ref(author_dir / "completion-actual-tool-observation.json"),
        "existing_controller_process_record": ref(author_dir / "controller-after-transport.json"),
        "existing_diagnostic_pid": structural["observed_controller_process_PID"],
        "existing_native_exit_code": native["exit_code"],
        "absent_current_main_core_outputs": absent_outputs,
        "opaque_fixture_gold_parsed_or_exposed": False,
        "current27_verifiers_run": 0, "VIEW_calls": 0, "model_calls": 0,
        "Lean_calls": 0, "qualification_authority": False, "activation_authority": False,
    }
    write(OUT / "checker-evidence.json", evidence)
    report = {
        "format": baseline["format"], "status": "BLOCKED",
        "closure_id": spec["closure_id"], "source_root": EXPECTED_SOURCE, "input_root": EXPECTED_INPUT,
        "failed_prerequisite": "UNIQUE_AUTHOR_COMPLETE_LITERAL_FINAL", "affected_claim_id": "Q019-07",
        "prerequisite_decision_scope": "Only the author-completion gate; no current27 qualification decision",
        "actual_literal_final": literal, "literal_final_sha256": literal_ref["sha256"],
        "concrete_counterexamples": [
            {"required": "field_roots has exactly /system and /user SHA256 values", "observed": roots, "missing_roots": missing_roots},
            {"required": "explicit /user EOF true before successful reconstruction", "observed": literal["field_eof"]["/user"]},
            {"required": "successful FINAL has exactly markers, field_roots, field_eof, field_chars", "observed_extra_fields": extra_fields},
        ],
        "all1538_frozen_inputs_unchanged": True, "checker_evidence_ref": ref(OUT / "checker-evidence.json"),
        "current27_claims": {claim_id: "UNRESOLVED_NOT_EXECUTED" for claim_id in claim_ids},
        "current27_passed": 0, "current27_verifiers_run": 0, "core_processes_started": 0,
        "main_collector_invocations": 0, "original_channel_invocations": 0,
        "native019_activated": False, "current_native_calls": 0, "current_task_calls": 0,
        "Tier2_task_claim": "PENDING", "independent_whole_root_admission": "NOT_EXECUTED",
        "author_spawn_count": 1, "author_followups": 0, "resampling": False, "inference_timeout": None,
        "author_reported_diagnostic": {"trust": "UNATTESTED", "stage": literal["failure"]["stage"],
                                       "observation": literal["failure"]["observation"], "success_path_authority": False},
        "hidden_failure_reason": "UNAVAILABLE", "historical_cause": "UNAVAILABLE",
        "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED",
        "finite_prerequisite_checker_processes": 2,
        "qualification_authority": False, "activation_authority": False, "task_TESTED_authority": False,
        "stop": baseline["stop"],
    }
    write(OUT / "report.json", report)
    print(json.dumps({"status": "BLOCKED", "report": ref(OUT / "report.json"),
                      "evidence": ref(OUT / "checker-evidence.json"), "frozen_inputs": 1538,
                      "all_guards_unchanged": True, "current27_passed": 0}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
