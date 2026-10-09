"""Generic engineering fixtures for exhaustive finite Tier 0 target campaigns."""
from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from verislop import canonical, dsl, fsutil, sandbox, testing

VAR = {"tag": "var", "index": 0}
FALSE = {"tag": "bool", "value": False}
TRUE = {"tag": "bool", "value": True}


def fixture(sorts=None, body=None, *, records=None, enums=None, legacy=False):
    sorts = ["Bool"] if sorts is None else sorts
    body = VAR if body is None else body
    raw = {"profile_id": "finite-engineering", "records": records or {}, "enums": enums or {},
           "predicates": {}, "symbols": {"probe": {"lean_decl": "Fixture.probe", "args": sorts,
                                                       "result": "Bool", "body": body}}}
    if not legacy:
        raw["dsl"] = dsl.ENCODING_V2
    profile = dsl.Profile.from_json(raw)
    args = [{"tag": "var", "index": i} for i in reversed(range(len(sorts)))]
    formula = {"tag": "eq", "left": {"tag": "call", "symbol": "probe", "args": args}, "right": body}
    for sort in reversed(sorts):
        formula = {"tag": "forall", "sort": sort, "body": formula}
    dsl.type_formula(formula, [], profile)
    return profile, formula


@unittest.skipUnless(sandbox.filesystem_isolation_available() and sandbox.network_isolation_available(),
                     "filesystem/network namespaces unavailable")
class FiniteCampaigns(unittest.TestCase):
    def execute(self, source, profile, formula, *, cfg=None):
        tmp = tempfile.TemporaryDirectory(prefix="verislop-finite-engineering-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        fsutil.atomic_write(root / "implementation/probe.py", source.encode())
        package = dsl.make_package(formula, profile.profile_id, encoding=profile.encoding)
        dsl.check_package(package, profile)
        payload = canonical.dumps(package)
        digest = canonical.digest(payload)
        fsutil.atomic_write(root / "expressions" / (digest[7:] + ".json"), payload)
        link = {"bindings": [{"symbol": "probe", "implementation_object": {"file": "probe.py", "qualname": "probe"}}]}
        claims = {"claims": [{"milestone": "TESTED", "obligation": "O1", "applicable": True}]}
        ir = {"obligations": {"O1": {"kind": "postcondition", "formal": {
            "representation": "contract_dsl", "formula_ref": "artifact:formula@" + digest}}}}
        cfg = cfg or testing.campaign_config(31, 1, 100, profile)
        return testing.execute(root / "implementation", link, claims, ir, profile, cfg, root / "expressions", {})

    def test_closed_correct_property_executes_and_wrong_output_has_concrete_failure(self):
        profile, _ = fixture()
        clauses = [{"tag": "eq", "left": {"tag": "call", "symbol": "probe", "args": [x]}, "right": x}
                   for x in (FALSE, TRUE)]
        formula = {"tag": "and", "left": clauses[0], "right": clauses[1]}
        good = self.execute("def probe(x):\n    return x\n", profile, formula)["obligations"]["O1"]
        self.assertEqual("PASS", good["outcome"], good)
        self.assertEqual(1, good["detail"]["counts"]["effective"])
        self.assertEqual({"generated": 1, "effective": 1, "discarded": 0, "indeterminate": 0,
                          "timeouts": 0, "failures": 0}, good["detail"]["counts"])
        domain = good["detail"]["domain"]
        self.assertEqual("exhaustive_finite", domain["mode"])
        self.assertEqual(1, domain["cardinality"])
        self.assertTrue(domain["exact_completion"])
        bad = self.execute("def probe(x):\n    return False\n", profile, formula)["obligations"]["O1"]
        self.assertEqual(["TEST_FAILURE"], bad["codes"], bad)
        self.assertTrue(bad["detail"]["domain"]["enumeration_complete"])
        self.assertFalse(bad["detail"]["domain"]["exact_completion"])
        self.assertEqual([], bad["detail"]["counterexamples"][0]["assignment"])
        self.assertEqual("consequent is false", bad["detail"]["counterexamples"][0]["reason"])

    def test_boolean_domain_is_fully_checked_even_when_only_one_case_requested(self):
        profile, formula = fixture()
        good = self.execute("def probe(x):\n    return x\n", profile, formula)["obligations"]["O1"]
        self.assertEqual("PASS", good["outcome"], good)
        self.assertEqual(2, good["detail"]["counts"]["generated"])
        self.assertEqual(2, good["detail"]["domain"]["accounted_assignments"])
        bad = self.execute("def probe(x):\n    return False\n", profile, formula)["obligations"]["O1"]
        self.assertEqual(["TEST_FAILURE"], bad["codes"], bad)
        self.assertEqual([True], bad["detail"]["counterexamples"][0]["assignment"])

    def test_record_of_boolean_fields_enumerates_every_combination(self):
        fields = [{"name": name, "sort": "Bool"} for name in ("first", "second")]
        field = lambda name: {"tag": "field", "sort": "Pair", "field": name, "value": VAR}
        body = {"tag": "bool_eq", "left": field("first"), "right": field("second")}
        profile, formula = fixture([{"record": "Pair"}], body, records={"Pair": {"fields": fields}})
        result = self.execute("def probe(x):\n    return x['first'] == x['second']\n", profile, formula)["obligations"]["O1"]
        self.assertEqual("PASS", result["outcome"], result)
        self.assertEqual(4, result["detail"]["counts"]["generated"])
        self.assertEqual(4, result["detail"]["domain"]["cardinality"])
        self.assertTrue(result["detail"]["domain"]["enumeration_complete"])
        self.assertTrue(result["detail"]["domain"]["exact_completion"])

    def test_unit_enum_option_and_result_have_exact_finite_cardinalities(self):
        sorts = ["Bool", "Unit", {"enum": "Flag"}, {"option": "Bool"}, {"result": {"error": "Bool", "ok": "Bool"}}]
        body = {"tag": "var", "index": 4}
        profile, formula = fixture(sorts, body, enums={"Flag": {"constructors": ["low", "high"]}})
        result = self.execute("def probe(b,u,e,o,r):\n    return b\n", profile, formula)["obligations"]["O1"]
        self.assertEqual("PASS", result["outcome"], result)
        self.assertEqual(48, result["detail"]["domain"]["cardinality"])
        self.assertEqual(48, result["detail"]["counts"]["effective"])

    def test_all_discarded_is_not_tested_despite_exact_enumeration(self):
        profile, formula = fixture()
        formula["body"] = {"tag": "implies", "left": {"tag": "false"}, "right": formula["body"]}
        out = self.execute("def probe(x):\n    raise AssertionError('must not execute')\n", profile, formula)
        result = out["obligations"]["O1"]
        self.assertEqual(["EMPTY_TEST_CAMPAIGN"], result["codes"], result)
        self.assertEqual(2, result["detail"]["counts"]["discarded"])
        self.assertEqual(0, result["detail"]["counts"]["effective"])
        self.assertTrue(result["detail"]["domain"]["enumeration_complete"])
        self.assertFalse(result["detail"]["domain"]["exact_completion"])
        self.assertNotIn(2, out["coverage"]["probe.py"]["executed"])

    def test_residual_unbounded_quantifier_is_indeterminate_not_exhaustive_success(self):
        profile, formula = fixture()
        formula["body"] = {"tag": "and", "left": formula["body"], "right": {
            "tag": "exists", "sort": "Nat", "body": {"tag": "eq", "left": VAR, "right": {"tag": "nat", "value": "0"}}}}
        result = self.execute("def probe(x):\n    return x\n", profile, formula)["obligations"]["O1"]
        self.assertEqual(["TEST_INCOMPLETE"], result["codes"], result)
        self.assertEqual(2, result["detail"]["counts"]["indeterminate"])
        self.assertTrue(result["detail"]["domain"]["enumeration_complete"])
        self.assertFalse(result["detail"]["domain"]["exact_completion"])

    def test_closed_pure_property_is_not_actual_target_execution_in_either_profile(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                profile, _ = fixture(legacy=legacy)
                result = self.execute("def probe(x):\n    return x\n", profile, {"tag": "true"})["obligations"]["O1"]
                self.assertEqual(["TEST_INCOMPLETE"], result["codes"], result)
                self.assertEqual(0, result["detail"]["counts"]["effective"])
                self.assertFalse(result["detail"]["domain"]["exact_completion"])

    def test_legacy_opt_in_still_requires_and_executes_real_target_calls(self):
        profile, formula = fixture(legacy=True)
        result = self.execute("def probe(x):\n    return x\n", profile, formula)["obligations"]["O1"]
        self.assertEqual("PASS", result["outcome"], result)
        self.assertEqual(2, result["detail"]["counts"]["effective"])

    def test_above_cap_samples_with_unchanged_twenty_case_threshold_and_no_exhaustion_claim(self):
        sorts = ["Bool"] * 13
        profile, formula = fixture(sorts, {"tag": "var", "index": 12})
        source = "def probe(*args):\n    return args[0]\n"
        result = self.execute(source, profile, formula)["obligations"]["O1"]
        self.assertEqual(["EMPTY_TEST_CAMPAIGN"], result["codes"], result)
        domain = result["detail"]["domain"]
        self.assertEqual("sampled", domain["mode"])
        self.assertIsNone(domain["cardinality"])
        self.assertEqual(4097, domain["cardinality_lower_bound"])
        self.assertFalse(domain["enumeration_complete"])
        self.assertFalse(domain["exact_completion"])
        cfg = testing.campaign_config(31, 32, 100, profile)
        larger = self.execute(source, profile, formula, cfg=cfg)["obligations"]["O1"]
        self.assertEqual("PASS", larger["outcome"], larger)
        self.assertEqual(32, larger["detail"]["counts"]["effective"])
        self.assertEqual("sampled", larger["detail"]["domain"]["mode"])

    def test_old_configuration_retains_sample_threshold_and_has_no_new_domain_claim(self):
        profile, formula = fixture()
        cfg = testing.campaign_config(31, 1, 100, profile)
        del cfg["finite_domain"]
        result = self.execute("def probe(x):\n    return x\n", profile, formula, cfg=cfg)["obligations"]["O1"]
        self.assertEqual(["EMPTY_TEST_CAMPAIGN"], result["codes"], result)
        self.assertEqual(1, result["detail"]["counts"]["generated"])
        self.assertNotIn("domain", result["detail"])

    def test_timeout_prevents_exact_completion_and_is_not_a_counterexample(self):
        profile, formula = fixture()
        result = self.execute("import time\ndef probe(x):\n    if x: time.sleep(60)\n    return x\n", profile, formula)["obligations"]["O1"]
        self.assertEqual(["TEST_INCOMPLETE"], result["codes"], result)
        self.assertEqual(1, result["detail"]["counts"]["timeouts"])
        self.assertFalse(result["detail"]["domain"]["exact_completion"])
        self.assertEqual([], result["detail"]["counterexamples"])


class CardinalityBounds(unittest.TestCase):
    def test_legacy_finite_case_budgets_refresh_per_assignment(self):
        profile, formula = fixture(legacy=True)
        cfg = testing.campaign_config(1, 1, 100, profile)
        cfg["finite_domain"]["step_budget"] = 16
        calls = []
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {
            "probe": lambda args: calls.append(args) or args[0]}), cfg, 1)
        for i in range(64):
            self.assertEqual("pass", camp.classify([bool(i % 2)])[0])
        self.assertEqual(64, len(calls))

    def test_enumeration_cap_boundary_is_exactly_4096_without_sample_truncation(self):
        profile, formula = fixture(["Bool"] * 12, {"tag": "var", "index": 11})
        cfg = testing.campaign_config(1, 1, 100, profile)
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {"probe": lambda args: args[0]}), cfg, 1)
        self.assertEqual(4096, camp.domain["cardinality"])
        assignments = list(camp.assignments())
        self.assertEqual(4096, len(assignments))
        self.assertEqual(4096, len({tuple(row) for row in assignments}))
        self.assertTrue(camp.assignments_exhausted)

    def test_oversized_nested_result_never_materializes_whole_finite_domain(self):
        sort = "Bool"
        for _ in range(13):
            sort = {"result": {"error": sort, "ok": "Unit"}}
        # Use many leading copies to exceed the cap without huge literal fixtures.
        profile, formula = fixture([sort] * 4, TRUE)
        cfg = testing.campaign_config(1, 1, 100, profile)
        camp = testing.Campaign(formula, profile, SimpleNamespace(symbols=lambda: {"probe": lambda args: True}), cfg, 1)
        self.assertEqual("sampled", camp.domain["mode"])
        with patch.object(dsl, "finite_values", side_effect=AssertionError("unbounded materialization")), \
             patch.object(testing, "_finite_values", side_effect=AssertionError("exhaustive materialization")):
            values = list(camp.assignments())
        self.assertLessEqual(len(values), cfg["cases_per_obligation"] * cfg["max_generated_factor"])
        self.assertTrue(values)

    def test_record_cycle_and_bounded_sort_traversal_cannot_claim_exhaustion(self):
        profile = dsl.Profile.from_json({"profile_id": "cyclic-finite", "dsl": dsl.ENCODING_V2,
            "records": {"Cycle": {"fields": [{"name": "next", "sort": "Bool"}]}}})
        # Acceptance rejects cycles already; exercise the defensive bounded
        # traversal independently with an explicitly mutated engineering fixture.
        profile.records["Cycle"]["fields"][0]["sort"] = {"record": "Cycle"}
        plan = testing._finite_domain([{"record": "Cycle"}], profile, {"max_assignments": 4096})
        self.assertEqual("sampled", plan["mode"])
        self.assertIn("cyclic", plan["reason"])
        with patch.dict(dsl.LIMITS, max_nodes=1):
            plan = testing._finite_domain(["Bool", "Bool"], profile, {"max_assignments": 4096})
        self.assertEqual("sampled", plan["mode"])
        self.assertIn("budget", plan["reason"])


if __name__ == "__main__":
    unittest.main()
