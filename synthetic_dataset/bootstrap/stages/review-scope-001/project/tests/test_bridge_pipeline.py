"""Pipeline preparation stays a structural gate and is rechecked on resume."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import EX, TempDir, codes, copy_pkg, run_cli, writable
from verislop import canonical
from verislop.run import _stages_for


class BridgePipelineRouting(unittest.TestCase):
    def test_preparation_stage_is_opt_in_after_export(self):
        ordinary = _stages_for({})
        self.assertNotIn("bridge:prepare", ordinary)
        prepared = _stages_for({"bridge_proposal": "proposal.json"})
        self.assertLess(prepared.index("export"), prepared.index("bridge:prepare"))
        self.assertLess(prepared.index("bridge:prepare"), prepared.index("generate"))

    def test_proposal_and_candidate_root_must_be_supplied_together(self):
        tmp = TempDir()
        self.addCleanup(tmp.cleanup)
        code, result, _ = run_cli("run", "--prompt-file", str(EX / "request.txt"),
                                  "--runs-dir", str(tmp.path / "runs"),
                                  "--bridge-proposal", str(EX / "bridge-proposal" / "proposal.json"))
        self.assertEqual(code, 64, result)
        self.assertFalse((tmp.path / "runs").exists())


class BridgePipelineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.runs = cls.tmp.path / "runs"
        cls.run_id = "bridge-pipeline"
        cls.package = cls.runs / cls.run_id
        cls.code, cls.result, cls.output = run_cli(
            "run", "--runs-dir", str(cls.runs), "--run-id", cls.run_id,
            "--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
            "--tier", "2", "--target", "vscore", "--endpoint", "restricted-source",
            "--draft-candidate", str(EX / "draft.json"),
            "--ledger-candidate", str(EX / "interpretation.json"),
            "--formalization-candidate", str(EX / "formalization"),
            "--bridge-proposal", str(EX / "bridge-proposal" / "proposal.json"),
            "--bridge-candidate-dir", str(EX / "bridge-proposal"), "--non-interactive")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_prepared_generic_bridge_cannot_establish_semantics_or_e2e(self):
        self.assertEqual(self.code, 2, (self.result, self.output))
        self.assertIn("ORPHAN_CLAIM", codes(self.result))
        stages = self.result["summary"]["stages"]
        self.assertEqual(next(s for s in stages if s["stage"] == "bridge:prepare")["status"], "PASS")
        report = canonical.load_file(self.package / "report.json")
        self.assertEqual(report["terminal_status"], "BLOCKED")
        self.assertEqual(report["tier"]["requested"], 2)
        self.assertEqual(report["tier"]["target"], "vscore")
        self.assertEqual(len(report["bridge_preparations"]), 1)
        prepared = report["bridge_preparations"][0]
        self.assertEqual(prepared["status"], "PASS")
        self.assertIs(prepared["semantic_acceptance"], False)
        self.assertIs(prepared["assigns_end_to_end_verified"], False)
        for record in report["obligations"].values():
            self.assertNotEqual(record["outcomes"]["END_TO_END_VERIFIED"], "PASS")

    def test_resume_rechecks_prepared_artifact_before_skipping_completed_stage(self):
        runs = self.tmp.path / "mutated-runs"
        package = copy_pkg(self.package, runs / self.run_id)
        meta = canonical.load_file(package / "package.json")
        bundle_path = next(iter(meta["bridge_preparations"].values()))
        bundle = package / bundle_path
        manifest = canonical.load_file(bundle / "artifacts.json")
        artifact = next(a for a in manifest["artifacts"] if a["role"] == "source")
        source = bundle / artifact["path"]
        writable(source)
        source.write_bytes(source.read_bytes() + b"\nmutated after preparation\n")
        before = len(meta["stage_history"])
        code, result, _ = run_cli("resume", "--runs-dir", str(runs), "--run-id", self.run_id)
        self.assertEqual(code, 2, result)
        self.assertIn("INPUT_MUTATION", codes(result))
        self.assertEqual(len(canonical.load_file(package / "package.json")["stage_history"]), before)

    def test_resume_rejects_removed_preparation_index(self):
        runs = self.tmp.path / "missing-index-runs"
        package = copy_pkg(self.package, runs / self.run_id)
        path = package / "package.json"
        meta = canonical.load_file(path)
        meta.pop("bridge_preparations")
        path.write_bytes(canonical.dumps(meta))
        before = len(meta["stage_history"])
        code, result, _ = run_cli("resume", "--runs-dir", str(runs), "--run-id", self.run_id)
        self.assertEqual(code, 2, result)
        self.assertIn("VERIFIER_NOT_RUN", codes(result))
        self.assertEqual(len(canonical.load_file(path)["stage_history"]), before)
