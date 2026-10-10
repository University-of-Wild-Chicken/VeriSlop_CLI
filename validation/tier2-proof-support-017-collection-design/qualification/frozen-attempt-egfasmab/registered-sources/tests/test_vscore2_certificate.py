"""Real isolated kernel replays and reconstruction across the delivered 0.2 core."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verislop import canonical
from verislop.targets import vscore2_check as checker, vscore2_source as src
from verislop.verifiers import verifier_hash

ROOT = Path(__file__).resolve().parents[1]


class VSCore2CertificateTests(unittest.TestCase):
    def test_complete_core_reconstructs_from_two_accepted_environments(self):
        program = src.parse_surface((ROOT / "examples/vscore-grammar/pure-data.vsc").read_text())
        ordering = src.parse_surface((ROOT / "examples/vscore-grammar/ordering.vsc").read_text())
        helpers = {f["id"]: f for f in program["helpers"]}
        for f in ordering["helpers"]:
            if f["id"] in helpers:
                self.assertEqual(helpers[f["id"]], f)
            helpers[f["id"]] = f
        program["helpers"] = list(helpers.values())
        program["entries"] += ordering["entries"]
        enum_type = ("enum", "Choice")
        nested_type = ("result", enum_type, ("option", ("list", "nat")))
        for name, typ in (("enum_identity", enum_type), ("nested_identity", nested_type)):
            program["entries"].append({"id": name, "params": [typ], "result": typ, "body": ("var", 0)})
        registry = {"Choice": ["left", "right"]}
        data = src.source_bytes(program)
        signatures = src.check_program(registry, program)
        with tempfile.TemporaryDirectory(prefix="verislop-vscore2-certificate-test-") as tmp:
            out = Path(tmp) / "certificate"
            result = checker.check(data, registry, out)
            self.assertEqual(result.status, "PASS", [d.to_json() for d in result.diagnostics])
            report = canonical.load_file(out / "report.json")
            ir = canonical.load_file(out / "implementation-ir.json")
            self.assertEqual(report["status"], "VERIFIED")
            self.assertEqual(report["input_root"], canonical.digest_json(report["inputs"]))
            self.assertEqual(report["inputs"]["verifier"], verifier_hash(checker.VERIFIER))
            self.assertEqual(report["builds"][0], report["builds"][1])
            self.assertEqual(set(report["builds"][0]["modules"]), {*checker.LIB_MODULES, checker.MODULE})
            self.assertEqual(ir["program"], src.program_json(program))
            self.assertEqual(ir["required_features"], list(src.FEATURES))
            self.assertEqual(ir["enums"], [{"id": "Choice", "constructors": ["left", "right"]}])
            self.assertEqual(ir["signatures"], [{"id": s["id"], "params": [src.ty_json(t) for t in s["params"]],
                "result": src.ty_json(s["result"])} for s in signatures])
            self.assertFalse(report["assigns_obligation_milestones"])
            self.assertFalse(report["assigns_end_to_end_verified"])
            self.assertEqual((out / "source.vscore.json").read_bytes(), data)
            before = canonical.digest_file(out / "report.json")
            repeat = checker.check(data, registry, out)
            self.assertEqual(repeat.status, "BLOCKED")
            self.assertEqual(canonical.digest_file(out / "report.json"), before)


if __name__ == "__main__":
    unittest.main()
