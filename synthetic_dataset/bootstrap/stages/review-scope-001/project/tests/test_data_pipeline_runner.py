"""Authored negative accounting/transport fixtures; never native PoC observations.

Accepted-IR and origin boundaries are explicitly mocked in these unit tests. No model
calls, generated benchmark artifacts, preregistered cases or cohort receipts are edited.
"""
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from synthetic_dataset.tools import check_data_pipeline_poc as checker
from synthetic_dataset.tools import run_data_pipeline_poc as runner
from synthetic_dataset.tools import data_pipeline_oracle as oracle
from verislop import canonical, contract, fsutil
from verislop.errors import UsageError
from verislop.package import Package
from verislop.targets import python_harness, python_target as pt

ZERO = "sha256:" + "0" * 64


class RunnerAccountingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="authored-poc-runner-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.protocol = self.root / "fixture-protocol"
        self.protocol.mkdir()
        (self.protocol / "endpoint-profiles.json").write_text('{}')

    def task_package(self):
        task = oracle.TASKS[0]
        task_root = self.root / "current-cohort" / task
        pkg = Package(task_root / "runs" / task.lower(), resolve_root=False)
        pkg.ensure(task.lower())
        return task, task_root, pkg

    def test_old_successful_package_reference_cannot_replace_current_native_package(self):
        task, task_root, pkg = self.task_package()
        old = Package(self.root / "old-cohort" / task.lower())
        old.ensure(task.lower())
        native = {"status": "PASS", "summary": {"active_package": str(old.root)}}
        with self.assertRaisesRegex(ValueError, "outside the current task"):
            runner.active_package(task_root, task, native, [pkg])
        native["summary"]["active_package"] = str(pkg.root)
        self.assertEqual(pkg.root, runner.active_package(task_root, task, native, [pkg]))

    def test_current_package_must_be_in_exact_audited_inventory_and_repair_lineage(self):
        task, task_root, pkg = self.task_package()
        native = {"status": "PASS", "artifacts": {"package": str(pkg.root)}}
        with self.assertRaisesRegex(ValueError, "inventory"):
            runner.active_package(task_root, task, native, [])
        fsutil.write_json(pkg.root / "recovery.json", {"format": "bad-journal", "active_package": "other-task"})
        with self.assertRaises(UsageError):
            runner.active_package(task_root, task, native, [pkg])

    def test_nonzero_native_exit_or_blocked_stage_cannot_be_promoted_by_passing_oracle(self):
        audits, oracle_pass = [{"status": "PASS"}], {"status": "VERIFIED"}
        self.assertEqual("VERIFIED", runner.task_status({"status": "PASS"}, 0, oracle_pass, audits, bound=True, unchanged=True))
        for native, exit_code in (("PASS", 2), ("BLOCKED", 0), ("BLOCKED", 2)):
            with self.subTest(native=native, exit_code=exit_code):
                self.assertEqual("BLOCKED", runner.task_status({"status": native}, exit_code, oracle_pass, audits, bound=True, unchanged=True))
        self.assertEqual("BLOCKED", runner.task_status({"status": "PASS"}, 0, oracle_pass, audits, bound=False, unchanged=True))

    def native_stub(self, *, redirected=False):
        def launch(argv, **kwargs):
            run_id = argv[argv.index("--run-id") + 1]
            runs = Path(argv[argv.index("--runs-dir") + 1])
            pkg = Package(runs / run_id, resolve_root=False)
            pkg.ensure(run_id)
            reference = self.root / "old-successful-cohort" / run_id if redirected else pkg.root
            kwargs["stdout"].write(canonical.dumps({"status": "PASS", "summary": {"active_package": str(reference)}}))
            return SimpleNamespace(returncode=0 if redirected else 2)
        return launch

    def test_full_runner_keeps_current_exit2_blocked_even_when_independent_cases_all_pass(self):
        cohort = self.root / "native-exit2"
        with patch.object(runner, "PROTOCOL", self.protocol), patch.object(runner, "check_preregistration", return_value={"root": ZERO}), \
                patch.object(runner, "source_inputs", return_value={}), patch.object(runner.subprocess, "run", side_effect=self.native_stub()), \
                patch.object(runner, "origin_audit", return_value={"status": "PASS", "provider_calls": 1}), \
                patch.object(runner, "run_check", return_value={"status": "VERIFIED", "passed_cases": 160, "distinct_cases": 160, "observations": 320}):
            self.assertEqual(2, runner.main(["--cohort", str(cohort)]))
        result = self.summary(cohort)
        self.assertEqual(0, result["verified_tasks"])
        self.assertTrue(all(row["status"] == "BLOCKED" and row["active_package_bound"] and row["independent_cases_passed"] == 160 for row in result["tasks"]))

    def test_full_runner_never_checks_an_old_successful_redirected_package(self):
        cohort = self.root / "native-redirect"
        with patch.object(runner, "PROTOCOL", self.protocol), patch.object(runner, "check_preregistration", return_value={"root": ZERO}), \
                patch.object(runner, "source_inputs", return_value={}), patch.object(runner.subprocess, "run", side_effect=self.native_stub(redirected=True)), \
                patch.object(runner, "origin_audit", return_value={"status": "PASS", "provider_calls": 1}), patch.object(runner, "run_check") as independent:
            self.assertEqual(2, runner.main(["--cohort", str(cohort)]))
        independent.assert_not_called()
        result = self.summary(cohort)
        self.assertEqual(0, result["verified_tasks"])
        self.assertTrue(all(row["status"] == "BLOCKED" and not row["active_package_bound"] for row in result["tasks"]))

    def test_actual_candidate_cli_names_and_equals_forms_are_forbidden(self):
        _, _, pkg = self.task_package()
        names = ("--draft-candidate", "--ledger-candidate", "--formalization-candidate", "--proof-candidate",
                 "--implementation-candidate", "--bindings-candidate", "--bridge-id", "--bridge-proposal", "--bridge-candidate-dir")
        with patch.object(runner, "source_inputs", return_value={}):
            for name in names:
                for arg in (name, name + "=authored-fixture"):
                    with self.subTest(arg=arg):
                        result = runner.origin_audit(pkg, ["python", "-m", "verislop", "run", arg], {})
                        self.assertIn("Supplied positive artifact argument", result["issues"])

    def summary(self, cohort):
        result = canonical.load_file(cohort / "SUMMARY.json")
        self.assertEqual(3, result["total_tasks"])
        self.assertEqual(list(oracle.TASKS), [row["task"] for row in result["tasks"]])
        for task in oracle.TASKS:
            self.assertTrue((cohort / task / "result.json").is_file())
        return result

    def test_missing_preregistration_seals_all_fixed_tasks_without_launching(self):
        cohort = self.root / "missing-prereg"
        with patch.object(runner, "check_preregistration", side_effect=FileNotFoundError("missing preregistration")), patch.object(runner.subprocess, "run") as launch:
            self.assertEqual(2, runner.main(["--cohort", str(cohort)]))
        launch.assert_not_called()
        result = self.summary(cohort)
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual(0, result["verified_tasks"])
        self.assertTrue(all(row["status"] == "BLOCKED" for row in result["tasks"]))

    def run_failure(self, cohort, launch):
        with patch.object(runner, "PROTOCOL", self.protocol), patch.object(runner, "check_preregistration", return_value={"root": ZERO}), \
                patch.object(runner, "source_inputs", return_value={}), patch.object(runner.subprocess, "run", side_effect=launch), \
                patch.object(runner, "run_check") as independent:
            self.assertEqual(2, runner.main(["--cohort", str(cohort)]))
        independent.assert_not_called()
        return self.summary(cohort)

    def test_native_launch_and_parse_failures_seal_all_tasks_as_infrastructure(self):
        def malformed(_argv, **kwargs):
            kwargs["stdout"].write(b'not a native CLI JSON result')
            return SimpleNamespace(returncode=1)
        for label, failure in (("launch", OSError("cannot launch interpreter")), ("parse", malformed)):
            with self.subTest(label=label):
                result = self.run_failure(self.root / label, failure)
                self.assertEqual("INFRASTRUCTURE_FAILURE", result["status"])
                self.assertTrue(all(row["status"] == "INFRASTRUCTURE_FAILURE" for row in result["tasks"]))
                self.assertEqual(0, result["verified_tasks"])

    def test_frozen_source_or_preregistration_failure_before_next_task_seals_denominator(self):
        for label, changes in (("source", [{}, {"changed.py": ZERO}]), ("prereg", [{}, {}])):
            cohort = self.root / label
            checks = [{"root": ZERO}, FileNotFoundError("preregistration disappeared")] if label == "prereg" else None
            with patch.object(runner, "PROTOCOL", self.protocol), patch.object(runner, "source_inputs", side_effect=changes), \
                    patch.object(runner, "check_preregistration", side_effect=checks, return_value={"root": ZERO}), \
                    patch.object(runner.subprocess, "run") as launch:
                self.assertEqual(2, runner.main(["--cohort", str(cohort)]))
            launch.assert_not_called()
            self.assertEqual("BLOCKED", self.summary(cohort)["status"])


class ContextConfigurationTests(RunnerAccountingTests):
    """The CLI results/origin/oracle are mocked; these are configuration accounting tests."""
    def setUp(self):
        super().setUp()
        self.base = canonical.load_file(runner.PROTOCOL / "qwen-config.json")
        fsutil.write_json(self.protocol / "qwen-config.json", self.base)

    def test_context_override_preserves_models_budgets_tasks_and_base_file(self):
        with patch.object(runner, "PROTOCOL", self.protocol):
            configured = runner.configuration_with_context(32768)
            for value in (True, 0, 1023, 262145, "32768"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    runner.configuration_with_context(value)
        for agent in configured["agents"].values():
            self.assertEqual(32768, agent.pop("context_window_tokens"))
        self.assertEqual(self.base, configured)
        self.assertEqual(self.base, canonical.load_file(self.protocol / "qwen-config.json"))

    def test_full_runner_preregisters_and_passes_exact_effective_configuration(self):
        cohort = self.root / "context-config"
        commands = []
        launch_stub = self.native_stub()
        def launch(argv, **kwargs):
            commands.append(argv)
            return launch_stub(argv, **kwargs)
        with patch.object(runner, "PROTOCOL", self.protocol), patch.object(runner, "check_preregistration", return_value={"root": ZERO}), \
                patch.object(runner, "source_inputs", return_value={}), patch.object(runner.subprocess, "run", side_effect=launch), \
                patch.object(runner, "origin_audit", return_value={"status": "PASS", "provider_calls": 1}) as audit, \
                patch.object(runner, "run_check", return_value={"status": "VERIFIED", "passed_cases": 160, "distinct_cases": 160, "observations": 320}):
            self.assertEqual(2, runner.main(["--cohort", str(cohort), "--ollama-context-tokens", "32768"]))
        configuration = canonical.load_file(cohort / "execution-config.json")
        freeze = canonical.load_file(cohort / "source-freeze.json")["execution_configuration"]
        self.assertEqual(canonical.digest_file(cohort / "execution-config.json"), freeze["sha256"])
        self.assertEqual(32768, freeze["context_window_tokens"])
        self.assertIn("same models", freeze["departure"])
        self.assertEqual(3, len(commands))
        for command in commands:
            self.assertEqual(str(cohort / "execution-config.json"), command[command.index("--config") + 1])
        for call in audit.call_args_list:
            self.assertEqual(configuration, call.kwargs["effective_config"])
        self.assertEqual(0, self.summary(cohort)["verified_tasks"])

    def test_changed_effective_configuration_blocks_and_preserves_all_task_rows(self):
        cohort = self.root / "mutated-context-config"
        launch_stub = self.native_stub()
        def launch(argv, **kwargs):
            result = launch_stub(argv, **kwargs)
            path = Path(argv[argv.index("--config") + 1])
            path.write_bytes(path.read_bytes() + b" ")
            return result
        with patch.object(runner, "PROTOCOL", self.protocol), patch.object(runner, "check_preregistration", return_value={"root": ZERO}), \
                patch.object(runner, "source_inputs", return_value={}), patch.object(runner.subprocess, "run", side_effect=launch) as calls, \
                patch.object(runner, "origin_audit", return_value={"status": "PASS", "provider_calls": 1}), \
                patch.object(runner, "run_check", return_value={"status": "VERIFIED", "passed_cases": 160, "distinct_cases": 160, "observations": 320}):
            self.assertEqual(2, runner.main(["--cohort", str(cohort), "--ollama-context-tokens", "32768"]))
        self.assertEqual(1, calls.call_count)
        summary = self.summary(cohort)
        self.assertEqual(0, summary["verified_tasks"])
        self.assertIn("INPUT_MUTATION", summary["blocking_reason"])



class OraclePartialFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="authored-poc-oracle-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = oracle.TASKS[0]
        self.protocol = self.root / "fixture-protocol"
        fsutil.atomic_write(self.protocol / (self.task + ".txt"), b"Authored transport unit fixture")
        self.cases = oracle.cases(self.task)[:2]
        fsutil.write_json(self.protocol / "withheld" / (self.task + ".json"), {"cases": self.cases})
        self.pkg = Package(self.root / "authored-unit-package")
        self.pkg.ensure("authored-oracle-unit")
        fsutil.atomic_write(self.pkg.path("prompt"), (self.protocol / (self.task + ".txt")).read_bytes())
        fsutil.write_json(self.pkg.path("accepted_ir"), {"unit_fixture": "IR boundary explicitly mocked"})
        fsutil.write_json(self.pkg.path("report"), {"terminal_status": "VERIFIED",
            "tier": {"requested": 0, "target": "python", "require_state": "TESTED",
                     "endpoint": "test_campaign", "requested_endpoint": "test_campaign", "tier_default_applied": False},
            "builds": [{"ok": True}, {"ok": True}], "determinism": {"mismatches": []},
            "review": {"checkpoints": {"formal_contract": "REVIEW_ACCEPTED", "release": "REVIEW_ACCEPTED"}},
            "obligations": {"O1": {"required": True, "required_milestones": ["TESTED"], "outcomes": {"TESTED": "PASS"}}}})
        fsutil.write_json(self.pkg.path("bridges") / "link.json", {"unit_fixture": True})
        fsutil.atomic_write(self.pkg.path("implementation") / "solve.py", b'def solve(data):\n    return data\n')
        self.binding = {"symbol": "solve", "implementation_object": {"file": "solve.py", "qualname": "solve"}}

    def context(self):
        stack = ExitStack()
        stack.enter_context(patch.object(checker, "PROTOCOL", self.protocol))
        stack.enter_context(patch.object(checker, "check_preregistration", return_value={"root": ZERO}))
        stack.enter_context(patch.object(checker, "verified_ir", return_value=({}, ZERO, {}, [])))
        stack.enter_context(patch.object(checker, "select_solve", return_value=(self.pkg.path("implementation"), {}, self.binding, [], self.pkg.path("bridges") / "link.json")))
        return stack

    def harness_factory(self, second_failure, *, second_constructor=False):
        task, instances = self.task, []
        class Harness:
            def __init__(self, *_args, **_kwargs):
                self.calls = 0
                self.index = len(instances)
                instances.append(self)
                self.isolation = {"authored_unit_stub": True, "instance": self.index}
                if self.index == 1 and second_constructor:
                    raise second_failure
            def call(self, _symbol, args):
                self.calls += 1
                if self.index == 1 and self.calls == 2:
                    raise second_failure
                expected = oracle.wire(oracle.expected(task, python_harness.dec(args[0])))
                return {"op": "result", "id": self.calls, "value": expected}
            def close(self):
                pass
        return Harness

    def test_partial_second_harness_timeout_crash_protocol_remain_blocked_and_keep_counts(self):
        for kind in ("timeout", "crash", "protocol"):
            with self.subTest(kind=kind), self.context(), patch.object(checker.pt, "Harness", self.harness_factory(pt.HarnessError(kind, "candidate failed"))):
                result = checker.run_check(self.pkg.root, self.task)
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual((1, 3, 3, 1), (result["passed_cases"], result["observations"], result["passed_observations"], result["incomplete_cases"]))
            self.assertEqual(2, len(result["isolation"]))
            self.assertTrue(result["input_bytes_unchanged"])

    def test_second_sandbox_isolation_and_launch_failures_are_infrastructure_with_partial_counts(self):
        for failure in (pt.HarnessError("isolation", "sandbox unavailable"), OSError("launch unavailable")):
            with self.subTest(failure=str(failure)), self.context(), patch.object(checker.pt, "Harness", self.harness_factory(failure, second_constructor=True)):
                result = checker.run_check(self.pkg.root, self.task)
            self.assertEqual("INFRASTRUCTURE_FAILURE", result["status"])
            self.assertEqual((0, 2, 2), (result["passed_cases"], result["observations"], result["passed_observations"]))
            self.assertEqual(1, len(result["isolation"]))

    def test_missing_and_changed_preregistration_are_retained_blocked_receipts(self):
        with patch.object(checker, "check_preregistration", side_effect=FileNotFoundError("missing preregistration")):
            missing = checker.run_check(self.pkg.root, self.task)
        self.assertEqual("BLOCKED", missing["status"])
        self.assertEqual(0, missing["observations"])
        with self.context(), patch.object(checker, "check_preregistration", side_effect=[{"root": ZERO}, FileNotFoundError("preregistration disappeared")]), \
                patch.object(checker.pt, "Harness", self.harness_factory(pt.HarnessError("timeout", "unused"), second_constructor=False)):
            # Fail the final preregistration recheck after retaining three observations.
            changed = checker.run_check(self.pkg.root, self.task)
        self.assertEqual("BLOCKED", changed["status"])
        self.assertEqual(3, changed["observations"])
        self.assertTrue(any("preregistration disappeared" in str(d) for d in changed["diagnostics"]))


if __name__ == '__main__':
    unittest.main()
