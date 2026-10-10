"""Pure source/mock controls only; no actual channel, fixture or model call."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import unittest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("capture_collector_templates", HERE / "collector_templates.py")
factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factory)
candidate = factory._candidate()
REFERENCE = {"path": "/unrelated/support019/002/own-carrier.json", "sha256": "sha256:" + "1" * 64,
             "request_sha256": "sha256:" + "2" * 64}


def field(selector="/system", start=0, cap=8192):
    return {"operation": "field", "selector": selector, "start_char": start,
            "output_cap_bytes": cap, "metadata_reserve_bytes": 2048}


def reverse_observer(recipe, reference, case_id):
    key = json.dumps(factory.collector_result_key(reference, case_id), ensure_ascii=True)
    observed = ('const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\n'
                'text(ACTUAL_RESULT);\n'
                'store(' + key + ', {result: ACTUAL_RESULT, view: VIEW});')
    lines = recipe.split("\n")
    block = observed.split("\n")
    positions = [index for index in range(len(lines)) if lines[index:index + 3] == block]
    if len(positions) != 1:
        raise AssertionError("one exact frozen observer block")
    index = positions[0]
    return "\n".join(lines[:index] + [factory.NORMAL_FORWARD] + lines[index + 3:])


def inert_node(recipes, initial_state=None, *, simulate_rendered_truncation=False):
    """Parse literal JavaScript blocks with mocks, never eval/source functions."""
    program = ('const state = new Map(Object.entries(' + json.dumps(initial_state or {}) + '));\n'
               + 'const simulateTruncation = ' + json.dumps(simulate_rendered_truncation) + ';\n')
    program += '''const calls=[], forwarded=[], resultStores=[], prefixStores=[], loads=[], errors=[], events=[];
      const actuals=[];
      const load=(key)=>{loads.push(key);return state.get(key);};
      const store=(key,value)=>{
        state.set(key,value);
        if(typeof value === "string"){prefixStores.push(key);return;}
        resultStores.push({key, same_actual: value.result === actuals[actuals.length-1],
          result:value.result, view:value.view}); events.push("result_store");
      };
      const text=(value)=>{
        forwarded.push({same_actual:value===actuals[actuals.length-1],
          rendered_output:simulateTruncation ? value.output.slice(0,128) : value.output});
        events.push("forward");
      };
      const tools={exec_command:async(args)=>{
        calls.push(args); events.push("call");
        const actual={exit_code:0,output:"unrelated pure mock:"+"X".repeat(12000),wall_time_seconds:0.01};
        actuals.push(actual); return actual;
      }};
    '''
    program += "\n".join('{try{\n' + recipe + '\nerrors.push(null);\n}catch(error){errors.push(String(error.message));}}' for recipe in recipes)
    program += '\nprocess.stdout.write(JSON.stringify({calls,forwarded,resultStores,prefixStores,loads,errors,events}));\n'
    process = subprocess.run(["node", "--input-type=module", "-e", program], text=True,
                             capture_output=True, check=True)
    return json.loads(process.stdout)


class CaptureControls(unittest.TestCase):
    def collision_reference(self, path):
        self.assertTrue(path.startswith("/"))
        self.assertNotIn("\x00", path)
        self.assertNotIn("/../", path)
        return {**REFERENCE, "path": path}

    def assert_collision_recipes(self, reference):
        # Only a pure inert-node mock runs: no carrier materialization or actual tool call.
        self.assertEqual(candidate.agent_message(reference), factory.plain_author_message(reference))
        for case_id in factory.CASE_IDS:
            normal_first = factory.initial_collector_template(reference, case_id)
            normal_next = factory.next_collector_template(reference, field("/user"), case_id)
            self.assertEqual(candidate.initial_session_template(reference), reverse_observer(normal_first, reference, case_id))
            self.assertEqual(candidate.next_session_template(reference, field("/user")), reverse_observer(normal_next, reference, case_id))
            recipes = [normal_first, normal_next]
            if case_id in ("AC002-002", "AC002-003"):
                fault = factory.next_collector_template(reference, factory.FAULT_VIEW, case_id, fault=True)
                recipes.append(fault)
                restored = (factory._replace_exact_source_line(fault, factory.FAULT_ACTUAL_RESULT,
                             factory.NORMAL_ACTUAL_RESULT, "fault test") if case_id == "AC002-002"
                            else factory.NORMAL_PRAGMA + fault[len(factory.FAULT_PRAGMA):])
                self.assertEqual(factory.next_collector_template(reference, factory.FAULT_VIEW, case_id), restored)
            observed = inert_node(recipes)
            self.assertEqual([None] * len(recipes), observed["errors"])
            self.assertEqual(len(recipes), len(observed["calls"]))
            self.assertEqual(len(recipes), len(observed["forwarded"]))
            self.assertEqual(len(recipes), len(observed["resultStores"]))
            self.assertEqual(["call", "forward", "result_store"] * len(recipes), observed["events"])
            for index, (recipe, call, retained, forwarded) in enumerate(zip(recipes, observed["calls"], observed["resultStores"], observed["forwarded"])):
                source_lines = recipe.split("\n")
                self.assertEqual(1, sum(line in (factory.NORMAL_ACTUAL_RESULT, factory.FAULT_ACTUAL_RESULT) for line in source_lines))
                self.assertEqual(1, source_lines.count("text(ACTUAL_RESULT);"))
                self.assertEqual(factory.collector_result_key(reference, case_id), retained["key"])
                self.assertTrue(retained["same_actual"] and forwarded["same_actual"])
                self.assertEqual(candidate.inline_prefix(reference), call["cmd"].partition("\nVIEW = json.loads(")[0] + "\n")
                self.assertEqual(256 if case_id == "AC002-002" and index == 2 else 16384, call["max_output_tokens"])
                self.assertTrue(recipe.startswith(factory.FAULT_PRAGMA if case_id == "AC002-003" and index == 2 else factory.NORMAL_PRAGMA))
            self.assertEqual(field("/user"), observed["resultStores"][1]["view"])

    def test_collision_path_with_complete_normal_forward_text(self):
        reference = self.collision_reference("/unrelated/" + factory.NORMAL_FORWARD + "/own-carrier.json")
        # The old raw substring counter sees quoted data; complete source-line equality sees one statement.
        self.assertGreater(candidate.initial_session_template(reference).count(factory.NORMAL_FORWARD), 1)
        self.assertGreater(candidate.next_session_template(reference).count(factory.NORMAL_FORWARD), 1)
        self.assert_collision_recipes(reference)

    def test_collision_paths_with_nested_call_substring_and_full_actual_result_line(self):
        for text in ("await tools.exec_command({cmd, max_output_tokens: 16384})", factory.NORMAL_ACTUAL_RESULT):
            with self.subTest(text=text):
                reference = self.collision_reference("/unrelated/" + text + "/own-carrier.json")
                normal = factory.next_collector_template(reference, factory.FAULT_VIEW, "AC002-002")
                self.assertGreater(normal.count("await tools.exec_command({cmd, max_output_tokens: 16384})"), 1)
                self.assert_collision_recipes(reference)

    def test_collision_combined_path_quotes_newlines_and_unicode_preserved(self):
        path = ("/unrelated/quote' double\" backslash\\ é🙂\u2028\n"
                + factory.NORMAL_FORWARD + "\n" + factory.NORMAL_ACTUAL_RESULT + "\r\n/own-carrier.json")
        reference = self.collision_reference(path)
        self.assert_collision_recipes(reference)

    def test_exact_source_line_replacer_preserves_quoted_data_and_refuses_missing_duplicate(self):
        for old, new in ((factory.NORMAL_FORWARD, "observer-one\nobserver-two\nobserver-three"),
                         (factory.NORMAL_ACTUAL_RESULT, factory.FAULT_ACTUAL_RESULT)):
            quoted = "const QUOTED = " + json.dumps("quote\"\n" + old + "🙂", ensure_ascii=True) + ";"
            source = quoted + "\n" + old + "\nother source line\n"
            expected = quoted + "\n" + new + "\nother source line\n"
            self.assertEqual(expected, factory._replace_exact_source_line(source, old, new, "exact test"))
            for invalid in (quoted + "\n", source + old + "\n"):
                with self.assertRaisesRegex(ValueError, "exact test"):
                    factory._replace_exact_source_line(invalid, old, new, "exact test")

    def test_old_capture001_factory_controls_registration_schema_and_manifest_unchanged(self):
        previous = HERE.parent / "capture-amendment-001"
        sha = lambda raw: "sha256:" + hashlib.sha256(raw).hexdigest()
        self.assertEqual("sha256:7b9aa5d071e87127f17dd984fb3da44ab45ff71ff16db841fdff0d9330e24067", sha((previous / "hash-manifest.json").read_bytes()))
        manifest = json.loads((previous / "hash-manifest.json").read_text())
        for relative, record in manifest["capture_files"].items():
            with self.subTest(path=relative):
                self.assertEqual(record["sha256"], sha((ROOT / relative).read_bytes()))

    def test_every_original002_frozen_file_and_manifest_unchanged(self):
        manifest_path = HERE.parent / "hash-manifest.json"
        sha = lambda raw: "sha256:" + hashlib.sha256(raw).hexdigest()
        self.assertEqual("sha256:b5dfdacd527aac0f5de6388793f1f0b23ca8847759b6e4379bbd7505db608328", sha(manifest_path.read_bytes()))
        manifest = json.loads(manifest_path.read_text())
        for relative, record in manifest["candidate_files"].items():
            with self.subTest(path=relative):
                self.assertEqual(record["sha256"], sha((ROOT / relative).read_bytes()))
        self.assertEqual(factory.CANDIDATE_SHA256, sha(factory.CANDIDATE_PATH.read_bytes()))

    def test_initial_and_next_differ_only_by_exact_forward_observer(self):
        for case_id in factory.CASE_IDS:
            observed = factory.initial_collector_template(REFERENCE, case_id)
            self.assertEqual(candidate.initial_session_template(REFERENCE), reverse_observer(observed, REFERENCE, case_id))
            for view in (field(), field("/user", 17), field("/user", 0, 4096)):
                observed = factory.next_collector_template(REFERENCE, view, case_id)
                self.assertEqual(candidate.next_session_template(REFERENCE, view), reverse_observer(observed, REFERENCE, case_id))

    def test_emitted_normal_and_fault_recipes_have_one_call_forward_and_no_wrapper(self):
        recipes = [factory.initial_collector_template(REFERENCE), factory.next_collector_template(REFERENCE)]
        recipes += [factory.next_collector_template(REFERENCE, factory.FAULT_VIEW, case_id, fault=True)
                    for case_id in ("AC002-002", "AC002-003")]
        for recipe in recipes:
            with self.subTest(recipe=recipe[:80]):
                self.assertEqual(1, recipe.count("tools.exec_command("))
                self.assertEqual(1, recipe.count("text("))
                self.assertEqual(1, recipe.count("const ACTUAL_RESULT = await"))
                self.assertEqual(1, recipe.count("text(ACTUAL_RESULT);"))
                self.assertNotRegex(recipe, r"\b(eval|Function|AsyncFunction)\s*\(")
                self.assertNotRegex(recipe, r"\b(for|while)\s*\(")
                self.assertNotIn("readFile", recipe)
                self.assertIn(candidate.inline_prefix(REFERENCE).splitlines()[0], candidate.inline_prefix(REFERENCE))
        short = factory.next_collector_template(REFERENCE)
        self.assertEqual(1, short.count("store("))
        self.assertEqual(1, short.count("load("))
        self.assertNotIn("viewFields", short)

    def test_mock_exact_actual_object_is_forwarded_then_stored_once_per_view(self):
        recipes = [factory.initial_collector_template(REFERENCE),
                   factory.next_collector_template(REFERENCE, field("/user", 0))]
        observed = inert_node(recipes)
        self.assertEqual([None, None], observed["errors"])
        self.assertEqual(["call", "forward", "result_store"] * 2, observed["events"])
        self.assertEqual(2, len(observed["calls"]))
        self.assertEqual(2, len(observed["forwarded"]))
        self.assertEqual(2, len(observed["resultStores"]))
        self.assertTrue(all(item["same_actual"] for item in observed["forwarded"]))
        self.assertTrue(all(item["same_actual"] for item in observed["resultStores"]))
        self.assertEqual(field("/user", 0), observed["resultStores"][-1]["view"])
        for call in observed["calls"]:
            self.assertEqual(16384, call["max_output_tokens"])
            self.assertEqual(candidate.inline_prefix(REFERENCE), call["cmd"].partition("\nVIEW = json.loads(")[0] + "\n")

    def test_mock_rendered_truncation_does_not_relabel_or_replace_retained_nested_object(self):
        # This is a pure simulation, not an actual outer truncation observation.
        recipe = factory.next_collector_template(REFERENCE, factory.FAULT_VIEW, "AC002-003", fault=True)
        state = {candidate.own_session_key(REFERENCE): candidate.inline_prefix(REFERENCE)}
        observed = inert_node([recipe], state, simulate_rendered_truncation=True)
        self.assertEqual([None], observed["errors"])
        self.assertEqual(128, len(observed["forwarded"][0]["rendered_output"]))
        retained = observed["resultStores"][0]
        self.assertTrue(retained["same_actual"])
        self.assertEqual(12020, len(retained["result"]["output"]))
        self.assertEqual(factory.FAULT_VIEW, retained["view"])
        self.assertNotIn("stdout", retained["result"])
        self.assertNotIn("stderr", retained["result"])
        self.assertNotIn("pid", retained["result"])
        self.assertEqual(["call", "forward", "result_store"], observed["events"])

    def test_only_view_literal_changes_and_no_cursor_is_automatically_advanced(self):
        recipes = [factory.next_collector_template(REFERENCE, view)
                   for view in (field("/user", 0), field("/user", 7), field("/user", 0, 4096))]
        strip = lambda value: "\n".join(line for line in value.splitlines() if not line.startswith("const VIEW = "))
        self.assertEqual(strip(recipes[0]), strip(recipes[1]))
        self.assertEqual(strip(recipes[0]), strip(recipes[2]))
        state = {candidate.own_session_key(REFERENCE): candidate.inline_prefix(REFERENCE)}
        observed = inert_node(recipes, state)
        self.assertEqual([0, 7, 0], [item["view"]["start_char"] for item in observed["resultStores"]])
        self.assertNotIn("next_char", recipes[0])

    def test_own_literal_result_keys_isolate_cases_paths_hashes_and_missing_prefix(self):
        variants = [REFERENCE, {**REFERENCE, "path": "/unrelated/other-own.json"},
                    {**REFERENCE, "sha256": "sha256:" + "3" * 64}]
        keys = {factory.collector_result_key(reference, case_id) for reference in variants for case_id in factory.CASE_IDS}
        self.assertEqual(12, len(keys))
        key = factory.collector_result_key(REFERENCE, "AC002-001")
        recipe = factory.next_collector_template(REFERENCE)
        self.assertIn("store(" + json.dumps(key, ensure_ascii=True) + ",", recipe)
        observed = inert_node([recipe])
        self.assertEqual(["OWN_CARRIER_PREFIX_ABSENT"], observed["errors"])
        self.assertFalse(observed["calls"])
        self.assertFalse(observed["forwarded"])
        self.assertFalse(observed["resultStores"])
        self.assertEqual([candidate.own_session_key(REFERENCE)], observed["loads"])
        with self.assertRaises(ValueError):
            factory.collector_result_key(REFERENCE, "unregistered")

    def test_registered_faults_only_change_one_budget_and_normal_retry_preserves_cursor(self):
        for case_id in ("AC002-002", "AC002-003"):
            fault = factory.next_collector_template(REFERENCE, factory.FAULT_VIEW, case_id, fault=True)
            normal = factory.next_collector_template(REFERENCE, factory.FAULT_VIEW, case_id)
            restored = fault.replace("max_output_tokens: 256", "max_output_tokens: 16384") if case_id == "AC002-002" else factory.NORMAL_PRAGMA + fault[len(factory.FAULT_PRAGMA):]
            self.assertEqual(normal, restored)
            retry = factory.next_collector_template(REFERENCE, field("/user", 0, 4096), case_id)
            observed = inert_node([fault, retry], {candidate.own_session_key(REFERENCE): candidate.inline_prefix(REFERENCE)})
            self.assertEqual([0, 0], [item["view"]["start_char"] for item in observed["resultStores"]])
            self.assertEqual(16384, observed["calls"][-1]["max_output_tokens"])
            self.assertTrue(retry.startswith(factory.NORMAL_PRAGMA))
        for case_id, view in (("AC002-001", factory.FAULT_VIEW), ("AC002-002", field("/user", 1))):
            with self.assertRaises(ValueError):
                factory.next_collector_template(REFERENCE, view, case_id, fault=True)

    def test_model_author_message_stays_original_plain002(self):
        message = factory.plain_author_message(REFERENCE)
        self.assertEqual(candidate.agent_message(REFERENCE), message)
        self.assertNotIn("ACTUAL_RESULT", message)
        self.assertNotIn("observable-carrier-collector-result", message)

    def test_registration_limits_evidence_and_preserves_full_fault_empty_one_author_cases(self):
        registration = json.loads((HERE / "registration.json").read_text())
        self.assertEqual("002", registration["capture_amendment"])
        self.assertFalse(registration["prior_pass_reuse"])
        self.assertEqual((15, 10), (registration["fresh_pure_controls"]["count"], registration["fresh_pure_controls"]["prior_controls_rerun_with_new_bindings"]))
        self.assertIn("Exact whole LF-delimited source-line equality", registration["replacement_scope"])
        self.assertEqual({"AC002-001", "AC002-002", "AC002-003", "AC002-004", "FA002-001"}, {item["id"] for item in registration["cases"]})
        self.assertEqual({"UNAVAILABLE"}, {value for key, value in registration["unavailable"].items() if key != "never_fabricate_or_relabel"})
        self.assertTrue(registration["unavailable"]["never_fabricate_or_relabel"])
        self.assertIn("Observable byte availability", registration["claim_scope"])
        self.assertIn("no hidden outer-envelope identity or LLM consumption", registration["claim_scope"])
        self.assertEqual([], registration["actual_cases_executed"])
        self.assertEqual([], registration["fresh_model_calls"])
        self.assertEqual([], registration["materialized_fixtures"])
        author = next(item for item in registration["cases"] if item["id"] == "FA002-001")
        self.assertEqual((1, "gpt-6.1-sol", "none"), (author["exact_count"], author["model"], author["fork_turns"]))
        self.assertFalse(registration["activation_authority"])


if __name__ == "__main__":
    unittest.main()
