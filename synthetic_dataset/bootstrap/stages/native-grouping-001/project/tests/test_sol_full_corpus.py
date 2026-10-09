"""Authored transport, scoring and resume checks; no measured model calls."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from synthetic_dataset.arm_worker import RAW_SYSTEM
from synthetic_dataset.tools import sol_full_corpus as poc
from synthetic_dataset.tools import sol_full_corpus_worker as worker
from synthetic_dataset.tools import sol_data_pipeline_worker as transport
from synthetic_dataset.tools import luna_worker
from verislop import canonical
from verislop.providers import config
from verislop.providers.broker import Broker


class FullCorpusProtocolTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="authored-full-sol-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.dataset = self.repo / "synthetic_dataset"
        self.dataset.mkdir()
        (self.repo / "fixture.py").write_bytes(b"# Authored source fixture\n")
        (self.dataset / "prompt.txt").write_text("Authored identity request; return its JSON input.")
        self.cases = [{"id": "authored-public", "visibility": "public", "input": {"value": 5}, "expected": {"value": 5}},
                      {"id": "authored-hidden", "visibility": "hidden", "input": ["λ", 1, True], "expected": ["λ", 1, True]}]
        (self.dataset / "cases.json").write_bytes(poc.encode(self.cases))
        self.tasks = {f"T{i:03d}": {"id": f"T{i:03d}", "title": "Authored identity fixture", "category": "authored",
                                     "prompt_path": "prompt.txt", "cases_path": "cases.json"} for i in range(100)}
        self.manifest = {"dataset_root": "sha256:" + "1" * 64, "tasks": 100,
                         "files": {name: poc.digest((self.dataset / name).read_bytes()) for name in ("prompt.txt", "cases.json")},
                         "generator_hashes": {}}
        (self.dataset / "manifest.json").write_bytes(poc.encode(self.manifest))
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(poc, "REPO", self.repo))
        stack.enter_context(patch.object(poc, "ROOT", self.dataset))
        stack.enter_context(patch.object(poc, "task_inventory", return_value=self.tasks))
        stack.enter_context(patch.object(poc.bench, "verify_dataset", return_value=self.manifest))
        stack.enter_context(patch.object(poc, "source_inventory", side_effect=lambda: {"fixture.py": poc.digest((self.repo / "fixture.py").read_bytes())}))
        self.cohort = self.root / "cohort"
        self.protocol = poc.prepare(self.cohort)
        self.selection = self.protocol["pair_order"][0]
        self.task = self.tasks[self.selection["task"]]
        self.directory = self.cohort / "artifacts" / self.task["id"] / "raw"

    def request(self, *, arm="raw", rid="0001"):
        selection = {**self.selection, "arm": arm}
        transport.atomic_json(self.cohort / "active-arm.json", {**selection, "phase": "generation"})
        mailbox = self.cohort / "artifacts" / self.task["id"] / arm / "mailbox"
        request = {"format": "verislop.collaboration-request/0.1", "request_id": rid,
                   "transport": "collaboration", "requested_model": worker.MODEL, "agent": "author", "instance": "raw/1",
                   "purpose": "raw-coding", "system": RAW_SYSTEM, "user": (self.dataset / "prompt.txt").read_text(),
                   "max_response_bytes": transport.MAX_RESPONSE_BYTES, "requested_max_output_tokens": 8192,
                   "output_token_limit_enforced": False}
        poc.write_once(mailbox / f"request-{rid}.json", request)
        return poc.pending_request(self.cohort)

    def envelope(self, pending, *, agent="/root/authored_full_sol_leaf", text="exact final λ\n"):
        value = {key: pending[key] for key in ("task", "arm", "request_sha256", "supplemental_protocol_root", "source_root", "dataset_root",
                      "spawn_message_sha256", "carrier_path", "carrier_sha256", "model_override", "fork_turns")}
        value.update(transport="collaboration", requested_model=worker.MODEL, relay_mode="file",
                     request_id=pending["request"]["request_id"], agent_task_id=agent, text=text, model_identity_attested=False)
        return value

    def completed_raw(self, source="def solve(data):\n    return data\n", *, score=True):
        # Exercise the actual bounded transport in a thread, then actual isolated graders.
        mailbox = transport.MailboxTransport(self.directory / "mailbox", 1, poll_seconds=0.01)
        resolved = config.resolve(worker.configuration(), worker.endpoint_profiles()["profiles"])
        broker = Broker(resolved, self.directory / "transcripts")
        results, errors = [], []
        def call():
            try:
                results.append(mailbox.call(broker, "author", "raw/1", RAW_SYSTEM,
                                             (self.dataset / "prompt.txt").read_text(), "raw-coding"))
            except Exception as exc:
                errors.append(exc)
        transport.atomic_json(self.cohort / "active-arm.json", {**self.selection, "phase": "generation"})
        poc.write_once(self.directory / "cli-invocation.json", {"argv": []})
        command = [poc.sys.executable, "-m", "synthetic_dataset.tools.sol_full_corpus_worker", "--cohort", str(self.cohort), "--task", self.task["id"], "--arm", "raw"]
        poc.write_once(self.directory / "invocation.json", {"argv": command, "cwd": str(self.repo), "cli_argv": [], "candidate_inputs": []})
        thread = threading.Thread(target=call)
        thread.start()
        deadline = time.monotonic() + 5
        while not (self.directory / "mailbox/request-0001.json").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((self.directory / "mailbox/request-0001.json").exists())
        pending = poc.pending_request(self.cohort)
        text = json.dumps({"files": {"solution.py": source}}, ensure_ascii=False)
        poc.submit_response(self.cohort, self.envelope(pending, text=text))
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual([], errors)
        transport.raw_artifact(results[0].text, self.directory)
        poc.write_once(self.directory / "worker-result.json", {"status": "ARTIFACT", "exit_code": 0})
        poc.write_once(self.directory / "stdout.json", {"status": "ARTIFACT"})
        return poc.score_arm(self.cohort, self.selection) if score else None

    def test_frozen_full_selection_alternates_preserves_sol_and_bounds(self):
        self.assertEqual(200, len(self.protocol["pair_order"]))
        self.assertEqual(["raw", "verislop", "verislop", "raw"], [row["arm"] for row in self.protocol["pair_order"][:4]])
        self.assertEqual((1, 128, 24, 2, 2, 200), tuple(self.protocol[field] for field in
                         ("raw_calls_per_task", "strict_calls_per_task", "max_calls_per_instance", "contract_repair_rounds", "independent_repeats", "cases")))
        self.assertEqual("gpt-6.1-sol", worker.MODEL)
        self.assertEqual("gpt-6-luna", luna_worker.MODEL)
        self.assertEqual("gpt-6-luna", luna_worker.configuration()["agents"]["author"]["model_ref"])
        self.assertFalse(self.protocol["model_identity_attested"])
        for field in ("model_generation_deadline", "proof_search_deadline", "review_tier_deadline", "input_tokens", "output_tokens"):
            self.assertIsNone(self.protocol[field])
        self.assertEqual(self.protocol, poc.verify_inputs(self.cohort))
        with self.assertRaises(ValueError):
            poc.prepare(self.cohort)

    def test_strict_invocation_preserves_all_requested_gates_without_positive_candidates(self):
        argv = worker.cli_argv(self.cohort, self.task)
        self.assertEqual("TESTED", argv[argv.index("--require-state") + 1])
        self.assertEqual("test_campaign", argv[argv.index("--endpoint") + 1])
        self.assertEqual("0", argv[argv.index("--budget-seconds") + 1])
        self.assertEqual("2", argv[argv.index("--repair-rounds") + 1])
        self.assertEqual("strict", argv[argv.index("--policy") + 1])
        self.assertIn("--require-tests", argv)
        self.assertFalse(any("candidate" in arg or arg.startswith("--bridge-") for arg in argv))

    def test_binding_rejects_wrong_source_corpus_task_carrier_model_or_freshness(self):
        pending = self.request()
        envelope = self.envelope(pending)
        for key, value in (("source_root", "wrong"), ("dataset_root", "wrong"), ("task", "T999"), ("arm", "verislop"),
                           ("model_override", "gpt-6-luna"), ("fork_turns", "all"), ("carrier_sha256", "wrong"),
                           ("spawn_message_sha256", "wrong"), ("supplemental_protocol_root", "wrong"), ("model_identity_attested", True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                poc.submit_response(self.cohort, {**envelope, key: value})
        publication = poc.submit_response(self.cohort, envelope)
        self.assertEqual(envelope, poc.bench.load(Path(publication["published"])))
        with self.assertRaises(ValueError):
            poc.submit_response(self.cohort, envelope)
        next_arm = self.request(arm="verislop")
        with self.assertRaisesRegex(ValueError, "already used"):
            poc.submit_response(self.cohort, self.envelope(next_arm))

    def test_empty_final_is_preserved_as_bound_transport_failure(self):
        pending = self.request()
        publication = poc.submit_response(self.cohort, self.envelope(pending, text=""))
        envelope = poc.bench.load(Path(publication["published"]))
        self.assertEqual("", envelope["text"])
        self.assertEqual(transport.EMPTY_FINAL_ERROR, envelope["transport_error"])

    def test_withheld_marker_carrier_and_source_mutation_fail_closed(self):
        pending = self.request()
        carrier = Path(pending["carrier_path"])
        original = carrier.read_bytes()
        carrier.chmod(0o600)
        carrier.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "carrier differs"):
            poc.pending_request(self.cohort)
        carrier.write_bytes(original)
        request_path = Path(pending["request_path"])
        request = poc.bench.load(request_path)
        request["user"] += " synthetic_dataset/cases/"
        transport.atomic_json(request_path, request)
        with self.assertRaisesRegex(ValueError, "Withheld"):
            poc.pending_request(self.cohort)
        (self.repo / "fixture.py").write_bytes(b"changed source")
        with self.assertRaisesRegex(ValueError, "INPUT_MUTATION"):
            poc.verify_inputs(self.cohort)

    def test_two_real_fresh_graders_score_exact_artifact_and_resume_never_reruns(self):
        row = self.completed_raw()
        self.assertTrue(row["successful_task"], row)
        self.assertEqual((1, 1, 4, 4), tuple(row[key] for key in ("public_passed", "hidden_passed", "executed_observations", "passed_observations")))
        observed = poc.bench.load(self.directory / "observations.json")
        self.assertEqual(2, len(observed["repeats"]))
        self.assertTrue(all(repeat["isolation"].get("network_namespace") and repeat["isolation"].get("filesystem_read_isolation") for repeat in observed["repeats"]))
        with patch.object(poc.subprocess, "Popen", side_effect=AssertionError("model arm restarted")), patch.object(poc.bench, "grade", side_effect=AssertionError("grader rerun")):
            self.assertEqual(row, poc.run_arm(self.cohort, self.selection))
        self.assertEqual(1, poc.verify(self.cohort)["fresh_agents"])
        progress = poc.update_progress(self.cohort)
        self.assertEqual((1, 100, 200), (progress["arms"]["raw"]["completed_tasks"], progress["arms"]["raw"]["total_tasks"], progress["arms"]["raw"]["total_case_slots"]))

    def test_finite_wrong_output_retains_concrete_observations(self):
        row = self.completed_raw("def solve(data):\n    return None\n")
        self.assertFalse(row["successful_task"])
        self.assertEqual((0, 0, 4, 0), tuple(row[key] for key in ("public_passed", "hidden_passed", "executed_observations", "passed_observations")))
        self.assertIsNone(row["held_out_results"][0]["observations"][0]["observed"])

    def test_completed_origin_or_observation_mutation_is_not_rescored_or_overwritten(self):
        row = self.completed_raw()
        (self.directory / "artifact/solution.py").write_text("def solve(data):\n    return None\n")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            poc.validate_score(self.cohort, self.selection, row)
        self.assertEqual(row, poc.bench.load(self.directory / "score.json"))
        observed = poc.bench.load(self.directory / "observations.json")
        observed["repeats"][0]["results"][0]["observed"] = None
        transport.atomic_json(self.directory / "observations.json", observed)
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            poc.validate_score(self.cohort, self.selection, row)

    def test_missing_artifact_is_unexecuted_failed_scope_and_partial_resume_preserves_failure(self):
        self.directory.mkdir(parents=True)
        with patch.object(poc.subprocess, "Popen", side_effect=AssertionError("partial arm restarted")):
            row = poc.run_arm(self.cohort, self.selection)
        self.assertEqual("INFRASTRUCTURE_FAILURE", row["workflow_status"])
        self.assertEqual((0, 0, 0, 1, 1), tuple(row[key] for key in ("hidden_passed", "public_passed", "executed_observations", "hidden_total", "public_total")))
        self.assertEqual("CONTROLLER_INTERRUPTED", poc.bench.load(self.directory / "worker-result.json")["status"])
        self.assertFalse(row["successful_task"])

    def test_live_partial_worker_refuses_duplicate_generation(self):
        self.directory.mkdir(parents=True)
        poc.write_once(self.directory / "process.json", {"pid": os.getpid()})
        with self.assertRaisesRegex(ValueError, "still live"):
            poc.run_arm(self.cohort, self.selection)
        self.assertFalse((self.directory / "worker-result.json").exists())

    def test_completed_score_counters_usage_status_or_native_fields_cannot_be_fabricated(self):
        row = self.completed_raw()
        for key, value in (("passed_observations", 999999), ("executed_observations", 0), ("native_status", "invented"),
                           ("worker_exit_code", 19), ("workflow_status", "BLOCKED"), ("usage", {"calls": 0}),
                           ("cli_stages", [{"stage": "invented", "status": "PASS"}]), ("native_tested", True)):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "score differs"):
                poc.validate_score(self.cohort, self.selection, {**row, key: value})

    def test_interrupted_grader_attempt_is_not_repeated_on_resume(self):
        self.completed_raw(score=False)
        with patch.object(poc.bench, "grade", side_effect=KeyboardInterrupt("authored lost grader")):
            with self.assertRaises(KeyboardInterrupt):
                poc.score_arm(self.cohort, self.selection)
        real_grade = poc.bench.grade
        with patch.object(poc.bench, "grade", wraps=real_grade) as grade:
            row = poc.score_arm(self.cohort, self.selection)
        self.assertEqual(1, grade.call_count)
        self.assertEqual("INFRASTRUCTURE_FAILURE", row["workflow_status"])
        self.assertEqual((2, 2), (row["executed_observations"], row["passed_observations"]))
        self.assertEqual("InterruptedGrader", row["grading_infrastructure_errors"][0]["type"])

    def test_actual_oracle_and_case_paths_are_rejected(self):
        pending = self.request()
        path = Path(pending["request_path"])
        request = poc.bench.load(path)
        for marker in ("generate_algorithms.py", "generate_graph_systems.py", "generate_text_data.py", "tasks/G03/cases.json"):
            transport.atomic_json(path, {**request, "user": request["user"] + " " + marker})
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, "Withheld"):
                poc.pending_request(self.cohort)

    def test_native_cli_infrastructure_failure_remains_distinct(self):
        selection = {**self.selection, "arm": "verislop"}
        directory = self.cohort / "artifacts" / self.task["id"] / "verislop"
        poc.write_once(directory / "worker-result.json", {"status": "CLI_RETURNED", "exit_code": 3})
        poc.write_once(directory / "stdout.json", {"status": "INFRASTRUCTURE_FAILURE", "diagnostics": [{"code": "PROVIDER_FAILURE"}]})
        row = poc.score_arm(self.cohort, selection)
        self.assertEqual("INFRASTRUCTURE_FAILURE", row["workflow_status"])
        self.assertFalse(row["successful_task"])

    def test_unsealed_summary_resume_finishes_only_finalization(self):
        # Exact finalization control flow is exercised with authored completed rows;
        # corpus identity and scoring remain separately exercised above.
        row = self.completed_raw()
        rows = [dict(row, task=f"T{i:03d}", task_id=f"T{i:03d}", arm=arm) for i in range(100) for arm in poc.ARMS]
        with patch.object(poc, "completed_rows", return_value=rows), patch.object(poc, "verify", return_value={"status": "PASS"}):
            summary = poc.update_progress(self.cohort, status="COMPLETE")
            poc.write_once(self.cohort / "SUMMARY.json", summary)
            with patch.object(poc, "run_arm", side_effect=AssertionError("generation rerun")), patch.object(poc.bench, "grade", side_effect=AssertionError("grader rerun")):
                self.assertEqual(0, poc.run(self.cohort))
            self.assertTrue((self.cohort / "EVIDENCE-MANIFEST.json").exists())
            self.assertEqual(b"".join(poc.encode(value) for value in rows), (self.cohort / "results.jsonl").read_bytes())

    def test_write_once_never_replaces_original_bytes(self):
        path = self.root / "once.json"
        poc.write_once(path, {"value": "λ"})
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            poc.write_once(path, {"value": "other"})
        self.assertEqual(original, path.read_bytes())
        self.assertFalse(list(path.parent.glob(".publish-*")))


if __name__ == "__main__":
    unittest.main()
