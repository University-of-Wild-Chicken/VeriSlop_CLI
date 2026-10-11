"""Finite generic collector source/mock controls; no actual VIEW/model/task."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("candidate004_collector", HERE / "capture-amendment-003/collector_templates.py")
factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factory)
candidate = factory._candidate()
REFERENCE = {"path": "/synthetic/unrelated-own.json", "sha256": "sha256:" + "a" * 64,
             "request_sha256": "sha256:" + "b" * 64}


def field(start=0, cap=8192):
    return {"operation": "field", "selector": "/user", "start_char": start,
            "output_cap_bytes": cap, "metadata_reserve_bytes": 2048}


def reverse_observer(recipe, reference, case_id):
    key = json.dumps(factory.collector_result_key(reference, case_id), ensure_ascii=True)
    block = ['const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});',
             'text(ACTUAL_RESULT);', 'store(' + key + ', {result: ACTUAL_RESULT, view: VIEW});']
    lines = recipe.split("\n")
    positions = [index for index in range(len(lines)) if lines[index:index+3] == block]
    if len(positions) != 1:
        raise AssertionError("one exact observer block")
    index = positions[0]
    return "\n".join(lines[:index] + [factory.NORMAL_FORWARD] + lines[index+3:])


def mock_calls(recipes):
    # JavaScript-only development engine; no recipe command is executed.
    source = '''const memory={},calls=[],forwarded=[],stored=[],actuals=[];
const store=(key,value)=>{memory[key]=value;if(typeof value!=="string")stored.push({key,same_actual:value.result===actuals.at(-1),view:value.view});};
const load=key=>memory[key];const text=value=>forwarded.push(value===actuals.at(-1));
const tools={exec_command:async options=>{calls.push(options);const result={exit_code:0,output:"mock unchanged actual result",wall_time_seconds:0.01};actuals.push(result);return result;}};
'''
    source += "\n".join("{\n" + recipe + "\n}" for recipe in recipes)
    source += '\nconsole.log(JSON.stringify({calls,forwarded,stored}));\n'
    result = subprocess.run(["node", "--input-type=module", "-e", source], text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class CollectorControls(unittest.TestCase):
    def test_legacy_observer_exact_diff_and_fixed_one_view_for_each_case(self):
        for case_id in factory.CASE_IDS:
            first = factory.initial_collector_template(REFERENCE, case_id)
            next_view = factory.next_collector_template(REFERENCE, field(), case_id)
            self.assertEqual(reverse_observer(first, REFERENCE, case_id), candidate.initial_session_template(REFERENCE))
            self.assertEqual(reverse_observer(next_view, REFERENCE, case_id), candidate.next_session_template(REFERENCE, field()))
            result = mock_calls([first, next_view])
            self.assertEqual(len(result["calls"]), 2)
            self.assertEqual(result["forwarded"], [True, True])
            self.assertTrue(all(entry["same_actual"] for entry in result["stored"]))
            self.assertEqual([factory.collector_result_key(REFERENCE, case_id)] * 2, [entry["key"] for entry in result["stored"]])
            self.assertNotIn("checkpointConfirm", next_view)

    def test_collision_quoted_source_text_newlines_and_unicode_preserved(self):
        reference = {**REFERENCE, "path": "/synthetic/é😀\n'\"\\/" + factory.NORMAL_FORWARD + "\n" + factory.NORMAL_ACTUAL_RESULT + "/own.json"}
        for case_id in factory.CASE_IDS:
            first = factory.initial_collector_template(reference, case_id)
            next_view = factory.next_collector_template(reference, field(), case_id)
            self.assertEqual(reverse_observer(first, reference, case_id), candidate.initial_session_template(reference))
            self.assertEqual(reverse_observer(next_view, reference, case_id), candidate.next_session_template(reference, field()))
            result = mock_calls([first, next_view])
            self.assertEqual(result["forwarded"], [True, True])
            self.assertEqual(candidate.inline_prefix(reference), result["calls"][0]["cmd"].partition("\nVIEW = json.loads(")[0] + "\n")

    def test_fault_and_retry_only_registered_budget_and_explicit_cursor(self):
        for case_id in ("AC002-002", "AC002-003"):
            fault = factory.next_collector_template(REFERENCE, factory.FAULT_VIEW, case_id, fault=True)
            normal = factory.next_collector_template(REFERENCE, factory.FAULT_VIEW, case_id)
            restored = (factory._replace_exact_source_line(fault, factory.FAULT_ACTUAL_RESULT, factory.NORMAL_ACTUAL_RESULT, "restore")
                        if case_id == "AC002-002" else factory.NORMAL_PRAGMA + fault[len(factory.FAULT_PRAGMA):])
            self.assertEqual(restored, normal)
            retry = factory.next_collector_template(REFERENCE, field(cap=4096), case_id)
            result = mock_calls([factory.initial_collector_template(REFERENCE, case_id), fault, retry])
            self.assertEqual([entry["view"].get("start_char") for entry in result["stored"]], [None, 0, 0])
            self.assertEqual([entry["max_output_tokens"] for entry in result["calls"]], [16384, 256 if case_id == "AC002-002" else 16384, 16384])

    def test_author_message_uses_separate_author_recipes_and_has_no_collector_key(self):
        message = factory.plain_author_message(REFERENCE)
        self.assertEqual(candidate.agent_message(REFERENCE), message)
        self.assertIn(candidate.author_initial_session_template(REFERENCE), message)
        self.assertIn(candidate.author_next_session_template(REFERENCE), message)
        self.assertIn(candidate.confirm_session_template(REFERENCE), message)
        self.assertIn(candidate.hash_session_template(REFERENCE), message)
        self.assertNotIn("observable-carrier-collector-result", message)
        self.assertIn("own-view-pending", message)

    def test_explicit_cursor_change_does_not_modify_any_other_recipe_source(self):
        recipes = [factory.next_collector_template(REFERENCE, current) for current in (field(), field(7), field(cap=4096))]
        strip = lambda recipe: "\n".join(line for line in recipe.splitlines() if not line.startswith("const VIEW = "))
        self.assertEqual(strip(recipes[0]), strip(recipes[1]))
        self.assertEqual(strip(recipes[0]), strip(recipes[2]))
        self.assertNotIn("next_char", recipes[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
