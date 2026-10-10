"""Supervisor sequencing and failed-report regressions without accepted fixtures."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir
from verislop import canonical, fsutil, report, run, schemas, view
from verislop.backends import registry
from verislop.events import EventSink
from verislop.package import Package
from verislop.stage import StageResult


class VSCoreWorkflowUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(self.tmp.path)
        self.pkg.ensure("workflow-unit")
        self.params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source", "config": None,
                       "require_state": "END_TO_END_VERIFIED"}

    def test_resume_never_skips_fresh_mechanics_or_release(self):
        calls = []
        def stage(name, *args):
            calls.append(name)
            return StageResult(name, "PASS", "fixture", summary={"mechanical_status": "VERIFIED"})
        with patch.object(run, "_stages_for", return_value=["verify", "review:release", "release:finalize"]), \
             patch.object(run, "_run_stage", side_effect=stage), patch.object(run, "_ensure_report"):
            result = run._execute(self.pkg, EventSink("unit", quiet=True), self.params,
                                  {"verify", "review:release", "release:finalize"})
        self.assertEqual(calls, ["verify", "review:release", "release:finalize"])
        self.assertEqual(result.status, "PASS")

    def test_failed_semantic_acceptance_stops_review_and_writes_bounded_result(self):
        calls = []
        def stage(name, *args):
            calls.append(name)
            return StageResult(name, "BLOCKED", "unproved source", summary={"mechanical_status": "BLOCKED"})
        with patch.object(run, "_stages_for", return_value=["bridge:accept", "review:implementation", "verify"]), \
             patch.object(run, "_run_stage", side_effect=stage), patch.object(registry, "is_vscore", return_value=True):
            result = run._execute(self.pkg, EventSink("unit", quiet=True), self.params, set())
        self.assertEqual(calls, ["bridge:accept", "verify"])
        self.assertEqual(result.status, "BLOCKED")
        record = canonical.load_file(self.pkg.path("report"))
        self.assertEqual(record["mechanical_status"], "BLOCKED")
        self.assertIsNone(record["endpoint"]["established"])
        self.assertEqual(schemas.validate("run-report-v2", record), [])

    def test_malformed_frozen_parameters_fail_as_diagnostics(self):
        for parameters in (None, [], "vscore"):
            fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json",
                              {"schema_version": "0.2", "format": "verislop.implementation-claims/0.2",
                               "parameters": parameters})
            backend, problems = registry.frozen_backend(self.pkg)
            self.assertIsNone(backend)
            self.assertEqual(problems[0].code, "INVALID_CANDIDATE")
        self.assertIsNone(registry.select(True, "python", "test_campaign"))
        self.assertIsNone(registry.select(2, "vscore", "restricted_source", "future"))

    def test_descriptor_results_do_not_mutate_registry(self):
        selected = registry.select(2, "vscore", "restricted_source")
        selected["producers"]["IMPLEMENTED"] = "candidate-verifier"
        self.assertEqual(registry.select(2, "vscore", "restricted_source")["producers"]["IMPLEMENTED"],
                         "verislop.vscore-materializer")

    def test_deleted_claim_inventory_cannot_dispatch_a_selected_source_as_python(self):
        fsutil.write_json(self.pkg.path("closure") / "selection.json", {})
        backend, problems = registry.frozen_backend(self.pkg)
        self.assertIsNone(backend)
        self.assertEqual(problems[0].code, "VERIFIER_NOT_RUN")

    def test_interrupted_report_keeps_vscore_boundary(self):
        run._interrupted_report(self.pkg, [], self.params)
        record = canonical.load_file(self.pkg.path("report"))
        self.assertEqual(schemas.validate("run-report-v2", record), [])
        self.assertEqual(record["terminal_status"], "BLOCKED")
        self.assertIsNone(record["endpoint"]["established"])
        self.assertIn("INTERRUPTED", record["qualified_result"])


if __name__ == "__main__":
    unittest.main()
