"""Fresh CLI startup fixtures exercise real configuration, execution and reporting.

Only the broker transport is replaced: no provider request, candidate implementation,
historical stage, or kernel acceptance is needed to reach the early report boundary.
"""
from __future__ import annotations

import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir, codes, mock_config, run_cli, unanimous

from verislop import agent_memory, canonical, fsutil, generate, schemas
from verislop.capabilities import capability
from verislop.errors import Diagnostic, InfrastructureError
from verislop.package import Package
from verislop.providers.broker import Broker


MARKER = "fresh CLI startup transport boundary"


class VSCore3CLIStartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.calls: list[tuple[Broker, str, str, str, str, str]] = []

    def _transport_failure(self, broker, agent, instance, system, user, purpose):
        self.calls.append((broker, agent, instance, system, user, purpose))
        raise InfrastructureError(MARKER, [Diagnostic(
            "PROVIDER_FAILURE", MARKER, severity="infrastructure")])

    def _startup(self, name: str, flags: tuple[str, ...], *, profile_file: str = "endpoint-profiles.json"):
        root = self.tmp.path / name
        root.mkdir()
        prompt = root / "request.txt"
        prompt.write_text("Return the integer input unchanged.\n")
        config, env = mock_config(root, 9, [unanimous("fresh-review", "reviewer", 1)],
                                  checkpoints=["interpretation"], max_repair_rounds=0)
        # Match the real requested delivery configuration without depending on a
        # saved example or the machine's installed endpoint profiles.
        conf = canonical.load_file(config)
        if "--target" in flags and flags[flags.index("--target") + 1] == "vscore":
            conf.update({"bridge_tier": 2, "endpoint": "restricted_source"})
            fsutil.write_json(config, conf, pretty=True)
        profile = Path(env["VERISLOP_CONFIG_HOME"]) / "endpoint-profiles.json"
        if profile_file == "missing":
            profile.unlink()
        elif profile_file != profile.name:
            profile.rename(profile.with_name(profile_file))
        self.calls.clear()
        with warnings.catch_warnings(), patch.object(
                Broker, "call", autospec=True, side_effect=self._transport_failure) as transport:
            # Existing run event-sink finalization can report delayed resource
            # warnings from an earlier invocation during this CLI call.
            warnings.simplefilter("ignore", ResourceWarning)
            code, result, error = run_cli(
                "run", "--prompt-file", str(prompt), "--runs-dir", str(root / "runs"),
                "--run-id", "fresh-startup", "--mode", "software", "--config", str(config),
                "--repair-rounds", "0", "--non-interactive", *flags, env=env)
        self.assertEqual(error, "")
        self.assertIsNotNone(result)
        pkg = Package(root / "runs" / "fresh-startup")
        self.assertTrue(pkg.path("report").is_file())
        report = canonical.load_file(pkg.path("report"))
        self.assertEqual(result["summary"]["stopped_at"], "interpret")
        self.assertEqual(result["summary"]["stages"][0]["stage"], "interpret")
        self.assertIsNone(report["endpoint"]["established"])
        self.assertEqual(report["obligations"], {})
        self.assertEqual(report["builds"], [])
        self.assertFalse((pkg.path("accepted") / "acceptance.json").exists())
        self.assertFalse((pkg.path("closure") / "implementation-claims.json").exists())
        self.assertNotEqual(report.get("mechanical_status"), "VERIFIED")
        self.assertFalse(result["asserts_closure_verified"])
        return code, result, report, pkg, transport.call_count

    def _assert_transport_reached(self, result, report, pkg, count):
        self.assertEqual(count, 1)
        self.assertEqual(result["status"], "INFRASTRUCTURE_FAILURE")
        self.assertEqual(report["terminal_status"], "INFRASTRUCTURE_FAILURE")
        self.assertIn("PROVIDER_FAILURE", codes(result))
        broker, agent, instance, system, user, purpose = self.calls[0]
        self.assertIsInstance(broker, Broker)
        self.assertFalse(any(d.severity == "blocking" for d in broker.r.diagnostics))
        self.assertEqual(broker.r.profiles["mock"]["base_url"], "http://127.0.0.1:9/v1")
        self.assertEqual((agent, instance, purpose), ("author", "interpreter/1", "interpret"))
        self.assertIn("Return the integer input unchanged.", user)
        self.assertTrue(system)
        self.assertEqual(pkg.path("prompt").read_text(), "Return the integer input unchanged.\n")
        retained = agent_memory.context_for(pkg, last=8)["snapshots"]
        self.assertIn("agent/interpret/input", {s["manifest"]["stage"] for s in retained})
        self.assertIn("agent/interpret/failure", {s["manifest"]["stage"] for s in retained})

    def test_registered_source_versions_reach_transport_and_write_exact_pending_report(self):
        for name, requested, expected in (("v3", "0.3", "0.3"),
                                          ("v1", "0.1", "0.1"),
                                          ("default-vscore", None, "0.1")):
            with self.subTest(version=requested):
                flags = ("--tier", "2", "--target", "vscore", "--endpoint", "restricted_source")
                if requested is not None:
                    flags += ("--backend-version", requested)
                code, result, report, pkg, count = self._startup(name, flags)
                self.assertEqual(code, 3)
                self._assert_transport_reached(result, report, pkg, count)
                self.assertEqual(pkg.meta()["run_parameters"]["backend_version"], requested)
                self.assertEqual(report["backend"], "verislop.backend.vscore/" + expected)
                self.assertEqual(report["language"], "vscore/" + expected)
                self.assertEqual(report["semantics"], "vscore-semantics/" + expected)
                self.assertEqual(report["tier"]["requested"], 2)
                self.assertEqual(report["tier"]["target"], "vscore")
                self.assertEqual(report["endpoint"]["requested"], "restricted_source")
                schema = "run-report-v3" if expected == "0.3" else "run-report-v2"
                self.assertEqual(schemas.validate(schema, report), [])

    def test_missing_or_wrong_profile_filename_blocks_before_transport_with_v3_report(self):
        for filename in ("missing", "providers.json"):
            with self.subTest(profile_file=filename):
                code, result, report, pkg, count = self._startup(
                    "profile-" + filename, ("--tier", "2", "--target", "vscore",
                        "--endpoint", "restricted_source", "--backend-version", "0.3"),
                    profile_file=filename)
                self.assertEqual((code, result["status"], count), (2, "BLOCKED", 0))
                self.assertEqual(self.calls, [])
                self.assertIn("CONFIGURATION_INVALID", codes(result))
                self.assertTrue(any("mock-local" in d["message"] and "does not resolve" in d["message"]
                                    for d in result["diagnostics"] if d["code"] == "CONFIGURATION_INVALID"))
                self.assertEqual(report["terminal_status"], "BLOCKED")
                self.assertEqual(report["backend"], "verislop.backend.vscore/0.3")
                self.assertEqual(schemas.validate("run-report-v3", report), [])
                self.assertEqual(pkg.meta()["run_parameters"]["backend_version"], "0.3")

    def test_python_explicit_and_omitted_tiers_preserve_default_selection(self):
        for name, flags, requested in (("python0", ("--tier", "0", "--target", "python"), 0),
                                      ("default-python", (), None)):
            with self.subTest(tier=requested):
                code, result, report, pkg, count = self._startup(name, flags)
                self.assertEqual(code, 3)
                self._assert_transport_reached(result, report, pkg, count)
                self.assertEqual(schemas.validate("report", report), [])
                self.assertNotIn("format", report)
                self.assertNotIn("backend", report)
                self.assertEqual(pkg.meta()["run_parameters"]["target"], "python")
                self.assertEqual(pkg.meta()["run_parameters"]["tier"], requested)
                self.assertEqual(report["tier"]["requested"], requested)
                self.assertFalse(report["tier"]["tier_default_applied"])
                # Early termination has not materialized an implementation. The
                # real generator resolver still applies the existing Tier0 rule.
                params, diagnostics = generate.resolve_parameters(pkg, requested, "python", None, None, None)
                self.assertEqual(diagnostics, [])
                self.assertEqual((params["tier"], params["endpoint"]), (0, "test_campaign"))
                self.assertEqual(params["tier_default_applied"], requested is None)

    def test_source_v2_does_not_become_a_registered_pipeline_backend(self):
        code, result, report, pkg, count = self._startup("unsupported-v2", (
            "--tier", "2", "--target", "vscore", "--endpoint", "restricted_source", "--backend-version", "0.2"))
        self.assertEqual(code, 3)
        self._assert_transport_reached(result, report, pkg, count)
        self.assertEqual(pkg.meta()["run_parameters"]["backend_version"], "0.2")
        self.assertIn("UNSUPPORTED_CAPABILITY", codes(result))
        self.assertIn("UNSUPPORTED_CAPABILITY", {d["code"] for d in report["blocking_reasons"]})
        self.assertFalse(capability(2, "vscore", "restricted_source", backend_version="0.2")[0])
        self.assertEqual(schemas.validate("report", report), [])
        self.assertNotIn("backend", report)
        self.assertNotIn("language", report)
        self.assertNotIn("format", report)

    def test_unknown_v2_with_missing_profile_reports_both_blocks_before_transport(self):
        code, result, report, pkg, count = self._startup("unsupported-v2-missing-profile", (
            "--tier", "2", "--target", "vscore", "--endpoint", "restricted_source", "--backend-version", "0.2"),
            profile_file="missing")
        self.assertEqual((code, result["status"], count), (2, "BLOCKED", 0))
        self.assertEqual(self.calls, [])
        self.assertIn("CONFIGURATION_INVALID", codes(result))
        self.assertIn("UNSUPPORTED_CAPABILITY", codes(result))
        self.assertIn("UNSUPPORTED_CAPABILITY", {d["code"] for d in report["blocking_reasons"]})
        self.assertEqual(report["terminal_status"], "BLOCKED")
        self.assertEqual(schemas.validate("report", report), [])
        self.assertEqual(pkg.meta()["run_parameters"]["backend_version"], "0.2")
        self.assertNotIn("backend", report)
        self.assertNotIn("language", report)
        self.assertNotIn("format", report)

    def test_v2_advisory_authoring_remains_available_without_a_pipeline_backend(self):
        root = self.tmp.path / "v2-source"
        root.mkdir()
        surface = root / "program.vsc"
        surface.write_text('program "vscore/0.2" profile "pure-data/0.2"; entry echo(n:Nat)->Nat{n}\n')
        delivered = root / "program.vscore.json"
        code, result, error = run_cli("vscore", "compile", "--package", str(root),
                                     "--source", str(surface), "--out", str(delivered))
        self.assertEqual((code, result["status"], error), (0, "PASS", ""))
        self.assertEqual(result["summary"]["language"], "vscore/0.2")
        self.assertFalse(result["summary"]["authoritative"])
        code, result, error = run_cli("vscore", "parse", "--package", str(root), "--source", str(delivered))
        self.assertEqual((code, result["status"], error), (0, "PASS", ""))
        self.assertEqual(result["summary"]["program"]["language"], "vscore/0.2")
        self.assertFalse(result["asserts_closure_verified"])
        code, result, error = run_cli("vscore", "goal", "--package", str(root), "--source", str(delivered),
                                     "--relation", str(root / "unused-relation.json"), "--out", str(root / "bridge"))
        self.assertEqual((code, result["status"], error), (2, "BLOCKED", ""))
        self.assertIn("UNSUPPORTED_CAPABILITY", codes(result))
        self.assertFalse((root / "bridge").exists())


if __name__ == "__main__":
    unittest.main()
