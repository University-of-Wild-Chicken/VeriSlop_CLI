"""Early source reports select capability identity without granting assurance."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verislop import canonical, closure, fsutil, report, run, schemas
from verislop.backends import registry
from verislop.errors import Diagnostic
from verislop.events import EventSink
from verislop.package import Package
from verislop.stage import StageResult


class PendingReportDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-pending-report-")
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name))
        self.pkg.ensure("pending-report")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)

    def request(self, version):
        # Reproduce the historical metadata layout: requested did not carry the
        # version, while native run_parameters contained the exact CLI choice.
        declared = {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                    "require_state": "END_TO_END_VERIFIED"}
        self.pkg.set_meta("requested", declared)
        self.pkg.set_meta("run_parameters", {**declared, "backend_version": version})
        return {**declared, "backend_version": version}

    def build(self, params=None):
        return report.build(self.pkg, {"obligations": {}}, "BLOCKED", [], [],
            {"compared": [], "mismatches": []}, params or {}, None, None, None, [],
            {"configured": False}, None)

    def test_pre_inventory_closure_validates_exact_source_schema_without_passes(self):
        for version, backend, schema in (("0.3", registry.VSCORE3_ID, "run-report-v3"),
                                         ("0.1", registry.VSCORE_ID, "run-report-v2"),
                                         (None, registry.VSCORE_ID, "run-report-v2")):
            with self.subTest(version=version):
                self.request(version)
                result = closure.run(self.pkg, self.events, endpoint="restricted_source")
                self.assertEqual(result.status, "BLOCKED")
                record = canonical.load_file(self.pkg.path("report"))
                self.assertEqual(record["backend"], backend)
                self.assertEqual(report.schema_name(record), schema)
                self.assertEqual(schemas.validate(schema, record), [])
                self.assertEqual(record["mechanical_status"], "BLOCKED")
                self.assertIsNone(record["endpoint"]["established"])
                self.assertIsNone(record["mechanical_result"])
                self.assertEqual(record["builds"], [])
                self.assertEqual(record["counts"]["obligations"], 0)
                self.assertFalse(self.pkg.path("accepted_ir").exists())
                self.assertFalse((self.pkg.path("closure") / "implementation-claims.json").exists())

    def test_unknown_version_is_explicit_blocked_report_without_registered_identity(self):
        params = self.request("0.2")
        result = closure.run(self.pkg, self.events)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("UNSUPPORTED_CAPABILITY", {d.code for d in result.diagnostics})
        for record in (canonical.load_file(self.pkg.path("report")), self.build(params)):
            self.assertEqual(record["terminal_status"], "BLOCKED")
            self.assertEqual(report.schema_name(record), "report")
            self.assertEqual(schemas.validate("report", record), [])
            self.assertNotIn("backend", record)
            self.assertNotIn("format", record)
            self.assertIsNone(record["endpoint"]["established"])
            self.assertIn("UNSUPPORTED_CAPABILITY", {d["code"] for d in record["blocking_reasons"]})

    def test_frozen_source_parameters_override_all_later_declared_choices(self):
        later = self.request("0.3")
        frozen = {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                  "backend": registry.VSCORE_ID, "backend_version": "0.1",
                  "require_state": "END_TO_END_VERIFIED"}
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json",
            {"schema_version": "0.2", "format": "verislop.implementation-claims/0.2",
             "parameters": frozen, "claims": []})
        for supplied in (later, {"tier": 0, "target": "python", "backend_version": "0.3"}):
            with self.subTest(supplied=supplied):
                record = self.build(supplied)
                self.assertEqual(record["backend"], registry.VSCORE_ID)
                self.assertEqual(record["language"], "vscore/0.1")
                self.assertEqual(record["tier"]["requested"], 2)
                self.assertEqual(schemas.validate("run-report-v2", record), [])
                self.assertIsNone(record["endpoint"]["established"])

    def test_frozen_python_parameters_prevent_source_report_from_later_metadata(self):
        later = self.request("0.3")
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json",
            {"schema_version": "0.1", "parameters": {"tier": 0, "target": "python",
                "endpoint": "test_campaign"}, "claims": []})
        record = self.build(later)
        self.assertEqual(record["schema_version"], "0.1")
        self.assertEqual(record["tier"]["requested"], 0)
        self.assertEqual(record["tier"]["target"], "python")
        self.assertNotIn("backend", record)
        self.assertEqual(schemas.validate("report", record), [])

    def test_fallback_infrastructure_and_interrupt_writers_keep_exact_source_schema(self):
        params = self.request("0.3")
        result = StageResult("run", "INFRASTRUCTURE_FAILURE", "interpreter transport stopped",
            diagnostics=[Diagnostic("PROVIDER_FAILURE", "startup marker", severity="infrastructure")])
        run._ensure_report(self.pkg, result, params)
        run._record_aggregate_infrastructure(self.pkg, result, params)
        record = canonical.load_file(self.pkg.path("report"))
        self.assertEqual(record["terminal_status"], "INFRASTRUCTURE_FAILURE")
        self.assertEqual(schemas.validate("run-report-v3", record), [])
        self.assertIsNone(record["endpoint"]["established"])
        run._interrupted_report(self.pkg, [], params)
        interrupted = canonical.load_file(self.pkg.path("report"))
        self.assertEqual(schemas.validate("run-report-v3", interrupted), [])
        self.assertEqual(interrupted["terminal_status"], "BLOCKED")
        self.assertIsNone(interrupted["endpoint"]["established"])


if __name__ == "__main__":
    unittest.main()
