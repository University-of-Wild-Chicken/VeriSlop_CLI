"""DSL0.2 data contracts are reconstructed from Lean and checked by the kernel."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import TempDir
from verislop import canonical, contract, dsl, leanbridge, policy, reify
from verislop.exprjson import name_str


SOURCE = '''import Std
namespace DataCore
structure NumericIn where
  values : List Int
  minimum : Int
  factor : Int
structure NumericOut where
  values : List Int
  total : Int
  count : Nat
def numericSolve (i : NumericIn) : NumericOut :=
  let ys := (i.values.filter fun x => decide (x ≥ i.minimum)).map (fun x => x * i.factor)
  {values := ys, total := ys.sum, count := ys.length}
theorem numeric_contract (i : NumericIn) : numericSolve i =
  {values := (i.values.filter fun x => decide (x ≥ i.minimum)).map (fun x => x * i.factor),
   total := ((i.values.filter fun x => decide (x ≥ i.minimum)).map (fun x => x * i.factor)).sum,
   count := ((i.values.filter fun x => decide (x ≥ i.minimum)).map (fun x => x * i.factor)).length} := rfl
theorem lambda_capture (i : NumericIn) (h : i.minimum ≤ 0) : (numericSolve i).values =
  (i.values.filter fun x => decide (x ≥ i.minimum)).map (fun x => x * i.factor) := rfl

structure Row where
  tag : String
  amount : Int
  enabled : Bool
structure RowOut where
  tag : String
  amount : Int
structure RowsIn where
  rows : List Row
  threshold : Int
structure RowsOut where
  rows : List RowOut
  total : Int
  count : Nat
def rowsSolve (i : RowsIn) : RowsOut :=
  let ys := (i.rows.filter fun r => r.enabled && decide (r.amount ≥ i.threshold)).map
    (fun r => ({tag := r.tag, amount := r.amount} : RowOut))
  {rows := ys, total := (ys.map fun r => r.amount).sum, count := ys.length}
theorem rows_contract (i : RowsIn) : rowsSolve i =
  {rows := (i.rows.filter fun r => r.enabled && decide (r.amount ≥ i.threshold)).map
      (fun r => ({tag := r.tag, amount := r.amount} : RowOut)),
   total := (((i.rows.filter fun r => r.enabled && decide (r.amount ≥ i.threshold)).map
      (fun r => ({tag := r.tag, amount := r.amount} : RowOut))).map fun r => r.amount).sum,
   count := ((i.rows.filter fun r => r.enabled && decide (r.amount ≥ i.threshold)).map
      (fun r => ({tag := r.tag, amount := r.amount} : RowOut))).length} := rfl

structure LabelsIn where
  labels : List String
  «prefix» : String
structure LabelsOut where
  labels : List String
  count : Nat
def labelsSolve (i : LabelsIn) : LabelsOut :=
  let ys := (i.labels.filter fun s => s != "").map (fun s => i.prefix ++ s)
  {labels := ys, count := ys.length}
theorem labels_contract (i : LabelsIn) : labelsSolve i =
  {labels := (i.labels.filter fun s => s != "").map (fun s => i.prefix ++ s),
   count := ((i.labels.filter fun s => s != "").map (fun s => i.prefix ++ s)).length} := rfl

theorem scalar_primitives (xs ys : List Int) (n : Int) :
  xs ++ ys = xs ++ ys ∧ xs.reverse = xs.reverse ∧ n - (-3) = n - (-3) ∧
  "λ🙂é" = "λ🙂é" ∧ ([-2, 0, 5] : List Int) = [-2, 0, 5] ∧
  decide (n < -1 ∧ n ≤ 2) = decide (n < -1 ∧ n ≤ 2) := by exact ⟨rfl,rfl,rfl,rfl,rfl,rfl⟩
theorem decisions (n : Int) (b : Bool) :
  decide True = decide True ∧ decide False = decide False ∧
  decide (¬ n < 0) = decide (¬ n < 0) ∧ decide (n < 0 ∨ n = 0) = decide (n < 0 ∨ n = 0) ∧
  decide (n < 0 → n ≤ 0) = decide (n < 0 → n ≤ 0) ∧
  decide (n < 0 ↔ n ≤ -1) = decide (n < 0 ↔ n ≤ -1) ∧
  decide (b = true) = decide (b = true) := by exact ⟨rfl,rfl,rfl,rfl,rfl,rfl,rfl⟩
theorem string_primitives (s : String) : s.length = s.length ∧ s.isEmpty = s.isEmpty := by exact ⟨rfl,rfl⟩
theorem unicode_examples : "λ🙂".length = 2 ∧ "é".length = 2 ∧ "é".length = 1 ∧
  "".isEmpty = true ∧ " ".isEmpty = false := by decide +kernel
end DataCore
'''


class DataContractKernelRoundtrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        cls.compiled = leanbridge.compile_module(cls.tc, SOURCE.encode(), cls.tmp.path / "data")
        if not cls.compiled.ok:
            raise AssertionError(cls.compiled.errors)
        cls.export = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        cls.env = contract.Env.from_export(cls.export, policy.get("strict"), "test")
        if cls.env.diagnostics:
            raise AssertionError(cls.env.diagnostics)
        cls.names = ["numeric_contract", "lambda_capture", "rows_contract", "labels_contract", "scalar_primitives", "decisions", "string_primitives", "unicode_examples"]
        cls.raw, cls.notes = reify.derive_profile("data-core.v0_2", cls.env.decls, cls.env.hashes,
                                                 {"DataCore." + n for n in cls.names})
        cls.profile = dsl.Profile.from_json(cls.raw)
        cls.formulas = {}
        requests = []
        for name in cls.names:
            row = cls.env.decls["DataCore." + name]
            formula, why, _ = reify.reify_formula(row["type"], cls.profile, cls.env.decls)
            if formula is None:
                raise AssertionError((name, why))
            cls.formulas[name] = formula
            requests.append({"id": name, "theorem": row["name"], "expr": reify.denote_formula(formula, cls.profile)})
        cls.checks = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"defeq": requests})["defeq"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_formula_roundtrips_to_its_actual_kernel_type(self):
        self.assertEqual(self.profile.encoding, dsl.ENCODING_V2)
        for result in self.checks:
            self.assertEqual(result["result"], {"ok": True, "typechecks": True, "defeq": True}, result)
        for formula in self.formulas.values():
            package = dsl.make_package(formula, self.profile.profile_id, encoding=self.profile.encoding)
            self.assertTrue(dsl.round_trip_ok(package, self.profile))

    def test_record_registry_binds_field_order_shapes_and_declarations(self):
        self.assertEqual(set(self.profile.symbols), {"numericSolve", "rowsSolve", "labelsSolve"})
        r = self.profile.records["NumericIn"]
        self.assertEqual([f["name"] for f in r["fields"]], ["values", "minimum", "factor"])
        self.assertEqual([f["sort"] for f in r["fields"]], [{"list": "Int"}, "Int", "Int"])
        for r in self.profile.records.values():
            self.assertEqual(r["decl_hash"], self.env.hashes[r["lean_decl"]])
            self.assertEqual(r["constructor_hash"], self.env.hashes[r["lean_constructor"]])
            for f in r["fields"]:
                self.assertEqual(f["projection_hash"], self.env.hashes[f["lean_projection"]])

    def expected(self, name, value):
        body = self.formulas[name]["body"]
        self.assertEqual(body["tag"], "eq")
        self.assertEqual(dsl.calls(body["right"]), set())
        return dsl.Evaluator(self.profile, {}, lambda b, e: []).term(body["right"], [value])

    def test_numeric_builtins_preserve_negative_values_duplicates_and_order(self):
        value = dsl.record_v("NumericIn", [(-7, -2, -2, 0, 3), -2, -3])
        self.assertEqual(self.expected("numeric_contract", value), dsl.record_v("NumericOut", [(6, 6, 0, -9), 3, 4]))
        self.assertEqual(self.expected("numeric_contract", dsl.record_v("NumericIn", [(), -10, -1])),
                         dsl.record_v("NumericOut", [(), 0, 0]))

    def test_nested_rows_preserve_unicode_tags_and_order(self):
        rows = (dsl.record_v("Row", ["🙂", -1, True]), dsl.record_v("Row", ["λ", 4, False]),
                dsl.record_v("Row", ["🙂", -1, True]), dsl.record_v("Row", ["é", 2, True]))
        result = self.expected("rows_contract", dsl.record_v("RowsIn", [rows, -1]))
        wanted = (dsl.record_v("RowOut", ["🙂", -1]), dsl.record_v("RowOut", ["🙂", -1]),
                  dsl.record_v("RowOut", ["é", 2]))
        self.assertEqual(result, dsl.record_v("RowsOut", [wanted, 0, 3]))

    def test_unicode_prefix_filter_treats_only_empty_string_as_empty(self):
        labels = ("", "λ", " ", "🙂", "λ", "é", "é", "\x00")
        wanted = tuple("✓" + x for x in labels if x != "")
        self.assertEqual(self.expected("labels_contract", dsl.record_v("LabelsIn", [labels, "✓"])),
                         dsl.record_v("LabelsOut", [wanted, len(wanted)]))

    def test_unicode_scalar_length_and_empty_are_fixed_string_primitives(self):
        ev = dsl.Evaluator(self.profile, {}, lambda b, e: [])
        for value in ("", "🙂", "λ🙂", "é", "é", "\x00", " "):
            with self.subTest(value=value):
                term = {"tag": "string", "value": value}
                self.assertEqual(ev.term({"tag": "string_length", "value": term}, []), len(value))
                self.assertEqual(ev.term({"tag": "string_is_empty", "value": term}, []), value == "")
        self.assertEqual(ev.formula(self.formulas["unicode_examples"], []), dsl.T_EXACT)

    def test_wrong_projection_record_order_and_lambda_capture_are_rejected(self):
        bad = [
            {"tag": "field", "sort": "NumericOut", "field": "total", "value": {"tag": "var", "index": 0}},
            {"tag": "record", "sort": "NumericIn", "fields": [{"tag": "int", "value": "0"}]},
            {"tag": "list_map", "value": {"tag": "list", "element_sort": "Int", "items": []},
             "function": {"sort": "Int", "body": {"tag": "var", "index": 1}}},
            {"tag": "list_filter", "value": {"tag": "list", "element_sort": "Int", "items": []},
             "function": {"sort": "Int", "body": {"tag": "int", "value": "0"}}},
        ]
        for term in bad:
            with self.subTest(term=term), self.assertRaises(dsl.DSLError):
                dsl.type_term(term, [{"record": "NumericIn"}] if term["tag"] == "field" else [], self.profile)
        self.assertFalse(dsl.value_has_sort(dsl.record_v("NumericIn", [-2, (), 3]), {"record": "NumericIn"}, self.profile))

    def test_changed_projection_is_not_registered_as_a_record(self):
        decls = copy.deepcopy(self.env.decls)
        decls["DataCore.NumericIn.minimum"]["value"]["lam"]["body"]["proj"]["idx"] = 2
        raw, _ = reify.derive_profile("bad-record.v0_2", decls, self.env.hashes, {"DataCore.numeric_contract"})
        self.assertNotIn("NumericIn", raw.get("records", {}))

    def test_custom_arithmetic_instance_fails_fixed_semantics_denotation(self):
        source = '''import Std
namespace CustomArithmetic
def different : HAdd Int Int Int where hAdd := fun a b => a - b
theorem bad (x : Int) : @HAdd.hAdd Int Int Int different x 1 = @HAdd.hAdd Int Int Int different x 1 := rfl
end CustomArithmetic
'''
        c = leanbridge.compile_module(self.tc, source.encode(), self.tmp.path / "custom-instance")
        self.assertTrue(c.ok, c.errors)
        env = contract.Env.from_export(leanbridge.run_kernel_tool(self.tc, c.olean, {"export": True, "axioms": True}),
                                       policy.get("strict"), "custom")
        raw, _ = reify.derive_profile("custom.v0_2", env.decls, env.hashes, {"CustomArithmetic.bad"})
        prof = dsl.Profile.from_json(raw)
        row = env.decls["CustomArithmetic.bad"]
        formula, why, _ = reify.reify_formula(row["type"], prof, env.decls)
        self.assertIsNotNone(formula, why)
        result = leanbridge.run_kernel_tool(self.tc, c.olean, {"defeq": [{"id": "bad", "theorem": row["name"],
                     "expr": reify.denote_formula(formula, prof)}]})["defeq"][0]["result"]
        self.assertTrue(result["typechecks"], result)
        self.assertFalse(result["defeq"], result)

    def test_polymorphic_recursive_dependent_and_proof_records_are_not_admitted(self):
        source = '''import Std
namespace WrongRecord
structure Poly (α : Type) where value : α
structure Dependent where
  n : Nat
  payload : Fin n
structure ProofField where
  value : Int
  witness : True
inductive Recursive where
  | node : List Recursive → Recursive
theorem p (x : Poly Int) : x = x := rfl
theorem d (x : Dependent) : x = x := rfl
theorem f (x : ProofField) : x = x := rfl
theorem r (x : Recursive) : x = x := rfl
end WrongRecord
'''
        c = leanbridge.compile_module(self.tc, source.encode(), self.tmp.path / "wrong-records")
        self.assertTrue(c.ok, c.errors)
        env = contract.Env.from_export(leanbridge.run_kernel_tool(self.tc, c.olean, {"export": True, "axioms": True}),
                                       policy.get("strict"), "records")
        raw, _ = reify.derive_profile("wrong.v0_2", env.decls, env.hashes, {"WrongRecord." + n for n in ("p", "d", "f", "r")})
        self.assertEqual(raw.get("records", {}), {})
        prof = dsl.Profile.from_json(raw)
        for n in ("p", "d", "f", "r"):
            formula, _, _ = reify.reify_formula(env.decls["WrongRecord." + n]["type"], prof, env.decls)
            self.assertIsNone(formula, n)

    def test_custom_order_and_boolean_equality_cannot_change_builtin_meaning(self):
        source = '''import Std
namespace CustomPrimitives
def differentOrder : LE Int where le := fun _ _ => True
def differentEquality : BEq String where beq := fun _ _ => true
theorem order (x : Int) : @LE.le Int differentOrder x 0 → @LE.le Int differentOrder x 0 := by intro h; exact h
theorem equality (s : String) : @BEq.beq String differentEquality s "" = true := rfl
end CustomPrimitives
'''
        c = leanbridge.compile_module(self.tc, source.encode(), self.tmp.path / "custom-primitives")
        self.assertTrue(c.ok, c.errors)
        env = contract.Env.from_export(leanbridge.run_kernel_tool(self.tc, c.olean, {"export": True, "axioms": True}),
                                       policy.get("strict"), "custom-primitives")
        raw, _ = reify.derive_profile("custom-primitives.v0_2", env.decls, env.hashes,
                                      {"CustomPrimitives.order", "CustomPrimitives.equality"})
        prof = dsl.Profile.from_json(raw)
        requests = []
        for n in ("order", "equality"):
            row = env.decls["CustomPrimitives." + n]
            formula, why, _ = reify.reify_formula(row["type"], prof, env.decls)
            self.assertIsNotNone(formula, why)
            requests.append({"id": n, "theorem": row["name"], "expr": reify.denote_formula(formula, prof)})
        results = leanbridge.run_kernel_tool(self.tc, c.olean, {"defeq": requests})["defeq"]
        for row in results:
            self.assertTrue(row["result"]["typechecks"], row)
            self.assertFalse(row["result"]["defeq"], row)

    def test_v2_primitives_without_extended_symbol_sorts_select_v2(self):
        source = '''import Std
namespace NatData
def f (n : Nat) : Nat := n + 2
theorem p (n : Nat) : f n = n + ([3, 4] : List Nat).length := rfl
end NatData
'''
        c = leanbridge.compile_module(self.tc, source.encode(), self.tmp.path / "nat-list-literals")
        self.assertTrue(c.ok, c.errors)
        env = contract.Env.from_export(leanbridge.run_kernel_tool(self.tc, c.olean, {"export": True, "axioms": True}),
                                       policy.get("strict"), "nat-data")
        raw, _ = reify.derive_profile("nat-data.v0_2", env.decls, env.hashes, {"NatData.p"})
        prof = dsl.Profile.from_json(raw)
        self.assertEqual(prof.encoding, dsl.ENCODING_V2)
        self.assertEqual(prof.symbols["f"]["args"], ["Nat"])
        formula, why, _ = reify.reify_formula(env.decls["NatData.p"]["type"], prof, env.decls)
        self.assertIsNotNone(formula, why)
        result = leanbridge.run_kernel_tool(self.tc, c.olean, {"defeq": [{"id": "p", "theorem": env.decls["NatData.p"]["name"],
                            "expr": reify.denote_formula(formula, prof)}]})["defeq"][0]["result"]
        self.assertEqual(result, {"ok": True, "typechecks": True, "defeq": True})


class DataContractTyping(unittest.TestCase):
    def setUp(self):
        self.profile = dsl.Profile.from_json({"profile_id": "types.v0_2", "dsl": dsl.ENCODING_V2,
                                            "enums": {}, "records": {}, "symbols": {}, "predicates": {}})

    def test_legacy_encoding_rejects_every_new_sort_or_tag(self):
        for f in (
            {"tag": "forall", "sort": "Int", "body": {"tag": "true"}},
            {"tag": "eq", "left": {"tag": "int", "value": "0"}, "right": {"tag": "int", "value": "0"}},
            {"tag": "eq", "left": {"tag": "list_length", "value": {"tag": "list", "element_sort": "Nat", "items": []}},
             "right": {"tag": "nat", "value": "0"}},
        ):
            with self.subTest(formula=f), self.assertRaises(dsl.DSLError):
                dsl.check_package(dsl.make_package(f, self.profile.profile_id), self.profile)
        f = {"tag": "forall", "sort": "Nat", "body": {"tag": "eq", "left": {"tag": "var", "index": 0},
                                                                        "right": {"tag": "var", "index": 0}}}
        self.assertTrue(dsl.round_trip_ok(dsl.make_package(f, self.profile.profile_id), self.profile))

    def test_signed_literals_unicode_and_scalar_value_shapes_are_strict(self):
        for v in ("-0", "+1", "01", "-01", " 1", "1.0", True):
            with self.subTest(value=v), self.assertRaises(dsl.DSLError):
                dsl.type_term({"tag": "int", "value": v}, [], self.profile)
        with self.assertRaises(dsl.DSLError):
            dsl.type_term({"tag": "string", "value": "\ud800"}, [], self.profile)
        self.assertFalse(dsl.value_has_sort(True, "Int", self.profile))
        self.assertFalse(dsl.value_has_sort("\udfff", "String", self.profile))
        self.assertTrue(dsl.value_has_sort(-10 ** 100, "Int", self.profile))

    def test_infinite_domain_exhaustion_is_unknown_and_counterexamples_are_exact(self):
        ev = dsl.Evaluator(self.profile, {}, lambda b, e: [0, 1, 2])
        self.assertEqual(ev.formula({"tag": "forall", "sort": "Int", "body": {"tag": "true"}}, []), dsl.UNKNOWN)
        self.assertEqual(ev.formula({"tag": "forall", "sort": "String", "body": {"tag": "false"}}, []), dsl.F_EXACT)
        self.assertEqual(ev.formula({"tag": "exists", "sort": {"list": "Int"}, "body": {"tag": "false"}}, []), dsl.UNKNOWN)

    def test_decide_cannot_hide_infinite_quantification(self):
        with self.assertRaises(dsl.DSLError):
            dsl.type_term({"tag": "decide", "formula": {"tag": "forall", "sort": "Int", "body": {"tag": "true"}}},
                          [], self.profile)

    def test_finite_outer_quantifiers_do_not_promote_approximate_inner_results(self):
        legacy = dsl.Profile.from_json({"profile_id": "legacy", "symbols": {}, "predicates": {}, "enums": {}})
        inner = {"tag": "forall", "sort": "Nat", "body": {"tag": "true"}}
        for profile in (legacy, self.profile):
            for tag, body in (("exists", {"tag": "not", "body": inner}), ("forall", inner)):
                with self.subTest(profile=profile.encoding, tag=tag):
                    ev = dsl.Evaluator(profile, {}, lambda b, e: [0, 1, 2])
                    self.assertEqual(ev.formula({"tag": tag, "sort": "Bool", "body": body}, []), dsl.UNKNOWN)
        ev = dsl.Evaluator(legacy, {}, lambda b, e: [0, 1, 2])
        self.assertEqual(ev.formula(inner, []), dsl.Truth(True, False))

    def test_recursive_records_and_huge_finite_record_products_fail_closed(self):
        raw = {"profile_id": "records.v0_2", "dsl": dsl.ENCODING_V2, "enums": {}, "symbols": {}, "predicates": {},
               "records": {"R": {"fields": [{"name": "xs", "sort": {"list": {"record": "R"}}}]}}}
        with self.assertRaises(dsl.DSLError):
            dsl.Profile.from_json(raw)
        raw["records"]["R"]["fields"] = [{"name": f"b{i}", "sort": "Bool"} for i in range(64)]
        profile = dsl.Profile.from_json(raw)
        with self.assertRaises(dsl.BudgetExceeded):
            dsl.finite_values({"record": "R"}, profile)


if __name__ == "__main__":
    unittest.main()
