"""Preregistered oracle sanity checks and fail-closed serialization boundaries."""
import tempfile
import unittest
from pathlib import Path

from verislop import canonical, dsl, link, monitors, schemas
from verislop.targets import python_target as pt
from synthetic_dataset.tools import data_pipeline_oracle as oracle
from synthetic_dataset.tools.check_data_pipeline_poc import check_preregistration, check_interface, CheckFailure, PROTOCOL
from synthetic_dataset.tools.run_data_pipeline_poc import origin_audit, source_inputs
from verislop.package import Package


class PipelineProtocolTests(unittest.TestCase):
    def test_request_oracles_cover_signed_boundary_duplicates_and_exact_unicode(self):
        self.assertEqual(oracle.expected(oracle.TASKS[0], {"values": [-2, -1, -1, 0, 2**128], "minimum": -1, "factor": -3}),
                         {"values": [3, 3, 0, -3*2**128], "total": 6-3*2**128, "count": 4})
        self.assertEqual(oracle.expected(oracle.TASKS[1], {"rows": [
            {"tag": "", "amount": -1, "enabled": True}, {"tag": "cafe\u0301", "amount": 0, "enabled": False},
            {"tag": "café", "amount": -1, "enabled": True}], "minimum": -1}),
            {"rows": [{"tag": "", "amount": -1}, {"tag": "café", "amount": -1}], "total": -2, "count": 2})
        self.assertEqual(oracle.expected(oracle.TASKS[2], {"labels": ["", " ", "e\u0301", "e\u0301", "é"], "prefix": "🐈"}),
                         {"labels": ["🐈 ", "🐈e\u0301", "🐈e\u0301", "🐈é"], "count": 4})
        self.assertNotEqual(oracle.wire(True), oracle.wire(1))

    def test_pre_generation_case_freeze_has_160_distinct_cases_each(self):
        receipt = check_preregistration()
        self.assertFalse(receipt["generation_started"])
        for task in oracle.TASKS:
            rows = oracle.cases(task)
            self.assertEqual(160, len(rows))
            self.assertEqual(160, len({canonical.dumps(row["input_wire"]) for row in rows}))
            self.assertEqual(rows, canonical.load_file(PROTOCOL / "withheld" / f"{task}.json")["cases"])

    def test_binding_schema_accepts_both_versions_but_structure_requires_exact_selected_profile(self):
        proposal = {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
                    "serialization_profile": "python-v0_2", "bindings": [{"binding_id": "B-solve", "symbol": "solve",
                    "object": {"file": "code.py", "qualname": "solve"}, "obligations": ["O1"]}], "helpers": []}
        inventory = pt.Inventory({}, [{"file": "code.py", "qualname": "solve", "kind": "function", "public": True,
                                       "positional": 1, "defaults": 0, "varargs": False, "kwonly_required": False, "decorated": False}])
        symbols = {"solve": {"args": ["Nat"], "result": "Nat"}}
        self.assertEqual([], schemas.validate("implementation-bindings", proposal))
        self.assertEqual([], link.structural_proposal_diagnostics(proposal, {"dsl": dsl.ENCODING_V2, "symbols": symbols}, inventory, {"solve": ["O1"]}))
        self.assertEqual(["INVALID_CANDIDATE"], [d.code for d in link.structural_proposal_diagnostics(proposal, {"dsl": dsl.ENCODING, "symbols": symbols}, inventory, {"solve": ["O1"]})])

    def test_new_tier1_semantics_fail_before_any_output_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            pkg = Package(Path(directory) / "package")
            pkg.ensure("no-silent-downgrade")
            diagnostics = monitors.generate(pkg, None, {}, {"dsl": dsl.ENCODING_V2}, {}, {})
            self.assertEqual(["UNSUPPORTED_CAPABILITY"], [d.code for d in diagnostics])
            self.assertFalse((pkg.path("bridges") / "tier1").exists())

    def test_record_boundary_cannot_be_replaced_by_flattened_or_natural_surrogate(self):
        profile = {"records": {"I": {"fields": [{"name": "values", "sort": {"list": "Int"}}, {"name": "minimum", "sort": "Int"},
                                                  {"name": "factor", "sort": "Int"}]},
                               "O": {"fields": [{"name": "values", "sort": {"list": "Int"}}, {"name": "total", "sort": "Int"},
                                                  {"name": "count", "sort": "Nat"}]}}}
        spec = {"args": [{"record": "I"}], "result": {"record": "O"}}
        check_interface(oracle.TASKS[0], spec, profile)
        with self.assertRaises(CheckFailure):
            check_interface(oracle.TASKS[0], {**spec, "args": ["Nat"]}, profile)
        with self.assertRaises(CheckFailure):
            check_interface(oracle.TASKS[0], {**spec, "args": [{"list": "Int"}, "Int", "Int"]}, profile)

    def test_origin_check_does_not_accept_an_authored_implementation_without_native_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            pkg = Package(Path(directory) / "package")
            pkg.ensure("authored-negative-origin-fixture")
            pkg.path("implementation").mkdir(exist_ok=True)
            (pkg.path("implementation") / "answer.py").write_text("def solve(data):\n    return data\n")
            result = origin_audit(pkg, ["python", "-m", "verislop", "run"], source_inputs())
            self.assertEqual("BLOCK", result["status"])
            self.assertIn("No native provider transcript", result["issues"])
            self.assertIn("Implementation bytes have no exact complete native proposal origin", result["issues"])


if __name__ == "__main__":
    unittest.main()
