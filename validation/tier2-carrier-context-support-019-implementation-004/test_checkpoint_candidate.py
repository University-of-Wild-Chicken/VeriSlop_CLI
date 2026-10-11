"""Generic source-only mock engine controls. No live carrier/model/Lean/task.

Node is only this test's JavaScript execution engine. Author recipes themselves
use only the exposed functions store/load/text/exec_command and inline stdlib.
"""
import ast
import hashlib
import importlib.util
import json
import subprocess
import unittest
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


CANDIDATE = module(HERE / "bootstrap_tier2_carrier_view.py", "checkpoint_candidate004")
BASELINE = module(ROOT / "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py", "checkpoint_baseline9930")
REFERENCE = {"path": "/synthetic/unrelated-own.json", "sha256": "sha256:" + "a" * 64,
             "request_sha256": "sha256:" + "b" * 64}


def view(selector="/system", start=0, cap=8192):
    return {"operation": "field", "selector": selector, "start_char": start,
            "output_cap_bytes": cap, "metadata_reserve_bytes": 2048}


def raw_doc(fields, current_view, end=None):
    doc = {"format": "verislop.exact-carrier-view/0.1", "status": "ok", "carrier_path": REFERENCE["path"],
           "carrier_raw_bytes": 12345, "carrier_sha256": REFERENCE["sha256"],
           "request_sha256": REFERENCE["request_sha256"], "request_id": "synthetic-unrelated-only",
           "char_unit": "decoded_unicode_code_points", "byte_unit": "decoded_field_utf8",
           "output_cap_bytes": current_view["output_cap_bytes"],
           "metadata_reserve_bytes": current_view["metadata_reserve_bytes"], "operation": current_view["operation"]}
    if current_view["operation"] == "inventory":
        doc.update(navigation="complete_linear_fields_only", fields=[
            {"selector": selector, "field_chars": len(fields[selector]), "field_utf8_bytes": len(fields[selector].encode()),
             "start_char": 0, "end_char": len(fields[selector])} for selector in ("/system", "/user")])
    else:
        selector, start = current_view["selector"], current_view["start_char"]
        content = fields[selector]
        if end is None:
            end = len(content)
        part = content[start:end]
        doc.update(selector=selector, field_chars=len(content), field_utf8_bytes=len(content.encode()), start_char=start,
                   end_char=end, start_utf8_byte=len(content[:start].encode()), end_utf8_byte=len(content[:end].encode()),
                   content_chars=len(part), content_utf8_bytes=len(part.encode()), content=part,
                   next_char=end, field_eof=end == len(content))
    return doc


def actual(doc, chunk="synthetic-chunk"):
    return {"chunk_id": chunk, "exit_code": 0, "wall_time_seconds": 0.001,
            "original_token_count": 100,
            "output": json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"}


NODE_HARNESS = r'''
const vm = require("vm"), assert = require("assert");
const input = JSON.parse(require("fs").readFileSync(0,"utf8"));
const memory = {}, outcomes = [], forwarded = [], commands = [];
let viewCalls = 0, hashCalls = 0;
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
for (const step of input.steps) {
  if (step.mutate) {
    let value = memory[input.checkpoint_key];
    for (const part of step.mutate.path.slice(0,-1)) value = value[part];
    value[step.mutate.path.at(-1)] = step.mutate.value;
    continue;
  }
  const before = JSON.stringify(memory[input.checkpoint_key]);
  const oldCalls = viewCalls, oldHashes = hashCalls, oldForwarded = forwarded.length;
  const context = {
    load: key => clone(memory[key]), store: (key,value) => { memory[key] = clone(value); },
    text: value => forwarded.push(clone(value)),
    tools: {exec_command: async options => {
      commands.push(options.cmd);
      if (options.cmd.includes("VERISLOP_OWN_VIEW_HASH")) hashCalls += 1;
      else viewCalls += 1;
      return clone(step.actual);
    }}
  };
  let error = null;
  try { await new vm.Script("(async () => {\n" + step.code + "\n})()").runInNewContext(context); }
  catch (failure) { error = String(failure.message); }
  if (step.error) {
    assert(error !== null && error.includes(step.error), "expected " + step.error + " got " + error);
    assert.strictEqual(JSON.stringify(memory[input.checkpoint_key]), before, "rejection mutated checkpoint");
  } else assert.strictEqual(error,null,"unexpected " + error);
  if (step.view) {
    assert.strictEqual(viewCalls - oldCalls, 1, "not one VIEW");
    assert.strictEqual(hashCalls - oldHashes, 0);
    assert.deepStrictEqual(forwarded[oldForwarded],step.actual,"actual result not forwarded entire");
    assert.strictEqual(JSON.stringify(memory[input.checkpoint_key]),before,"VIEW committed before outer confirmation");
  }
  if (step.confirm) {
    assert.strictEqual(viewCalls,oldCalls,"CONFIRM performed VIEW");
    assert.strictEqual(hashCalls,oldHashes,"CONFIRM performed tool");
  }
  if (step.hash) {
    assert.strictEqual(viewCalls,oldCalls,"HASH performed VIEW");
    assert.strictEqual(hashCalls,oldHashes,"HASH performed child command");
    assert.strictEqual(forwarded[oldForwarded].format,"verislop.own-view-field-hashes/0.1");
    assert.strictEqual(forwarded[oldForwarded].semantic_acceptance_authority,false);
    assert.strictEqual(JSON.stringify(memory[input.checkpoint_key]),before,"HASH mutated VIEW state");
  }
  outcomes.push({error,summary:forwarded.slice(oldForwarded)});
}
console.log(JSON.stringify({memory,outcomes,viewCalls,hashCalls,commands}));
'''


def run_steps(steps):
    payload = {"steps": steps, "checkpoint_key": CANDIDATE.own_checkpoint_key(REFERENCE)}
    # A synchronous bounded source-only mock test, not a protocol timeout.
    result = subprocess.run(["node", "--input-type=module", "-e", "import { createRequire } from 'module';\nconst require=createRequire(import.meta.url);\n" + NODE_HARNESS],
                            input=json.dumps(payload, ensure_ascii=True), text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def stage(doc, chunk="synthetic-chunk", initial=False, current_view=None, overrides=None):
    recipe = CANDIDATE.author_initial_session_template(REFERENCE) if initial else CANDIDATE.author_next_session_template(REFERENCE, current_view)
    result = actual(doc, chunk)
    if overrides:
        result.update(overrides)
    return {"code": recipe, "actual": result, "view": True}


def confirm(chunk="synthetic-chunk", error=None, intact=True):
    return {"code": CANDIDATE.confirm_session_template(REFERENCE, {"chunk_id": chunk, "outer_output_intact": intact}),
            "confirm": True, **({"error": error} if error else {})}


def inventory_steps(fields):
    inventory = {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
    return [stage(raw_doc(fields, inventory), initial=True), confirm()]


def complete_steps(fields):
    steps = inventory_steps(fields)
    for selector in ("/system", "/user"):
        current = view(selector)
        steps.extend([stage(raw_doc(fields, current), current_view=current), confirm()])
    return steps


class CandidateControls(unittest.TestCase):
    def test_empty_request_id_reader_and_checkpoint_compatibility(self):
        fields = {"/system": "", "/user": "own unrelated"}
        with tempfile.TemporaryDirectory(prefix="empty-request-id-") as directory:
            path = Path(directory) / "own.json"
            raw = json.dumps({"format": "verislop.collaboration-carrier/0.1", "request_id": "",
                              "request_sha256": REFERENCE["request_sha256"], "system": fields["/system"],
                              "user": fields["/user"]}, sort_keys=True, separators=(",", ":")).encode()
            path.write_bytes(raw)
            reference = {**REFERENCE, "path": str(path), "sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}
            namespace = {}
            exec(CANDIDATE.READER_SOURCE, namespace)
            inventory = {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
            doc = json.loads(namespace["carrier_view"](reference, inventory))
            self.assertEqual(doc["status"], "ok")
            self.assertEqual(doc["request_id"], "")
        steps = complete_steps(fields)
        for step in steps:
            if "actual" in step:
                doc = json.loads(step["actual"]["output"])
                doc["request_id"] = ""
                step["actual"] = actual(doc)
        result = run_steps(steps + [{"code": CANDIDATE.hash_session_template(REFERENCE), "hash": True}])
        checkpoint = result["memory"][CANDIDATE.own_checkpoint_key(REFERENCE)]
        self.assertEqual(checkpoint["inventory"]["request_id"], "")
        self.assertTrue(checkpoint["fields"]["/user"]["field_eof"])

    def test_exact_key_set_rejects_comma_collision(self):
        script = (CANDIDATE.CHECKPOINT_VALIDATOR_SOURCE
                  + '\ncheckpointKeys({b:0,a:0},["a","b"],"POSITIVE_FAILED");\n'
                  + 'let error=null;try{checkpointKeys({"a,b":0},["a","b"],"EXACT_KEY_COLLISION");}catch(e){error=e.message;}\n'
                  + 'if(error!=="EXACT_KEY_COLLISION")throw new Error("comma collision accepted");console.log(error);\n')
        result = subprocess.run(["node", "-e", script], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "EXACT_KEY_COLLISION")

    def test_reader_and_legacy_view_apis_byte_exact(self):
        self.assertEqual(CANDIDATE.READER_SOURCE, BASELINE.READER_SOURCE)
        self.assertEqual(CANDIDATE.inline_prefix(REFERENCE), BASELINE.inline_prefix(REFERENCE))
        self.assertEqual(CANDIDATE.initial_session_template(REFERENCE), BASELINE.initial_session_template(REFERENCE))
        for current in (view(), view("/user", 17, 4096), {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}):
            self.assertEqual(CANDIDATE.next_session_template(REFERENCE, current), BASELINE.next_session_template(REFERENCE, current))
        self.assertEqual(CANDIDATE.legacy_agent_message(REFERENCE), BASELINE.agent_message(REFERENCE))

    def test_outer_truncation_stages_without_commit_and_same_cursor_retry(self):
        fields = {"/system": "own synthetic", "/user": "payload"}
        steps = inventory_steps(fields)
        first = view()
        retry = view(cap=4096)
        # The first forwarded outer view is treated as truncated: no CONFIRM.
        steps.extend([stage(raw_doc(fields, first), chunk="old", current_view=first),
                      stage(raw_doc(fields, retry), chunk="new", current_view=retry),
                      confirm("old", "ACTUAL_RESULT_NOT_COMPLETE_OR_UNMATCHED"), confirm("new")])
        result = run_steps(steps)
        state = result["memory"][CANDIDATE.own_checkpoint_key(REFERENCE)]
        self.assertEqual(state["fields"]["/system"]["content"], fields["/system"])
        self.assertEqual(len(state["observations"]), 2)
        self.assertEqual(result["viewCalls"], 3)

    def test_false_outer_confirmation_rejected_without_mutation(self):
        fields = {"/system": "one", "/user": "two"}
        current = view()
        run_steps(inventory_steps(fields) + [stage(raw_doc(fields, current), current_view=current),
                  confirm(error="OUTER_OUTPUT_NOT_CONFIRMED_INTACT", intact=False), confirm()])

    def test_nonzero_missing_boolean_or_running_status_rejected(self):
        fields = {"/system": "one", "/user": "two"}
        current = view()
        for overrides in ({"exit_code": 2}, {"exit_code": True}, {"exit_code": None}, {"session_id": 123}):
            with self.subTest(overrides=overrides):
                run_steps(inventory_steps(fields) + [stage(raw_doc(fields, current), current_view=current, overrides=overrides),
                          confirm(error="ACTUAL_RESULT_NOT_COMPLETE_OR_UNMATCHED")])

    def test_malformed_duplicate_truncated_or_overbudget_output_rejected(self):
        fields = {"/system": "one", "/user": "two"}
        current = view()
        valid = actual(raw_doc(fields, current))["output"]
        for overrides, error in (({"output": valid[:-7]}, "MALFORMED_OR_TRUNCATED_ACTUAL_OUTPUT"),
                                 ({"output": valid[:-2] + ',"status":"ok"}\n'}, "NONCANONICAL_OR_DUPLICATE_ACTUAL_OUTPUT"),
                                 ({"original_token_count": 20000}, "NESTED_OUTPUT_TRUNCATION")):
            with self.subTest(error=error):
                run_steps(inventory_steps(fields) + [stage(raw_doc(fields, current), current_view=current, overrides=overrides), confirm(error=error)])

    def test_identity_cursor_size_and_eof_counterexamples_rejected(self):
        fields = {"/system": "é😀", "/user": "two"}
        current = view()
        mutants = [("carrier_sha256", "sha256:" + "c" * 64, "ACTUAL_VIEW_IDENTITY_MISMATCH"),
                   ("request_id", "other", "ACTUAL_REQUEST_IDENTITY_CHANGED"),
                   ("next_char", 1, "ACTUAL_CURSOR_LENGTH_OR_EOF_MISMATCH"),
                   ("content_utf8_bytes", 2, "ACTUAL_CURSOR_LENGTH_OR_EOF_MISMATCH"),
                   ("field_eof", False, "ACTUAL_CURSOR_LENGTH_OR_EOF_MISMATCH"),
                   ("end_char", True, "INVALID_ACTUAL_CURSOR_OR_TOTAL")]
        for name, value, error in mutants:
            with self.subTest(name=name):
                doc = raw_doc(fields, current); doc[name] = value
                run_steps(inventory_steps(fields) + [stage(doc, current_view=current), confirm(error=error)])

    def test_unicode_codepoint_offsets_and_exact_replay(self):
        fields = {"/system": "é😀e\u0301\n", "/user": "用户𝄞\\\""}
        steps = inventory_steps(fields)
        for selector in ("/system", "/user"):
            first = view(selector)
            second = view(selector, 2)
            steps.extend([stage(raw_doc(fields, first, 2), current_view=first), confirm(),
                          stage(raw_doc(fields, second), current_view=second), confirm(),
                          stage(raw_doc(fields, first, 2), current_view=first), confirm()])
        result = run_steps(steps)
        state = result["memory"][CANDIDATE.own_checkpoint_key(REFERENCE)]
        for selector in ("/system", "/user"):
            field = state["fields"][selector]
            self.assertEqual(field["content"], fields[selector])
            self.assertEqual(field["next_char"], len(fields[selector]))
            self.assertEqual(field["next_utf8_byte"], len(fields[selector].encode()))
            self.assertTrue(field["field_eof"])

    def test_gap_overlap_or_mismatched_replay_rejected(self):
        fields = {"/system": "abcdef", "/user": "two"}
        first = view()
        initial = inventory_steps(fields) + [stage(raw_doc(fields, first, 3), current_view=first), confirm()]
        gap = view(start=4)
        run_steps(initial + [stage(raw_doc(fields, gap), current_view=gap), confirm(error="OWN_CURSOR_GAP_OR_BYTE_MISMATCH")])
        overlap = view(start=2)
        run_steps(initial + [stage(raw_doc(fields, overlap), current_view=overlap), confirm(error="REPLAY_OR_OVERLAP_MISMATCH")])
        replay = raw_doc(fields, first, 3); replay["content"] = "xyz"
        run_steps(initial + [stage(replay, current_view=first), confirm(error="REPLAY_OR_OVERLAP_MISMATCH")])

    def test_system_eof_required_and_empty_eof_explicit(self):
        fields = {"/system": "", "/user": ""}
        user = view("/user")
        run_steps(inventory_steps(fields) + [stage(raw_doc(fields, user), current_view=user), confirm(error="SYSTEM_EOF_REQUIRED_BEFORE_USER")])
        result = run_steps(complete_steps(fields))
        state = result["memory"][CANDIDATE.own_checkpoint_key(REFERENCE)]
        self.assertTrue(state["fields"]["/system"]["field_eof"])
        self.assertTrue(state["fields"]["/user"]["field_eof"])
        self.assertEqual(len(state["observations"]), 3)

    def test_checkpoint_reference_or_original_content_tamper_rejected(self):
        fields = {"/system": "é😀", "/user": "two"}
        current = view("/user")
        for path, value, error in ((["reference", "path"], "/other.json", "UNMATCHED_OWN_CHECKPOINT"),
                                   (["fields", "/system", "content"], "edited", "OWN_CHECKPOINT_REPLAY_MISMATCH")):
            with self.subTest(path=path):
                run_steps(complete_steps(fields) + [{"mutate": {"path": path, "value": value}},
                          stage(raw_doc(fields, current), current_view=current), confirm(error=error)])

    def test_non_scalar_content_rejected_without_normalization(self):
        fields = {"/system": "x", "/user": "two"}
        current = view()
        doc = raw_doc(fields, current); doc["content"] = "\ud800"
        result = actual(raw_doc(fields, current))
        result["output"] = json.dumps(doc, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        step = stage(raw_doc(fields, current), current_view=current); step["actual"] = result
        run_steps(inventory_steps(fields) + [step, confirm(error="NONSCALAR_OWN_FIELD")])

    def test_own_state_hash_no_view_or_child_and_exact_stdlib_unicode_roots(self):
        fields = {"/system": "é😀e\u0301\n", "/user": "用户𝄞\\\""}
        result = run_steps(complete_steps(fields) + [{"code": CANDIDATE.hash_session_template(REFERENCE), "hash": True}])
        hashes = result["memory"][CANDIDATE.own_hash_key(REFERENCE)]
        self.assertEqual(hashes["field_roots"], {selector: "sha256:" + hashlib.sha256(value.encode()).hexdigest() for selector, value in fields.items()})
        self.assertEqual(hashes["field_chars"], {selector: len(value) for selector, value in fields.items()})
        self.assertEqual(result["hashCalls"], 0)
        self.assertNotIn("tools.exec_command", CANDIDATE.hash_session_template(REFERENCE))

    def test_sha256_padding_utf8_boundaries_and_long_own_memory_stdlib_crosscheck(self):
        vectors = ["", "abc", "The quick brown fox jumps over the lazy dog", "\x00\x01\b\f\n\r\t\\\"",
                   "\x7f\x80\u07ff\u0800\ud7ff\ue000\uffff\U00010000\U0010ffff", "e\u0301😀𝄞用户"]
        vectors += ["a" * count for count in (1, 55, 56, 63, 64, 65, 127, 128, 129, 1000)]
        vectors += ["é" * count for count in (27, 28, 31, 32, 33)]
        # Large unrelated data exceeds the observed shell argument size threshold.
        long_value = "a用户😀𝄞e\u0301\\\n" * 50000
        self.assertGreaterEqual(len(long_value.encode()), 660115)
        self.assertGreater(len(long_value), 400000)
        vectors.append(long_value)
        script = (CANDIDATE.CHECKPOINT_VALIDATOR_SOURCE + CANDIDATE.OWN_SHA256_SOURCE
                  + '\nconst inputs=JSON.parse(require("fs").readFileSync(0,"utf8"));\n'
                  + 'console.log(JSON.stringify(inputs.map(ownViewSha256)));\n')
        result = subprocess.run(["node", "-e", script], input=json.dumps(vectors, ensure_ascii=True), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [hashlib.sha256(value.encode()).hexdigest() for value in vectors])

    def test_hash_incomplete_state_rejected_without_tool_or_cursor_advance(self):
        fields = {"/system": "one", "/user": "two"}
        steps = inventory_steps(fields) + [{"code": CANDIDATE.hash_session_template(REFERENCE), "error": "OWN_FIELDS_NOT_COMPLETE"}]
        result = run_steps(steps)
        self.assertEqual(result["hashCalls"], 0)

    def test_author_recipe_fixed_diff_and_distinct_zero_view_exceptions(self):
        first = CANDIDATE.author_initial_session_template(REFERENCE)
        next_view = CANDIDATE.author_next_session_template(REFERENCE)
        for recipe in (first, next_view):
            self.assertEqual(recipe.count("await tools.exec_command("), 1)
            self.assertIn("text(ACTUAL_RESULT);", recipe)
            self.assertIn("store(PENDING_KEY, {reference: OWN_REFERENCE, view: VIEW, result: ACTUAL_RESULT});", recipe)
            self.assertNotIn("checkpointConfirm(", recipe)
        confirmation = CANDIDATE.confirm_session_template(REFERENCE)
        self.assertNotIn("tools.exec_command", confirmation)
        message = CANDIDATE.agent_message(REFERENCE)
        self.assertIn(first, message)
        self.assertIn(next_view, message)
        self.assertIn(confirmation, message)
        self.assertIn(CANDIDATE.hash_session_template(REFERENCE), message)
        self.assertIn("loops over VIEW calls", message)
        self.assertIn("semantic_consumption", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
