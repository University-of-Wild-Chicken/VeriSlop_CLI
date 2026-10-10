"""Independent checked-subtraction contract, total source proof and Tier 2 pipeline fixture.

Concrete values here are fixture validation, including a Nat above 2^64; they never produce
TESTED evidence. Each negative program changes the exact refinement target for the same
accepted contract, without narrowing any assumption.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import EX, TempDir, codes, copy_pkg, run_cli, writable
from verislop import canonical
from verislop.bridges import vscore_checker as checker
from verislop.package import Package
from verislop.targets import vscore_source

FIXTURE = EX / "vscore-subtraction"
SOURCE = (FIXTURE / "program.vscore.json").read_bytes()
RELATION = (FIXTURE / "relation.json").read_bytes()
PROOF = (FIXTURE / "Proof.lean").read_bytes()
REQUIRED = {"S1", "R1", "B1", "E1"}
ENUMS = {"DebitError": ["insufficient"]}


def variant(edit) -> bytes:
    source = canonical.loads(SOURCE)
    edit(source["entries"][0]["body"])
    return canonical.dumps(source)


def wrong_order(body: dict):
    value = body["then"]["value"]
    value["left"], value["right"] = value["right"], value["left"]


def wrong_boundary(body: dict):
    body["cond"]["tag"] = "lt"


def wrong_result(body: dict):
    body["else"] = {"error_type": {"enum": "DebitError"}, "tag": "ok",
                    "value": {"tag": "nat", "value": "0"}}


NEGATIVES = {"wrong-order": variant(wrong_order), "equality-is-error": variant(wrong_boundary),
             "underflow-is-success": variant(wrong_result)}


def accepted_contract(package: Path):
    """Interpret this fixture's own request, formalize it and accept its own proof terms."""
    stages = [
        ("interpret", ["--prompt-file", str(FIXTURE / "request.txt"), "--request-ref",
                       "examples/vscore-subtraction/request.txt", "--candidate", str(FIXTURE / "draft.json"),
                       "--ledger", str(FIXTURE / "interpretation.json"), "--non-interactive"]),
        ("formalize", ["--candidate", str(FIXTURE / "formalization")]),
        ("prove", ["--candidate", str(FIXTURE / "formalization" / "Contract.lean"), "--no-portfolio"]),
        ("accept", ["--policy", "strict"]), ("export", []),
    ]
    for stage, args in stages:
        code, result, output = run_cli(stage, "--package", str(package), *args)
        if code:
            raise AssertionError((stage, code, result, output))


def stage(package: Path, name: str, *args: str) -> dict:
    argv = (name, args[0], "--package", str(package), *args[1:]) if name == "bridge" else (
        name, "--package", str(package), *args)
    code, result, output = run_cli(*argv)
    if code:
        raise AssertionError((name, code, result, output))
    return result


def mechanical(package: Path) -> dict:
    # The immutable result reference is selected by the current closure index.
    index = canonical.load_file(package / "closure" / "current.json")
    for key in ("mechanical_result", "mechanical_result_ref", "result"):
        ref = index.get(key)
        if isinstance(ref, dict):
            ref = ref.get("path")
        if isinstance(ref, str):
            return canonical.load_file(package / ref)
    raise AssertionError(("closure current index has no mechanical result", index))


class CheckedSubtractionSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.package = cls.tmp.path / "accepted-subtraction"
        accepted_contract(cls.package)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_independent_accepted_guarantees_and_concrete_witnesses(self):
        cert = canonical.load_file(self.package / "accepted" / "acceptance.json")
        ir = canonical.load_file(self.package / "accepted" / "accepted-ir.json")
        self.assertEqual({oid for oid, r in ir["obligations"].items()
                          if r["required"] and r["role"] == "guarantee" and r["kind"] != "non_vacuity"}, REQUIRED)
        for oid in REQUIRED | {"W1"}:
            self.assertEqual(cert["obligations"][oid]["proved"], "PASS")
        self.assertEqual(cert["obligations"]["W1"]["witnesses"], [[0, 0, 0], [7, 7, 0], [2, 3]])
        self.assertEqual(ir["obligations"]["E1"]["formal"]["hypotheses"], [])
        self.assertNotIn("BoundedIncrement", (FIXTURE / "formalization" / "Contract.lean").read_text())

    def test_exact_source_refinement_and_operational_fixture_cases_kernel_replay(self):
        spec, build, info = checker.preview(Package(self.package, resolve_root=False), SOURCE, RELATION, PROOF)
        self.assertEqual(set(info["obligations"]), REQUIRED)
        self.assertEqual(set(info["required_obligations"]), REQUIRED)
        self.assertEqual(canonical.dumps(build.ir["program"]), SOURCE)
        self.assertEqual([(s.symbol, s.entry) for s in spec.symbols], [("subtractIfEnough", "subtractIfEnough")])
        # PROOF includes kernel evaluation of zero, equality, underflow and unbounded values.
        for name in ("zero_case", "equality_case", "underflow_case", "unbounded_case"):
            self.assertIn(("theorem " + name).encode(), PROOF)
        self.assertNotIn(b"native_decide", PROOF)

    def test_wrong_order_boundary_and_result_fail_exact_refinement(self):
        for name, source in NEGATIVES.items():
            with self.subTest(name=name):
                # Each candidate remains well typed; preparation cannot substitute for proof.
                vscore_source.check_program(ENUMS, vscore_source.parse_source(source))
                checker.preview(Package(self.package, resolve_root=False), source, RELATION, proof=None)
                with self.assertRaises(checker.EdgeFailure) as rejected:
                    checker.preview(Package(self.package, resolve_root=False), source, RELATION, PROOF)
                self.assertIn("CANDIDATE_BUILD_FAILURE", {d.code for d in rejected.exception.diagnostics})

    def test_single_constructor_error_identity_is_not_replaceable(self):
        source = variant(lambda body: body["else"]["value"].update({"ctor": "other"}))
        with self.assertRaises(checker.EdgeFailure) as rejected:
            checker.preview(Package(self.package, resolve_root=False), source, RELATION, PROOF)
        self.assertIn("INVALID_CANDIDATE", {d.code for d in rejected.exception.diagnostics})


class CheckedSubtractionPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.accepted = cls.tmp.path / "accepted"
        accepted_contract(cls.accepted)
        cls.manual = copy_pkg(cls.accepted, cls.tmp.path / "manual")
        stage(cls.manual, "generate", "--tier", "2", "--target", "vscore", "--candidate", str(FIXTURE))
        stage(cls.manual, "link")
        stage(cls.manual, "bridge", "accept", "--bridge-id", "implementation")
        cls.result = stage(cls.manual, "verify")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def assert_complete(self, package: Path, result: dict):
        self.assertEqual(result["summary"]["mechanical_status"], "VERIFIED", result)
        report = canonical.load_file(package / "report.json")
        self.assertEqual(report["schema_version"], "0.2")
        view = canonical.load_file(package / "obligation-view.json")
        for oid in REQUIRED:
            rec = view["obligations"][oid]
            self.assertEqual(rec["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "PASS", rec)
            self.assertEqual(rec["lifecycle"]["TESTED"]["outcome"], "PENDING", rec)
        self.assertEqual(view["obligations"]["D1"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "NOT_APPLICABLE")
        self.assertEqual(view["obligations"]["W1"]["lifecycle"]["IMPLEMENTED"]["outcome"], "NOT_APPLICABLE")
        self.assertEqual((package / "implementation" / "program.vscore.json").read_bytes(), SOURCE)
        current = mechanical(package)
        self.assertEqual(current["mechanical_status"], "VERIFIED")
        self.assertEqual(current["endpoint"], "restricted_source")
        self.assertEqual(len(current["builds"]), 2)
        self.assertEqual({b["build"] for b in current["builds"]}, {"A", "B"})
        self.assertTrue(all(b["ok"] for b in current["builds"]))
        self.assertEqual(current["determinism"]["mismatches"], [])
        self.assertTrue(current["claims"])
        for claim in current["claims"]:
            if claim["required"]:
                self.assertEqual(claim["outcome"], "PASS", claim)

    def test_manual_pipeline_closes_without_running_a_host_campaign(self):
        self.assert_complete(self.manual, self.result)

    def test_one_command_pipeline_independently_closes(self):
        runs = self.tmp.path / "one-command"
        with patch("verislop.targets.python_target.inventory", side_effect=AssertionError("VSCore reached Python inventory")):
            code, result, output = run_cli(
                "run", "--prompt-file", str(FIXTURE / "request.txt"), "--request-ref",
                "examples/vscore-subtraction/request.txt", "--mode", "software", "--tier", "2", "--target", "vscore",
                "--draft-candidate", str(FIXTURE / "draft.json"), "--ledger-candidate", str(FIXTURE / "interpretation.json"),
                "--formalization-candidate", str(FIXTURE / "formalization"), "--proof-candidate",
                str(FIXTURE / "formalization" / "Contract.lean"), "--implementation-candidate", str(FIXTURE),
                "--runs-dir", str(runs), "--run-id", "subtraction", "--non-interactive")
        self.assertEqual(code, 0, (result, output))
        self.assert_complete(runs / "subtraction", result)

    def test_explicit_prepared_bridge_route_has_same_checked_program_and_coverage(self):
        package = copy_pkg(self.accepted, self.tmp.path / "prepared")
        _, _, info = checker.preview(Package(package, resolve_root=False), SOURCE, RELATION, proof=None)
        candidate = self.tmp.path / "prepared-candidate"
        candidate.mkdir()
        for name, data in checker.candidate_files("subtraction-prepared", info, SOURCE, RELATION, PROOF).items():
            (candidate / name).write_bytes(data)
        stage(package, "bridge", "prepare", "--proposal", str(candidate / "proposal.json"), "--candidate-dir", str(candidate))
        stage(package, "generate", "--tier", "2", "--target", "vscore", "--bridge-id", "subtraction-prepared")
        stage(package, "link")
        stage(package, "bridge", "accept", "--bridge-id", "subtraction-prepared")
        result = stage(package, "verify")
        self.assert_complete(package, result)
        a = canonical.load_file(self.manual / "implementation" / "materialization.json")
        b = canonical.load_file(package / "implementation" / "materialization.json")
        for field in ("source_hash", "program", "signatures", "entries"):
            if field in a:
                self.assertEqual(a[field], b[field])
        link_a = canonical.load_file(self.manual / "bridges" / "link.json")
        link_b = canonical.load_file(package / "bridges" / "link.json")
        self.assertEqual(link_a["covered"], link_b["covered"])

    def test_wrong_program_materializes_and_links_but_cannot_close(self):
        package = copy_pkg(self.accepted, self.tmp.path / "wrong-result")
        candidate = self.tmp.path / "wrong-result-candidate"
        candidate.mkdir()
        for name, data in (("program.vscore.json", NEGATIVES["underflow-is-success"]),
                           ("relation.json", RELATION), ("Proof.lean", PROOF)):
            (candidate / name).write_bytes(data)
        stage(package, "generate", "--tier", "2", "--target", "vscore", "--candidate", str(candidate))
        stage(package, "link")
        view = canonical.load_file(package / "obligation-view.json")
        for oid in REQUIRED:
            self.assertEqual(view["obligations"][oid]["lifecycle"]["IMPLEMENTED"]["outcome"], "PASS")
            self.assertEqual(view["obligations"][oid]["lifecycle"]["LINKED"]["outcome"], "PASS")
        code, rejected, _ = run_cli("bridge", "accept", "--package", str(package), "--bridge-id", "implementation")
        self.assertEqual(code, 2, rejected)
        self.assertIn("CANDIDATE_BUILD_FAILURE", codes(rejected))
        code, blocked, _ = run_cli("verify", "--package", str(package))
        self.assertEqual(code, 2, blocked)
        view = canonical.load_file(package / "obligation-view.json")
        self.assertTrue(all(view["obligations"][oid]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"] != "PASS"
                            for oid in REQUIRED))

    def test_delivered_source_copy_cannot_disagree_with_selected_bundle(self):
        package = copy_pkg(self.manual, self.tmp.path / "mutated-delivery")
        path = package / "implementation" / "program.vscore.json"
        writable(path)
        path.write_bytes(NEGATIVES["wrong-order"])
        code, rejected, _ = run_cli("verify", "--package", str(package))
        self.assertEqual(code, 2, rejected)
        self.assertIn("INPUT_MUTATION", codes(rejected))


if __name__ == "__main__":
    unittest.main()
