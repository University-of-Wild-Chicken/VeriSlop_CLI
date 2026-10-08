"""Concrete correctness checks for paired benchmark scoring and actual CLI invocation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from synthetic_dataset import arm_worker
from synthetic_dataset.benchmark import artifact_files, cli_success, configuration, grade, resolve_cli_package, run_arm, summarize, write
from synthetic_dataset.build_dataset import ROOT
from verislop import schemas
from verislop.providers.broker import Broker
from verislop.providers import adapters


class SyntheticBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-benchmark-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cases = [{"id": "zero", "input": [], "expected": 0, "visibility": "hidden"},
                      {"id": "two", "input": [1, 2], "expected": 3, "visibility": "hidden"}]

    def strict_result(self, package):
        stages = [{"stage": stage, "status": "PASS"} for stage in
                  ("formalize", "prove", "accept", "export", "review:formal_contract",
                   "generate", "link", "test", "review:release")]
        result = {"status": "PASS", "summary": {"active_package": str(package), "stages": stages}}
        report = {"terminal_status": "VERIFIED", "tier": {"requested": 0, "target": "python",
                  "endpoint": "test_campaign", "require_state": "TESTED"},
                  "blocking_reasons": [], "infrastructure_errors": [], "obligations": {"O1": {
                  "required": True, "required_milestones": ["PROVED", "IMPLEMENTED", "LINKED", "TESTED"],
                  "outcomes": {"PROVED": "PASS", "IMPLEMENTED": "PASS", "LINKED": "PASS", "TESTED": "PASS"}}}}
        return result, report

    def test_correct_code_wrong_code_and_bool_integer_are_distinguished(self):
        for source, passed in (("def solve(data): return sum(data)", 2),
                               ("def solve(data): return 0", 1),
                               ("def solve(data): return False", 0)):
            scores, _ = grade({"solution.py": source.encode()}, "solution.py", self.cases, 1)
            self.assertEqual(sum(s["status"] == "PASS" for s in scores), passed)

    def test_timeout_and_exception_are_failures(self):
        for source in ("def solve(data):\n while True: pass\n", "def solve(data): raise ValueError('test')"):
            scores, _ = grade({"solution.py": source.encode()}, "solution.py", self.cases, 0.05)
            self.assertTrue(all(s["status"] == "FAIL" for s in scores))
            self.assertTrue(all("error" in s for s in scores))

    def test_missing_artifact_fails_every_case(self):
        scores, isolation = grade({}, None, self.cases, 1)
        self.assertEqual([s["status"] for s in scores], ["FAIL", "FAIL"])
        self.assertEqual(isolation, {})

    def test_reference_directory_is_unavailable_to_candidate(self):
        outside = self.root / "hidden-reference.txt"
        outside.write_text("expected secret")
        code = f"def solve(data):\n return open({str(outside)!r}).read()\n"
        scores, isolation = grade({"solution.py": code.encode()}, "solution.py", self.cases, 1)
        self.assertTrue(all(s["status"] == "FAIL" for s in scores))
        self.assertTrue(isolation["network_namespace"])
        self.assertTrue(all(s["error"]["type"] == "FileNotFoundError" for s in scores))

    def test_ambiguous_solve_objects_are_not_selected(self):
        artifact = self.root / "artifact"
        artifact.mkdir()
        for name in ("a.py", "b.py"):
            (artifact / name).write_text("def solve(data): return data\n")
        files, entry = artifact_files("raw", self.root)
        self.assertEqual(len(files), 2)
        self.assertIsNone(entry)

    def test_actual_repaired_package_supplies_artifacts_and_preserves_failed_parent(self):
        parent, child = self.root / "package", self.root / "package-repair-01"
        for package, value in ((parent, 0), (child, 3)):
            (package / "implementation").mkdir(parents=True)
            (package / "implementation/solution.py").write_text(f"def solve(data): return {value}\n")
        write(parent / "report.json", {"terminal_status": "BLOCKED"})
        pipeline, _ = self.strict_result(child)
        files, entry = artifact_files("verislop", self.root, pipeline)
        self.assertEqual(entry, "solution.py")
        self.assertIn(b"return 3", files[entry])
        self.assertEqual(resolve_cli_package(self.root, pipeline), child)
        self.assertEqual(json.loads((parent / "report.json").read_text())["terminal_status"], "BLOCKED")
        pipeline["summary"]["active_package"] = child.name
        self.assertEqual(resolve_cli_package(self.root, pipeline), child)

    def test_package_resolution_rejects_wrong_lineage_and_symlinks(self):
        for selected in (self.root.parent / "package", self.root / "other", self.root / "package-repair-00"):
            with self.assertRaises(ValueError):
                resolve_cli_package(self.root, {"summary": {"active_package": str(selected)}})
        (self.root / "package-repair-01").symlink_to(self.root / "package")
        with self.assertRaisesRegex(ValueError, "symlink"):
            resolve_cli_package(self.root, {"summary": {"active_package": "package-repair-01"}})
        for pipeline in ([1], {"summary": []}, {"summary": {"active_package": 1}}):
            with self.assertRaises(ValueError):
                resolve_cli_package(self.root, pipeline)

    def test_passed_case_scores_cannot_promote_blocked_or_incomplete_strict_workflow(self):
        pipeline, report = self.strict_result(self.root / "package")
        self.assertTrue(cli_success(pipeline, report, 0))
        self.assertFalse(cli_success(pipeline, report, 2))
        self.assertFalse(cli_success(pipeline, report, 0, timed_out=True))
        report["terminal_status"] = "BLOCKED"
        self.assertFalse(cli_success(pipeline, report, 0))
        report["terminal_status"] = "VERIFIED"
        report["obligations"]["O1"]["outcomes"]["TESTED"] = "UNSUPPORTED"
        self.assertFalse(cli_success(pipeline, report, 0))
        report["obligations"]["O1"]["outcomes"]["TESTED"] = "PASS"
        pipeline["summary"]["stages"][-1]["status"] = "BLOCKED"
        self.assertFalse(cli_success(pipeline, report, 0))
        pipeline["summary"]["stages"][-1]["status"] = "PASS"
        pipeline["summary"]["stages"].pop()
        self.assertFalse(cli_success(pipeline, report, 0))
        pipeline, report = self.strict_result(self.root / "package")
        report["tier"]["require_state"] = "PROVED"
        self.assertFalse(cli_success(pipeline, report, 0))
        report["tier"]["require_state"] = "TESTED"
        report["obligations"]["O1"]["required_milestones"].remove("TESTED")
        self.assertFalse(cli_success(pipeline, report, 0))

    def test_supervisor_grades_repaired_package_and_reports_actual_closure(self):
        dataset = self.root / "dataset"
        dataset.mkdir()
        (dataset / "grade_worker.py").write_bytes((ROOT / "grade_worker.py").read_bytes())
        write(dataset / "cases.json", self.cases)
        task = {"id": "fixture", "title": "sum", "category": "fixture",
                "prompt_path": "prompt.txt", "cases_path": "cases.json"}
        args = SimpleNamespace(arm_seconds=0, output_token_budget=262144, harness_calls=32, case_seconds=1)
        import subprocess
        actual_popen = subprocess.Popen

        def worker(command, **kwargs):
            if "synthetic_dataset.arm_worker" not in command:
                return actual_popen(command, **kwargs)
            directory = Path(command[command.index("--out") + 1])
            parent, child = directory / "package", directory / "package-repair-01"
            write(parent / "report.json", {"terminal_status": "BLOCKED"})
            (child / "implementation").mkdir(parents=True)
            (child / "implementation/solution.py").write_text("def solve(data): return sum(data)\n")
            pipeline, report = self.strict_result(child)
            write(child / "report.json", report)
            write(child / "package.json", {"stage_history": pipeline["summary"]["stages"]})
            from unittest.mock import Mock
            return SimpleNamespace(returncode=0, communicate=Mock(return_value=(json.dumps(pipeline).encode(), b"")))

        with patch("synthetic_dataset.benchmark.ROOT", dataset), patch("synthetic_dataset.benchmark.subprocess.Popen", side_effect=worker):
            row = run_arm(task, "verislop", 0, self.root, self.root / "config.json", args)
        self.assertTrue(row["successful_task"])
        self.assertTrue(row["strict_cli_success"])
        self.assertEqual(row["hidden_passed"], 2)
        self.assertEqual(row["active_package"], "artifacts/fixture/verislop/package-repair-01")
        self.assertEqual(row["cli_report"], "artifacts/fixture/verislop/package-repair-01/report.json")

    def test_full_cli_uses_actual_runs_directory_and_strict_gate(self):
        conf = configuration("chosen-model:tag", "a" * 64, 60, 4096)
        self.assertEqual(schemas.validate("review-config", conf), [])
        path = self.root / "config.json"
        write(path, conf)
        prompt = self.root / "prompt.txt"
        prompt.write_text("Implement solve(data).")
        out = self.root / "full"
        argv = ["worker", "--arm", "verislop", "--task", str(prompt), "--out", str(out),
                "--config", str(path), "--seconds", "60", "--tokens", "8192", "--calls", "6"]
        previous_call, previous_inference = Broker.call, adapters._inference_request
        try:
            with patch("sys.argv", argv), patch.object(arm_worker.cli, "main", return_value=2) as cli:
                self.assertEqual(arm_worker.main(), 2)
            invoked = cli.call_args.args[0]
            self.assertEqual(invoked[invoked.index("--runs-dir") + 1], str(out))
            self.assertEqual(invoked[invoked.index("--run-id") + 1], "package")
            self.assertEqual(invoked[invoked.index("--policy") + 1], "strict")
            self.assertEqual(invoked[invoked.index("--require-state") + 1], "TESTED")
            self.assertEqual(invoked[invoked.index("--repair-rounds") + 1], "2")
            self.assertNotIn("--draft-candidate", invoked)
            self.assertNotIn("--formalization-candidate", invoked)
            self.assertNotIn("--implementation-candidate", invoked)
        finally:
            Broker.call, adapters._inference_request = previous_call, previous_inference

    def test_unbounded_cli_has_nullable_provider_and_zero_proof_and_review_budget(self):
        conf = configuration("chosen-model:tag", "a" * 64, 0, 8192)
        self.assertEqual(schemas.validate("review-config", conf), [])
        self.assertIsNone(conf["providers"]["local"]["request_timeout_seconds"])
        self.assertEqual(conf["review"]["budgets"]["max_wall_seconds_per_tier"], 0)
        path, prompt, out = self.root / "config.json", self.root / "prompt.txt", self.root / "full"
        write(path, conf)
        prompt.write_text("Implement solve(data).")
        argv = ["worker", "--arm", "verislop", "--task", str(prompt), "--out", str(out),
                "--config", str(path), "--seconds", "0", "--tokens", "262144", "--calls", "32"]
        previous_call, previous_inference = Broker.call, adapters._inference_request
        try:
            with patch("sys.argv", argv), patch.object(arm_worker.cli, "main", return_value=2) as cli:
                self.assertEqual(arm_worker.main(), 2)
            invoked = cli.call_args.args[0]
            self.assertEqual(invoked[invoked.index("--budget-seconds") + 1], "0")
        finally:
            Broker.call, adapters._inference_request = previous_call, previous_inference

    def test_supervisor_waits_without_deadline_when_zero_selected(self):
        task = json.loads((ROOT / "tasks.jsonl").read_text().splitlines()[0])
        args = SimpleNamespace(arm_seconds=0, output_token_budget=262144, harness_calls=32, case_seconds=1)
        process = SimpleNamespace(returncode=2)
        from unittest.mock import Mock
        process.communicate = Mock(return_value=(b"", b""))
        with patch("synthetic_dataset.benchmark.subprocess.Popen", return_value=process):
            row = run_arm(task, "verislop", 0, self.root, self.root / "config.json", args)
        process.communicate.assert_called_once_with(timeout=None)
        self.assertFalse(row["timed_out"])
        self.assertFalse(row["successful_task"])


if __name__ == "__main__":
    unittest.main()
