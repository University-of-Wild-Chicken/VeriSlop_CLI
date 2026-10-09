"""Untrusted run paths cannot redirect supervisor lock or event writes."""

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import codes, run_cli

from verislop import fsutil
from verislop.errors import VeriSlopError
from verislop.events import EventSink
from verislop.package import Package


class SafeRunSetup(unittest.TestCase):
    def test_lock_rejects_links_and_special_files_before_writing(self):
        for kind in ("symlink", "hardlink", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = root / "run"
                package.mkdir()
                outside = root / "outside"
                outside.write_bytes(b"unchanged")
                lock = package / ".verislop.lock"
                if kind == "symlink":
                    lock.symlink_to(outside)
                elif kind == "hardlink":
                    os.link(outside, lock)
                else:
                    os.mkfifo(lock)
                with self.assertRaises(VeriSlopError) as caught:
                    with fsutil.package_lock(package):
                        self.fail("unsafe lock was accepted")
                self.assertEqual(caught.exception.diagnostics[0].code, "INPUT_MUTATION")
                self.assertEqual(outside.read_bytes(), b"unchanged")

    def test_lock_rejects_symlink_ancestor_before_creating_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (root / "alias").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(VeriSlopError):
                with fsutil.package_lock(root / "alias" / "run"):
                    self.fail("symlink ancestor was accepted")
            self.assertEqual(list(outside.iterdir()), [])

    def test_lock_remains_exclusive_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "new" / "run"
            with fsutil.package_lock(package):
                with self.assertRaises(VeriSlopError) as caught:
                    with fsutil.package_lock(package):
                        self.fail("second writer was accepted")
                self.assertEqual(caught.exception.diagnostics[0].code, "RUN_LOCKED")
            with fsutil.package_lock(package):
                self.assertEqual((package / ".verislop.lock").read_text(), str(os.getpid()))

    def test_bridge_cli_rejects_unsafe_lock_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "run"
            Package(package).ensure("test")
            outside = root / "outside"
            outside.write_bytes(b"unchanged")
            (package / ".verislop.lock").symlink_to(outside)
            code, result, _ = run_cli("bridge", "prepare", "--package", str(package),
                                       "--proposal", "examples/bridge-proposal/proposal.json",
                                       "--candidate-dir", "examples/bridge-proposal")
            self.assertEqual(code, 2, result)
            self.assertIn("INPUT_MUTATION", codes(result))
            self.assertEqual(outside.read_bytes(), b"unchanged")

    def test_event_log_rejects_links_and_special_files_before_writing(self):
        for kind in ("symlink", "hardlink", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = root / "run"
                package.mkdir()
                outside = root / "outside"
                outside.write_bytes(b"unchanged")
                log = package / "events.jsonl"
                if kind == "symlink":
                    log.symlink_to(outside)
                elif kind == "hardlink":
                    os.link(outside, log)
                else:
                    os.mkfifo(log)
                with self.assertRaises(VeriSlopError):
                    EventSink("test", package, quiet=True)
                self.assertEqual(outside.read_bytes(), b"unchanged")

    def test_event_log_uses_opened_file_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "run"
            sink = EventSink("test", package, quiet=True)
            log = package / "events.jsonl"
            log.rename(package / "original-log")
            outside = root / "outside"
            outside.write_bytes(b"unchanged")
            log.symlink_to(outside)
            try:
                sink.emit("progress", "test", "safe append")
            finally:
                sink.close()
            self.assertEqual(outside.read_bytes(), b"unchanged")
            self.assertEqual(json.loads((package / "original-log").read_text())["seq"], 1)

    def test_event_sequence_continues_and_explicit_target_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "run"
            package.mkdir()
            log = package / "events.jsonl"
            log.write_text('{}\n{}\n')
            sink = EventSink("test", package, quiet=True)
            try:
                sink.emit("progress", "test")
            finally:
                sink.close()
            self.assertEqual(json.loads(log.read_text().splitlines()[-1])["seq"], 3)
            target = root / "target"
            target.symlink_to(log)
            with self.assertRaises(VeriSlopError):
                EventSink("test", target=str(target), quiet=True)
