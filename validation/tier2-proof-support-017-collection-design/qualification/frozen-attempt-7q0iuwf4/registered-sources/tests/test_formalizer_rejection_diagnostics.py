"""Rejected transport placeholders expose real errors; no formal gate is relaxed."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_formal_frontend_workflow import AST, FrontendWorkflowTests
from verislop import agents, canonical, contract, formalize, fsutil


class FormalizerRejectionDiagnosticTests(unittest.TestCase):
    setUp = FrontendWorkflowTests.setUp
    assert_pass = FrontendWorkflowTests.assert_pass

    def malformed_ast(self):
        proposal = copy.deepcopy(AST)
        proposal["symbols"]["bump"]["body"]["right"] = {"tag": "string", "value": "wrong sort"}
        return canonical.dumps(proposal).decode()

    def role(self, responses, captured):
        responses = iter(responses)
        def call(*args):
            captured.append({"system": args[2], "user": args[3]})
            return SimpleNamespace(text=next(responses), request_id="authored-diagnostic-fixture")
        broker = SimpleNamespace(call=call)
        with patch.object(agents, "_broker", return_value=(broker, {"roles": {"formalizer": "author"}})):
            return agents.formalizer_agent("unused", self.pkg, self.events)

    def test_malformed_typed_ast_then_corrected_candidate_receives_only_real_diagnostic(self):
        invalid = self.malformed_ast()
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        records = formalize._records(draft, ledger, None)
        with self.assertRaises(ValueError) as failure:
            agents.assemble_formalization_response(invalid, records, "authored-diagnostic-fixture")
        message = "unparseable formalizer response: " + str(failure.exception)
        captured = []
        proposer = self.role([invalid, canonical.dumps(AST).decode()], captured)
        with patch.object(formalize, "attempt", wraps=formalize.attempt) as attempt:
            result = formalize.run(self.pkg, self.events, agent=proposer, max_attempts=2)
        self.assert_pass(result)
        self.assertEqual(2, len(captured))
        self.assertEqual(1, attempt.call_count)
        self.assertIn(message, captured[1]["user"])
        self.assertIn(invalid, captured[1]["user"])
        self.assertNotIn("missing required property", captured[1]["user"])
        self.assertNotIn("unexpected property 'error'", captured[1]["user"])
        self.assertTrue((contract.challenge_dir(self.pkg) / "challenge.json").is_file())
        check = canonical.load_file(self.pkg.path("contract") / "candidate/statement-check.json")
        self.assertTrue(check["frontend_defeq"])
        self.assertTrue(all(row["result"]["defeq"] for row in check["frontend_defeq"]))

    def test_exhausted_malformed_ast_is_blocked_with_one_real_diagnostic(self):
        captured = []
        proposer = self.role([self.malformed_ast()], captured)
        with patch.object(formalize, "attempt") as attempt:
            result = formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(1, len(result.diagnostics))
        self.assertEqual("INVALID_CANDIDATE", result.diagnostics[0].code)
        self.assertTrue(result.diagnostics[0].message.startswith("unparseable formalizer response: "))
        attempt.assert_not_called()
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())

    def test_malformed_raw_manifest_keeps_existing_schema_rejection(self):
        captured = []
        raw = canonical.dumps({"lean_source": "import Std\n", "formalization": {"error": "unparseable formalizer response: raw error"}}).decode()
        proposer = self.role([raw], captured)
        with patch.object(formalize, "attempt") as attempt:
            result = formalize.run(self.pkg, self.events, agent=proposer, max_attempts=1)
        self.assertEqual("BLOCKED", result.status)
        self.assertTrue(any("missing required property" in d.message for d in result.diagnostics))
        attempt.assert_not_called()
        self.assertFalse((contract.challenge_dir(self.pkg) / "challenge.json").exists())

    def test_supplied_candidate_placeholder_still_uses_all_schema_gates(self):
        candidate = Path(self.tmp.name) / "supplied-invalid-candidate"
        fsutil.atomic_write(candidate / "Contract.lean", b"-- unparseable formalizer response\n")
        fsutil.write_json(candidate / "formalization.json", {"error": "unparseable formalizer response: supplied"})
        with patch.object(formalize, "attempt") as attempt:
            result = formalize.run(self.pkg, self.events, candidate=candidate)
        self.assertEqual("BLOCKED", result.status)
        self.assertTrue(any("missing required property" in d.message for d in result.diagnostics))
        attempt.assert_not_called()

    def test_partial_marker_or_extra_manifest_fields_cannot_skip_schema_validation(self):
        for source, manifest in ((b"-- unparseable formalizer response\n", {"error": "not the transport prefix"}),
                                 (b"-- unparseable formalizer response\n", {"error": "unparseable formalizer response: rejected", "bindings": []})):
            with self.subTest(manifest=manifest), patch.object(formalize, "attempt") as attempt:
                result = formalize.run(self.pkg, self.events, agent=lambda ctx: (source, manifest), max_attempts=1)
            self.assertEqual("BLOCKED", result.status)
            self.assertTrue(any("missing required property" in d.message for d in result.diagnostics))
            attempt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
