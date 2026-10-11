from pathlib import Path
import hashlib, importlib.util, json, os, re

ROOT = Path("/home/augustus/VeriSlop_CLI")
Q = ROOT / "validation/tier2-support-019-qualification-007"
E = Q / "fresh-author"
PARSER = ROOT / "validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py"
PARSER_SHA = "sha256:d93415f13d9179b351ae1aabe57049764b3e607b97491c47f88fdd09144352dd"
ACTUAL_AUTHOR = "/root/support019_author_controller/support021_carrier_author_007"
def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()
def load(path):
    return json.loads(path.read_bytes().decode("utf-8", "strict"))
def save(path, value):
    assert not path.exists(), str(path)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
def ref(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(data), "byte_count": len(data)}
before = load(E / "controller-before-transport.json")
inputs = load(Q / "qualification-inputs.json")
spec = load(Q / "qualification-specification.json")
contract = spec["adapters"]["author_contract"]
observed = {}
mismatches = []
for name, expected in inputs["source_hashes"].items():
    actual = sha((ROOT / name).read_bytes())
    observed[name] = actual
    if actual != expected or actual != before["observed_input_hashes"].get(name):
        mismatches.append({"path": name, "expected": expected, "before": before["observed_input_hashes"].get(name), "after": actual})
external = {}
for name, expected in before["external_bindings"].items():
    actual = sha((Q / name).read_bytes())
    external[name] = actual
    if actual != expected:
        mismatches.append({"path": str((Q / name).relative_to(ROOT)), "expected": expected, "after": actual})
request = load(E / "spawn-request.json")
response = load(E / "spawn-result.json")
literal = (E / "literal-final.txt").read_bytes()
wrapper = load(E / "exposed-responses/001-final-delivered.json")
assert len(observed) == before["frozen_input_count"] == 6880
assert not mismatches, mismatches
assert type(response) is dict and set(response) == {"task_name"}
assert response["task_name"] == ACTUAL_AUTHOR
assert request["task_name"] == "support021_carrier_author_007"
assert request["model"] == "gpt-6.1-sol" and request["fork_turns"] == "none"
assert request["message"].encode("utf-8", "strict") == (ROOT / contract["submitted_message_path"]).read_bytes()
assert wrapper["payload"].encode("utf-8", "strict") == literal
assert wrapper["message_type"] == "FINAL_ANSWER" and wrapper["sender"] == ACTUAL_AUTHOR
assert not (E / "author-index.json").exists()
assert sha(PARSER.read_bytes()) == PARSER_SHA == inputs["source_hashes"][str(PARSER.relative_to(ROOT))]
module_spec = importlib.util.spec_from_file_location("current_frozen_evidence_only_diagnostic_parser", PARSER)
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)
diagnostic = {"format": "verislop.support021-author-diagnostic-parser-observation/1",
              "parser_ref": ref(PARSER), "literal_final_ref": ref(E / "literal-final.txt"),
              "fixture_failure_allowed": True, "fixture_permission_basis": "CURRENT_ROOT_EXPLICIT_REGISTERED_GATE_FAILURE_BRANCH",
              "trust": "UNATTESTED", "success_authority": False, "independent_reproduction_executed": False}
try:
    diagnostic["parsed"] = module.parse_failure(literal, fixture_failure_allowed=True, exposed_references=())
    diagnostic["schema_valid"] = True
except module.DiagnosticSchemaError as error:
    diagnostic["schema_valid"] = False
    diagnostic["error_type"] = type(error).__name__
    diagnostic["error_literal"] = str(error)
save(E / "diagnostic-parser-observation.json", diagnostic)
after = {"format": "verislop.support021-author-controller-after-transport/1",
         "closure_id": before["closure_id"], "source_root": before["source_root"], "input_root": before["input_root"],
         "observed_input_hashes": observed, "external_bindings": external, "frozen_input_count": len(observed),
         "input_hashes_unchanged": True, "binding_hashes_unchanged": True, "guard_mismatches": mismatches,
         "actual_author_spawn_count": 1, "actual_author_followup_count": 0,
         "replacement_or_resampling": False, "author_index_created": False,
         "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED",
         "hidden_native_agent_id": "UNAVAILABLE", "author_PID": "UNAVAILABLE",
         "author_tokens": "UNAVAILABLE", "author_CPU": "UNAVAILABLE", "author_peak_memory": "UNAVAILABLE",
         "actual_exposed_model_response_count": 1, "controller_process_pid": os.getpid(),
         "exposed_author_tool_trace": "UNAVAILABLE", "qualification_claim": False}
save(E / "controller-after-transport.json", after)
spawn_request_ref = ref(E / "spawn-request.json")
spawn_result_ref = ref(E / "spawn-result.json")
descriptor = {
    "format": "verislop.support019-single-fresh-author-evidence/1", "status": "OBSERVED",
    "closure_id": before["closure_id"], "source_root": before["source_root"], "input_root": before["input_root"],
    "spawn_count": 1, "requested_model": "gpt-6.1-sol", "fork_turns": "none",
    "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED",
    "fresh_fixture": contract["fresh_fixture"],
    "submitted_message_ref": ref(ROOT / contract["submitted_message_path"]),
    "expected_literal_message_ref": contract["expected_literal_message_ref"],
    "evaluator_expectations_ref": contract["evaluator_expectations_ref"],
    "spawn_request_ref": spawn_request_ref, "spawn_result_ref": spawn_result_ref,
    "author_agent_id": ACTUAL_AUTHOR,
    "observed_author_requests": [{"spawn_request_ref": spawn_request_ref, "spawn_result_ref": spawn_result_ref, "agent_id": ACTUAL_AUTHOR}],
    "literal_final_ref": ref(E / "literal-final.txt"),
    "exposed_responses_refs": [ref(E / "exposed-responses/001-final-delivered.json")],
    "evaluator_expectations_sent_to_author": False, "replacement_author_or_resampling": False
}
save(E / "author-records.json", descriptor)
final = json.loads(literal.decode("utf-8", "strict"))
summary = {"format": "verislop.support021-author-controller-recording-summary/1",
           "controller_process_pid": os.getpid(), "author_records_ref": ref(E / "author-records.json"),
           "before_ref": ref(E / "controller-before-transport.json"), "after_ref": ref(E / "controller-after-transport.json"),
           "literal_final_ref": ref(E / "literal-final.txt"), "exposed_response_refs": descriptor["exposed_responses_refs"],
           "diagnostic_parser_observation_ref": ref(E / "diagnostic-parser-observation.json"),
           "schema_valid": diagnostic["schema_valid"], "diagnostic_parser_error": diagnostic.get("error_literal"),
           "spawn_count": 1, "followup_count": 0, "frozen_inputs_unchanged": len(observed),
           "author_index_created": False, "literal_final_key_count": len(final),
           "field_eof_reported": final["field_eof"], "field_roots_reported": final["field_roots"],
           "gate_completion": "UNSUCCESSFUL_LITERAL_FINAL", "qualification_claim": False,
           "independent_error_reproduction_executed": False, "hidden_cause": "UNAVAILABLE"}
save(E / "structural-admission-observation.json", summary)
print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
