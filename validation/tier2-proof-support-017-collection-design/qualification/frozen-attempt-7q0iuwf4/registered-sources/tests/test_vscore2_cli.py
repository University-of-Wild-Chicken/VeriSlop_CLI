"""Authoring commands retain an explicit boundary from kernel source admission and bridges."""
from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import REPO, codes, run_cli
from verislop.targets import vscore2_source as src


class VSCore2CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-vscore2-cli-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.surface = self.root / "program.vsc"
        self.delivered = self.root / "program.vscore.json"
        self.surface.write_text('program "vscore/0.2" profile "pure-data/0.2";\nfn inc(n:Nat)->Nat{n+1}\nentry total(xs:List(Nat))->Nat{call inc(List.fold(xs,0;acc,item=>acc+item))}\n')

    def compile(self):
        return run_cli("vscore", "compile", "--source", str(self.surface), "--out", str(self.delivered))

    def test_surface_compile_and_host_parse_are_explicitly_advisory(self):
        code, result, error = self.compile()
        self.assertEqual((code, result["status"], error), (0, "PASS", ""))
        self.assertFalse(result["summary"]["authoritative"])
        self.assertFalse(result["asserts_closure_verified"])
        self.assertEqual(result["summary"]["required_features"], ["base", "list", "acyclicCalls", "listFold"])
        self.assertEqual(self.delivered.read_bytes(), src.compile_surface(self.surface.read_text()))
        code, result, error = run_cli("vscore", "parse", "--source", str(self.delivered))
        self.assertEqual((code, result["status"], error), (0, "PASS", ""))
        self.assertFalse(result["summary"]["authoritative"])
        self.assertFalse(result["asserts_closure_verified"])
        self.assertEqual(result["summary"]["signatures"], [{"id": "total", "params": [{"list": "nat"}], "result": "nat"}])
        self.assertEqual(result["summary"]["program"]["entries"][0]["body"]["args"][0]["step"]["left"]["index"], 1)

    def test_surface_is_not_silently_treated_as_certified_canonical_json(self):
        for command in ("parse", "check"):
            with self.subTest(command=command):
                code, result, error = run_cli("vscore", command, "--source", str(self.surface))
                self.assertNotEqual(code, 0)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("INVALID_CANDIDATE", codes(result))
                self.assertFalse(result["asserts_closure_verified"])
                self.assertEqual(error, "")

    def test_failed_authoring_does_not_write_a_delivered_artifact(self):
        self.surface.write_text('program "vscore/0.2" profile "pure-data/0.2"; fn loop()->Nat{if false then call loop() else 0} entry run()->Nat{0}')
        code, result, error = self.compile()
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("INVALID_CANDIDATE", codes(result))
        self.assertFalse(self.delivered.exists())
        self.assertEqual(error, "")

    def test_old_source_parse_dispatch_is_preserved(self):
        profile = self.root / "profile.json"
        profile.write_text('{"enums":{"IncrementError":{"constructors":["limitReached"]}}}')
        code, result, error = run_cli("vscore", "parse", "--source", str(REPO / "examples/vscore/program.vscore.json"), "--profile", str(profile))
        self.assertEqual((code, result["status"], error), (0, "PASS", ""))
        self.assertEqual(result["summary"]["program"]["language"], "vscore/0.1")
        self.assertFalse(result["summary"]["authoritative"])

    def test_malformed_profiles_and_missing_input_paths_are_diagnostics(self):
        for value in ([], {"enums": []}, {"enums": {"E": []}},
                      {"enums": {"E": {"constructors": "a"}}},
                      {"enums": {"E": {"constructors": [1]}}},
                      {"enums": {"E": {"constructors": []}}},
                      {"enums": {"E": {"constructors": ["a", "a"]}}}):
            with self.subTest(profile=value):
                profile = self.root / "bad-profile.json"
                profile.write_text(json.dumps(value))
                code, result, error = run_cli("vscore", "compile", "--source", str(self.surface),
                    "--out", str(self.delivered), "--profile", str(profile))
                self.assertNotEqual(code, 0)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("INVALID_CANDIDATE", codes(result))
                self.assertFalse(self.delivered.exists())
                self.assertEqual(error, "")
        for command in ("parse", "check"):
            code, result, error = run_cli("vscore", command, "--source", str(self.root / "missing-source"))
            self.assertNotEqual(code, 0)
            self.assertIn("INVALID_CANDIDATE", codes(result))
            self.assertEqual(error, "")
        code, result, error = run_cli("vscore", "compile", "--source", str(self.surface), "--out", str(self.delivered),
                                     "--profile", str(self.root / "missing-profile"))
        self.assertNotEqual(code, 0)
        self.assertIn("INVALID_CANDIDATE", codes(result))
        self.assertEqual(error, "")

    def test_output_write_failure_is_an_infrastructure_diagnostic(self):
        code, result, error = run_cli("vscore", "compile", "--source", str(self.surface), "--out", str(self.root))
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "INFRASTRUCTURE_FAILURE")
        self.assertIn("VERIFIER_FAILURE", codes(result))
        self.assertEqual(error, "")

    def test_missing_bridge_and_wrong_source_check_version_are_capability_errors(self):
        code, result, _ = self.compile()
        self.assertEqual(code, 0, result)
        code, result, error = run_cli("vscore", "goal", "--source", str(self.delivered),
                                     "--relation", str(self.root / "missing-relation.json"), "--out", str(self.root / "bridge"))
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("UNSUPPORTED_CAPABILITY", codes(result))
        self.assertFalse((self.root / "bridge").exists())
        self.assertEqual(error, "")
        code, result, error = run_cli("vscore", "check", "--source", str(REPO / "examples/vscore/program.vscore.json"))
        self.assertNotEqual(code, 0)
        self.assertIn("UNSUPPORTED_CAPABILITY", codes(result))
        self.assertEqual(error, "")


if __name__ == "__main__":
    unittest.main()
