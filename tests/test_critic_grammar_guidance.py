"""Grammar feedback supplies syntax, never a repaired proposal or a live score."""
from __future__ import annotations

import copy
import unittest

import test_autonomous_probe_signal as fixture
from test_formal_frontend_enums import enum_proposal
from verislop import agents, autonomous, canonical, dsl, formal_frontend
from verislop.errors import Diagnostic


class CriticGrammarGuidanceTests(unittest.TestCase):
    setUp = fixture.AutonomousProbeSignalTests.setUp

    def test_current_formalization_error_without_analysis_gets_complete_grammar(self):
        self.ctx.update(analysis=None, diagnostics=[Diagnostic("INVALID_CANDIDATE", "typing: invalid sort 'Parcel'")])
        data = autonomous.packet(self.pkg, self.ctx)
        self.assertEqual(agents.TYPED_FORMALIZER_SYSTEM, data["registered_formalizer_language"])
        self.assertEqual(self.ctx["source"].decode(), data["lean_source"])
        self.assertEqual(1, len(data["diagnostics"]))

    def test_history_proof_and_valid_analysis_do_not_enable_extra_grammar(self):
        self.ctx["previous_critique"] = {"diagnostics": [{"message": "old invalid sort"}]}
        self.assertIsNone(autonomous.packet(self.pkg, self.ctx)["registered_formalizer_language"])
        self.ctx.update(analysis=None, diagnostics=[])
        self.assertIsNone(autonomous.packet(self.pkg, self.ctx)["registered_formalizer_language"])
        self.ctx.update(phase="prove", diagnostics=[Diagnostic("PROOF_UNRESOLVED", "one proof hole")])
        self.assertIsNone(autonomous.packet(self.pkg, self.ctx)["registered_formalizer_language"])


class NamedSortDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.proposal, self.records = enum_proposal()
        self.good = formal_frontend.compile_response(canonical.dumps(self.proposal), self.records, "sort.feedback")

    def test_bare_record_and_enum_sorts_get_exact_syntax_without_mutation(self):
        for sort, expected in (("Packet", '{"record":"Packet"}'), ("Gamma", '{"enum":"Gamma"}')):
            with self.subTest(sort=sort):
                raw = {"list": sort}
                before = copy.deepcopy(raw)
                with self.assertRaises(dsl.DSLError) as raised:
                    dsl.check_sort(raw, self.good.profile)
                self.assertIn(expected, str(raised.exception))
                self.assertEqual(before, raw)
        with self.assertRaisesRegex(dsl.DSLError, "^invalid sort 'Undeclared'$"):
            dsl.check_sort("Undeclared", self.good.profile)

    def test_nested_records_and_term_bare_ids_remain_valid_and_cycles_rejected(self):
        dsl.check_sort({"list": {"record": "Packet"}}, self.good.profile)
        term = self.proposal["symbols"]["packet"]["body"]
        self.assertEqual({"record": "Packet"}, dsl.type_term(term, [], self.good.profile))
        projection = {"tag": "field", "sort": "Inner", "field": "pick", "value": {"tag": "var", "index": 0}}
        self.assertEqual({"enum": "Gamma"}, dsl.type_term(projection, [{"record": "Inner"}], self.good.profile))
        cyclic = copy.deepcopy(self.proposal)
        cyclic["records"]["Inner"]["fields"][0]["sort"] = {"record": "Packet"}
        with self.assertRaisesRegex(formal_frontend.FrontendError, "recursive record"):
            formal_frontend.compile_response(canonical.dumps(cyclic), self.records, "sort.feedback")

    def test_frontend_rejection_keeps_raw_candidate_and_explicit_repair_restores_exact_output(self):
        bad = copy.deepcopy(self.proposal)
        bad["symbols"]["packet"]["result"] = "Packet"
        before = canonical.dumps(bad)
        with self.assertRaises(formal_frontend.FrontendError) as raised:
            formal_frontend.compile_response(before, self.records, "sort.feedback")
        self.assertIn('{"record":"Packet"}', str(raised.exception))
        self.assertEqual(before, canonical.dumps(bad))
        bad["symbols"]["packet"]["result"] = {"record": "Packet"}
        repaired = formal_frontend.compile_response(canonical.dumps(bad), self.records, "sort.feedback")
        self.assertEqual(self.good.source, repaired.source)
        self.assertEqual(self.good.formalization, repaired.formalization)


if __name__ == "__main__":
    unittest.main()
