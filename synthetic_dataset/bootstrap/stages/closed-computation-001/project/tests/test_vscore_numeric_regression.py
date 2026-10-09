"""VSCore numeric bounds must reject source with stable diagnostics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import TempDir, codes, run_cli
from verislop import canonical
from verislop.targets import vscore_source as src, vscore_target as target


def indexed_source(digits: bytes) -> bytes:
    program = {"language": src.LANGUAGE, "entries": [
        {"id": "f", "params": ["nat"], "result": "nat", "body": {"index": 0, "tag": "var"}}]}
    return canonical.dumps(program).replace(b'"index":0', b'"index":' + digits)


class NumericSourceRegression(unittest.TestCase):
    def test_json_integer_bound_is_exact(self):
        for digits in (b"0", b"1", b"9007199254740990", b"9007199254740991"):
            with self.subTest(digits=digits):
                program = src.parse_source(indexed_source(digits))
                self.assertEqual(program["entries"][0]["body"], ("var", int(digits)))
        for digits in (b"9007199254740992", b"9999999999999999", b"10000000000000000", b"1" * 5000):
            with self.subTest(length=len(digits)), self.assertRaisesRegex(src.SourceError, "integer exceeds"):
                src.parse_source(indexed_source(digits))

    def test_oversized_integer_cli_returns_source_rejection(self):
        tmp = TempDir()
        self.addCleanup(tmp.cleanup)
        source = tmp.path / "program.vscore.json"
        data = indexed_source(b"1" * 5000)
        self.assertLess(len(data), target.MAX_SOURCE_BYTES)
        source.write_bytes(data)
        code, result, _ = run_cli("vscore", "parse", "--package", str(tmp.path), "--source", str(source))
        self.assertEqual(code, 2, result)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("INVALID_CANDIDATE", codes(result))

    def test_oversized_integer_goal_derivation_uses_bridge_diagnostic(self):
        profile = {"profile_id": "numeric-test", "dsl": "verislop.contract-dsl/0.1",
                   "enums": {}, "predicates": {}, "symbols": {
                       "f": {"args": ["Nat"], "result": "Nat", "lean_decl": "Test.f", "level_params": []}}}
        relation = {"schema_version": "0.1", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
                    "source_slot": "source", "proof_slot": "proof", "bindings": [{"symbol": "f", "entry": "f"}]}
        with self.assertRaises(target.BridgeInvalid) as caught:
            target.build_goal(indexed_source(b"1" * 5000), relation, profile, {})
        self.assertEqual(caught.exception.code, "INVALID_CANDIDATE")
        self.assertIn("integer exceeds", str(caught.exception))
