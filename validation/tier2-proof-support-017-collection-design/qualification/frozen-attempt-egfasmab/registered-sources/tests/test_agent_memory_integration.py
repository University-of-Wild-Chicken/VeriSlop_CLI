"""Authored role/resume fixtures verify durable context without model calls.

The successful repaired formalization crosses the existing real Lean statement
checker. These are regression fixtures, never benchmark or native PoC results.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_formal_frontend_workflow as frontend_fixture
import test_prover_feedback as proof_fixture

from verislop import agent_memory, agents, autonomous, canonical, contract, formalize, leanbridge, prove, recovery, run, schemas
from verislop.errors import BlockedError, Diagnostic
from verislop.package import Package
from verislop.providers import config as provider_config
from verislop.stage import StageResult


def snapshot_payload(pkg, reference):
    return canonical.loads(agent_memory.restore(pkg, reference)["payload.json"])


def corrupt_blob(pkg, context, source):
    rows = context["snapshots"][-1]["manifest"]["artifacts"]
    row = next(row for row in rows if row["source_ref"] == source)
    path = pkg.root / row["blob_ref"]["path"]
    raw = path.read_bytes()
    if not raw:
        raise AssertionError("tamper fixture needs a nonempty retained blob")
    path.chmod(0o600)
    path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])


class RecordedAgentCallMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "package")
        self.pkg.ensure("authored-recorded-call-memory")

    def test_exact_role_input_and_response_have_bound_persistent_snapshots(self):
        system = "Strict role\nUnicode: λ"
        user = '{"input":"x\\ny"}\n  preserve trailing spaces  \n'
        response = '```json\n{"proposal": "untrusted", "x": 2}\n```\n'
        completion = SimpleNamespace(text=response, request_id="authored-memory-call")
        broker = SimpleNamespace(call=Mock(return_value=completion))
        returned = agents.recorded_call(broker, self.pkg, "author", "role/1", system, user, "formalize")
        self.assertIs(completion, returned)
        broker.call.assert_called_once_with("author", "role/1", system, user, "formalize")
        fresh = Package(self.pkg.root)
        context = agent_memory.context_for(fresh, last=2)
        self.assertEqual(["agent/formalize/input", "agent/formalize/response"],
                         [item["manifest"]["stage"] for item in context["snapshots"]])
        input_ref = context["snapshots"][0]["snapshot_ref"]
        output_ref = context["snapshots"][1]["snapshot_ref"]
        self.assertEqual({"system.txt": system.encode(), "user.txt": user.encode()},
                         agent_memory.restore(fresh, input_ref))
        self.assertEqual({"response.txt": response.encode()}, agent_memory.restore(fresh, output_ref))
        self.assertEqual(input_ref, context["snapshots"][1]["manifest"]["metadata"]["input_snapshot"])
        self.assertEqual("role/1", context["snapshots"][0]["manifest"]["metadata"]["instance"])
        self.assertEqual({}, fresh.meta()["artifacts"])

    def test_provider_failure_keeps_input_and_exact_error_without_fake_response(self):
        original = RuntimeError("authored transport failure: no response\nretry separately")
        broker = SimpleNamespace(call=Mock(side_effect=original))
        with self.assertRaises(RuntimeError) as raised:
            agents.recorded_call(broker, self.pkg, "critic", "critic/2", "system", "exact request", "review")
        self.assertIs(original, raised.exception)
        fresh = Package(self.pkg.root)
        context = agent_memory.context_for(fresh, last=3)
        self.assertEqual(["agent/review/input", "agent/review/failure"],
                         [item["manifest"]["stage"] for item in context["snapshots"]])
        input_ref = context["snapshots"][0]["snapshot_ref"]
        failure = snapshot_payload(fresh, context["snapshots"][1]["snapshot_ref"])
        self.assertEqual({"input_snapshot": input_ref, "error_type": "RuntimeError", "error": str(original)}, failure)
        self.assertEqual({"system.txt": b"system", "user.txt": b"exact request"},
                         agent_memory.restore(fresh, input_ref))
        self.assertIsNone(agent_memory.latest_snapshot(fresh, stage_prefix="agent/review/response"))

    def test_old_response_tampering_blocks_next_role_before_provider_call(self):
        first = SimpleNamespace(call=Mock(return_value=SimpleNamespace(text="untrusted old response")))
        agents.recorded_call(first, self.pkg, "author", "author/1", "system", "request", "formalize")
        context = agent_memory.context_for(self.pkg, last=1)
        corrupt_blob(self.pkg, context, "response.txt")
        next_broker = SimpleNamespace(call=Mock())
        with self.assertRaises(BlockedError) as raised:
            agents.recorded_call(next_broker, Package(self.pkg.root), "critic", "critic/1", "system", "new request", "review")
        self.assertEqual("STALE_OR_UNBOUND_EVIDENCE", raised.exception.diagnostics[0].code)
        next_broker.call.assert_not_called()


class CriticMembershipIntegrationTests(unittest.TestCase):
    setUp = RecordedAgentCallMemoryTests.setUp
    def test_repeated_agent_groups_keep_distinct_ballots_and_required_abstention(self):
        # Two groups with distinct focuses may name the same configured model.
        # The first group abstains after two invalid envelopes; the second accepts.
        # Unanimity must retain the abstention and stop before the higher tier.
        path = Path(__file__).resolve().parents[1] / "examples/ollama-review-config.json"
        conf = json.loads(path.read_text())
        for spec in conf["agents"].values():
            spec["model_ref"] = "authored-mock-model"
        tier = conf["review"]["review_tiers"][0]
        tier["reviewers"] = [{"agent": "local-critic", "count": 1, "focus": "syntax"},
                             {"agent": "local-critic", "count": 1, "focus": "boundary cases"}]
        self.assertEqual([], schemas.validate("review-config", conf))
        resolved = provider_config.resolve(conf, {})
        self.assertEqual([], [d.to_json() for d in resolved.diagnostics if d.severity == "blocking"])
        self.pkg.path("prompt").parent.mkdir()
        self.pkg.path("prompt").write_bytes(b"Authored opaque fixture request")
        from verislop.events import EventSink
        events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(events.close)
        instances = []
        def call(agent, instance, system, user, purpose):
            instances.append(instance)
            value = {} if len(instances) <= 2 else {"encoding": autonomous.VERSION, "verdict": "ACCEPT",
                                                    "counterexamples": [], "corrections": []}
            return SimpleNamespace(text=canonical.dumps(value).decode())
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), conf)):
            critic = autonomous.critic_agent("unused", self.pkg, events)
        result = critic({"phase": "formalize", "attempt": 1, "source": b"-- opaque fixture", "form": {},
                         "records": [], "ledger": {"clauses": []}, "diagnostics": [],
                         "analysis": None, "statements": {}})
        self.assertEqual(3, len(instances))
        self.assertEqual(instances[0], instances[1])
        self.assertNotEqual(instances[1], instances[2])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual(1, len(result["tiers"]))
        self.assertEqual({"members": 2, "accepts": 1, "abstains": 1, "result": "INCOMPLETE"},
                         {key: result["tiers"][0][key] for key in ("members", "accepts", "abstains", "result")})
        self.assertEqual(["INVALID", "SEARCH_COMPLETED"], [item["status"] for item in result["results"]])
        self.assertFalse(result["milestone_authority"])


class FormalizerMemoryIntegrationTests(unittest.TestCase):
    setUp = frontend_fixture.FrontendWorkflowTests.setUp
    assert_pass = frontend_fixture.FrontendWorkflowTests.assert_pass

    def malformed_ast(self):
        proposal = copy.deepcopy(frontend_fixture.AST)
        proposal["symbols"]["bump"]["body"]["right"] = {"tag": "string", "value": "wrong sort"}
        return canonical.dumps(proposal).decode()

    def role(self, pkg, responses, captured):
        values = iter(responses)
        def call(*args):
            captured.append({"instance": args[1], "system": args[2], "user": args[3], "purpose": args[4]})
            return SimpleNamespace(text=next(values), request_id="authored-memory-formalizer")
        broker = SimpleNamespace(call=call)
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "author"}})):
            return agents.formalizer_agent("unused", pkg, self.events)

    def context(self, pkg, prior=None, feedback=None):
        draft, ledger, _ = formalize.require_interpretation(pkg)
        return {"draft": draft, "ledger": ledger, "records": formalize._records(draft, ledger, None),
                "feedback": feedback or [], "attempt": 2, "previous_candidate": prior,
                "requested": pkg.meta()["requested"]}

    def test_fresh_factory_recovers_exact_rejected_raw_response(self):
        raw = "  ```json\n{not-valid-json}\n```\n  rejected proposal λ\n"
        first_calls = []
        first_role = self.role(self.pkg, [raw], first_calls)
        source, manifest = first_role(self.context(self.pkg))
        self.assertEqual(b"-- unparseable formalizer response\n", source)
        fresh = Package(self.pkg.root)
        second_calls = []
        second_role = self.role(fresh, [canonical.dumps(frontend_fixture.AST).decode()], second_calls)
        prior = {"lean_source": source.decode(), "formalization": manifest}
        repaired_source, repaired_form = second_role(self.context(fresh, prior, [manifest["error"]]))
        self.assertIn("PREVIOUS REJECTED FORMALIZER RESPONSE", second_calls[0]["user"])
        self.assertIn(raw, second_calls[0]["user"])
        self.assertIn(manifest["error"], second_calls[0]["user"])
        self.assertNotEqual(source, repaired_source)
        self.assertNotIn("error", repaired_form)
        context = agent_memory.context_for(fresh, last=4)
        self.assertEqual(raw, context["snapshots"][1]["artifacts"]["response.txt"]["content"])

    def test_formalize_resume_restores_candidate_diagnostics_then_kernel_checks_repair(self):
        raw = self.malformed_ast()
        first_calls = []
        first_role = self.role(self.pkg, [raw], first_calls)
        first_result = formalize.run(self.pkg, self.events, agent=first_role, max_attempts=1)
        self.assertEqual("BLOCKED", first_result.status)
        self.assertEqual("INVALID_CANDIDATE", first_result.diagnostics[0].code)
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())
        old_ref = agent_memory.latest_snapshot(self.pkg, stage_prefix="formalize/attempt")
        old_bytes = agent_memory.restore(self.pkg, old_ref)
        saved = canonical.loads(old_bytes["payload.json"])
        self.assertEqual(1, saved["attempt"])
        self.assertEqual([first_result.diagnostics[0].message], saved["feedback"])
        fresh = Package(self.pkg.root)
        second_calls = []
        fresh_role = self.role(fresh, [canonical.dumps(frontend_fixture.AST).decode()], second_calls)
        with patch.object(formalize, "attempt", wraps=formalize.attempt) as checker:
            result = formalize.run(fresh, self.events, agent=fresh_role, max_attempts=1)
        self.assert_pass(result)
        self.assertEqual(1, checker.call_count)
        self.assertEqual("formalizer/2", second_calls[0]["instance"])
        self.assertIn(raw, second_calls[0]["user"])
        self.assertIn(saved["candidate"]["lean_source"].rstrip(), second_calls[0]["user"])
        self.assertIn(saved["feedback"][0], second_calls[0]["user"])
        self.assertNotIn("missing required property", second_calls[0]["user"])
        self.assertEqual(old_bytes, agent_memory.restore(fresh, old_ref))
        latest = snapshot_payload(fresh, agent_memory.latest_snapshot(fresh, stage_prefix="formalize/attempt"))
        self.assertEqual(2, latest["attempt"])
        self.assertEqual([], latest["diagnostics"])
        self.assertTrue((contract.challenge_dir(fresh) / "challenge.json").is_file())
        checked = canonical.load_file(fresh.path("contract") / "candidate/statement-check.json")
        self.assertTrue(checked["frontend_defeq"])
        self.assertTrue(all(row["result"]["defeq"] for row in checked["frontend_defeq"]))

    def test_tampered_latest_attempt_blocks_resume_before_formalizer_call(self):
        initial = self.role(self.pkg, [self.malformed_ast()], [])
        result = formalize.run(self.pkg, self.events, agent=initial, max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        context = agent_memory.context_for(self.pkg, last=1, stages=["formalize/attempt"])
        corrupt_blob(self.pkg, context, "payload.json")
        fresh = Package(self.pkg.root)
        unused = Mock(side_effect=AssertionError("provider must not run after corrupted memory"))
        with self.assertRaises(BlockedError) as raised:
            formalize.run(fresh, self.events, agent=unused, max_attempts=1)
        self.assertEqual("STALE_OR_UNBOUND_EVIDENCE", raised.exception.diagnostics[0].code)
        unused.assert_not_called()
        self.assertFalse((contract.challenge_dir(fresh) / "challenge.json").exists())

    def test_many_error_recovery_handoff_preserves_exact_critical_feedback(self):
        critical = "CONCRETE REFUTED: authored exact case, input {int:0}, false equality 1=0"
        critique = {"status": "REPAIR", "feedback": [critical], "milestone_authority": False}
        agent_memory.capture_context(self.pkg, "critique/prove", critique)
        errors = [f"authored detailed diagnostic {i}: retain the exact failure" for i in range(40)]
        attempts = self.pkg.path("contract") / "proofs/attempts.jsonl"
        attempts.parent.mkdir(parents=True)
        attempts.write_bytes(canonical.dumps({"errors": errors}) + b"\n")
        problem = Diagnostic("PROOF_UNRESOLVED", "the latest authored proof remains unresolved")
        failure = StageResult("run", "BLOCKED", "authored rejected attempt", diagnostics=[problem],
                              summary={"stopped_at": "prove", "failed_stage_summary": {"errors": []}})
        handoff = recovery.seed(self.pkg, failure)
        self.assertIn(critical, handoff["feedback"])
        self.assertEqual(critique, handoff["autonomous_critique"])
        fresh = Package(self.pkg.root)
        captured = []
        role = self.role(fresh, ["not JSON"], captured)
        ctx = self.context(fresh, feedback=handoff["feedback"])
        ctx["critique"] = handoff["autonomous_critique"]
        role(ctx)
        self.assertIn(critical, captured[0]["user"])
        for error in errors:
            self.assertIn(error, captured[0]["user"])
        self.assertIn("AUTONOMOUS CRITIQUE", captured[0]["user"])
        resumed_contexts = []
        def rejected_proposal(resumed_ctx):
            resumed_contexts.append(copy.deepcopy(resumed_ctx))
            return b"-- unparseable formalizer response\n", {"error": "unparseable formalizer response: authored rejection"}
        with patch.object(leanbridge, "resolve_toolchain", return_value=object()), patch.object(formalize, "attempt") as checker:
            resumed = formalize.run(fresh, self.events, agent=rejected_proposal, max_attempts=1,
                                    recovery_feedback=handoff["feedback"], recovery_critique=handoff["autonomous_critique"])
        self.assertEqual("BLOCKED", resumed.status)
        checker.assert_not_called()
        self.assertEqual(critique, resumed_contexts[0]["critique"])
        self.assertEqual(handoff["feedback"], resumed_contexts[0]["feedback"])
        # Independently verify actual CLI stage dispatch forwards both fields;
        # role output remains untrusted and no Lean/model call is made here.
        parameters = {"config": "authored-mock-config", "formalization_candidate": None, "policy": "strict",
                      "recovery_context": handoff}
        with patch.object(agents, "formalizer_agent", return_value=role), \
             patch.object(autonomous, "critic_agent", return_value=object()), \
             patch.object(formalize, "run", return_value=StageResult("formalize", "BLOCKED", "untrusted fixture")) as stage:
            run._run_stage("formalize", fresh, self.events, parameters)
        self.assertEqual(handoff["feedback"], stage.call_args.kwargs["recovery_feedback"])
        self.assertEqual(critique, stage.call_args.kwargs["recovery_critique"])


class ProverResumeMemoryIntegrationTests(unittest.TestCase):
    setUp = proof_fixture.ProverFeedbackTests.setUp
    inputs = proof_fixture.ProverFeedbackTests.inputs

    def test_default_portfolio_preserves_latest_rejected_proposal_on_fresh_resume(self):
        # Artifact-loading fixture only: both submissions and their diagnostics
        # are checked by actual Lean. The portfolio is kept incomplete to force
        # the fresh role to repair the previous bad submission.
        baseline = (self.challenge / "Contract.lean").read_text()
        bad = proof_fixture.SOURCE.replace("by sorry", "by exact missing_proof")
        good = proof_fixture.SOURCE.replace("by sorry", "by rfl")
        with self.inputs(real_lean=True), patch.object(prove, "apply_portfolio", return_value=baseline):
            initial = prove.run(self.pkg, self.events, budget_seconds=0, max_attempts=1, agent=lambda ctx: bad)
            self.assertEqual("BLOCKED", initial.status)
            old_ref = agent_memory.latest_snapshot(self.pkg, stage_prefix="prove/attempt")
            old_bytes = agent_memory.restore(self.pkg, old_ref)
            saved = canonical.loads(old_bytes["payload.json"])
            self.assertEqual(bad, saved["candidate"])
            self.assertTrue(any("Unknown identifier `missing_proof`" in error for error in saved["result"]["errors"]))
            contexts = []
            def resumed_proposer(ctx):
                contexts.append(copy.deepcopy(ctx))
                return good
            fresh = Package(self.pkg.root)
            repaired = prove.run(fresh, self.events, budget_seconds=0, max_attempts=1, agent=resumed_proposer)
        self.assertEqual("PASS", repaired.status, [d.to_json() for d in repaired.diagnostics])
        self.assertEqual(1, len(contexts))
        self.assertEqual(baseline, contexts[0]["best"])
        self.assertEqual(bad, contexts[0]["previous_candidate"])
        self.assertEqual("retained_latest", contexts[0]["previous_result"]["generator"])
        self.assertTrue(any("Unknown identifier `missing_proof`" in error for error in contexts[0]["errors"]))
        self.assertEqual(old_bytes, agent_memory.restore(fresh, old_ref))
        snapshots = agent_memory.context_for(fresh, last=4, stages=["prove/attempt"])["snapshots"]
        portfolio_payload = canonical.loads(snapshots[-2]["artifacts"]["payload.json"]["content"])
        self.assertEqual("builtin_tactic_portfolio", portfolio_payload["recorded_evaluation"]["generator"])
        self.assertEqual(bad, portfolio_payload["candidate"])
        self.assertTrue(portfolio_payload["result"]["errors"])
        self.assertEqual(baseline, (self.challenge / "Contract.lean").read_text())
        self.assertFalse(fresh.path("accepted").exists())


if __name__ == "__main__":
    unittest.main()
