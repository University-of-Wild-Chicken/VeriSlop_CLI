"""Preparation positives replay real Lean acceptance; no service or fabricated proof."""

from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import EX, build, copy_pkg, run_cli
from verislop import canonical, fsutil
from verislop.bridges import prepare
from verislop.bridges.manifest import InvalidPackage
from verislop.bridges.publish import publish, record_preparation
from verislop.events import EventSink
from verislop.errors import Diagnostic
from verislop.package import Package
from verislop.stage import StageResult


def overwrite(path: Path, data: bytes) -> None:
    """Deliberately corrupt a read-only fixture as its owning adversarial user."""
    path.chmod(0o644)
    path.write_bytes(data)


class PreparationWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name) / "accepted"
        stages = build(cls.base, "export")
        failures = {name: result for name, result in stages.items() if result[0] != 0}
        if failures:
            raise AssertionError(f"real accepted-contract fixture did not pass: {failures}")
        cls.prepared = Path(cls.temporary.name) / "prepared"
        copy_pkg(cls.base, cls.prepared)
        original = prepare.import_contract
        def capture(root):
            cls.imported = original(root)
            return cls.imported
        pkg = Package(cls.prepared)
        with patch.object(prepare, "import_contract", side_effect=capture):
            cls.preparation = prepare.run(pkg, EventSink(pkg.run_id, quiet=True),
                                          EX / "bridge-proposal/proposal.json", EX / "bridge-proposal")
        if cls.preparation.status != "PASS":
            raise AssertionError(cls.preparation.to_json())
        cls.bid = cls.preparation.summary["bridge_id"]

    def setUp(self):
        self.temporary_case = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_case.cleanup)
        self.root = Path(self.temporary_case.name) / "run"
        copy_pkg(self.prepared, self.root)
        self.candidate = Path(self.temporary_case.name) / "candidate"
        copy_pkg(EX / "bridge-proposal", self.candidate)
        self.proposal_path = self.candidate / "proposal.json"
        self.pkg = Package(self.root)
        self.bundle = self.root / "bridges" / self.bid

    def run_prepare(self, **kw):
        return prepare.run(self.pkg, EventSink(self.pkg.run_id, quiet=True), self.proposal_path, self.candidate, **kw)

    def proposal(self, change):
        p = canonical.load_file(self.proposal_path)
        change(p)
        self.proposal_path.write_bytes(canonical.dumps(p))

    def blocked(self, result, code=None):
        self.assertEqual(result.status, "BLOCKED", result.to_json())
        self.assertFalse(result.summary["semantic_acceptance"])
        self.assertFalse(result.summary["assigns_end_to_end_verified"])
        if code:
            self.assertIn(code, {d.code for d in result.diagnostics}, result.to_json())

    def test_real_preparation_contains_supervisor_claim_and_no_semantic_acceptance(self):
        result = self.preparation
        self.assertTrue(result.summary["accepted_contract_replayed"])
        self.assertEqual(result.summary["required_obligations"], ["E1", "I2", "O17"])
        self.assertFalse(result.summary["semantic_acceptance"])
        plan = canonical.load_file(self.bundle / "plan.json")
        structural = next(c for c in plan["claims"] if c["claim_id"].startswith("BRIDGE:structure:"))
        self.assertEqual(structural["verifier_id"], prepare.VERIFIER)
        self.assertEqual(structural["result_predicate"], "bridge-structural/0.1")
        self.assertEqual(self.pkg.meta()["bridge_preparations"][self.bid], f"bridges/{self.bid}")
        self.assertTrue(all(p.stat().st_mode & 0o222 == 0 for p in self.bundle.rglob("*") if p.is_file()))

    def test_verify_preparation_replays_real_contract_and_is_read_only(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = prepare.verify_preparation(self.pkg, self.bid)
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertTrue(result.summary["accepted_contract_replayed"])
        self.assertFalse(result.summary["semantic_acceptance"])
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_same_inputs_in_distinct_real_run_copies_reproduce_input_roots(self):
        copy_pkg(self.base, self.root)
        self.pkg = Package(self.root)
        code, result, err = run_cli("bridge", "prepare", "--package", str(self.root),
                                   "--proposal", os.path.relpath(EX / "bridge-proposal/proposal.json"),
                                   "--candidate-dir", os.path.relpath(EX / "bridge-proposal"))
        self.assertEqual(code, 0, (result, err))
        self.assertFalse(result["summary"]["semantic_acceptance"])
        for name in ("plan.json", "artifacts.json", prepare.RECEIPT):
            self.assertEqual((self.bundle / name).read_bytes(), (self.prepared / "bridges" / self.bid / name).read_bytes())

    def test_existing_id_is_no_clobber_even_if_candidate_changes(self):
        before = (self.bundle / "plan.json").read_bytes()
        (self.candidate / "candidate/program.txt").write_text("changed implementation")
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare(), "INPUT_MUTATION")
        self.assertEqual((self.bundle / "plan.json").read_bytes(), before)

    def test_request_scope_mismatch_rejected_before_replay(self):
        self.proposal(lambda p: p.update(bridge_id="fresh"))
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare(expected_tier=3), "SCOPE_LEAK")
            self.blocked(self.run_prepare(expected_endpoint="native_binary"), "SCOPE_LEAK")
        self.assertFalse((self.root / "bridges/fresh").exists())

    def test_untrusted_id_and_reserved_slot_rejected(self):
        self.proposal(lambda p: p.update(bridge_id="nested/escape"))
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare())
        self.proposal(lambda p: (p.update(bridge_id="fresh"), p["artifacts"][0].update(slot_id="contract-model")))
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare())

    def test_candidate_symlink_and_hardlink_rejected_before_replay(self):
        self.proposal(lambda p: p.update(bridge_id="fresh"))
        artifact = self.candidate / "candidate/program.txt"
        outside = Path(self.temporary_case.name) / "outside"
        outside.write_bytes(artifact.read_bytes())
        artifact.unlink()
        artifact.symlink_to(outside)
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare())
            artifact.unlink()
            os.link(outside, artifact)
            self.blocked(self.run_prepare())

    def test_symlink_destination_parent_rejected_without_touching_target(self):
        fsutil.remove_tree(self.root / "bridges")
        outside = Path(self.temporary_case.name) / "outside"
        outside.mkdir()
        (outside / "sentinel").write_text("unchanged")
        (self.root / "bridges").symlink_to(outside, target_is_directory=True)
        # Clear only bookkeeping so the directory check is the rejection.
        meta = self.pkg.meta()
        meta.pop("bridge_preparations", None)
        overwrite(self.root / "package.json", canonical.dumps(meta))
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare())
        self.assertEqual(list(outside.iterdir()), [outside / "sentinel"])

    def test_bad_bookkeeping_rejected_before_publication(self):
        self.proposal(lambda p: p.update(bridge_id="fresh"))
        for bad in ([], {"fresh": "../outside"}, {"nested/path": "bridges/nested/path"}):
            meta = canonical.load_file(self.root / "package.json")
            meta["bridge_preparations"] = bad
            overwrite(self.root / "package.json", canonical.dumps(meta))
            with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
                self.blocked(self.run_prepare())
            self.assertFalse((self.root / "bridges/fresh").exists())

    def test_mutated_frozen_input_blocks_before_replay(self):
        overwrite(self.bundle / "candidate-inputs/candidate/program.txt", b"tampered")
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(prepare.verify_preparation(self.pkg, self.bid), "INPUT_MUTATION")

    def test_mutated_source_accepted_ir_is_not_reused(self):
        overwrite(self.pkg.path("accepted_ir"), b"{}")
        self.blocked(prepare.verify_preparation(self.pkg, self.bid))

    def test_wrong_preparation_checker_and_pending_claim_omission_rejected(self):
        path = self.bundle / prepare.CERTIFICATE
        original = canonical.load_file(path)
        for change in (lambda c: c["checker"].update(verifier_hash="sha256:" + "0" * 64),
                       lambda c: c.update(pending_semantic_claims=["unrelated"])):
            cert = copy.deepcopy(original)
            change(cert)
            overwrite(path, canonical.dumps(cert))
            # This is a negative binding test over an earlier *real* import;
            # successful verification positives above always execute Lean.
            with patch.object(prepare, "import_contract", return_value=self.imported):
                self.blocked(prepare.verify_preparation(self.pkg, self.bid))

    def test_claiming_semantic_success_in_descriptor_is_rejected(self):
        path = self.bundle / prepare.CERTIFICATE
        cert = canonical.load_file(path)
        cert["semantic_acceptance"] = True
        overwrite(path, canonical.dumps(cert))
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(prepare.verify_preparation(self.pkg, self.bid))

    def test_reserved_import_output_path_cannot_replace_accepted_ir(self):
        imported = copy.deepcopy(self.imported)
        data = imported.files.pop(imported.ir_path)
        imported.ir_path = prepare.CERTIFICATE
        imported.files[imported.ir_path] = data
        proposed = canonical.load_file(self.proposal_path)
        candidates = {a["path"]: (self.candidate / a["path"]).read_bytes() for a in proposed["artifacts"]}
        with self.assertRaises(InvalidPackage):
            prepare._assemble(imported, proposed, self.proposal_path.read_bytes(), candidates)

    def test_package_metadata_hardlink_blocks_before_replay(self):
        self.proposal(lambda p: p.update(bridge_id="fresh"))
        os.link(self.root / "package.json", Path(self.temporary_case.name) / "metadata-link")
        with patch.object(prepare, "import_contract", side_effect=AssertionError("must reject before replay")):
            self.blocked(self.run_prepare())

    def test_cli_verify_and_tamper_roundtrip(self):
        code, result, err = run_cli("bridge", "verify", "--package", str(self.root), "--bridge-id", self.bid)
        self.assertEqual(code, 0, (result, err))
        self.assertFalse(result["summary"]["semantic_acceptance"])
        overwrite(self.bundle / "artifacts.json", b"{}")
        code, result, err = run_cli("bridge", "verify", "--package", str(self.root), "--bridge-id", self.bid)
        self.assertEqual(code, 2, (result, err))


class PublicationDiscipline(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "run"
        self.root.mkdir()
        (self.root / "package.json").write_bytes(canonical.dumps({"run_id": "test-run"}))

    def test_no_clobber_including_empty_directory_and_symlink(self):
        target = self.root / "bridges" / "same"
        target.mkdir(parents=True)
        with self.assertRaises(InvalidPackage):
            publish(self.root, "same", {"file": b"candidate"})
        self.assertEqual(list(target.iterdir()), [])
        target.rmdir()
        outside = Path(self.temporary.name) / "outside"
        outside.write_text("safe")
        target.symlink_to(outside)
        with self.assertRaises(InvalidPackage):
            publish(self.root, "same", {"file": b"candidate"})
        self.assertEqual(outside.read_text(), "safe")
        self.assertFalse(list((self.root / "bridges").glob(".preparing-*")))

    def test_failed_atomic_publish_leaves_no_partial_attempt(self):
        with patch("verislop.bridges.publish._rename_noreplace", side_effect=OSError("forced failure")):
            with self.assertRaises(OSError):
                publish(self.root, "new", {"a/b": b"complete inputs"})
        self.assertFalse((self.root / "bridges/new").exists())
        self.assertEqual(list((self.root / "bridges").iterdir()), [])

    def test_metadata_writer_never_follows_or_chmods_link(self):
        outside = Path(self.temporary.name) / "outside"
        original = (self.root / "package.json").read_bytes()
        outside.write_bytes(original)
        outside.chmod(0o400)
        (self.root / "package.json").unlink()
        (self.root / "package.json").symlink_to(outside)
        with self.assertRaises(InvalidPackage):
            record_preparation(self.root, "new", "test-run")
        self.assertEqual(outside.read_bytes(), original)
        self.assertEqual(outside.stat().st_mode & 0o777, 0o400)

    def test_publication_helper_rejects_nested_ids(self):
        with self.assertRaises(InvalidPackage):
            publish(self.root, "../outside", {"file": b"candidate"})
        self.assertFalse((Path(self.temporary.name) / "outside").exists())


class PreparationInventory(unittest.TestCase):
    """Cheap inventory tests; no Lean fixture or fabricated semantic acceptance."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.meta = {"run_id": "inventory-test"}
        self.save()
        self.pkg = Package(self.root)

    def save(self):
        (self.root / "package.json").write_bytes(canonical.dumps(self.meta))

    def marker(self, bid="orphan", filename=prepare.CERTIFICATE):
        folder = self.root / "bridges" / bid
        folder.mkdir(parents=True)
        (folder / filename).write_bytes(b"{}")

    def check(self):
        with patch.object(prepare, "verify_preparation", side_effect=AssertionError("no indexed ID should be evaluated")):
            results, diagnostics = prepare.verify_preparations(self.pkg)
        self.assertEqual(results, [])
        return {d.code for d in diagnostics}

    def test_missing_index_cannot_hide_requested_preparation(self):
        self.meta["run_parameters"] = {"bridge_proposal": "/original/proposal.json"}
        self.save()
        self.assertIn("VERIFIER_NOT_RUN", self.check())

    def test_empty_index_cannot_hide_completed_preparation(self):
        self.meta.update(bridge_preparations={}, stage_history=[{"stage": "bridge:prepare", "status": "PASS"}])
        self.save()
        self.assertIn("VERIFIER_NOT_RUN", self.check())

    def test_completed_stage_cannot_hide_behind_deleted_history(self):
        self.meta["completed_stages"] = ["bridge:prepare"]
        self.save()
        self.assertIn("VERIFIER_NOT_RUN", self.check())

    def test_unindexed_descriptor_or_partial_bundle_is_detected(self):
        self.marker()
        self.marker("partial", "plan.json")
        self.assertIn("ORPHAN_CLAIM", self.check())

    def test_legacy_tier1_and_link_records_are_not_preparation_bundles(self):
        folder = self.root / "bridges/tier1"
        folder.mkdir(parents=True)
        (folder / "placement.json").write_bytes(b"{}")
        (folder.parent / "bindings.json").write_bytes(b"{}")
        (folder.parent / "link.json").write_bytes(b"{}")
        self.assertEqual(self.check(), set())

    def test_index_redirect_is_rejected_even_when_bundle_exists(self):
        self.marker("known")
        self.meta["bridge_preparations"] = {"known": "../elsewhere"}
        self.save()
        self.assertTrue({"INVALID_CANDIDATE", "ORPHAN_CLAIM"}.issubset(self.check()))

    def test_symbolic_link_inventory_entry_is_not_followed(self):
        (self.root / "bridges").mkdir()
        (self.root / "bridges/unknown").symlink_to(self.root, target_is_directory=True)
        self.assertIn("INVALID_CANDIDATE", self.check())

    def test_indexed_verification_diagnostics_are_collected_once(self):
        self.marker("known")
        self.meta["bridge_preparations"] = {"known": "bridges/known"}
        self.save()
        diagnostic = Diagnostic("INPUT_MUTATION", "negative fixture verifier result")
        blocked = StageResult("bridge verify", "BLOCKED", prepare.GATE, diagnostics=[diagnostic])
        with patch.object(prepare, "verify_preparation", return_value=blocked) as verifier:
            results, diagnostics = prepare.verify_preparations(self.pkg)
        verifier.assert_called_once_with(self.pkg, "known")
        self.assertEqual(results, [blocked])
        self.assertEqual(diagnostics, [diagnostic])


if __name__ == "__main__":
    unittest.main()
