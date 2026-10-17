"""Explicit pre-dispatch critic fallback; fixtures are not live-model results."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_autonomous_correction as workflow
import test_autonomous_probe_signal as fixture
import test_critic_routing as routing_fixture
from verislop import agent_memory, agents, autonomous, canonical, formalize
from verislop.errors import BlockedError, Diagnostic, InfrastructureError, UsageError


def context_failure():
    return InfrastructureError("exact primary allocation rejected", [Diagnostic(
        "PROVIDER_FAILURE", "full input plus reserved output exceeds context", severity="infrastructure",
        details={"kind": "context_budget_exceeded", "call_dispatched": False, "prompt_preflight": {
            "kind": "context_budget_exceeded", "fits": False, "input_tokens": 41000,
            "declared_max_output_tokens": 2048, "context_window_tokens": 40960,
            "total_budget_tokens": 43048, "rendered_prompt_sha256": "sha256:" + "1" * 64}})])


class CriticCapacityTests(unittest.TestCase):
    run_critic = routing_fixture.CriticRoutingTests.run_critic
    valid = staticmethod(routing_fixture.CriticRoutingTests.valid)
    executed = staticmethod(routing_fixture.CriticRoutingTests.executed)

    def setUp(self):
        routing_fixture.CriticRoutingTests.setUp(self)
        self.conf["critic_routing"]["on_context_limit"] = True

    def test_capacity_fallback_retains_exact_packet_error_and_effective_slot(self):
        failure = context_failure()
        result, calls = self.run_critic([failure, self.valid()], [self.executed()])
        self.assertEqual(["critic", "senior"], [c["agent"] for c in calls])
        self.assertEqual("SEARCH_COMPLETED", result["status"])
        self.assertEqual(["CONTEXT_LIMIT", "SEARCH_COMPLETED"], [r["status"] for r in result["results"]])
        observation = result["results"][0]
        self.assertFalse(observation["counts_as_vote"])
        self.assertEqual([calls[-1]["instance"]], result["tiers"][0]["effective_membership"])
        self.assertEqual("senior", result["results"][-1]["agent"])
        self.assertEqual("critic", result["results"][-1]["configured_agent"])
        dispatch = calls[-1]["data"]["critic_dispatch"]
        self.assertEqual("primary_context_budget_exceeded", dispatch["reason"])
        self.assertEqual(observation["failed_allocation"], dispatch["primary_capacity_failure"])
        retained = dispatch["primary_capacity_failure"]["failure"]
        self.assertEqual(str(failure), retained["message"])
        self.assertEqual([d.to_json() for d in failure.diagnostics], retained["diagnostics"])
        for key in calls[0]["data"]:
            if key != "critic_dispatch":
                self.assertEqual(calls[0]["data"][key], calls[-1]["data"][key], key)
        self.assertFalse(result["milestone_authority"])

    def test_opt_in_required_even_when_protocol_routing_is_enabled(self):
        for flag in (None, False):
            with self.subTest(flag=flag):
                self.setUp()
                if flag is None:
                    del self.conf["critic_routing"]["on_context_limit"]
                else:
                    self.conf["critic_routing"]["on_context_limit"] = flag
                with self.assertRaisesRegex(InfrastructureError, "exact primary allocation"):
                    self.run_critic([context_failure()])

    def test_routing_disabled_remains_terminal(self):
        self.conf["critic_routing"]["enabled"] = False
        with self.assertRaisesRegex(InfrastructureError, "exact primary allocation"):
            self.run_critic([context_failure()])

    def test_resume_revalidates_fallback_without_redispatch_or_budget_reset(self):
        first, _ = self.run_critic([context_failure(), self.valid()], [self.executed()])
        resumed, calls = self.run_critic([], [self.executed()])
        self.assertEqual([], calls)
        self.assertEqual(first["results"], resumed["results"])
        snapshot = agent_memory.latest_snapshot(self.pkg, stage_prefix="critic-route/")
        state = canonical.loads(agent_memory.restore(self.pkg, snapshot)["payload.json"])
        self.assertEqual(2, len(state["attempts"]))
        self.assertEqual(1, sum("failure" in a for a in state["attempts"].values()))

    def test_context_policy_change_cannot_reset_retained_allocation(self):
        self.run_critic([context_failure(), self.valid()], [self.executed()])
        self.conf["critic_routing"]["on_context_limit"] = False
        with self.assertRaisesRegex(BlockedError, "configuration binding differs"):
            self.run_critic([])

    def test_failure_after_invalid_primary_preserves_raw_response_and_protocol_errors(self):
        malformed = {"unrecognized": "complete prior primary response"}
        result, calls = self.run_critic([malformed, context_failure(), self.valid()], [self.executed()])
        self.assertEqual(["critic", "critic", "senior"], [c["agent"] for c in calls])
        self.assertEqual(canonical.dumps(malformed).decode(), calls[-1]["data"]["previous_response"])
        self.assertEqual(calls[1]["data"]["protocol_errors"], calls[-1]["data"]["protocol_errors"])
        self.assertTrue(calls[-1]["data"]["protocol_errors"])
        self.assertEqual(2, result["results"][0]["failed_allocation"]["ordinal"])
        resumed, calls = self.run_critic([], [self.executed()])
        self.assertEqual([], calls)
        self.assertEqual(result["results"], resumed["results"])

    def test_prior_probe_replay_limitations_are_retained(self):
        no_execution = {"status": "UNKNOWN", "receipts": [], "execution_observations": [],
                        "diagnostics": [{"kind": "UNKNOWN_EVALUATION", "message": "fixture body unavailable"}]}
        result, calls = self.run_critic([self.valid(), context_failure(), self.valid()],
                                       [no_execution, self.executed()])
        self.assertEqual([no_execution], result["results"][0]["attempted_checks"])
        self.assertTrue(any("body unavailable" in x for x in calls[-1]["data"]["protocol_errors"]))

    def test_primary_counterexample_veto_is_not_replaced_by_fallback(self):
        checked = {"status": "REFUTED", "receipts": [{"status": "REFUTED", "obligation_id": "O1"}],
                   "diagnostics": [], "execution_observations": []}
        result, calls = self.run_critic([self.valid()], [checked])
        self.assertEqual("REPAIR", result["status"])
        self.assertEqual(["critic"], [c["agent"] for c in calls])

    def test_fallback_counterexample_still_vetoes_consensus(self):
        checked = {"status": "REFUTED", "receipts": [{"status": "REFUTED", "obligation_id": "O1"}],
                   "diagnostics": [], "execution_observations": []}
        result, _ = self.run_critic([context_failure(), self.valid()], [checked])
        self.assertEqual("REPAIR", result["status"])
        self.assertEqual("CHANGES_REQUESTED", result["tiers"][0]["result"])

    def test_valid_primary_abstention_remains_unchanged(self):
        proposal = self.valid()
        proposal["verdict"] = "REPAIR"
        result, calls = self.run_critic([proposal], [self.executed()])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual(["critic"], [c["agent"] for c in calls])

    def test_fallback_capacity_error_is_terminal_and_durable(self):
        with self.assertRaises(InfrastructureError):
            self.run_critic([context_failure(), context_failure()])
        with self.assertRaisesRegex(InfrastructureError, "retained critic dispatch failure"):
            self.run_critic([])

    def test_fallback_protocol_attempt_cap_is_not_reset(self):
        result, calls = self.run_critic([context_failure(), {}, {}])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual(["critic", "senior", "senior"], [c["agent"] for c in calls])
        result, calls = self.run_critic([])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual([], calls)

    def test_fallback_checker_error_is_terminal(self):
        with self.assertRaisesRegex(ValueError, "native checker unavailable"):
            self.run_critic([context_failure(), self.valid()], [ValueError("native checker unavailable")])

    def test_non_capacity_and_ambiguous_errors_never_route(self):
        cases = []
        for key, value in (("call_dispatched", True), ("call_dispatched", 0), ("kind", "network"),
                           ("binding_failure", True), ("binding_failure", 1), ("binding_failure", "false"),
                           ("binding_failure", None), ("prompt_preflight", None)):
            e = context_failure(); e.diagnostics[0].details[key] = value; cases.append((key, e))
        for key, value in (("fits", True), ("fits", 0), ("kind", "provider_error"),
                           ("input_tokens", True), ("input_tokens", -1), ("input_tokens", "41000"),
                           ("declared_max_output_tokens", 0), ("context_window_tokens", 0),
                           ("total_budget_tokens", 43049), ("context_window_tokens", 43048)):
            e = context_failure(); e.diagnostics[0].details["prompt_preflight"][key] = value; cases.append((key, e))
        e = context_failure(); e.diagnostics.append(Diagnostic("BUDGET_EXHAUSTED", "global call cap")); cases.append(("mixed", e))
        e = context_failure(); e.diagnostics *= 2; cases.append(("duplicate", e))
        e = context_failure(); e.diagnostics[0].severity = "warning"; cases.append(("severity", e))
        cases.extend((name, InfrastructureError(message, diagnostics)) for name, message, diagnostics in [
            ("text-only", "context_budget_exceeded", []),
            ("global-budget", "tokens exhausted", [Diagnostic("BUDGET_EXHAUSTED", "global token cap")]),
            ("checker", "checker failure", [Diagnostic("VERIFIER_FAILURE", "native checker failed")])])
        cases.append(("usage", UsageError("capacity-like usage", context_failure().diagnostics)))
        for label, error in cases:
            with self.subTest(label=label):
                self.setUp()
                with self.assertRaises(type(error)):
                    self.run_critic([error])


class RealLeanCriticCapacityTest(unittest.TestCase):
    setUp = workflow.AutonomousCorrectionTests.setUp
    assert_pass = workflow.AutonomousCorrectionTests.assert_pass
    finish_tested = workflow.AutonomousCorrectionTests.finish_tested

    def test_capacity_fallback_crosses_real_replay_and_tested_gates(self):
        conf = copy.deepcopy(workflow.CONFIG)
        conf["review"]["review_tiers"] = [workflow.tier("R0", "critic", 1)]
        conf["critic_routing"] = {"enabled": True, "fallback_agent": "senior", "fallback_attempts": 2,
                                  "on_context_limit": True}
        calls = []
        def call(agent, instance, system, user, purpose):
            calls.append((agent, purpose))
            if purpose == "formalize":
                value = workflow.AST
            elif purpose == "critic":
                if agent == "critic":
                    raise context_failure()
                value = fixture.response([{"obligation_id": "O1", "inputs": [workflow.INPUT]}])
            elif purpose == "generate":
                value = {"files": {"main.py": 'def bump(data):\n    return data["value"] + 1\n'},
                    "bindings": {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
                        "serialization_profile": "python-v0_2", "helpers": [], "bindings": [{"binding_id": "B1", "symbol": "bump",
                            "object": {"file": "main.py", "qualname": "bump"}, "obligations": ["O1"]}]}}
            else:
                raise AssertionError(purpose)
            return SimpleNamespace(text=canonical.dumps(value).decode(), request_id="authored-capacity-fixture")
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), conf)):
            proposer = agents.formalizer_agent("unused", self.pkg, self.events)
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
            implementer = agents.implementer_agent("unused", self.pkg, self.events)
        self.assert_pass(formalize.run(self.pkg, self.events, agent=proposer, critic=critic, max_attempts=1))
        self.assertEqual(["critic", "senior"], [a for a, p in calls if p == "critic"])
        self.finish_tested(implementer)


if __name__ == "__main__":
    unittest.main()
