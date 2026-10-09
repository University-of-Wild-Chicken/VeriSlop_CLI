"""Fresh generic restricted-source constructor and projection kernel fixtures."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from verislop import autonomous, canonical, contract, contract_refutation, contract_values, dsl, formal_frontend, formalize, leanbridge, policy, reify, source_contract
from verislop.exprjson import app, const, parse_name
from verislop.package import Package
from verislop.backends import vscore3, vscore3_admission
from tests import test_formal_frontend_workflow as frontend_fixture
from tests import test_contract_refutation as refutation_fixture


FROZEN = [{"id": "D1", "role": "declaration"}, {"id": "O1", "role": "guarantee"}]


def proposal():
    obj = copy.deepcopy(frontend_fixture.AST)
    obj["source_requirements"] = {"Boundary": {"symbol": "bump", "requirements": [
        {"tag": "entry", "file": "program.vscore.json", "entry": "bump", "arity": 1},
        *({"tag": t} for t in ("typed_total", "pure_data", "restricted_runtime_only", "no_external_io",
                              "input_preserved", "deterministic", "no_floating_point"))]}}
    obj["theorems"]["result"]["source"] = ["Boundary"]
    return obj


class SourceValueSurfaceTests(unittest.TestCase):
    def test_closed_source_parameters_and_unbounded_signature_arity(self):
        source_contract.validate_requirements([{"tag": "entry", "file": "program.vscore.json", "entry": "many.args", "arity": 27}], arity=27)
        for row in ({"tag": "entry", "file": "solution.py", "entry": "f", "arity": 1},
                    {"tag": "entry", "file": "program.vscore.json", "entry": "f", "arity": True},
                    {"tag": "deterministic", "observed": True}, {"tag": "pure_json"}):
            with self.subTest(row=row), self.assertRaises(source_contract.SourceError):
                source_contract.validate_requirements([row], arity=1)

    def test_mixed_critic_uses_only_checked_value_and_source_only_has_no_oracle(self):
        st = {"role": "guarantee", "representation": "source_facets", "formula_package": {
            "encoding": source_contract.ENCODING, "value": {"formula": {"tag": "true"}}, "source": []}}
        self.assertEqual(st["formula_package"]["value"], contract_values.statement_value_package(st))
        data = {"clauses": [], "diagnostics": [], "statements": {"O1": st}}
        verdict = {"encoding": autonomous.VERSION, "verdict": "ACCEPT", "counterexamples": [], "corrections": []}
        self.assertTrue(autonomous.validate(verdict, data))
        verdict["counterexamples"] = [{"obligation_id": "O1", "inputs": []}]
        self.assertEqual([], autonomous.validate(verdict, data))
        st["formula_package"]["value"] = None
        self.assertIsNone(contract_values.statement_value_package(st))
        verdict["counterexamples"] = []
        self.assertEqual([], autonomous.validate(verdict, data))

    def test_python_campaign_cannot_accept_revised_source_boundary(self):
        rec = {"id": "O1", "kind": "safety_property", "role": "guarantee", "required": True,
               "dependencies": [], "blocked_by": []}
        raw = {"profile_id": "fixture", "dsl": dsl.ENCODING_V2, "records": {}, "enums": {}, "predicates": {},
               "symbols": {"f": {"lean_decl": "f", "args": ["Int"], "result": "Int"}}}
        st = {"representation": "source_facets", "semantic_closure": {"f": "hash"}, "formula_package": {
            "encoding": source_contract.ENCODING, "value": None, "source": [{"symbol": "f"}]}}
        result = formalize.executable_readiness([rec], contract.Analysis(raw, {"O1": st}, [], [], []),
            {"target": "python", "tier": 0, "endpoint": "test_campaign", "require_state": "TESTED"})
        self.assertEqual(["UNSUPPORTED_CAPABILITY"], [d.code for d in result])

    def test_source_only_admission_binds_endpoint_and_does_not_drop_bad_required_facets(self):
        raw = {"profile_id": "fixture", "dsl": dsl.ENCODING_V2, "records": {}, "enums": {}, "predicates": {},
               "symbols": {"f": {"lean_decl": "Fixture.f", "args": ["Int"], "result": "Int"}}}
        package = {"encoding": source_contract.ENCODING, "semantic_profile": "fixture", "value": None,
                   "value_projection": None, "source": [{"symbol": "f", "requirements": [
                       {"tag": "entry", "file": "program.vscore.json", "entry": "f", "arity": 1}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Package(Path(tmp) / "package")
            pkg.ensure("source-admission-unit-fixture")

            def row(payload):
                digest = canonical.digest_json(payload)
                path = pkg.path("accepted") / "expressions" / (digest.split(":")[1] + ".json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(canonical.dumps(payload))
                return {"id": "S1", "kind": "safety_property", "role": "guarantee", "required": True,
                        "formal": {"representation": "source_facets", "formula_ref": "source@" + digest}}

            accepted = row(package)
            features, _ = vscore3_admission.features(pkg, {"obligations": {"S1": accepted}}, raw)
            self.assertEqual(("admitted", None, ["S1"]), vscore3_admission.admit(2, None, "no_tests", features))
            self.assertEqual(["f"], vscore3.source_symbols(pkg, accepted, raw))
            for edit in (lambda p: p["source"][0]["requirements"][0].update(arity=2),
                         lambda p: p["source"][0]["requirements"][0].update(file="solution.py"),
                         lambda p: p["source"][0].update(symbol="missing"),
                         lambda p: p["source"][0]["requirements"].append({"tag": "external_io_allowed"})):
                changed = copy.deepcopy(package)
                edit(changed)
                bad = row(changed)
                features, _ = vscore3_admission.features(pkg, {"obligations": {"S1": bad}}, raw)
                self.assertEqual(["S1"], vscore3_admission.covered(features))
                self.assertEqual(("rejected", "UNSUPPORTED_CAPABILITY", ["S1"]),
                                 vscore3_admission.admit(2, None, "no_tests", features))


class SourceConstructorKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-source-contract-fixture-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.tc = leanbridge.resolve_toolchain()
        cls.compiled = formal_frontend.compile_response(canonical.dumps(proposal()), FROZEN, "source.fixture")
        source = cls.compiled.source.replace(b":= by sorry", ":= by exact ⟨by intros; rfl, VeriSlop.Source.contract_sound _⟩".encode())
        build = leanbridge.compile_module(cls.tc, source, Path(cls.tmp.name))
        if not build.ok:
            raise AssertionError(build.errors)
        cls.olean = build.olean
        cls.kernel = leanbridge.run_kernel_tool(cls.tc, cls.olean, {"export": True, "axioms": True,
            "defeq": formal_frontend.kernel_audit_requests(cls.compiled)})
        cls.env = contract.Env.from_export(cls.kernel, policy.get("strict"), "source.fixture")
        raw, _ = reify.derive_profile("source.fixture", cls.env.decls, cls.env.hashes, {"VeriSlopAST.result"})
        cls.profile = dsl.Profile.from_json(raw)

    def decode(self, *, expr=None, binding=None, decls=None, hashes=None):
        return source_contract.reify_contract(expr or self.env.decls["VeriSlopAST.result"]["type"], self.profile,
            decls or self.env.decls, hashes or self.env.hashes, pin=self.tc.pin, theorem="VeriSlopAST.result",
            binding=binding or self.compiled.formalization["bindings"][1])

    def test_complete_accepted_conjunction_and_dependent_projection_round_trip(self):
        self.assertEqual([], self.env.diagnostics)
        self.assertTrue(all(row["result"].get("defeq") for row in self.kernel["defeq"]))
        package, _, checks, roots = self.decode()
        self.assertEqual({"bump"}, source_contract.symbols(package))
        self.assertEqual("program.vscore.json", package["source"][0]["requirements"][0]["file"])
        self.assertEqual("VeriSlopAST._vs_value_result", package["value_projection"]["lean_symbol"])
        self.assertIn("VeriSlopAST._vs_value_result", roots)
        self.assertFalse(any(name.startswith(source_contract.NS + ".") for name in self.profile.symbols))
        checks.append({"id": "whole", "theorem": parse_name("VeriSlopAST.result"),
                       "expr": source_contract.denote_package(package, self.profile, self.env.decls)})
        result = leanbridge.run_kernel_tool(self.tc, self.olean, {"defeq": checks})
        self.assertTrue(all(row["result"].get("defeq") for row in result["defeq"]))

    def test_author_json_has_no_authority_after_constructor_reconstruction(self):
        original = self.compiled.proposal["source_requirements"]["Boundary"]["requirements"][0]["file"]
        self.compiled.proposal["source_requirements"]["Boundary"]["requirements"][0]["file"] = "forged.py"
        try:
            package, *_ = self.decode()
            self.assertEqual("program.vscore.json", package["source"][0]["requirements"][0]["file"])
        finally:
            self.compiled.proposal["source_requirements"]["Boundary"]["requirements"][0]["file"] = original

    def test_missing_projection_wrong_definition_and_model_drift_reject(self):
        for edit in (lambda b: b.pop("source_requirements"), lambda b: b.pop("value_projection"),
                     lambda b: b.update(source_requirements=["VeriSlopAST.missing"]),
                     lambda b: b.update(value_projection="VeriSlopAST.result")):
            binding = copy.deepcopy(self.compiled.formalization["bindings"][1])
            edit(binding)
            with self.subTest(binding=binding), self.assertRaises(source_contract.SourceError):
                self.decode(binding=binding)
        hashes = dict(self.env.hashes)
        hashes[source_contract.NS + ".checkBoundary"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(source_contract.SourceError, "normative library"):
            self.decode(hashes=hashes)
        native_prop = app(const("VeriSlop.Native.Contract"), const("Nat"), const("fake"))
        with self.assertRaises(source_contract.SourceError):
            self.decode(expr=app(const("And"), native_prop, self.env.decls["VeriSlopAST.result"]["type"]))

    def test_source_only_reconstructs_without_fabricating_a_value_projection(self):
        obj = proposal()
        obj["theorems"]["result"].pop("formula")
        compiled = formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "source.fixture")
        source = compiled.source.replace(b":= by sorry", b":= by exact VeriSlop.Source.contract_sound _")
        with tempfile.TemporaryDirectory() as tmp:
            build = leanbridge.compile_module(self.tc, source, Path(tmp))
            self.assertTrue(build.ok, build.errors)
            response = leanbridge.run_kernel_tool(self.tc, build.olean, {"export": True, "axioms": True})
            env = contract.Env.from_export(response, policy.get("strict"), "source.fixture")
            raw, _ = reify.derive_profile("source.fixture", env.decls, env.hashes, {"VeriSlopAST.result"})
            profile = dsl.Profile.from_json(raw)
            package, _, checks, _ = source_contract.reify_contract(env.decls["VeriSlopAST.result"]["type"], profile,
                env.decls, env.hashes, pin=self.tc.pin, theorem="VeriSlopAST.result", binding=compiled.formalization["bindings"][1])
            self.assertIsNone(package["value"])
            self.assertIsNone(package["value_projection"])
            self.assertEqual([], checks)
            self.assertEqual({"bump"}, source_contract.symbols(package))
            result = leanbridge.run_kernel_tool(self.tc, build.olean, {"defeq": [{"id": "whole",
                "theorem": parse_name("VeriSlopAST.result"), "expr": source_contract.denote_package(package, profile, env.decls)}]})
            self.assertTrue(result["defeq"][0]["result"]["defeq"])


class SourceRefutationKernelTests(unittest.TestCase):
    def test_false_mixed_value_gets_bound_kernel_counterexample_without_source_fact_claim(self):
        records = refutation_fixture.records()
        obj = proposal()
        obj["theorems"]["result"]["formula"]["body"]["right"] = {
            "tag": "field", "sort": "Input", "field": "value", "value": {"tag": "var", "index": 0}}
        compiled = formal_frontend.compile_response(canonical.dumps(obj), records, "source.refutation.fixture")
        source, _, problems = contract.compose_challenge(compiled.source, contract.registry_lean(records,
                                                        contract.binding_names(compiled.formalization)))
        self.assertEqual([], problems)
        tc, pol = leanbridge.resolve_toolchain(), policy.get("strict")
        with tempfile.TemporaryDirectory() as tmp:
            build = leanbridge.compile_module(tc, source, Path(tmp) / "base")
            self.assertTrue(build.ok, build.errors)
            response = leanbridge.run_kernel_tool(tc, build.olean, {"export": True, "axioms": True})
            env = contract.Env.from_export(response, pol, "source.refutation.fixture")
            analysis = contract.analyze(env, records, compiled.formalization, pol, tc.pin, "source.refutation.fixture")
            self.assertEqual([], analysis.diagnostics)
            probes = [{"obligation_id": "O1", "inputs": [{"dict": {"value": {"int": "0"}}}]}]
            self.assertEqual([], contract_refutation.validate_proposals(analysis, probes))
            pkg = Package(Path(tmp) / "package")
            pkg.ensure("authored-source-refutation")
            result = contract_refutation.check(pkg, compiled.source, compiled.formalization, records, analysis, proposals=probes)
            self.assertEqual("REFUTED", result["status"], result)
            receipt = next(r for r in result["receipts"] if r["status"] == "REFUTED")
            self.assertEqual("value", receipt["facet"])
            self.assertEqual("VeriSlopAST._vs_value_result", receipt["value_projection"]["lean_symbol"])
            self.assertEqual(canonical.digest_json(analysis.statements["O1"]["formula_package"]), receipt["parent_package_hash"])
            self.assertTrue(receipt["ok"])


if __name__ == "__main__":
    unittest.main()
