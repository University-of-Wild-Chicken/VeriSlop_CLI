"""CLI selection/retention with generic advisory preview fixtures, no model or Lean."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from verislop import canonical, cli
from verislop.bridges import vscore3_checker as checker
from verislop.errors import UsageError
from verislop.package import Package
from verislop.targets import vscore3_source as source, vscore3_target as target

SELECTION = "support/readable/selection.json"


class ReadableCLITests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="verislop-readable-cli-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.pkg = Package(self.root / "run")
        self.pkg.ensure("generic-readable-cli")
        src = self.root / "program.json"
        src.write_bytes(source.compile_surface(
            'program "vscore/0.3" profile "data-pipeline/0.3"; entry echo(x:Bool)->Bool{x}'))
        rel = self.root / "relation.json"
        rel.write_bytes(canonical.dumps({"schema_version": "0.3", "format": target.RELATION_FORMAT,
                                        "template": target.TEMPLATE, "source_slot": "vscore-source",
                                        "proof_slot": "vscore-proof", "bindings": [{"symbol": "echo", "entry": "echo"}]}))
        self.args = SimpleNamespace(source=str(src), vscore_action="goal", package=str(self.pkg.root),
                                    relation=str(rel), proof=None, bridge_id=None, obligation=[],
                                    out=str(self.root / "out"), readable_view=False, readable_selection=None)
        self.selection = canonical.dumps({"fixture": "selected source support"})
        self.meta = {SELECTION: self.selection, "support/readable/diagnostic.json": b"frozen fixture diagnostic"}
        self.info = {"proposition_hash": "sha256:" + "a" * 64, "model": b"{}", "profile": b"{}",
                     "readable_selection": self.selection, "readable_candidate_artifacts": self.meta,
                     "readable_artifacts": {"readable/ReadableSource.lean": b"generic readable fixture"},
                     "readable_source_view": {"selected_mode": "BASE", "authoritative": False}}
        self.spec = SimpleNamespace(text="generic fixture goal")
        self.constants = patch.object(checker, "READABLE_SELECTION_PATH", SELECTION, create=True)
        self.constants.start()
        self.addCleanup(self.constants.stop)

    def write_metadata(self):
        for name, data in self.meta.items():
            path = self.root / "candidate" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.args.readable_selection = str(self.root / "candidate" / SELECTION)

    def test_explicit_first_selection_retains_artifacts_and_hides_byte_maps(self):
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)) as preview:
            result = cli.cmd_vscore(self.args)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(preview.call_args.kwargs, {"select_readable": True})
        for name, data in {**self.meta, **self.info["readable_artifacts"]}.items():
            self.assertEqual((Path(self.args.out) / name).read_bytes(), data)
        self.assertEqual(result.summary["readable_selection"]["sha256"], canonical.digest(self.selection))
        self.assertFalse(result.summary["readable_selection"]["authoritative"])
        self.assertNotIn("readable_artifacts", result.summary)
        canonical.dumps(result.to_json())

    def test_replay_passes_exact_selection_and_frozen_diagnostics(self):
        self.write_metadata()
        with patch.object(checker, "readable_candidate_metadata", return_value=self.meta, create=True), \
             patch.object(checker, "preview", return_value=(self.spec, None, self.info)) as preview:
            result = cli.cmd_vscore(self.args)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(preview.call_args.kwargs, {
            "readable_selection": self.selection,
            "readable_diagnostics": {"support/readable/diagnostic.json": b"frozen fixture diagnostic"}})

    def test_replayed_metadata_substitution_blocks_before_output(self):
        self.write_metadata()
        changed = {**self.info, "readable_candidate_artifacts": {SELECTION: self.selection}}
        with patch.object(checker, "readable_candidate_metadata", return_value=self.meta, create=True), \
             patch.object(checker, "preview", return_value=(self.spec, None, changed)):
            result = cli.cmd_vscore(self.args)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertFalse(Path(self.args.out).exists())

    def test_selection_mutation_during_preview_blocks_before_output(self):
        self.write_metadata()

        def preview(*args, **kwargs):
            Path(self.args.readable_selection).write_bytes(b"substituted selection")
            return self.spec, None, self.info

        with patch.object(checker, "readable_candidate_metadata", return_value=self.meta, create=True), \
             patch.object(checker, "preview", side_effect=preview):
            result = cli.cmd_vscore(self.args)
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "INPUT_MUTATION")
        self.assertFalse(Path(self.args.out).exists())

    def test_first_selection_with_proof_is_invalid_invocation(self):
        self.args.readable_view = True
        self.args.proof = str(self.root / "unused-proof.lean")
        with patch.object(checker, "preview") as preview, self.assertRaises(UsageError):
            cli.cmd_vscore(self.args)
        preview.assert_not_called()

    def test_legacy_reuse_rejects_stale_selection_before_writing(self):
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)):
            self.assertEqual(cli.cmd_vscore(self.args).status, "PASS")
        out = Path(self.args.out)
        before = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        self.args.readable_view = False
        legacy_info = {"proposition_hash": "sha256:" + "b" * 64, "model": b"changed", "profile": b"{}"}
        with patch.object(checker, "preview", return_value=(SimpleNamespace(text="changed goal"), None, legacy_info)), \
             self.assertRaisesRegex(UsageError, "stale readable output artifact"):
            cli.cmd_vscore(self.args)
        self.assertEqual(before, {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()})

    def test_selected_reuse_rejects_orphan_diagnostic_before_writing(self):
        out = Path(self.args.out)
        stale = out / "support/readable/old-diagnostic.json"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"old diagnostic")
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)), \
             self.assertRaisesRegex(UsageError, "stale readable output artifact"):
            cli.cmd_vscore(self.args)
        self.assertEqual(stale.read_bytes(), b"old diagnostic")
        self.assertFalse((out / "VeriSlopBridgeGoal.lean").exists())

    def test_exact_inventory_reuse_remains_supported(self):
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)):
            self.assertEqual(cli.cmd_vscore(self.args).status, "PASS")
            self.assertEqual(cli.cmd_vscore(self.args).status, "PASS")

    def test_symlinked_readable_tree_rejects_before_writing(self):
        out = Path(self.args.out)
        out.mkdir()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (out / "readable").symlink_to(elsewhere, target_is_directory=True)
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)), \
             self.assertRaisesRegex(UsageError, "symlink"):
            cli.cmd_vscore(self.args)
        self.assertFalse((out / "VeriSlopBridgeGoal.lean").exists())

    def test_symlinked_support_parent_rejects_before_writing(self):
        out = Path(self.args.out)
        out.mkdir()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (out / "support").symlink_to(elsewhere, target_is_directory=True)
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)), \
             self.assertRaisesRegex(UsageError, "symlink"):
            cli.cmd_vscore(self.args)
        self.assertFalse((out / "VeriSlopBridgeGoal.lean").exists())

    def test_directory_at_declared_artifact_rejects_before_writing(self):
        out = Path(self.args.out)
        (out / SELECTION).mkdir(parents=True)
        (out / "VeriSlopBridgeGoal.lean").write_bytes(b"prior goal")
        before = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        self.args.readable_view = True
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)), \
             self.assertRaisesRegex(UsageError, "not a regular file"):
            cli.cmd_vscore(self.args)
        self.assertEqual(before, {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
