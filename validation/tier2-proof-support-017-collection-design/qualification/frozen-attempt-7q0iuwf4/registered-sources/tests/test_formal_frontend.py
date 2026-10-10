"""Generic native JSON formalizer frontend; no tasks or examples enter agent prompts."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir
from verislop.exprjson import constants
from verislop import canonical, contract, dsl, formal_frontend as ff, formalize, leanbridge, policy, reify
from verislop.jsonschema_lite import Registry


def frozen_records():
    return [{"id": oid, "origin": "interpreted", "blocked_by": [], "kind": kind, "role": role,
             "required": kind != "explicit_non_goal"} for oid, kind, role in [
        ("D1", "entity", "declaration"), ("A1", "precondition", "assumption"),
        ("O1", "postcondition", "guarantee"), ("O2", "invariant", "guarantee"),
        ("N1", "explicit_non_goal", "exclusion")]]


def example_proposal():
    var = lambda i: {"tag": "var", "index": i}
    integer = lambda n: {"tag": "int", "value": str(n)}
    field = lambda name, i=0: {"tag": "field", "sort": "Input", "field": name, "value": var(i)}
    valid = {"tag": "le", "left": field("minimum"), "right": integer(0)}
    accepted = {"tag": "list_filter", "value": field("values"), "function": {"sort": "Int", "body": {
        "tag": "decide", "formula": {"tag": "le", "left": field("minimum", 1), "right": var(0)}}}}
    values = {"tag": "list_map", "value": accepted, "function": {"sort": "Int", "body": {
        "tag": "int_mul", "left": var(0), "right": field("factor", 1)}}}
    total = {"tag": "list_foldl", "value": values, "initial": integer(0), "function": {
        "accumulator_sort": "Int", "element_sort": "Int", "body": {"tag": "int_add", "left": var(1), "right": var(0)}}}
    body = {"tag": "record", "sort": "Output", "fields": [values, total,
        {"tag": "nat_to_int", "value": {"tag": "list_length", "value": values}},
        {"tag": "string_append", "left": field("prefix"), "right": {"tag": "string", "value": '\"\\\x00\b\fé🙂'}}]}
    theorem = {"tag": "forall", "sort": {"record": "Input"}, "body": {"tag": "implies",
        "left": {"tag": "predicate", "predicate": "valid", "args": [var(0)]}, "right": {"tag": "eq",
        "left": {"tag": "call", "symbol": "solve", "args": [var(0)]}, "right": copy.deepcopy(body)}}}
    return {"encoding": ff.VERSION,
        "records": {"Input": {"fields": [{"name": "values", "sort": {"list": "Int"}},
            {"name": "minimum", "sort": "Int"}, {"name": "factor", "sort": "Int"}, {"name": "prefix", "sort": "String"}]},
            "Output": {"fields": [{"name": "values", "sort": {"list": "Int"}}, {"name": "total", "sort": "Int"},
                {"name": "count", "sort": "Int"}, {"name": "label", "sort": "String"}]}},
        "symbols": {"solve": {"args": [{"record": "Input"}], "result": {"record": "Output"}, "body": body}},
        "predicates": {"valid": {"args": [{"record": "Input"}], "formula": valid}},
        "theorems": {"observable": {"formula": theorem}, "nonvacuity": {"formula": {
            "tag": "exists", "sort": {"record": "Input"}, "body": {"tag": "predicate", "predicate": "valid", "args": [var(0)]}}}},
        "obligations": {"D1": {"declarations": [{"kind": "record", "name": "Input"}, {"kind": "record", "name": "Output"},
            {"kind": "symbol", "name": "solve"}]}, "A1": {"predicate": "valid"}, "O1": {"theorem": "observable"},
            "O2": {"theorem": "observable"}, "N1": {}},
        "witness_obligations": {"W1": {"theorem": "nonvacuity", "witnesses_for": ["A1"], "description": "a valid input exists"}}}


class FormalFrontendKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        cls.proposal = example_proposal()
        cls.frozen = frozen_records()
        cls.generated = ff.compile_response(canonical.dumps(cls.proposal), cls.frozen, "generated.v0_2")
        cls.compiled = leanbridge.compile_module(cls.tc, cls.generated.source, cls.tmp.path / "frontend")
        if not cls.compiled.ok:
            raise AssertionError((cls.compiled.errors, cls.generated.source.decode()))
        cls.exported = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        cls.env = contract.Env.from_export(cls.exported, policy.get("strict"), "frontend")
        if cls.env.diagnostics:
            raise AssertionError(cls.env.diagnostics)
        cls.kernel = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"defeq": ff.kernel_audit_requests(cls.generated)})["defeq"]
        cls.roots = {"VeriSlopAST.observable", "VeriSlopAST.nonvacuity", "VeriSlopAST.valid", "VeriSlopAST.solve", "VeriSlopAST.Input", "VeriSlopAST.Output"}
        raw, _ = reify.derive_profile("generated.v0_2", cls.env.decls, cls.env.hashes, cls.roots)
        cls.profile = dsl.Profile.from_json(raw)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_canonical_generated_source_and_manifest_compile_with_exact_kernel_fidelity(self):
        for result in self.kernel:
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, result["result"], result)
        self.assertEqual([], formalize.validate_candidate(self.generated.formalization, self.frozen))
        source = self.generated.source.decode()
        self.assertIn("«prefix» : _root_.String", source)
        self.assertIn("«Input».«prefix»", source)
        self.assertNotIn("「", source)
        self.assertIn('\\x00\\x08\\x0c', source)
        self.assertEqual(2, source.count("by sorry"))
        self.assertEqual(1, source.count("theorem «observable»"))

    def test_shared_theorem_and_witness_preserve_exact_frozen_ids_roles(self):
        bindings = {row["obligation"]: row for row in self.generated.formalization["bindings"]}
        self.assertEqual(set(row["id"] for row in self.frozen), set(bindings))
        self.assertEqual(bindings["O1"]["theorem"], bindings["O2"]["theorem"])
        self.assertEqual("VeriSlopAST.valid", bindings["A1"]["predicate"])
        self.assertEqual(["A1"], self.generated.formalization["internal_obligations"][0]["witnesses_for"])
        self.assertIn("VeriSlopAST.valid", constants(self.env.decls["VeriSlopAST.nonvacuity"]["type"]))

    def test_accepted_lean_reifier_exports_standard_dsl_and_hash_bound_records(self):
        requests = []
        for name in ("observable", "nonvacuity"):
            row = self.env.decls["VeriSlopAST." + name]
            formula, why, _ = reify.reify_formula(row["type"], self.profile, self.env.decls)
            self.assertIsNotNone(formula, why)
            self.assertNotIn('"tag":"predicate"', canonical.dumps(formula).decode())
            package = dsl.make_package(formula, self.profile.profile_id, encoding=dsl.ENCODING_V2)
            self.assertTrue(dsl.round_trip_ok(package, self.profile))
            requests.append({"id": name, "theorem": row["name"], "expr": reify.denote_formula(formula, self.profile)})
        for result in leanbridge.run_kernel_tool(self.tc, self.compiled.olean, {"defeq": requests})["defeq"]:
            self.assertTrue(result["result"]["defeq"], result)
        self.assertEqual(["values", "minimum", "factor", "prefix"], [f["name"] for f in self.profile.records["Input"]["fields"]])
        self.assertEqual(self.env.hashes["VeriSlopAST.Input.prefix"], self.profile.records["Input"]["fields"][-1]["projection_hash"])

    def test_proposal_declarations_named_like_generated_binders_are_fully_qualified(self):
        proposal = example_proposal()
        proposal["symbols"]["_v0"] = {"args": ["Nat"], "result": "Nat", "body": {"tag": "var", "index": 0}}
        proposal["theorems"]["binderSafe"] = {"formula": {"tag": "forall", "sort": "Nat", "body": {
            "tag": "eq", "left": {"tag": "call", "symbol": "_v0", "args": [{"tag": "var", "index": 0}]},
            "right": {"tag": "var", "index": 0}}}}
        proposal["obligations"]["O2"] = {"theorem": "binderSafe"}
        generated = ff.compile_response(canonical.dumps(proposal), self.frozen, "binder.v0_2")
        compiled = leanbridge.compile_module(self.tc, generated.source, self.tmp.path / "binder")
        self.assertTrue(compiled.ok, compiled.errors)
        self.assertIn(b'_root_.VeriSlopAST.\xc2\xab_v0\xc2\xbb \xc2\xab_v0\xc2\xbb', generated.source)
        for result in leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(generated)})["defeq"]:
            self.assertTrue(result["result"]["defeq"], result)

    def test_original_json_is_not_the_downstream_artifact_or_a_proof(self):
        row = self.env.decls["VeriSlopAST.observable"]
        formula, _, _ = reify.reify_formula(row["type"], self.profile, self.env.decls)
        body = formula["body"]["right"]["right"]
        self.assertEqual(set(), dsl.calls(body))
        inp = dsl.record_v("Input", [(-5, -2, -2, 0, 7), -2, -3, "✓"])
        result = dsl.Evaluator(self.profile, {}, lambda *_: []).term(body, [inp])
        self.assertEqual(dsl.record_v("Output", [(6, 6, 0, -21), -9, 4, '✓\"\\\x00\b\fé🙂']), result)
        self.assertIn("sorryAx", self.env.axioms("VeriSlopAST.observable"))

    def test_remaining_primitive_palette_and_bounded_quantifiers_have_exact_denotations(self):
        proposal = example_proposal()
        var = lambda n: {"tag": "var", "index": n}
        proposal["symbols"].update({
            "naturals": {"args": ["Nat", "Nat"], "result": "Nat", "body": {"tag": "sub", "left": var(1), "right": var(0)}},
            "booleans": {"args": ["Bool", "Bool"], "result": "Bool", "body": {"tag": "bool_eq", "left": {
                "tag": "bool_and", "left": var(1), "right": {"tag": "bool_not", "value": var(0)}}, "right": var(0)}},
            "text": {"args": ["String", "String"], "result": "Bool", "body": {"tag": "bool_or", "left": {
                "tag": "bool_eq", "left": {"tag": "string_append", "left": var(1), "right": var(0)}, "right": {"tag": "string", "value": ""}},
                "right": {"tag": "string_is_empty", "value": var(0)}}},
            "textSize": {"args": ["String"], "result": "Nat", "body": {"tag": "string_length", "value": var(0)}},
            "merge": {"args": [{"list": "Nat"}, {"list": "Nat"}], "result": {"list": "Nat"}, "body": {"tag": "list_reverse", "value": {
                "tag": "list_append", "left": {"tag": "list_cons", "head": {"tag": "nat", "value": "2"}, "tail": var(1)}, "right": var(0)}}},
            "summer": {"args": [{"list": "Int"}], "result": "Int", "body": {"tag": "list_sum", "value": var(0)}},
            "unitValue": {"args": [], "result": "Unit", "body": {"tag": "unit"}},
            "success": {"args": ["Int"], "result": {"result": {"error": "String", "ok": "Int"}}, "body": {"tag": "ok", "error_sort": "String", "value": var(0)}},
            "failure": {"args": ["String"], "result": {"result": {"error": "String", "ok": "Int"}}, "body": {"tag": "error", "ok_sort": "Int", "value": var(0)}}})
        proposal["theorems"]["bounded"] = {"formula": {"tag": "forall", "sort": "Nat", "body": {
            "tag": "forall_range", "lower": {"tag": "nat", "value": "0"}, "upper": var(0), "body": {
                "tag": "exists_range", "lower": {"tag": "nat", "value": "0"}, "upper": var(1), "body": {
                    "tag": "eq", "left": var(0), "right": var(1)}}}}}
        proposal["obligations"]["O2"] = {"theorem": "bounded"}
        generated = ff.compile_response(canonical.dumps(proposal), self.frozen, "palette.v0_2")
        compiled = leanbridge.compile_module(self.tc, generated.source, self.tmp.path / "palette")
        self.assertTrue(compiled.ok, compiled.errors)
        for result in leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(generated)})["defeq"]:
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, result["result"], result)

    def test_kernel_fidelity_rejects_a_wrong_primitive_even_if_tampered_source_compiles(self):
        changed = self.generated.source.replace(b"_root_.Int.add", b"_root_.Int.sub")
        self.assertNotEqual(self.generated.source, changed)
        compiled = leanbridge.compile_module(self.tc, changed, self.tmp.path / "wrong-primitive")
        self.assertTrue(compiled.ok, compiled.errors)
        results = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(self.generated)})["defeq"]
        checks = {r["id"]: r["result"] for r in results}
        self.assertTrue(checks["body:_vs_body_solve"]["typechecks"])
        self.assertFalse(checks["body:_vs_body_solve"]["defeq"])
        self.assertFalse(checks["statement:observable"]["defeq"])

    def test_capture_avoiding_predicate_macros_under_quantifiers_and_fold(self):
        proposal = example_proposal()
        proposal["predicates"]["less"] = {"args": ["Int", "Int"], "formula": {
            "tag": "forall", "sort": "Int", "body": {"tag": "le", "left": {"tag": "var", "index": 2}, "right": {"tag": "var", "index": 1}}}}
        proposal["predicates"]["same"] = {"args": ["Int"], "formula": {"tag": "eq", "left": {"tag": "var", "index": 0}, "right": {"tag": "var", "index": 0}}}
        proposal["symbols"]["captured"] = {"args": ["Int", {"list": "Int"}], "result": "Bool", "body": {
            "tag": "list_foldl", "value": {"tag": "var", "index": 0}, "initial": {"tag": "bool", "value": True}, "function": {
                "accumulator_sort": "Bool", "element_sort": "Int", "body": {"tag": "bool_and", "left": {"tag": "var", "index": 1}, "right": {
                    "tag": "decide", "formula": {"tag": "predicate", "predicate": "same", "args": [{"tag": "int_add", "left": {"tag": "var", "index": 0}, "right": {"tag": "var", "index": 3}}]}}}}}}
        proposal["theorems"]["quantifierCapture"] = {"formula": {"tag": "forall", "sort": "Int", "body": {"tag": "forall", "sort": "Int", "body": {
            "tag": "predicate", "predicate": "less", "args": [{"tag": "var", "index": 1}, {"tag": "var", "index": 0}]}}}}
        proposal["obligations"]["O2"] = {"theorem": "quantifierCapture"}
        generated = ff.compile_response(canonical.dumps(proposal), self.frozen, "capture.v0_2")
        compiled = leanbridge.compile_module(self.tc, generated.source, self.tmp.path / "capture")
        self.assertTrue(compiled.ok, compiled.errors)
        for result in leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(generated)})["defeq"]:
            self.assertTrue(result["result"]["defeq"], result)


class FormalFrontendValidationTests(unittest.TestCase):
    def setUp(self):
        self.obj, self.records = example_proposal(), frozen_records()

    def compile(self, obj=None, records=None):
        return ff.compile_proposal(self.obj if obj is None else obj, self.records if records is None else records)

    def test_source_origin_reconstructs_exact_response_context_and_compiler_output(self):
        raw = b' \n' + canonical.dumps(self.obj) + b'\n'
        source, manifest, receipt = ff.compile_proposal(self.obj, self.records, captured_response=raw, response_ref="native/response.json")
        self.assertEqual("generated.v0_2", receipt["profile_id"])
        self.assertEqual(ff.NAMESPACE, receipt["namespace"])
        self.assertTrue(ff.replay_receipt(self.obj, self.records, source, manifest, receipt, captured_response=raw))
        variants = [(source + b"-- edit\n", manifest, receipt, raw),
                    (source, {**manifest, "profile_id": "changed"}, receipt, raw),
                    (source, manifest, {**receipt, "compiler_source_hash": "sha256:" + "0" * 64}, raw),
                    (source, manifest, receipt, canonical.dumps(self.obj))]
        for s, f, r, captured in variants:
            with self.subTest(change=(s != source, f != manifest, r != receipt, captured != raw)):
                self.assertFalse(ff.replay_receipt(self.obj, self.records, s, f, r, captured_response=captured))
        changed = copy.deepcopy(self.records)
        changed[2]["role"] = "assumption"
        self.assertFalse(ff.replay_receipt(self.obj, changed, source, manifest, receipt, captured_response=raw))

    def test_wrong_ids_roles_references_raw_source_and_unknown_fields_are_rejected(self):
        mutations = []
        wrong = copy.deepcopy(self.obj); wrong["obligations"]["O99"] = wrong["obligations"].pop("O1"); mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["obligations"]["A1"] = {"theorem": "observable"}; mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["obligations"]["O1"] = {"predicate": "valid"}; mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["obligations"]["D1"]["declarations"][0]["name"] = "Missing"; mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["lean_source"] = "anything"; mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["theorems"]["observable"]["proof"] = "by rfl"; mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["symbols"]["solve"]["body"] = {"tag": "lean", "source": "「prefix」"}; mutations.append(wrong)
        wrong = copy.deepcopy(self.obj); wrong["records"]["Input"]["fields"][-1]["name"] = "prefix; theorem hacked : True := by trivial"; mutations.append(wrong)
        for obj in mutations:
            with self.subTest(keys=list(obj)), self.assertRaises(ff.FrontendError):
                self.compile(obj)

    def test_acyclic_forward_definitions_are_sorted_and_recursive_definitions_fail_closed(self):
        obj = copy.deepcopy(self.obj)
        obj["symbols"]["zhelper"] = {"args": ["Int"], "result": "Int", "body": {"tag": "var", "index": 0}}
        obj["symbols"]["afirst"] = {"args": ["Int"], "result": "Int", "body": {"tag": "call", "symbol": "zhelper", "args": [{"tag": "var", "index": 0}]}}
        source, _, _ = self.compile(obj)
        self.assertLess(source.index(b"def \xc2\xabzhelper"), source.index(b"def \xc2\xabafirst"))
        obj["symbols"]["zhelper"]["body"] = {"tag": "call", "symbol": "afirst", "args": [{"tag": "var", "index": 0}]}
        with self.assertRaisesRegex(ff.FrontendError, "cyclic"):
            self.compile(obj)
        obj = copy.deepcopy(self.obj)
        obj["records"]["Input"]["fields"].append({"name": "loop", "sort": {"list": {"record": "Input"}}})
        with self.assertRaisesRegex(ff.FrontendError, "recursive record"):
            self.compile(obj)

    def test_predicate_signature_cycles_and_mixed_symbol_cycles_fail_closed(self):
        obj = copy.deepcopy(self.obj)
        obj["theorems"]["nonvacuity"]["formula"]["body"]["args"] = [{"tag": "int", "value": "0"}]
        with self.assertRaisesRegex(ff.FrontendError, "arity/sorts"):
            self.compile(obj)
        obj = copy.deepcopy(self.obj)
        obj["predicates"]["valid"]["formula"] = {"tag": "predicate", "predicate": "valid", "args": [{"tag": "var", "index": 0}]}
        with self.assertRaisesRegex(ff.FrontendError, "cyclic"):
            self.compile(obj)
        obj = copy.deepcopy(self.obj)
        obj["symbols"]["cyclicBool"] = {"args": [{"record": "Input"}], "result": "Bool", "body": {"tag": "decide", "formula": {"tag": "predicate", "predicate": "valid", "args": [{"tag": "var", "index": 0}]}}}
        obj["predicates"]["valid"]["formula"] = {"tag": "holds", "term": {"tag": "call", "symbol": "cyclicBool", "args": [{"tag": "var", "index": 0}]}}
        with self.assertRaisesRegex(ff.FrontendError, "cyclic"):
            self.compile(obj)

    def test_witnesses_require_existentials_and_actual_frozen_assumptions(self):
        for which in ("shape", "target", "id"):
            obj = copy.deepcopy(self.obj)
            if which == "shape":
                obj["witness_obligations"]["W1"]["theorem"] = "observable"
            elif which == "target":
                obj["witness_obligations"]["W1"]["witnesses_for"] = ["O1"]
            else:
                obj["witness_obligations"]["A1"] = obj["witness_obligations"].pop("W1")
            with self.subTest(which=which), self.assertRaises(ff.FrontendError):
                self.compile(obj)

    def test_primitive_shadowing_and_malformed_typed_references_are_rejected(self):
        for name in ("Nat", "Int", "List", "String", "decide", "True"):
            obj = copy.deepcopy(self.obj)
            obj["symbols"][name] = {"args": [], "result": "Int", "body": {"tag": "int", "value": "0"}}
            with self.subTest(name=name), self.assertRaisesRegex(ff.FrontendError, "shadow"):
                self.compile(obj)
        for mutation in ("theorem", "predicate", "declaration", "witness"):
            obj = copy.deepcopy(self.obj)
            if mutation == "theorem":
                obj["obligations"]["O1"]["theorem"] = {}
            elif mutation == "predicate":
                obj["obligations"]["A1"]["predicate"] = []
            elif mutation == "declaration":
                obj["obligations"]["D1"]["declarations"][0]["kind"] = {}
            else:
                obj["witness_obligations"]["W1"]["witnesses_for"] = [{}]
            with self.subTest(mutation=mutation), self.assertRaises(ff.FrontendError):
                self.compile(obj)

    def test_registered_schema_structure_and_open_question_binding(self):
        registry = Registry()
        schema = canonical.load_file(Path(__file__).resolve().parents[1] / "schemas" / "formalizer-ast.schema.json")
        registry.add(schema)
        self.assertEqual([], registry.validate(self.obj, schema["$id"]))
        obj = copy.deepcopy(self.obj)
        obj["symbols"]["solve"]["proof"] = "by rfl"
        self.assertTrue(registry.validate(obj, schema["$id"]))
        rows = copy.deepcopy(self.records) + [{"id": "Q1", "origin": "interpreted", "blocked_by": [],
            "kind": "ambiguity", "role": "open_question", "required": False}]
        obj = copy.deepcopy(self.obj)
        obj["obligations"]["Q1"] = {}
        _, manifest, _ = self.compile(obj, rows)
        self.assertIn({"obligation": "Q1"}, manifest["bindings"])

    def test_duplicate_or_mismatched_captured_response_and_code_fences_are_rejected(self):
        with self.assertRaises(ff.FrontendError):
            ff.compile_response(b'{"encoding":"bad","encoding":"bad"}', self.records, "generated.v0_2")
        with self.assertRaises(ff.FrontendError):
            ff.compile_proposal(self.obj, self.records, captured_response=canonical.dumps({**self.obj, "encoding": "other"}))
        with self.assertRaises(ff.FrontendError):
            ff.compile_proposal(self.obj, self.records, captured_response=b'```json\n' + canonical.dumps(self.obj) + b'\n```')


if __name__ == "__main__":
    unittest.main()
