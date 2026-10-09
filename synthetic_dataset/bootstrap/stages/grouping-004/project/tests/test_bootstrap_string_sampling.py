"""Finite campaign coverage of named String guards without external examples."""
from __future__ import annotations

import copy
from types import SimpleNamespace
import unittest
from verislop import dsl, testing


def string(value):
    return {"tag": "string", "value": value}


def categorical_formula():
    var = {"tag": "var", "index": 0}
    return {"tag": "forall", "sort": "String", "body": {"tag": "implies",
        "left": {"tag": "or", "left": {"tag": "eq", "left": var, "right": string("mode_one")},
                 "right": {"tag": "eq", "left": var, "right": string("mode_two")}},
        "right": {"tag": "true"}}}


class StringSamplingTests(unittest.TestCase):
    def make_campaign(self, formula=None, profile=None, cfg=None):
        profile = profile or dsl.Profile.from_json({"profile_id": "string-sampling",
            "dsl": dsl.ENCODING_V2, "enums": {}, "symbols": {}, "predicates": {}})
        cfg = cfg or testing.campaign_config(2026, 32, 1000, profile)
        # These fixtures measure the generator, not a linked target campaign.
        cfg.pop("reference_preflight", None)
        return testing.Campaign(formula or categorical_formula(), profile,
                                SimpleNamespace(symbols=lambda: {}), cfg, 2026)

    def test_satisfiable_categorical_guard_gets_effective_cases_and_other_values_remain(self):
        profile = dsl.Profile.from_json({"profile_id": "categorical-record", "dsl": dsl.ENCODING_V2,
            "enums": {}, "symbols": {}, "predicates": {}, "records": {"Input": {"fields": [
                {"name": "mode", "sort": "String"}, {"name": "ticket", "sort": "Int"}]}}})
        formula = categorical_formula()
        formula["sort"] = {"record": "Input"}
        selector = {"tag": "field", "sort": "Input", "field": "mode", "value": {"tag": "var", "index": 0}}
        formula["body"]["left"]["left"]["left"] = selector
        formula["body"]["left"]["right"]["left"] = selector
        camp = self.make_campaign(formula, profile)
        grid = list(camp.assignments())
        self.assertGreaterEqual(sum(camp.classify(v)[0] == "pass" for v in grid), camp.cfg["min_effective_cases"])
        values = [camp._value("String", 0, []) for _ in range(100)]
        self.assertIn("mode_one", values)
        self.assertIn("mode_two", values)
        self.assertTrue(any(v not in {"mode_one", "mode_two"} for v in values))
        again = self.make_campaign(formula, profile)
        list(again.assignments())
        self.assertEqual(values, [again._value("String", 0, []) for _ in range(100)])

    def test_only_reachable_symbol_terms_contribute_and_literal_limits_hold(self):
        profile = dsl.Profile.from_json({"profile_id": "reachable-string-sampling", "dsl": dsl.ENCODING_V2,
            "enums": {}, "predicates": {}, "symbols": {
                "reachable": {"args": [], "result": "String", "body": string("reachable_literal")},
                "unused": {"args": [], "result": "String", "body": string("unrelated_literal")}}})
        formula = {"tag": "eq", "left": {"tag": "call", "symbol": "reachable", "args": []},
                   "right": string("local_literal")}
        camp = self.make_campaign(formula, profile)
        self.assertEqual({"reachable_literal", "local_literal"}, set(camp.string_literals))
        terms = [string("x" * 33), string("\ud800")] + [string(str(i)) for i in range(30)]
        hints = self.make_campaign({"tag": "eq", "left": {"tag": "list", "element_sort": "String", "items": terms},
            "right": {"tag": "list", "element_sort": "String", "items": []}}).string_literals
        self.assertEqual(16, len(hints))
        self.assertEqual([str(i) for i in range(16)], hints)
        # An ordinary metadata value without a String-term tag is not a hint.
        self.assertEqual([], self.make_campaign({"tag": "true", "description": "metadata"}).string_literals)

    def test_old_configuration_keeps_its_original_sequence_and_no_hints(self):
        camp = self.make_campaign()
        old = copy.deepcopy(camp.cfg)
        del old["string_literal_sampling"]
        a = self.make_campaign(cfg=old)
        b = self.make_campaign({"tag": "forall", "sort": "String", "body": {"tag": "true"}}, cfg=old)
        self.assertEqual([], a.string_literals)
        self.assertEqual(a._grid_values("String"), old["unicode_boundary"])
        self.assertEqual([a._value("String", 0, []) for _ in range(100)],
                         [b._value("String", 0, []) for _ in range(100)])

    def test_node_budget_stops_traversal_without_expanding_a_cycle(self):
        node = {"tag": "true"}
        node["body"] = node
        self.assertEqual([], self.make_campaign(node).string_literals)


if __name__ == "__main__":
    unittest.main()
