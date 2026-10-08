"""Exact persisted context and failure boundaries; authored fixtures, no model calls."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import agent_memory as memory, canonical
from verislop.errors import BlockedError
from verislop.package import Package


class AgentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "run")
        self.pkg.ensure("memory-fixture")

    def assertBlocked(self, code, function, *args, **kwargs):
        with self.assertRaises(BlockedError) as caught:
            function(*args, **kwargs)
        self.assertEqual(code, caught.exception.diagnostics[0].code)

    def blob(self, manifest, source):
        row = next(row for row in manifest["artifacts"] if row["source_ref"] == source)
        return self.pkg.root / row["blob_ref"]["path"]

    def mutate(self, path, data):
        path.chmod(0o600)
        path.write_bytes(data)

    def test_exact_json_lean_binary_and_empty_bytes_survive_new_process(self):
        artifacts = {"draft/obligations.json": b'{ "entities": [], "ambiguous": true }\n',
                     "contract/proposal.lean": 'import Std\n-- é🙂\ntheorem t : True := by trivial\n'.encode(),
                     "responses/empty.txt": b"", "responses/raw.bin": b"\xff\x00\x80"}
        captured = memory.checkpoint(self.pkg, "formalize:failed:1", artifacts,
                                     metadata={"outcome": "rejected", "diagnostics": ["example"]})
        self.assertEqual(artifacts, memory.restore(Package(self.pkg.root), captured["snapshot_ref"]))
        program = """
import base64,json,sys
from pathlib import Path
from verislop.agent_memory import restore
from verislop.package import Package
values=restore(Package(Path(sys.argv[1])),json.loads(sys.argv[2]))
print(json.dumps({k:base64.b64encode(v).decode('ascii') for k,v in values.items()}))
"""
        result = subprocess.run([sys.executable, "-c", program, str(self.pkg.root),
                                 json.dumps(captured["snapshot_ref"])], check=True, capture_output=True, text=True)
        self.assertEqual(artifacts, {k: base64.b64decode(v) for k, v in json.loads(result.stdout).items()})
        context = memory.context_for(Package(self.pkg.root), last=1)
        self.assertEqual("base64", context["snapshots"][0]["artifacts"]["responses/raw.bin"]["encoding"])
        self.assertEqual(artifacts["contract/proposal.lean"].decode(),
                         context["snapshots"][0]["artifacts"]["contract/proposal.lean"]["content"])

    def test_identical_blobs_are_reused_and_changed_versions_preserve_old_bytes(self):
        first = memory.checkpoint(self.pkg, "proof:1", {"Proof.lean": b"-- failed first\n"})
        pinned = {p: p.read_bytes() for folder in ("blobs", "snapshots", "indexes")
                  for p in (self.pkg.root / memory.BASE / folder).iterdir()}
        second = memory.checkpoint(self.pkg, "proof:2", {"Proof.lean": b"-- failed first\n"})
        third = memory.checkpoint(self.pkg, "proof:3", {"Proof.lean": b"-- corrected proposal\n"})
        self.assertNotEqual(first["snapshot_ref"], second["snapshot_ref"])
        self.assertEqual(2, len(list((self.pkg.root / memory.BASE / "blobs").iterdir())))
        for path, original in pinned.items():
            self.assertEqual(original, path.read_bytes())
        self.assertEqual({"Proof.lean": b"-- failed first\n"}, memory.restore(self.pkg, first["snapshot_ref"]))
        self.assertEqual({"Proof.lean": b"-- corrected proposal\n"}, memory.restore(self.pkg, third["snapshot_ref"]))

    def test_capture_persists_canonical_payload_and_exact_extra_proposal(self):
        payload = {"obligations": [{"id": "O1", "state": "INTERPRETED"}], "error": "failed\nline"}
        manifest = memory.capture_context(self.pkg, "critique:1", payload,
                                          extra_artifacts={"candidate/Contract.lean": b"-- unaccepted\n"})
        self.assertEqual({"payload.json": canonical.dumps(payload), "candidate/Contract.lean": b"-- unaccepted\n"},
                         memory.restore(self.pkg, manifest["snapshot_ref"]))
        self.assertIn("no proof", manifest["authority"])
        self.assertEqual(manifest["index_ref"], memory.context_for(self.pkg)["index_ref"])

    def test_latest_matching_stages_reload_whole_critique_and_skip_old_request(self):
        memory.checkpoint(self.pkg, "request:1", {"request.txt": b"x" * 10000})
        old = memory.capture_context(self.pkg, "critique:1", {"finding": "old"})
        memory.capture_context(self.pkg, "response:1", {"other": "response"})
        latest = memory.capture_context(self.pkg, "critique:2", {"finding": "new"})
        with patch.object(memory, "MAX_CONTEXT_BYTES", 4096):
            self.assertBlocked("BUDGET_EXHAUSTED", memory.context_for, self.pkg, last=4)
            context = memory.context_for(self.pkg, last=2, stage_prefixes=["critique:"])
        self.assertEqual([old["snapshot_ref"], latest["snapshot_ref"]], [x["snapshot_ref"] for x in context["snapshots"]])
        exact = memory.context_for(self.pkg, stages=["critique:1"])
        self.assertEqual(old["snapshot_ref"], exact["snapshots"][0]["snapshot_ref"])
        self.assertEqual(latest["snapshot_ref"], memory.latest_snapshot(self.pkg, stage_prefix="critique:"))
        self.assertIsNone(memory.latest_snapshot(self.pkg, stage_prefix="absent:"))

    def test_structured_hydrated_context_cannot_be_captured_recursively(self):
        context = memory.context_for(self.pkg)
        self.assertBlocked("INVALID_CANDIDATE", memory.capture_context, self.pkg, "request", {"nested": [context]})
        self.assertBlocked("INVALID_CANDIDATE", memory.capture_context, self.pkg, "request", {},
                           extra_artifacts={"payload.json": b"replacement"})

    def test_blob_hash_tampering_and_missing_blob_fail_closed(self):
        manifest = memory.checkpoint(self.pkg, "proof", {"Proof.lean": b"abc"})
        blob = self.blob(manifest, "Proof.lean")
        self.mutate(blob, b"xyz")
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.restore, self.pkg, manifest["snapshot_ref"])
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.latest_snapshot, self.pkg)
        blob.unlink()
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.context_for, self.pkg)

    def test_manifest_hash_tampering_is_rejected(self):
        manifest = memory.capture_context(self.pkg, "formalize", {"stage": "actual"})
        path = self.pkg.root / manifest["snapshot_ref"]["path"]
        data = path.read_bytes().replace(b'"formalize"', b'"untrusted"')
        self.mutate(path, data)
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.restore, self.pkg, manifest["snapshot_ref"])

    def test_references_reject_traversal_wrong_kind_unknown_fields_and_bool_size(self):
        manifest = memory.checkpoint(self.pkg, "formalize", {"Proof.lean": b"true"})
        reference = manifest["snapshot_ref"]
        bad = [{**reference, "path": "../outside.json"}, {**reference, "path": "/tmp/outside.json"},
               {**reference, "path": reference["path"].replace("snapshots", "indexes")},
               {**reference, "size": True}, {**reference, "unknown": 1},
               {**reference, "sha256": "sha256:" + "0" * 64}]
        for ref in bad:
            with self.subTest(ref=ref):
                self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.restore, self.pkg, ref)

    def test_unsafe_source_names_and_collisions_are_rejected_before_writing(self):
        for name in ("../Proof.lean", "/Proof.lean", "a//b", "a\\b", "bad\x00name"):
            with self.subTest(name=name):
                self.assertBlocked("INVALID_CANDIDATE", memory.checkpoint, self.pkg, "proof", {name: b"x"})
        self.assertBlocked("INVALID_CANDIDATE", memory.checkpoint, self.pkg, "proof", {"A.lean": b"x", "a.lean": b"y"})
        self.assertFalse((self.pkg.root / memory.BASE).exists())

    def test_symlinks_hardlinks_and_symlink_directory_are_rejected(self):
        for link in ("symlink", "hardlink"):
            with self.subTest(link=link):
                pkg = Package(Path(self.tmp.name) / link)
                pkg.ensure(link)
                manifest = memory.checkpoint(pkg, "proof", {"Proof.lean": b"abc"})
                blob = pkg.root / manifest["artifacts"][0]["blob_ref"]["path"]
                outside = Path(self.tmp.name) / (link + "-outside")
                if link == "symlink":
                    outside.write_bytes(blob.read_bytes())
                    blob.unlink()
                    blob.symlink_to(outside)
                else:
                    os.link(blob, outside)
                self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.restore, pkg, manifest["snapshot_ref"])
        manifest = memory.checkpoint(self.pkg, "proof", {"Proof.lean": b"abc"})
        blobs = self.pkg.root / memory.BASE / "blobs"
        moved = Path(self.tmp.name) / "moved-blobs"
        blobs.rename(moved)
        blobs.symlink_to(moved, target_is_directory=True)
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.restore, self.pkg, manifest["snapshot_ref"])

    def test_replacement_during_blob_read_is_detected(self):
        manifest = memory.checkpoint(self.pkg, "proof", {"Proof.lean": b"abc"})
        blob = self.blob(manifest, "Proof.lean")
        inode = blob.stat().st_ino
        real_read = os.read
        replaced = []
        def replacing_read(fd, size):
            data = real_read(fd, size)
            if os.fstat(fd).st_ino == inode and not replaced:
                replaced.append(True)
                blob.unlink()
                blob.write_bytes(b"abc")
            return data
        with patch.object(memory.os, "read", replacing_read):
            self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.restore, self.pkg, manifest["snapshot_ref"])
        self.assertEqual([True], replaced)

    def test_missing_latest_index_or_snapshot_never_falls_back(self):
        first = memory.capture_context(self.pkg, "critique:1", {"error": "one"})
        latest = memory.capture_context(self.pkg, "critique:2", {"error": "two"})
        for key in ("index_ref", "snapshot_ref"):
            with self.subTest(key=key):
                path = self.pkg.root / latest[key]["path"]
                data = path.read_bytes()
                path.unlink()
                self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.context_for, self.pkg)
                self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.latest_snapshot, self.pkg)
                path.write_bytes(data)
        self.assertEqual(first["snapshot_ref"], memory.context_for(self.pkg, last=2)["snapshots"][0]["snapshot_ref"])

    def test_truncated_journal_or_stale_index_is_not_an_older_success(self):
        memory.capture_context(self.pkg, "critique:1", {"error": "one"})
        latest = memory.capture_context(self.pkg, "critique:2", {"error": "two"})
        journal = self.pkg.root / memory.BASE / "journal.jsonl"
        original = journal.read_bytes()
        journal.write_bytes(original.splitlines(keepends=True)[0])
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.context_for, self.pkg)
        journal.write_bytes(original)
        path = self.pkg.root / latest["index_ref"]["path"]
        index = canonical.loads(path.read_bytes())
        index["snapshots"][-1] = index["snapshots"][0]
        data = canonical.dumps(index)
        wrong = {"path": f"{memory.BASE}/indexes/00000002-{canonical.sha256_hex(data)}.json",
                 "sha256": canonical.digest(data), "size": len(data)}
        path.unlink()
        (self.pkg.root / wrong["path"]).write_bytes(data)
        commits = [canonical.loads(line) for line in original.splitlines()]
        commits[-1]["index_ref"] = wrong
        journal.write_bytes(b"".join(canonical.dumps(row) + b"\n" for row in commits))
        self.assertBlocked("STALE_OR_UNBOUND_EVIDENCE", memory.context_for, self.pkg)

    def test_oversized_input_and_returned_context_have_explicit_diagnostics(self):
        with patch.object(memory, "MAX_ARTIFACT_BYTES", 64):
            self.assertBlocked("BUDGET_EXHAUSTED", memory.checkpoint, self.pkg, "proof", {"Proof.lean": b"x" * 65})
        with patch.object(memory, "MAX_CHECKPOINT_BYTES", 64):
            self.assertBlocked("BUDGET_EXHAUSTED", memory.checkpoint, self.pkg, "proof", {"one": b"x" * 40, "two": b"x" * 40})
        manifest = memory.checkpoint(self.pkg, "proof", {"Proof.lean": b"x" * 2048})
        with patch.object(memory, "MAX_CONTEXT_BYTES", 1024):
            self.assertBlocked("BUDGET_EXHAUSTED", memory.context_for, self.pkg)
        self.assertEqual({"Proof.lean": b"x" * 2048}, memory.restore(self.pkg, manifest["snapshot_ref"]))

    def test_storage_deduplication_and_snapshot_count_bounds(self):
        memory.checkpoint(self.pkg, "proof:1", {"Proof.lean": b"x" * 65536})
        root = self.pkg.root / memory.BASE
        used = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        with patch.object(memory, "MAX_STORAGE_BYTES", used + 8192):
            memory.checkpoint(self.pkg, "proof:2", {"Proof.lean": b"x" * 65536})
        journal = (root / "journal.jsonl").read_bytes()
        with patch.object(memory, "MAX_SNAPSHOTS", 2):
            self.assertBlocked("BUDGET_EXHAUSTED", memory.capture_context, self.pkg, "proof:3", {})
        self.assertEqual(journal, (root / "journal.jsonl").read_bytes())

    def test_memory_never_changes_claims_or_promotes_a_rejected_proposal(self):
        claims = self.pkg.root / "claims.json"
        claims.write_bytes(b'{"status":"unproved"}\n')
        before = self.pkg.meta_path.read_bytes()
        memory.capture_context(self.pkg, "proof:rejected", {"claim": "PROVED", "proposal": "sorry"})
        context = memory.context_for(self.pkg)
        self.assertIn("no proof", context["authority"])
        self.assertEqual(b'{"status":"unproved"}\n', claims.read_bytes())
        self.assertEqual(before, self.pkg.meta_path.read_bytes())

    def test_invalid_filters_and_noncanonical_payloads_do_not_mutate_history(self):
        for last in (True, 0, -1, memory.MAX_SNAPSHOTS + 1):
            self.assertBlocked("INVALID_CANDIDATE", memory.context_for, self.pkg, last=last)
        self.assertBlocked("INVALID_CANDIDATE", memory.context_for, self.pkg, stages=["x"], stage_prefixes=["x"])
        self.assertBlocked("INVALID_CANDIDATE", memory.capture_context, self.pkg, "proof", {"bad": 1.5})
        self.assertBlocked("INVALID_CANDIDATE", memory.capture_context, self.pkg, "proof", {"bad": 2**60})
        cyclic = {}
        cyclic["cycle"] = cyclic
        self.assertBlocked("BUDGET_EXHAUSTED", memory.capture_context, self.pkg, "proof", cyclic)
        self.assertIsNone(memory.latest_snapshot(self.pkg))


if __name__ == "__main__":
    unittest.main()
