"""Fresh own-carrier session regressions; no live task data or model calls."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from synthetic_dataset.tools import bootstrap_tier2_carrier_view as viewer
from synthetic_dataset.tools import bootstrap_tier2_transport as transport
from verislop import canonical


def field_view(selector="/system", start=0, cap=8192):
    return {"operation": "field", "selector": selector, "start_char": start,
            "output_cap_bytes": cap, "metadata_reserve_bytes": 2048}


def run_inert_templates(scripts, initial_state=None):
    """Run literal generated JS with inert tool calls and no dynamic evaluation."""
    program = "const state = new Map(Object.entries(" + json.dumps(initial_state or {}) + "));\n"
    program += """
const calls = [], loads = [], stores = [], forwarded = [], errors = [];
const actual = {exit_code: 0, output: "inert session fixture\\n"};
const load = key => { loads.push(key); return state.get(key); };
const store = (key, value) => { stores.push(key); state.set(key, value); };
const tools = {exec_command: async args => { calls.push(args); return actual; }};
const text = value => { forwarded.push({same_actual: value === actual, value}); };
"""
    for script in scripts:
        program += "{ try {\n" + script + "\nerrors.push(null);\n} catch (error) { errors.push(error.message); } }\n"
    program += "process.stdout.write(JSON.stringify({calls, loads, stores, forwarded, errors, state: Object.fromEntries(state)}));\n"
    process = subprocess.run(["node", "--input-type=module", "-e", program],
                             text=True, capture_output=True, check=True)
    return json.loads(process.stdout)


class Tier2CarrierSessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="unrelated-carrier-session-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def carrier(self, system="opaque unrelated system", user="fresh unrelated user", name="own.json"):
        document = {"format": bootstrap.CARRIER_FORMAT, "request_id": "session-regression",
                    "request_sha256": "sha256:" + "a" * 64, "system": system, "user": user}
        path = self.root / name
        path.write_bytes(canonical.dumps(document))
        reference = {"path": str(path), "sha256": canonical.digest_file(path),
                     "request_sha256": document["request_sha256"]}
        return reference, document

    def run_python_command(self, command):
        # Split at complete heredoc boundary lines, never at substrings in filenames.
        header, program = command.split("\n", 1)
        self.assertEqual("python -I -B - <<'VERISLOP_EXACT_CARRIER_VIEW'", header)
        ending = "VERISLOP_EXACT_CARRIER_VIEW\n"
        self.assertTrue(program.endswith(ending))
        program = program[:-len(ending)]
        process = subprocess.run([sys.executable, "-I", "-B", "-"],
                                 input=program.encode(), cwd=self.root, capture_output=True)
        self.assertEqual(0, process.returncode, process.stderr)
        return process.stdout

    def assert_slice(self, encoded, reference, document, selector, start):
        item = json.loads(encoded)
        original = document[selector[1:]]
        self.assertEqual("ok", item["status"])
        self.assertEqual("field", item["operation"])
        self.assertEqual(reference["path"], item["carrier_path"])
        self.assertEqual(reference["sha256"], item["carrier_sha256"])
        self.assertEqual(reference["request_sha256"], item["request_sha256"])
        self.assertEqual(selector, item["selector"])
        self.assertEqual(start, item["start_char"])
        end = item["end_char"]
        self.assertIs(type(end), int)
        self.assertLessEqual(start, end)
        self.assertLessEqual(end, len(original))
        self.assertEqual(end, item["next_char"])
        self.assertEqual(original[start:end], item["content"])
        self.assertEqual(end - start, item["content_chars"])
        self.assertEqual(len(original[start:end].encode()), item["content_utf8_bytes"])
        self.assertEqual(len(original[:start].encode()), item["start_utf8_byte"])
        self.assertEqual(len(original[:end].encode()), item["end_utf8_byte"])
        self.assertEqual(len(original), item["field_chars"])
        self.assertEqual(len(original.encode()), item["field_utf8_bytes"])
        self.assertEqual("decoded_unicode_code_points", item["char_unit"])
        self.assertEqual("decoded_field_utf8", item["byte_unit"])
        self.assertIs(type(item["field_eof"]), bool)
        self.assertEqual(end == len(original), item["field_eof"])
        self.assertLessEqual(len(encoded), item["output_cap_bytes"])
        if start < len(original):
            self.assertGreater(end, start)
        return item

    def test_initial_next_store_one_own_prefix_and_forward_one_result_per_call(self):
        reference, document = self.carrier()
        scripts = [viewer.initial_session_template(reference), viewer.next_session_template(reference)]
        observed = run_inert_templates(scripts)
        key = viewer.own_session_key(reference)
        self.assertEqual([None, None], observed["errors"])
        self.assertEqual([key], observed["stores"])
        self.assertEqual([key], observed["loads"])
        self.assertEqual({key: viewer.inline_prefix(reference)}, observed["state"])
        self.assertEqual(2, len(observed["calls"]))
        self.assertEqual(2, len(observed["forwarded"]))
        for script, call, forwarded in zip(scripts, observed["calls"], observed["forwarded"]):
            self.assertTrue(script.startswith('// @exec: {"max_output_tokens": 20000}\n'))
            self.assertEqual(1, script.count("tools.exec_command("))
            self.assertEqual(1, script.count("text("))
            self.assertEqual({"cmd", "max_output_tokens"}, set(call))
            self.assertEqual(16384, call["max_output_tokens"])
            self.assertTrue(call["cmd"].startswith(viewer.inline_prefix(reference)))
            self.assertTrue(forwarded["same_actual"])
        inventory = json.loads(self.run_python_command(observed["calls"][0]["cmd"]))
        self.assertEqual("ok", inventory["status"])
        self.assertEqual(["/system", "/user"], [row["selector"] for row in inventory["fields"]])
        item = self.assert_slice(self.run_python_command(observed["calls"][1]["cmd"]),
                                 reference, document, "/system", 0)
        self.assertTrue(item["field_eof"])

    def test_missing_own_prefix_cannot_call_python_or_load_another_carrier(self):
        reference, _ = self.carrier()
        other, _ = self.carrier(name="other.json")
        observed = run_inert_templates([viewer.next_session_template(reference)],
            {viewer.own_session_key(other): viewer.inline_prefix(other)})
        self.assertEqual([viewer.own_session_key(reference)], observed["loads"])
        self.assertEqual(["OWN_CARRIER_PREFIX_ABSENT"], observed["errors"])
        self.assertEqual([], observed["calls"])
        self.assertEqual([], observed["forwarded"])
        self.assertEqual([], observed["stores"])

    def test_renderer_rejects_nonclosed_unsafe_view_literals(self):
        reference, _ = self.carrier()
        invalid = [[], {}, {**field_view(), "path": "sibling"},
                   {**field_view(), "selector": "/../sibling"},
                   {**field_view(), "start_char": True},
                   {**field_view(), "start_char": 2**53},
                   {**field_view(), "output_cap_bytes": 8193},
                   {**field_view(), "metadata_reserve_bytes": 8192}]
        for value in invalid:
            with self.subTest(view=value), self.assertRaises(ValueError):
                viewer.next_session_template(reference, value)

    def test_truncation_retry_preserves_same_selector_start_and_fixed_tool_caps(self):
        reference, document = self.carrier("", "\\\n\x00🙂" * 5000 + "TAIL\t ")
        first_view, retry_view = field_view("/user"), field_view("/user", 0, 4096)
        scripts = [viewer.next_session_template(reference, first_view),
                   viewer.next_session_template(reference, retry_view)]
        observed = run_inert_templates(scripts,
            {viewer.own_session_key(reference): viewer.inline_prefix(reference)})
        self.assertEqual([None, None], observed["errors"])
        self.assertEqual(2, len(observed["calls"]))
        first = self.run_python_command(observed["calls"][0]["cmd"])
        first_item = self.assert_slice(first, reference, document, "/user", 0)
        with self.assertRaises((ValueError, KeyError)):
            self.assert_slice(first[:100], reference, document, "/user", 0)
        retry = self.run_python_command(observed["calls"][1]["cmd"])
        retry_item = self.assert_slice(retry, reference, document, "/user", 0)
        self.assertLess(retry_item["next_char"], first_item["next_char"])
        self.assertEqual(4096, retry_item["output_cap_bytes"])
        self.assertEqual(2048, retry_item["metadata_reserve_bytes"])
        for call in observed["calls"]:
            self.assertEqual(16384, call["max_output_tokens"])
        for script in scripts:
            self.assertTrue(script.startswith('// @exec: {"max_output_tokens": 20000}\n'))
        self.assertEqual({viewer.own_session_key(reference): viewer.inline_prefix(reference)}, observed["state"])

    def test_unicode_and_quote_filename_roundtrips_only_own_exact_reference(self):
        filename = 'quote\' double" dollar$ backtick` unicode🙂 VIEW = json.loads(\'fixture\').json'
        reference, document = self.carrier("", "é🙂e\u0301\\\" tail\t ", filename)
        observed = run_inert_templates([viewer.initial_session_template(reference),
                                       viewer.next_session_template(reference, field_view("/user"))])
        self.assertEqual([None, None], observed["errors"])
        for call in observed["calls"]:
            self.assertTrue(call["cmd"].startswith(viewer.inline_prefix(reference)))
        self.run_python_command(observed["calls"][0]["cmd"])
        item = self.assert_slice(self.run_python_command(observed["calls"][1]["cmd"]),
                                 reference, document, "/user", 0)
        self.assertTrue(item["field_eof"])
        self.assertEqual(document["user"], item["content"])
        self.assertEqual({filename}, {path.name for path in self.root.iterdir()})

    def test_own_json_draft_validation_preserves_literal_final_bytes(self):
        draft = ' \n{"unrelated":"é🙂", "value": 3}\n '
        program = "const draft = " + json.dumps(draft) + "; JSON.parse(draft); process.stdout.write(draft);"
        validated = subprocess.run(["node", "-e", program], capture_output=True, check=True)
        self.assertEqual(draft.encode(), validated.stdout)
        malformed = subprocess.run(["node", "-e", 'JSON.parse("{invalid");'], capture_output=True)
        self.assertNotEqual(0, malformed.returncode)
        envelope = {"transport": "collaboration", "requested_model": transport.MODEL,
                    "request_id": "session-regression", "request_sha256": "own-digest",
                    "agent_task_id": "/root/unrelated_session_fixture", "text": draft}
        self.assertEqual(draft, transport.validate_response(envelope, "session-regression", "own-digest")[0])
        reference, _ = self.carrier()
        message = viewer.agent_message(reference)
        self.assertIn("your own exact draft with JSON.parse", message)
        self.assertIn("Syntax success grants no semantic", message)
        self.assertIn("forwards literal FINAL unchanged", message)


if __name__ == "__main__":
    unittest.main()
