"""Generic finite-enum authoring; no task templates or retained benchmark answers."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_formal_frontend import example_proposal, frozen_records
from verislop import canonical, contract, dsl, formal_frontend as ff, leanbridge, policy, reify, schemas, verifiers
from verislop.targets.python_target import decode_result, encode_arg

VALIDATION = Path(__file__).resolve().parents[1] / "validation" / "formalizer-enumerations"
LEGACY_SOURCE_HASH = "sha256:6718d510f90f4dc70b2aefd33b078804fb7f0de53011b44fc3ad4bf4d7269e68"


def choice(sort, constructor):
    return {"tag": "enum", "sort": sort, "constructor": constructor}


def enum_proposal():
    """Two nominally distinct two-choice types and an unrelated three-choice type."""
    alpha, beta, gamma = ({"enum": name} for name in ("Alpha", "Beta", "Gamma"))
    var = lambda i: {"tag": "var", "index": i}
    eq = lambda a, b: {"tag": "eq", "left": a, "right": b}
    obj = {"encoding": ff.VERSION_V2,
        "enums": {"Alpha": {"constructors": ["alpha", "beta"]},
                  "Beta": {"constructors": ["alpha", "beta"]},
                  "Gamma": {"constructors": ["first", "second", "third"]}},
        "records": {"Inner": {"fields": [{"name": "pick", "sort": gamma}]},
            "Packet": {"fields": [{"name": "mode", "sort": alpha},
                {"name": "choices", "sort": {"list": gamma}},
                {"name": "optional", "sort": {"option": {"record": "Inner"}}},
                {"name": "outcome", "sort": {"result": {"error": beta, "ok": gamma}}}]}},
        "symbols": {
            "sameAlpha": {"args": [alpha, alpha], "result": "Bool", "body": {
                "tag": "bool_eq", "left": var(1), "right": var(0)}},
            "sameBeta": {"args": [beta, beta], "result": "Bool", "body": {
                "tag": "bool_eq", "left": var(1), "right": var(0)}},
            "sameGamma": {"args": [gamma, gamma], "result": "Bool", "body": {
                "tag": "decide", "formula": eq(var(1), var(0))}},
            "switchAlpha": {"args": [alpha], "result": gamma, "body": {"tag": "ite",
                "condition": {"tag": "bool_eq", "left": var(0), "right": choice("Alpha", "alpha")},
                "then": choice("Gamma", "first"), "else": choice("Gamma", "third")}},
            "packet": {"args": [], "result": {"record": "Packet"}, "body": {
                "tag": "record", "sort": "Packet", "fields": [choice("Alpha", "alpha"),
                    {"tag": "list", "element_sort": gamma, "items": [choice("Gamma", "first"), choice("Gamma", "third")]},
                    {"tag": "some", "value": {"tag": "record", "sort": "Inner", "fields": [choice("Gamma", "second")]}},
                    {"tag": "ok", "error_sort": beta, "value": choice("Gamma", "third")}]}}},
        "predicates": {"isAlpha": {"args": [alpha], "formula": eq(var(0), choice("Alpha", "alpha"))}},
        "theorems": {"reflexive": {"formula": {"tag": "forall", "sort": alpha, "body": eq(var(0), var(0))}},
            "inhabited": {"formula": {"tag": "exists", "sort": alpha,
                "body": {"tag": "predicate", "predicate": "isAlpha", "args": [var(0)]}}}},
        "obligations": {"D1": {"declarations": [{"kind": "enum", "name": n} for n in ("Alpha", "Beta", "Gamma")] +
                [{"kind": "record", "name": "Inner"}, {"kind": "record", "name": "Packet"}]},
            "A1": {"predicate": "isAlpha"}, "O0": {"theorem": "reflexive"}},
        "witness_obligations": {"W1": {"theorem": "inhabited", "witnesses_for": ["A1"], "description": "a nominal choice exists"}}}
    roles = [("D1", "entity", "declaration"), ("A1", "precondition", "assumption"), ("O0", "postcondition", "guarantee")]
    for sort, symbol, constructors in (("Alpha", "sameAlpha", ["alpha", "beta"]),
                                       ("Beta", "sameBeta", ["alpha", "beta"]),
                                       ("Gamma", "sameGamma", ["first", "second", "third"])):
        for left in constructors:
            for right in constructors:
                name = sort + "_" + left + "_" + right
                obj["theorems"][name] = {"formula": eq({"tag": "call", "symbol": symbol,
                    "args": [choice(sort, left), choice(sort, right)]}, {"tag": "bool", "value": left == right})}
                obj["obligations"][name] = {"theorem": name}
                roles.append((name, "postcondition", "guarantee"))
    for constructor, result in (("alpha", "first"), ("beta", "third")):
        name = "branch_" + constructor
        obj["theorems"][name] = {"formula": eq({"tag": "call", "symbol": "switchAlpha",
            "args": [choice("Alpha", constructor)]}, choice("Gamma", result))}
        obj["obligations"][name] = {"theorem": name}
        roles.append((name, "postcondition", "guarantee"))
    frozen = [{"id": oid, "origin": "interpreted", "blocked_by": [], "kind": kind, "role": role, "required": True}
              for oid, kind, role in roles]
    return obj, frozen


def empty_proposal(version=ff.VERSION_V2):
    obj = {"encoding": version, "records": {}, "symbols": {}, "predicates": {}, "theorems": {},
           "obligations": {}, "witness_obligations": {}}
    if version == ff.VERSION_V2:
        obj["enums"] = {}
    return obj


class EnumFrontendValidationTests(unittest.TestCase):
    def setUp(self):
        self.obj, self.frozen = enum_proposal()

    def compile(self, obj=None):
        return ff.compile_response(canonical.dumps(self.obj if obj is None else obj), self.frozen, "enum.generic")

    def test_exact_version_dispatch_and_legacy_byte_stability(self):
        legacy = ff.compile_response(canonical.dumps(example_proposal()), frozen_records(), "generated.v0_2")
        self.assertEqual(LEGACY_SOURCE_HASH, canonical.digest(legacy.source))
        self.assertEqual(ff.COMPILER, legacy.receipt["compiler"])
        self.assertNotIn("frontend_version", legacy.receipt)
        v1, v2 = empty_proposal(ff.VERSION), empty_proposal()
        old = ff.compile_response(canonical.dumps(v1), [], "empty.generic")
        new = ff.compile_response(canonical.dumps(v2), [], "empty.generic")
        self.assertEqual(old.source, new.source)
        self.assertEqual(ff.COMPILER_V2, new.receipt["compiler"])
        self.assertEqual(ff.VERSION_V2, new.receipt["frontend_version"])
        for invalid in ({**v1, "enums": {}}, {k: v for k, v in v2.items() if k != "enums"},
                        {**v2, "encoding": "verislop.formalizer-ast/0.3"}, {**v2, "extra": None}):
            with self.subTest(invalid=invalid), self.assertRaises(ff.FrontendError):
                ff.compile_response(canonical.dumps(invalid), [], "empty.generic")

    def test_nominal_carriers_quoted_source_and_precedence(self):
        generated = self.compile()
        self.assertNotEqual(generated.profile.enums["Alpha"]["lean_decl"], generated.profile.enums["Beta"]["lean_decl"])
        self.assertEqual(["VeriSlopAST.Alpha.alpha", "VeriSlopAST.Alpha.beta"], generated.profile.enums["Alpha"]["lean_constructors"])
        source = generated.source.decode()
        self.assertIn("inductive «Gamma» where\n  | «first»\n  | «second»\n  | «third»\n  deriving _root_.DecidableEq", source)
        self.assertLess(source.index("inductive «Gamma»"), source.index("structure «Inner»"))
        self.assertLess(source.index("structure «Inner»"), source.index("structure «Packet»"))
        self.assertIn("_root_.VeriSlopAST.«instDecidableEqAlpha»", source)
        self.assertEqual(["VeriSlopAST.Alpha", "VeriSlopAST.Beta", "VeriSlopAST.Gamma", "VeriSlopAST.Inner", "VeriSlopAST.Packet"],
                         next(row["declarations"] for row in generated.formalization["bindings"] if row["obligation"] == "D1"))
        self.assertIn(b"by sorry", generated.source)

    def test_bad_enumeration_shapes_names_and_generated_collisions(self):
        bad_rows = [None, {}, {"constructors": []}, {"constructors": ["alpha", "alpha"]},
                    {"constructors": "alpha"}, {"constructors": [None]}, {"constructors": ["has space"]},
                    {"constructors": ["_vs_hidden"]}, {"constructors": ["x"] * 65},
                    {"constructors": ["alpha"], "lean_decl": "other"}]
        bad_rows += [{"constructors": [member, "other"]} for member in sorted(ff.GENERATED_TYPE_MEMBERS)]
        for row in bad_rows:
            obj = copy.deepcopy(self.obj); obj["enums"]["Alpha"] = row
            with self.subTest(row=row), self.assertRaises(ff.FrontendError):
                self.compile(obj)
        for name in ("Nat", "Int", "String", "Bad.Name", "_vs_enum", "Inner", "sameAlpha", "instDecidableEqAlpha"):
            obj = copy.deepcopy(self.obj); obj["enums"][name] = {"constructors": ["choice"]}
            with self.subTest(name=name), self.assertRaises(ff.FrontendError):
                self.compile(obj)
        obj = copy.deepcopy(self.obj)
        obj["records"]["Inner"]["fields"][0]["name"] = "mk"
        with self.assertRaisesRegex(ff.FrontendError, "generated Lean"):
            self.compile(obj)

    def test_constructor_type_unknown_sort_and_term_shape_fail_closed(self):
        mutations = [choice("Alpha", "third"), choice("Missing", "alpha"), choice("Beta", "alpha"),
                     {**choice("Alpha", "alpha"), "coercion": "String"},
                     {"tag": "string", "value": "alpha"}]
        for term in mutations:
            obj = copy.deepcopy(self.obj)
            obj["symbols"]["packet"]["body"]["fields"][0] = term
            with self.subTest(term=term), self.assertRaises(ff.FrontendError):
                self.compile(obj)
        for sort in ({"enum": "Missing"}, {"record": "Alpha"}, {"enum": "Alpha", "record": "Alpha"},
                     {"enum": []}, {"option": {"option": {"enum": "Alpha"}}}):
            obj = copy.deepcopy(self.obj); obj["records"]["Packet"]["fields"][0]["sort"] = sort
            with self.subTest(sort=sort), self.assertRaises(ff.FrontendError):
                self.compile(obj)

    def test_global_declaration_and_constructor_budgets(self):
        obj = empty_proposal()
        obj["enums"] = {"Enum" + str(i): {"constructors": ["ctor" + str(j) for j in range(64)]} for i in range(64)}
        ff.compile_response(canonical.dumps(obj), [], "budget.generic")
        obj["enums"]["Excess"] = {"constructors": ["one"]}
        with self.assertRaisesRegex(ff.FrontendError, "aggregate constructor budget"):
            ff.compile_response(canonical.dumps(obj), [], "budget.generic")
        obj["enums"] = {"Enum" + str(i): {"constructors": ["one"]} for i in range(128)}
        ff.compile_response(canonical.dumps(obj), [], "budget.generic")
        obj["symbols"]["extra"] = {"args": [], "result": "Nat", "body": {"tag": "nat", "value": "0"}}
        with self.assertRaisesRegex(ff.FrontendError, "total declaration budget"):
            ff.compile_response(canonical.dumps(obj), [], "budget.generic")

    def test_origin_replay_rejects_changed_constructor_nominality_order_and_receipts(self):
        response = canonical.dumps(self.obj); generated = self.compile()
        args = (response, self.frozen, generated.source, generated.formalization, generated.receipt)
        self.assertTrue(ff.reconstruct_origin(*args))
        for receipt in ({**generated.receipt, "compiler": ff.COMPILER},
                        {**generated.receipt, "frontend_version": ff.VERSION},
                        {**generated.receipt, "source_hash": "sha256:" + "0" * 64},
                        {**generated.receipt, "invented_acceptance": True}):
            with self.subTest(receipt=receipt):
                self.assertFalse(ff.reconstruct_origin(*args[:-1], receipt))
        for field in ("constructor", "nominality", "order", "envelope"):
            obj = copy.deepcopy(self.obj)
            if field == "constructor": obj["enums"]["Gamma"]["constructors"][-1] = "fourth"
            elif field == "nominality": obj["symbols"]["switchAlpha"]["args"] = [{"enum": "Beta"}]
            elif field == "order": obj["enums"]["Alpha"]["constructors"].reverse()
            else: obj["encoding"] = ff.VERSION
            with self.subTest(field=field):
                self.assertFalse(ff.reconstruct_origin(canonical.dumps(obj), *args[1:]))
        formalization = copy.deepcopy(generated.formalization)
        next(row["declarations"] for row in formalization["bindings"] if row["obligation"] == "D1").reverse()
        self.assertFalse(ff.reconstruct_origin(response, self.frozen, generated.source, formalization, generated.receipt))

    def test_both_schema_hashes_registered_and_schema_is_only_structural(self):
        self.assertEqual([], schemas.validate("formalizer-ast-v2", self.obj))
        self.assertTrue(schemas.validate("formalizer-ast", self.obj))
        missing = copy.deepcopy(self.obj); missing.pop("enums")
        self.assertTrue(schemas.validate("formalizer-ast-v2", missing))
        malformed = copy.deepcopy(self.obj); malformed["enums"]["Alpha"]["constructors"] = []
        self.assertTrue(schemas.validate("formalizer-ast-v2", malformed))
        foreign = copy.deepcopy(self.obj); foreign["symbols"]["packet"]["body"]["fields"][0] = choice("Beta", "alpha")
        self.assertEqual([], schemas.validate("formalizer-ast-v2", foreign))
        with self.assertRaises(ff.FrontendError): self.compile(foreign)
        declared = verifiers.VERIFIERS["verislop.formal-statement-checker"]["schemas"]
        self.assertIn("formalizer-ast.schema.json", declared)
        self.assertIn("formalizer-ast-v2.schema.json", declared)
        self.assertNotEqual(schemas.schema_hash("formalizer-ast"), schemas.schema_hash("formalizer-ast-v2"))


class EnumFrontendKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        VALIDATION.mkdir(parents=True, exist_ok=True)
        cls.attempt = Path(tempfile.mkdtemp(prefix="frontend-kernel-", dir=VALIDATION))
        cls.tc = leanbridge.resolve_toolchain()
        cls.obj, cls.frozen = enum_proposal()
        cls.generated = ff.compile_response(canonical.dumps(cls.obj), cls.frozen, "enum.generic")
        (cls.attempt / "response.json").write_bytes(canonical.dumps(cls.obj))
        (cls.attempt / "frozen.json").write_bytes(canonical.dumps(cls.frozen))
        (cls.attempt / "origin.json").write_bytes(canonical.dumps(cls.generated.receipt))
        cls.compiled = leanbridge.compile_module(cls.tc, cls.generated.source, cls.attempt / "candidate")
        (cls.attempt / "candidate-result.json").write_bytes(canonical.dumps({"ok": cls.compiled.ok, "errors": cls.compiled.errors}))
        if not cls.compiled.ok: raise AssertionError((cls.compiled.errors, cls.generated.source.decode()))
        exported = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"export": True, "axioms": True})
        (cls.attempt / "candidate-export.json").write_bytes(canonical.dumps(exported))
        cls.env = contract.Env.from_export(exported, policy.get("strict"), "enum.generic")
        if cls.env.diagnostics: raise AssertionError(cls.env.diagnostics)
        cls.audit = leanbridge.run_kernel_tool(cls.tc, cls.compiled.olean, {"defeq": ff.kernel_audit_requests(cls.generated)})
        (cls.attempt / "candidate-audit.json").write_bytes(canonical.dumps(cls.audit))
        roots = {"VeriSlopAST." + n for kind in ("enums", "records", "symbols", "predicates", "theorems") for n in cls.obj[kind]}
        cls.raw, cls.notes = reify.derive_profile("enum.accepted", cls.env.decls, cls.env.hashes, roots)
        (cls.attempt / "accepted-profile.json").write_bytes(canonical.dumps(cls.raw))
        cls.profile = dsl.Profile.from_json(cls.raw)

    def test_actual_kernel_fidelity_and_accepted_nominal_registry(self):
        for row in self.audit["defeq"]:
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, row["result"], row)
        self.assertEqual({"Alpha", "Beta", "Gamma"}, set(self.profile.enums))
        for name, enum in self.profile.enums.items():
            self.assertEqual(self.obj["enums"][name]["constructors"], enum["constructors"])
            self.assertNotIn("candidate_decidable_eq", enum)
            binding = enum["decidable_eq"]
            self.assertEqual(self.env.hashes[binding["lean_decl"]], binding["decl_hash"])
            self.assertIn("sorryAx", self.env.axioms("VeriSlopAST.reflexive"))

    def test_accepted_reifier_and_wire_round_trips_with_nested_carriers(self):
        for name, enum in self.profile.enums.items():
            for ctor in enum["constructors"]:
                value = dsl.enum_v(name, ctor)
                self.assertEqual({"str": ctor}, encode_arg(value, {"enum": name}, self.profile))
                self.assertEqual(value, decode_result({"str": ctor}, {"enum": name}, self.profile))
            for bad in ("invalid", "", "Alpha.alpha"):
                with self.assertRaises(ValueError): decode_result({"str": bad}, {"enum": name}, self.profile)
        with self.assertRaises(ValueError): encode_arg(dsl.enum_v("Beta", "alpha"), {"enum": "Alpha"}, self.profile)
        value = dsl.record_v("Packet", [dsl.enum_v("Alpha", "alpha"),
            (dsl.enum_v("Gamma", "first"), dsl.enum_v("Gamma", "third")),
            dsl.option_some_v(dsl.record_v("Inner", [dsl.enum_v("Gamma", "second")])),
            ("ok", dsl.enum_v("Gamma", "third"))])
        self.assertEqual(value, decode_result(encode_arg(value, {"record": "Packet"}, self.profile), {"record": "Packet"}, self.profile))
        requests = []
        for name in self.obj["theorems"]:
            decl = self.env.decls["VeriSlopAST." + name]
            formula, reason, _ = reify.reify_formula(decl["type"], self.profile, self.env.decls)
            self.assertIsNotNone(formula, reason)
            self.assertTrue(dsl.round_trip_ok(dsl.make_package(formula, self.profile.profile_id, encoding=dsl.ENCODING_V2), self.profile))
            requests.append({"id": name, "theorem": decl["name"], "expr": reify.denote_formula(formula, self.profile)})
        results = leanbridge.run_kernel_tool(self.tc, self.compiled.olean, {"defeq": requests})
        (self.attempt / "accepted-denotation.json").write_bytes(canonical.dumps(results))
        for row in results["defeq"]: self.assertTrue(row["result"]["defeq"], row)

    def test_every_constructor_pair_and_both_branches_are_kernel_proved(self):
        source = self.generated.source.replace(b" := by sorry", b" := by decide")
        source = source.replace(b"theorem \xc2\xabreflexive\xc2\xbb : (\xe2\x88\x80 (\xc2\xab_v0\xc2\xbb : _root_.VeriSlopAST.\xc2\xabAlpha\xc2\xbb), (\xc2\xab_v0\xc2\xbb = \xc2\xab_v0\xc2\xbb)) := by decide",
                                b"theorem \xc2\xabreflexive\xc2\xbb : (\xe2\x88\x80 (\xc2\xab_v0\xc2\xbb : _root_.VeriSlopAST.\xc2\xabAlpha\xc2\xbb), (\xc2\xab_v0\xc2\xbb = \xc2\xab_v0\xc2\xbb)) := by intros; rfl")
        lines = source.decode().splitlines()
        lines = [line.removesuffix("by decide") + "by exact \u27e8_root_.VeriSlopAST.\u00abAlpha\u00bb.\u00abalpha\u00bb, rfl\u27e9"
                 if line.startswith("theorem \u00abinhabited\u00bb :") else line for line in lines]
        source = ("\n".join(lines) + "\n").encode()
        compiled = leanbridge.compile_module(self.tc, source, self.attempt / "proved-generic")
        (self.attempt / "proved-generic-result.json").write_bytes(canonical.dumps({"ok": compiled.ok, "errors": compiled.errors}))
        self.assertTrue(compiled.ok, compiled.errors)
        exported = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"export": True, "axioms": True})
        (self.attempt / "proved-generic-export.json").write_bytes(canonical.dumps(exported))
        env = contract.Env.from_export(exported, policy.get("strict"), "enum.generic.proved")
        self.assertEqual([], env.diagnostics)
        for name in self.obj["theorems"]: self.assertNotIn("sorryAx", env.axioms("VeriSlopAST." + name))
        results = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"defeq": ff.kernel_audit_requests(self.generated)})
        (self.attempt / "proved-generic-audit.json").write_bytes(canonical.dumps(results))
        for row in results["defeq"]: self.assertTrue(row["result"]["defeq"], row)

    def test_false_nominal_equality_theorem_fails_actual_lean(self):
        obj = empty_proposal(); obj["enums"] = {"Alpha": {"constructors": ["alpha", "beta"]}}
        obj["theorems"] = {"falseChoice": {"formula": {"tag": "eq", "left": choice("Alpha", "alpha"), "right": choice("Alpha", "beta")}}}
        obj["obligations"] = {"O1": {"theorem": "falseChoice"}}
        frozen = [{"id": "O1", "origin": "interpreted", "blocked_by": [], "kind": "postcondition", "role": "guarantee", "required": True}]
        generated = ff.compile_response(canonical.dumps(obj), frozen, "enum.false")
        compiled = leanbridge.compile_module(self.tc, generated.source.replace(b"by sorry", b"by decide"), self.attempt / "false-theorem")
        (self.attempt / "false-theorem-result.json").write_bytes(canonical.dumps({"ok": compiled.ok, "errors": compiled.errors}))
        self.assertFalse(compiled.ok)
        self.assertTrue(compiled.errors)

    def test_fixed_composite_decisions_and_predicate_expansion_have_kernel_fidelity(self):
        obj = copy.deepcopy(self.obj)
        atom = {"tag": "eq", "left": {"tag": "var", "index": 0}, "right": choice("Alpha", "alpha")}
        formulas = {tag: {"tag": tag, "left": atom, "right": {"tag": "not", "body": atom}}
                    for tag in dsl.CONNECTIVES}
        formulas.update({"not": {"tag": "not", "body": atom},
                         "predicate": {"tag": "predicate", "predicate": "isAlpha", "args": [{"tag": "var", "index": 0}]}})
        for name, formula in formulas.items():
            obj["symbols"]["decision_" + name] = {"args": [{"enum": "Alpha"}], "result": "Bool",
                                                   "body": {"tag": "decide", "formula": formula}}
        generated = ff.compile_response(canonical.dumps(obj), self.frozen, "enum.composite")
        built = leanbridge.compile_module(self.tc, generated.source, self.attempt / "composite-decisions")
        (self.attempt / "composite-decisions-result.json").write_bytes(canonical.dumps({"ok": built.ok, "errors": built.errors}))
        self.assertTrue(built.ok, built.errors)
        results = leanbridge.run_kernel_tool(self.tc, built.olean, {"defeq": ff.kernel_audit_requests(generated)})
        (self.attempt / "composite-decisions-audit.json").write_bytes(canonical.dumps(results))
        for row in results["defeq"]: self.assertTrue(row["result"]["defeq"], row)

    def test_actual_generated_declaration_inventory_at_constructor_extremes(self):
        obj = empty_proposal()
        obj["enums"] = {"Singleton": {"constructors": ["only"]},
                        "Many": {"constructors": ["choice" + str(i) for i in range(64)]}}
        generated = ff.compile_response(canonical.dumps(obj), [], "enum.extremes")
        built = leanbridge.compile_module(self.tc, generated.source, self.attempt / "constructor-extremes")
        (self.attempt / "constructor-extremes-result.json").write_bytes(canonical.dumps({"ok": built.ok, "errors": built.errors}))
        self.assertTrue(built.ok, built.errors)
        exported = leanbridge.run_kernel_tool(self.tc, built.olean, {"export": True, "axioms": True})
        (self.attempt / "constructor-extremes-export.json").write_bytes(canonical.dumps(exported))
        env = contract.Env.from_export(exported, policy.get("strict"), "enum.extremes")
        self.assertEqual([], env.diagnostics)
        inventory = {}
        for name, constructors in (("Alpha", ["alpha", "beta"]), ("Singleton", ["only"]),
                                   ("Many", ["choice" + str(i) for i in range(64)])):
            decls = self.env.decls if name == "Alpha" else env.decls
            prefix = "VeriSlopAST." + name + "."
            children = {n.removeprefix(prefix) for n in decls if n.startswith(prefix) and "." not in n.removeprefix(prefix)}
            generated_members = ff.GENERATED_SINGLETON_MEMBERS if len(constructors) == 1 else ff.GENERATED_TYPE_MEMBERS
            self.assertEqual(set(constructors) | generated_members, children)
            self.assertIn("VeriSlopAST.instDecidableEq" + name, decls)
            self.assertTrue(set(constructors).isdisjoint(ff.GENERATED_TYPE_MEMBERS))
            inventory[name] = sorted(children)
        (self.attempt / "actual-generated-name-inventory.json").write_bytes(canonical.dumps(inventory))


if __name__ == "__main__":
    unittest.main()
