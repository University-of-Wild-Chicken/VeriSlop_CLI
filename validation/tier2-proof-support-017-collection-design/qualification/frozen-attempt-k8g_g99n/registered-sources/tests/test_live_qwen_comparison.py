"""Offline protocol/guard tests; no model calls or historical benchmark rescoring."""
from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from verislop import canonical
from verislop.errors import InfrastructureError
from synthetic_dataset.tools import live_qwen_comparison as live


class LiveQwenComparisonTests(unittest.TestCase):
    def test_pair_order_is_alternating_and_defined(self):
        self.assertEqual([live.pair_order(i) for i in range(3)], [("raw", "strict"), ("strict", "raw"), ("raw", "strict")])
        for invalid in (-1, True, "1"):
            with self.assertRaises(ValueError):
                live.pair_order(invalid)

    def test_inventory_includes_new_runtime_and_every_top_level_harness(self):
        files = live.source_inventory()
        for rel in ("verislop/autonomous.py", "verislop/agent_memory.py", "verislop/contract_refutation.py",
                    "synthetic_dataset/arm_worker.py", "synthetic_dataset/tools/live_qwen_comparison.py"):
            self.assertIn(rel, files)
        self.assertFalse(any(path.startswith("synthetic_dataset/diagnostics/") for path in files))
        self.assertEqual(files, dict(sorted(files.items())))

    def test_prepare_has_no_inference_and_pins_actual_source_and_protocol(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(live.Broker, "call", side_effect=AssertionError("No inference")):
            cohort = Path(root) / "cohort"
            protocol = live.prepare(cohort)
            freeze = live.verify_inputs(cohort)
            self.assertEqual(protocol["source_root"], canonical.digest_json(live.source_inventory()))
            self.assertEqual(freeze["protocol_sha256"], canonical.digest_file(cohort / "PROTOCOL.json"))
            self.assertEqual(protocol["logical_call_limits"], {"raw": 1, "strict": 128})
            self.assertEqual(protocol["context_window_tokens"], 32768)
            self.assertTrue(protocol["max_output_tokens_enforced"])
            self.assertEqual(protocol["generation_deadlines"]["outer_seconds"], None)
            cfg = canonical.load_file(cohort / "execution-config.json")
            self.assertEqual(cfg["providers"]["local"]["request_timeout_seconds"], None)
            self.assertEqual(cfg["review"]["budgets"]["max_calls_per_instance"], 24)
            with self.assertRaises(live.CheckFailure):
                live.prepare(cohort)
            (cohort / "PROTOCOL.json").write_bytes(canonical.dumps({**protocol, "repair_rounds": 99}))
            with self.assertRaisesRegex(live.CheckFailure, "protocol changed"):
                live.verify_inputs(cohort)

    def test_shared_freeze_rejects_another_source_version_without_creating_cohort(self):
        with tempfile.TemporaryDirectory() as root:
            cohort = Path(root) / "cohort"
            with self.assertRaises(live.CheckFailure):
                live.prepare(cohort, frozen={})
            self.assertFalse(cohort.exists())

    def test_staged_source_mutation_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            cohort = Path(root) / "cohort"
            live.prepare(cohort)
            (cohort / "execution-source/verislop/autonomous.py").write_text("changed")
            with self.assertRaisesRegex(live.CheckFailure, "staged source changed"):
                live.verify_inputs(cohort)

    def test_native_cli_has_no_positive_artifacts_or_generation_deadline(self):
        args = live.strict_argv(Path("/tmp/cohort"), Path("/tmp/cohort/task/strict"), live.TASKS[0])
        self.assertEqual(args[args.index("--budget-seconds") + 1], "0")
        self.assertEqual(args[args.index("--repair-rounds") + 1], "2")
        self.assertEqual(args[args.index("--require-state") + 1], "TESTED")
        self.assertEqual(args[args.index("--policy") + 1], "strict")
        self.assertFalse(any(arg.startswith("--candidate") or arg.startswith("--bridge-") for arg in args))

    def test_observer_guard_preserves_original_call_arguments_and_native_budget(self):
        with tempfile.TemporaryDirectory() as root:
            observer = live.ObservedCalls(Path(root), 2)
            native_budget = object()
            broker = SimpleNamespace(budget=native_budget, validate_prompt=mock.Mock())
            observer.original_call = mock.Mock(return_value="answer")
            self.assertEqual(observer.call(broker, "author", "x", "system", "user", "purpose"), "answer")
            observer.call(broker, "critic", "y", "s2", "u2", "p2")
            with self.assertRaises(InfrastructureError):
                observer.call(broker, "author", "x", "s3", "u3", "p3")
            self.assertIs(broker.budget, native_budget)
            self.assertEqual(observer.original_call.call_count, 2)
            self.assertEqual(observer.original_call.call_args.args, (broker, "critic", "y", "s2", "u2", "p2"))
            self.assertEqual(observer.state["calls"], 2)
            self.assertTrue(observer.state["call_budget_exhausted"])
            self.assertFalse((Path(root) / "request-003.json").exists())

    def test_raw_system_and_prompt_are_exact_originals_not_oracle_material(self):
        from synthetic_dataset.arm_worker import RAW_SYSTEM
        self.assertEqual(live.RAW_SYSTEM, RAW_SYSTEM)
        for task in live.TASKS:
            prompt = (live.PROTOCOL / f"{task}.txt").read_text()
            self.assertFalse(any(marker in prompt for marker in ("expected_wire", "withheld/", "PREREGISTRATION.json")))

    def test_summary_counts_cases_separately_from_native_success(self):
        rows = []
        for task in live.TASKS:
            for arm in live.CALL_LIMITS:
                rows.append({"task": task, "arm": arm, "status": "PASS" if arm == "raw" else "BLOCKED",
                    "successful_task": arm == "raw", "independent_cases_passed": 160, "observations": 320,
                    "passed_observations": 320, "logical_calls": 1})
        summary = live.comparison_summary(rows, "sha256:test")
        self.assertEqual(summary["arms"]["raw"]["successful_tasks"], 3)
        self.assertEqual(summary["arms"]["strict"]["successful_tasks"], 0)
        self.assertEqual(summary["arms"]["strict"]["independent_cases_passed"], 480)
        self.assertEqual(summary["paired_tasks"]["raw_only"], 3)

    def test_raw_origin_rejects_forged_model_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory / "transcripts").mkdir()
            (directory / "artifact").mkdir()
            source = "def solve(data):\n    return data\n"
            (directory / "artifact/solution.py").write_text(source)
            prompt = (live.PROTOCOL / f"{live.TASKS[0]}.txt").read_text()
            entry = {"agent": "author", "instance": "raw/1", "purpose": "raw-coding", "system": live.RAW_SYSTEM,
                "user": prompt, "system_sha256": canonical.digest(live.RAW_SYSTEM.encode()), "user_sha256": canonical.digest(prompt.encode()),
                "requested_model": live.MODEL, "returned_model": live.MODEL, "model_digest_sha256": live.MODEL_DIGEST,
                "context_window_tokens": live.CONTEXT, "response": canonical.dumps({"files": {"solution.py": source}}).decode()}
            transcript = directory / "transcripts/1.json"
            transcript.write_bytes(canonical.dumps(entry))
            (directory / "usage.json").write_bytes(canonical.dumps({"calls": 1, "responses": 1, "call_budget_exhausted": False}))
            self.assertEqual(live.raw_origin_audit(directory, live.TASKS[0], {})["status"], "PASS")
            transcript.write_bytes(canonical.dumps({**entry, "response": canonical.dumps({"files": {"solution.py": source}, "extra": True}).decode()}))
            self.assertEqual(live.raw_origin_audit(directory, live.TASKS[0], {})["status"], "BLOCK")
            transcript.write_bytes(canonical.dumps({**entry, "model_digest_sha256": "forged"}))
            self.assertEqual(live.raw_origin_audit(directory, live.TASKS[0], {})["status"], "BLOCK")
            transcript.write_bytes(canonical.dumps(entry))
            (directory / "artifact/solution.py").write_text(source + "# added after generation\n")
            self.assertEqual(live.raw_origin_audit(directory, live.TASKS[0], {})["status"], "BLOCK")

    def test_controller_has_no_subprocess_generation_timeout(self):
        with tempfile.TemporaryDirectory() as root:
            cohort = Path(root)
            def row(_cohort, _directory, task, arm, code):
                return {"task": task, "arm": arm, "status": "BLOCKED", "successful_task": False,
                    "independent_cases_passed": 0, "observations": 0, "passed_observations": 0,
                    "logical_calls": 1, "frozen_inputs_unchanged": True}
            with mock.patch.object(live, "verify_inputs", return_value={"root": "sha256:test"}), \
                    mock.patch.object(live.subprocess, "run", return_value=SimpleNamespace(returncode=2)) as run, \
                    mock.patch.object(live, "score_arm", side_effect=row):
                summary = live.run(cohort)
            self.assertEqual(run.call_count, 6)
            self.assertEqual(summary["paired_tasks"]["neither"], 3)
            for call in run.call_args_list:
                self.assertNotIn("timeout", call.kwargs)

    def test_authored_case_runs_twice_in_fresh_real_harnesses(self):
        # Authored fixture independent of preregistered measurement cases.
        with tempfile.TemporaryDirectory() as root:
            artifact = Path(root) / "artifact"
            artifact.mkdir()
            (artifact / "solution.py").write_text("def solve(data):\n    return {'value': data['value'] + 1}\n")
            case = {"id": "authored", "input_wire": {"dict": {"value": {"int": "2"}}},
                    "expected_wire": {"dict": {"value": {"int": "3"}}}}
            original_load = canonical.load_file
            def fixture_load(path):
                if Path(path).parent.name == "withheld":
                    return {"cases": [case]}
                return original_load(path)
            with mock.patch.object(live, "CASES", 1), mock.patch.object(canonical, "load_file", side_effect=fixture_load):
                result = live.raw_check(artifact, live.TASKS[0])
            self.assertEqual(result["status"], "PASS", result["diagnostics"])
            self.assertEqual(result["passed_cases"], 1)
            self.assertEqual(result["observations"], 2)
            self.assertEqual(len(result["isolation"]), 2)
            self.assertTrue(result["input_bytes_unchanged"])


if __name__ == "__main__":
    unittest.main()
