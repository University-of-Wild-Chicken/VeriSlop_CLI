"""Kernel/AST/native-codec checks for generic grammar increments, independent of live models."""
from __future__ import annotations

import copy
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from verislop import canonical, contract, dsl, formal_frontend as ff, leanbridge, policy, reify
from verislop.targets import python_target


def variable(i):
    return {"tag": "var", "index": i}


def integer(i):
    return {"tag": "int", "value": str(i)}


def core_proposal():
    field = lambda n: {"tag": "field", "sort": "Input", "field": n, "value": variable(0)}
    option_int = {"option": "Int"}
    selected = {"tag": "ite", "condition": field("flag"), "then": field("candidate"),
                "else": {"tag": "none", "element_sort": "Int"}}
    body = {"tag": "record", "sort": "Output", "fields": [selected,
        {"tag": "option_get_or", "value": selected, "default": integer(-7)},
        {"tag": "option_is_some", "value": selected},
        {"tag": "list_cons", "head": {"tag": "some", "value": {"tag": "string", "value": "🙂"}},
         "tail": field("values")} ]}
    formula = {"tag": "forall", "sort": {"record": "Input"}, "body": {"tag": "eq",
        "left": {"tag": "call", "symbol": "solve", "args": [variable(0)]}, "right": body}}
    frozen = [{"id": "D1", "kind": "entity", "role": "declaration", "required": True},
              {"id": "O1", "kind": "postcondition", "role": "guarantee", "required": True}]
    proposal = {"encoding": ff.VERSION,
        "records": {"Input": {"fields": [{"name": "flag", "sort": "Bool"},
            {"name": "candidate", "sort": option_int}, {"name": "values", "sort": {"list": {"option": "String"}}}]},
            "Output": {"fields": [{"name": "selected", "sort": option_int}, {"name": "fallback", "sort": "Int"},
                {"name": "present", "sort": "Bool"}, {"name": "values", "sort": {"list": {"option": "String"}}}]}},
        "symbols": {"solve": {"args": [{"record": "Input"}], "result": {"record": "Output"}, "body": body}},
        "predicates": {}, "theorems": {"observable": {"formula": formula}},
        "obligations": {"D1": {"declarations": [{"kind": "record", "name": "Input"},
            {"kind": "record", "name": "Output"}, {"kind": "symbol", "name": "solve"}]}, "O1": {"theorem": "observable"}},
        "witness_obligations": {}}
    return proposal, frozen


class CoreKernelCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.tc = leanbridge.resolve_toolchain()
        proposal, frozen = core_proposal()
        cls.generated = ff.compile_response(canonical.dumps(proposal), frozen, "bootstrap.core")
        # The canonical compiler intentionally emits proof holes. This fixture discharges
        # its exact definitional theorem before inspecting the accepted artifact.
        cls.compiled = leanbridge.compile_module(cls.tc, cls.generated.source.replace(b"by sorry", b"by intros; rfl"),
                                                Path(cls.tmp.name) / "core")
        if not cls.compiled.ok:
            raise AssertionError((cls.compiled.errors, cls.generated.source.decode()))
        exported = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        cls.env = contract.Env.from_export(exported, policy.get("strict"), "core")
        raw, _ = reify.derive_profile("bootstrap.core", cls.env.decls, cls.env.hashes,
            {"VeriSlopAST.observable", "VeriSlopAST.Input", "VeriSlopAST.Output", "VeriSlopAST.solve"})
        cls.profile = dsl.Profile.from_json(raw)
        cls.formula, why, _ = reify.reify_formula(cls.env.decls["VeriSlopAST.observable"]["type"], cls.profile, cls.env.decls)
        if cls.formula is None:
            raise AssertionError(why)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_source_and_accepted_ast_have_kernel_equal_denotations_and_no_proof_holes(self):
        checks = ff.kernel_audit_requests(self.generated)
        checks.append({"id": "accepted", "theorem": ["VeriSlopAST", "observable"],
                       "expr": reify.denote_formula(self.formula, self.profile)})
        for result in leanbridge.run_kernel_tool(self.tc, self.compiled.olean, {"defeq": checks})["defeq"]:
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, result["result"], result)
        self.assertNotIn("sorryAx", self.env.axioms("VeriSlopAST.observable"))
        self.assertEqual({"option": "Int"}, self.profile.records["Input"]["fields"][1]["sort"])

    def test_reconstructed_formula_interprets_zero_none_lists_and_branch_choice(self):
        body = self.formula["body"]["right"]
        cases = [(True, dsl.option_some_v(0), dsl.option_some_v(0), 0, True),
                 (False, dsl.option_some_v(23), dsl.OPTION_NONE, -7, False),
                 (True, dsl.OPTION_NONE, dsl.OPTION_NONE, -7, False)]
        for flag, candidate, selected, fallback, present in cases:
            inp = dsl.record_v("Input", [flag, candidate, (dsl.OPTION_NONE, dsl.option_some_v("é"))])
            actual = dsl.Evaluator(self.profile, {}, lambda *_: []).term(body, [inp])
            self.assertEqual(dsl.record_v("Output", [selected, fallback, present,
                (dsl.option_some_v("🙂"), dsl.OPTION_NONE, dsl.option_some_v("é"))]), actual)

    def test_python_wire_maps_options_to_exact_native_none_or_payload(self):
        cases = [(dsl.OPTION_NONE, {"option": "Int"}, {"none": None}),
            (dsl.option_some_v(0), {"option": "Int"}, {"int": "0"}),
            (dsl.option_some_v(()), {"option": {"list": "Int"}}, {"list": []}),
            (dsl.option_some_v(dsl.record_v("Input", [True, dsl.OPTION_NONE, ()])), {"option": {"record": "Input"}},
             {"dict": {"flag": {"bool": True}, "candidate": {"none": None}, "values": {"list": []}}})]
        for value, sort, wire in cases:
            self.assertEqual(wire, python_target.encode_arg(value, sort, self.profile))
            self.assertEqual(value, python_target.decode_result(wire, sort, self.profile))
        with self.assertRaises(ValueError):
            python_target.decode_result({"bool": False}, {"option": "Int"}, self.profile)
        with self.assertRaises(ValueError):
            python_target.encode_arg(("some",), {"option": "Int"}, self.profile)

    def test_tampered_branch_source_cannot_pass_the_original_kernel_receipt(self):
        changed = self.generated.source.replace(b"_root_.Option.none _root_.Int", b"_root_.Option.some _root_.Int (_root_.Int.ofNat 99)")
        self.assertNotEqual(self.generated.source, changed)
        compiled = leanbridge.compile_module(self.tc, changed, Path(self.tmp.name) / "changed")
        self.assertTrue(compiled.ok, compiled.errors)
        results = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(self.generated)})["defeq"]
        self.assertFalse(next(x["result"]["defeq"] for x in results if x["id"] == "statement:observable"))


class CoreTypingCoverageTests(unittest.TestCase):
    def setUp(self):
        self.profile = dsl.Profile.from_json({"profile_id": "core", "dsl": dsl.ENCODING_V2,
            "enums": {}, "symbols": {}, "predicates": {}})

    def test_ambiguous_options_and_recursive_option_records_fail_closed(self):
        for sort in ({"option": "Unit"}, {"option": {"option": "Int"}}):
            with self.assertRaisesRegex(dsl.DSLError, "conflate"):
                dsl.check_sort(sort, self.profile)
        with self.assertRaisesRegex(dsl.DSLError, "recursive"):
            dsl.Profile.from_json({**self.profile.raw, "records": {"Node": {"fields": [
                {"name": "next", "sort": {"option": {"record": "Node"}}}]}}})

    def test_default_branch_condition_and_exact_shape_are_checked(self):
        bad = [{"tag": "option_get_or", "value": {"tag": "some", "value": integer(0)}, "default": {"tag": "bool", "value": False}},
            {"tag": "ite", "condition": integer(1), "then": integer(0), "else": integer(2)},
            {"tag": "ite", "condition": {"tag": "bool", "value": True}, "then": integer(0), "else": {"tag": "bool", "value": False}},
            {"tag": "none", "element_sort": "Int", "ignored": True}]
        for term in bad:
            with self.assertRaises(dsl.DSLError):
                dsl.type_term(term, [], self.profile)

    def test_finite_option_enumeration_and_unselected_branch_are_exact(self):
        self.assertEqual([dsl.OPTION_NONE, dsl.option_some_v(False), dsl.option_some_v(True)],
                         dsl.finite_values({"option": "Bool"}, self.profile))
        expensive = {"tag": "list_foldl", "value": {"tag": "list", "element_sort": "Int", "items": [integer(1)] * 64},
                     "initial": integer(0), "function": {"accumulator_sort": "Int", "element_sort": "Int",
                         "body": {"tag": "int_add", "left": variable(0), "right": variable(1)}}}
        term = {"tag": "ite", "condition": {"tag": "bool", "value": True}, "then": integer(4), "else": expensive}
        dsl.type_term(term, [], self.profile)
        self.assertEqual(4, dsl.Evaluator(self.profile, {}, lambda *_: [], step_budget=4).term(term, []))
        term["condition"]["value"] = False
        with self.assertRaises(dsl.BudgetExceeded):
            dsl.Evaluator(self.profile, {}, lambda *_: [], step_budget=4).term(term, [])


def arithmetic_proposal():
    field = lambda n, i=0: {"tag": "field", "sort": "ArithmeticInput", "field": n, "value": variable(i)}
    body = {"tag": "list_map", "value": {"tag": "list_range", "stop": field("count")},
        "function": {"sort": "Nat", "body": {"tag": "int_fdiv", "left": {"tag": "int_add",
            "left": {"tag": "int_mul", "left": field("factor", 1),
                "right": {"tag": "nat_to_int", "value": variable(0)}}, "right": field("offset", 1)},
            "right": field("denominator", 1)}}}
    symbols = {"quotients": {"args": [{"record": "ArithmeticInput"}], "result": {"list": "Int"}, "body": body},
        "divide": {"args": ["Int", "Int"], "result": "Int", "body": {"tag": "int_fdiv", "left": variable(1), "right": variable(0)}},
        "clamp": {"args": ["Int"], "result": "Nat", "body": {"tag": "int_to_nat", "value": variable(0)}}}
    theorems = {}
    for name, row in symbols.items():
        formula = {"tag": "eq", "left": {"tag": "call", "symbol": name,
            "args": [variable(i) for i in reversed(range(len(row["args"]))) ]}, "right": row["body"]}
        for sort in reversed(row["args"]):
            formula = {"tag": "forall", "sort": sort, "body": formula}
        theorems[name + "Law"] = {"formula": formula}
    frozen = [{"id": "D1", "kind": "entity", "role": "declaration", "required": True}]
    obligations = {"D1": {"declarations": [{"kind": "record", "name": "ArithmeticInput"},
        *({"kind": "symbol", "name": name} for name in symbols)]}}
    for index, name in enumerate(symbols, 1):
        frozen.append({"id": f"O{index}", "kind": "postcondition", "role": "guarantee", "required": True})
        obligations[f"O{index}"] = {"theorem": name + "Law"}
    return {"encoding": ff.VERSION, "records": {"ArithmeticInput": {"fields": [
        {"name": "count", "sort": "Nat"}, {"name": "factor", "sort": "Int"},
        {"name": "offset", "sort": "Int"}, {"name": "denominator", "sort": "Int"}]}},
        "symbols": symbols, "predicates": {}, "theorems": theorems, "obligations": obligations,
        "witness_obligations": {}}, frozen


class ArithmeticKernelCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.tc = leanbridge.resolve_toolchain()
        proposal, frozen = arithmetic_proposal()
        cls.generated = ff.compile_response(canonical.dumps(proposal), frozen, "bootstrap.arithmetic")
        cls.compiled = leanbridge.compile_module(cls.tc,
            cls.generated.source.replace(b"by sorry", b"by intros; rfl"), Path(cls.tmp.name) / "arithmetic")
        if not cls.compiled.ok:
            raise AssertionError(cls.compiled.errors)
        exported = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        cls.env = contract.Env.from_export(exported, policy.get("strict"), "arithmetic")
        raw, _ = reify.derive_profile("bootstrap.arithmetic", cls.env.decls, cls.env.hashes,
            {"VeriSlopAST." + name for name in ["ArithmeticInput", *proposal["symbols"], *proposal["theorems"]]})
        cls.profile = dsl.Profile.from_json(raw)
        cls.formulas = {}
        for name in proposal["theorems"]:
            formula, why, _ = reify.reify_formula(cls.env.decls["VeriSlopAST." + name]["type"], cls.profile, cls.env.decls)
            if formula is None:
                raise AssertionError(why)
            cls.formulas[name] = formula

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_accepted_arithmetic_ast_denotes_exact_original_kernel_statements(self):
        requests = ff.kernel_audit_requests(self.generated)
        requests.extend({"id": name, "theorem": ["VeriSlopAST", name],
            "expr": reify.denote_formula(formula, self.profile)} for name, formula in self.formulas.items())
        for result in leanbridge.run_kernel_tool(self.tc, self.compiled.olean, {"defeq": requests})["defeq"]:
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, result["result"], result)

    def test_floor_division_signs_zero_and_large_values_match_kernel_reduction(self):
        cases = [(12, 7, 1), (12, -7, -2), (-12, 7, -2), (-12, -7, 1),
                 (0, -7, 0), (13, 0, 0), (-13, 0, 0), (10**30 + 7, 3, 333333333333333333333333333335)]
        body = self.formulas["divideLaw"]["body"]["body"]["right"]
        kernel_source = ["import Std"]
        for index, (a, b, expected) in enumerate(cases):
            self.assertEqual(expected, dsl.Evaluator(self.profile, {}, lambda *_: []).term(body, [b, a]))
            kernel_source.append(f"theorem boundary{index} : Int.fdiv ({a} : Int) ({b} : Int) = ({expected} : Int) := by decide")
        result = leanbridge.compile_module(self.tc, "\n".join(kernel_source).encode(), Path(self.tmp.name) / "boundary")
        self.assertTrue(result.ok, result.errors)

    def test_input_dependent_range_and_signed_map_are_reconstructed_and_executed(self):
        body = self.formulas["quotientsLaw"]["body"]["right"]
        inp = dsl.record_v("ArithmeticInput", [5, -3, -2, 2])
        self.assertEqual((-1, -3, -4, -6, -7), dsl.Evaluator(self.profile, {}, lambda *_: []).term(body, [inp]))
        empty = dsl.record_v("ArithmeticInput", [0, 10**30, -9, 0])
        self.assertEqual((), dsl.Evaluator(self.profile, {}, lambda *_: []).term(body, [empty]))
        self.assertEqual(tuple(range(500)), dsl.Evaluator(self.profile, {}, lambda *_: []).term(
            {"tag": "list_range", "stop": {"tag": "nat", "value": "500"}}, []))
        clamp = self.formulas["clampLaw"]["body"]["right"]
        for value, expected in [(-1, 0), (0, 0), (10**30, 10**30)]:
            self.assertEqual(expected, dsl.Evaluator(self.profile, {}, lambda *_: []).term(clamp, [value]))

    def test_wrong_division_semantics_are_detected_after_source_still_compiles(self):
        changed = self.generated.source.replace(b"_root_.Int.fdiv", b"_root_.Int.ediv")
        compiled = leanbridge.compile_module(self.tc, changed, Path(self.tmp.name) / "wrongdivision")
        self.assertTrue(compiled.ok, compiled.errors)
        results = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(self.generated)})["defeq"]
        self.assertFalse(next(x["result"]["defeq"] for x in results if x["id"] == "statement:divideLaw"))

    def test_range_rejects_bad_sort_and_exhausts_before_unbounded_allocation(self):
        for bad in [integer(2), {"tag": "bool", "value": True}]:
            with self.assertRaises(dsl.DSLError):
                dsl.type_term({"tag": "list_range", "stop": bad}, [], self.profile)
        huge = {"tag": "list_range", "stop": {"tag": "nat", "value": str(10**30)}}
        with self.assertRaises(dsl.BudgetExceeded):
            dsl.Evaluator(self.profile, {}, lambda *_: []).term(huge, [])
        small = {"tag": "list_range", "stop": {"tag": "nat", "value": "4"}}
        with self.assertRaises(dsl.BudgetExceeded):
            dsl.Evaluator(self.profile, {}, lambda *_: [], step_budget=5).term(small, [])


if __name__ == "__main__":
    unittest.main()
