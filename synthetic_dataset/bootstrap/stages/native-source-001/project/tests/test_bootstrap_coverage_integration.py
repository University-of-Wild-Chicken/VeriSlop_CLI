"""Negative provenance and nullable campaign/witness integration regressions."""
from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_formal_frontend_workflow as workflow
import test_bootstrap_agent_repair as repairs
from verislop import accept, agents, canonical, contract_refutation as refutation, dsl, formalize, fsutil, reify, review, testing
from synthetic_dataset.tools import bootstrap_coverage as bootstrap
from synthetic_dataset.tools.run_data_pipeline_poc import artifact_origin_audit


class CapabilityOriginTests(unittest.TestCase):
    setUp = workflow.FrontendWorkflowTests.setUp
    assert_pass = workflow.FrontendWorkflowTests.assert_pass

    def test_report_is_exact_negative_origin_and_tampered_report_is_rejected(self):
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        raw = canonical.dumps(repairs.REPORT).decode()
        source, form, _ = agents.assemble_formalization_response(raw, records, "fixture")
        directory = self.pkg.path("contract") / "candidate"
        fsutil.atomic_write(directory / "proposal.lean", source)
        fsutil.write_json(directory / "formalization.json", form)
        calls = [{"purpose": "formalize", "response": raw}]
        audit = artifact_origin_audit(self.pkg, calls)
        self.assertEqual([], audit["issues"], audit)
        self.assertTrue(audit["formalization_origins"])
        self.assertTrue(all(not x["positive_artifact"] for x in audit["formalization_origins"]))
        changed = copy.deepcopy(form)
        changed["capability_report"]["gaps"][0]["reason"] = "manually changed report"
        fsutil.write_json(directory / "formalization.json", changed)
        self.assertTrue(artifact_origin_audit(self.pkg, calls)["issues"])

    def test_original_corpus_selection_and_normal_strict_invocation(self):
        chosen = bootstrap.selection("A23")
        self.assertEqual("verislop", chosen["arm"])
        with self.assertRaises(StopIteration):
            bootstrap.selection("made_up_task")
        from synthetic_dataset.tools.sol_full_corpus_worker import cli_argv
        from synthetic_dataset.tools.sol_full_corpus import task_inventory
        argv = cli_argv(Path(self.tmp.name), task_inventory()["A23"])
        self.assertNotIn("--formalization-candidate", argv)
        self.assertNotIn("--implementation-candidate", argv)
        self.assertIn("TESTED", argv)
        self.assertIn("test_campaign", argv)


class NullableCampaignTests(unittest.TestCase):
    def setUp(self):
        self.profile = dsl.Profile.from_json({"profile_id": "nullable-integration", "dsl": dsl.ENCODING_V2,
            "enums": {}, "symbols": {}, "predicates": {}})
        formula = {"tag": "forall", "sort": {"option": "Int"}, "body": {"tag": "true"}}
        oracle = SimpleNamespace(symbols=lambda: {})
        self.campaign = testing.Campaign(formula, self.profile, oracle,
            testing.campaign_config(19, 32, 1000, self.profile), 19)

    def test_grid_and_shrinker_include_none_some_zero_and_signed_payloads(self):
        values = self.campaign._grid_values({"option": "Int"})
        self.assertIn(dsl.option_none_v(), values)
        self.assertTrue(any(v[0] == "some" and v[1] < 0 for v in values))
        self.assertTrue(all(dsl.value_has_sort(v, {"option": "Int"}, self.profile) for v in values))
        shrunk = list(self.campaign._shrinks(dsl.option_some_v(-17), {"option": "Int"}))
        self.assertIn(dsl.option_none_v(), shrunk)
        self.assertIn(dsl.option_some_v(0), shrunk)

    def test_random_values_and_finite_nullable_booleans_remain_in_sort(self):
        values = [self.campaign._value({"option": "Int"}, 0, []) for _ in range(64)]
        self.assertIn(dsl.option_none_v(), values)
        self.assertTrue(any(v[0] == "some" for v in values))
        self.assertTrue(all(dsl.value_has_sort(v, {"option": "Int"}, self.profile) for v in values))
        self.assertEqual([dsl.option_none_v(), dsl.option_some_v(False), dsl.option_some_v(True)],
                         self.campaign._grid_values({"option": "Bool"}))

    def test_witness_and_refutation_literals_preserve_option_constructors(self):
        sort = {"option": "Int"}
        for value in (dsl.option_none_v(), dsl.option_some_v(0), dsl.option_some_v(-3)):
            literal = refutation._literal(value, sort, self.profile)
            expr, _ = reify._Denoter(self.profile).term(literal, [])
            self.assertEqual(value, accept.decode_witness_value(expr, sort, self.profile))
        seeds = refutation._defaults(sort, self.profile)
        self.assertIn(dsl.option_none_v(), seeds)
        self.assertIn(dsl.option_some_v(0), seeds)
        self.assertEqual({"none": None}, review._assignment_example(sort, self.profile))


if __name__ == "__main__":
    unittest.main()
