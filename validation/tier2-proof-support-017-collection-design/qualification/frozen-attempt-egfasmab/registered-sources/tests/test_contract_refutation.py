"""Actual Lean counterexample receipts; authored fixtures, never model/benchmark outputs."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, contract, contract_refutation as cr, dsl, leanbridge, policy
from verislop.exprjson import app, const
from verislop.package import Package


SOURCE = b'''import Std
namespace RefFixture
structure Payload where
  items : List String
  leading : String
def compose (i : Payload) : List String := i.items.map (fun s => i.leading ++ s)
theorem wrong (i : Payload) : compose i = i.items := by sorry
theorem right (i : Payload) : compose i = i.items.map (fun s => i.leading ++ s) := by rfl
theorem guarded (i : Payload) (h : i.leading = "") : compose i = i.items := by sorry
theorem unbounded (n : Nat) : n <= 2 := by sorry
theorem nested (i : Payload) : forall n : Nat, n = n := by sorry
structure AContainer where
  payload : Payload
def pack (i : Payload) : AContainer := {payload := i}
theorem packright (i : Payload) : pack i = {payload := i} := by rfl
theorem unsupported (f : Nat -> Nat) : f 0 = f 0 := by rfl
def branch (n : Nat) : Nat := match n with | 0 => 1 | k + 1 => k + 3
theorem wrongbranch (n : Nat) : branch n = n := by sorry
end RefFixture
'''


def records():
    result = []
    for oid, kind, role in [("D1", "entity", "declaration"), ("O1", "postcondition", "guarantee")]:
        result.append({"id": oid, "revision": 1, "kind": kind, "role": role, "statement": "Authored fixture",
            "required": True, "source_refs": [], "scope": ["fixture"], "dependencies": [],
            "acceptance_criteria": [], "origin": "interpreted", "blocked_by": []})
    return result


class ContractRefutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-refutation-test-")
        cls.directory = Path(cls.tmp.name)
        cls.tc = leanbridge.resolve_toolchain()
        cls.pol = policy.get("strict")
        cls.records = records()
        cls.fixtures = {}
        for name in ["wrong", "right", "guarded", "unbounded", "nested", "packright", "unsupported", "wrongbranch"]:
            form = {"schema_version": "0.1", "artifact_kind": "formalization_candidate", "profile_id": "refutation.v0_2",
                "lean_toolchain": cls.tc.pin, "lean_file": "Contract.lean", "internal_obligations": [],
                "bindings": [{"obligation": "D1", "declarations": ["RefFixture.Payload", "RefFixture.compose"]},
                             {"obligation": "O1", "theorem": "RefFixture." + name}]}
            base, _, problems = contract.compose_challenge(SOURCE, contract.registry_lean(cls.records, contract.binding_names(form)))
            if problems:
                raise AssertionError(problems)
            comp = leanbridge.compile_module(cls.tc, base, cls.directory / ("fixture-" + name))
            if not comp.ok:
                raise AssertionError(comp.errors)
            exp = leanbridge.run_kernel_tool(cls.tc, comp.olean, {"export": True, "axioms": True})
            env = contract.Env.from_export(exp, cls.pol, "fixture")
            if env.diagnostics:
                raise AssertionError(env.diagnostics)
            analysis = contract.analyze(env, cls.records, form, cls.pol, cls.tc.pin, "fixture")
            if analysis.diagnostics:
                raise AssertionError(analysis.diagnostics)
            cls.fixtures[name] = form, analysis, base, env

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_check(self, name, proposals=None, source=SOURCE, analysis=None):
        form, original, _, _ = self.fixtures[name]
        pkg = Package(self.directory / self.id().split(".")[-1])
        pkg.ensure()
        return cr.check(pkg, source, form, self.records, original if analysis is None else analysis, proposals=proposals)

    def test_sort_cartesian_scan_refutes_false_prefix_composition_with_clean_kernel_root(self):
        result = self.run_check("wrong")
        self.assertEqual("REFUTED", result["status"], result["diagnostics"])
        receipt = result["receipts"][0]
        self.assertEqual("guarantee_refutation", receipt["kind"])
        self.assertEqual("bounded_sort_scan", receipt["origin"])
        self.assertEqual(0, receipt["refutation_sorry_dependencies"])
        self.assertGreater(receipt["candidate_sorry_warning_count"], 0)
        self.assertNotIn("sorryAx", receipt["axioms"])
        self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, receipt["kernel_defeq"])
        self.assertTrue(receipt["kernel_proof_hash"].startswith("sha256:"))
        pkg = Package(self.directory / self.id().split(".")[-1])
        for artifact in receipt["artifacts"].values():
            self.assertEqual(artifact["sha256"], canonical.digest_file(pkg.root / artifact["path"]))
        self.assertNotIn("verified", result)

    def test_concrete_critic_wire_inputs_are_bound_to_original_candidate(self):
        inp = {"dict": {"items": {"list": [{"str": "x"}]}, "leading": {"str": "p"}}}
        result = self.run_check("wrong", [{"obligation_id": "O1", "inputs": [inp]}])
        self.assertEqual("REFUTED", result["status"], result)
        receipt = result["receipts"][0]
        self.assertEqual([inp], receipt["inputs"])
        self.assertEqual("critic_proposal", receipt["origin"])
        self.assertEqual(canonical.digest(SOURCE), receipt["binding"]["candidate_source_hash"])

    def test_correct_guarantee_and_guarded_implication_never_gain_proved_from_sampling(self):
        for name in ["right", "guarded"]:
            with self.subTest(name=name):
                result = self.run_check(name)
                self.assertEqual("UNKNOWN", result["status"])
                self.assertEqual([], result["receipts"], result)
                self.assertEqual(0, result["bounded_scan"]["proof_attempts"])
                self.assertTrue(result["bounded_scan"]["no_counterexample_is_not_a_proof"])

    def test_actual_model_calls_are_distinct_from_vacuous_and_witness_probes(self):
        inp = {"dict": {"items": {"list": [{"str": "x"}]}, "leading": {"str": "p"}}}
        probe = [{"obligation_id": "O1", "inputs": [inp]}]
        real = self.run_check("right", probe)
        self.assertEqual("UNKNOWN", real["status"])
        observation = real["execution_observations"][0]
        self.assertEqual("compose", observation["calls"][0]["symbol"])
        self.assertEqual([inp], observation["calls"][0]["inputs"])
        self.assertEqual({"list": [{"str": "px"}]}, observation["calls"][0]["actual"])
        self.assertFalse(observation["milestone_authority"])
        vacuous = self.run_check("guarded", probe)
        self.assertEqual([], vacuous["execution_observations"][0]["calls"])
        self.assertEqual([], vacuous["receipts"])

    def test_unbounded_unsearched_and_nested_quantifier_remain_unknown(self):
        for name in ["unbounded", "nested", "unsupported"]:
            with self.subTest(name=name):
                result = self.run_check(name)
                self.assertEqual("UNKNOWN", result["status"])
                self.assertEqual([], result["receipts"])

    def test_critic_can_refute_beyond_default_nat_scan(self):
        result = self.run_check("unbounded", [{"obligation_id": "O1", "inputs": [{"int": "3"}]}])
        self.assertEqual("REFUTED", result["status"], result)

    def test_critic_case_can_use_kernel_reduction_when_host_body_is_unsupported(self):
        result = self.run_check("wrongbranch", [{"obligation_id": "O1", "inputs": [{"int": "0"}]}])
        self.assertEqual("REFUTED", result["status"], result)
        self.assertEqual("critic_proposal", result["receipts"][0]["origin"])

    def test_malformed_wires_extra_fields_and_wrong_sort_are_not_evidence(self):
        malformed = [
            {"obligation_id": "O1", "inputs": [{"int": "01"}]},
            {"obligation_id": "O1", "inputs": [{"bool": True}]},
            {"obligation_id": "O1", "inputs": [{"int": "3", "extra": 0}]},
            {"obligation_id": "O1", "inputs": [{"int": "3"}], "trust_me": True},
            {"obligation_id": "D1", "inputs": [{"int": "3"}]},
        ]
        result = self.run_check("unbounded", malformed)
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual([], result["receipts"])
        self.assertEqual(len(malformed), len([d for d in result["diagnostics"] if d.get("origin") == "critic_proposal"]))
        self.assertTrue(all(d.get("kind") == "INVALID_PROPOSAL" for d in result["diagnostics"] if d.get("origin") == "critic_proposal"))

    def test_wire_signature_validation_has_no_kernel_or_model_calls(self):
        analysis = self.fixtures["unbounded"][1]
        with patch.object(leanbridge, "compile_module", side_effect=AssertionError("must not compile")), patch.object(leanbridge, "run_kernel_tool", side_effect=AssertionError("must not replay")):
            self.assertEqual([], cr.validate_proposals(analysis, [{"obligation_id": "O1", "inputs": [{"int": "3"}]}]))
            self.assertEqual(1, len(cr.validate_proposals(analysis, [{"obligation_id": "O1", "inputs": [{"bool": True}]}])))
            self.assertEqual(1, len(cr.validate_proposals(analysis, [{"obligation_id": "O1", "inputs": [{"int": "03"}]}])))

    def test_reference_expected_output_is_an_untrusted_annotation(self):
        inp = {"dict": {"items": {"list": [{"str": "x"}]}, "leading": {"str": "p"}}}
        proposal = {"obligation_id": "O1", "exact_clause_id": "authored-clause", "entry_symbol": "compose",
                    "inputs": [inp], "expected": {"list": [{"str": "x"}]}}
        result = self.run_check("right", [proposal])
        self.assertEqual("SEMANTIC_MISMATCH", result["status"], result)
        receipt = result["receipts"][0]
        self.assertEqual({"list": [{"str": "px"}]}, receipt["actual"])
        self.assertFalse(receipt["natural_language_clause_verified"])
        self.assertFalse(receipt["guarantee_refuted"])
        self.assertEqual("untrusted_critic_annotation", receipt["expectation_authority"])
        self.assertNotIn("PROVED", canonical.dumps(result).decode())

    def test_reference_match_proves_only_exact_candidate_output(self):
        inp = {"dict": {"items": {"list": [{"str": "x"}]}, "leading": {"str": "p"}}}
        result = self.run_check("right", [{"obligation_id": "O1", "exact_clause_id": "authored-clause", "entry_symbol": "RefFixture.compose",
            "inputs": [inp], "expected": {"list": [{"str": "px"}]}}])
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual("REFERENCE_MATCH", result["receipts"][0]["status"])

    def test_nested_record_output_equality_derives_inner_carriers_first(self):
        inp = {"dict": {"items": {"list": [{"str": "x"}]}, "leading": {"str": "p"}}}
        result = self.run_check("packright", [{"obligation_id": "O1", "exact_clause_id": "authored-clause", "entry_symbol": "pack",
            "inputs": [inp], "expected": {"dict": {"payload": inp}}}])
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual(1, len(result["receipts"]), result)
        self.assertEqual("REFERENCE_MATCH", result["receipts"][0]["status"])

    def test_changed_source_and_forged_analysis_fail_binding_before_refutation(self):
        changed = SOURCE.replace(b"i.leading ++ s", b's ++ i.leading')
        result = self.run_check("wrong", source=changed)
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual([], result["receipts"])
        self.assertIn("do not match", str(result["diagnostics"]))
        fake = copy.deepcopy(self.fixtures["wrong"][1])
        fake.statements["O1"]["formula_package"]["formula"] = {"tag": "false"}
        result = self.run_check("wrong", analysis=fake)
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual([], result["receipts"])

    def test_wrong_closed_proof_cannot_be_compiled_into_a_receipt(self):
        form, analysis, base, env = self.fixtures["right"]
        pkg = Package(self.directory / self.id().split(".")[-1]); pkg.ensure()
        profile = dsl.Profile.from_json(analysis.profile)
        expr = app(const("Not"), const("True"))
        result = cr._proof(pkg, base, expr, {"test": "false proposition"}, profile, self.tc, self.pol, env)
        self.assertFalse(result["ok"])

    def test_kernel_mismatch_or_sorry_closure_cannot_become_refuted(self):
        original = leanbridge.run_kernel_tool
        for kind in ["type_mismatch", "sorry"]:
            def tampered(*args, **kwargs):
                result = original(*args, **kwargs)
                request = args[2]
                if request.get("defeq", [{}])[0].get("id") == "closed_check":
                    result = copy.deepcopy(result)
                    if kind == "type_mismatch":
                        result["defeq"][0]["result"]["defeq"] = False
                    else:
                        for c in result["constants"]:
                            if c.get("name", [])[-1:] == ["closed_check"]:
                                c["axioms"] = [["sorryAx"]]
                return result
            with self.subTest(kind=kind), patch.object(cr, "MAX_PROOF_ATTEMPTS", 1), patch.object(leanbridge, "run_kernel_tool", side_effect=tampered):
                result = self.run_check("wrong")
                self.assertEqual("UNKNOWN", result["status"], result)
                self.assertEqual([], result["receipts"])


if __name__ == "__main__":
    unittest.main()
