"""Authored mock agents self-correct through real Lean and TESTED gates.

These are regression fixtures, not local-model benchmark scores.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_formal_frontend_workflow import AST, BODY
import test_formal_frontend_workflow as workflow_fixture
from verislop import accept, agent_memory, agents, autonomous, canonical, closure, contract, export, formalize, fsutil, generate, link, prove, testing


def tier(name, agent, count):
    return {"id": name, "reviewers": [{"agent": agent, "count": count, "focus": ["concrete boundary cases"]}],
            "consensus": {"mode": "unanimous", "require_all_responses": True, "max_soft_rejects": 0,
                          "max_abstentions": 0, "blocking_findings_veto": True}}


CONFIG = {"roles": {"formalizer": "writer", "prover": "prover", "implementer": "coder"},
          "review": {"review_tiers": [tier("lower", "critic", 2), tier("higher", "senior", 1)]}}
INPUT = {"dict": {"value": {"int": "0"}}}


class AutonomousCorrectionTests(unittest.TestCase):
    setUp = workflow_fixture.FrontendWorkflowTests.setUp
    assert_pass = workflow_fixture.FrontendWorkflowTests.assert_pass

    def roles(self, proposals, *, reference=False, invalid_once=False):
        proposals = iter(proposals)
        captured = []
        bad_sent = False
        source = 'def bump(data):\n    return data["value"] + 1\n'
        bindings = {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
                    "serialization_profile": "python-v0_2", "helpers": [], "bindings": [{"binding_id": "B1", "symbol": "bump",
                    "object": {"file": "main.py", "qualname": "bump"}, "obligations": ["O1"]}]}

        def call(agent, instance, system, user, purpose):
            nonlocal bad_sent
            captured.append({"agent": agent, "instance": instance, "system": system, "user": user, "purpose": purpose})
            if purpose == "formalize":
                text = canonical.dumps(next(proposals)).decode()
            elif purpose == "critic":
                data = json.loads(user)
                if invalid_once and not bad_sent:
                    bad_sent = True
                    text = canonical.dumps({"verdict": "ACCEPT"}).decode()
                else:
                    correction = [{"diagnostic_index": 0, "artifact": "proposal.lean",
                                   "explanation": "Preserve the plus-one request; the theorem RHS must include the increment."}] if data["diagnostics"] else []
                    probe = {"obligation_id": "O1", "inputs": [INPUT]}
                    if reference:
                        probe.update({"entry_symbol": "bump", "exact_clause_id": "C1", "expected": {"int": "1"}})
                    text = canonical.dumps({"encoding": autonomous.VERSION, "verdict": "REPAIR" if correction else "ACCEPT",
                                            "corrections": correction, "counterexamples": [] if correction else [probe]}).decode()
            elif purpose == "generate":
                text = canonical.dumps({"files": {"main.py": source}, "bindings": bindings}).decode()
            else:
                raise AssertionError("unexpected mock role: " + purpose)
            return SimpleNamespace(text=text, request_id="authored-autonomous-fixture")

        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), CONFIG)):
            proposer = agents.formalizer_agent("unused", self.pkg, self.events)
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
            implementer = agents.implementer_agent("unused", self.pkg, self.events)
        return proposer, critic, implementer, captured

    def finish_tested(self, implementer):
        self.assert_pass(prove.run(self.pkg, self.events, budget_seconds=0))
        self.assert_pass(accept.run(self.pkg, self.events))
        self.assert_pass(export.run(self.pkg, self.events))
        self.assert_pass(generate.run(self.pkg, self.events, agent=implementer, tier=0, target="python", require_state="TESTED"))
        self.assert_pass(link.run(self.pkg, self.events))
        self.assert_pass(testing.run(self.pkg, self.events, seed=97, cases=24))
        self.assert_pass(closure.run(self.pkg, self.events))
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual("PASS", report["obligations"]["O1"]["outcomes"]["TESTED"])
        self.assertNotEqual("PASS", report["obligations"]["O1"]["outcomes"]["END_TO_END_VERIFIED"])

    def test_false_contract_is_refuted_then_agents_correct_it_before_freeze_and_test_code(self):
        wrong = copy.deepcopy(AST)
        wrong["theorems"]["result"]["formula"]["body"]["right"] = BODY["left"]
        proposer, critic, implementer, captured = self.roles([wrong, AST])
        self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, critic=critic, max_attempts=2))
        calls = [c for c in captured if c["purpose"] == "critic"]
        self.assertEqual(["critic", "critic", "critic", "critic", "senior"], [c["agent"] for c in calls])
        second = [c for c in captured if c["purpose"] == "formalize"][1]
        self.assertIn("Lean replayed a concrete negation", second["user"])
        memory = agent_memory.context_for(self.pkg, last=2, stages=["formalize/attempt"])
        old = memory["snapshots"][0]
        self.assertEqual(wrong, canonical.loads(old["artifacts"]["typed-proposal.json"]["content"]))
        payload = canonical.loads(old["artifacts"]["payload.json"]["content"])
        self.assertIn("CONTRACT_REFUTED", [d["code"] for d in payload["diagnostics"]])
        self.assertIn("sorry", old["artifacts"]["proposal.lean"]["content"])
        frozen = (contract.challenge_dir(self.pkg) / "Contract.lean").read_bytes()
        self.finish_tested(implementer)
        self.assertEqual(frozen, (contract.challenge_dir(self.pkg) / "Contract.lean").read_bytes())

    def test_proved_wrong_reference_gets_concrete_semantic_feedback_without_claiming_nl_proof(self):
        wrong = copy.deepcopy(AST)
        wrong["symbols"]["bump"]["body"] = copy.deepcopy(BODY["left"])
        wrong["theorems"]["result"]["formula"]["body"]["right"] = copy.deepcopy(BODY["left"])
        proposer, critic, implementer, captured = self.roles([wrong, AST], reference=True, invalid_once=True)
        self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, critic=critic, max_attempts=2))
        saved = agent_memory.context_for(self.pkg, last=2, stages=["formalize/attempt"])
        first = canonical.loads(saved["snapshots"][0]["artifacts"]["payload.json"]["content"])
        receipt = first["critique"]["results"][0]["checked"]["receipts"][0]
        self.assertEqual("SEMANTIC_MISMATCH", receipt["status"])
        self.assertEqual({"int": "0"}, receipt["actual"])
        self.assertEqual({"int": "1"}, receipt["expected"])
        self.assertFalse(receipt["natural_language_clause_verified"])
        self.assertFalse(receipt["guarantee_refuted"])
        self.assertIn("REFERENCE_REQUEST_MISMATCH", [d["code"] for d in first["diagnostics"]])
        self.assertIn("protocol_errors", [c["user"] for c in captured if c["purpose"] == "critic"][1])
        self.finish_tested(implementer)

    def test_repeated_failed_proof_receives_critique_then_stops_and_retains_diagnostics(self):
        proposer, critic, _, _ = self.roles([AST])
        self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1))
        challenge = (contract.challenge_dir(self.pkg) / "Contract.lean").read_text()
        contexts = []
        def generator(ctx):
            contexts.append(ctx)
            return challenge
        failed = {"ok": False, "errors": ["unknown constant fixture.badName"], "sorries": 1, "complete": False, "wall_ms": 1}
        with patch.object(prove, "evaluate", return_value=failed):
            result = prove.run(self.pkg, self.events, agent=generator, critic=critic, max_attempts=8,
                               portfolio=False, budget_seconds=0)
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(3, len(contexts))
        self.assertTrue(any(d.code == "NO_PROGRESS" for d in result.diagnostics))
        self.assertIn("CRITIC DIAGNOSTIC REPAIR", contexts[-1]["critique"]["feedback"][0])
        saved = agent_memory.context_for(self.pkg, last=3, stages=["prove/attempt"])
        self.assertEqual(3, len(saved["snapshots"]))
        self.assertEqual(challenge, saved["snapshots"][-1]["artifacts"]["proposal.lean"]["content"])

    def test_speculative_empty_or_forged_diagnostic_criticism_is_rejected(self):
        data = {"clauses": [], "statements": {"O1": {"role": "guarantee", "representation": "contract_dsl"}}, "diagnostics": []}
        value = {"encoding": autonomous.VERSION, "verdict": "REPAIR", "counterexamples": [], "corrections": []}
        self.assertTrue(autonomous.validate(value, data))
        value["corrections"] = [{"diagnostic_index": 0, "artifact": "proposal.lean", "explanation": "maybe unreliable"}]
        self.assertTrue(autonomous.validate(value, data))

    def test_quorum_tolerates_configured_abstention_and_escalates_to_higher_tier(self):
        lower = tier("lower", "bad", 1)
        lower["reviewers"].append({"agent": "good", "count": 1, "focus": []})
        lower["consensus"].update({"mode": "quorum", "min_accepts": 1, "require_all_responses": False,
                                   "max_abstentions": 1})
        conf = {"review": {"review_tiers": [lower, tier("higher", "senior", 1)]}}
        calls = []
        def call(agent, *args):
            calls.append(agent)
            text = "{}" if agent == "bad" else canonical.dumps({"encoding": autonomous.VERSION, "verdict": "ACCEPT",
                "counterexamples": [], "corrections": []}).decode()
            return SimpleNamespace(text=text)
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), conf)):
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        result = critic({"phase": "formalize", "attempt": 1, "source": b"-- opaque candidate", "form": {},
                         "records": [], "ledger": ledger, "diagnostics": [], "analysis": None, "statements": {}})
        self.assertEqual(["bad", "bad", "good", "senior"], calls)
        self.assertEqual("SEARCH_COMPLETED", result["status"])
        self.assertEqual(["TIER_ACCEPTED", "TIER_ACCEPTED"], [t["result"] for t in result["tiers"]])
        self.assertTrue(all(d["severity"] == "warning" for d in result["diagnostics"]))
        self.assertFalse(result["milestone_authority"])

    def test_proof_stage_rejects_noncanonical_probe_using_frozen_signatures(self):
        proposer, _, _, _ = self.roles([AST])
        self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1))
        from verislop.errors import Diagnostic
        raw = {"encoding": autonomous.VERSION, "verdict": "REPAIR", "counterexamples": [{"obligation_id": "O1",
            "inputs": [{"dict": {"value": {"int": "01"}}}]}], "corrections": [{"diagnostic_index": 0,
            "artifact": "proposal.lean", "explanation": "Close the recorded proof hole."}]}
        broker = SimpleNamespace(call=lambda *args: SimpleNamespace(text=canonical.dumps(raw).decode()))
        with patch.object(agents, "_broker", return_value=(broker, CONFIG)):
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        with patch.object(autonomous.contract_refutation, "check") as checker:
            result = critic({"phase": "prove", "attempt": 1, "source": b"-- fixture", "form": {}, "records": [],
                "ledger": ledger, "analysis": None, "profile": contract.frozen_json(self.pkg, "profile.json"),
                "statements": contract.frozen_json(self.pkg, "statements.json")["statements"],
                "diagnostics": [Diagnostic("PROOF_UNRESOLVED", "one remaining proof hole")]})
        self.assertEqual("INCOMPLETE", result["status"])
        checker.assert_not_called()
        self.assertTrue(all(r["status"] == "INVALID" for r in result["results"]))

    def test_context_cli_reloads_exact_json_and_lean_without_modifying_package(self):
        source = b"import Std\n-- retained rejected proposal\n"
        agent_memory.checkpoint(self.pkg, "formalize/attempt", {"proposal.lean": source,
            "formalization.json": canonical.dumps({"authored": "rejected"})})
        before = {name: (self.pkg.root / name).read_bytes() for name in fsutil.list_files(self.pkg.root)}
        response = subprocess.run([sys.executable, "-m", "verislop", "context", "--package", str(self.pkg.root),
            "--json", "--last", "1", "--stage-prefix", "formalize/attempt"], capture_output=True, text=True)
        self.assertEqual(0, response.returncode, response.stderr)
        data = json.loads(response.stdout)["summary"]
        self.assertEqual(source.decode(), data["snapshots"][0]["artifacts"]["proposal.lean"]["content"])
        self.assertEqual(before, {name: (self.pkg.root / name).read_bytes() for name in fsutil.list_files(self.pkg.root)})


if __name__ == "__main__":
    unittest.main()
