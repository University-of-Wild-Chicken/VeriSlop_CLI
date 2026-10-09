"""Candidate-created links must not change host files during staged cleanup."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from verislop import fsutil


class SafeCleanup(unittest.TestCase):
    def test_nested_symlinks_and_hardlinks_do_not_change_host_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            outside = parent / "outside"
            outside.mkdir()
            secret = outside / "secret"
            secret.write_text("unchanged")
            secret.chmod(0o400)
            stage = parent / "stage"
            stage.mkdir()
            (stage / "file-link").symlink_to(secret)
            (stage / "directory-link").symlink_to(outside, target_is_directory=True)
            os.link(secret, stage / "hardlink")
            fsutil.remove_tree(stage)
            self.assertFalse(stage.exists())
            self.assertEqual(secret.read_text(), "unchanged")
            self.assertEqual(stat.S_IMODE(secret.stat().st_mode), 0o400)

    def test_root_symlink_is_unlinked_without_removing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            outside = parent / "outside"
            outside.mkdir()
            (outside / "secret").write_text("unchanged")
            link = parent / "stage"
            link.symlink_to(outside, target_is_directory=True)
            fsutil.remove_tree(link)
            self.assertFalse(link.is_symlink())
            self.assertEqual((outside / "secret").read_text(), "unchanged")

    def test_readonly_files_can_be_removed_without_chmod(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            stage.mkdir()
            readonly = stage / "readonly"
            readonly.write_text("candidate")
            readonly.chmod(0o444)
            fsutil.remove_tree(stage)
            self.assertFalse(stage.exists())

    def test_temporary_stage_does_not_chmod_failed_symlink_unlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            secret = parent / "outside"
            secret.write_text("unchanged")
            secret.chmod(0o400)
            stage = None
            try:
                with fsutil.temporary_directory(dir=parent) as name:
                    stage = Path(name)
                    locked = stage / "locked"
                    locked.mkdir()
                    (locked / "link").symlink_to(secret)
                    locked.chmod(0o500)
            except PermissionError:
                # Safe failure is allowed; cleanup must never chmod the outside target.
                pass
            finally:
                self.assertEqual(secret.read_text(), "unchanged")
                self.assertEqual(stat.S_IMODE(secret.stat().st_mode), 0o400)
                if stage is not None and stage.exists():
                    (stage / "locked").chmod(0o700)
                    fsutil.remove_tree(stage)
