from pathlib import Path
import ast
import hashlib
import json
import os
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def read(name):
    return json.loads((HERE / name).read_bytes())

def put(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

registration = read("CONTROL_REGISTRATION_BEFORE_EXECUTION.json")
observed = {name: digest((ROOT / name).read_bytes()) for name in registration["guards"]}
assert observed and observed == registration["guards"]
actual = {f"P{i:02}": read(f"P{i:02}-actual-result.json") for i in range(1, 10)}
requests = {key: read(key + "-actual-request.json") for key in actual}
outputs = {key: json.loads(value["output"]) for key, value in actual.items()}
for key, result in actual.items():
    assert type(result["exit_code"]) is int and result["exit_code"] == (2 if key == "P07" else 0)
    assert type(result["chunk_id"]) is str and result["chunk_id"]
    assert "session_id" not in result
    assert (HERE / (key + "-actual-combined-output.raw")).read_text(encoding="utf-8") == result["output"]
for confirmation, source in (("P02", "P01"), ("P04", "P03"), ("P06", "P05"), ("P09", "P08")):
    request = requests[confirmation]
    assert request["confirmation"] == {"chunk_id": actual[source]["chunk_id"], "outer_output_intact": True}
    assert request["pending"]["result"] == actual[source]
    assert request["pending"]["view"] == requests[source]["view"]
literal = read("PUBLIC_FIXTURE_LITERAL_DEFINITION.json")
for key in ("P03", "P05", "P08"):
    value = outputs[key]
    source = literal[value["selector"][1:]]
    assert value["content"] == source[value["start_char"]:value["end_char"]]
    assert len(value["content"]) == value["content_chars"]
    assert len(value["content"].encode("utf-8")) == value["content_utf8_bytes"]
    assert len(actual[key]["output"].encode("utf-8")) <= requests[key]["view"]["output_cap_bytes"]
assert outputs["P06"]["fields"]["/system"]["field_eof"] is True
prior = outputs["P06"]["fields"]["/user"]
assert prior["field_eof"] is False and prior["next_char"] == 254
assert requests["P07"]["operation"] == "checkpoint"
assert set(requests["P07"]) == {"format", "operation", "reference", "session_path", "code"}
assert outputs["P07"]["code"] == "INVALID_RUNTIME_OPERATION"
assert outputs["P07"]["semantic_acceptance_authority"] is False
phases = ["BEFORE_SEQUENCE", "BEFORE_CHECKPOINT", "AFTER_CHECKPOINT", "AFTER_RECOVERY_VIEW", "AFTER_RECOVERY_CONFIRM"]
observations = {phase: read(phase + "-observation.json") for phase in phases}
assert all(value["guards"] == registration["guards"] and value["all_registered_guards_match"] is True for value in observations.values())
assert observations["BEFORE_SEQUENCE"]["accepted_state_exists"] is False
before = (HERE / "BEFORE_CHECKPOINT-accepted-state.raw").read_bytes()
assert before == (HERE / "AFTER_CHECKPOINT-accepted-state.raw").read_bytes()
assert before == (HERE / "AFTER_RECOVERY_VIEW-accepted-state.raw").read_bytes()
assert requests["P08"]["view"]["start_char"] == prior["next_char"]
following = outputs["P09"]["fields"]["/user"]
assert following["next_char"] == 508 and following["field_eof"] is False
after = (HERE / "AFTER_RECOVERY_CONFIRM-accepted-state.raw").read_bytes()
assert after != before

descriptor = read("OWN_REFERENCE_AND_CODE.json")
preimages = {}
for name in registration["guards"]:
    if name.startswith("synthetic_dataset/"):
        source = ROOT / name
        target = HERE / "preimages" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        preimages[name] = {"path": str(target.relative_to(ROOT)), "sha256": digest(target.read_bytes()), "binding_role": "HISTORICAL_ACTUAL_CURRENT_SOURCE_DURING_PROBE; immutable raw preimage"}
runtime_source = (ROOT / "synthetic_dataset/tools/carrier_runtime020/carrier_runtime.js").read_text()
start = runtime_source.index("function runtimeMain(request)")
end = runtime_source.index("\ntry {\n  checkpointNeed(process.argv.length", start)
(HERE / "RUNTIME_CLOSED_OPERATION_SOURCE_WITNESS.txt").write_text(runtime_source[start:end] + "\n")
assert '["view", "confirm", "hash"].includes(request.operation)' in runtime_source[start:end]
assert runtime_source[start:end].index('["view", "confirm", "hash"].includes(request.operation)') < runtime_source[start:end].index("runtimeCodeGuard(request.code)")
generator_source = (ROOT / "synthetic_dataset/tools/carrier_runtime020/compact_protocol.py").read_bytes()
tree = ast.parse(generator_source)
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
assert "runtime_checkpoint_template" not in functions
message = functions["runtime_agent_message"]
segments = generator_source.decode().splitlines(keepends=True)
(HERE / "GENERATOR_MESSAGE_SOURCE_WITNESS.txt").write_text("".join(segments[message.lineno-1:message.end_lineno]))
report = {
    "format": "verislop.bounded-generic-reproduction-report/1",
    "status": "SOURCE_INTERFACE_GAP_REPRODUCED_KNOWN_CURSOR_RECOVERY_DEMONSTRATED_UNQUALIFIED",
    "actual_report_builder_pid": os.getpid(),
    "authority": "NO_QUALIFICATION_AUTHORITY",
    "historical_cause": "UNKNOWN; neither Q007 carrier nor author state/trace was read; this generic result cannot establish its cause",
    "specification": {"path": str((HERE / "SPECIFICATION_BEFORE_FIXTURE_AND_EXECUTION.json").relative_to(ROOT)), "sha256": digest((HERE / "SPECIFICATION_BEFORE_FIXTURE_AND_EXECUTION.json").read_bytes())},
    "registration": {"path": str((HERE / "CONTROL_REGISTRATION_BEFORE_EXECUTION.json").relative_to(ROOT)), "sha256": digest((HERE / "CONTROL_REGISTRATION_BEFORE_EXECUTION.json").read_bytes())},
    "findings": [
        {"id": "C01", "resolution": "REPRODUCED", "counterexample": "Closed own checkpoint operation against partially confirmed public session", "actual_chunk_id": actual["P07"]["chunk_id"], "actual_integer_status": actual["P07"]["exit_code"], "actual_error": outputs["P07"]["code"], "zero_view": "Source operation enum rejects before state dispatch or reader invocation"},
        {"id": "C02", "resolution": "OBSERVED", "before_and_after_state_sha256": digest(before), "state_bytes": len(before), "carrier_and_source_guards_unchanged": True, "nonempty_guard_count": len(observed)},
        {"id": "C03", "resolution": "OBSERVED", "accepted_cursor_before": prior["next_char"], "explicit_recovery_view_chunk": actual["P08"]["chunk_id"], "explicit_recovery_confirm_chunk": actual["P09"]["chunk_id"], "accepted_cursor_after": following["next_char"], "system_eof": True, "user_eof": False},
        {"id": "C04", "resolution": "SOURCE_WITNESS", "meaning": "No fixed zero-VIEW read-only checkpoint/resume operation or template exists; summary is only returned by confirmation, which atomically writes accepted observations. Existing explicit known-cursor retrieval succeeds; exact replay confirmation can return a summary via a state-mutating operation. This does not prove continuation impossible."}
    ],
    "actual_runtime_results": {key: {"chunk_id": value["chunk_id"], "exit_code": value["exit_code"], "native_runtime_pid": "UNAVAILABLE_FROM_EXEC_COMMAND", "native_reader_pid": "UNAVAILABLE_FROM_EXEC_COMMAND", "separate_stderr": "UNAVAILABLE_FROM_COMBINED_OUTPUT", "result_ref": str((HERE / (key + "-actual-result.json")).relative_to(ROOT)), "result_sha256": digest((HERE / (key + "-actual-result.json")).read_bytes())} for key, value in actual.items()},
    "observations": {phase: {"actual_observer_pid": value["actual_observer_pid"], "accepted_state_sha256": value.get("accepted_state_sha256"), "guard_count": len(value["guards"])} for phase, value in observations.items()},
    "preimages": preimages,
    "accepted_state_after": {"sha256": digest(after), "bytes": len(after)},
    "limitations": "Partial unrelated public generic session only; Unicode literal independently retained but the two partial user slices contain ASCII only. No whole-field HASH, semantic consumption, proof, TESTED, lifecycle, current27, admission, native activation, model, author continuation, hidden/task/expected data, or historical causal authority. No additional probes or retries."
}
put("REPORT.json", report)
files = {str(path.relative_to(ROOT)): {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size} for path in sorted(HERE.rglob("*")) if path.is_file() and path.name not in ("hash-manifest.json", "SEAL.sha256")}
inputs = {name: {"sha256": sha, "bytes": Path(name).stat().st_size} for name, sha in registration["guards"].items() if name.startswith("/usr/bin/")}
put("hash-manifest.json", {"format": "verislop.source-reproduction-manifest/1", "status": report["status"], "files": files, "inputs": inputs, "mutable_live_source_input_policy": "Historical actual guarded observations plus immutable raw preimages; no live production old hash asserted current after later installation", "qualification_authority": False})
manifest_hash = hashlib.sha256((HERE / "hash-manifest.json").read_bytes()).hexdigest()
(HERE / "SEAL.sha256").write_text(manifest_hash + "  hash-manifest.json\n")
print(json.dumps({"actual_report_builder_pid": os.getpid(), "report_sha256": digest((HERE / "REPORT.json").read_bytes()), "manifest_sha256": "sha256:" + manifest_hash, "seal_sha256": digest((HERE / "SEAL.sha256").read_bytes()), "own_files": len(files), "stable_inputs": len(inputs), "status": report["status"]}), flush=True)
