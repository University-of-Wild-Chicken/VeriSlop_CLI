"""Finite regression surface for shared Lean Unicode literal rendering.

Actual kernel round-trip qualification is registered in
validation/tier2-unicode-literal-support-018/verify.py.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from verislop.targets import vscore_source, vscore2_source, vscore3_source
from verislop.targets import vscore_target, vscore3_target


FIXTURE = Path(__file__).resolve().parents[1] / "validation/tier2-unicode-literal-support-018/fixtures.json"


def positive_fixtures():
    fixture = json.loads(FIXTURE.read_text())
    rows = [{**row, "text": "".join(chr(c) for c in row["scalars"])} for row in fixture["positive"]]
    legacy = [c for c in range(0x20, 0x7F) if c not in (0x22, 0x5C)]
    rows.extend({"id": f"legacy_{c:04x}", "text": chr(c), "expected_lean": '"' + chr(c) + '"'} for c in legacy)
    rows.append({"id": "legacy_concatenated", "text": "".join(chr(c) for c in legacy),
                 "expected_lean": '"' + "".join(chr(c) for c in legacy) + '"'})
    rows.extend({"id": f"control_{c:04x}", "text": chr(c)}
                for c in [*range(0x20), *range(0x7F, 0xA0)])
    return rows


def invalid_fixtures():
    fixture = json.loads(FIXTURE.read_text())
    return [{**row, "text": "".join(chr(c) for c in row["codepoints"])} for row in fixture["invalid"]]


class UnicodeLeanLiteralTests(unittest.TestCase):
    def test_fixture_expected_syntax_and_shared_literal_printers(self):
        for row in positive_fixtures():
            with self.subTest(case=row["id"]):
                rendered = vscore_source.lean_string(row["text"])
                if "expected_lean" in row:
                    self.assertEqual(rendered, row["expected_lean"])
                self.assertEqual(vscore2_source.lean_string(row["text"]), rendered)
                self.assertEqual(vscore3_source.lean_string(row["text"]), rendered)
                expression = {"lit": {"str": row["text"]}}
                self.assertEqual(vscore_target.Printer().term(expression), rendered)
                self.assertEqual(vscore3_target.Printer().term(expression), rendered)
                self.assertIs(vscore3_target.Printer, vscore_target.Printer)
                rendered.encode("utf-8", "strict")

    def test_invalid_surrogate_text_is_rejected_in_every_shared_path(self):
        for row in invalid_fixtures():
            expression = {"lit": {"str": row["text"]}}
            calls = [lambda s=src: s.lean_string(row["text"])
                     for src in (vscore_source, vscore2_source, vscore3_source)]
            calls.extend(lambda p=printer: p().term(expression)
                         for printer in (vscore_target.Printer, vscore3_target.Printer))
            for call in calls:
                with self.subTest(case=row["id"]), self.assertRaisesRegex(vscore_source.SourceError, "surrogate"):
                    call()


if __name__ == "__main__":
    unittest.main()
