"""Zero disables orchestration deadlines while attempt and verifier limits remain."""
from __future__ import annotations

import contextlib
import io
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from verislop import cli, contract, prove, review, run
from verislop.errors import UsageError
from verislop.events import EventSink
from verislop.package import Package


class UnboundedRunBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="verislop-unbounded-budget-test-")
        self.root = Path(self.temporary.name)
        self.pkg = Package(self.root / "package")
        self.pkg.ensure("unbounded-budget")
        self.challenge = self.root / "challenge"
        self.challenge.mkdir()
        (self.challenge / "Contract.lean").write_text(
            "theorem obligation : True := by sorry\n" + contract.REGISTRY_BEGIN + "\n" + contract.REGISTRY_END + "\n")
        (self.challenge / "lean-toolchain").write_text("leanprover/lean4:v4.34.1\n")
        self.policy = {"build_timeout_seconds": 7, "memory_mb": 256, "require_network_isolation": True}
        self.events = EventSink("unbounded-budget", quiet=True)

    def tearDown(self):
        self.temporary.cleanup()

    def proof_inputs(self):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(contract, "load_frozen", return_value=({}, [])))
        stack.enter_context(patch.object(contract, "challenge_dir", return_value=self.challenge))
        stack.enter_context(patch.object(contract, "frozen_json", side_effect=lambda pkg, name: {
            "statements.json": {"statements": {}}, "profile.json": {}, "policy.json": self.policy}[name]))
        stack.enter_context(patch.object(prove.leanbridge, "resolve_toolchain", return_value=object()))
        return stack

    @staticmethod
    def incomplete():
        return {"ok": True, "errors": [], "sorries": 1, "complete": False, "wall_ms": 1}

    def test_zero_enables_proof_agent_and_retains_attempt_cap(self):
        agent = Mock(return_value="theorem obligation : True := by sorry\n")
        with self.proof_inputs(), patch.object(prove, "evaluate", return_value=self.incomplete()) as evaluate, \
             patch.object(prove.time, "monotonic", side_effect=AssertionError("zero budget must not consult a deadline")):
            result = prove.run(self.pkg, self.events, budget_seconds=0, max_attempts=3, portfolio=False, agent=agent)
        self.assertEqual(agent.call_count, 3)
        self.assertEqual([call.args[0]["attempt"] for call in agent.call_args_list], [1, 2, 3])
        self.assertEqual(evaluate.call_count, 3)
        self.assertTrue(all(call.args[1] == self.policy for call in evaluate.call_args_list))
        self.assertEqual({d.code for d in result.diagnostics}, {"PROOF_UNRESOLVED"})
        self.assertEqual(result.summary["budget_seconds"], 0)
        self.assertEqual(result.status, "BLOCKED")

    def test_zero_keeps_builtin_portfolio_enabled(self):
        complete = {"ok": True, "errors": [], "sorries": 0, "complete": True, "wall_ms": 1}
        with self.proof_inputs(), patch.object(prove, "apply_portfolio", return_value="theorem obligation : True := by trivial\n") as portfolio, \
             patch.object(prove, "evaluate", return_value=complete), \
             patch.object(prove.time, "monotonic", side_effect=AssertionError("zero budget must not consult a deadline")):
            result = prove.run(self.pkg, self.events, budget_seconds=0)
        portfolio.assert_called_once()
        self.assertEqual(result.status, "PASS")
        self.assertTrue(result.summary["complete"])

    def test_positive_budget_still_expires(self):
        agent = Mock(return_value="theorem obligation : True := by sorry\n")
        with self.proof_inputs(), patch.object(prove, "evaluate", return_value=self.incomplete()), \
             patch.object(prove.time, "monotonic", side_effect=[0, 0, 2, 2]):
            result = prove.run(self.pkg, self.events, budget_seconds=1, max_attempts=3, portfolio=False, agent=agent)
        self.assertEqual(agent.call_count, 1)
        self.assertEqual({d.code for d in result.diagnostics}, {"BUDGET_EXHAUSTED"})

    def test_cli_accepts_zero_preserves_defaults_and_rejects_negative(self):
        parser = cli.build_parser()
        args = parser.parse_args(["run", "--prompt-file", "request.txt", "--budget-seconds", "0"])
        self.assertEqual(run._params_from_args(args)["budget_seconds"], 0)
        self.assertEqual(parser.parse_args(["run", "--prompt-file", "request.txt"]).budget_seconds, 600)
        self.assertEqual(parser.parse_args(["prove"]).budget_seconds, 600)
        self.assertEqual(parser.parse_args(["prove", "--budget-seconds", "0"]).budget_seconds, 0)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            parser.parse_args(["run", "--prompt-file", "request.txt", "--budget-seconds", "-1"])
        self.assertEqual(raised.exception.code, 64)
        args.budget_seconds = -1
        with self.assertRaises(UsageError):
            run._params_from_args(args)
        with self.assertRaises(UsageError):
            prove.run(self.pkg, self.events, budget_seconds=-1)

    def test_verifier_build_deadline_remains_finite(self):
        compiled = Mock(ok=True, errors=[], sorry_positions=[], wall_seconds=0.001)
        with patch.object(prove.leanbridge, "compile_module", return_value=compiled) as compiler:
            result = prove.evaluate(object(), self.policy, "theorem obligation : True := by trivial\n")
        self.assertTrue(result["complete"])
        self.assertEqual(compiler.call_args.kwargs["timeout"], 7)
        self.assertEqual(compiler.call_args.kwargs["memory_mb"], 256)
        self.assertTrue(compiler.call_args.kwargs["require_network_isolation"])

    def test_zero_review_tier_waits_for_actual_completion(self):
        release = threading.Event()
        timer = threading.Timer(0.05, release.set)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(release.wait)
            timer.start()
            try:
                done, pending = review._wait_for_tier({future}, 0)
            finally:
                release.set()
                timer.join()
        self.assertEqual(done, {future})
        self.assertEqual(pending, set())
        self.assertTrue(future.result())

    def test_positive_review_tier_keeps_its_configured_deadline(self):
        with patch.object(review, "wait", return_value=(set(), set())) as wait:
            review._wait_for_tier(set(), 9)
        wait.assert_called_once_with(set(), timeout=9)


if __name__ == "__main__":
    unittest.main()
