"""Finite authored regressions for gap reporting and exact repair provenance."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_formal_frontend_workflow import AST, FrontendWorkflowTests
from verislop import agent_memory, agents, autonomous, canonical, contract, formalize, recovery
from verislop.errors import BlockedError
from verislop.package import Package
from verislop.stage import StageResult


REPORT = {"encoding": agents.CAPABILITY_VERSION, "obligation_ids": ["D1", "O1"], "gaps": [{
    "obligation_ids": ["O1"], "feature": "authored reported signed addition gap",
    "reason": "Authored fixture deliberately overlooks registered int_add.",
    "attempted_representations": ["Use Nat, which would lose negative inputs; this is not faithful."]}]}


class BootstrapAgentRepairTests(unittest.TestCase):
    setUp = FrontendWorkflowTests.setUp
    assert_pass = FrontendWorkflowTests.assert_pass

    def role(self, pkg, responses, captured):
        pending = iter(responses)
        def call(*args):
            captured.append({"system": args[2], "user": args[3], "purpose": args[4]})
            return SimpleNamespace(text=next(pending), request_id="authored-bootstrap-response")
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), {"roles": {"formalizer": "author"}})):
            return agents.formalizer_agent("unused", pkg, self.events)

    def critic(self, captured):
        conf = json.loads((Path(__file__).resolve().parents[1] / "examples/ollama-review-config.json").read_text())
        conf["review"]["review_tiers"] = conf["review"]["review_tiers"][:1]
        conf["review"]["review_tiers"][0]["reviewers"] = [{"agent": "critic", "count": 1, "focus": "faithful representation"}]
        def call(*args):
            packet = json.loads(args[3])
            captured.append(packet)
            value = {"encoding": autonomous.VERSION, "verdict": "REPAIR", "counterexamples": [],
                     "corrections": [{"diagnostic_index": 0, "artifact": "formalization.json",
                                      "explanation": "int_add is registered; preserve Int and propose the full signed expression."}]}
            return SimpleNamespace(text=canonical.dumps(value).decode())
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), conf)):
            return autonomous.critic_agent("unused", self.pkg, self.events)

    def test_gap_is_concrete_feedback_then_actual_lean_accepts_complete_alternative(self):
        raw = " \n" + canonical.dumps(REPORT).decode() + "\n  "
        calls, packets = [], []
        proposer = self.role(self.pkg, [raw, canonical.dumps(AST).decode()], calls)
        # Actual critic protocol runs only on the gap in this fixture. The ordinary
        # contract refutation/checker still validates the successful proposal.
        actual_critic = self.critic(packets)
        def critic(ctx):
            return actual_critic(ctx) if ctx.get("capability_report") else {"status": "SEARCH_COMPLETED", "feedback": [], "results": [], "diagnostics": []}
        with patch.object(formalize, "attempt", wraps=formalize.attempt) as checker:
            result = formalize.run(self.pkg, self.events, agent=proposer, critic=critic, max_attempts=2)
        self.assert_pass(result)
        self.assertEqual(1, checker.call_count)
        self.assertEqual(raw, packets[0]["raw_formalizer_response"])
        self.assertEqual(REPORT, packets[0]["capability_report"])
        self.assertEqual("UNSUPPORTED_CAPABILITY", packets[0]["diagnostics"][0]["code"])
        self.assertIn("int_add", packets[0]["registered_formalizer_language"])
        self.assertIn(raw, calls[1]["user"])
        self.assertNotIn("unparseable formalizer response", calls[1]["user"])
        saved = agent_memory.context_for(self.pkg, stages=["formalize/attempt"], last=2)["snapshots"]
        first = canonical.loads(saved[0]["artifacts"]["payload.json"]["content"])
        self.assertEqual(raw, first["candidate"]["raw_response"])
        self.assertFalse(packets[0]["authority"].startswith("accepted"))
        self.assertTrue((contract.challenge_dir(self.pkg) / "challenge.json").exists())

    def test_exhausted_reports_block_without_lean_or_outer_parse_error_retry(self):
        raw = canonical.dumps(REPORT).decode()
        calls = []
        with patch.object(formalize, "attempt") as checker:
            result = formalize.run(self.pkg, self.events, agent=self.role(self.pkg, [raw] * 3, calls), max_attempts=3)
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(3, len(calls))
        checker.assert_not_called()
        self.assertEqual(["UNSUPPORTED_CAPABILITY"], [d.code for d in result.diagnostics])
        self.assertEqual(["O1"], result.diagnostics[0].obligations)
        self.assertEqual(REPORT, result.diagnostics[0].details["capability_report"])
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())
        wrapped = StageResult("run", result.status, "authored gap", diagnostics=result.diagnostics,
            summary={"stopped_at": "formalize", "failed_stage_diagnostics": [d.to_json() for d in result.diagnostics]})
        self.assertFalse(recovery.eligible(wrapped, {"config": "authored", "repair_rounds": 2}, self.pkg))
        self.assertTrue(all(e.record["status"] != "PASS" for e in self.pkg.evidence.load()
                            if str(e.record["claim_id"]).startswith("FORMALIZED:")))

    def test_unknown_omitted_duplicate_ids_and_extra_fields_are_malformed(self):
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        variants = []
        for ids in (["O1"], ["D1", "O1", "O1"], ["D1", "unknown"]):
            v = copy.deepcopy(REPORT); v["obligation_ids"] = ids; variants.append(v)
        v = copy.deepcopy(REPORT); v["gaps"][0]["obligation_ids"] = ["unknown"]; variants.append(v)
        v = copy.deepcopy(REPORT); v["gaps"][0]["attempted_representations"] = []; variants.append(v)
        v = copy.deepcopy(REPORT); v["status"] = "accepted"; variants.append(v)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                agents.assemble_formalization_response(canonical.dumps(value).decode(), records, "authored")

    def test_malformed_raw_response_reaches_critic_exactly(self):
        raw = "```json\n{ broken λ :}\n```  \n"
        packets = []
        with patch.object(formalize, "attempt") as checker:
            result = formalize.run(self.pkg, self.events, agent=self.role(self.pkg, [raw], []),
                                   critic=self.critic(packets), max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        checker.assert_not_called()
        self.assertEqual(raw, packets[0]["raw_formalizer_response"])
        self.assertIsNone(packets[0]["capability_report"])
        self.assertEqual(raw.encode(), agent_memory.restore(self.pkg, packets[0]["raw_response_snapshot"])["response.txt"])

    def test_outer_repair_rebinds_exact_raw_bytes_to_child_memory_and_prompt(self):
        raw = "  malformed { json\nwith retained whitespace λ  \n"
        first = formalize.run(self.pkg, self.events, agent=self.role(self.pkg, [raw], []), max_attempts=1)
        failure = StageResult("run", first.status, first.message if hasattr(first, "message") else "authored rejection",
            diagnostics=first.diagnostics, summary={"stopped_at": "formalize",
            "failed_stage_diagnostics": [d.to_json() for d in first.diagnostics]})
        seed = recovery.seed(self.pkg, failure)
        self.assertEqual(raw, seed["previous_candidate"]["raw_response"])
        parent_ref = seed["previous_candidate"]["raw_response_snapshot"]
        params = {"config": "authored", "repair_rounds": 1}
        child, parameters, record = recovery.create(self.pkg, self.pkg, params, failure, 1, self.events)
        prior = parameters["recovery_context"]["previous_candidate"]
        self.assertEqual(raw, prior["raw_response"])
        self.assertEqual(parent_ref, prior["parent_raw_response_snapshot"]["snapshot_ref"])
        self.assertNotEqual(parent_ref, prior["raw_response_snapshot"])
        self.assertEqual(raw.encode(), agent_memory.restore(child, prior["raw_response_snapshot"])["response.txt"])
        recovery.write_journal(self.pkg, child, [record], 1)
        self.assertEqual(child.root, recovery.resolve_active(self.pkg)[0].root)
        captured = []
        role = self.role(Package(child.root), [canonical.dumps(AST).decode()], captured)
        result = formalize.run(child, self.events, agent=role, max_attempts=1,
            previous_candidate=prior, recovery_feedback=parameters["recovery_context"]["feedback"])
        self.assert_pass(result)
        self.assertIn(raw, captured[0]["user"])
        self.assertIn("VERIFIED RESPONSE SNAPSHOT", captured[0]["user"])
        self.assertEqual(raw.encode(), agent_memory.restore(self.pkg, parent_ref)["response.txt"])

    def test_rejected_response_text_mismatch_blocks_before_provider(self):
        role = self.role(self.pkg, ["not json"], [])
        formalize.run(self.pkg, self.events, agent=role, max_attempts=1)
        ref = agent_memory.latest_snapshot(self.pkg, stage_prefix="formalize/attempt")
        prior = canonical.loads(agent_memory.restore(self.pkg, ref)["payload.json"])["candidate"]
        prior["raw_response"] += "tampered"
        next_role = self.role(self.pkg, [], [])
        with self.assertRaises(BlockedError) as caught:
            formalize.run(self.pkg, self.events, agent=next_role, max_attempts=1, previous_candidate=prior)
        self.assertEqual("STALE_OR_UNBOUND_EVIDENCE", caught.exception.diagnostics[0].code)


if __name__ == "__main__":
    unittest.main()
