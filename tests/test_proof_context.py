"""Exact local-prover library projection; authored context only, no model calls."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verislop import agent_memory, canonical, proof_context
from verislop.errors import BlockedError
from verislop.package import Package
from verislop.targets import vscore3_target


class VSCoreProofContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "run")
        self.pkg.ensure("proof-context-fixture")
        self.library = {name: raw.decode("utf-8") for name, raw in vscore3_target.library_sources().items()}
        self.data = {"parameters": {"backend_version": "0.3"}, "source": {"exact": "source"},
                     "relation": {"exact": "relation"}, "generated_goal": "-- exact goal\n",
                     "accepted_reference": "-- exact reference\n", "accepted_packages": {"O1": {"formula": True}},
                     "accepted_profile": {"enums": {}}, "refinement_symbols": ["solve"],
                     "proof_support": vscore3_target.proof_support_catalog(),
                     "readable_source_view": {"mode": "CHECKED", "status": "CHECKED"},
                     "lean_toolchain": "leanprover/lean4:v4.34.1", "verifier_library": self.library}

    def assertBlocked(self, fn, *args):
        with self.assertRaises(BlockedError) as caught:
            fn(*args)
        self.assertEqual("STALE_OR_UNBOUND_EVIDENCE", caught.exception.diagnostics[0].code)

    def test_exact_restore_selection_and_all_other_fields_unchanged(self):
        before = deepcopy(self.data)
        compact = proof_context.project_vscore_prompt(self.pkg, self.data)
        self.assertEqual(before, self.data)
        self.assertEqual(set(before) | {"verifier_library_reference"}, set(compact))
        for key in before:
            if key != "verifier_library":
                self.assertEqual(before[key], compact[key])
        self.assertEqual(list(proof_context.INLINE_MODULES), list(compact["verifier_library"]))
        for name, source in compact["verifier_library"].items():
            self.assertEqual(self.library[name], source)
        ref = compact["verifier_library_reference"]
        self.assertEqual(canonical.digest_json(self.library), ref["library_sha256"])
        self.assertEqual(self.library, proof_context.restore_verifier_library(Package(self.pkg.root), ref))
        self.assertFalse(Path(ref["snapshot_ref"]["path"]).is_absolute())
        self.assertLess(len(canonical.dumps(compact)), len(canonical.dumps(self.data)) // 2)
        self.assertEqual(1, len((self.pkg.root / agent_memory.BASE / "journal.jsonl").read_text().splitlines()))

    def test_selection_is_deterministic_and_does_not_depend_on_candidate(self):
        first = proof_context.project_vscore_prompt(self.pkg, self.data)
        other = {**self.data, "source": {"different": True}, "generated_goal": "another goal"}
        second = proof_context.project_vscore_prompt(self.pkg, other)
        self.assertEqual(first["verifier_library"], second["verifier_library"])
        left, right = (dict(x["verifier_library_reference"]) for x in (first, second))
        left.pop("snapshot_ref"); right.pop("snapshot_ref")
        self.assertEqual(left, right)
        self.assertEqual(1, len(list((self.pkg.root / agent_memory.BASE / "blobs").iterdir())))

    def test_old_version_and_unspecified_context_are_unchanged_without_storage(self):
        for version in ("0.1", "0.2", None):
            data = {**self.data, "parameters": {"backend_version": version}}
            self.assertIs(data, proof_context.project_vscore_prompt(self.pkg, data))
        self.assertFalse((self.pkg.root / agent_memory.BASE).exists())

    def test_missing_extra_nontext_changed_and_invalid_unicode_modules_block_before_storage(self):
        missing = dict(self.library); missing.pop("VSCore3")
        bad = [missing, {**self.library, "Injected": "axiom p : False"},
               {**self.library, "VSCore3": None}, {**self.library, "VSCore3": "changed"},
               {**self.library, "VSCore3": "\ud800"}]
        for library in bad:
            with self.subTest(library_keys=list(library)):
                self.assertBlocked(proof_context.project_vscore_prompt, self.pkg,
                                   {**self.data, "verifier_library": library})
        self.assertFalse((self.pkg.root / agent_memory.BASE).exists())

    def test_missing_toolchain_and_double_projection_block(self):
        for pin in (None, "", "  "):
            self.assertBlocked(proof_context.project_vscore_prompt, self.pkg,
                               {**self.data, "lean_toolchain": pin})
        compact = proof_context.project_vscore_prompt(self.pkg, self.data)
        self.assertBlocked(proof_context.project_vscore_prompt, self.pkg, compact)

    def test_changed_reference_hash_toolchain_selection_inventory_or_schema_block(self):
        ref = proof_context.project_vscore_prompt(self.pkg, self.data)["verifier_library_reference"]
        mutations = [{**ref, "sha256": "sha256:" + "0" * 64},
                     {**ref, "library_sha256": "sha256:" + "0" * 64},
                     {**ref, "lean_toolchain": "another-pin"}, {**ref, "module_inventory": []},
                     {**ref, "inline_modules": ["VSCore3"]}, {**ref, "omitted_modules": []},
                     {**ref, "source_ref": "../library.json"}, {**ref, "extra": True}]
        for changed in mutations:
            with self.subTest(keys=list(changed)):
                self.assertBlocked(proof_context.restore_verifier_library, self.pkg, changed)

    def test_historical_restore_does_not_substitute_current_sources(self):
        ref = proof_context.project_vscore_prompt(self.pkg, self.data)["verifier_library_reference"]
        with patch.object(vscore3_target, "library_sources", side_effect=AssertionError("ambient library read")):
            self.assertEqual(self.library, proof_context.restore_verifier_library(self.pkg, ref))

    def test_changed_cas_blob_blocks(self):
        ref = proof_context.project_vscore_prompt(self.pkg, self.data)["verifier_library_reference"]
        manifest = canonical.load_file(self.pkg.root / ref["snapshot_ref"]["path"])
        blob = self.pkg.root / manifest["artifacts"][0]["blob_ref"]["path"]
        blob.chmod(0o600)
        blob.write_bytes(blob.read_bytes() + b"\n")
        self.assertBlocked(proof_context.restore_verifier_library, self.pkg, ref)

    def test_changed_snapshot_and_broken_journal_block(self):
        ref = proof_context.project_vscore_prompt(self.pkg, self.data)["verifier_library_reference"]
        path = self.pkg.root / ref["snapshot_ref"]["path"]
        original = path.read_bytes()
        path.chmod(0o600); path.write_bytes(original + b"\n")
        self.assertBlocked(proof_context.restore_verifier_library, self.pkg, ref)
        path.write_bytes(original)
        journal = self.pkg.root / agent_memory.BASE / "journal.jsonl"
        journal.write_bytes(journal.read_bytes() + b"{}\n")
        self.assertBlocked(proof_context.restore_verifier_library, self.pkg, ref)


if __name__ == "__main__":
    unittest.main()
