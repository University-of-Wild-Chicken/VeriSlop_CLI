"""Critic search must submit actual software inputs; these are engineering fixtures."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import agents, autonomous, canonical, contract, contract_refutation as cr, dsl
from verislop.events import EventSink
from verislop.package import Package

VAR = {"tag": "var", "index": 0}
PROFILE = {"profile_id": "probe_signal", "dsl": dsl.ENCODING_V2,
    "records": {"Parcel": {"lean_decl": "Fixture.Parcel", "fields": [{"name": "amount", "sort": "Int"}]}},
    "symbols": {"shift": {"lean_decl": "Fixture.shift", "args": [{"record": "Parcel"}], "result": "Int"}},
    "predicates": {}, "enums": {}}
FORMULA = {"tag": "forall", "sort": {"record": "Parcel"}, "body": {"tag": "eq",
    "left": {"tag": "call", "symbol": "shift", "args": [VAR]},
    "right": {"tag": "field", "sort": "Parcel", "field": "amount", "value": VAR}}}


def statement(formula, closure):
    return {"role": "guarantee", "representation": "contract_dsl", "semantic_closure": closure,
            "formula_package": dsl.make_package(formula, PROFILE["profile_id"], encoding=dsl.ENCODING_V2)}


STATEMENTS = {"O1": statement(FORMULA, ["Fixture.shift"]),
    "NV1": statement({"tag": "exists", "sort": "Int", "body": {"tag": "eq", "left": VAR, "right": VAR}}, [])}
INPUT = {"dict": {"amount": {"int": "-2"}}}


def response(probes):
    return {"encoding": autonomous.VERSION, "verdict": "ACCEPT", "counterexamples": probes, "corrections": []}


class AutonomousProbeSignalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="verislop-critic-signal-")
        self.addCleanup(temp.cleanup)
        self.pkg = Package(Path(temp.name) / "package")
        self.pkg.ensure()
        self.pkg.path("prompt").parent.mkdir(parents=True, exist_ok=True)
        self.pkg.path("prompt").write_bytes(b"Deliver a signed parcel shift.")
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        self.addCleanup(self.events.close)
        self.ctx = {"phase": "formalize", "attempt": 1, "source": b"-- fixture", "form": {}, "records": [],
            "ledger": {"clauses": [{"start_byte": 0, "end_byte": 29, "refs": ["O1"]}]}, "diagnostics": [],
            "analysis": contract.Analysis(PROFILE, STATEMENTS, [], [], [])}
        self.conf = {"review": {"review_tiers": [{"id": "R0", "reviewers": [{"agent": "critic", "count": 1,
            "focus": []}], "consensus": {"mode": "unanimous", "require_all_responses": True,
            "max_soft_rejects": 0, "max_abstentions": 0, "blocking_findings_veto": True}}]}}

    def run_critic(self, proposals, checks=None):
        inputs = iter(proposals)
        calls = []
        def call(*args):
            calls.append(json.loads(args[3]))
            return SimpleNamespace(text=canonical.dumps(next(inputs)).decode())
        with patch.object(agents, "_broker", return_value=(SimpleNamespace(call=call), self.conf)):
            critic = autonomous.critic_agent("unused", self.pkg, self.events)
        with patch.object(cr, "check", side_effect=checks or AssertionError("no valid checker call expected")):
            result = critic(self.ctx)
        return result, calls

    def test_phase_specific_record_wire_and_functional_targets(self):
        data = autonomous.packet(self.pkg, self.ctx)
        interface = data["probe_interface"]
        self.assertTrue(interface["functional_search_available"])
        self.assertEqual({"dict": {"amount": {"int": "canonical decimal string; nonnegative for Nat"}}},
                         interface["targets"]["O1"]["universal_inputs"][0])
        self.assertFalse(interface["targets"]["NV1"]["functional"])
        self.assertEqual([], cr.validate_proposals(self.ctx["analysis"], [{"obligation_id": "O1", "inputs": [INPUT]}]))
        bad = {"record": {"amount": {"int": "-2"}}}
        self.assertTrue(cr.validate_proposals(self.ctx["analysis"], [{"obligation_id": "O1", "inputs": [bad]}]))

    def test_empty_nonvacuity_assignment_cannot_replace_software_probe(self):
        value = response([{"obligation_id": "NV1", "inputs": []}])
        result, calls = self.run_critic([value, value])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertIn("non-vacuity", calls[1]["protocol_errors"][0])
        self.assertTrue(any("non-vacuity" in f for f in result["feedback"]))
        self.assertFalse(result["milestone_authority"])

    def test_invalid_wire_shape_is_returned_to_critic_and_formalizer(self):
        value = response([{"obligation_id": "O1", "inputs": [{"dict": {"amount": {"int": "-02"}}}]}])
        result, calls = self.run_critic([value, value])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertTrue(calls[1]["protocol_errors"])
        self.assertTrue(result["feedback"])
        self.assertIn("probe_interface", calls[1])
        self.assertEqual([], result["results"][0]["attempted_checks"])

    def test_vacuous_search_retries_and_actual_call_remains_only_search(self):
        value = response([{"obligation_id": "O1", "inputs": [INPUT]}])
        empty = {"status": "UNKNOWN", "receipts": [], "diagnostics": [],
                 "execution_observations": [{"calls": []}]}
        executed = {"status": "UNKNOWN", "receipts": [],
            "diagnostics": [{"message": "closed negation did not elaborate"}],
            "execution_observations": [{"obligation_id": "O1", "inputs": [INPUT], "calls": [{"symbol": "shift"}],
                                        "milestone_authority": False}]}
        result, calls = self.run_critic([value, value], [empty, executed])
        self.assertEqual("SEARCH_COMPLETED", result["status"])
        self.assertIn("no submitted probe executed", calls[1]["protocol_errors"][0])
        self.assertEqual(2, len(result["results"][0]["attempted_checks"]))
        self.assertTrue(any("SEARCH LIMITATION" in f for f in result["feedback"]))
        self.assertFalse(result["milestone_authority"])

    def test_repeated_no_execution_is_incomplete_with_exact_checker_limitation(self):
        value = response([{"obligation_id": "O1", "inputs": [INPUT]}])
        unavailable = {"status": "UNKNOWN", "receipts": [], "execution_observations": [],
                       "diagnostics": [{"kind": "UNKNOWN_EVALUATION", "message": "body unavailable"}]}
        result, _ = self.run_critic([value, value], [unavailable, unavailable])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertTrue(any("body unavailable" in f for f in result["feedback"]))
        self.assertEqual(2, len(result["results"][0]["attempted_checks"]))

    def test_real_zero_argument_reference_entry_is_eligible(self):
        profile = {**PROFILE, "symbols": {"constant": {"lean_decl": "Fixture.constant", "args": [], "result": "Int"}}}
        st = {"O1": statement({"tag": "eq", "left": {"tag": "call", "symbol": "constant", "args": []},
                              "right": {"tag": "int", "value": "4"}}, ["Fixture.constant"])}
        self.ctx["analysis"] = contract.Analysis(profile, st, [], [], [])
        value = response([{"obligation_id": "O1", "entry_symbol": "constant", "exact_clause_id": "C1",
                           "inputs": [], "expected": {"int": "4"}}])
        self.assertEqual([], autonomous.validate(value, autonomous.packet(self.pkg, self.ctx)))
        self.assertEqual([], cr.validate_proposals(self.ctx["analysis"], value["counterexamples"]))

    def test_frozen_signatures_without_diagnostics_cannot_complete_functional_search(self):
        self.ctx.update({"analysis": None, "profile": PROFILE, "statements": STATEMENTS, "phase": "prove"})
        value = response([{"obligation_id": "O1", "inputs": [INPUT]}])
        result, calls = self.run_critic([value, value])
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertIn("kernel-replayed analysis", calls[1]["protocol_errors"][0])
        self.assertTrue(any("frozen signatures" in f for f in result["feedback"]))

    def test_trace_limitation_does_not_change_model_execution(self):
        profile = dsl.Profile.from_json(PROFILE)
        body = {"tag": "field", "sort": "Parcel", "field": "amount", "value": VAR}
        calls = []
        evaluator = cr._evaluator(profile, {"shift": body}, calls)
        with patch.object(cr, "_wire_bound", side_effect=ValueError("fixture trace limit")):
            actual = evaluator.symbols["shift"]([dsl.record_v("Parcel", [-2])])
        self.assertEqual(-2, actual)
        self.assertEqual([{"symbol": "shift", "completed": True, "payload_omitted": "bounded trace limit"}], calls)

    def test_helper_trace_saturation_preserves_actual_outer_endpoint(self):
        profile_json = {"profile_id": "trace_saturation", "dsl": dsl.ENCODING_V2, "symbols": {
            **{f"f{i}": {"lean_decl": f"Trace.f{i}", "args": ["Int"], "result": "Int"} for i in range(5)},
            "main": {"lean_decl": "Trace.main", "args": [{"list": "Int"}], "result": "Int"}}}
        bodies = {"f0": VAR}
        for i in range(1, 5):
            sub = {"tag": "call", "symbol": f"f{i-1}", "args": [VAR]}
            bodies[f"f{i}"] = {"tag": "int_add", "left": sub, "right": sub}
        bodies["main"] = {"tag": "list_sum", "value": {"tag": "list_map", "value": VAR,
            "function": {"sort": "Int", "body": {"tag": "call", "symbol": "f4", "args": [VAR]}}}}
        calls = []
        evaluator = cr._evaluator(dsl.Profile.from_json(profile_json), bodies, calls)
        self.assertEqual(4096, evaluator.symbols["main"]([(1,) * 256]))
        self.assertLessEqual(len(calls), cr.MAX_VALUE_NODES)
        self.assertEqual("main", calls[-1]["symbol"])
        self.assertTrue(any(c.get("preceding_trace_truncated") for c in calls))


if __name__ == "__main__":
    unittest.main()
