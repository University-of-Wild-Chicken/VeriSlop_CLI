"""Generic nominal enum equality; synthetic typing checks have no acceptance authority."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verislop import canonical, contract, contract_refutation, dsl, leanbridge, policy, reify, schemas
from verislop.exprjson import app, const, decl_hash, name_str, parse_name
from verislop.targets import vscore3_target


def enum_term(eid, constructor):
    return {"tag": "enum", "sort": eid, "constructor": constructor}


def equality(left, right):
    return {"tag": "eq", "left": left, "right": right}


def pure_profile(*, candidate=False, binding=True):
    enums = {}
    for eid, ctors in (("Alpha", ["first", "second"]), ("Beta", ["first", "second", "third"])):
        row = {"constructors": ctors, "lean_decl": "Generic." + eid,
               "lean_constructors": ["Generic." + eid + "." + c for c in ctors]}
        if binding:
            row["candidate_decidable_eq" if candidate else "decidable_eq"] = {
                "lean_decl": "Generic.instDecidableEq" + eid}
            if not candidate:
                row["decidable_eq"]["decl_hash"] = canonical.digest(b"synthetic declaration identity")
        enums[eid] = row
    return {"profile_id": "generic-enum-equality", "dsl": dsl.ENCODING_V2,
            "enums": enums, "records": {}, "symbols": {}, "predicates": {}}


class EnumEqualityTypingTests(unittest.TestCase):
    def test_same_nominal_enum_pairs_and_decisions(self):
        p = dsl.Profile.from_json(pure_profile())
        evaluator = dsl.Evaluator(p, {}, lambda *_: [])
        for eid, row in p.enums.items():
            for left in row["constructors"]:
                for right in row["constructors"]:
                    a, b = enum_term(eid, left), enum_term(eid, right)
                    for term in ({"tag": "bool_eq", "left": a, "right": b},
                                 {"tag": "decide", "formula": equality(a, b)}):
                        with self.subTest(eid=eid, left=left, right=right, term=term["tag"]):
                            self.assertEqual("Bool", dsl.type_term(term, [], p))
                            self.assertEqual(left == right, evaluator.term(term, []))

    def test_equal_wire_labels_of_different_nominal_enums_are_not_equal_sorts(self):
        p = dsl.Profile.from_json(pure_profile())
        a, b = enum_term("Alpha", "first"), enum_term("Beta", "first")
        for term in ({"tag": "bool_eq", "left": a, "right": b},
                     {"tag": "decide", "formula": equality(a, b)}):
            with self.assertRaisesRegex(dsl.DSLError, "equal.*sorts"):
                dsl.type_term(term, [], p)

    def test_legacy_carrier_and_proposition_equality_survive_without_dispatch(self):
        p = dsl.Profile.from_json(pure_profile(binding=False))
        a, b = enum_term("Alpha", "first"), enum_term("Alpha", "second")
        dsl.type_formula(equality(a, b), [], p)
        self.assertEqual([dsl.enum_v("Alpha", "first"), dsl.enum_v("Alpha", "second")],
                         dsl.finite_values({"enum": "Alpha"}, p))
        for term in ({"tag": "bool_eq", "left": a, "right": b},
                     {"tag": "decide", "formula": equality(a, b)}):
            with self.assertRaisesRegex(dsl.DSLError, "no bound computable DecidableEq"):
                dsl.type_term(term, [], p)
        with self.assertRaisesRegex(dsl.DSLError, "no bound computable DecidableEq"):
            reify._Denoter(p).equality_instance({"enum": "Alpha"})

    def test_candidate_metadata_requires_explicit_internal_opt_in(self):
        raw = pure_profile(candidate=True)
        with self.assertRaisesRegex(dsl.DSLError, "candidate-only metadata"):
            dsl.Profile.from_json(raw)
        p = dsl.Profile.from_json(raw, allow_candidate_enum_equality=True)
        self.assertEqual(const("Generic.instDecidableEqAlpha"),
                         reify._Denoter(p).equality_instance({"enum": "Alpha"}))
        with self.assertRaisesRegex(reify.Unsupported, "candidate equality metadata"):
            reify.validate_enum_equality_binding(p, "Alpha", {})
        raw["enums"]["Alpha"]["decidable_eq"] = {"lean_decl": "Generic.elsewhere", "decl_hash": canonical.digest(b"x")}
        with self.assertRaisesRegex(dsl.DSLError, "forbidden candidate"):
            dsl.Profile.from_json(raw, allow_candidate_enum_equality=True)

    def test_malformed_metadata_has_structured_rejections(self):
        for bad in (None, [], {}, {"lean_decl": "Generic.eq"},
                    {"lean_decl": "Generic.eq", "decl_hash": "stale"},
                    {"lean_decl": "", "decl_hash": canonical.digest(b"x")},
                    {"lean_decl": "Generic.eq", "decl_hash": canonical.digest(b"x"), "body": "trusted"}):
            raw = pure_profile()
            raw["enums"]["Alpha"]["decidable_eq"] = bad
            with self.subTest(metadata=bad), self.assertRaises(dsl.DSLError):
                dsl.Profile.from_json(raw)

    def test_new_metadata_is_closed_in_accepted_vscore3_profile_schema(self):
        raw = pure_profile()
        descriptor = vscore3_target.profile_descriptor(raw, canonical.digest_json(raw))
        self.assertEqual([], schemas.validate("vscore-profile-v3", descriptor))
        for bad in ({"lean_decl": "Generic.eq"}, {"lean_decl": "Generic.eq", "decl_hash": "stale"}):
            changed = copy.deepcopy(descriptor)
            changed["enums"]["Alpha"]["decidable_eq"] = bad
            self.assertTrue(schemas.validate("vscore-profile-v3", changed))
        changed = copy.deepcopy(descriptor)
        changed["enums"]["Alpha"]["candidate_decidable_eq"] = {"lean_decl": "Generic.eq"}
        self.assertTrue(schemas.validate("vscore-profile-v3", changed))

    def test_enum_order_aggregate_equality_and_deduplication_remain_outside_scope(self):
        p = dsl.Profile.from_json(pure_profile())
        a, b = enum_term("Alpha", "first"), enum_term("Alpha", "second")
        values = {"tag": "list", "element_sort": {"enum": "Alpha"}, "items": [a, b]}
        for term in ({"tag": "list_sort", "value": values}, {"tag": "list_unique", "value": values},
                     {"tag": "bool_eq", "left": values, "right": values},
                     {"tag": "decide", "formula": {"tag": "lt", "left": a, "right": b}}):
            with self.subTest(term=term), self.assertRaises(dsl.DSLError):
                dsl.type_term(term, [], p)

    def test_primitive_equality_instances_and_v1_rejection_are_unchanged(self):
        p = dsl.Profile.from_json(pure_profile())
        for sort, name, levels in (("Nat", "instDecidableEqNat", []), ("Int", "Int.instDecidableEq", []),
                                   ("Bool", "instDecidableEqBool", []), ("String", "instDecidableEqString", []),
                                   ("Unit", "instDecidableEqPUnit", [1])):
            self.assertEqual(const(name, levels), reify._Denoter(p).equality_instance(sort))
        raw = pure_profile()
        raw["dsl"] = dsl.ENCODING
        legacy = dsl.Profile.from_json(raw)
        with self.assertRaisesRegex(dsl.DSLError, "requires contract DSL 0.2"):
            dsl.type_term({"tag": "bool_eq", "left": enum_term("Alpha", "first"),
                           "right": enum_term("Alpha", "first")}, [], legacy)


SOURCE = '''import Std
namespace EnumEqualityCore
inductive Alpha where | first | second deriving DecidableEq
inductive Beta where | first | second | third deriving DecidableEq
structure Packet where
  kind : Alpha
  values : List Alpha
def equalAlpha (a b : Alpha) : Bool := @Decidable.decide (a = b) (instDecidableEqAlpha a b)
def equalBeta (a b : Beta) : Bool := @Decidable.decide (a = b) (instDecidableEqBeta a b)
def dispatch (p : Packet) : Nat := cond (decide (p.kind = Alpha.first)) 7 11
def filtered (p : Packet) : List Alpha := p.values.filter (fun x => decide (x = p.kind))
def mapped (p : Packet) : List Bool := p.values.map (fun x => decide (x = p.kind))
def folded (p : Packet) : Nat := p.values.foldl (fun acc x => cond (decide (x = p.kind)) (acc + 1) acc) 0
def compound (a : Alpha) : Bool := decide (a = Alpha.first ∧ ¬ a = Alpha.second)
theorem alpha_contract (a b : Alpha) : equalAlpha a b = decide (a = b) := rfl
theorem beta_contract (a b : Beta) : equalBeta a b = decide (a = b) := rfl
theorem dispatch_contract (p : Packet) : dispatch p = cond (decide (p.kind = Alpha.first)) 7 11 := rfl
theorem filtered_contract (p : Packet) : filtered p = p.values.filter (fun x => decide (x = p.kind)) := rfl
theorem mapped_contract (p : Packet) : mapped p = p.values.map (fun x => decide (x = p.kind)) := rfl
theorem folded_contract (p : Packet) : folded p = p.values.foldl (fun acc x => cond (decide (x = p.kind)) (acc + 1) acc) 0 := rfl
theorem compound_contract (a : Alpha) : compound a = decide (a = Alpha.first ∧ ¬ a = Alpha.second) := rfl
theorem primitive_contract (a b : Nat) : decide (a = b) = decide (a = b) := rfl
end EnumEqualityCore
'''


class EnumEqualityKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Retain every attempt, including failures, for the root qualification.
        parent = Path(__file__).resolve().parents[1] / "validation" / "formalizer-enumerations"
        parent.mkdir(parents=True, exist_ok=True)
        cls.capture = Path(tempfile.mkdtemp(prefix="core-kernel-", dir=parent))
        cls.tc = leanbridge.resolve_toolchain()
        cls.compiled = leanbridge.compile_module(cls.tc, SOURCE.encode(), cls.capture / "compile")
        (cls.capture / "compile-result.json").write_bytes(canonical.dumps({
            "ok": cls.compiled.ok, "errors": cls.compiled.errors, "process_evidence": cls.compiled.process_evidence}))
        if not cls.compiled.ok:
            raise AssertionError(cls.compiled.errors)
        cls.export = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        (cls.capture / "export.json").write_bytes(canonical.dumps(cls.export))
        cls.env = contract.Env.from_export(cls.export, policy.get("strict"), "enum-core")
        if cls.env.diagnostics:
            raise AssertionError(cls.env.diagnostics)
        cls.names = ["alpha_contract", "beta_contract", "dispatch_contract", "filtered_contract",
                     "mapped_contract", "folded_contract", "compound_contract", "primitive_contract"]
        cls.roots = {"EnumEqualityCore." + n for n in cls.names}
        cls.raw, cls.notes = reify.derive_profile("generic-enum-kernel", cls.env.decls, cls.env.hashes, cls.roots)
        (cls.capture / "profile.json").write_bytes(canonical.dumps(cls.raw))
        cls.profile = dsl.Profile.from_json(cls.raw)
        cls.formulas, requests = {}, []
        for n in cls.names:
            row = cls.env.decls["EnumEqualityCore." + n]
            f, why, _ = reify.reify_formula(row["type"], cls.profile, cls.env.decls)
            if f is None:
                raise AssertionError((n, why))
            cls.formulas[n] = f
            requests.append({"id": n, "theorem": row["name"], "expr": reify.denote_formula(f, cls.profile)})
        cls.checks = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"defeq": requests})["defeq"]
        (cls.capture / "defeq.json").write_bytes(canonical.dumps(cls.checks))

    def test_actual_nominal_bindings_and_universal_denotations(self):
        for eid in ("Alpha", "Beta"):
            row = self.profile.enums[eid]
            binding = row["decidable_eq"]
            self.assertEqual("EnumEqualityCore.instDecidableEq" + eid, binding["lean_decl"])
            self.assertEqual(self.env.hashes[binding["lean_decl"]], binding["decl_hash"])
            self.assertEqual(binding["lean_decl"], reify.validate_enum_equality_binding(self.profile, eid, self.env.decls))
            self.assertNotIn("candidate_decidable_eq", row)
        for result in self.checks:
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, result["result"], result)

    def test_actual_reference_bodies_all_pairs_and_nested_binders(self):
        bodies = contract_refutation._definition_bodies(self.profile, self.env)
        for name in ("equalAlpha", "equalBeta", "dispatch", "filtered", "mapped", "folded", "compound"):
            self.assertIn(name, bodies)
        evaluator = dsl.Evaluator(self.profile, {}, lambda *_: [])
        for name, eid in (("equalAlpha", "Alpha"), ("equalBeta", "Beta")):
            for left in self.profile.enums[eid]["constructors"]:
                for right in self.profile.enums[eid]["constructors"]:
                    self.assertEqual(left == right, evaluator.term(bodies[name],
                        [dsl.enum_v(eid, right), dsl.enum_v(eid, left)]))
        first, second = dsl.enum_v("Alpha", "first"), dsl.enum_v("Alpha", "second")
        for selected, expected in ((first, 7), (second, 11)):
            packet = dsl.record_v("Packet", [selected, (first, second, first)])
            self.assertEqual(expected, evaluator.term(bodies["dispatch"], [packet]))
            self.assertEqual(tuple(x for x in (first, second, first) if x == selected),
                             evaluator.term(bodies["filtered"], [packet]))
            self.assertEqual(tuple(x == selected for x in (first, second, first)),
                             evaluator.term(bodies["mapped"], [packet]))
            self.assertEqual(2 if selected == first else 1, evaluator.term(bodies["folded"], [packet]))

    def test_stale_foreign_unknown_and_malformed_binding_reject(self):
        for change in ({"decl_hash": canonical.digest(b"stale")},
                       {"lean_decl": "EnumEqualityCore.instDecidableEqBeta"},
                       {"lean_decl": "EnumEqualityCore.unknown"}):
            raw = copy.deepcopy(self.raw)
            raw["enums"]["Alpha"]["decidable_eq"].update(change)
            p = dsl.Profile.from_json(raw)
            with self.subTest(change=change), self.assertRaises(reify.Unsupported):
                reify.validate_enum_equality_binding(p, "Alpha", self.env.decls)

    def test_unsafe_noncomputable_incompatible_or_ambiguous_actual_instances(self):
        name = self.profile.enums["Alpha"]["decidable_eq"]["lean_decl"]
        for kind in ("unsafe", "noncomputable", "foreign"):
            decls = copy.deepcopy(self.env.decls)
            if kind == "unsafe":
                decls[name]["safety"] = "unsafe"
            elif kind == "noncomputable":
                decls[name]["axioms"] = [parse_name("Classical.choice")]
            else:
                decls[name]["type"] = app(const("DecidableEq", [1]), const("EnumEqualityCore.Beta"))
            with self.subTest(kind=kind), self.assertRaises(reify.Unsupported):
                reify.validate_enum_equality_binding(self.profile, "Alpha", decls)
        decls = copy.deepcopy(self.env.decls)
        alternative = "EnumEqualityCore.alternativeEquality"
        decls[alternative] = {**decls[name], "name": parse_name(alternative)}
        hashes = {n: decl_hash(c) for n, c in decls.items()}
        raw, notes = reify.derive_profile("ambiguous", decls, hashes, self.roots | {alternative})
        self.assertNotIn("decidable_eq", raw["enums"]["Alpha"])
        self.assertTrue(any("ambiguous" in n for n in notes))
        with self.assertRaisesRegex(dsl.DSLError, "no bound computable"):
            dsl.type_term({"tag": "decide", "formula": equality(enum_term("Alpha", "first"),
                enum_term("Alpha", "second"))}, [], dsl.Profile.from_json(raw))

    def test_full_semantic_closure_catches_helper_change_without_claiming_transitive_decl_hash(self):
        name = self.profile.enums["Alpha"]["decidable_eq"]["lean_decl"]
        helper = "EnumEqualityCore.Alpha.ctorIdx"
        decls = copy.deepcopy(self.env.decls)
        decls[helper]["value"] = {"lit": {"nat": "99"}}
        self.assertEqual(decl_hash(self.env.decls[name]), decl_hash(decls[name]))
        from verislop.exprjson import closure
        family = closure({name}, decls)
        before = {n: self.env.hashes[n] for n in sorted(family)}
        after = {n: decl_hash(decls[n]) for n in sorted(family)}
        self.assertNotEqual(canonical.digest_json(before), canonical.digest_json(after))
        raw, notes = reify.derive_profile("stale-helper", decls, self.env.hashes, self.roots)
        self.assertNotIn("decidable_eq", raw["enums"]["Alpha"])
        self.assertTrue(any("stale semantic identity" in n for n in notes))

    def test_custom_beq_or_wrong_selected_decider_never_reifies_as_enum_equality(self):
        a, b = const("EnumEqualityCore.Alpha.first"), const("EnumEqualityCore.Alpha.second")
        ty = const("EnumEqualityCore.Alpha")
        r = reify._Reifier(self.profile, self.env.decls)
        with self.assertRaisesRegex(reify.Unsupported, "nonprimitive"):
            r.term(app(const("BEq.beq", [0]), ty, const("EnumEqualityCore.customBEq"), a, b), [])
        proposition = app(const("Eq", [1]), ty, a, b)
        with self.assertRaisesRegex(reify.Unsupported, "exact bound equality instance"):
            r.term(app(const("Decidable.decide"), proposition,
                       app(const("EnumEqualityCore.alternativeEquality"), a, b)), [])
        # Well-typed arbitrary Boolean comparison is still not registered machinery.
        with self.assertRaisesRegex(reify.Unsupported, "exact bound equality instance"):
            r.term(app(const("Decidable.decide"), proposition,
                       app(const("EnumEqualityCore.instDecidableEqBeta"), a, b)), [])

    def test_false_enum_theorem_is_actually_rejected_by_pinned_lean(self):
        source = SOURCE + '''
theorem false_enum_claim : EnumEqualityCore.equalAlpha .first .second = true := by decide +kernel
'''
        result = leanbridge.compile_module(self.tc, source.encode(), self.capture / "false-theorem")
        (self.capture / "false-theorem-result.json").write_bytes(canonical.dumps({
            "ok": result.ok, "errors": result.errors, "process_evidence": result.process_evidence}))
        self.assertFalse(result.ok)
        self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
