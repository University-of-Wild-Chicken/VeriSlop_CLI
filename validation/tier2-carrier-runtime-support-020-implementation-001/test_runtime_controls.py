"""Finite unrelated generic controls, with actual subprocess evidence.

Tool chunk IDs are explicitly mocked; subprocess statuses/output bytes are real.
No model, current gate fixture, qualification predicate or task is invoked.
"""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("runtime020_control_protocol", HERE / "compact_protocol.py")
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)
OUTPUT = None
TOTAL_CALLS = 0
LARGE_OBSERVATION = None


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


class RuntimeControls(unittest.TestCase):
    def setUp(self):
        self.directory = OUTPUT / self._testMethodName
        self.directory.mkdir()
        self.sessions = self.directory / "own-session-output"; self.sessions.mkdir()
        self.carrier = self.directory / "unrelated-carrier.json"
        self.fields = {"system": "System α🙂e\u0301\r\n ' \\", "user": "User \t🙂 é \" literal $(printf data) `data` \\ tail\n"}
        self.counter = 0
        self.set_carrier()

    def set_carrier(self, system=None, user=None, request_id="generic-runtime020"):
        if system is not None: self.fields["system"] = system
        if user is not None: self.fields["user"] = user
        self.request_hash = sha(("unrelated-runtime020:" + self._testMethodName).encode())
        record = {"format": "verislop.collaboration-carrier/0.1", "request_id": request_id,
                  "request_sha256": self.request_hash, **self.fields}
        self.carrier.write_text(wire(record) + "\n")
        self.reference = {"path": str(self.carrier), "sha256": sha(self.carrier.read_bytes()), "request_sha256": self.request_hash}
        self.code = protocol.code_bindings(str(self.sessions))
        self.state_path = Path(protocol.session_path(self.reference, self.code))

    def request(self, operation, **extra):
        return {**protocol._request(self.reference, self.code, operation), **extra}

    def start(self, request, raw_command=None):
        self.counter += 1
        evidence = self.directory / ("call-%04d" % self.counter); evidence.mkdir()
        command = raw_command or protocol.runtime_command(request)
        (evidence / "submitted-request.json").write_text(wire(request) + "\n")
        (evidence / "submitted-command.sh").write_text(command + "\n")
        child = subprocess.Popen(["/bin/sh", "-c", command], cwd=self.directory,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return child, evidence, request, command

    def finish(self, running):
        global TOTAL_CALLS
        child, evidence, request, command = running
        stdout, stderr = child.communicate(); TOTAL_CALLS += 1
        (evidence / "stdout.bin").write_bytes(stdout); (evidence / "stderr.bin").write_bytes(stderr)
        receipt = {"format": "verislop.runtime020-generic-subprocess-observation/1", "actual_pid": child.pid,
                   "argv": ["/bin/sh", "-c", command], "cwd": str(self.directory), "integer_returncode": child.returncode,
                   "stdout_sha256": sha(stdout), "stdout_bytes": len(stdout), "stderr_sha256": sha(stderr),
                   "stderr_bytes": len(stderr), "operation": request["operation"], "mock_tool_chunk_id": True,
                   "qualified_evidence": False, "model_calls": 0, "runtime_timeout": None}
        (evidence / "actual-process-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        actual = {"chunk_id": "GENERIC_CONTROL_%04d" % self.counter,
                  "exit_code": child.returncode, "output": stdout.decode("utf-8"), "original_token_count": 0}
        return actual, stderr

    def call(self, request, raw_command=None):
        return self.finish(self.start(request, raw_command))[0]

    def view(self, selector=None, start=0, cap=8192, reserve=2048):
        view = {"operation": "inventory" if selector is None else "field", "output_cap_bytes": cap, "metadata_reserve_bytes": reserve}
        if selector is not None: view.update(selector=selector, start_char=start)
        actual = self.call(self.request("view", view=view))
        self.assertIs(type(actual["exit_code"]), int); self.assertEqual(actual["exit_code"], 0)
        self.assertLessEqual(len(actual["output"].encode()), cap)
        return {"reference": self.reference, "view": view, "result": actual}

    def confirm(self, pending, confirmation=None):
        confirmation = confirmation or {"chunk_id": pending["result"]["chunk_id"], "outer_output_intact": True}
        return self.call(self.request("confirm", pending=pending, confirmation=confirmation))

    def accepted(self):
        return self.state_path.read_bytes() if self.state_path.exists() else None

    def reject(self, pending, confirmation=None):
        before = self.accepted(); actual = self.confirm(pending, confirmation)
        self.assertEqual(actual["exit_code"], 2, actual["output"])
        self.assertEqual(self.accepted(), before)
        self.assertFalse(list(self.sessions.glob("*.temporary-*")))
        return json.loads(actual["output"])["code"]

    def inventory(self):
        pending = self.view(); self.assertEqual(self.confirm(pending)["exit_code"], 0)
        return pending

    def complete(self, cap=8192):
        self.inventory(); views = 1; max_output = 0
        for selector in ("/system", "/user"):
            cursor = 0; text = self.fields[selector[1:]]
            bound = max(1, (len(text) * 12) // (cap - 2048) + 16)
            for _ in range(bound):
                pending = self.view(selector, cursor, cap=cap); views += 1
                document = json.loads(pending["result"]["output"])
                self.assertEqual(document["content"], text[document["start_char"]:document["end_char"]])
                self.assertEqual(document["start_utf8_byte"], len(text[:cursor].encode()))
                self.assertEqual(self.confirm(pending)["exit_code"], 0)
                max_output = max(max_output, len(pending["result"]["output"].encode()))
                cursor = document["next_char"]
                if document["field_eof"]: break
            else: self.fail("Registered finite generic view bound exhausted")
            self.assertEqual(cursor, len(text))
        result = self.call(self.request("hash")); self.assertEqual(result["exit_code"], 0, result["output"])
        hashes = json.loads(result["output"])
        for selector in ("/system", "/user"):
            text = self.fields[selector[1:]]
            self.assertEqual(hashes["field_roots"][selector], sha(text.encode()))
            self.assertEqual(hashes["field_chars"][selector], len(text))
            self.assertEqual(hashes["field_utf8_bytes"][selector], len(text.encode()))
            self.assertTrue(hashes["field_eof"][selector])
        return hashes, views, max_output

    def test_01_exact_sources_and_legacy_apis(self):
        baseline = ROOT / "validation/tier2-support019-author-recovery-implementation-006/bootstrap_tier2_carrier_view.py"
        self.assertEqual((HERE / "legacy006.py").read_bytes(), baseline.read_bytes())
        tree = ast.parse(baseline.read_bytes())
        literals = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("READER_SOURCE", "CHECKPOINT_VALIDATOR_SOURCE", "OWN_SHA256_SOURCE")}
        self.assertEqual((HERE / "reader.py").read_bytes(), literals["READER_SOURCE"].encode() + (HERE / "reader_cli.py.fragment").read_bytes())
        runtime = (HERE / "carrier_runtime.js").read_bytes()
        for key in ("CHECKPOINT_VALIDATOR_SOURCE", "OWN_SHA256_SOURCE"):
            self.assertEqual(runtime.count(literals[key].encode()), 1)
        self.assertNotIn(b"eval(", runtime); self.assertNotIn(b"new Function", runtime)
        self.assertEqual(runtime.count(b"childProcess.spawnSync("), 1)

    def test_02_complete_exact_unicode(self):
        self.complete()

    def test_03_empty_fields_and_empty_request_id(self):
        self.set_carrier(system="", user="", request_id="")
        hashes, views, _ = self.complete(); self.assertEqual(views, 3)
        self.assertEqual(hashes["field_roots"]["/user"], sha(b""))

    def test_04_status_counterexamples_atomic(self):
        pending = self.view()
        for changes in ({"exit_code": 2}, {"exit_code": True}, {"exit_code": None}, {"session_id": 1}):
            bad = copy.deepcopy(pending); bad["result"].update(changes); self.reject(bad)
        bad = copy.deepcopy(pending); del bad["result"]["exit_code"]; self.reject(bad)
        self.assertEqual(self.confirm(pending)["exit_code"], 0)

    def test_05_explicit_outer_confirmation(self):
        pending = self.view()
        for confirm in ({"chunk_id": pending["result"]["chunk_id"], "outer_output_intact": False},
                        {"chunk_id": "wrong", "outer_output_intact": True},
                        {"chunk_id": "", "outer_output_intact": True},
                        {"chunk_id": pending["result"]["chunk_id"], "outer_output_intact": True, "extra": 1}):
            self.reject(pending, confirm)
        self.assertEqual(self.confirm(pending)["exit_code"], 0)

    def test_06_truncation_canonical_duplicate_and_budget(self):
        pending = self.view()
        for output in (pending["result"]["output"][:-3], "{}\n", '{"status":"ok","status":"ok"}\n', " " + pending["result"]["output"]):
            bad = copy.deepcopy(pending); bad["result"]["output"] = output; self.reject(bad)
        bad = copy.deepcopy(pending); bad["result"]["original_token_count"] = 16385; self.reject(bad)
        self.assertEqual(self.confirm(pending)["exit_code"], 0)

    def test_07_identity_and_reference_isolation(self):
        pending = self.view()
        for key, value in (("carrier_sha256", "sha256:" + "0"*64), ("request_sha256", "sha256:" + "1"*64), ("carrier_path", "/unrelated/wrong")):
            bad = copy.deepcopy(pending); document = json.loads(bad["result"]["output"]); document[key] = value
            bad["result"]["output"] = wire(document) + "\n"; self.reject(bad)
        bad = copy.deepcopy(pending); bad["reference"]["request_sha256"] = "sha256:" + "2"*64; self.reject(bad)
        request = self.request("confirm", pending=pending, confirmation={"chunk_id": pending["result"]["chunk_id"], "outer_output_intact": True})
        request["reference"]["request_sha256"] = "sha256:" + "3"*64
        self.assertEqual(self.call(request)["exit_code"], 2); self.assertIsNone(self.accepted())

    def test_08_cursors_lengths_and_false_eof(self):
        self.inventory(); pending = self.view("/system")
        for key, value in (("start_char", 1), ("start_utf8_byte", 1), ("end_char", 0), ("content_chars", 999), ("content_utf8_bytes", 999), ("next_char", 0), ("field_eof", False)):
            bad = copy.deepcopy(pending); document = json.loads(bad["result"]["output"]); document[key] = value
            bad["result"]["output"] = wire(document) + "\n"; self.reject(bad)
        self.assertEqual(self.confirm(pending)["exit_code"], 0)

    def test_09_system_before_user_and_gaps(self):
        self.inventory(); self.reject(self.view("/user"))
        self.reject(self.view("/system", 1))
        self.assertEqual(self.confirm(self.view("/system"))["exit_code"], 0)

    def test_10_exact_replay_and_conflicting_overlap(self):
        self.inventory(); pending = self.view("/system"); self.assertEqual(self.confirm(pending)["exit_code"], 0)
        before = json.loads(self.accepted()); self.assertEqual(self.confirm(pending)["exit_code"], 0)
        after = json.loads(self.accepted()); self.assertEqual(before["fields"], after["fields"])
        self.assertEqual(len(after["observations"]), len(before["observations"])+1)
        bad = copy.deepcopy(pending); document = json.loads(bad["result"]["output"])
        document["content"] = "X" + document["content"][1:]; bad["result"]["output"] = wire(document) + "\n"; self.reject(bad)

    def test_11_state_tamper_and_non_scalar_rejected(self):
        self.complete(); state = json.loads(self.accepted())
        state["fields"]["/user"]["content"] += "changed"; self.state_path.write_text(wire(state)+"\n")
        before = self.accepted(); self.assertEqual(self.call(self.request("hash"))["exit_code"], 2); self.assertEqual(self.accepted(), before)
        state["fields"]["/user"]["content"] = "\ud800"
        self.state_path.write_text(json.dumps(state, sort_keys=True, ensure_ascii=True, separators=(",", ":"))+"\n")
        before = self.accepted(); self.assertEqual(self.call(self.request("hash"))["exit_code"], 2); self.assertEqual(self.accepted(), before)

    def test_12_confirm_and_hash_without_carrier_reads(self):
        self.complete(); pending = self.view("/user")
        self.carrier.unlink()
        self.assertEqual(self.confirm(pending)["exit_code"], 0)
        actual = self.call(self.request("hash")); self.assertEqual(actual["exit_code"], 0)
        self.assertEqual(json.loads(actual["output"])["field_roots"]["/user"], sha(self.fields["user"].encode()))

    def test_13_hash_requires_both_eof_without_mutation(self):
        self.inventory(); self.assertEqual(self.confirm(self.view("/system"))["exit_code"], 0)
        before = self.accepted(); actual = self.call(self.request("hash"))
        self.assertEqual(actual["exit_code"], 2); self.assertEqual(self.accepted(), before)
        self.assertNotIn("field_roots", json.loads(actual["output"]))

    def test_14_lock_atomic_failure_and_concurrent_replay(self):
        pending = self.view(); request = self.request("confirm", pending=pending, confirmation={"chunk_id": pending["result"]["chunk_id"], "outer_output_intact": True})
        lock = Path(str(self.state_path)+".lock"); lock.write_text("own generic held lock")
        self.assertEqual(self.call(request)["exit_code"], 2); self.assertIsNone(self.accepted()); lock.unlink()
        first = self.start(request); second = self.start(request)
        responses = [self.finish(first)[0], self.finish(second)[0]]
        self.assertIn(0, [item["exit_code"] for item in responses])
        for item in responses:
            if item["exit_code"] != 0:
                self.assertEqual(json.loads(item["output"])["code"], "OWN_SESSION_BUSY")
                self.assertEqual(self.call(request)["exit_code"], 0)
        self.assertEqual(len(json.loads(self.accepted())["observations"]), 2)
        self.assertFalse(list(self.sessions.glob("*.temporary-*"))); self.assertFalse(lock.exists())

    def test_15_large_multislice_original_hashes(self):
        global LARGE_OBSERVATION
        self.set_carrier(system="Leading 🙂é\r\n" + "s"*18000, user="🙂e\u0301 begin\n" + "x"*450001 + "\nUnicode-tail α🙂e\u0301\\'\t")
        hashes, views, maximum = self.complete()
        self.assertGreater(len(self.fields["user"]), 450000); self.assertGreater(views, 50)
        LARGE_OBSERVATION = {"decoded_user_chars": len(self.fields["user"]), "decoded_user_utf8_bytes": len(self.fields["user"].encode()),
                             "explicit_view_calls": views, "max_field_view_output_bytes": maximum, "field_roots": hashes["field_roots"],
                             "both_confirmed_eof": hashes["field_eof"], "actual_subprocess_status_preserved_per_call": True,
                             "generic_test_harness_only": True, "no_author_automatic_retrieval": True}

    def test_16_posix_json_quotes_are_data_and_source_guard(self):
        self.carrier = self.directory / "quote'$(printf data)`data`é🙂.json"; self.set_carrier()
        self.complete()
        request = self.request("hash"); request["code"]["runtime_sha256"] = "sha256:"+"0"*64
        before = self.accepted(); actual = self.call(request)
        self.assertNotEqual(actual["exit_code"], 0); self.assertEqual(self.accepted(), before)

    def test_17_closed_requests_and_wrong_session(self):
        for request in (self.request("unknown"), {**self.request("hash"), "extra": 1}, {**self.request("hash"), "session_path": str(self.sessions/"wrong.json")}):
            self.assertEqual(self.call(request)["exit_code"], 2); self.assertIsNone(self.accepted())
        request = self.request("hash"); encoded = wire(request)
        duplicate = encoded[:-1] + ',"operation":"hash"}'
        command = protocol.runtime_command(request).rsplit(" ", 1)[0]
        # Preserve the exact fixed launcher, changing only its JSON data argument.
        import shlex
        command = shlex.quote(protocol.PYTHON_PATH)+" -I -B -c "+shlex.quote(protocol.LAUNCHER_SOURCE)+" "+shlex.quote(duplicate)
        self.assertEqual(self.call(request, command)["exit_code"], 2); self.assertIsNone(self.accepted())

    def test_18_compact_template_syntax_and_exact_forwarding(self):
        recipes = [protocol.runtime_initial_template(self.reference,self.code), protocol.runtime_next_template(self.reference,self.code),
                   protocol.runtime_confirm_template(self.reference,self.code), protocol.runtime_hash_template(self.reference,self.code)]
        for index, recipe in enumerate(recipes):
            source = self.directory / ("recipe-%d.js" % index); source.write_text(recipe)
            checked = subprocess.run(["/usr/bin/node", "--input-type=module", "--check"], input=recipe.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(recipe.count("await tools.exec_command("),1); self.assertEqual(recipe.count("text(ACTUAL_RESULT);"),1)
            self.assertNotIn("checkpointAdvance", recipe); self.assertNotIn("ownViewSha256", recipe)
            if index<2: self.assertLess(recipe.index("store(PENDING_KEY,"),recipe.index("text(ACTUAL_RESULT);"))
        message = protocol.runtime_agent_message(self.reference,self.code)
        self.assertIn(str(self.state_path),message); self.assertIn(self.reference["request_sha256"],message)
        self.assertLess(len(recipes[2].encode()),5000); self.assertLess(len(recipes[3].encode()),5000)


def main():
    global OUTPUT
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True);args=parser.parse_args()
    OUTPUT=args.output.resolve();OUTPUT.mkdir(exist_ok=False)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeControls)
    ids=[case.id() for case in suite];result=unittest.TextTestRunner(verbosity=2).run(suite)
    summary={"format":"verislop.runtime020-creator-control-result/1","pid":os.getpid(),"control_count":len(ids),"control_ids":ids,
             "passed":result.wasSuccessful(),"failures":len(result.failures),"errors":len(result.errors),"actual_runtime_subprocess_calls":TOTAL_CALLS,
             "large_field":LARGE_OBSERVATION,"mock_tool_chunk_ids":True,"model_calls":0,"gate_fixture_inputs":False,"qualification_authority":False}
    (OUTPUT/"result.json").write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps(summary))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=="__main__":main()
