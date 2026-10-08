from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthetic_dataset.tools import check_reservation_poc as checker
from verislop import canonical, contract, fsutil
from verislop.errors import Diagnostic
from verislop.package import Package


class ReservationCheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "package")
        self.pkg.ensure("oracle-unit")
        fsutil.atomic_write(self.pkg.path("prompt"), checker.REQUEST.read_bytes())
        fsutil.write_json(self.pkg.path("accepted_ir"), {"fixture": "accepted identity mocked for target-only unit tests"})
        # Negative reports remain checkable; the oracle never promotes their state.
        fsutil.write_json(self.pkg.path("report"), {"terminal_status": "BLOCKED"})
        self.ir_hash = canonical.digest_file(self.pkg.path("accepted_ir"))
        self.profile = {"profile_id": "fixture", "symbols": {"reserve": {"lean_decl": "Model.reserve", "args": ["Nat", "Nat"],
                        "result": {"result": {"ok": "Nat", "error": {"enum": "Error"}}}}},
                        "enums": {"Error": {"lean_decl": "Model.Error", "constructors": ["insufficient"]}}, "predicates": {}}
        fsutil.write_json(contract.challenge_dir(self.pkg) / "profile.json", self.profile)
        fsutil.write_json(contract.challenge_dir(self.pkg) / "statements.json", {"declaration_hashes": {"Model.reserve": "sha256:" + "0"*64}})
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {"bound_to": {"accepted_ir": self.ir_hash}, "parameters": {"target": "python"}})

    def target(self, source):
        fsutil.atomic_write(self.pkg.path("implementation") / "reserve.py", source.encode())
        inventory = checker.pt.inventory(self.pkg.path("implementation"))
        obj = inventory.find("reserve.py", "reserve")
        link = {"artifact_kind": "link_record", "accepted_ir": self.ir_hash, "implementation_root": self.pkg.implementation_root(),
                "serialization_profile": checker.pt.PROFILE_DOC, "bindings": [{"binding_id": "B-reserve", "symbol": "reserve",
                "formal_declaration": {**self.profile["symbols"]["reserve"], "decl_hash": "sha256:" + "0"*64},
                "implementation_object": {"file": "reserve.py", "qualname": "reserve", "source_hash": obj["source_hash"],
                                          "file_hash": inventory.files["reserve.py"], "lineno": obj["lineno"]},
                "serialization_profile": checker.pt.PROFILE_ID}]}
        fsutil.write_json(self.pkg.path("bridges") / "link.json", link)
        return patch.object(checker, "verified_ir", return_value=({}, self.ir_hash, {}, []))

    def test_independent_wire_oracle_and_full_cross_product(self):
        self.assertEqual(len(checker.VALUES), 20)
        self.assertEqual(checker.expected_wire(2**128, 2**64), {"tuple": [{"str": "ok"}, {"int": str(2**128 - 2**64)}]})
        self.assertEqual(checker.expected_wire(0, 1), {"tuple": [{"str": "error"}, {"str": "insufficient"}]})
        self.assertFalse(checker.exact({"bool": True}, {"int": "1"}))

    def test_actual_isolated_positive_executes_400_cases_twice_without_package_mutation(self):
        with self.target('def reserve(balance, amount):\n    return ("ok", balance - amount) if amount <= balance else ("error", "insufficient")\n'):
            before = fsutil.manifest_tree(self.pkg.root)
            result = checker.run_check(self.pkg.root)
        self.assertEqual(result["status"], "PASS", result["diagnostics"])
        self.assertEqual((result["passed_cases"], result["distinct_cases"], result["completed_observations"]), (400, 400, 800))
        self.assertEqual(before, fsutil.manifest_tree(self.pkg.root))
        self.assertTrue(all(i["filesystem_read_isolation"] and i["network_namespace"] for i in result["isolation"]))

    def test_linked_negative_report_remains_checkable_and_concrete_equality_error_fails(self):
        with self.target('def reserve(balance, amount):\n    return ("ok", balance - amount) if amount < balance else ("error", "insufficient")\n'):
            result = checker.run_check(self.pkg.root, repeats=1)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual((result["passed_cases"], result["failed_cases"]), (380, 20))
        first = result["cases"][0]
        self.assertEqual((first["balance"], first["amount"]), ("0", "0"))
        self.assertEqual(first["observations"][0]["response"]["value"], checker.expected_wire(0, 1))
        self.assertEqual(canonical.load_file(self.pkg.path("report")), {"terminal_status": "BLOCKED"})

    def test_real_verified_ir_boundary_rejects_fixture_before_execution(self):
        with self.target('def reserve(balance, amount): return ("ok", 0)\n'):
            pass
        with patch.object(checker.pt, "Harness") as harness:
            result = checker.run_check(self.pkg.root, repeats=1)
        self.assertEqual(result["status"], "INPUT_INVALID")
        harness.assert_not_called()
        self.assertIn("verified_ir rejected", result["diagnostics"][0])

    def test_mutated_implementation_bytes_fail_before_execution(self):
        with self.target('def reserve(balance, amount): return ("ok", 0)\n'):
            fsutil.atomic_write(self.pkg.path("implementation") / "reserve.py", b'def reserve(balance, amount): return ("ok", 1)\n')
            with patch.object(checker.pt, "Harness") as harness:
                result = checker.run_check(self.pkg.root, repeats=1)
        self.assertEqual(result["status"], "INPUT_INVALID")
        harness.assert_not_called()
        self.assertIn("linked manifest", result["diagnostics"][0])

    def test_ambiguous_reserve_binding_rejected(self):
        with self.target('def reserve(balance, amount): return ("ok", 0)\n'):
            path = self.pkg.path("bridges") / "link.json"
            link = canonical.load_file(path)
            link["bindings"].append(dict(link["bindings"][0]))
            fsutil.write_json(path, link)
            with patch.object(checker.pt, "Harness") as harness:
                result = checker.run_check(self.pkg.root, repeats=1)
        self.assertEqual(result["status"], "INPUT_INVALID")
        harness.assert_not_called()
        self.assertIn("ambiguous", result["diagnostics"][0])

    def test_package_mutation_during_observation_overrides_passing_cases(self):
        pkg = self.pkg

        class MutatingHarness:
            def __init__(self, *_args, **_kwargs):
                self.calls = 0
                self.isolation = {"test_stub": True}

            def call(self, _symbol, args):
                self.calls += 1
                if self.calls == 1:
                    fsutil.write_json(pkg.path("report"), {"terminal_status": "changed"})
                return {"op": "result", "id": self.calls,
                        "value": checker.expected_wire(int(args[0]["int"]), int(args[1]["int"]))}

            def close(self):
                pass

        with self.target('def reserve(balance, amount): return ("ok", 0)\n'):
            with patch.object(checker.pt, "Harness", MutatingHarness):
                result = checker.run_check(self.pkg.root, repeats=1)
        self.assertEqual(result["status"], "INPUT_MUTATION")
        self.assertFalse(result["input_bytes_unchanged"])
        self.assertEqual(result["passed_cases"], 400)

    def test_output_inside_package_or_existing_file_is_rejected(self):
        self.assertEqual(checker.main(["--package", str(self.pkg.root), "--out", str(self.pkg.root / "oracle.json")]), 2)
        out = Path(self.tmp.name) / "existing.json"
        out.write_bytes(b"unchanged")
        self.assertEqual(checker.main(["--package", str(self.pkg.root), "--out", str(out)]), 2)
        self.assertEqual(out.read_bytes(), b"unchanged")


if __name__ == "__main__":
    unittest.main()
