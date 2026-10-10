"""Generic authored proof regressions; not live corpus outcomes or role context."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from verislop import accept, canonical, contract, dsl, formal_frontend, leanbridge, policy, prove, reify
from tests import test_formal_frontend_workflow as frontend_fixture


def string(value):
    return {"tag": "string", "value": value}


def signed(value):
    return {"tag": "int", "value": str(value)}


def cell(label, quotient):
    return {"tag": "record", "sort": "Cell", "fields": [string(label),
        {"tag": "some", "value": signed(quotient)}]}


def list_of(sort, elements):
    return {"tag": "list", "element_sort": sort, "items": elements}


def catalogue_proposal():
    labels = list_of("String", [string("beta"), string("amber"), string("beta")])
    sorted_labels = {"tag": "list_sort", "value": {"tag": "list_unique", "value": {"tag": "var", "index": 0}}}
    body = {"tag": "list_map", "value": sorted_labels, "function": {"sort": "String", "body": {"tag": "record", "sort": "Cell", "fields": [
        {"tag": "var", "index": 0}, {"tag": "some", "value": {"tag": "int_fdiv",
            "left": {"tag": "nat_to_int", "value": {"tag": "string_length", "value": {"tag": "var", "index": 0}}},
            "right": signed(4)}}]}}}
    fold = {"tag": "list_foldl", "value": list_of("Int", [signed(-4), signed(6), signed(7)]),
        "initial": signed(0), "function": {"accumulator_sort": "Int", "element_sort": "Int",
            "body": {"tag": "int_add", "left": {"tag": "var", "index": 1},
                "right": {"tag": "var", "index": 0}}}}
    formula = {"tag": "and", "left": {"tag": "eq", "left": {"tag": "call", "symbol": "catalogue", "args": [labels]},
        "right": list_of({"record": "Cell"}, [cell("amber", 1), cell("beta", 1)])},
        "right": {"tag": "eq", "left": fold, "right": signed(9)}}
    return {"encoding": formal_frontend.VERSION,
        "records": {"Cell": {"fields": [{"name": "label", "sort": "String"},
            {"name": "quotient", "sort": {"option": "Int"}}]}},
        "symbols": {"catalogue": {"args": [{"list": "String"}], "result": {"list": {"record": "Cell"}}, "body": body}},
        "predicates": {}, "theorems": {"examples": {"formula": formula}},
        "obligations": {"D1": {"declarations": [{"kind": "record", "name": "Cell"}, {"kind": "symbol", "name": "catalogue"}]},
            "O1": {"theorem": "examples"}}, "witness_obligations": {}}


FROZEN = [{"id": "D1", "role": "declaration"}, {"id": "O1", "role": "guarantee"}]


def statement(formula):
    return {"role": "guarantee", "lean_symbol": "VeriSlopAST.examples", "representation": "contract_dsl",
        "formula_package": {"formula": formula}}


class ClosedReductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.tc = leanbridge.resolve_toolchain()
        cls.obj = catalogue_proposal()
        cls.c = formal_frontend.compile_response(canonical.dumps(cls.obj), FROZEN, "closed.v0_2")

    def compile(self, source, name):
        return leanbridge.compile_module(self.tc, source.encode(), self.root / name)

    def candidate(self, compiled):
        st = statement(compiled.proposal["theorems"]["examples"]["formula"])
        return prove.apply_portfolio(compiled.source.decode(), {"O1": st}, compiled.profile.raw)

    def test_actual_compiler_example_reduces_without_record_decidable_eq(self):
        self.assertNotIn(b"deriving DecidableEq", self.c.source)
        baseline = self.compile(self.c.source.decode().replace("by sorry", "by rfl"), "rfl")
        self.assertFalse(baseline.ok)
        candidate = self.candidate(self.c)
        self.assertIn("cbv <;> simp_all <;> done", candidate)
        compiled = self.compile(candidate, "accepted")
        self.assertTrue(compiled.ok, compiled.errors)
        self.assertEqual([], compiled.sorry_positions)
        kernel = leanbridge.run_kernel_tool(self.tc, compiled.olean, {"export": True, "axioms": True,
            "defeq": formal_frontend.kernel_audit_requests(self.c)})
        self.assertTrue(kernel["replay"]["ok"], kernel)
        self.assertTrue(all(row["result"]["defeq"] for row in kernel["defeq"]))
        env = contract.Env.from_export(kernel, policy.get("strict"), "closed")
        self.assertEqual([], env.diagnostics)
        profile, _ = reify.derive_profile("closed.v0_2", env.decls, env.hashes,
            {"VeriSlopAST.examples", "VeriSlopAST.catalogue", "VeriSlopAST.Cell"})
        raw, why, _ = reify.reify_formula(env.decls["VeriSlopAST.examples"]["type"], dsl.Profile.from_json(profile), env.decls)
        self.assertIsNotNone(raw, why)
        self.assertTrue(dsl.round_trip_ok(dsl.make_package(raw, "closed.v0_2", encoding=dsl.ENCODING_V2), dsl.Profile.from_json(profile)))
        self.assertTrue(formal_frontend.reconstruct_origin(canonical.dumps(self.obj), FROZEN, self.c.source,
            self.c.formalization, self.c.receipt))
        ax = str(env.decls["VeriSlopAST.examples"].get("axioms", []))
        self.assertNotIn("sorryAx", ax)
        self.assertNotIn("ofReduceBool", ax)

    def test_false_closed_record_example_remains_unresolved(self):
        obj = copy.deepcopy(self.obj)
        obj["theorems"]["examples"]["formula"]["left"]["right"]["items"][0] = cell("amber", 2)
        compiled = formal_frontend.compile_response(canonical.dumps(obj), FROZEN, "false.v0_2")
        result = self.compile(self.candidate(compiled), "false")
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.sorry_positions)

    def test_bounded_typed_eligibility_rejects_bad_open_and_oversized_formulas(self):
        check = lambda f: prove._closed_reduction_eligible(f, self.c.profile.raw)
        self.assertTrue(check(self.obj["theorems"]["examples"]["formula"]))
        for malformed in ({}, {"tag": "unknown"}, {"tag": "eq", "left": signed(1)},
                          {"tag": "eq", "left": {"tag": "var", "index": 0}, "right": signed(0)}):
            self.assertFalse(check(malformed))
        for quantifier in dsl.QUANTIFIERS:
            self.assertFalse(check({"tag": quantifier, "sort": "Int", "body": {"tag": "true"}}))
        deep = {"tag": "true"}
        for _ in range(65):
            deep = {"tag": "not", "body": deep}
        self.assertFalse(check(deep))
        self.assertFalse(check({"tag": "holds", "term": {"tag": "list", "elements": [0] * 5000}}))
        cycle = {"tag": "not"}
        cycle["body"] = cycle
        self.assertFalse(check(cycle))

    def test_native_only_and_opaque_statements_do_not_receive_cbv(self):
        for st in (None, {"representation": "lean_expr"}, {"representation": "contract_facets",
            "formula_package": {"encoding": "verislop.contract-facets/0.1", "value": None, "native": []}}):
            self.assertNotIn("cbv", prove.portfolio_tactic(st, [], self.c.profile.raw))

    def test_unbounded_false_goal_does_not_acquire_proof(self):
        formula = {"tag": "forall", "sort": "Int", "body": {"tag": "false"}}
        tactic = prove.portfolio_tactic(statement(formula), [], self.c.profile.raw)
        self.assertNotIn("cbv", tactic)
        compiled = self.compile("import Std\ntheorem impossible : ∀ _ : Int, False := by " + tactic + "\n", "quantified")
        self.assertTrue(compiled.ok, compiled.errors)
        self.assertTrue(compiled.sorry_positions)


class ClosedAcceptanceTests(unittest.TestCase):
    setUp = frontend_fixture.FrontendWorkflowTests.setUp
    assert_pass = frontend_fixture.FrontendWorkflowTests.assert_pass

    def test_false_proof_search_cannot_acquire_proved_milestone(self):
        from verislop import formalize
        def author(ctx):
            draft, ledger, _ = formalize.require_interpretation(self.pkg)
            records = formalize._records(draft, ledger, None)
            obj = copy.deepcopy(frontend_fixture.AST)
            obj["theorems"]["result"]["formula"] = {"tag": "eq", "left": {"tag": "call", "symbol": "bump",
                "args": [{"tag": "record", "sort": "Input", "fields": [signed(0)]}]}, "right": signed(2)}
            c = formal_frontend.compile_response(canonical.dumps(obj), records, "negative.v0_2")
            return c.source, c.formalization
        self.assert_pass(formalize.run(self.pkg, self.events, agent=author, max_attempts=1))
        self.assertEqual("BLOCKED", prove.run(self.pkg, self.events, budget_seconds=0).status)
        self.assertEqual("BLOCKED", accept.run(self.pkg, self.events).status)


if __name__ == "__main__":
    unittest.main()
