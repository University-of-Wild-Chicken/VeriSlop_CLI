"""Pure unrelated fixtures only; no native/task/artifact input or model calls."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


candidate = module(HERE / "bootstrap_tier2_carrier_view.py", "carrier_candidate")
original = module(REPO / "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py", "carrier_original")
previous = module(REPO / "validation/tier2-carrier-context-support-019-implementation/bootstrap_tier2_carrier_view.py", "carrier_previous001")


def pack(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def view(selector="/system", start=0, cap=8192, reserve=2048):
    return {"operation": "field", "selector": selector, "start_char": start,
            "output_cap_bytes": cap, "metadata_reserve_bytes": reserve}


def node_templates(scripts, initial_state=None):
    """Parse literal recipe blocks with inert tools; no eval/Function wrapper."""
    program = 'const state = new Map(Object.entries(' + json.dumps(initial_state or {}) + '));\n' + '''
    const loads = [], stores = [], calls = [], forwarded = [], errors = [];
    const actual = {exit_code: 0, output: "unrelated mock result\\n", wall_time_seconds: 0.01};
    const load = (key) => { loads.push(key); return state.get(key); };
    const store = (key, value) => { stores.push(key); state.set(key, value); };
    const text = (value) => { forwarded.push({same_actual: value === actual, value}); };
    const tools = {exec_command: async (args) => { calls.push(args); return actual; }};
    '''
    program += "\n".join("{try {\n" + script + '\nerrors.push(null);\n} catch(error) {errors.push(String(error.message));}}' for script in scripts)
    program += '\nprocess.stdout.write(JSON.stringify({loads, stores, calls, forwarded, errors, state: Object.fromEntries(state)}));\n'
    process = subprocess.run(["node", "--input-type=module", "-e", program],
                             text=True, capture_output=True, check=True)
    return json.loads(process.stdout)


def validate(encoded, reference, document, selector, start):
    """Independent original-slice comparator with no lifecycle authority."""
    item = json.loads(encoded)
    field = document[selector[1:]]
    end = item["end_char"]
    assert item["status"] == "ok" and item["operation"] == "field"
    assert item["carrier_path"] == reference["path"]
    assert item["carrier_sha256"] == reference["sha256"]
    assert item["request_sha256"] == reference["request_sha256"]
    assert item["selector"] == selector and item["start_char"] == start
    assert type(end) is int and start <= end <= len(field) and item["next_char"] == end
    assert item["content"] == field[start:end]
    assert item["content_chars"] == end - start
    assert item["content_utf8_bytes"] == len(field[start:end].encode())
    assert item["start_utf8_byte"] == len(field[:start].encode())
    assert item["end_utf8_byte"] == len(field[:end].encode())
    assert item["field_chars"] == len(field)
    assert item["field_utf8_bytes"] == len(field.encode())
    assert item["char_unit"] == "decoded_unicode_code_points"
    assert item["byte_unit"] == "decoded_field_utf8"
    assert type(item["field_eof"]) is bool and item["field_eof"] == (end == len(field))
    assert len(encoded) <= item["output_cap_bytes"]
    assert len(pack({**item, "content": ""})) <= item["metadata_reserve_bytes"]
    assert start == len(field) or end > start
    return item


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="unrelated-support019-pure-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        namespace = {}
        exec(candidate.READER_SOURCE, namespace)
        self.read = namespace["carrier_view"]

    def carrier(self, system="opaque unrelated instructions", user="unrelated fixture", raw=None, name="own.json"):
        document = {"format": "verislop.collaboration-carrier/0.1", "request_id": "unrelated",
                    "request_sha256": "sha256:" + "a" * 64, "system": system, "user": user}
        path = self.root / name
        path.write_bytes(pack(document) if raw is None else raw)
        reference = {"path": str(path), "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                     "request_sha256": document["request_sha256"]}
        return reference, document

    def test_reader_and_existing_helpers_byte_identical(self):
        self.assertEqual(original.READER_SOURCE.encode(), candidate.READER_SOURCE.encode())
        self.assertEqual(previous.READER_SOURCE.encode(), candidate.READER_SOURCE.encode())
        for path in (REPO / "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py",
                     HERE / "bootstrap_tier2_carrier_view.py"):
            source = path.read_text()
            tree = ast.parse(source)
            pieces = {node.name: ast.get_source_segment(source, node) for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name in ("inline_source", "inline_command")}
            if path.name == "bootstrap_tier2_carrier_view.py" and path.parent == HERE:
                self.assertEqual(prior, pieces)
            else:
                prior = pieces
        reference, _ = self.carrier()
        for request in (None, view(), view("/user", 7, 4096)):
            self.assertEqual(original.inline_source(reference, request), candidate.inline_source(reference, request))
            self.assertEqual(original.inline_command(reference, request), candidate.inline_command(reference, request))

    def test_001_prefix_initial_recipe_and_required_helpers_byte_identical(self):
        for reference in ({"path": "/unrelated/002/own.json", "sha256": "sha256:" + "1" * 64,
                           "request_sha256": "sha256:" + "2" * 64}, self.carrier()[0]):
            self.assertEqual(previous.inline_prefix(reference), candidate.inline_prefix(reference))
            self.assertEqual(previous.initial_session_template(reference), candidate.initial_session_template(reference))
            self.assertEqual(previous.own_session_key(reference), candidate.own_session_key(reference))
        old_text = Path(previous.__file__).read_text()
        new_text = Path(candidate.__file__).read_text()
        names = {"inline_source", "inline_command", "inline_prefix", "initial_session_template"}
        extracts = lambda source: {node.name: ast.get_source_segment(source, node) for node in ast.parse(source).body
                                   if isinstance(node, ast.FunctionDef) and node.name in names}
        self.assertEqual(extracts(old_text), extracts(new_text))

    def test_first_next_prefix_identity_and_one_actual_forward(self):
        reference, _ = self.carrier()
        first = candidate.initial_session_template(reference)
        next_call = candidate.next_session_template(reference)
        observed = node_templates([first, next_call])
        key = candidate.own_session_key(reference)
        self.assertEqual([key], observed["stores"])
        self.assertEqual([key], observed["loads"])
        self.assertEqual(candidate.inline_prefix(reference), observed["state"][key])
        self.assertEqual([None, None], observed["errors"])
        self.assertEqual(2, len(observed["calls"]))
        self.assertEqual(2, len(observed["forwarded"]))
        for script, call, forwarded in zip((first, next_call), observed["calls"], observed["forwarded"]):
            self.assertTrue(script.startswith('// @exec: {"max_output_tokens": 20000}\n'))
            self.assertEqual(1, script.count("tools.exec_command("))
            self.assertEqual(1, script.count("text("))
            self.assertNotRegex(script, r"\b(for|while)\s*\(")
            self.assertEqual({"cmd", "max_output_tokens"}, set(call))
            self.assertEqual(16384, call["max_output_tokens"])
            self.assertEqual(candidate.inline_prefix(reference), call["cmd"].partition("\nVIEW = json.loads(")[0] + "\n")
            self.assertTrue(forwarded["same_actual"])

    def test_only_closed_view_changes_across_next_calls(self):
        reference, _ = self.carrier()
        first = candidate.next_session_template(reference, view())
        retry = candidate.next_session_template(reference, view("/user", 17, 4096))
        strip = lambda script: "\n".join(line for line in script.splitlines() if not line.startswith("const VIEW = "))
        self.assertEqual(strip(first), strip(retry))
        self.assertNotIn(candidate.READER_SOURCE, first)
        self.assertNotIn("store(", first)
        self.assertEqual(1, first.count("load("))
        self.assertNotIn("viewFields", first)
        self.assertNotIn("INVALID_CLOSED_VIEW", first)
        self.assertNotIn("Number.isSafeInteger", first)
        self.assertNotRegex(first, r"\b(eval|Function|AsyncFunction)\s*\(")
        self.assertLess(len(first), len(previous.next_session_template(reference)))

    def test_state_isolation_path_hash_and_absent_own_key(self):
        reference, _ = self.carrier()
        other, _ = self.carrier(name="other.json")
        changed_hash = {**reference, "sha256": "sha256:" + "b" * 64}
        keys = {candidate.own_session_key(item) for item in (reference, other, changed_hash)}
        self.assertEqual(3, len(keys))
        observed = node_templates([candidate.initial_session_template(reference),
                                  candidate.initial_session_template(other),
                                  candidate.next_session_template(reference)])
        self.assertEqual([candidate.own_session_key(reference)], observed["loads"])
        self.assertEqual(candidate.inline_prefix(reference), observed["calls"][-1]["cmd"].partition("\nVIEW = json.loads(")[0] + "\n")
        missing = node_templates([candidate.next_session_template(reference)],
                                 {candidate.own_session_key(other): candidate.inline_prefix(other)})
        self.assertEqual(["OWN_CARRIER_PREFIX_ABSENT"], missing["errors"])
        self.assertFalse(missing["calls"])
        self.assertFalse(missing["forwarded"])

    def test_renderer_closed_literal_rejects_nonclosed_or_unsafe_values(self):
        reference, _ = self.carrier()
        invalid = [None, [], {**view(), "path": "/unrelated/sibling"},
                   {**view(), "selector": "'); throw Error('injection"},
                   {**view(), "start_char": True}, {**view(), "start_char": 2**53},
                   {**view(), "start_char": -1}, {**view(), "output_cap_bytes": 8193},
                   {**view(), "metadata_reserve_bytes": 8192}, {**view(), "operation": "other"}]
        for invalid_view in invalid:
            with self.subTest(value=invalid_view), self.assertRaises(ValueError):
                candidate.next_session_template(reference, invalid_view) if invalid_view is not None else candidate._closed_view(invalid_view)

    def test_malformed_literal_views_reach_unchanged_python_checks_exact001_outputs(self):
        reference, _ = self.carrier()
        template = candidate.next_session_template(reference)
        original_line = next(line for line in template.splitlines() if line.startswith("const VIEW = "))
        cases = [
            (None, None), ([], None), (False, None),
            ({**view(), "path": "/unrelated/sibling"}, "INVALID_VIEW_FIELDS"),
            ({**view(), "operation": "other"}, "INVALID_OPERATION"),
            ({**view(), "selector": "'); throw Error('injection"}, "INVALID_SELECTOR"),
            ({**view(), "start_char": -1}, "INVALID_CURSOR"),
            ({**view(), "start_char": True}, "INVALID_CURSOR"),
            ({**view(), "start_char": "1"}, "INVALID_CURSOR"),
            ({**view(), "start_char": 2**53}, "INVALID_CURSOR"),
            ({**view(), "output_cap_bytes": 0}, None),
            ({**view(), "output_cap_bytes": 8193}, None),
            ({**view(), "output_cap_bytes": True}, None),
            ({**view(), "output_cap_bytes": 4096.5}, None),
            ({**view(), "metadata_reserve_bytes": 8192}, "INVALID_BOUNDS"),
            ({**view(), "metadata_reserve_bytes": True}, "INVALID_BOUNDS"),
            ({**view(), "metadata_reserve_bytes": 127}, "INVALID_BOUNDS"),
            ({**view(), "output_cap_bytes": 1024, "metadata_reserve_bytes": 128}, "METADATA_RESERVE_EXCEEDED"),
            ({**view(), "output_cap_bytes": 2050, "metadata_reserve_bytes": 2049}, "NO_CONTENT_CAPACITY"),
        ]
        scripts = [template.replace(original_line, "const VIEW = " + json.dumps(value, sort_keys=True) + ";")
                   for value, _ in cases]
        observed = node_templates(scripts, {candidate.own_session_key(reference): candidate.inline_prefix(reference)})
        self.assertEqual([None] * len(cases), observed["errors"])
        self.assertEqual(len(cases), len(observed["calls"]))
        self.assertEqual(len(cases), len(observed["forwarded"]))
        for (value, expected_code), call in zip(cases, observed["calls"]):
            with self.subTest(value=value):
                source = call["cmd"].split("\n", 1)[1].rsplit("VERISLOP_EXACT_CARRIER_VIEW\n", 1)[0]
                actual = subprocess.run([sys.executable, "-I", "-B", "-"], input=source.encode(), cwd=self.root, capture_output=True)
                prior_source = previous.inline_prefix(reference).split("\n", 1)[1]
                prior_source += "VIEW = json.loads(" + repr(json.dumps(value, sort_keys=True)) + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\n"
                prior = subprocess.run([sys.executable, "-I", "-B", "-"], input=prior_source.encode(), cwd=self.root, capture_output=True)
                self.assertEqual(2, actual.returncode)
                self.assertEqual((prior.returncode, prior.stdout, prior.stderr), (actual.returncode, actual.stdout, actual.stderr))
                if expected_code is None:
                    self.assertEqual(b"", actual.stdout)
                else:
                    item = json.loads(actual.stdout)
                    self.assertEqual(expected_code, item["code"])
                    self.assertIsNone(item["next_char"])
                    self.assertFalse(item["field_eof"])
        self.assertEqual({"own.json"}, {item.name for item in self.root.iterdir()})

    def test_existing_server_defaults_are_preserved_and_not_claimed_as_closed_renderer_keys(self):
        reference, document = self.carrier()
        self.assertEqual(previous.inline_source(reference, {}), candidate.inline_source(reference, {}))
        validate(self.read(reference, {}), reference, document, "/system", 0)
        with self.assertRaises(ValueError):
            candidate.next_session_template(reference, {})

    def test_reference_and_closed_view_serialization_are_executable_without_injection(self):
        reference, document = self.carrier(name="quote' double\" dollar$ backtick` unicode🙂 VIEW = json.loads('fixture').json")
        observed = node_templates([candidate.initial_session_template(reference),
                                  candidate.next_session_template(reference, view("/user"))])
        for call in observed["calls"]:
            source = call["cmd"].split("\n", 1)[1].rsplit("VERISLOP_EXACT_CARRIER_VIEW\n", 1)[0]
            process = subprocess.run([sys.executable, "-I", "-B", "-"], input=source.encode(),
                                     cwd=self.root, capture_output=True)
            self.assertEqual(0, process.returncode, process.stderr)
        validate(process.stdout, reference, document, "/user", 0)
        self.assertEqual(1, len(list(self.root.iterdir())))

    def test_unrelated_linear_multibyte_escape_tail_and_empty_eof(self):
        # Pure finite controls; the gated >=400000-char actual fixture is not run here.
        controls = ''.join(chr(i) for i in range(32)) + 'é🙂e\u0301\\"/'
        reference, document = self.carrier("", "HEAD" + controls * 2300 + "FINAL🙂\t ")
        for selector in ("/system", "/user"):
            cursor, restored, eof = 0, "", False
            while not eof:
                encoded = self.read(reference, view(selector, cursor))
                item = validate(encoded, reference, document, selector, cursor)
                restored += item["content"]
                cursor, eof = item["next_char"], item["field_eof"]
            self.assertEqual(document[selector[1:]], restored)
        self.assertTrue(restored.endswith("FINAL🙂\t "))

    def test_existing_raw_hash_request_metadata_path_and_strict_json_controls(self):
        reference, document = self.carrier()
        self.assertEqual("CARRIER_HASH_MISMATCH", json.loads(self.read({**reference, "sha256": "sha256:" + "0" * 64}, view()))["code"])
        self.assertEqual("REQUEST_METADATA_MISMATCH", json.loads(self.read({**reference, "request_sha256": "sha256:" + "0" * 64}, view()))["code"])
        raw = pack(document)
        for invalid in (b"{", b"\xff", b"\xef\xbb\xbf" + raw,
                        raw.replace(b'"unrelated"', b'"unrelated","request_id":"duplicate"'),
                        raw.replace(b'"opaque unrelated instructions"', b'"\\ud800"'),
                        raw.replace(b'"opaque unrelated instructions"', b"NaN"),
                        raw.replace(b'"opaque unrelated instructions"', b"1.2"),
                        raw.replace(b'"opaque unrelated instructions"', b"9007199254740992")):
            bad_reference, _ = self.carrier(raw=invalid)
            item = json.loads(self.read(bad_reference, view()))
            self.assertEqual("error", item["status"])
            self.assertIsNone(item["next_char"])
        reference, document = self.carrier()
        link = self.root / "link.json"
        link.symlink_to(reference["path"])
        self.assertEqual("INDIRECT_PATH", json.loads(self.read({**reference, "path": str(link)}, view()))["code"])
        observed_paths = []
        real_open = os.open
        def only_own(path, flags, *args):
            self.assertEqual(reference["path"], path)
            self.assertEqual(0, flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
            observed_paths.append(path)
            return real_open(path, flags, *args)
        with patch("os.open", side_effect=only_own), patch("builtins.open", side_effect=AssertionError("helper read")):
            validate(self.read(reference, view()), reference, document, "/system", 0)
        self.assertEqual([reference["path"]], observed_paths)

    def test_retry_cannot_advance_and_original_bounds_are_unchanged(self):
        reference, document = self.carrier("", "\\\n\x00🙂" * 5000 + "TAIL\t ")
        first = self.read(reference, view("/user"))
        for truncated in (first[:100], first[:100] + b"...truncated..."):
            with self.assertRaises((ValueError, KeyError, AssertionError)):
                validate(truncated, reference, document, "/user", 0)
        retried = validate(self.read(reference, view("/user", 0, 4096)), reference, document, "/user", 0)
        self.assertEqual(0, retried["start_char"])
        self.assertLess(retried["next_char"], json.loads(first)["next_char"])
        for cursor in (-1, True, "1", len(document["user"]) + 1):
            self.assertEqual("INVALID_CURSOR", json.loads(self.read(reference, view("/user", cursor)))["code"])
        self.assertEqual("INVALID_VIEW_FIELDS", json.loads(self.read(reference, {**view(), "path": "sibling"}))["code"])
        self.assertEqual("INVALID_SELECTOR", json.loads(self.read(reference, view("/../sibling")))["code"])
        self.assertEqual(b"", self.read(reference, view(cap=1, reserve=0)))

    def test_message_constraints_notes_json_syntax_and_no_authority(self):
        reference, _ = self.carrier()
        message = candidate.agent_message(reference)
        self.assertIn(candidate.initial_session_template(reference), message)
        self.assertIn(candidate.next_session_template(reference), message)
        for phrase in ("complete system field first", "complete user field", "explicit EOF view",
                       "nested exec_command", "outer functions.exec", "SAME selector/start",
                       "Private own working notes", "never replace exact input views",
                       "If exact SYSTEM requests structured JSON", "your own exact draft with JSON.parse",
                       "same request", "no helper/file/history/other-agent", "Lean builds or additional model calls",
                       "native strict schema/kernel remain authoritative", "forwards literal FINAL unchanged",
                       "no root cleanup", "grant no ACCEPT", "cannot attest that an LLM consumed",
                       "semantic search", "model/call/repair/output/compiler budgets",
                       "No inference, retrieval or review deadline"):
            self.assertIn(phrase, message)
        self.assertNotIn("base64", message)
        self.assertNotIn("token savings", message)
        self.assertIn("fixed short code unchanged", message)
        self.assertIn("do not add duplicate guards", message)
        # Own in-memory JSON syntax success preserves exact draft bytes; no semantic authority follows.
        draft = ' \n{"unrelated":"é🙂", "value": 3}\n '
        program = 'const draft = ' + json.dumps(draft) + '; JSON.parse(draft); process.stdout.write(draft);'
        result = subprocess.run(["node", "-e", program], capture_output=True, check=True)
        self.assertEqual(draft.encode(), result.stdout)
        malformed = subprocess.run(["node", "-e", 'JSON.parse("{invalid");'], capture_output=True)
        self.assertNotEqual(0, malformed.returncode)

    def test_prepared_fixture_contract_only_no_materialization_or_channel_execution(self):
        prepared = module(HERE / "prepare_unrelated_fixture.py", "prepared_fixture_contract")
        system, user = prepared.fixture()
        self.assertEqual(429112, len(user))
        self.assertGreaterEqual(len(user), 400000)
        self.assertTrue(user.endswith("UNRELATED_019_002_FINAL_TAIL🙂\t "))
        self.assertIn("é🙂e\u0301", user)
        self.assertIn('\x00\t\r\n\\"/', user)
        self.assertEqual(list(prepared.MARKERS), sorted(prepared.MARKERS, key=user.index))
        self.assertIn("syntactically valid JSON", system)
        self.assertIn("strict UTF-8", system)
        self.assertIn("complete reconstructed decoded field", system)
        self.assertNotIn("tools.exec_command", prepared.__doc__)

    def test_fresh002_protocol_registers_full_faults_empty_and_exactly_one_author_unexecuted(self):
        protocol = json.loads((HERE / "prepared-qualification-protocol.json").read_text())
        self.assertEqual("002", protocol["revision"])
        self.assertFalse(protocol["activation_authority"])
        self.assertEqual([], protocol["actual_cases_executed"])
        self.assertEqual([], protocol["fresh_author_cases_executed"])
        self.assertEqual([], protocol["materialized_fixtures"])
        cases = {item["id"]: item for item in protocol["actual_channel_cases"]}
        self.assertEqual({"AC002-001", "AC002-002", "AC002-003", "AC002-004"}, set(cases))
        self.assertEqual({"outer_max_output_tokens": 20000, "nested_max_output_tokens": 256}, cases["AC002-002"]["registered_fault_budgets"])
        self.assertEqual({"outer_max_output_tokens": 256, "nested_max_output_tokens": 16384}, cases["AC002-003"]["registered_fault_budgets"])
        for key in ("AC002-002", "AC002-003"):
            self.assertEqual(view("/user"), cases[key]["registered_fault_view"])
            self.assertIn("SAME selector/start", cases[key]["retry"])
            self.assertIn("outer20000/nested16384", cases[key]["retry"])
        author = protocol["fresh_author_case"]
        self.assertEqual(1, author["exact_count"])
        self.assertEqual("gpt-6.1-sol", author["model"])
        self.assertEqual("none", author["fork_turns"])
        self.assertEqual("UNATTESTED", author["inspection_assertions"])


if __name__ == "__main__":
    unittest.main()
