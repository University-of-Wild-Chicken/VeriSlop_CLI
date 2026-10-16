"""Explicit critic protocol fallback; authored fixtures, never benchmark scores."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_autonomous_correction as workflow
import test_autonomous_probe_signal as fixture
from verislop import agents, autonomous, canonical, contract_refutation, formalize, schemas
from verislop.errors import BlockedError, Diagnostic, InfrastructureError
from verislop.providers import config


class CriticRoutingTests(unittest.TestCase):
    def setUp(self):
        fixture.AutonomousProbeSignalTests.setUp(self)
        self.conf["critic_routing"] = {"enabled": True, "fallback_agent": "senior", "fallback_attempts": 2}

    def run_critic(self, proposals, checks=None):
        pending = iter(proposals)
        calls = []
        def call(agent, instance, system, user, purpose):
            calls.append({"agent": agent, "instance": instance, "data": json.loads(user)})
            value = next(pending)
            if isinstance(value, BaseException):
                raise value
            return SimpleNamespace(text=canonical.dumps(value).decode())
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), self.conf)):
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
        with patch.object(contract_refutation, "check", side_effect=checks or AssertionError("unexpected checker call")):
            result = critic(self.ctx)
        return result, calls

    @staticmethod
    def valid():
        return fixture.response([{"obligation_id": "O1", "inputs": [fixture.INPUT]}])

    @staticmethod
    def executed():
        return {"status": "UNKNOWN", "receipts": [], "diagnostics": [],
                "execution_observations": [{"obligation_id": "O1", "calls": [{"symbol": "shift"}]}]}

    def test_invalid_primary_resolves_one_slot_with_actual_fallback_identity_and_same_packet(self):
        result, calls = self.run_critic([{}, {}, self.valid()], [self.executed()])
        self.assertEqual(["critic", "critic", "senior"], [c["agent"] for c in calls])
        self.assertEqual("SEARCH_COMPLETED", result["status"])
        self.assertEqual(["INVALID", "SEARCH_COMPLETED"], [r["status"] for r in result["results"]])
        self.assertFalse(result["results"][0]["counts_as_vote"])
        self.assertEqual([calls[-1]["instance"]], result["tiers"][0]["effective_membership"])
        self.assertEqual("senior", result["results"][-1]["agent"])
        self.assertEqual("critic", result["results"][-1]["configured_agent"])
        for field in ("request", "lean_source", "formalization", "profile", "statements", "diagnostics", "probe_interface"):
            self.assertEqual(calls[0]["data"][field], calls[-1]["data"][field])
        self.assertFalse(result["milestone_authority"])
        self.assertTrue(calls[-1]["data"]["protocol_errors"])
        self.assertEqual("primary_protocol_exhausted", calls[-1]["data"]["critic_dispatch"]["reason"])

    def test_retained_responses_are_revalidated_without_new_dispatch_after_resume(self):
        self.run_critic([{}, {}, self.valid()], [self.executed()])
        result, calls = self.run_critic([], [self.executed()])
        self.assertEqual([], calls)
        self.assertEqual("SEARCH_COMPLETED", result["status"])

    def test_exhausted_fallback_remains_incomplete_and_does_not_reset_on_resume(self):
        result, calls = self.run_critic([{}, {}, {}, {}])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual(["critic", "critic", "senior", "senior"], [c["agent"] for c in calls])
        result, calls = self.run_critic([])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual([], calls)

    def test_actual_primary_counterexample_veto_never_calls_fallback(self):
        checked = {"status": "REFUTED", "receipts": [{"status": "REFUTED", "obligation_id": "O1"}],
                   "diagnostics": [], "execution_observations": []}
        result, calls = self.run_critic([self.valid()], [checked])
        self.assertEqual("REPAIR", result["status"])
        self.assertEqual(["critic"], [c["agent"] for c in calls])
        result, calls = self.run_critic([], [checked])
        self.assertEqual("REPAIR", result["status"])
        self.assertEqual([], calls)

    def test_valid_abstention_is_not_replaced(self):
        value = self.valid()
        value["verdict"] = "REPAIR"
        result, calls = self.run_critic([value], [self.executed()])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual(["critic"], [c["agent"] for c in calls])

    def test_current_requirements_reject_stale_diagnostics(self):
        self.ctx["previous_critique"] = {"diagnostics": [{"message": "old parse error"}]}
        stale = {"encoding": autonomous.VERSION, "verdict": "REPAIR", "counterexamples": [],
                 "corrections": [{"diagnostic_index": 0, "artifact": "proposal.lean", "explanation": "old fix"}]}
        result, calls = self.run_critic([stale, stale, self.valid()], [self.executed()])
        self.assertEqual("SEARCH_COMPLETED", result["status"])
        requirements = calls[-1]["data"]["current_response_requirements"]
        self.assertEqual([], requirements["current_diagnostic_indices"])
        self.assertTrue(requirements["corrections_must_be_empty"])
        self.assertTrue(requirements["functional_probe_required"])
        self.assertIn("actual diagnostic", calls[-1]["data"]["protocol_errors"][0])

    def test_opaque_search_remains_unsupported_without_fallback(self):
        self.ctx.update(analysis=None, statements={})
        result, calls = self.run_critic([fixture.response([])])
        self.assertEqual("SEARCH_UNSUPPORTED", result["status"])
        self.assertEqual(1, len(calls))
        self.assertFalse(result["milestone_authority"])

    def test_interrupted_dispatch_remains_consumed_and_blocks_same_job(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_critic([KeyboardInterrupt()])
        with self.assertRaisesRegex(BlockedError, "allocated but has no retained response"):
            self.run_critic([])

    def test_binding_change_rejects_resume(self):
        self.run_critic([{}, {}, self.valid()], [self.executed()])
        self.conf["critic_routing"]["fallback_attempts"] = 3
        with self.assertRaisesRegex(BlockedError, "configuration binding differs"):
            self.run_critic([])

    def test_disabling_or_removing_routing_cannot_reset_retained_attempts(self):
        self.run_critic([{}, {}, self.valid()], [self.executed()])
        self.conf["critic_routing"]["enabled"] = False
        with self.assertRaisesRegex(BlockedError, "cannot disable retained critic routing"):
            self.run_critic([])
        del self.conf["critic_routing"]
        with self.assertRaisesRegex(BlockedError, "cannot disable retained critic routing"):
            self.run_critic([])

    def test_provider_or_budget_failure_is_terminal_and_retained(self):
        failure = InfrastructureError("budget exhausted", [Diagnostic("BUDGET_EXHAUSTED", "no calls")])
        with self.assertRaisesRegex(InfrastructureError, "budget exhausted"):
            self.run_critic([failure])
        with self.assertRaisesRegex(InfrastructureError, "retained critic dispatch failure"):
            self.run_critic([])

    def test_checker_failure_is_not_reclassified_as_bad_model_protocol(self):
        with self.assertRaisesRegex(ValueError, "checker unavailable"):
            self.run_critic([self.valid()], [ValueError("checker unavailable")])

    def test_configuration_requires_declared_readonly_fallback_only_when_enabled(self):
        conf = canonical.load_file(Path(__file__).resolve().parents[1] / "examples/local-hybrid-config.json")
        self.assertEqual([], schemas.validate("review-config", conf))
        self.assertIn("sol-critic", config.resolve(conf, {}).used_agents)
        for key in ("fallback_agent", "fallback_attempts"):
            changed = copy.deepcopy(conf)
            del changed["critic_routing"][key]
            self.assertTrue(schemas.validate("review-config", changed))
        for value in (0, 4, True):
            changed = copy.deepcopy(conf)
            changed["critic_routing"]["fallback_attempts"] = value
            self.assertTrue(schemas.validate("review-config", changed))
        conf["agents"]["sol-critic"]["tool_profile"] = "candidate_writer"
        self.assertTrue(any("fallback agent sol-critic must use tool_profile review_readonly" in d.message
                            for d in config.resolve(conf, {}).diagnostics))
        conf["critic_routing"]["enabled"] = False
        self.assertNotIn("sol-critic", config.resolve(conf, {}).used_agents)

    def test_unused_model_alias_is_not_resolved_by_route_binding(self):
        self.conf["agents"] = {"unused": {"model_ref": "env:UNSET_UNUSED_MODEL"}}
        selected = []
        def model_for(agent):
            selected.append(agent)
            if agent == "unused":
                raise AssertionError("unused alias must not be resolved")
            return agent + "-model"
        autonomous._CriticAttempts(self.pkg, SimpleNamespace(model_for=model_for), self.conf,
                                   autonomous.packet(self.pkg, self.ctx), "configured-slot")
        self.assertEqual(["critic", "senior"], selected)


class RealLeanCriticFallbackTest(unittest.TestCase):
    setUp = workflow.AutonomousCorrectionTests.setUp
    assert_pass = workflow.AutonomousCorrectionTests.assert_pass
    finish_tested = workflow.AutonomousCorrectionTests.finish_tested

    def test_replayed_fallback_probe_crosses_real_lean_and_tested_gates(self):
        conf = copy.deepcopy(workflow.CONFIG)
        conf["review"]["review_tiers"] = [workflow.tier("R0", "critic", 1)]
        conf["critic_routing"] = {"enabled": True, "fallback_agent": "senior", "fallback_attempts": 2}
        calls = []
        def call(agent, instance, system, user, purpose):
            calls.append((agent, purpose))
            if purpose == "formalize":
                value = workflow.AST
            elif purpose == "critic":
                value = fixture.response([] if agent == "critic" else [{"obligation_id": "O1", "inputs": [workflow.INPUT]}])
            elif purpose == "generate":
                value = {"files": {"main.py": 'def bump(data):\n    return data["value"] + 1\n'},
                    "bindings": {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
                        "serialization_profile": "python-v0_2", "helpers": [], "bindings": [{"binding_id": "B1", "symbol": "bump",
                            "object": {"file": "main.py", "qualname": "bump"}, "obligations": ["O1"]}]}}
            else:
                raise AssertionError(purpose)
            return SimpleNamespace(text=canonical.dumps(value).decode(), request_id="authored-fallback-fixture")
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), conf)):
            proposer = agents.formalizer_agent("unused", self.pkg, self.events)
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
            implementer = agents.implementer_agent("unused", self.pkg, self.events)
        self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, critic=critic, max_attempts=1))
        self.assertEqual(["critic", "critic", "senior"], [a for a, p in calls if p == "critic"])
        self.finish_tested(implementer)


if __name__ == "__main__":
    unittest.main()
