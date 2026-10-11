"""Finite preregistered support021 source controls; no runtime/model/task calls."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import os

ROOT = Path("/home/augustus/VeriSlop_CLI")
HERE = Path(__file__).resolve().parent
OLD = ROOT / "validation/tier2-support019-author-recovery-implementation-006"
INSTALLED = ROOT / "synthetic_dataset/tools/carrier_runtime020"
HELPER = ROOT / "validation/tier2-carrier-runtime-support-020-integration-001/compact_author_protocol_reconstruction.py"
MAX = 2**53 - 1
SUCCESS = {"markers", "field_roots", "field_eof", "field_chars"}

def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()

def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8", "strict")

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def definitions(raw):
    return {node.name: node for node in ast.parse(raw).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}

def dump(node):
    return ast.dump(node, include_attributes=False)

def erase_functions(raw, names):
    tree = ast.parse(raw)
    for index, node in enumerate(tree.body):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            tree.body[index] = ast.Expr(value=ast.Constant(value=node.name))
    return dump(tree)

def fails(function, error=None):
    try:
        function()
    except Exception as observed:
        if error is not None:
            assert str(observed) == error, (str(observed), error)
        return {"type": type(observed).__name__, "literal": str(observed)}
    raise AssertionError("EXPECTED_REJECTION_NOT_OBSERVED")

def diagnostic(view):
    operation = {"chunk_id": "SYNTHETIC_GENERIC_CONTROL_NOT_ACTUAL",
                 "selector": view["selector"], "start_char": view["start_char"],
                 "output_cap_bytes": view["output_cap_bytes"],
                 "metadata_reserve_bytes": view["metadata_reserve_bytes"]}
    return {"markers": [], "field_roots": {}, "field_eof": {"/system": True, "/user": False},
            "field_chars": {"/system": 0, "/user": 0},
            "failure": {"format": "verislop.author-observed-failure/0.1", "trust": "UNATTESTED",
                        "stage": "NEXT_USER", "operation": operation,
                        "observation": {"kind": "literal", "source": "OWN_VISIBLE_PROTOCOL_STATE",
                                        "text": "SYNTHETIC attempted-input error; not an actual tool observation",
                                        "scope": "complete"},
                        "reproduction": {"template": "NEXT", "view": view, "confirmation": None,
                                         "own_input_literal": None,
                                         "expected_observed_error_literal": "SYNTHETIC attempted-input error",
                                         "availability": "PROVIDED"},
                        "self_critique": {"violated_check": None, "own_attempted_retry": None,
                                          "observed_retry_error_literal": None, "recovery": "UNAVAILABLE"}}}

def view(**changes):
    result = {"operation": "field", "selector": "/user", "start_char": 0,
              "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
    result.update(changes)
    return result

def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")

def main():
    registration = json.loads((HERE / "CONTROL_EXECUTION_REGISTRATION.json").read_bytes())
    contract = json.loads((HERE / "CONTROL_CONTRACT_BEFORE_SOURCE.json").read_bytes())
    run = HERE / "controls-run-001"
    assert not run.exists()
    run.mkdir()
    guards = registration["source_guards"]
    before = {name: sha((ROOT / name).read_bytes()) for name in guards}
    assert before and before == guards
    compact_raw = (HERE / "compact_protocol.py").read_bytes()
    old_compact_raw = (INSTALLED / "compact_protocol.py").read_bytes()
    parser_raw = (HERE / "diagnostic_failure_parser.py").read_bytes()
    old_parser_raw = (OLD / "diagnostic_failure_parser.py").read_bytes()
    compact = load_module("support021_candidate_compact", HERE / "compact_protocol.py")
    old_compact = load_module("support021_preimage_compact", INSTALLED / "compact_protocol.py")
    parser = load_module("support021_candidate_evidence_only_parser", HERE / "diagnostic_failure_parser.py")
    old_parser = load_module("support021_preimage_evidence_only_parser", OLD / "diagnostic_failure_parser.py")
    helper = load_module("support021_independent_source_reconstructor", HELPER)
    controls = []
    fidelity = {}
    def checked(ident, procedure):
        evidence = procedure()
        controls.append({"id": ident, "status": "PASS", "evidence": evidence})
    checked("C01", lambda: {"source_guards": len(before), "before_match": True})

    def producer_fidelity():
        before_defs, after_defs = definitions(old_compact_raw), definitions(compact_raw)
        changed = sorted(name for name in before_defs if dump(before_defs[name]) != dump(after_defs[name]))
        assert changed == ["runtime_agent_message"]
        assert erase_functions(old_compact_raw, changed) == erase_functions(compact_raw, changed)
        old = old_compact_raw.decode()
        anchor = "FIRST requests inventory; NEXT requests one explicit closed VIEW per call. "
        expected = old.replace(anchor, anchor + contract["allowed_message_insertion"]["bounds"], 1)
        expected = expected.replace("Retry the SAME explicit cursor with 4096 cap/2048 reserve when appropriate. ",
                                    contract["allowed_message_insertion"]["recovery"], 1)
        assert expected.encode() == compact_raw
        fidelity["producer_changed_functions"] = changed
        fidelity["producer_changes_only_registered_prose"] = True
        return {"changed_functions": changed, "registered_literal_delta_exact": True}
    checked("C02", producer_fidelity)

    def preserved_runtime():
        for name in ("reader.py", "carrier_runtime.js"):
            assert (HERE / name).read_bytes() == (INSTALLED / name).read_bytes()
        return {"reader_byte_equal": True, "runtime_byte_equal": True}
    checked("C03", preserved_runtime)

    def parser_fidelity():
        before_defs, after_defs = definitions(old_parser_raw), definitions(parser_raw)
        changed = sorted(name for name in before_defs if dump(before_defs[name]) != dump(after_defs[name]))
        assert changed == ["_operation", "_view"]
        assert erase_functions(old_parser_raw, changed) == erase_functions(parser_raw, changed)
        class NumericValidation(ast.NodeTransformer):
            def visit_Call(self, node):
                node = self.generic_visit(node)
                if isinstance(node.func, ast.Name) and node.func.id == "_integer":
                    node.keywords = [value for value in node.keywords if value.arg not in ("low", "high")]
                return node
            def visit_If(self, node):
                # Remove only the predecessor's numeric reserve<cap check.
                if len(node.body) == 1 and isinstance(node.body[0], ast.Expr):
                    call = node.body[0].value
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_need":
                        exact = ast.parse('_need(value["metadata_reserve_bytes"] < value["output_cap_bytes"], "INVALID_OWN_RESERVE")').body[0].value
                        if dump(call) == dump(exact):
                            assert dump(node.test) == dump(ast.parse('value["output_cap_bytes"] is not None', mode="eval").body)
                            assert not node.orelse
                            return None
                return self.generic_visit(node)
        for name in changed:
            normal_old = NumericValidation().visit(copy.deepcopy(before_defs[name]))
            normal_new = NumericValidation().visit(copy.deepcopy(after_defs[name]))
            assert dump(normal_old) == dump(normal_new), name
            calls = [node for node in ast.walk(after_defs[name]) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Name) and node.func.id == "_integer"]
            assert len(calls) == 3
            for call in calls:
                assert len(call.keywords) == 1 and call.keywords[0].arg == "low"
                assert dump(call.keywords[0].value) == dump(ast.parse("-MAX_SAFE_INTEGER", mode="eval").body)
        assert parser.SUCCESS_KEYS == old_parser.SUCCESS_KEYS == SUCCESS
        fidelity["parser_changed_functions"] = changed
        fidelity["all_other_parser_ASTs_exact"] = True
        return {"changed_functions": changed, "numeric_domain_only": True, "success_key_set_preserved": True}
    checked("C04", parser_fidelity)

    def capture_fidelity():
        for name in ("bootstrap_tier2_carrier_view.py", "capture-amendment-003/collector_templates.py"):
            assert (HERE / name).read_bytes() == (OLD / name).read_bytes()
        factory = load_module("support021_exact_capture_factory", HERE / "capture-amendment-003/collector_templates.py")
        assert sha(factory.CANDIDATE_PATH.read_bytes()) == factory.CANDIDATE_SHA256
        assert factory.CANDIDATE_PATH == HERE / "bootstrap_tier2_carrier_view.py"
        fidelity["capture_factory_changed_functions"] = []
        return {"factory_byte_equal": True, "legacy_source_byte_equal": True, "relative_source_pin_match": True}
    checked("C05", capture_fidelity)

    reference = {"path": "/tmp/UNRELATED_GENERIC_SUPPORT021.json", "sha256": "sha256:" + "1"*64,
                 "request_sha256": "sha256:" + "2"*64}
    code = compact.code_bindings(str(HERE / "unused-generic-session-directory"))
    message = compact.runtime_agent_message(reference, code)
    def reconstruct():
        renderer = helper.PureTemplateAST(compact_raw)
        rebuilt = renderer.call("runtime_agent_message", reference, code)
        assert rebuilt == message
        api = ("runtime_initial_template", "runtime_next_template", "runtime_confirm_template", "runtime_hash_template")
        for name in api:
            assert getattr(compact, name)(reference, code) == getattr(old_compact, name)(reference, code)
            assert renderer.call(name, reference, code) == getattr(compact, name)(reference, code)
        (run / "generic-reconstructed-message.txt").write_bytes(rebuilt.encode("utf-8", "strict"))
        return {"independent_AST_message_equal": True, "unchanged_template_APIs": list(api),
                "generic_message_sha256": sha(rebuilt.encode()), "byte_count": len(rebuilt.encode())}
    checked("C06", reconstruct)
    checked("C07", lambda: {"explicit_bounds_literal_present": contract["allowed_message_insertion"]["bounds"] in message} if
            contract["allowed_message_insertion"]["bounds"] in message else (_ for _ in ()).throw(AssertionError("BOUNDS_ABSENT")))
    checked("C08", lambda: {"explicit_same_accepted_cursor_recovery_present": True} if
            contract["allowed_message_insertion"]["recovery"] in message else (_ for _ in ()).throw(AssertionError("RECOVERY_ABSENT")))

    def actual_literal():
        raw = (ROOT / "validation/tier2-support-019-qualification-006/fresh-author/literal-final.txt").read_bytes()
        reject = fails(lambda: old_parser.parse_failure(raw, fixture_failure_allowed=True), "INVALID_OWN_CAP")
        result = parser.parse_failure(raw, fixture_failure_allowed=True)
        assert result["trust"] == "UNATTESTED" and result["success"] is False
        assert result["qualification_claims_discharged"] == []
        assert result["literal_final_sha256"] == sha(raw)
        assert result["report"]["failure"]["operation"]["output_cap_bytes"] == 65536
        assert result["report"]["field_eof"]["/user"] is False
        write_new(run / "actual-Q006-evidence-only-parse.json", result)
        return {"actual_literal_sha256": sha(raw), "predecessor_rejection": reject,
                "success": False, "cause_reproduced": False}
    checked("C09", actual_literal)

    def accepted_attempts():
        variants = [view(output_cap_bytes=65536), view(start_char=-1), view(metadata_reserve_bytes=8192),
                    view(output_cap_bytes=-1), view(metadata_reserve_bytes=-1),
                    view(start_char=-MAX, output_cap_bytes=-MAX, metadata_reserve_bytes=MAX),
                    view(start_char=MAX, output_cap_bytes=MAX, metadata_reserve_bytes=-MAX)]
        observations = []
        for number, attempt in enumerate(variants):
            raw = wire(diagnostic(attempt))
            result = parser.parse_failure(raw, fixture_failure_allowed=True)
            assert result["report"]["failure"]["reproduction"]["view"] == attempt
            assert result["literal_final_sha256"] == sha(raw)
            assert result["success"] is False and result["trust"] == "UNATTESTED"
            assert result["qualification_claims_discharged"] == []
            observations.append({"synthetic_case": number, "attempt": attempt, "evidence_success": False})
        write_new(run / "synthetic-attempted-values.json", observations)
        return {"synthetic_variants_admitted_as_failure_only": len(variants)}
    checked("C10", accepted_attempts)

    def invalid_numbers():
        errors = []
        for location in ("operation", "reproduction"):
            for key in ("start_char", "output_cap_bytes", "metadata_reserve_bytes"):
                report = diagnostic(view())
                target = report["failure"]["operation"] if location == "operation" else report["failure"]["reproduction"]["view"]
                target[key] = True
                errors.append(fails(lambda report=report: parser.parse_failure(wire(report), fixture_failure_allowed=True)))
        for bad in (MAX+1, -MAX-1):
            errors.append(fails(lambda bad=bad: parser.parse_failure(wire(diagnostic(view(start_char=bad))),
                                                                    fixture_failure_allowed=True), "UNSAFE_JSON_INTEGER"))
        errors.append(fails(lambda: parser.parse_failure(wire(diagnostic(view(start_char=0.5))),
                                                         fixture_failure_allowed=True), "UNSUPPORTED_JSON_NUMBER"))
        return {"negative_control_rejections": errors}
    checked("C11", invalid_numbers)

    def malformed():
        clean = wire(diagnostic(view()))
        duplicated = clean.replace(b'"markers":[]', b'"markers":[],"markers":[]', 1)
        errors = [fails(lambda: parser.parse_failure(duplicated, fixture_failure_allowed=True), "DUPLICATE_JSON_KEY"),
                  fails(lambda: parser.parse_failure(clean), "FIXTURE_FAILURE_BRANCH_NOT_AUTHORIZED")]
        extra = diagnostic(view()); extra["failure"]["operation"]["extra"] = 0
        errors.append(fails(lambda: parser.parse_failure(wire(extra), fixture_failure_allowed=True), "INVALID_OWN_OPERATION"))
        claim = diagnostic(view()); claim["failure"]["trust"] = "VERIFIED"
        errors.append(fails(lambda: parser.parse_failure(wire(claim), fixture_failure_allowed=True), "FAILURE_AUTHORITY_OVERCLAIM"))
        return {"closed_schema_rejections": errors}
    checked("C12", malformed)

    def no_success():
        report = diagnostic(view())
        result = parser.parse_failure(wire(report), fixture_failure_allowed=True)
        assert result["success"] is False and result["qualification_claims_discharged"] == []
        assert result["historical_cause"] == "UNAVAILABLE"
        ordinary = {key: report[key] for key in SUCCESS}
        error = fails(lambda: parser.parse_failure(wire(ordinary), fixture_failure_allowed=True),
                      "NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH")
        return {"five_key_failure_success": False, "four_key_success_not_diagnostic": error}
    checked("C13", no_success)

    def accepted_domain_unchanged():
        rejected = []
        for attempt in (view(output_cap_bytes=65536), view(start_char=-1), view(metadata_reserve_bytes=8192),
                        view(output_cap_bytes=True), view(start_char=True), view(metadata_reserve_bytes=True)):
            rejected.append(fails(lambda attempt=attempt: compact.runtime_next_template(reference, code, attempt)))
        for attempt in (view(), view(output_cap_bytes=4096)):
            assert compact.runtime_next_template(reference, code, attempt) == old_compact.runtime_next_template(reference, code, attempt)
        return {"invalid_template_requests_rejected": rejected, "valid8192_4096_templates_preserved": True,
                "runtime_model_VIEW_task_Lean_qualification_calls": 0}
    checked("C14", accepted_domain_unchanged)

    assert [entry["id"] for entry in controls] == [entry["id"] for entry in contract["controls"]]
    after = {name: sha((ROOT / name).read_bytes()) for name in guards}
    assert after == before == guards
    write_new(HERE / "SOURCE_FIDELITY.json", {"format": "verislop.support021-source-fidelity/1",
              "status": "SOURCE_PREPARED_RUNTIME_UNQUALIFIED", **fidelity,
              "reader_runtime_legacy_capture_bytes_exact": True,
              "all27_claim_objects_changed": False, "success_acceptance_changed": False})
    report = {"format": "verislop.support021-actual-finite-controls/1",
              "status": "SOURCE_READINESS_PASS_RUNTIME_UNQUALIFIED", "actual_control_pid": os.getpid(),
              "controls": controls, "control_count": len(controls), "run_count": 1,
              "source_guards_before": before, "source_guards_after": after, "source_guard_count": len(guards),
              "all_source_guards_unchanged": True,
              "source_runtime_model_VIEW_task_Lean_qualification_calls": 0,
              "synthetic_fixtures_are_actual_tool_observations": False,
              "actual_Q006_diagnostic_is_unconfirmed_failure_evidence": True,
              "historical_cause": "UNAVAILABLE", "qualification_claim": False}
    write_new(HERE / "ACTUAL_CONTROL_REPORT.json", report)
    print(json.dumps({"actual_control_pid": os.getpid(), "control_count": len(controls),
                      "controls": [{"id": entry["id"], "status": entry["status"]} for entry in controls],
                      "source_guard_count": len(guards), "all_source_guards_unchanged": True,
                      "qualification_claim": False}, sort_keys=True))

if __name__ == "__main__":
    main()
