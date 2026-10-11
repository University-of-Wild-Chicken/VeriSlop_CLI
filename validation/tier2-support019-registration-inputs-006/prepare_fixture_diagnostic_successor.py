"""Registered source-only SYSTEM successor and four generic grammar controls."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / "source-preimages/integration001-prepare_unrelated_fixture.py.raw"
CARRIER = ROOT / "validation/tier2-support019-author-recovery-implementation-006/bootstrap_tier2_carrier_view.py"
PARSER = ROOT / "validation/tier2-support019-author-recovery-implementation-006/diagnostic_failure_parser.py"

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def system_node(tree):
    return next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SYSTEM" for t in n.targets))

def masked(tree):
    tree = copy.deepcopy(tree)
    system_node(tree).value = ast.Constant(value="DECLARED_SYSTEM_LITERAL")
    return ast.dump(tree, include_attributes=False)

def main():
    raw = BASE.read_bytes()
    text = raw.decode()
    tree = ast.parse(text)
    node = system_node(tree)
    old = ast.literal_eval(node.value)
    pointer = "specified in the outer author instructions"
    assert old.count(pointer) == 1
    prefix = old.split(" If a concrete observed protocol failure prevents completion,")[0]
    carrier_tree = ast.parse(CARRIER.read_bytes())
    start = "When the gate-fixture SYSTEM permits diagnostic failure, return the four ordinary fields"
    instruction = next(n.value for n in ast.walk(carrier_tree) if isinstance(n, ast.Constant) and type(n.value) is str and start in n.value)
    grammar = instruction[instruction.index(start):instruction.index("An already visible tool error or pure CONFIRM/HASH exception")]
    consistency_start = instruction.index("CLOSED REPRODUCTION CONSISTENCY:")
    consistency = instruction[consistency_start:instruction.index("\n\nCANONICAL FIXED-TEMPLATE RESTORATION:", consistency_start)]
    new = prefix + " If a concrete observed protocol failure prevents completion, this fixture SYSTEM explicitly permits the following self-contained diagnostic branch. It is evidence only, unsuccessful, and grants zero claim authority. Preserve only actual observed partial fields, never invent roots, EOF, markers or errors. " + grammar + " " + consistency + " Partial-result markers is an ordered list of nonempty strings; field_roots is a subset of /system and /user with strict sha256: plus 64 lowercase hexadecimal digests; field_eof contains both selectors with exact booleans; field_chars contains both selectors with nonnegative exact safe integers. Every string must encode as strict UTF-8; reject duplicate keys, a BOM, floats, nonfinite values and integers beyond JavaScript safe integer range. The exact failure grammar here governs only this unrelated fixture; permitted compact runtime operations and recovery remain those in the fixed outer protocol. A diagnostic response never satisfies successful completion."
    assert pointer not in new and new.startswith(prefix)
    lines = text.splitlines(keepends=True)
    successor = "".join(lines[:node.lineno-1]) + "SYSTEM = " + repr(new) + "\n" + "".join(lines[node.end_lineno:])
    assert masked(tree) == masked(ast.parse(successor))
    output = HERE / "prepare_unrelated_fixture.py"
    assert not output.exists()
    output.write_text(successor)
    spec = importlib.util.spec_from_file_location("registered_diagnostic_parser", PARSER)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    failure = {"format":"verislop.author-observed-failure/0.1", "trust":"UNATTESTED", "stage":"UNKNOWN", "operation":None,
       "observation":{"kind":"unavailable","reason":"NOT_EXPOSED"},
       "reproduction":{"template":"UNAVAILABLE","view":None,"confirmation":None,"own_input_literal":None,"expected_observed_error_literal":None,"availability":"UNAVAILABLE"},
       "self_critique":{"violated_check":None,"own_attempted_retry":None,"observed_retry_error_literal":None,"recovery":"UNAVAILABLE"}}
    sample = {"markers":[],"field_roots":{},"field_eof":{"/system":False,"/user":False},"field_chars":{"/system":0,"/user":0},"failure":failure}
    def accepted(value, allowed=True):
        return parser.parse_failure(json.dumps(value).encode(), fixture_failure_allowed=allowed)
    def rejected(value, allowed=True):
        try:
            accepted(value, allowed)
        except (ValueError, TypeError):
            return True
        raise AssertionError("GENERIC_DIAGNOSTIC_SHOULD_REJECT")
    result = accepted(sample)
    assert result["success"] is False and result["trust"] == "UNATTESTED" and result["qualification_claims_discharged"] == []
    rejected(sample, False)
    known = copy.deepcopy(sample)
    known["failure"]["stage"] = "NEXT_USER"
    known["failure"]["observation"] = {"kind":"literal","source":"OWN_VISIBLE_PROTOCOL_STATE","text":"generic source-control error","scope":"complete"}
    known["failure"]["reproduction"] = {"template":"NEXT","view":{"operation":"field","selector":"/user","start_char":0,"output_cap_bytes":4096,"metadata_reserve_bytes":2048},"confirmation":None,"own_input_literal":None,"expected_observed_error_literal":"generic source-control error","availability":"PROVIDED"}
    known["failure"]["self_critique"]["recovery"] = "FIXED_SOURCE_BLOCKED"
    result2 = accepted(known)
    assert result2["success"] is False
    wrong = copy.deepcopy(known)
    wrong["failure"]["reproduction"]["view"] = {"operation":"inventory","output_cap_bytes":4096,"metadata_reserve_bytes":2048}
    rejected(wrong)
    unknown = copy.deepcopy(sample)
    unknown["failure"]["operation"] = {"chunk_id":None,"selector":"/user","start_char":0,"output_cap_bytes":4096,"metadata_reserve_bytes":2048}
    rejected(unknown)
    evidence = {"format":"verislop.fixture-diagnostic-source-fidelity/1","scope":"SOURCE_ONLY_NOT_QUALIFICATION","preimage":{"path":str(BASE.relative_to(ROOT)),"sha256":sha(raw)},"successor":{"path":str(output.relative_to(ROOT)),"sha256":sha(successor.encode())},"old_pointer_witness":pointer,"old_pointer_offset":old.index(pointer),"system_sha256_before":sha(old.encode()),"system_sha256_after":sha(new.encode()),"whole_ast_equal_excluding_only_system_literal":True,"successful_schema_prefix_byte_exact":True,"generic_control_groups":4,"all_generic_controls_passed":True,"model_runtime_view_qualification_calls":0}
    (HERE / "fixture-system-source-fidelity.json").write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
    print(json.dumps(evidence,sort_keys=True))

if __name__ == "__main__":
    main()
