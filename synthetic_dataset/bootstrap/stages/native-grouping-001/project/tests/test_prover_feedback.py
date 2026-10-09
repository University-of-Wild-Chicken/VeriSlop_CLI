"""Proof search retains the best baseline while repairing the latest concrete failure."""
from __future__ import annotations

import contextlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, contract, leanbridge, prove
from verislop.errors import InfrastructureError
from verislop.events import EventSink
from verislop.package import Package


SOURCE = ("import Std\nnamespace Feedback\n"
          "def identity (n : Nat) : Nat := n\n"
          "theorem preserves (n : Nat) : identity n = n := by sorry\n"
          "end Feedback\n")
REGISTRY = contract.REGISTRY_BEGIN + "\n" + contract.REGISTRY_END + "\n"


class ProverFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-prover-feedback-")
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "package")
        self.pkg.ensure("prover-feedback")
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)
        self.challenge = Path(self.tmp.name) / "frozen-challenge"
        self.challenge.mkdir()
        (self.challenge / "Contract.lean").write_text(SOURCE + REGISTRY)
        (self.challenge / "lean-toolchain").write_text("leanprover/lean4:v4.34.1\n")
        self.policy = {"build_timeout_seconds": 15, "memory_mb": 512, "require_network_isolation": True}

    def inputs(self, *, real_lean=False):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(contract, "load_frozen", return_value=({}, [])))
        stack.enter_context(patch.object(contract, "challenge_dir", return_value=self.challenge))
        stack.enter_context(patch.object(contract, "frozen_json", side_effect=lambda pkg, name: {
            "statements.json": {"statements": {}}, "profile.json": {}, "policy.json": self.policy}[name]))
        if not real_lean:
            stack.enter_context(patch.object(leanbridge, "resolve_toolchain", return_value=object()))
        return stack

    @staticmethod
    def evaluated(*, errors=None, sorries=0):
        errors = errors or []
        return {"ok": not errors, "errors": errors, "sorries": sorries,
                "complete": not errors and not sorries, "wall_ms": 1}

    def test_worse_candidates_feed_exact_latest_source_and_errors_without_replacing_best(self):
        baseline = (self.challenge / "Contract.lean").read_text()
        bad1 = SOURCE.replace("by sorry", "by exact missing_one")
        bad2 = SOURCE.replace("by sorry", "by exact missing_two")
        errors1 = [f"{i}: unknown identifier missing_one_{i}" for i in range(35)]
        errors2 = ["8: unknown identifier missing_two"]
        proposals = iter([bad1, bad2])
        contexts = []

        def proposer(ctx):
            contexts.append(copy.deepcopy(ctx))
            return next(proposals)

        evaluations = [self.evaluated(sorries=1), self.evaluated(errors=errors1), self.evaluated(errors=errors2)]
        with self.inputs(), patch.object(prove, "apply_portfolio", return_value=baseline), \
             patch.object(prove, "evaluate", side_effect=evaluations):
            result = prove.run(self.pkg, self.events, budget_seconds=0, max_attempts=2, agent=proposer)
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(2, len(contexts))
        self.assertEqual(baseline, contexts[1]["best"])
        self.assertEqual(bad1, contexts[1]["previous_candidate"])
        self.assertEqual(errors1, contexts[1]["errors"])
        self.assertFalse(contexts[1]["previous_result"]["ok"])
        self.assertEqual(baseline, (self.pkg.path("contract") / "proofs/candidate.lean").read_text())
        self.assertEqual(baseline, (self.challenge / "Contract.lean").read_text())
        records = [json.loads(line) for line in (self.pkg.path("contract") / "proofs/attempts.jsonl").read_text().splitlines()]
        self.assertEqual([[], errors1, errors2], [r["errors"] for r in records])
        self.assertEqual(canonical.digest(bad1.encode()), records[1]["proposal_sha256"])
        self.assertNotEqual(records[1]["source_sha256"], records[1]["proposal_sha256"])
        for rec, proposal in zip(records, [baseline, bad1, bad2]):
            path = self.pkg.path("contract") / "proofs/proposals" / (rec["proposal_sha256"].split(":")[1][:16] + ".lean")
            self.assertEqual(proposal, path.read_text())

    def test_explicit_candidate_failure_is_supplied_to_first_agent_attempt(self):
        submitted = SOURCE.replace("by sorry", "by exact absent")
        candidate = Path(self.tmp.name) / "candidate.lean"
        candidate.write_text(submitted)
        contexts = []

        def proposer(ctx):
            contexts.append(copy.deepcopy(ctx))
            return SOURCE.replace("by sorry", "by rfl")

        with self.inputs(), patch.object(prove, "evaluate", side_effect=[self.evaluated(errors=["unknown identifier absent"]), self.evaluated()]):
            result = prove.run(self.pkg, self.events, candidate=candidate, portfolio=False,
                               budget_seconds=0, max_attempts=1, agent=proposer)
        self.assertEqual("PASS", result.status)
        self.assertEqual(submitted, contexts[0]["previous_candidate"])
        self.assertEqual(["unknown identifier absent"], contexts[0]["errors"])
        self.assertEqual("candidate_file", contexts[0]["previous_result"]["generator"])
        self.assertEqual(submitted, candidate.read_text())

    def test_real_lean_failure_is_repaired_with_exact_context_and_frozen_bytes_unchanged(self):
        # Only frozen-artifact loading is stubbed; Lean elaboration and its diagnostics are real.
        baseline = (self.challenge / "Contract.lean").read_text()
        frozen_before = {p.name: p.read_bytes() for p in self.challenge.iterdir()}
        bad = SOURCE.replace("by sorry", "by exact missing_proof")
        good = SOURCE.replace("by sorry", "by rfl")
        contexts = []

        def proposer(ctx):
            contexts.append(copy.deepcopy(ctx))
            return bad if len(contexts) == 1 else good

        with self.inputs(real_lean=True), patch.object(prove, "apply_portfolio", return_value=baseline):
            result = prove.run(self.pkg, self.events, budget_seconds=0, max_attempts=3, agent=proposer)
        self.assertEqual("PASS", result.status, [d.to_json() for d in result.diagnostics])
        self.assertEqual(2, len(contexts))
        self.assertEqual(bad, contexts[1]["previous_candidate"])
        self.assertEqual(baseline, contexts[1]["best"])
        self.assertTrue(any("Unknown identifier `missing_proof`" in error for error in contexts[1]["errors"]), contexts[1]["errors"])
        self.assertTrue(result.summary["complete"])
        self.assertEqual(frozen_before, {p.name: p.read_bytes() for p in self.challenge.iterdir()})
        self.assertFalse(self.pkg.path("accepted").exists())  # proof search is not Lean acceptance or PROVED.

    def test_infrastructure_failure_is_not_a_model_repair_or_silent_acceptance(self):
        calls = []

        def proposer(ctx):
            calls.append(ctx)
            return SOURCE

        with self.inputs(), patch.object(prove, "evaluate", side_effect=InfrastructureError("missing toolchain")):
            with self.assertRaises(InfrastructureError):
                prove.run(self.pkg, self.events, budget_seconds=0, max_attempts=3, portfolio=False, agent=proposer)
        self.assertEqual(1, len(calls))
        self.assertFalse((self.pkg.path("contract") / "proofs/candidate.lean").exists())


if __name__ == "__main__":
    unittest.main()
