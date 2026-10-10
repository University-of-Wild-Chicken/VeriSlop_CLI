"""Fresh source-facet authoring fixtures; no inference, retained programs or acceptance authority."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import agents, canonical, formal_frontend as ff, native_contract, reify, schemas, source_contract
from verislop.errors import UsageError
from verislop.events import EventSink
from verislop.exprjson import app, const, constants, head_const, pi
from verislop.package import Package


def frozen_records():
    return [{"id": "G1", "origin": "interpreted", "blocked_by": [], "kind": "postcondition",
             "role": "guarantee", "required": True, "statement": "fresh source fixture", "dependencies": [],
             "acceptance_criteria": ["preserve the exact entry and source guarantees"]}]


def source_proposal(*, mixed=False):
    var = {"tag": "var", "index": 0}
    body = {"tag": "int_add", "left": var, "right": {"tag": "int", "value": "2"}}
    theorem = {"source": ["Delivery"]}
    if mixed:
        theorem["formula"] = {"tag": "forall", "sort": "Int", "body": {"tag": "eq",
            "left": {"tag": "call", "symbol": "plus", "args": [var]}, "right": copy.deepcopy(body)}}
    return {"encoding": ff.VERSION, "records": {},
            "symbols": {"plus": {"args": ["Int"], "result": "Int", "body": body}}, "predicates": {},
            "theorems": {"Spec": theorem}, "obligations": {"G1": {"theorem": "Spec"}}, "witness_obligations": {},
            "source_requirements": {"Delivery": {"symbol": "plus", "requirements": [
                {"tag": "entry", "file": "program.vscore.json", "entry": "plus", "arity": 1},
                *({"tag": tag} for tag in ("typed_total", "deterministic", "input_preserved", "no_external_io",
                                          "no_floating_point", "pure_data", "restricted_runtime_only"))]}}}


class SourceFrontendTests(unittest.TestCase):
    def compile(self, proposal=None, records=None):
        return ff.compile_response(canonical.dumps(proposal if proposal is not None else source_proposal()),
                                   records if records is not None else frozen_records(), "fresh.source.v0_2")

    def test_source_only_contract_and_closed_schema_are_distinct_from_native(self):
        proposal = source_proposal()
        self.assertEqual(schemas.validate("formalizer-ast", proposal), [])
        compiled = self.compile(proposal)
        self.assertEqual(schemas.validate("formalization-candidate", compiled.formalization), [])
        binding = compiled.formalization["bindings"][0]
        self.assertEqual(binding, {"obligation": "G1", "theorem": "VeriSlopAST.Spec",
                                  "source_requirements": ["VeriSlopAST.Delivery"]})
        text = compiled.source.decode()
        self.assertIn("_root_.VeriSlop.Source.SourceDefinition (_root_.Int → _root_.Int)", text)
        self.assertIn('_root_.VeriSlop.Source.SourceRequirement.entry "program.vscore.json" "plus" 1', text)
        self.assertIn("theorem «Spec» : (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«Delivery»)", text)
        self.assertNotIn("VeriSlop.Native", text)
        self.assertNotIn("value_projection", binding)
        self.assertEqual(compiled.receipt["source_model_version"], source_contract.MODEL_VERSION)
        self.assertEqual(compiled.receipt["source_model_source_hash"], source_contract.model_source_hash())
        self.assertNotIn("native_model_version", compiled.receipt)
        requests = {r["id"]: r for r in ff.kernel_audit_requests(compiled)}
        endpoint_type = pi("x", const("Int"), const("Int"))
        self.assertEqual(requests["statement:Spec"]["expr"], source_contract.source_prop("VeriSlopAST.Delivery", endpoint_type))
        self.assertNotIn("value:Spec", requests)

    def test_mixed_projection_depends_on_original_complete_theorem_and_retains_each_id(self):
        proposal = source_proposal(mixed=True)
        proposal["obligations"]["G2"] = {"theorem": "Spec"}
        records = frozen_records() + [{**frozen_records()[0], "id": "G2"}]
        compiled = self.compile(proposal, records)
        self.assertEqual({b["obligation"] for b in compiled.formalization["bindings"]}, {"G1", "G2"})
        for binding in compiled.formalization["bindings"]:
            self.assertEqual(binding["source_requirements"], ["VeriSlopAST.Delivery"])
            self.assertEqual(binding["value_projection"], "VeriSlopAST._vs_value_Spec")
        self.assertIn("by exact _root_.VeriSlopAST.«Spec».1", compiled.source.decode())
        requests = {r["id"]: r for r in ff.kernel_audit_requests(compiled)}
        value = reify.denote_formula(proposal["theorems"]["Spec"]["formula"], compiled.profile)
        source = source_contract.source_prop("VeriSlopAST.Delivery", pi("x", const("Int"), const("Int")))
        self.assertEqual(requests["statement:Spec"]["expr"], app(const("And"), value, source))
        self.assertEqual(requests["value:Spec"]["expr"], value)
        self.assertTrue(ff.reconstruct_origin(canonical.dumps(proposal), records, compiled.source,
                                              compiled.formalization, compiled.receipt))
        altered = copy.deepcopy(compiled.formalization)
        altered["bindings"][0]["value_projection"] = "VeriSlopAST.Spec"
        self.assertFalse(ff.reconstruct_origin(canonical.dumps(proposal), records, compiled.source, altered, compiled.receipt))

    def test_bad_source_paths_names_arities_parameters_and_endpoints_block(self):
        mutations = [
            lambda p: p["source_requirements"]["Delivery"]["requirements"][0].update(file="solution.py"),
            lambda p: p["source_requirements"]["Delivery"]["requirements"][0].update(file="../program.vscore.json"),
            lambda p: p["source_requirements"]["Delivery"]["requirements"][0].update(entry="bad/name"),
            lambda p: p["source_requirements"]["Delivery"]["requirements"][0].update(arity=0),
            lambda p: p["source_requirements"]["Delivery"]["requirements"][0].update(arity=True),
            lambda p: p["source_requirements"]["Delivery"]["requirements"][0].update(qualname="plus"),
            lambda p: p["source_requirements"]["Delivery"]["requirements"].append({"tag": "physical_time"}),
            lambda p: p["source_requirements"]["Delivery"]["requirements"].append({"tag": "typed_total", "fact": True}),
            lambda p: p["source_requirements"]["Delivery"]["requirements"].append({"tag": "typed_total"}),
            lambda p: p["source_requirements"]["Delivery"].update(symbol="missing"),
            lambda p: p["source_requirements"]["Delivery"].update(facts={"typed_total": True}),
            lambda p: p["theorems"]["Spec"].update(source=["missing"]),
            lambda p: p["theorems"]["Spec"].update(source=["Delivery", "Delivery"]),
            lambda p: p["source_requirements"].update(Unused=copy.deepcopy(p["source_requirements"]["Delivery"])),
        ]
        for number, mutate in enumerate(mutations):
            with self.subTest(mutation=number):
                proposal = source_proposal()
                mutate(proposal)
                with self.assertRaises(ff.FrontendError):
                    self.compile(proposal)
        # Exact accepted arity is not constrained by Python's separate 16-argument budget.
        proposal = source_proposal()
        proposal["symbols"]["plus"].update(args=["Int"] * 17)
        proposal["source_requirements"]["Delivery"]["requirements"][0].update(arity=17, entry="deployed-plus.v3")
        self.assertEqual(schemas.validate("formalizer-ast", proposal), [])
        self.assertIn('"deployed-plus.v3" 17', self.compile(proposal).source.decode())

    def test_native_and_source_cannot_mix_in_one_theorem_or_binding(self):
        proposal = source_proposal()
        proposal["native_requirements"] = {"PythonDelivery": {"symbol": "plus", "requirements": [{"tag": "deterministic"}]}}
        proposal["theorems"]["Spec"]["native"] = ["PythonDelivery"]
        self.assertTrue(schemas.validate("formalizer-ast", proposal))
        with self.assertRaises(ff.FrontendError):
            self.compile(proposal)
        candidate = self.compile().formalization
        candidate["bindings"][0]["native_requirements"] = ["VeriSlopAST.PythonDelivery"]
        self.assertTrue(schemas.validate("formalization-candidate", candidate))

    def test_separate_native_theorem_keeps_original_native_namespace_and_requirements(self):
        proposal = source_proposal()
        proposal["native_requirements"] = {"PythonDelivery": {"symbol": "plus", "requirements": [
            {"tag": "entry", "file": "module.py", "qualname": "plus", "arity": 1}, {"tag": "pure_json"}]}}
        proposal["theorems"]["PythonSpec"] = {"native": ["PythonDelivery"]}
        proposal["obligations"]["G2"] = {"theorem": "PythonSpec"}
        compiled = self.compile(proposal, frozen_records() + [{**frozen_records()[0], "id": "G2"}])
        text = compiled.source.decode()
        self.assertEqual(text.count("import Std"), 1)
        self.assertIn("namespace VeriSlop.Native", text)
        self.assertIn("namespace VeriSlop.Source", text)
        self.assertIn('_root_.VeriSlop.Native.NativeRequirement.entry "module.py" "plus" 1', text)
        self.assertEqual(compiled.receipt["native_model_source_hash"], native_contract.model_source_hash())
        bindings = {b["obligation"]: b for b in compiled.formalization["bindings"]}
        self.assertNotIn("native_requirements", bindings["G1"])
        self.assertNotIn("source_requirements", bindings["G2"])
        requests = {r["id"]: r for r in ff.kernel_audit_requests(compiled)}
        self.assertIn("VeriSlop.Native.Contract", constants(requests["statement:PythonSpec"]["expr"]))
        self.assertNotIn("VeriSlop.Source.Contract", constants(requests["statement:PythonSpec"]["expr"]))

    def test_marker_schema_and_receipt_mutation_preserve_closed_authority_boundary(self):
        proposal = source_proposal()
        for marker in ("pure_json", "standard_runtime_only", "host_runtime_only", "no_floating_point"):
            p = copy.deepcopy(proposal)
            p["source_requirements"]["Delivery"]["requirements"] = [{"tag": marker, "fact": True}]
            with self.subTest(marker=marker):
                self.assertTrue(schemas.validate("formalizer-ast", p))
        compiled = self.compile(proposal)
        receipt = {**compiled.receipt, "source_model_source_hash": "sha256:" + "0" * 64}
        self.assertFalse(ff.reconstruct_origin(canonical.dumps(proposal), frozen_records(), compiled.source,
                                               compiled.formalization, receipt))


class SourceFrontendAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-source-front-agent-")
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name))
        self.pkg.ensure("source-agent-unit")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)

    def test_backend3_formalizer_uses_typed_source_instructions_without_campaign_constraints(self):
        response = json.dumps(source_proposal(mixed=True))
        requested = {"tier": 2, "target": "vscore", "endpoint": "restricted_source", "backend_version": "0.3",
                     "require_state": "END_TO_END_VERIFIED"}
        with patch.object(agents, "_broker", return_value=(None, {})), patch.object(agents, "_role", return_value="formalizer"), \
             patch.object(agents, "restore_formalizer_response", return_value=None), \
             patch.object(agents, "recorded_call", return_value=SimpleNamespace(text=response, request_id="fixture")) as called:
            agent = agents.formalizer_agent("unused", self.pkg, self.events)
            source, form = agent({"records": frozen_records(), "ledger": {}, "requested": requested,
                                  "feedback": [], "attempt": 1})
        self.assertIn(b"VeriSlop.Source.Contract", source)
        self.assertEqual(form["bindings"][0]["source_requirements"], ["VeriSlopAST.Delivery"])
        self.assertEqual(called.call_args.args[4], agents.TYPED_FORMALIZER_SYSTEM)
        user = called.call_args.args[5]
        self.assertIn("VSCORE 0.3 SOURCE BOUNDARY", user)
        self.assertIn("source_requirements", user)
        self.assertNotIn("current Python generated-test bridge", user)
        self.assertNotIn("CAMPAIGN QUANTIFIER SHAPE", user)
        self.assertNotIn("NATIVE BOUNDARY FACETS:", user)

    def test_accepted_source_packages_are_exact_and_source_only_is_not_a_value_oracle(self):
        compiled = ff.compile_response(canonical.dumps(source_proposal(mixed=True)), frozen_records(), "fresh.source.v0_2")
        value = {"encoding": "verislop.contract-dsl/0.2", "semantic_profile": compiled.profile.profile_id,
                 "formula": source_proposal(mixed=True)["theorems"]["Spec"]["formula"]}
        for value_package in (None, value):
            package = {"encoding": source_contract.ENCODING, "semantic_profile": compiled.profile.profile_id,
                       "value": value_package, "source": [{"symbol": "plus"}], "value_projection": None}
            rec = {**frozen_records()[0], "revision": 1, "formal": {"representation": "source_facets", "formula_ref": "fixture"}}
            ctx = {"profile": compiled.profile.raw, "ir": {"obligations": {"G1": rec}},
                   "statements": {"G1": {"representation": "source_facets", "formula_package": package}}}
            with self.subTest(source_only=value_package is None), patch("verislop.backends.admission.formula_package", return_value=package):
                result = agents._accepted_implementation_formulas(self.pkg, ctx)
                self.assertEqual(result["G1"]["formula_package"], package)
                ctx["statements"]["G1"]["formula_package"] = {**package, "source": []}
                with self.assertRaises(UsageError) as raised:
                    agents._accepted_implementation_formulas(self.pkg, ctx)
                self.assertEqual(raised.exception.diagnostics[0].code, "IR_REIFICATION_MISMATCH")


if __name__ == "__main__":
    unittest.main()
