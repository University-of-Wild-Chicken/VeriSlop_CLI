"""Concrete regressions for frozen source checks and atomic certificate publication."""
from __future__ import annotations

import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from verislop import canonical, verifiers
from verislop.bridges.publish import publish_into
from verislop.bridges.manifest import InvalidPackage
from verislop.package import Package
from verislop.targets import vscore2_check as checker, vscore2_source as src
from tests.helpers import codes, run_cli


class SourceCheckFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-source-check-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.surface = 'program "vscore/0.2" profile "pure-data/0.2"; entry run()->Nat{0}'
        self.data = src.compile_surface(self.surface)

    def test_default_malformed_accepted_profile_is_a_structured_diagnostic(self):
        pkg = Package(self.root / "package")
        pkg.ensure()
        pkg.path("accepted").mkdir()
        source = self.root / "program.vsc"
        source.write_text(self.surface)
        output = self.root / "source.json"
        for accepted in ({}, [], {"artifacts": []}, {"artifacts": {"profile": {"path": 3}}},
                         {"artifacts": {"profile": {"path": "../outside.json"}}}):
            with self.subTest(accepted=accepted):
                (pkg.path("accepted") / "acceptance.json").write_text(json.dumps(accepted))
                code, result, error = run_cli("vscore", "compile", "--package", str(pkg.root),
                    "--source", str(source), "--out", str(output))
                self.assertNotEqual(code, 0)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("INVALID_CANDIDATE", codes(result))
                self.assertEqual(error, "")
                self.assertFalse(output.exists())

    def test_registered_hash_changes_for_executed_policy_and_publication_dependencies(self):
        with patch.object(verifiers, "PKG", self.root):
            for rel in ("policy.py", "bridges/publish.py", "bridges/manifest.py", "cli.py"):
                with self.subTest(dependency=rel):
                    verifiers.verifier_hash.cache_clear()
                    before = verifiers.verifier_hash(checker.VERIFIER)
                    path = self.root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"modified verifier dependency")
                    verifiers.verifier_hash.cache_clear()
                    self.assertNotEqual(before, verifiers.verifier_hash(checker.VERIFIER))
        verifiers.verifier_hash.cache_clear()

    def test_failed_root_level_publication_removes_staging_files(self):
        with patch("verislop.bridges.publish._rename_noreplace", side_effect=OSError(errno.ENOSPC, "full")):
            with self.assertRaises(OSError):
                publish_into(self.root, [], "certificate", {"report.json": b"{}"})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_publication_does_not_replace_an_existing_certificate(self):
        publish_into(self.root, [], "certificate", {"report.json": b"first"})
        with self.assertRaises(InvalidPackage):
            publish_into(self.root, [], "certificate", {"report.json": b"second"})
        self.assertEqual((self.root / "certificate/report.json").read_bytes(), b"first")
        self.assertEqual([p.name for p in self.root.iterdir()], ["certificate"])

    def test_differing_clean_builds_block_without_publication(self):
        tc = Mock()
        tc.identity.return_value = {"pin": "test toolchain"}
        a = checker.Build({"toolchain": tc.identity(), "kernel_export_hash": "a"}, {}, {})
        b = checker.Build({"toolchain": tc.identity(), "kernel_export_hash": "b"}, {}, {})
        out = self.root / "certificate"
        with patch.object(checker.leanbridge, "resolve_toolchain", return_value=tc), \
             patch.object(checker, "run_build", side_effect=[a, b]):
            result = checker.check(self.data, {}, out)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("NONDETERMINISM", {d.code for d in result.diagnostics})
        self.assertFalse(out.exists())
        self.assertNotIn("implementation_ir", result.summary)

    def test_changed_library_after_clean_builds_blocks_without_publication(self):
        tc = Mock()
        tc.identity.return_value = {"pin": "test toolchain"}
        build = checker.Build({"toolchain": tc.identity()}, {}, {})
        out = self.root / "certificate"
        with patch.object(checker.leanbridge, "resolve_toolchain", return_value=tc), \
             patch.object(checker, "library_sources", side_effect=[{"Library": b"first"}, {"Library": b"changed"}]), \
             patch.object(checker, "run_build", return_value=build):
            result = checker.check(self.data, {}, out)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("INPUT_MUTATION", {d.code for d in result.diagnostics})
        self.assertFalse(out.exists())

    def test_caller_registry_mutation_cannot_change_frozen_report(self):
        tc = Mock()
        tc.identity.return_value = {"pin": "test toolchain"}
        registry = {"E": ["before"]}
        build = checker.Build({"toolchain": tc.identity()}, {"enums": [{"id": "E", "constructors": ["before"]}]}, {})
        def mutate_caller(*args):
            registry["E"][0] = "after"
            return build
        with patch.object(checker.leanbridge, "resolve_toolchain", return_value=tc), \
             patch.object(checker, "run_build", side_effect=mutate_caller):
            result = checker.check(self.data, registry)
        self.assertEqual(result.status, "PASS")
        report = result.summary["report"]
        self.assertEqual(report["inputs"]["enums"], {"E": ["before"]})
        self.assertEqual(report["input_root"], canonical.digest_json(report["inputs"]))

    def test_changed_toolchain_identity_blocks_without_publication(self):
        tc = Mock()
        tc.identity.side_effect = [{"pin": "before"}, {"pin": "after"}]
        build = checker.Build({"toolchain": {"pin": "before"}}, {}, {})
        out = self.root / "certificate"
        with patch.object(checker.leanbridge, "resolve_toolchain", return_value=tc), \
             patch.object(checker, "run_build", return_value=build):
            result = checker.check(self.data, {}, out)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("INPUT_MUTATION", {d.code for d in result.diagnostics})
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
