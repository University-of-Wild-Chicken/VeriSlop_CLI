"""Unrelated finite regression witnesses for the admission reader repair.

No native inputs, inference, Lean builds, qualification results, or promotions.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("support019_admission002", HERE / "audit_actual.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AdmissionControls(unittest.TestCase):
    def test_evidence_parse_uses_only_authenticated_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "replacement.json"
            path.write_bytes(b'{"origin":"substituted"}')
            reader = audit.Audit.__new__(audit.Audit)
            authenticated = b'{"origin":"authenticated"}'
            with patch.object(reader, "evidence", return_value=authenticated) as evidence:
                result = reader.doc({"path": "replacement.json"})
            self.assertEqual(result, {"origin": "authenticated"})
            evidence.assert_called_once()
            # Concrete former two-read behavior would consume different content.
            self.assertNotEqual(result, audit.parse(path.read_bytes()))

    def test_initial_metadata_different_from_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            gate = root / "validation" / "gate"
            gate.mkdir(parents=True)
            path = gate / "qualification-specification.json"
            original = b'{"identity":"frozen"}'
            substituted = b'{"identity":"substituted"}'
            path.write_bytes(original)
            name = path.relative_to(root).as_posix()
            reader = audit.Audit.__new__(audit.Audit)
            reader.gate = gate
            reader.manifest = {"source_hashes": {name: audit.digest(original)}}
            reader.metadata_reads = {name: {"path": name, "sha256": audit.digest(substituted),
                                           "byte_count": len(substituted)}}
            with patch.object(audit, "ROOT", root):
                with self.assertRaisesRegex(audit.Block, "INITIAL_METADATA_NOT_FROZEN"):
                    reader.guards()

    def test_repeated_metadata_substitution_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "metadata.json"
            path.write_bytes(b'{"identity":1}')
            reader = audit.Audit.__new__(audit.Audit)
            reader.metadata_reads = {}
            with patch.object(audit, "ROOT", root):
                self.assertEqual(reader.metadata(path), {"identity": 1})
                path.write_bytes(b'{"identity":2}')
                with self.assertRaisesRegex(audit.Block, "METADATA_MUTATION"):
                    reader.metadata(path)

    def test_output_aliases_cannot_escape_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "validation").mkdir()
            (root / "policies").mkdir()
            (root / "validation" / "indirect").symlink_to(root / "policies", target_is_directory=True)
            rejected = ("validation/../policies/audit", "validation/./audit", "validation//audit",
                        "policies/audit", "validation", str(root / "validation" / "absolute"),
                        "validation/indirect/audit")
            for value in rejected:
                with self.subTest(value=value), self.assertRaises(audit.Block):
                    audit.fresh_output(root, value)
            self.assertEqual(list((root / "policies").iterdir()), [])
            self.assertEqual(audit.fresh_output(root, "validation/fresh-audit"), root / "validation/fresh-audit")
            self.assertFalse((root / "validation" / "fresh-audit").exists())

    def test_author_bool_int_substitution_is_rejected(self):
        expected = {"markers": ["UNRELATED_CONTROL"],
                    "field_roots": {"/system": "sha256:a", "/user": "sha256:b"},
                    "field_eof": {"/system": True, "/user": True},
                    "field_chars": {"/system": 1, "/user": 2}}
        raw = lambda value: json.dumps(value).encode("utf-8")
        self.assertEqual(audit.author_value(raw(expected)), audit.author_value(raw(copy.deepcopy(expected))))
        for field, selector, value in (("field_eof", "/system", 1), ("field_chars", "/system", True),
                                       ("field_chars", "/system", 1.0)):
            altered = copy.deepcopy(expected)
            altered[field][selector] = value
            self.assertEqual(altered, expected)  # Concrete permissive Python equality witness.
            with self.subTest(field=field, value=value), self.assertRaisesRegex(audit.Block, "AUTHOR_FIELD_TYPES"):
                audit.author_value(raw(altered))
        for change in (lambda x: x.update(extra=True), lambda x: x["field_eof"].pop("/user")):
            altered = copy.deepcopy(expected); change(altered)
            with self.assertRaises(audit.Block):
                audit.author_value(raw(altered))


if __name__ == "__main__":
    unittest.main(verbosity=2)
