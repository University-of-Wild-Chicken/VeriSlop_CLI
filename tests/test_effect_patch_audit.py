"""Offline audit regressions for effect checking and the actual review entry point."""
from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from verislop import canonical
from verislop.agent_effects import Artifact, EffectError, Operation, Plan, SIGNATURES, check, review_call
from verislop.providers.broker import Budget

import test_review_protocol_repair as protocol_tests
from test_providers_review import accepted_review, review_packet


class EffectAuthorityAuditTests(unittest.TestCase):
    def setUp(self):
        self.conf = {
            "agent_effect_dsl": {"enabled": True},
            "agents": {
                "critic": {"tool_profile": "review_readonly", "max_output_tokens": 10},
                "second": {"tool_profile": "review_readonly", "max_output_tokens": 10},
            },
            "review": {"budgets": {
                "max_calls_per_instance": 1, "max_total_tokens": 100, "max_provider_retries": 0,
            }},
        }
        self.step = Operation("review", "critic", "slot", Artifact(
            "review_packet", "target", "sha256:" + "a" * 64), SIGNATURES["review"][3], 10, 0)
        self.plan = Plan((self.step,), 1, 10, 1)

    def broker(self, conf=None, budget=None):
        return SimpleNamespace(r=SimpleNamespace(conf=self.conf if conf is None else conf),
                               budget=budget or Budget(1, 100, 0), call=Mock(return_value="untrusted"))

    def call(self, broker, conf=None):
        return review_call(broker, "critic", "slot", "system", "user", "release", "target", conf)

    def test_explicit_configuration_cannot_substitute_dispatch_authority(self):
        actual = copy.deepcopy(self.conf)
        actual["agents"]["critic"]["tool_profile"] = "candidate_writer"
        broker = self.broker(actual)
        with self.assertRaises(EffectError):
            self.call(broker, self.conf)
        broker.call.assert_not_called()

    def test_explicit_configuration_cannot_disable_actual_opt_in(self):
        override = copy.deepcopy(self.conf)
        override["agent_effect_dsl"]["enabled"] = False
        broker = self.broker()
        with self.assertRaises(EffectError):
            self.call(broker, override)
        broker.call.assert_not_called()

    def test_custom_runtime_budget_is_the_checked_retry_authority(self):
        broker = self.broker(budget=Budget(1, 100, 2))
        with patch("verislop.agent_effects.check", wraps=check) as checked:
            self.assertEqual("untrusted", self.call(broker))
        plan, conf = checked.call_args.args
        self.assertEqual(2, plan.steps[0].retries)
        self.assertEqual(3, plan.max_attempts)
        self.assertEqual(2, conf["review"]["budgets"]["max_provider_retries"])
        self.assertEqual(0, self.conf["review"]["budgets"]["max_provider_retries"])
        broker.call.assert_called_once()

    def test_custom_runtime_budget_cannot_exceed_actual_output_allowance(self):
        broker = self.broker(budget=Budget(1, 5, 0))
        with self.assertRaises(EffectError):
            self.call(broker)
        broker.call.assert_not_called()

    def test_direct_ast_validation_cannot_be_bypassed_by_skipping_parse(self):
        malformed = [
            replace(self.plan, steps=[self.step]),
            replace(self.plan, max_calls=True),
            replace(self.plan, steps=(replace(self.step, output_tokens=True),)),
            replace(self.plan, steps=(replace(self.step, retries=False),)),
            replace(self.plan, steps=(replace(self.step, effects=set(self.step.effects)),)),
            replace(self.plan, steps=(replace(self.step, artifact=replace(self.step.artifact, identity=" ")),)),
            replace(self.plan, steps=(replace(self.step, artifact=replace(self.step.artifact, kind="accepted_contract")),)),
        ]
        for candidate in malformed:
            with self.subTest(candidate=candidate), self.assertRaises(EffectError):
                check(candidate, self.conf)

    def test_instance_call_limit_is_shared_across_agent_names(self):
        second = replace(self.step, agent="second")
        with self.assertRaises(EffectError):
            check(Plan((self.step, second), 2, 20, 2), self.conf)
        self.assertEqual(SIGNATURES["review"][3], check(
            Plan((self.step, replace(second, instance="other")), 2, 20, 2), self.conf))


class EffectReviewEntryAuditTests(unittest.TestCase):
    # Reuse only the ordinary CLI/mock fixture, not its inherited test methods.
    setUp = protocol_tests.ReviewProtocolRepairTests.setUp
    configure = protocol_tests.ReviewProtocolRepairTests.configure
    invoke = protocol_tests.ReviewProtocolRepairTests.invoke

    def enable(self, **budgets):
        conf = self.configure(**budgets)
        conf["agent_effect_dsl"] = {"enabled": True}
        self.config.write_bytes(canonical.dumps(conf))

    def test_static_budget_rejection_retains_incomplete_campaign_without_dispatch(self):
        self.enable(max_total_tokens=1)
        code, result, output, campaign, certificate = self.invoke()
        self.assertNotEqual(0, code, output)
        self.assertEqual("INCOMPLETE", certificate["final"])
        self.assertEqual(0, len(self.mock.requests))
        self.assertEqual(1, certificate["tiers"][0]["tally"]["members"])
        self.assertEqual(["R0/critic#1"], certificate["tiers"][0]["tally"]["missing"])
        self.assertEqual("effect_check_failed", certificate["tiers"][0]["execution_failures"][0]["kind"])
        attempt = canonical.load_file(campaign / "ballot-attempts/R0_critic#1/1.json")
        self.assertEqual("effect_check_failed", attempt["status"])
        self.assertEqual(["budget exceeded"], attempt["diagnostics"])
        self.assertFalse(list((campaign / "ballots").glob("*.json")))

    def test_opt_in_still_corrects_invalid_ballot_then_replays_exact_model_proposal(self):
        self.enable()
        responses = []

        def respond(system, user, model):
            packet = review_packet(user)
            ballot = accepted_review(user, packet["scope"])
            if not responses:
                ballot["search"]["probes"][0]["note"] = "not an allowed probe field"
            responses.append(json.dumps(ballot))
            return responses[-1]

        self.handler = respond
        code, result, output, campaign, certificate = self.invoke()
        self.assertEqual(0, code, (result, output))
        self.assertEqual("REVIEW_ACCEPTED", certificate["final"])
        self.assertEqual(2, len(self.mock.requests))
        first, corrected = [r["body"]["messages"][1]["content"] for r in self.mock.requests]
        self.assertEqual(review_packet(first), review_packet(corrected))
        self.assertIn(responses[0], corrected)
        self.assertIn("unexpected keys: ['note']", corrected)
        attempts = campaign / "ballot-attempts/R0_critic#1"
        self.assertEqual("invalid_protocol", canonical.load_file(attempts / "1.json")["status"])
        self.assertEqual("valid_protocol", canonical.load_file(attempts / "2.json")["status"])
        self.assertEqual(responses[1], (attempts / "2.raw.txt").read_text())
        ballot = canonical.load_file(campaign / "ballots/R0_critic#1.json")
        self.assertEqual(responses[1], (campaign / "ballots/R0_critic#1.raw.txt").read_text())
        self.assertEqual("ACCEPT", ballot["verdict"])
        self.assertTrue(ballot["counterexample_receipts"])
        self.assertTrue(all(r["status"] == "NOT_REPRODUCED" for r in ballot["counterexample_receipts"]))
