"""Generic authored native-facet fixtures; these are not live corpus results."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verislop import accept, autonomous, canonical, contract, contract_refutation, dsl, export, formal_frontend, formalize, leanbridge, native_contract, policy, prove, reify, schemas
from verislop.exprjson import app, const, parse_name
from tests import test_formal_frontend_workflow as frontend_fixture
from tests import test_contract_refutation as refutation_fixture
from verislop.package import Package


def proposal(*, mixed=True, two=False):
    obj = copy.deepcopy(frontend_fixture.AST)
    obj["native_requirements"] = {"Boundary": {"symbol": "bump", "requirements": [
        {"tag": "entry", "file": "worker.py", "qualname": "bump", "arity": 1},
        *({"tag": t} for t in ("pure_json", "standard_runtime_only", "no_external_io", "input_preserved", "deterministic", "no_floating_point"))]}}
    if not mixed:
        obj["theorems"]["result"] = {}
    obj["theorems"]["result"]["native"] = ["Boundary"]
    if two:
        obj["native_requirements"]["OtherBoundary"] = {"symbol": "bump", "requirements": [{"tag": "no_external_io"}]}
        obj["theorems"]["result"]["native"].append("OtherBoundary")
    return obj


FROZEN = [{"id": "D1", "role": "declaration"}, {"id": "O1", "role": "guarantee"}]


class NativeAuthoringTests(unittest.TestCase):
    def test_closed_schema_and_same_original_binding_with_real_proof_holes(self):
        obj = proposal(two=True)
        self.assertEqual([], schemas.validate("formalizer-ast", obj))
        compiled = formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "fixture")
        self.assertEqual([], schemas.validate("formalization-candidate", compiled.formalization))
        b = compiled.formalization["bindings"][1]
        self.assertEqual("O1", b["obligation"])
        self.assertEqual(["VeriSlopAST.Boundary", "VeriSlopAST.OtherBoundary"], b["native_requirements"])
        self.assertEqual("VeriSlopAST._vs_value_result", b["value_projection"])
        self.assertIn(b":= by sorry", compiled.source)
        self.assertIn(b"by exact _root_.VeriSlopAST.", compiled.source)
        self.assertTrue(formal_frontend.reconstruct_origin(canonical.dumps(obj), FROZEN, compiled.source,
                                                         compiled.formalization, compiled.receipt))

    def test_native_parameters_cannot_contain_observations_flags_or_unsupported_policies(self):
        for bad in ({"tag": "no_external_io", "status": "PASS"}, {"tag": "no_external_io", "observed": True},
                    {"tag": "time_bound", "seconds": 1}, {"tag": "pure_json", "policy": "unchecked"}):
            with self.subTest(bad=bad):
                obj = proposal()
                obj["native_requirements"]["Boundary"]["requirements"] = [bad]
                self.assertTrue(schemas.validate("formalizer-ast", obj))
                with self.assertRaises(formal_frontend.FrontendError):
                    formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "fixture")

    def test_layout_signature_duplicates_unknown_endpoints_and_orphan_facets_reject(self):
        modifications = [lambda o: o["native_requirements"]["Boundary"].update(symbol="missing"),
            lambda o: o["native_requirements"]["Boundary"]["requirements"][0].update(file="../worker.py"),
            lambda o: o["native_requirements"]["Boundary"]["requirements"][0].update(file="/worker.py"),
            lambda o: o["native_requirements"]["Boundary"]["requirements"][0].update(arity=2),
            lambda o: o["native_requirements"]["Boundary"]["requirements"].append({"tag": "no_external_io"}),
            lambda o: o["theorems"]["result"].update(native=["missing"]),
            lambda o: o["native_requirements"].update(Unused={"symbol": "bump", "requirements": [{"tag": "pure_json"}]})]
        for edit in modifications:
            obj = proposal()
            edit(obj)
            with self.subTest(proposal=obj), self.assertRaises(formal_frontend.FrontendError):
                formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "fixture")

    def test_old_proposals_remain_byte_identical_and_native_empty_rows_reject(self):
        obj = copy.deepcopy(frontend_fixture.AST)
        old = formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "fixture")
        obj["native_requirements"] = {}
        new = formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "fixture")
        self.assertEqual(old.source, new.source)
        self.assertEqual(old.formalization, new.formalization)
        for bad in ([], ["Boundary", "Boundary"]):
            obj = proposal()
            obj["theorems"]["result"]["native"] = bad
            with self.assertRaises(formal_frontend.FrontendError):
                formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "fixture")


class NativeKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.tc = leanbridge.resolve_toolchain()
        cls.c = formal_frontend.compile_response(canonical.dumps(proposal()), FROZEN, "fixture")
        # Authored generic regression proof; never provided to a live corpus agent.
        source = cls.c.source.replace(b":= by sorry", b":= by exact \xe2\x9f\xa8by intros; rfl, VeriSlop.Native.contract_sound _\xe2\x9f\xa9")
        build = leanbridge.compile_module(cls.tc, source, Path(cls.tmp.name))
        if not build.ok:
            raise AssertionError(build.errors)
        cls.olean = build.olean
        cls.kernel = leanbridge.run_kernel_tool(cls.tc, build.olean, {"export": True, "axioms": True,
            "defeq": formal_frontend.kernel_audit_requests(cls.c)})
        cls.env = contract.Env.from_export(cls.kernel, policy.get("strict"), "fixture")
        raw, _ = reify.derive_profile("fixture", cls.env.decls, cls.env.hashes, {"VeriSlopAST.result"})
        cls.profile = dsl.Profile.from_json(raw)

    def decode(self, *, expr=None, binding=None, decls=None, hashes=None):
        return native_contract.reify_contract(expr or self.env.decls["VeriSlopAST.result"]["type"], self.profile,
            decls or self.env.decls, hashes or self.env.hashes, pin=self.tc.pin, theorem="VeriSlopAST.result",
            binding=binding or self.c.formalization["bindings"][1])

    def test_transfer_inhabitation_and_exact_mixed_projection_cross_real_kernel(self):
        self.assertEqual([], self.env.diagnostics)
        self.assertTrue(all(row["result"].get("defeq") for row in self.kernel["defeq"]))
        for name in ("transfer_sound", "admission_inhabited", "contract_sound", "modelWitness"):
            self.assertNotIn(["sorryAx"], self.env.decls[native_contract.NS + "." + name].get("axioms", []))
        package, _, checks, roots = self.decode()
        self.assertEqual({"bump"}, native_contract.symbols(package))
        self.assertEqual("worker.py", package["native"][0]["requirements"][0]["file"])
        self.assertIn({"tag": "no_floating_point"}, package["native"][0]["requirements"])
        self.assertEqual(self.profile.symbols["bump"]["decl_hash"], package["native"][0]["decl_hash"])
        self.assertEqual("VeriSlopAST._vs_value_result", package["value_projection"]["lean_symbol"])
        self.assertIn("VeriSlopAST._vs_value_result", roots)
        checks += [{"id": "whole", "theorem": parse_name("VeriSlopAST.result"),
                    "expr": native_contract.denote_package(package, self.profile, self.env.decls)}]
        result = leanbridge.run_kernel_tool(self.tc, self.olean, {"defeq": checks})
        self.assertTrue(all(row["result"].get("defeq") for row in result["defeq"]))

    def test_requirement_data_comes_from_accepted_ast_not_mutated_candidate_json(self):
        self.c.proposal["native_requirements"]["Boundary"]["requirements"][0]["file"] = "forged.py"
        try:
            package, *_ = self.decode()
            self.assertEqual("worker.py", package["native"][0]["requirements"][0]["file"])
            self.assertNotIn("PASS", canonical.dumps(package).decode())
        finally:
            self.c.proposal["native_requirements"]["Boundary"]["requirements"][0]["file"] = "worker.py"

    def test_missing_changed_bindings_projection_and_model_reject(self):
        for edit in (lambda b: b.pop("native_requirements"),
                     lambda b: b.update(native_requirements=["VeriSlopAST.missing"]),
                     lambda b: b.pop("value_projection"),
                     lambda b: b.update(value_projection="VeriSlopAST.result")):
            b = copy.deepcopy(self.c.formalization["bindings"][1])
            edit(b)
            with self.subTest(binding=b), self.assertRaises(native_contract.NativeError):
                self.decode(binding=b)
        hashes = dict(self.env.hashes)
        hashes[native_contract.NS + ".checkBoundary"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(native_contract.NativeError, "normative library"):
            self.decode(hashes=hashes)

    def test_native_under_optional_connective_or_caller_assumption_is_not_admitted(self):
        original = self.env.decls["VeriSlopAST.result"]["type"]
        n = original["app"][2]
        for expr in (app(const("Or"), const("True"), n),
                     {"pi": {"name": ["h"], "bi": "default", "type": const("False"), "body": n}}):
            with self.subTest(expr=expr), self.assertRaises(native_contract.NativeError):
                self.decode(expr=expr)


class NativeReadinessTests(unittest.TestCase):
    def test_native_only_still_requires_real_target_and_mixed_keeps_existing_value_gates(self):
        rec = {"id": "R1", "kind": "resource_constraint", "role": "guarantee", "required": True,
               "dependencies": [], "blocked_by": []}
        req = {"target": "python", "tier": 0, "endpoint": "test_campaign", "require_state": "TESTED"}
        raw = {"profile_id": "fixture", "dsl": dsl.ENCODING_V2, "records": {}, "enums": {}, "predicates": {},
               "symbols": {"f": {"lean_decl": "f", "args": ["Int"], "result": "Int"}}}
        native = {"encoding": native_contract.ENCODING, "value": None, "native": [{"symbol": "f"}]}
        statement = {"representation": "contract_facets", "semantic_closure": {"f": "hash"}, "formula_package": native}
        analysis = contract.Analysis(raw, {"R1": statement}, [], [], [])
        self.assertEqual([], formalize.executable_readiness([rec], analysis, req))
        statement["semantic_closure"] = {}
        self.assertTrue(formalize.executable_readiness([rec], analysis, req)[0].details["missing_implementation_symbol"])
        statement["semantic_closure"] = {"f": "hash"}
        native["value"] = dsl.make_package({"tag": "eq", "left": {"tag": "int", "value": "0"},
                                          "right": {"tag": "int", "value": "0"}}, "fixture", encoding=dsl.ENCODING_V2)
        self.assertTrue(any(d.details.get("structurally_trivial_guarantee") for d in formalize.executable_readiness([rec], analysis, req)))

    def test_autonomous_mixed_requires_concrete_value_probe_native_only_does_not_fake_one(self):
        statement = {"role": "guarantee", "representation": "contract_facets", "formula_package": {
            "encoding": native_contract.ENCODING, "value": {"formula": {"tag": "true"}}, "native": []}}
        data = {"clauses": [], "diagnostics": [], "statements": {"O1": statement}}
        verdict = {"encoding": autonomous.VERSION, "verdict": "ACCEPT", "counterexamples": [], "corrections": []}
        self.assertTrue(autonomous.validate(verdict, data))
        verdict["counterexamples"] = [{"obligation_id": "O1", "inputs": []}]
        self.assertEqual([], autonomous.validate(verdict, data))
        statement["formula_package"]["value"] = None
        self.assertTrue(autonomous.validate(verdict, data))
        verdict["counterexamples"] = []
        self.assertEqual([], autonomous.validate(verdict, data))


class NativeRefutationTests(unittest.TestCase):
    def test_false_mixed_value_has_real_bound_kernel_counterexample_not_native_refutation(self):
        records = refutation_fixture.records()
        obj = proposal()
        obj["theorems"]["result"]["formula"]["body"]["right"] = {
            "tag": "field", "sort": "Input", "field": "value", "value": {"tag": "var", "index": 0}}
        compiled = formal_frontend.compile_response(canonical.dumps(obj), records, "refutation.fixture")
        source, _, problems = contract.compose_challenge(compiled.source, contract.registry_lean(records,
                                                        contract.binding_names(compiled.formalization)))
        self.assertEqual([], problems)
        tc, pol = leanbridge.resolve_toolchain(), policy.get("strict")
        with tempfile.TemporaryDirectory() as tmp:
            build = leanbridge.compile_module(tc, source, Path(tmp) / "base")
            self.assertTrue(build.ok, build.errors)
            result = leanbridge.run_kernel_tool(tc, build.olean, {"export": True, "axioms": True})
            env = contract.Env.from_export(result, pol, "refutation.fixture")
            analysis = contract.analyze(env, records, compiled.formalization, pol, tc.pin, "refutation.fixture")
            self.assertEqual([], analysis.diagnostics)
            probes = [{"obligation_id": "O1", "inputs": [{"dict": {"value": {"int": "0"}}}]}]
            self.assertEqual([], contract_refutation.validate_proposals(analysis, probes))
            pkg = Package(Path(tmp) / "package")
            pkg.ensure("authored-native-refutation")
            checked = contract_refutation.check(pkg, compiled.source, compiled.formalization, records, analysis, proposals=probes)
            self.assertEqual("REFUTED", checked["status"], checked)
            receipt = next(r for r in checked["receipts"] if r["status"] == "REFUTED")
            self.assertEqual("value", receipt["facet"])
            self.assertEqual("VeriSlopAST._vs_value_result", receipt["value_projection"]["lean_symbol"])
            self.assertEqual(canonical.digest_json(analysis.statements["O1"]["formula_package"]), receipt["parent_package_hash"])
            self.assertTrue(receipt["ok"])

    def test_mixed_existential_portfolio_does_not_manufacture_native_instance_proof(self):
        formula = {"tag": "exists", "sort": "Nat", "body": {"tag": "true"}}
        statement = {"representation": "contract_facets", "formula_package": {
            "encoding": native_contract.ENCODING, "value": {"formula": formula}, "native": [{"symbol": "f"}]}}
        tactic = prove.portfolio_tactic(statement, [], {})
        self.assertNotIn("contract_sound", tactic)
        source = native_contract.library_source() + ("\ndef endpoint (n : Nat) := n\n"
            "def boundary : VeriSlop.Native.NativeDefinition (Nat → Nat) := ⟨endpoint, [.noExternalIO]⟩\n"
            "theorem sample : (∃ n : Nat, True) ∧ VeriSlop.Native.Contract boundary := by " + tactic + "\n").encode()
        with tempfile.TemporaryDirectory() as tmp:
            result = leanbridge.compile_module(leanbridge.resolve_toolchain(), source, Path(tmp))
            self.assertTrue(result.ok, result.errors)
            self.assertTrue(result.sorry_positions)


class NativeFormalPipelineTests(unittest.TestCase):
    setUp = frontend_fixture.FrontendWorkflowTests.setUp
    assert_pass = frontend_fixture.FrontendWorkflowTests.assert_pass

    def test_mixed_reconstructs_from_kernel_with_scope_and_unchanged_original_claim(self):
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        compiled = formal_frontend.compile_response(canonical.dumps(proposal()), records, "fixture")
        self.assert_pass(formalize.run(self.pkg, self.events, agent=lambda ctx: (compiled.source, compiled.formalization), max_attempts=1))
        def proof(ctx):
            return ctx["challenge"].replace(":= by sorry", ":= by exact ⟨by intros; rfl, VeriSlop.Native.contract_sound _⟩")
        self.assert_pass(prove.run(self.pkg, self.events, portfolio=False, agent=proof, budget_seconds=0, max_attempts=1))
        self.assert_pass(accept.run(self.pkg, self.events))
        self.assert_pass(export.run(self.pkg, self.events))
        ir = canonical.load_file(self.pkg.path("accepted_ir"))
        obligation = ir["obligations"]["O1"]
        self.assertEqual(("postcondition", "guarantee", True), (obligation["kind"], obligation["role"], obligation["required"]))
        self.assertEqual("contract_facets", obligation["formal"]["representation"])
        digest = obligation["formal"]["formula_ref"].rsplit("@", 1)[1].split(":")[1]
        package = canonical.load_file(self.pkg.path("accepted") / "expressions" / (digest + ".json"))
        self.assertEqual("worker.py", package["native"][0]["requirements"][0]["file"])
        statements = contract.frozen_json(self.pkg, "statements.json")["statements"]
        self.assertIn("VeriSlopAST._vs_value_result", statements["O1"]["semantic_closure"])
        self.assertIn("VeriSlopAST.bump", statements["O1"]["semantic_closure"])

    def test_native_only_theorem_is_real_model_proof_without_invented_value_formula(self):
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        compiled = formal_frontend.compile_response(canonical.dumps(proposal(mixed=False)), records, "fixture")
        self.assert_pass(formalize.run(self.pkg, self.events, agent=lambda ctx: (compiled.source, compiled.formalization), max_attempts=1))
        self.assert_pass(prove.run(self.pkg, self.events, portfolio=False,
            agent=lambda ctx: ctx["challenge"].replace(":= by sorry", ":= by exact VeriSlop.Native.contract_sound _"), budget_seconds=0, max_attempts=1))
        self.assert_pass(accept.run(self.pkg, self.events))
        statements = contract.frozen_json(self.pkg, "statements.json")["statements"]
        self.assertIsNone(statements["O1"]["formula_package"]["value"])
        self.assertIsNone(statements["O1"]["formula_package"]["value_projection"])
