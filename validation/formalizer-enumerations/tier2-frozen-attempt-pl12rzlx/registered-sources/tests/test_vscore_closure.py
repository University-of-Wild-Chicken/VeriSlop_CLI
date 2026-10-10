"""Full source closure and mutation/publication regressions for Tier 2."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import EX, TempDir, copy_pkg, run_cli, writable
from test_vscore import accepted_run
from verislop import canonical, closure, fsutil, schemas, testing, view
from verislop.claimcheck import evaluate_claim
from verislop.evidence import validated_execution
from verislop.backends import vscore_closure as vc
from verislop.events import EventSink
from verislop.package import Package


class VSCoreClosureUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.pkg = Package(self.tmp.path)
        self.pkg.ensure("closure-unit")

    def tearDown(self):
        self.tmp.cleanup()

    def test_unknown_frozen_format_never_dispatches_to_python(self):
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json",
                          {"schema_version": "9.9", "format": "candidate.backend", "parameters": {"tier": 2}})
        with patch.object(closure.pt, "byte_compile", side_effect=AssertionError("Python reached")):
            result = closure.run(self.pkg, EventSink("unit", quiet=True))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("UNSUPPORTED_CAPABILITY", {d.code for d in result.diagnostics})

    def test_metadata_and_wrong_issuer_cannot_satisfy_semantic_closure(self):
        root = "sha256:" + "0" * 64
        claim = {"claim_id": "CLOSURE:endpoint", "verifier": "verislop.closure",
                 "root_kind": "closure_root", "result_predicate": "closure-endpoint/0.2"}
        for issuer, result in (
            ("verislop.closure", {"milestone_outcome": "PASS"}),
            ("verislop.bridge-preparation", {"format": "closure-endpoint/0.2", "milestone_outcome": "PASS",
                "binding_root": "closure_root", "predicate_satisfied": True,
                "endpoint": "restricted_source", "complete_required_coverage": True}),
        ):
            ev = self.pkg.evidence.record(claim_id=claim["claim_id"], verifier_id=issuer, status="PASS",
                scope=["restricted_source"], input_root=root, result=result, invocation=["unit"])
            checked = evaluate_claim(claim, [ev], {"closure_root": root}, "closure_root")
            self.assertNotEqual(checked.outcome, "PASS")

    def test_total_wall_bound_interrupts_a_build_operation(self):
        with self.assertRaises(vc.InvalidPackage) as failure:
            with vc._wall_bound(0.02):
                time.sleep(1)
        self.assertEqual(failure.exception.code, "CLEAN_BUILD_FAILURE")

    def test_expected_selection_failures_are_structured_blocks(self):
        failure = vc.checker.EdgeFailure([vc.Diagnostic("INPUT_MUTATION", "selected source changed")])
        with patch.object(vc, "_selection", side_effect=failure):
            self.assertEqual({d.code for d in vc.freeze(self.pkg)}, {"INPUT_MUTATION"})
            result = vc.run(self.pkg, EventSink("unit", quiet=True))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("INPUT_MUTATION", {d.code for d in result.diagnostics})

    def test_live_toolchain_binary_mutation_is_not_hidden_by_identity_cache(self):
        executable = self.tmp.path / "lean"
        executable.write_bytes(b"original executable")
        expected = canonical.digest(executable.read_bytes())
        cached = SimpleNamespace(lean=executable, identity=lambda: {"lean_binary_sha256": expected})
        cert = {"toolchain": {"pin": "pinned", "lean_binary_sha256": expected}}
        with patch.object(vc.leanbridge, "resolve_toolchain", return_value=cached):
            vc._check_toolchain_binary(cert)
            executable.write_bytes(b"mutated executable")
            with self.assertRaises(vc.InvalidPackage) as failure:
                vc._check_toolchain_binary(cert)
        self.assertEqual(failure.exception.code, "UNDECLARED_DEPENDENCY")


class VSCoreClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.package = accepted_run(cls.tmp.path)
        for command in (
            ("generate", "--package", str(cls.package), "--tier", "2", "--target", "vscore",
             "--candidate", str(EX / "vscore")),
            ("link", "--package", str(cls.package)),
            ("bridge", "accept", "--package", str(cls.package), "--bridge-id", "implementation"),
            ("verify", "--package", str(cls.package)),
        ):
            code, result, output = run_cli(*command)
            if code:
                raise AssertionError((command, result, output))

    def copy(self, label):
        return copy_pkg(self.package, self.tmp.path / (self.id().split(".")[-1] + "-" + label))

    def test_two_full_builds_and_exact_finite_boundary(self):
        pkg = Package(self.package)
        result = vc.mechanical_snapshot(pkg)
        self.assertEqual(result["mechanical_status"], "VERIFIED")
        self.assertEqual(len(result["builds"]), 2)
        for build in result["builds"]:
            self.assertTrue(build["ok"])
            self.assertEqual(set(build["outputs"]), set(vc.COMPARISON_SLOTS))
            self.assertTrue(build["outputs"]["contract_receipt"]["accepted_contract_replayed"])
            self.assertIn("VSCore.Semantics", build["outputs"]["module_parts"])
            self.assertIn("VeriSlopContract", build["outputs"]["module_parts"])
            self.assertIn("VeriSlopBridgeProof", build["outputs"]["module_parts"])
        self.assertEqual(result["builds"][0]["outputs"], result["builds"][1]["outputs"])
        current = view.derive(pkg)["obligations"]
        for oid in ("O17", "I2", "E1"):
            self.assertEqual(current[oid]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "PASS")
            self.assertEqual(current[oid]["lifecycle"]["TESTED"]["outcome"], "PENDING")
        witnesses = [rec for rec in current.values() if rec["kind"] == "non_vacuity"]
        self.assertTrue(witnesses)
        self.assertTrue(all(rec["lifecycle"]["END_TO_END_VERIFIED"]["outcome"] == "NOT_APPLICABLE" for rec in witnesses))
        self.assertTrue(any("host interpreter" in line for line in result["boundary"]["excluded_surface"]))
        self.assertEqual({"INTERPRETATION:request"} - {c["claim_id"] for c in result["claims"]}, set())
        self.assertTrue(any(c["claim_id"].startswith("REIFIED:") for c in result["claims"]))

    def test_explicit_campaign_request_does_not_run_python_or_erase_proof_closure(self):
        package = Package(self.copy("unsupported-campaign"))
        before = {ev.id for ev in package.evidence.load()}
        snapshot = vc.mechanical_snapshot(package)
        with patch.object(testing, "execute", side_effect=AssertionError("Python harness reached")):
            result = testing.run(package, EventSink("unsupported-campaign", quiet=True))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("UNSUPPORTED_CAPABILITY", {d.code for d in result.diagnostics})
        package.reset_evidence_cache()
        self.assertEqual({ev.id for ev in package.evidence.load()}, before)
        self.assertEqual(vc.mechanical_snapshot(package)["mechanical_result_path"], snapshot["mechanical_result_path"])
        current = view.derive(package)["obligations"]
        for oid in ("O17", "I2", "E1"):
            self.assertEqual(current[oid]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "PASS")
            self.assertEqual(current[oid]["lifecycle"]["TESTED"]["outcome"], "PENDING")

    def test_frozen_membership_and_exact_bytes_are_required(self):
        mutations = {
            "source-whitespace": lambda pkg: self.append(pkg / "implementation/program.vscore.json"),
            "extra-source": lambda pkg: fsutil.atomic_write(pkg / "implementation/helper.vscore.json", b"{}"),
            "extra-bridge-input": lambda pkg: fsutil.atomic_write(pkg / "bridges/implementation/undeclared.json", b"{}"),
            "deleted-selection": lambda pkg: (pkg / "closure/selection.json").unlink(),
        }
        for label, edit in mutations.items():
            with self.subTest(mutation=label):
                pkg = self.copy(label)
                edit(pkg)
                self.assertTrue(vc.validate_frozen(Package(pkg)))
                with patch.object(closure.pt, "byte_compile", side_effect=AssertionError("Python backend called")):
                    result = closure.run(Package(pkg), EventSink("mutation", quiet=True))
                self.assertNotEqual(result.status, "PASS")

    @staticmethod
    def append(path):
        writable(path)
        path.write_bytes(path.read_bytes() + b"\n")

    def test_internal_claim_wrong_issuer_or_coverage_cannot_be_waived(self):
        for label, edit in (
            ("issuer", lambda data: next(c for c in data["claims"] if c["claim_id"].startswith("BRIDGE:") and c["root_kind"] == "semantic_edge").update(verifier="verislop.closure")),
            ("requiredness", lambda data: next(c for c in data["claims"] if c["claim_id"] == "CLOSURE:provenance").update(required=False)),
            ("premises", lambda data: next(c for c in data["claims"] if c["milestone"] == "END_TO_END_VERIFIED" and c["required"]).update(premises=[])),
        ):
            with self.subTest(mutation=label):
                pkg = self.copy(label)
                path = pkg / "closure/implementation-claims.json"
                data = canonical.load_file(path)
                edit(data)
                writable(path)
                fsutil.write_json(path, data)
                self.assertIn("CLAIM_MUTATION", {d.code for d in vc.validate_frozen(Package(pkg))})

    def test_missing_duplicate_and_cyclic_internal_claims_fail_closed(self):
        def internal(data):
            return next(c for c in data["claims"] if c["claim_id"].startswith("BRIDGE:")
                        and c["root_kind"] == "semantic_edge")

        def remove_internal(data):
            data["claims"].remove(internal(data))

        def duplicate_id(data):
            data["claims"].append(dict(internal(data)))

        def cycle(data):
            claim = internal(data)
            claim["premises"].append(claim["claim_id"])

        for label, edit in (("missing-internal", remove_internal),
                            ("duplicate-id", duplicate_id), ("cyclic-premise", cycle)):
            with self.subTest(mutation=label):
                pkg = self.copy(label)
                path = pkg / "closure/implementation-claims.json"
                data = canonical.load_file(path)
                edit(data)
                writable(path)
                fsutil.write_json(path, data)
                self.assertIn("CLAIM_MUTATION", {d.code for d in vc.validate_frozen(Package(pkg))})
                result = closure.run(Package(pkg), EventSink("invalid-graph", quiet=True))
                self.assertEqual(result.status, "BLOCKED")
                self.assertIn("CLAIM_MUTATION", {d.code for d in result.diagnostics})

    def test_detached_selected_endpoint_cannot_reuse_complete_execution(self):
        pkg = self.copy("detached-endpoint")
        path = pkg / "closure/selection.json"
        selection = canonical.load_file(path)
        selection["endpoint_node"] = "unconnected-endpoint"
        writable(path)
        fsutil.write_json(path, selection)
        self.assertIn("INPUT_MUTATION", {d.code for d in vc.validate_frozen(Package(pkg))})
        result = closure.run(Package(pkg), EventSink("detached-endpoint", quiet=True))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("INPUT_MUTATION", {d.code for d in result.diagnostics})

    def test_certificate_metadata_and_undeclared_trust_fail_closed(self):
        pkg = self.copy("certificate")
        selection = canonical.load_file(pkg / "closure/selection.json")
        cert = pkg / "bridges/implementation/semantic" / vc.checker.edge_key(selection["edge_id"]) / "certificate.json"
        data = canonical.load_file(cert)
        data["symbols"][0]["lean_decl"] = "Unproved.replacement"
        writable(cert)
        fsutil.write_json(cert, data)
        self.assertTrue(vc.validate_frozen(Package(pkg)))
        pkg = self.copy("trust")
        path = pkg / "closure/tcb.json"
        data = canonical.load_file(path)
        data["trusted"].append("waived semantic correspondence")
        writable(path)
        fsutil.write_json(path, data)
        self.assertIn("UNDECLARED_DEPENDENCY", {d.code for d in vc.validate_frozen(Package(pkg))})

    def test_execution_inventory_and_result_formats_are_closed(self):
        pkg = self.copy("result")
        snapshot = vc.mechanical_snapshot(Package(pkg))
        folder = (pkg / snapshot["mechanical_result_path"]).parent
        fsutil.atomic_write(folder / "unlisted.json", b"{}")
        with self.assertRaises(vc.InvalidPackage):
            vc.validate_execution(folder)
        result = {k: v for k, v in snapshot.items() if k != "mechanical_result_path"}
        result["candidate_supplied_pass"] = True
        self.assertTrue(schemas.validate("mechanical-result", result))

    def test_empty_claims_failed_builds_and_missing_outputs_cannot_publish_verified(self):
        changes = {
            "empty-claims": lambda data: data.update(claims=[]),
            "failed-build": lambda data: data["builds"][1].update(ok=False),
            "missing-output": lambda data: data["builds"][0]["outputs"].pop("implementation_ir"),
        }
        for label, edit in changes.items():
            with self.subTest(mutation=label):
                pkg = self.copy(label)
                snapshot = vc.mechanical_snapshot(Package(pkg))
                path = pkg / snapshot["mechanical_result_path"]
                data = canonical.load_file(path)
                edit(data)
                writable(path)
                fsutil.write_json(path, data)
                with self.assertRaises(ValueError):
                    validated_execution(path.parent)

    def test_duplicate_or_unsorted_publication_rows_cannot_reuse_checked_evidence(self):
        def duplicate_terminal(data):
            claim = dict(next(row for row in data["claims"] if row["claim_id"] == "CLOSURE:endpoint"))
            claim["reason"] = "different reason for the same checked terminal claim"
            data["claims"].append(claim)
            data["claims"].sort(key=lambda row: row["claim_id"])

        def duplicate_path(data):
            data["execution_inventory"].append(dict(data["execution_inventory"][0]))
            data["execution_inventory"].sort(key=lambda row: row["path"])

        for label, expected_code, edit in (
            ("duplicate-terminal", "ORPHAN_CLAIM", duplicate_terminal),
            ("unsorted-claims", "ORPHAN_CLAIM", lambda data: data["claims"].reverse()),
            ("duplicate-path", "INPUT_MUTATION", duplicate_path),
            ("unsorted-paths", "INPUT_MUTATION", lambda data: data["execution_inventory"].reverse()),
        ):
            with self.subTest(mutation=label):
                pkg = self.copy(label)
                snapshot = vc.mechanical_snapshot(Package(pkg))
                path = pkg / snapshot["mechanical_result_path"]
                data = canonical.load_file(path)
                edit(data)
                self.assertFalse(schemas.validate("mechanical-result", data))
                writable(path)
                fsutil.write_json(path, data)
                with self.assertRaises(vc.InvalidPackage) as failure:
                    vc.validate_execution(path.parent)
                self.assertEqual(failure.exception.code, expected_code)
                with self.assertRaises(ValueError):
                    validated_execution(path.parent)

    def test_self_consistent_inventory_cannot_hide_mutated_consumed_result(self):
        pkg = self.copy("consumed-result")
        snapshot = vc.mechanical_snapshot(Package(pkg))
        path = pkg / snapshot["mechanical_result_path"]
        data = canonical.load_file(path)
        row = next(row for row in data["execution_inventory"] if row["path"].startswith("consumed/") and row["path"].endswith("/raw.json"))
        raw_path = path.parent / row["path"]
        raw = canonical.load_file(raw_path)
        raw["milestone_outcome"] = "FAIL"
        writable(raw_path)
        payload = fsutil.write_json(raw_path, raw)
        row.update(sha256=canonical.digest(payload), size=len(payload))
        writable(path)
        fsutil.write_json(path, data)
        with self.assertRaises(ValueError):
            validated_execution(path.parent)

    def test_publication_failure_exposes_no_staged_e2e_pass(self):
        pkg = self.copy("publication")
        package = Package(pkg)
        before = {ev.id for ev in package.evidence.load()}
        snapshot = vc.mechanical_snapshot(package)
        folder = (pkg / snapshot["mechanical_result_path"]).parent
        builds = []
        for original in snapshot["builds"]:
            replay = vc.BuildObservation(original)
            prefix = "builds/" + original["build"] + "/"
            replay.artifacts = {row["path"][len(prefix):]: (folder / row["path"]).read_bytes()
                                for row in snapshot["execution_inventory"] if row["path"].startswith(prefix)}
            builds.append(replay)
        with patch.object(vc, "clean_build", side_effect=builds), \
             patch.object(vc, "publish_into", side_effect=OSError("publication unavailable")):
            result = vc.run(package, EventSink("publication", quiet=True))
        self.assertEqual(result.status, "INFRASTRUCTURE_FAILURE")
        package.reset_evidence_cache()
        self.assertEqual({ev.id for ev in package.evidence.load()}, before)


if __name__ == "__main__":
    unittest.main()
