"""Registered bounded pure source controls; no model, VIEW or qualification."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
OLD = ROOT / "validation/tier2-support019-author-diagnostic-implementation-005"
HELPER_PATH = ROOT / "validation/tier2-support-019-qualification-adapters-006/author_protocol_reconstruction.py"
REGISTRATION = json.loads((HERE / "source-control-registration-002-before-execution.json").read_bytes())
NODE = REGISTRATION["node_executable"]["path"]
LOGS = ROOT / REGISTRATION["output_directory"] / "node-processes"
LOGS.mkdir()
spec = importlib.util.spec_from_file_location("recovery006_source_owner", HELPER_PATH)
HELPER = importlib.util.module_from_spec(spec); spec.loader.exec_module(HELPER)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def absolute_ref(path):
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha(raw), "byte_count": len(raw)}


def ref(path):
    item = absolute_ref(path); item["path"] = path.relative_to(ROOT).as_posix(); return item


def run_node(case):
    registered = next(value for value in REGISTRATION["node_cases"] if value["id"] == case)
    argv = registered["argv"]
    assert argv[0] == NODE and len(argv) in (2, 3)
    assert absolute_ref(Path(NODE)) == REGISTRATION["node_executable"]
    program = ROOT / registered["source"]["path"]
    assert ref(program) == registered["source"]
    directory = LOGS / case; directory.mkdir()
    stdout_path, stderr_path = directory / "stdout.log", directory / "stderr.log"
    before = ref(program)
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(argv, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                   env={**os.environ, "LC_ALL": "C.UTF-8"})
        with (directory / "started.json").open("x") as stream:
            json.dump({"pid": process.pid, "argv": argv, "scope": "UNRELATED_PURE_SOURCE_ONLY"}, stream, sort_keys=True)
            stream.write("\n")
        code = process.wait()
    after = ref(program)
    receipt = {"format": "verislop.support019-source-node-actual-receipt/1", "id": case, "pid": process.pid,
               "argv": argv, "cwd": str(ROOT), "returncode": code, "timeout_seconds": None,
               "source_before": before, "source_after": after,
               "node_before": REGISTRATION["node_executable"], "node_after": absolute_ref(Path(NODE)),
               "stdout": ref(stdout_path), "stderr": ref(stderr_path), "qualification_authority": False,
               "activation_authority": False, "task_TESTED_authority": False,
               "historical_cause": "UNAVAILABLE", "scope": "UNRELATED_PURE_SOURCE_ONLY"}
    with (directory / "actual-process-receipt.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2); stream.write("\n")
    assert type(code) is int and before == after and receipt["node_before"] == receipt["node_after"]
    return code, stdout_path.read_text(), stderr_path.read_text()


class PureSyntaxControls(unittest.TestCase):
    def test_01_constructed_minimal_transcription_counterexample(self):
        code, stdout, stderr = run_node("minimal-malformed")
        self.assertNotEqual(code, 0); self.assertIn("SyntaxError:", stderr); self.assertEqual(stdout, "")

    def test_02_minimal_canonical_positive(self):
        code, stdout, stderr = run_node("minimal-canonical")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout), {"semantic_consumption": "UNATTESTED", "semantic_acceptance_authority": False, "fields": {}})

    def test_03_whole_canonical_confirm_compiles(self):
        code, stdout, stderr = run_node("canonical-confirm")
        self.assertEqual(code, 0, stderr); self.assertEqual(stdout, "")

    def test_04_whole_transcription_counterexample_fails_syntax(self):
        code, stdout, stderr = run_node("malformed-confirm")
        self.assertNotEqual(code, 0); self.assertIn("SyntaxError:", stderr); self.assertEqual(stdout, "")

    def test_05_exact_restoration_compiles_original(self):
        self.assertEqual((HERE / "control-sources/restored-confirm.js").read_bytes(), (HERE / "control-sources/canonical-confirm.js").read_bytes())
        code, stdout, stderr = run_node("restored-confirm")
        self.assertEqual(code, 0, stderr); self.assertEqual(stdout, "")

    def test_06_unchanged_validator_rejects_then_corrects_same_pending(self):
        code, stdout, stderr = run_node("canonical-pure-validator")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout), {"scope": "UNRELATED_PURE_SOURCE_ONLY", "explicit_empty_eofs": 2,
            "rejected_confirmation_preserved_state": True, "same_pending_allowed_correction": True,
            "availability_only": True, "semantic_consumption": "UNATTESTED", "semantic_acceptance_authority": False})


class SourceFidelity(unittest.TestCase):
    def test_07_only_instruction_bytes_and_ast_change(self):
        values = [(directory / "bootstrap_tier2_carrier_view.py").read_bytes() for directory in (OLD, HERE)]
        trees = [ast.parse(raw.decode("utf-8")) for raw in values]
        funcs = [next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "agent_message") for tree in trees]
        self.assertEqual([len(function.body) for function in funcs], [7, 7])
        nodes = [function.body[4].value for function in funcs]
        self.assertEqual(ast.literal_eval(nodes[1]), ast.literal_eval(nodes[0]) + (HERE / "RECOVERY_INSTRUCTION_LITERAL.txt").read_text())
        def split(raw, node):
            lines = raw.splitlines(keepends=True)
            start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
            end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
            return raw[:start], raw[end:]
        self.assertEqual(split(values[0], nodes[0]), split(values[1], nodes[1]))
        funcs[1].body[4].value = copy.deepcopy(nodes[0])
        self.assertEqual(ast.dump(trees[0], include_attributes=False), ast.dump(trees[1], include_attributes=False))

    def test_08_all_constants_and_other_function_asts_unchanged(self):
        profiles = [HELPER.extract_schema((directory / "bootstrap_tier2_carrier_view.py").read_bytes()) for directory in (OLD, HERE)]
        self.assertEqual(profiles[0]["constants"], profiles[1]["constants"])
        functions = [{name: value for name, value in profile["function_ast_hashes"].items() if name != "agent_message"} for profile in profiles]
        self.assertEqual(len(functions[0]), 17); self.assertEqual(functions[0], functions[1])
        for directory in (OLD, HERE):
            self.assertEqual((directory / "diagnostic_failure_parser.py").read_bytes(), (OLD / "diagnostic_failure_parser.py").read_bytes())

    def test_09_factory_only_candidate_hash_change(self):
        sources = [(directory / "bootstrap_tier2_carrier_view.py").read_bytes() for directory in (OLD, HERE)]
        factories = [(directory / "capture-amendment-003/collector_templates.py").read_bytes() for directory in (OLD, HERE)]
        hashes = [hashlib.sha256(source).hexdigest().encode() for source in sources]
        self.assertEqual(factories[0].count(hashes[0]), 1)
        self.assertEqual(factories[0].replace(hashes[0], hashes[1], 1), factories[1])

    def test_10_source_owned_literals_all_recipes_and_whole_messages(self):
        profiles = [json.loads((directory / "independent-carrier-literals.json").read_bytes()) for directory in (OLD, HERE)]
        # Historical005 hashes use Python3.10. This fresh comparison derives the
        # unchanged baseline source under the same registered Python3.12 AST.
        reconstruction = copy.deepcopy(profiles[0]["author_protocol"]["reconstruction_source"])
        profiles[0].update(HELPER.extract_schema((OLD / "bootstrap_tier2_carrier_view.py").read_bytes()))
        profiles[0]["author_protocol"]["reconstruction_source"] = reconstruction
        for directory, profile in zip((OLD, HERE), profiles):
            HELPER.validate_literals((directory / "bootstrap_tier2_carrier_view.py").read_bytes(), profile)
        refs = [{"path": path, "sha256": "sha256:" + "7" * 64, "request_sha256": "sha256:" + "8" * 64}
                for path in ("/generic/alpha.json", "/generic/quoted ' carrier.json", "/generic/λ🙂.json")]
        for reference in refs:
            self.assertEqual(HELPER.recipes(profiles[0], reference), HELPER.recipes(profiles[1], reference))
            messages = [HELPER.author_message(profile, reference) for profile in profiles]
            anchor = profiles[0]["author_protocol"]["instruction"].encode() + b"\nCARRIER:\n"
            replacement = profiles[1]["author_protocol"]["instruction"].encode() + b"\nCARRIER:\n"
            self.assertEqual(messages[0].count(anchor), 1)
            self.assertEqual(messages[0].replace(anchor, replacement, 1), messages[1])

    def test_11_independent_reconstruction_rejects_tampered_source_and_instruction(self):
        source = (HERE / "bootstrap_tier2_carrier_view.py").read_bytes()
        profile = json.loads((HERE / "independent-carrier-literals.json").read_bytes())
        changed = copy.deepcopy(profile); changed["author_protocol"]["instruction"] += "unregistered permission"
        with self.assertRaisesRegex(ValueError, "AUTHOR_PROTOCOL_SCHEMA_NOT_SOURCE_DERIVED"):
            HELPER.validate_literals(source, changed)
        with self.assertRaisesRegex(ValueError, "AUTHOR_SOURCE_HASH_MISMATCH"):
            HELPER.validate_literals(source + b"\n", profile)

    def test_12_recovery_instruction_scope_and_no_historical_identifiers(self):
        text = (HERE / "RECOVERY_INSTRUCTION_LITERAL.txt").read_text()
        for expected in ("restore the exact canonical template", "same own pending observation", "exact attempted program",
                         "reproduction.availability UNAVAILABLE", "Failure stays UNATTESTED and unsuccessful"):
            self.assertIn(expected, text)
        for forbidden in ("c50c51", "UNRELATED_019_004", "Q004", "22e1b52d", "SyntaxError: Invalid or unexpected token"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
