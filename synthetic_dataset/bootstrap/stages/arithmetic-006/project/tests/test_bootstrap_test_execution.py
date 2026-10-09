"""Per-case reference budgets and fail-stop finite target campaigns."""
from __future__ import annotations
import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from verislop import canonical, dsl, fsutil, testing

VAR = {"tag": "var", "index": 0}
FIELD = {"tag": "field", "sort": "Input", "field": "n", "value": VAR}
BODY = {"tag": "list_sum", "value": {"tag": "list_map", "value": {
    "tag": "list_range", "stop": {"tag": "int_to_nat", "value": FIELD}},
    "function": {"sort": "Nat", "body": {"tag": "nat_to_int", "value": VAR}}}}


def fixture(body=None):
    body = BODY if body is None else body
    profile = dsl.Profile.from_json({"profile_id": "preflight-tests", "dsl": dsl.ENCODING_V2,
        "enums": {}, "predicates": {}, "records": {"Input": {"fields": [{"name": "n", "sort": "Int"}]}},
        "symbols": {"solve": {"lean_decl": "Fixture.solve", "args": [{"record": "Input"}],
                              "result": "Int", "body": body}}})
    formula = {"tag": "forall", "sort": {"record": "Input"}, "body": {"tag": "eq",
        "left": {"tag": "call", "symbol": "solve", "args": [VAR]}, "right": body}}
    dsl.type_formula(formula, [], profile)
    return profile, formula


class PreflightTests(unittest.TestCase):
    def campaign(self, callback, body=None, cfg=None, bodies=None):
        profile, formula = fixture(body)
        cfg = cfg or testing.campaign_config(17, 32, 100, profile)
        return testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {"solve": callback}),
                                cfg, 17, bodies)

    def test_oversize_reference_never_calls_target_and_small_case_does(self):
        calls = []
        def target(args):
            n = args[0][2][0]
            calls.append(n)
            return sum(range(max(n, 0)))
        camp = self.campaign(target)
        self.assertEqual("indeterminate", camp.classify([dsl.record_v("Input", [10**30])])[0])
        self.assertEqual([], calls)
        self.assertEqual(1, sum(camp.preflight_skips.values()))
        self.assertEqual("pass", camp.classify([dsl.record_v("Input", [20])])[0])
        self.assertEqual([20], calls)

    def test_reference_truth_never_substitutes_for_wrong_target(self):
        camp = self.campaign(lambda _: 1)
        self.assertEqual(("fail", "consequent is false"), camp.classify([dsl.record_v("Input", [0])]))
        self.assertEqual(1, camp.target_evaluations)

    def test_each_case_has_fresh_reference_and_target_budgets(self):
        camp = self.campaign(lambda args: args[0][2][0], FIELD)
        camp.cfg["reference_preflight"]["step_budget"] = 16
        for n in range(64):
            self.assertEqual("pass", camp.classify([dsl.record_v("Input", [n])])[0])
        self.assertEqual(64, camp.target_evaluations)

    def test_old_config_preserves_shared_budget_and_execution_order(self):
        cfg = testing.campaign_config(17, 32, 100, fixture()[0])
        del cfg["reference_preflight"]
        cfg.pop("finite_domain", None)
        calls = []
        camp = self.campaign(lambda args: calls.append(args) or 0, cfg=cfg)
        self.assertEqual("indeterminate", camp.classify([dsl.record_v("Input", [10**30])])[0])
        self.assertEqual(1, len(calls))  # Old configuration executes the left call first.
        self.assertEqual({}, camp.preflight_skips)
        camp.ev.steps = 0
        self.assertEqual("indeterminate", camp.classify([dsl.record_v("Input", [0])])[0])
        self.assertEqual(1, len(calls))

    def test_missing_wrong_sort_recursive_bodies_block_without_target(self):
        for bodies in ({}, {"solve": {"tag": "nat", "value": "0"}},
                       {"solve": {"tag": "call", "symbol": "solve", "args": [VAR]}}):
            calls = []
            camp = self.campaign(lambda args: calls.append(args), bodies=bodies)
            self.assertEqual("indeterminate", camp.classify([dsl.record_v("Input", [0])])[0])
            self.assertEqual([], calls)

    def test_invalid_reference_graph_cannot_recurse_in_sampling_hints(self):
        profile = dsl.Profile.from_json({"profile_id": "cycle-hint", "dsl": dsl.ENCODING_V2,
            "symbols": {"loop": {"args": [], "result": "Nat", "body": {"tag": "call", "symbol": "loop", "args": []}}}})
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "eq", "left": VAR,
            "right": {"tag": "call", "symbol": "loop", "args": []}}}
        calls = []
        cfg = testing.campaign_config(17, 32, 100, profile)
        cfg["grid"] = []
        cfg["hint_probability_percent"] = 100
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {
            "loop": lambda args: calls.append(args) or 0}), cfg, 17)
        self.assertTrue(list(camp.assignments()))
        self.assertEqual([], calls)
        self.assertEqual("indeterminate", camp.classify([7])[0])

    def test_target_dependent_false_antecedent_is_not_a_discard(self):
        profile = dsl.Profile.from_json({"profile_id": "target-guard", "dsl": dsl.ENCODING_V2,
            "symbols": {"f": {"args": ["Nat"], "result": "Nat", "body": {"tag": "nat", "value": "1"}}}})
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "implies", "left": {
            "tag": "eq", "left": {"tag": "call", "symbol": "f", "args": [VAR]},
            "right": {"tag": "nat", "value": "0"}}, "right": {"tag": "false"}}}
        calls = []
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {
            "f": lambda args: calls.append(args) or 0}), testing.campaign_config(17, 32, 100, profile), 17)
        self.assertEqual("indeterminate", camp.classify([7])[0])
        self.assertEqual([], calls)

    def test_target_evaluation_restarts_at_original_antecedents(self):
        profile = dsl.Profile.from_json({"profile_id": "original-guard", "dsl": dsl.ENCODING_V2,
            "symbols": {"f": {"args": ["Nat"], "result": "Nat", "body": {"tag": "nat", "value": "0"}}}})
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "implies", "left": {
            "tag": "eq", "left": {"tag": "call", "symbol": "f", "args": [VAR]},
            "right": {"tag": "nat", "value": "0"}}, "right": {"tag": "true"}}}
        calls = []
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {
            "f": lambda args: calls.append(args) or 1}), testing.campaign_config(17, 32, 100, profile), 17)
        self.assertEqual("discarded", camp.classify([7])[0])
        self.assertEqual([[7]], calls)

    def test_each_effective_assignment_bypasses_oracle_result_cache(self):
        profile = dsl.Profile.from_json({"profile_id": "constant-call", "dsl": dsl.ENCODING_V2,
            "symbols": {"f": {"args": ["Nat"], "result": "Nat", "body": {"tag": "nat", "value": "0"}}}})
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "eq", "left": {
            "tag": "call", "symbol": "f", "args": [{"tag": "nat", "value": "0"}]},
            "right": {"tag": "nat", "value": "0"}}}
        calls = []
        harness = SimpleNamespace(call=lambda sym, args: calls.append(args) or {"op": "result", "value": {"int": "0"}})
        oracle = testing.Oracle(harness, profile, {"f"})
        camp = testing.Campaign(formula, profile, oracle, testing.campaign_config(17, 32, 100, profile), 17)
        self.assertEqual("pass", camp.classify([0])[0])
        first = len(calls)
        self.assertEqual("pass", camp.classify([1])[0])
        self.assertGreater(len(calls), first)

    def test_false_reference_cannot_pass_and_pure_formula_is_not_target_execution(self):
        camp = self.campaign(lambda _: 0, bodies={"solve": {"tag": "int", "value": "1"}})
        self.assertEqual("indeterminate", camp.classify([dsl.record_v("Input", [0])])[0])
        self.assertEqual(0, camp.target_evaluations)
        profile, _ = fixture()
        pure = testing.Campaign({"tag": "true"}, profile, SimpleNamespace(symbols=lambda: {}),
                                testing.campaign_config(1, 32, 100, profile), 1)
        self.assertEqual("indeterminate", pure.classify([])[0])

    def test_generator_hints_never_call_python(self):
        profile, _ = fixture(FIELD)
        calls = []
        formula = {"tag": "forall", "sort": "Nat", "body": {"tag": "eq", "left": VAR,
            "right": {"tag": "int_to_nat", "value": {"tag": "call", "symbol": "solve", "args": [
                {"tag": "record", "sort": "Input", "fields": [{"tag": "int", "value": "7"}]}]}}}}
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {
            "solve": lambda args: calls.append(args) or 7}), testing.campaign_config(17, 32, 100, profile), 17)
        self.assertIn(7, camp._inner_candidates(formula["body"], []))
        list(camp.assignments())
        self.assertEqual([], calls)

    def test_native_reference_requires_bound_environment_not_supplied_profile_body(self):
        profile, _ = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            expressions = Path(tmp) / "expressions"
            export = {"import": {"ok": True}, "replay": {"ok": True}, "constants": []}
            payload = canonical.dumps(export)
            hashed = canonical.digest(payload)
            path = expressions.parent / "environment" / (hashed[7:] + ".json")
            fsutil.atomic_write(path, payload)
            self.assertEqual({}, testing._accepted_reference_bodies(profile, {
                "accepted_environment_hash": hashed}, expressions))
            path.write_bytes(payload + b" ")
            self.assertEqual({}, testing._accepted_reference_bodies(profile, {
                "accepted_environment_hash": hashed}, expressions))

    def execute(self, source):
        profile, formula = fixture()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        fsutil.atomic_write(root / "implementation/solution.py", source.encode())
        package = dsl.make_package(formula, profile.profile_id, encoding=dsl.ENCODING_V2)
        payload = canonical.dumps(package)
        hashed = canonical.digest(payload)
        fsutil.atomic_write(root / "expressions" / (hashed[7:] + ".json"), payload)
        link = {"bindings": [{"symbol": "solve", "implementation_object": {"file": "solution.py", "qualname": "solve"}}]}
        claims = {"claims": [{"milestone": "TESTED", "obligation": "O1", "applicable": True}]}
        ir = {"obligations": {"O1": {"kind": "postcondition", "formal": {
            "representation": "contract_dsl", "formula_ref": "artifact:formula@" + hashed}}}}
        cfg = testing.campaign_config(17, 32, 100, profile)
        return testing.execute(root / "implementation", link, claims, ir, profile, cfg, root / "expressions", {})

    def test_real_correct_artifact_passes_and_concrete_mutant_fails(self):
        source = "def solve(x):\n    return sum(range(max(0, x['n'])))\n"
        good = self.execute(source)["obligations"]["O1"]
        self.assertEqual("PASS", good["outcome"], good)
        self.assertEqual(32, good["detail"]["counts"]["effective"])
        self.assertGreater(good["detail"]["reference_preflight"]["skipped"], 0)
        bad = self.execute(source.replace("return sum", "return 1 + sum"))["obligations"]["O1"]
        self.assertEqual(["TEST_FAILURE"], bad["codes"], bad)
        self.assertTrue(bad["detail"]["counterexamples"])

    def test_real_timeout_stops_campaign_without_shrinking_or_later_cases(self):
        started = time.monotonic()
        out = self.execute("def solve(x):\n    while True:\n        pass\n")
        self.assertLess(time.monotonic() - started, 5)
        result = out["obligations"]["O1"]
        self.assertEqual(["TEST_INCOMPLETE"], result["codes"], result)
        self.assertEqual(1, result["detail"]["counts"]["generated"])
        self.assertEqual(0, result["detail"]["counts"]["failures"])
        self.assertEqual([], result["detail"]["counterexamples"])
        self.assertEqual({}, out["coverage"])


if __name__ == "__main__":
    unittest.main()
