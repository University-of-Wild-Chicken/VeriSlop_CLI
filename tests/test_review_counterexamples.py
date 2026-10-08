"""Closed proposals and independent exact target/coverage/evidence replay."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir
from verislop import canonical, contract, dsl, fsutil, review_counterexamples as rc, segment
from verislop.package import Package

ZERO = "sha256:" + "0" * 64


class CounterexampleReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(self.tmp.path)
        self.pkg.ensure("counterexample-units")
        self.registry = patch.dict(rc.VERIFIERS, {rc.VERIFIER: {}})
        self.registry.start()
        self.addCleanup(self.registry.stop)
        self.identity = patch.object(rc, "verifier_hash", return_value=ZERO)
        self.identity.start()
        self.addCleanup(self.identity.stop)
        prompt = b"Do A. Do B."
        fsutil.atomic_write(self.pkg.path("prompt"), prompt)
        fsutil.write_json(self.pkg.path("draft"), {})
        self.spans = segment.segments(prompt)
        self.ledger = {"request": {"document_hash": canonical.digest(prompt), "byte_length": len(prompt)},
                       "clauses": [{"start_byte": a, "end_byte": b} for a, b in self.spans]}
        fsutil.write_json(self.pkg.path("interpretation"), self.ledger)

    def probe(self, kind="target_case", **kwargs):
        return {"kind": kind, **kwargs}

    def target(self, source="def f(n): return n\n", body=None, helpers=None):
        fsutil.atomic_write(self.pkg.path("implementation") / "target.py", source.encode())
        profile = {"profile_id": "review-test", "symbols": {"f": {"lean_decl": "Model.f", "args": ["Nat"], "result": "Nat"}},
                   "enums": {}, "predicates": {}}
        fsutil.write_json(contract.challenge_dir(self.pkg) / "profile.json", profile)
        formula = {"tag": "forall", "sort": "Nat", "body": body or {
            "tag": "implies", "left": {"tag": "le", "left": {"tag": "var", "index": 0}, "right": {"tag": "nat", "value": "5"}},
            "right": {"tag": "eq", "left": {"tag": "call", "symbol": "f", "args": [{"tag": "var", "index": 0}]},
                      "right": {"tag": "var", "index": 0}}}}
        package = dsl.make_package(formula, profile["profile_id"])
        payload = canonical.dumps(package)
        digest = canonical.digest(payload)
        fsutil.atomic_write(self.pkg.path("accepted") / "expressions" / (digest[7:] + ".json"), payload)
        ir = {"acceptance_certificate_ref": "accepted/acceptance.json", "obligations": {"O1": {"id": "O1", "revision": 1, "role": "guarantee", "kind": "postcondition", "required": True,
             "formal": {"representation": "contract_dsl", "formula_ref": "artifact:formula@" + digest, "statement_hash": ZERO}}}}
        fsutil.write_json(self.pkg.path("accepted_ir"), ir)
        fsutil.write_json(self.pkg.path("accepted") / "acceptance.json", {})
        ir_hash = canonical.digest_json(ir)
        statements = {"statements": {"O1": {"semantic_closure": ["Model.f"]}}, "declaration_hashes": {"Model.f": ZERO}}
        fsutil.write_json(contract.challenge_dir(self.pkg) / "statements.json", statements)
        proposal = {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
                    "serialization_profile": "python-v0_1", "helpers": helpers or [], "bindings": [{"binding_id": "B-f", "symbol": "f",
                    "object": {"file": "target.py", "qualname": "f"}, "obligations": ["O1"]}]}
        fsutil.write_json(self.pkg.path("bridges") / "bindings.json", proposal)
        claim = {"claim_id": "LINKED:O1@1", "obligation": "O1", "milestone": "LINKED", "applicable": True,
                 "required": True, "verifier": "verislop.python-linker"}
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {
            "schema_version": "0.1", "artifact_kind": "implementation_claims", "claims": [claim], "bound_to": {"accepted_ir": ir_hash},
            "parameters": {"tier": 0, "target": "python", "endpoint": "test_campaign"}})
        inventory = rc.pt.inventory(self.pkg.path("implementation"))
        obj = inventory.find("target.py", "f")
        fsutil.write_json(self.pkg.path("bridges") / "link.json", {
            "schema_version": "0.1", "artifact_kind": "link_record", "accepted_ir": ir_hash,
            "implementation_root": self.pkg.implementation_root(), "serialization_profile": rc.pt.PROFILE_DOC,
            "correspondence": "structural identity and coverage only; semantic correspondence is not established at this tier",
            "bindings": [{"binding_id": "B-f", "symbol": "f", "obligations": ["O1"], "serialization_profile": "python-v0_1",
                "formal_declaration": {"lean_decl": "Model.f", "decl_hash": ZERO, "args": ["Nat"], "result": "Nat"},
                "implementation_object": {"file": "target.py", "qualname": "f", "source_hash": obj["source_hash"],
                    "file_hash": inventory.files["target.py"], "lineno": obj["lineno"]}}]})
        self.pkg.evidence.record(claim_id=claim["claim_id"], verifier_id="verislop.python-linker", status="PASS",
            scope=["current structural association"], input_root=self.pkg.link_root(), result={"milestone_outcome": "PASS"}, invocation=["unit"])
        # The fixture isolates invocation/classification. Workflow integration tests use real
        # accepted contracts and the real verified_ir boundary independently.
        return patch.object(rc, "verified_ir", return_value=(ir, canonical.digest_json(ir), {}, [])), \
               patch.object(rc.contract, "frozen_json", return_value=profile)

    def replay_target(self, assignment, source="def f(n): return n\n", body=None):
        accepted, profile = self.target(source, body)
        with accepted, profile:
            return rc.replay(self.pkg, "implementation", self.probe(obligation_id="O1", assignment=assignment))

    def test_closed_proposals_reject_commands_results_unknown_fields_and_noncanonical_values(self):
        good = self.probe(obligation_id="O1", assignment=[{"int": "0"}])
        self.assertEqual(rc.validate_proposal(good), [])
        for mutation in ({**good, "command": "echo forge"}, {**good, "status": "CONFIRMED"},
                         {**good, "assignment": [{"int": "00"}]},
                         {**good, "assignment": [{"bool": 1}]}, {**good, "assignment": [{"none": True}]},
                         {**good, "assignment": [{"int": "0", "extra": True}]}):
            with self.subTest(proposal=mutation):
                self.assertTrue(rc.validate_proposal(mutation))
                with patch.object(rc, "_target", side_effect=AssertionError("invalid proposal reached execution")):
                    self.assertEqual(rc.replay(self.pkg, "implementation", mutation)["status"], "UNSUPPORTED")

    def test_signed_wire_syntax_is_valid_but_negative_nat_assignment_is_unsupported(self):
        signed = self.probe(obligation_id="O1", assignment=[{"int": "-1"}])
        self.assertEqual([], rc.validate_proposal(signed))
        self.assertEqual("UNSUPPORTED", self.replay_target(signed["assignment"])["status"])

    def test_real_target_observation_confirms_false_predicate_and_keeps_exact_bindings(self):
        result = self.replay_target([{"int": "2"}], "def f(n): return n + 1\n")
        self.assertEqual(result["status"], "CONFIRMED", result)
        self.assertTrue(result["observed"]["guard"])
        self.assertFalse(result["observed"]["predicate"])
        self.assertEqual(result["observed"]["calls"][0]["response"]["value"], {"int": "3"})
        self.assertEqual(result["claim"]["revision"], 1)
        self.assertIn("implementation/target.py", result["input_bindings"])
        self.assertIn("contract/challenge/profile.json", result["input_bindings"])
        self.assertEqual(result["checker"], {"id": rc.VERIFIER, "sha256": ZERO})
        self.assertEqual(result["proposal_hash"], canonical.digest_json(result["proposal"]))

    def test_correct_case_is_not_reproduced_and_outside_guard_cannot_refute_claim(self):
        self.assertEqual(self.replay_target([{"int": "2"}])["status"], "NOT_REPRODUCED")
        result = self.replay_target([{"int": "6"}], "def f(n): return n + 1\n")
        self.assertEqual(result["status"], "NOT_REPRODUCED")
        self.assertFalse(result["observed"]["guard"])
        self.assertEqual(result["observed"]["calls"], [])

    def test_wrong_sort_or_arity_is_unsupported(self):
        for assignment in ([], [{"bool": True}], [{"int": "0"}, {"int": "1"}]):
            with self.subTest(assignment=assignment):
                self.assertEqual(self.replay_target(assignment)["status"], "UNSUPPORTED")

    def test_unbounded_residual_rejected_before_target_or_legacy_exactness_inference(self):
        body = {"tag": "exists", "sort": "Bool", "body": {"tag": "not", "body": {
            "tag": "forall", "sort": "Nat", "body": {"tag": "le", "left": {"tag": "var", "index": 0},
                                                         "right": {"tag": "nat", "value": "100"}}}}}
        accepted, profile = self.target(body=body)
        with accepted, profile, patch.object(rc, "_BoundedHarness", side_effect=AssertionError("sampled residual executed")):
            result = rc.replay(self.pkg, "implementation", self.probe(obligation_id="O1", assignment=[{"int": "0"}]))
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertIn("unbounded residual", result["diagnostics"][0])

    def test_target_profile_failure_is_not_fabricated_logical_false(self):
        result = self.replay_target([{"int": "0"}], "def f(n): return True\n")
        self.assertEqual(result["status"], "CONFIRMED", result)
        self.assertEqual(result["claim"]["result_predicate"], "total-target-profile/0.1")
        self.assertIsNone(result["observed"]["predicate"])
        self.assertFalse(result["observed"]["target_profile_valid"])

    def test_guard_target_fault_leaves_assumptions_unresolved(self):
        body = {"tag": "implies", "left": {"tag": "eq", "left": {"tag": "call", "symbol": "f", "args": [{"tag": "var", "index": 0}]},
                                             "right": {"tag": "nat", "value": "0"}}, "right": {"tag": "false"}}
        result = self.replay_target([{"int": "0"}], "def f(n): raise ValueError('observed')\n", body)
        self.assertEqual(result["status"], "UNSUPPORTED", result)
        self.assertIsNone(result["observed"]["guard"])
        self.assertIsNone(result["observed"]["predicate"])
        self.assertTrue(result["observed"]["calls"])

    def test_timeout_is_infrastructure_not_counterexample(self):
        accepted, profile = self.target()
        with accepted, profile, patch.object(rc, "_BoundedHarness", side_effect=rc.pt.HarnessError("timeout", "observed load timeout")):
            result = rc.replay(self.pkg, "release", self.probe(obligation_id="O1", assignment=[{"int": "0"}]))
        self.assertEqual(result["status"], "INFRASTRUCTURE_FAILURE")

    def test_exact_uncovered_request_span_confirms_structural_omission_only(self):
        a, b = self.spans[-1]
        proposal = self.probe("missing_requirement", start_byte=a, end_byte=b, quoted="Do B.")
        self.assertEqual(rc.replay(self.pkg, "interpretation", proposal)["status"], "NOT_REPRODUCED")
        self.ledger["clauses"].pop()
        fsutil.write_json(self.pkg.path("interpretation"), self.ledger)
        result = rc.replay(self.pkg, "formal_contract", proposal)
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["claim"]["result_predicate"], "interpretation-coverage/0.1")
        self.assertFalse(result["observed"]["span_disposition_present"])
        self.assertIn("not semantic", result["observed"]["limitation"])
        self.assertEqual(rc.replay(self.pkg, "release", proposal)["status"], "UNSUPPORTED")
        self.assertEqual(rc.replay(self.pkg, "interpretation", {**proposal, "quoted": "Do something else."})["status"], "UNSUPPORTED")

    def test_current_registered_mechanical_pass_and_failure_are_replayed(self):
        proposal = self.probe("mechanical_failure", claim_id="INTERPRETATION:request")
        self.assertEqual(rc.replay(self.pkg, "interpretation", proposal)["status"], "UNSUPPORTED")
        root = self.pkg.interpretation_root()
        self.pkg.evidence.record(claim_id=proposal["claim_id"], verifier_id="verislop.interpretation-recorder", status="PASS",
            scope=["request coverage"], input_root=root, result={"milestone_outcome": "PASS", "coverage": {"uncovered_segments": []}}, invocation=["unit"])
        result = rc.replay(self.pkg, "interpretation", proposal)
        self.assertEqual(result["status"], "NOT_REPRODUCED", result)
        self.pkg.evidence.record(claim_id=proposal["claim_id"], verifier_id="verislop.interpretation-recorder", status="BLOCK",
            scope=["request coverage"], input_root=root, result={"milestone_outcome": "FAIL", "codes": ["UNCOVERED_SOURCE_CLAUSE"]}, invocation=["unit"])
        self.assertEqual(rc.replay(self.pkg, "interpretation", proposal)["status"], "CONFIRMED")

    def test_checkpoint_roots_and_claim_inputs_ignore_future_stage_growth(self):
        fsutil.write_json(contract.challenge_dir(self.pkg) / "challenge.json", {})
        fsutil.write_json(contract.challenge_dir(self.pkg) / "profile.json", {})
        fsutil.write_json(self.pkg.path("claims"), {"claims": []})
        proposal = self.probe("mechanical_failure", claim_id="INTERPRETATION:request")
        self.pkg.evidence.record(claim_id=proposal["claim_id"], verifier_id="verislop.interpretation-recorder", status="PASS",
            scope=["request coverage"], input_root=self.pkg.interpretation_root(),
            result={"milestone_outcome": "PASS", "coverage": {"uncovered_segments": []}}, invocation=["unit"])
        formal_roots = rc.bound_roots(self.pkg, "formal_contract")
        formal = rc.replay(self.pkg, "formal_contract", proposal)
        interpreted = rc.replay(self.pkg, "interpretation", proposal)
        self.assertEqual(formal["status"], "NOT_REPRODUCED", formal)
        self.assertEqual(set(formal_roots), {"interpretation_root", "contract_input_root"})
        self.assertNotIn("claims.json", interpreted["input_bindings"])
        fsutil.atomic_write(self.pkg.path("implementation") / "target.py", b"def f(n): return n\n")
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {
            "claims": [], "parameters": {"target": "python"}})
        self.assertEqual(rc.bound_roots(self.pkg, "formal_contract"), formal_roots)
        self.assertEqual(rc.replay(self.pkg, "formal_contract", proposal)["input_bindings"], formal["input_bindings"])
        self.assertEqual(rc.replay(self.pkg, "interpretation", proposal)["input_bindings"], interpreted["input_bindings"])
        self.assertNotIn("closure/implementation-claims.json", formal["input_bindings"])
        self.assertEqual(set(rc.bound_roots(self.pkg, "implementation")),
            {"interpretation_root", "contract_input_root", "implementation_root", "link_root"})
        self.assertEqual(set(rc.bound_roots(self.pkg, "release")), set(self.pkg.roots()))
        fsutil.write_json(contract.challenge_dir(self.pkg) / "profile.json", {"changed": True})
        self.assertNotEqual(rc.bound_roots(self.pkg, "formal_contract"), formal_roots)

    def test_unknown_checkpoint_or_unregistered_checker_cannot_confirm(self):
        proposal = self.probe("mechanical_failure", claim_id="INTERPRETATION:request")
        self.assertEqual(rc.replay(self.pkg, "other", proposal)["status"], "UNSUPPORTED")
        with patch.dict(rc.VERIFIERS, {}, clear=True):
            self.assertEqual(rc.replay(self.pkg, "interpretation", proposal)["status"], "UNSUPPORTED")
        for timeout in (0, float("inf"), -1, True, 31):
            self.assertEqual(rc.replay(self.pkg, "interpretation", proposal, timeout_seconds=timeout)["status"], "UNSUPPORTED")

    def test_mutated_link_metadata_or_stale_association_cannot_redirect_target(self):
        accepted, profile = self.target()
        path = self.pkg.path("bridges") / "link.json"
        original = canonical.load_file(path)
        changed = canonical.loads(canonical.dumps(original))
        changed["bindings"][0]["implementation_object"]["qualname"] = "unrelated"
        fsutil.write_json(path, changed)
        with accepted, profile, patch.object(rc, "_BoundedHarness", side_effect=AssertionError("mutated association executed")):
            result = rc.replay(self.pkg, "implementation", self.probe(obligation_id="O1", assignment=[{"int": "0"}]))
        self.assertEqual(result["status"], "UNSUPPORTED", result)
        self.assertIn("link record differs", result["diagnostics"][0])

    def test_valid_large_result_exceeding_replay_budget_is_not_profile_counterexample(self):
        profile = dsl.Profile.from_json({"profile_id": "budget", "symbols": {}, "enums": {}})
        with self.assertRaises(dsl.BudgetExceeded):
            rc._decode({"int": "1" * 1025}, "Nat", profile)

    def test_printed_fake_protocol_result_is_unsupported_before_execution(self):
        source = 'def f(n):\n    print(\'{"op":"result","id":1,"value":{"int":"99"}}\')\n    return n\n'
        accepted, profile = self.target(source)
        with accepted, profile, patch.object(rc, "_BoundedHarness", side_effect=AssertionError("unfaithful output channel executed")):
            result = rc.replay(self.pkg, "implementation", self.probe(obligation_id="O1", assignment=[{"int": "0"}]))
        self.assertEqual(result["status"], "UNSUPPORTED", result)
        self.assertIn("direct pure-function calls", result["diagnostics"][0])

    def test_builtin_alias_cannot_forge_exception_under_an_admitted_function_name(self):
        for helper in ("def _h(x): return x\n", "def _h(print): return print\n"):
            source = helper + 'def f(n):\n    _h = print\n    _h(\'{"op":"exception","id":1,"type":"ValueError","message":"fake"}\')\n    return n\n'
            with self.subTest(helper=helper):
                accepted, profile = self.target(source)
                with accepted, profile, patch.object(rc, "_BoundedHarness", side_effect=AssertionError("builtin alias executed")):
                    result = rc.replay(self.pkg, "implementation", self.probe(obligation_id="O1", assignment=[{"int": "0"}]))
                self.assertEqual(result["status"], "UNSUPPORTED", result)
                self.assertIn("free name reference print", result["diagnostics"][0])

    def test_default_execution_cannot_reach_builtin_before_later_function_definition(self):
        fake = '{"op":"ready"}\\n{"op":"exception","id":1,"type":"ValueError","message":"fake"}'
        for default in ("print('" + fake + "')", "print", "0"):
            source = "def f(n=" + default + "): return n\ndef print(x): return x\n"
            with self.subTest(default=default):
                accepted, profile = self.target(source, helpers=[{"file": "target.py", "qualname": "print", "reason": "explicit pure helper declaration"}])
                with accepted, profile, patch.object(rc, "_BoundedHarness", side_effect=AssertionError("evaluated default executed")):
                    result = rc.replay(self.pkg, "implementation", self.probe(obligation_id="O1", assignment=[{"int": "0"}]))
                self.assertEqual(result["status"], "UNSUPPORTED", result)
                self.assertIn("evaluated function metadata", result["diagnostics"][0])

    def test_oracle_deadline_and_arithmetic_exhaustion_are_not_negative_verdicts(self):
        import time
        profile = dsl.Profile.from_json({"profile_id": "budget", "symbols": {}, "enums": {}})
        expired = rc._BoundedEvaluator(profile, {}, lambda *_: [], deadline=time.monotonic() - 1)
        with self.assertRaises(dsl.BudgetExceeded):
            expired.formula({"tag": "true"}, [])
        bounded = rc._BoundedEvaluator(profile, {}, lambda *_: [], deadline=time.monotonic() + 5)
        value = {"tag": "var", "index": 0}
        with self.assertRaises(dsl.BudgetExceeded):
            bounded.term({"tag": "mul", "left": value, "right": value}, [2 ** 3000])


if __name__ == "__main__":
    unittest.main()
