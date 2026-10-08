"""Fixed Nat→Int and ordered typed fold primitives roundtrip through real Lean."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir
from verislop import canonical, contract, dsl, fsutil, leanbridge, policy, reify, testing


SOURCE = '''import Std
namespace CastFold
structure Input where
  values : List Int
structure IntCount where
  count : Int
structure NatCount where
  count : Nat
def intCount (i : Input) : IntCount := {count := i.values.length}
def natCount (i : Input) : NatCount := {count := i.values.length}
theorem int_count (i : Input) : intCount i = {count := i.values.length} := rfl
theorem nat_count (i : Input) : natCount i = {count := i.values.length} := rfl
theorem explicit_cast (xs : List Int) : Int.ofNat xs.length = (xs.length : Int) := rfl
theorem abstract_cast (n : Nat) : Int.ofNat n = (n : Int) := rfl

def foldSum (xs : List Int) : Int := xs.foldl (fun acc x => acc + x) 0
theorem fold_sum (xs : List Int) : foldSum xs = xs.foldl (fun acc x => acc + x) 0 := rfl
structure Row where
  tag : String
  amount : Int
structure RowsInput where
  rows : List Row
  factor : Int
  start : Int
def foldRows (i : RowsInput) : Int := i.rows.foldl (fun acc row => acc + row.amount * i.factor) i.start
theorem fold_rows (i : RowsInput) : foldRows i =
  i.rows.foldl (fun acc row => acc + row.amount * i.factor) i.start := rfl
theorem fold_hypothesis (i : RowsInput) (h : i.factor ≤ 0) : foldRows i =
  i.rows.foldl (fun acc row => acc + row.amount * i.factor) i.start := rfl
structure Aggregate where
  total : Int
  count : Nat
def aggregate (i : RowsInput) : Aggregate := i.rows.foldl
  (fun acc row => {total := acc.total + row.amount * i.factor, count := acc.count + 1})
  {total := i.start, count := 0}
theorem aggregate_rows (i : RowsInput) : aggregate i = i.rows.foldl
  (fun acc row => {total := acc.total + row.amount * i.factor, count := acc.count + 1})
  {total := i.start, count := 0} := rfl
def concatLabels (xs : List String) : String := xs.foldl (fun acc x => acc ++ x) "→"
theorem concat_labels (xs : List String) : concatLabels xs = xs.foldl (fun acc x => acc ++ x) "→" := rfl
def collect (xs : List Int) : List Int := xs.foldl (fun acc x => acc ++ [x]) []
theorem collect_values (xs : List Int) : collect xs = xs.foldl (fun acc x => acc ++ [x]) [] := rfl

def unusual : NatCast Int where natCast := fun n => -(Int.ofNat n)
theorem custom_cast (xs : List Int) :
  @Nat.cast Int unusual xs.length = @Nat.cast Int unusual xs.length := rfl
def faithful : NatCast Int where natCast := Int.ofNat
theorem faithful_cast (xs : List Int) :
  @Nat.cast Int faithful xs.length = @Nat.cast Int faithful xs.length := rfl

def combine (acc x : Int) : Int := acc + x
theorem foreign_function (xs : List Int) : xs.foldl combine 0 = xs.foldl combine 0 := rfl
end CastFold
'''


class CastFoldKernelRoundtrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        cls.compiled = leanbridge.compile_module(cls.tc, SOURCE.encode(), cls.tmp.path / "casts-folds")
        if not cls.compiled.ok:
            raise AssertionError(cls.compiled.errors)
        exported = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        cls.env = contract.Env.from_export(exported, policy.get("strict"), "test")
        if cls.env.diagnostics:
            raise AssertionError(cls.env.diagnostics)
        cls.names = ["int_count", "nat_count", "explicit_cast", "abstract_cast", "fold_sum", "fold_rows",
                     "fold_hypothesis", "aggregate_rows", "concat_labels", "collect_values", "custom_cast", "faithful_cast"]
        raw, _ = reify.derive_profile("casts-folds.v0_2", cls.env.decls, cls.env.hashes,
                                     {"CastFold." + name for name in cls.names + ["foreign_function"]})
        cls.profile = dsl.Profile.from_json(raw)
        cls.formulas = {}
        requests = []
        for name in cls.names:
            row = cls.env.decls["CastFold." + name]
            formula, why, _ = reify.reify_formula(row["type"], cls.profile, cls.env.decls)
            if formula is None:
                raise AssertionError((name, why))
            cls.formulas[name] = formula
            requests.append({"id": name, "theorem": row["name"], "expr": reify.denote_formula(formula, cls.profile)})
        results = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"defeq": requests})["defeq"]
        cls.checks = {result["id"]: result["result"] for result in results}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def expected(self, name, *args):
        body = self.formulas[name]
        while body["tag"] == "forall":
            body = body["body"]
        if body["tag"] == "implies":
            body = body["right"]
        self.assertEqual("eq", body["tag"])
        self.assertEqual(set(), dsl.calls(body["right"]))
        return dsl.Evaluator(self.profile, {}, lambda *_: []).term(body["right"], list(reversed(args)))

    def test_standard_casts_and_typed_folds_have_exact_kernel_denotations(self):
        for name, result in self.checks.items():
            if name == "custom_cast":
                continue
            with self.subTest(theorem=name):
                self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, result)
                pkg = dsl.make_package(self.formulas[name], self.profile.profile_id, encoding=dsl.ENCODING_V2)
                self.assertTrue(dsl.round_trip_ok(pkg, self.profile))

    def test_custom_natcast_cannot_change_the_registered_conversion_semantics(self):
        # Reification proposes the fixed primitive; kernel defeq is the mandatory guard.
        # A negating instance is rejected, while a definitionally faithful alias passes.
        self.assertEqual({"ok": True, "typechecks": True, "defeq": False}, self.checks["custom_cast"])
        self.assertTrue(self.checks["faithful_cast"]["defeq"])

    def test_dynamic_int_and_nat_count_apis_keep_their_actual_field_sorts(self):
        int_rhs = self.formulas["int_count"]["body"]["right"]["fields"][0]
        nat_rhs = self.formulas["nat_count"]["body"]["right"]["fields"][0]
        self.assertEqual("nat_to_int", int_rhs["tag"])
        self.assertEqual(nat_rhs, int_rhs["value"])
        self.assertEqual("Int", self.profile.records["IntCount"]["fields"][0]["sort"])
        self.assertEqual("Nat", self.profile.records["NatCount"]["fields"][0]["sort"])
        for values in ((), (-7, -7, 0, 2), tuple(range(100))):
            inp = dsl.record_v("Input", [values])
            self.assertEqual(dsl.record_v("IntCount", [len(values)]), self.expected("int_count", inp))
            self.assertEqual(dsl.record_v("NatCount", [len(values)]), self.expected("nat_count", inp))

    def test_dynamic_conversion_is_arbitrary_precision_and_not_host_coercion(self):
        for value in (0, 1, 2**256 + 7):
            self.assertEqual(value, self.expected("abstract_cast", value))
        for values in ((), (-3, -3, 9)):
            self.assertEqual(len(values), self.expected("explicit_cast", values))

    def test_int_fold_preserves_negative_arithmetic_and_empty_identity(self):
        for values in ((), (-8, -8, 3), (2**180, -(2**180), -1)):
            self.assertEqual(sum(values), self.expected("fold_sum", values))

    def test_record_elements_and_outer_multiplier_are_correctly_bound(self):
        rows = (dsl.record_v("Row", ["🙂", -3]), dsl.record_v("Row", ["λ", 2]),
                dsl.record_v("Row", ["🙂", -3]))
        inp = dsl.record_v("RowsInput", [rows, -4, 11])
        wanted = 11 + (-3 + 2 - 3) * -4
        self.assertEqual(wanted, self.expected("fold_rows", inp))
        self.assertEqual(wanted, self.expected("fold_hypothesis", inp))
        empty = dsl.record_v("RowsInput", [(), -5, -17])
        self.assertEqual(-17, self.expected("fold_rows", empty))
        fn = self.formulas["fold_rows"]["body"]["right"]["function"]
        self.assertEqual("Int", fn["accumulator_sort"])
        self.assertEqual({"record": "Row"}, fn["element_sort"])
        self.assertEqual(1, fn["body"]["left"]["index"])
        self.assertEqual(0, fn["body"]["right"]["left"]["value"]["index"])
        self.assertEqual(2, fn["body"]["right"]["right"]["value"]["index"])

    def test_generic_record_accumulator_does_not_assume_numeric_zero(self):
        rows = (dsl.record_v("Row", ["é", -2]), dsl.record_v("Row", ["é", -2]))
        self.assertEqual(dsl.record_v("Aggregate", [19, 2]),
                         self.expected("aggregate_rows", dsl.record_v("RowsInput", [rows, -3, 7])))
        self.assertEqual(dsl.record_v("Aggregate", [-7, 0]),
                         self.expected("aggregate_rows", dsl.record_v("RowsInput", [(), 9, -7])))

    def test_ordered_string_and_list_accumulators_preserve_unicode_duplicates(self):
        self.assertEqual("→λ🙂λé", self.expected("concat_labels", ("λ", "🙂", "λ", "é")))
        self.assertEqual("→", self.expected("concat_labels", ()))
        values = (-2, 7, -2, 0)
        self.assertEqual(values, self.expected("collect_values", values))
        self.assertEqual((), self.expected("collect_values", ()))

    def test_real_python_campaigns_compare_both_count_apis_and_fold_against_reified_primitives(self):
        implementation = self.tmp.path / "python-campaigns"
        source = ('def intCount(data):\n    return {"count": len(data["values"])}\n'
                  'def natCount(data):\n    return {"count": len(data["values"])}\n'
                  'def foldRows(data):\n'
                  '    return data["start"] + sum(row["amount"] * data["factor"] for row in data["rows"])\n')
        fsutil.atomic_write(implementation / "pipeline.py", source.encode())
        bindings = [{"symbol": symbol, "implementation_object": {"file": "pipeline.py", "qualname": symbol}}
                    for symbol in ("intCount", "natCount", "foldRows")]
        cfg = testing.campaign_config(17, 32, 5000, self.profile)

        def execute(name):
            package = dsl.make_package(self.formulas[name], self.profile.profile_id, encoding=dsl.ENCODING_V2)
            payload = canonical.dumps(package)
            digest = canonical.digest(payload)
            expressions = self.tmp.path / "campaign-expressions"
            fsutil.atomic_write(expressions / (digest[7:] + ".json"), payload)
            claims = {"claims": [{"milestone": "TESTED", "obligation": "O1", "applicable": True}]}
            ir = {"obligations": {"O1": {"kind": "postcondition", "formal": {
                "representation": "contract_dsl", "formula_ref": "artifact:formula@" + digest}}}}
            return testing.execute(implementation, {"bindings": bindings}, claims, ir, self.profile,
                                   cfg, expressions, {})["obligations"]["O1"]

        for name in ("int_count", "nat_count", "fold_rows"):
            with self.subTest(contract=name):
                result = execute(name)
                self.assertEqual("PASS", result["outcome"], result)
                self.assertEqual(32, result["detail"]["counts"]["effective"])
        fsutil.atomic_write(implementation / "pipeline.py", source.replace('return data["start"] + sum(',
                                                                          'return 1 + data["start"] + sum(').encode())
        mutant = execute("fold_rows")
        self.assertEqual("FAIL", mutant["outcome"], mutant)
        self.assertTrue(mutant["detail"]["counterexamples"])

    def test_arbitrary_function_arguments_are_not_admitted_as_fold_lambdas(self):
        row = self.env.decls["CastFold.foreign_function"]
        formula, why, _ = reify.reify_formula(row["type"], self.profile, self.env.decls)
        self.assertIsNone(formula)
        self.assertIn("explicit typed two-binder lambda", why)


class CastFoldTypingTests(unittest.TestCase):
    def setUp(self):
        self.profile = dsl.Profile.from_json({"profile_id": "primitives.v0_2", "dsl": dsl.ENCODING_V2,
                                             "enums": {}, "records": {}, "symbols": {}, "predicates": {}})
        self.fold = {"tag": "list_foldl", "value": {"tag": "var", "index": 0},
                     "initial": {"tag": "int", "value": "-2"}, "function": {
                         "accumulator_sort": "Int", "element_sort": "Nat", "body": {
                             "tag": "int_add", "left": {"tag": "var", "index": 1},
                             "right": {"tag": "nat_to_int", "value": {"tag": "var", "index": 0}}}}}

    def test_conversion_requires_a_nat_operand_and_exact_node_shape(self):
        self.assertEqual("Int", dsl.type_term({"tag": "nat_to_int", "value": {"tag": "nat", "value": "3"}}, [], self.profile))
        invalid = [{"tag": "int", "value": "3"}, {"tag": "bool", "value": True},
                   {"tag": "string", "value": "3"}, {"tag": "nat", "value": 3},
                   {"tag": "nat", "value": "-1"}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(dsl.DSLError):
                dsl.type_term({"tag": "nat_to_int", "value": value}, [], self.profile)
        with self.assertRaises(dsl.DSLError):
            dsl.type_term({"tag": "nat_to_int", "value": {"tag": "nat", "value": "0"}, "instance": "custom"}, [], self.profile)

    def test_fold_type_and_debruijn_context_are_closed_and_ordered(self):
        self.assertEqual("Int", dsl.type_term(self.fold, [{"list": "Nat"}], self.profile))
        self.assertEqual(8, dsl.Evaluator(self.profile, {}, lambda *_: []).term(self.fold, [(1, 2, 7)]))
        self.assertIn("fun x1 x2 =>", dsl.render({"tag": "eq", "left": self.fold, "right": self.fold}, ["xs"]))
        bad = []
        for key, value in (("accumulator_sort", "Nat"), ("element_sort", "Int"),
                           ("body", {"tag": "bool", "value": True}), ("body", {"tag": "var", "index": 3})):
            t = copy.deepcopy(self.fold)
            t["function"][key] = value
            bad.append(t)
        bad.append({**self.fold, "value": {"tag": "int", "value": "0"}})
        bad.append({**self.fold, "function": {**self.fold["function"], "extra": 0}})
        for term in bad:
            with self.subTest(term=term), self.assertRaises(dsl.DSLError):
                dsl.type_term(term, [{"list": "Nat"}], self.profile)

    def test_fold_evaluation_is_resource_bounded(self):
        with self.assertRaises(dsl.BudgetExceeded):
            dsl.Evaluator(self.profile, {}, lambda *_: [], step_budget=10).term(self.fold, [tuple(range(100))])

    def test_legacy_encoding_cannot_smuggle_either_new_primitive(self):
        old = dsl.Profile.from_json({"profile_id": "old", "enums": {}, "symbols": {}, "predicates": {}})
        for term in ({"tag": "nat_to_int", "value": {"tag": "nat", "value": "0"}}, self.fold):
            with self.subTest(tag=term["tag"]), self.assertRaises(dsl.DSLError):
                dsl.type_term(term, [{"list": "Nat"}], old)
        formula = {"tag": "eq", "left": {"tag": "nat_to_int", "value": {"tag": "nat", "value": "0"}},
                   "right": {"tag": "int", "value": "0"}}
        with self.assertRaises(dsl.DSLError):
            dsl.check_package(dsl.make_package(formula, self.profile.profile_id, encoding=dsl.ENCODING), self.profile)


if __name__ == "__main__":
    unittest.main()
