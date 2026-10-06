"""Tier 2 review normalization, pre-ballot identities and independent release gates."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import EX, MockLLM, TempDir, codes, copy_pkg, mock_config, run_cli, unanimous
from verislop import canonical, inspection, review, review_projection as projection, schemas
from verislop.backends import vscore_closure, vscore_release
from verislop.bridges.manifest import InvalidPackage
from verislop.errors import Diagnostic, UsageError
from verislop.package import Package
from verislop.stage import StageResult

ZERO = "sha256:" + "0" * 64


def evidence(vid="verislop.vscore-materializer"):
    return {"schema_version": "0.1", "evidence_id": "ev-fixture", "closure_id": "closure",
            "claim_id": "IMPLEMENTED:O1@1", "input_root_hash": ZERO, "verifier_id": vid, "verifier_hash": ZERO,
            "execution_environment": {"python": "3.12", "os": "linux"}, "invocation": ["verislop", "generate"],
            "raw_result_ref": "evidence/raw/fixture.json", "raw_result_hash": ZERO,
            "exit_code": 0, "status": "PASS", "scope": ["restricted_source"], "trusted_dependencies": ["kernel"]}


def raw():
    return {"claim_id": "IMPLEMENTED:O1@1", "sequence": 1, "recorded_at": "2026-01-01T00:00:00Z",
            "milestone_outcome": "PASS", "materialized": True, "inventory_hash": ZERO,
            "proof_checked": False, "symbols": ["f"], "objects": [], "source_hash": ZERO, "codes": []}


class VSCoreReviewProjectionUnits(unittest.TestCase):
    def test_only_explicit_metadata_paths_are_excluded(self):
        envelope = {"record": evidence(), "raw": {**raw(), "semantic": {"id": "a", "time": 3, "sequence": 7, "path": "/actual/source"}},
                    "execution": {"attempt_id": "a", "started_at": "now", "finished_at": "later", "wall_ms": 2, "work_directory": "/tmp/a"}}
        baseline = projection.project_envelope(envelope)
        changed = copy.deepcopy(envelope)
        for parent, key in projection.EXCLUDED_PATHS:
            changed[parent][key] = 123 if key in ("wall_ms", "sequence") else "fresh metadata"
        self.assertEqual(baseline, projection.project_envelope(changed))
        for name in ("id", "time", "sequence", "path"):
            changed = copy.deepcopy(envelope)
            changed["raw"]["semantic"][name] = "meaningfully changed"
            self.assertNotEqual(baseline, projection.project_envelope(changed))
        with self.assertRaises(InvalidPackage):
            projection.project_envelope({**envelope, "unknown": {}})
        changed = copy.deepcopy(envelope)
        changed["execution"]["toolchain"] = "different"
        with self.assertRaises(InvalidPackage):
            projection.project_envelope(changed)
        for metadata in ({"wall_ms": True}, {"wall_ms": -1}, {"attempt_id": {}}, {"started_at": None}):
            with self.subTest(metadata=metadata), self.assertRaises(InvalidPackage):
                projection.project_envelope({**envelope, "execution": metadata})

    def test_legacy_result_adapter_is_closed_and_preserves_environment_scope_trust_invocation(self):
        rec, result = evidence(), raw()
        _, baseline = projection.normalize(rec, result)
        for field, value in (("execution_environment", {"python": "3.12", "os": "other"}),
                             ("scope", ["stronger_scope"]), ("trusted_dependencies", ["different trust"]),
                             ("invocation", ["verislop", "other"]), ("verifier_hash", "sha256:" + "1" * 64)):
            changed = copy.deepcopy(rec)
            changed[field] = value
            self.assertNotEqual(baseline, projection.normalize(changed, result)[1], field)
        with self.assertRaises(InvalidPackage):
            projection.normalize(rec, {**result, "unknown_semantic_field": True})
        with self.assertRaises(InvalidPackage):
            projection.normalize({**rec, "unknown": True}, result)
        with self.assertRaises(InvalidPackage):
            projection.normalize(evidence("unregistered-producer"), result)
        for metadata in ({"sequence": True}, {"sequence": -1}, {"sequence": "1"}, {"recorded_at": {}}, {"recorded_at": ""}):
            with self.subTest(metadata=metadata), self.assertRaises(InvalidPackage):
                projection.normalize(rec, {**result, **metadata})

    def test_build_wall_time_mapping_is_explicit_and_unknown_execution_fields_block(self):
        observation = {"build": "A", "ok": True, "errors": [], "closure_root": ZERO,
                       "producer": {"verifier_id": "verislop.closure", "verifier_hash": ZERO},
                       "outputs": {key: {} for key in projection.OUTPUT_FIELDS}, "execution": {"wall_ms": 3}}
        first = projection._builds([observation], [])
        changed = copy.deepcopy(observation)
        changed["execution"]["wall_ms"] = 500
        self.assertEqual(first, projection._builds([changed], []))
        closure_record = {**evidence("verislop.closure"), "claim_id": "CLOSURE:clean-builds"}
        closure_raw = {"claim_id": "CLOSURE:clean-builds", "sequence": 2, "recorded_at": "2026-01-01T00:00:00Z",
                       "format": "verislop.closure-final-result/0.2", "milestone_outcome": "PASS", "binding_root": ZERO,
                       "predicate_satisfied": True, "builds": [observation], "determinism": {}, "nonfinal_claims": [],
                       "required_claim_ids": [], "endpoint": "restricted_source", "complete_required_coverage": True,
                       "declared_dependencies": [], "public_provenance_complete": True, "output_plan_complete": True}
        original = projection.normalize(closure_record, closure_raw)
        self.assertEqual(original, projection.normalize(closure_record, {**closure_raw, "builds": [changed]}))
        changed["outputs"]["contract_receipt"] = {"time": 500}
        self.assertNotEqual(first, projection._builds([changed], []))
        changed["execution"]["unknown"] = 1
        with self.assertRaises(InvalidPackage):
            projection._builds([changed], [])
        for duration in (True, -1, "3", {}):
            changed = copy.deepcopy(observation)
            changed["execution"]["wall_ms"] = duration
            with self.subTest(duration=duration), self.assertRaises(InvalidPackage):
                projection._builds([changed], [])

    def test_target_has_exact_non_circular_inputs(self):
        target = projection.review_target("release", ZERO, ZERO, ZERO, ZERO)
        self.assertEqual(set(target), {"format", "checkpoint", "closure_root", "mechanical_projection_hash",
                                       "reviewer_configuration_hash", "model_resolution_manifest_hash"})
        self.assertNotIn("ballots", target)
        self.assertNotIn("returned_model", target)

    def test_metadata_rerun_keeps_target_and_semantic_change_invalidates_it(self):
        rec, result = evidence(), raw()
        first = projection.normalize(rec, result)[1]
        rerun_rec = {**rec, "evidence_id": "fresh-id", "raw_result_ref": "fresh-ref", "raw_result_hash": "sha256:" + "1" * 64}
        rerun = projection.normalize(rerun_rec, {**result, "sequence": 8, "recorded_at": "2026-02-01T00:00:00Z"})[1]
        a = projection.review_target("release", ZERO, canonical.digest_json(first), ZERO, ZERO)
        b = projection.review_target("release", ZERO, canonical.digest_json(rerun), ZERO, ZERO)
        self.assertEqual(canonical.digest_json(a), canonical.digest_json(b))
        changed = projection.normalize(rec, {**result, "source_hash": "sha256:" + "2" * 64})[1]
        self.assertNotEqual(canonical.digest_json(a), canonical.digest_json(
            projection.review_target("release", ZERO, canonical.digest_json(changed), ZERO, ZERO)))

    def test_malformed_pinned_model_configuration_is_rejected(self):
        conf = canonical.load_file(EX / "review-config.json")
        agent = next(iter(conf["agents"]))
        for identity in ({"mode": "pinned"}, {"mode": "alias", "resolved_model": "snapshot"},
                         {"mode": "pinned", "resolved_model": ""},
                         {"mode": "pinned", "resolved_model": "snapshot", "learned_from_ballot": True}):
            changed = copy.deepcopy(conf)
            changed["agents"][agent]["model_identity"] = identity
            self.assertTrue(schemas.validate("review-config", changed), identity)

    def test_vscore_inspection_marks_recorded_gate_while_legacy_output_is_preserved(self):
        res = StageResult("inspect", "PASS", "read-only", summary={"terminal_status": "VERIFIED"}, lines=["report"])
        with patch("verislop.backends.registry.frozen_claims", return_value={"schema_version": "0.2", "format": "verislop.implementation-claims/0.2"}):
            marked = inspection._recorded_vscore(object(), res)
        self.assertEqual(marked.summary["freshness"], "recorded_execution_only")
        self.assertIn("Recorded", marked.lines[0])
        self.assertFalse(marked.to_json()["asserts_closure_verified"])
        legacy = StageResult("inspect", "PASS", "read-only", summary={"terminal_status": "VERIFIED"}, lines=["report"])
        with patch("verislop.backends.registry.frozen_claims", return_value={"schema_version": "0.1"}):
            unchanged = inspection._recorded_vscore(object(), legacy)
        self.assertEqual(unchanged.summary, {"terminal_status": "VERIFIED"})
        self.assertEqual(unchanged.lines, ["report"])

    def test_historical_vscore_report_stays_recorded_when_claims_are_missing_or_unreadable(self):
        with tempfile.TemporaryDirectory() as location:
            path = Path(location)
            package = SimpleNamespace(path=lambda slot: path / (slot + ".json"))
            (path / "report.json").write_bytes(canonical.dumps({"schema_version": "0.2", "target": "vscore",
                "backend": "verislop.backend.vscore/0.1", "terminal_status": "VERIFIED",
                "freshness": "current execution revalidated"}))
            for command in ("inspect", "status", "explain-block"):
                result = StageResult(command, "PASS", "read-only", summary={"terminal_status": "VERIFIED"}, lines=["report"])
                with patch("verislop.backends.registry.frozen_claims", return_value=None):
                    marked = inspection._recorded_vscore(package, result)
                self.assertEqual(marked.summary["freshness"], "recorded_execution_only")
                self.assertFalse(marked.to_json()["asserts_closure_verified"])
            result = StageResult("inspect", "PASS", "read-only", summary={}, lines=["report"])
            with patch("verislop.backends.registry.frozen_claims", side_effect=ValueError("malformed claims")):
                marked = inspection._recorded_vscore(package, result)
            self.assertEqual(marked.summary["freshness"], "recorded_execution_only")
            self.assertEqual(marked.status, "BLOCKED")
            self.assertIn("INVALID_CANDIDATE", [d.code for d in marked.diagnostics])
            (path / "report.json").write_bytes(canonical.dumps({"schema_version": "0.1", "target": "python"}))
            legacy = StageResult("status", "PASS", "read-only", summary={"terminal_status": "VERIFIED"}, lines=["report"])
            with patch("verislop.backends.registry.frozen_claims", return_value=None):
                self.assertEqual(inspection._recorded_vscore(package, legacy).summary, {"terminal_status": "VERIFIED"})

    def test_model_identity_policy_is_frozen_before_responses(self):
        conf = {"agents": {"r": {"provider": "p", "model_ref": "alias"}}, "review": {}}
        resolved = SimpleNamespace(profiles={"p": {"base_url": "https://provider.invalid", "adapter": "test"}})
        manifest = review.model_resolution_manifest(conf, resolved, {"r": "alias"})
        self.assertEqual(manifest["models"][0]["mode"], "provider_alias")
        self.assertIn("request time", manifest["models"][0]["trust"])
        original = canonical.digest_json(manifest)
        self.assertTrue(review._model_matches(manifest, "r", "alias", "snapshot-1"))
        self.assertTrue(review._model_matches(manifest, "r", "alias", "snapshot-2"))
        self.assertEqual(original, canonical.digest_json(manifest))
        conf["review"]["require_fixed_model_snapshot"] = True
        with self.assertRaises(UsageError):
            review.model_resolution_manifest(conf, resolved, {"r": "alias"})
        conf["agents"]["r"]["model_identity"] = {"mode": "pinned", "resolved_model": "snapshot-1"}
        pinned = review.model_resolution_manifest(conf, resolved, {"r": "alias"})
        self.assertTrue(review._model_matches(pinned, "r", "alias", "snapshot-1"))
        self.assertFalse(review._model_matches(pinned, "r", "alias", "snapshot-2"))

    def test_internal_pending_claim_vetoes_unanimous_review(self):
        snapshot = {"mechanical_status": "BLOCKED", "claims": [{"claim_id": "CLOSURE:provenance", "required": True, "outcome": "PENDING"}]}
        with patch("verislop.backends.registry.is_vscore", return_value=True), \
             patch.object(vscore_closure, "mechanical_snapshot", return_value=snapshot):
            veto = review._mechanical_veto(object(), "release")
        self.assertIn("CLOSURE:provenance", veto)
        tier = unanimous("r", "reviewer", 1)
        tally = review.tally_tier(tier, ["r/reviewer#1"], {"r/reviewer#1": {"verdict": "ACCEPT", "unresolved_blocking_findings": []}}, veto)
        self.assertEqual(tally["result"], "CHANGES_REQUESTED")

    def test_finalize_requires_a_snapshot_and_rechecks_currency_after_review(self):
        missing = vscore_release.finalize(object(), object(), None)
        self.assertEqual(missing.summary["mechanical_status"], "BLOCKED")
        self.assertIn("VERIFIER_NOT_RUN", [d.code for d in missing.diagnostics])
        with tempfile.TemporaryDirectory() as location:
            tmp = SimpleNamespace(path=Path(location))
            snapshot = {"diagnostics": [], "mechanical_status": "VERIFIED", "parameters": {}, "builds": [],
                        "determinism": {}, "closure_root": ZERO, "provenance": {}, "closure_id": "c",
                        "mechanical_result_path": "closure/executions/a/mechanical-result.json"}
            package = SimpleNamespace(path=lambda slot: tmp.path / slot, rel=lambda path: str(path))
            (tmp.path / "closure").mkdir()
            (tmp.path / "closure" / "review-config.json").write_text("{}")
            event = SimpleNamespace(emit=lambda *args: None)
            projected = {"projection_hash": ZERO, "normalizer_registry_hash": ZERO, "raw_inventory_hash": ZERO}
            rejection = {"configured": True, "checkpoints": {}, "diagnostics": [Diagnostic("REVIEW_REJECTED", "review rejected")]}
            cases = [("initial publication changed", [{**snapshot, "closure_id": "changed"}], [[], []], "BLOCKED"),
                     ("initial frozen inputs changed", [snapshot], [[Diagnostic("INPUT_MUTATION", "changed")]], "BLOCKED"),
                     ("final publication changed", [snapshot, {**snapshot, "closure_id": "changed"}], [[], []], "BLOCKED"),
                     ("final frozen inputs changed", [snapshot], [[], [Diagnostic("INPUT_MUTATION", "changed")]], "BLOCKED"),
                     ("review rejection only", [snapshot, snapshot], [[], []], "VERIFIED")]
            for name, publications, validation, expected in cases:
                with self.subTest(name=name), patch.object(schemas, "validate", return_value=[]), \
                     patch.object(vscore_closure, "mechanical_snapshot", side_effect=publications), \
                     patch.object(vscore_closure, "validate_frozen", side_effect=validation), \
                     patch.object(projection, "build", return_value=projected), \
                     patch.object(review, "gate", return_value=rejection), \
                     patch.object(vscore_release.view, "derive", return_value={}), \
                     patch.object(vscore_release.view, "write"), \
                     patch.object(vscore_release.report, "build", side_effect=lambda *a: {"endpoint": {"established": None}}), \
                     patch.object(vscore_release.report, "render_lines", return_value=[]), \
                     patch.object(vscore_release.fsutil, "write_json") as writer:
                    result = vscore_release.finalize(package, event, snapshot)
                    emitted = writer.call_args.args[1]
                    self.assertEqual(result.summary["mechanical_status"], expected)
                    self.assertEqual(emitted["freshness"], "current execution revalidated" if expected == "VERIFIED" else "recorded_execution_only")
                    self.assertEqual(emitted["endpoint"]["established"], "restricted_source" if expected == "VERIFIED" else None)
                    self.assertEqual(snapshot["mechanical_status"], "VERIFIED")


class VSCoreReviewIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.verdict = "ACCEPT"
        def handler(system, user, model):
            packet = json.loads(user.split("\n", 1)[1].split("\nLOWER-TIER", 1)[0])
            return json.dumps({"verdict": cls.verdict, "reviewed_obligations": packet["scope"],
                               "findings": [], "limitations": ["mock review"], "rationale": "fixture"})
        cls.mock = MockLLM(handler)
        cls.config, cls.env = mock_config(cls.tmp.path, cls.mock.port, [unanimous("release", "r", 1)], checkpoints=["release"])
        cls.base = cls.tmp.path / "base"
        stages = [
            ("interpret", ["--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt", "--candidate", str(EX / "draft.json"), "--ledger", str(EX / "interpretation.json"), "--non-interactive"]),
            ("formalize", ["--candidate", str(EX / "formalization")]), ("prove", []), ("accept", []), ("export", []),
            ("generate", ["--tier", "2", "--target", "vscore", "--candidate", str(EX / "vscore")]), ("link", []),
            ("bridge", ["accept", "--bridge-id", "implementation"]), ("verify", [])]
        for command, args in stages:
            argv = [command, args[0], "--package", str(cls.base), *args[1:]] if command == "bridge" else [command, "--package", str(cls.base), *args]
            code, result, output = run_cli(*argv)
            if code:
                raise AssertionError((command, code, result, output))

    @classmethod
    def tearDownClass(cls):
        cls.mock.close()
        cls.tmp.cleanup()

    def setUp(self):
        self.verdict = type(self).verdict = "ACCEPT"
        self.package = copy_pkg(self.base, self.tmp.path / self._testMethodName)

    def cli(self, *args):
        return run_cli(*args, "--package", str(self.package), env=self.env)

    def test_fresh_verifies_change_raw_inventory_but_reuse_validated_projection_target(self):
        code, blocked, _ = self.cli("verify", "--config", str(self.config))
        self.assertEqual(code, 2, blocked)
        self.assertEqual(blocked["summary"]["mechanical_status"], "VERIFIED")
        self.assertIn("REVIEW_NOT_RUN", codes(blocked))
        code, accepted, _ = self.cli("review", "--checkpoint", "release", "--config", str(self.config))
        self.assertEqual(code, 0, accepted)
        packet = review.build_packet(Package(self.package, resolve_root=False), "release")
        self.assertIn("normative Lean", packet["assurance_boundary"])
        self.assertTrue(packet["required_mechanical_claims"])
        code, fresh, _ = self.cli("verify", "--config", str(self.config))
        self.assertEqual(code, 0, fresh)
        report = canonical.load_file(self.package / "report.json")
        reused = report["review_projection"]["reuse"]["release"]
        self.assertNotEqual(reused["original_raw_inventory_hash"], reused["current_raw_inventory_hash"])
        self.assertEqual(report["review_projection"]["hash"], reused["projection_hash"])
        self.assertEqual(report["review_target"], accepted["summary"]["target_root"])

    def test_review_rejection_preserves_mechanical_e2e_and_prevents_python_repair(self):
        type(self).verdict = "REJECT"
        conf = canonical.load_file(self.config)
        conf["review"]["budgets"]["max_repair_rounds"] = 2
        path = self.tmp.path / "repair-policy.json"
        path.write_bytes(canonical.dumps(conf))
        with patch("verislop.review._repair", side_effect=AssertionError("frozen VSCore entered Python repair")):
            code, rejected, _ = self.cli("review", "--checkpoint", "release", "--config", str(path))
        self.assertEqual(code, 2, rejected)
        code, blocked, _ = self.cli("verify", "--config", str(path))
        self.assertEqual(code, 2, blocked)
        self.assertEqual(blocked["summary"]["mechanical_status"], "VERIFIED")
        self.assertEqual(blocked["summary"]["release_status"], "BLOCKED")
        view = canonical.load_file(self.package / "obligation-view.json")
        self.assertEqual(view["obligations"]["O17"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "PASS")

    def test_changed_reviewer_policy_and_pinned_response_identity_invalidate_review(self):
        code, accepted, _ = self.cli("review", "--checkpoint", "release", "--config", str(self.config))
        self.assertEqual(code, 0, accepted)
        conf = canonical.load_file(self.config)
        conf["agents"]["r"]["model_identity"] = {"mode": "pinned", "resolved_model": "different-from-mock"}
        conf["review"]["require_fixed_model_snapshot"] = True
        path = self.tmp.path / "pinned-policy.json"
        path.write_bytes(canonical.dumps(conf))
        code, stale, _ = self.cli("verify", "--config", str(path))
        self.assertEqual(code, 2, stale)
        self.assertIn("REVIEW_NOT_RUN", codes(stale))
        code, mismatch, _ = self.cli("review", "--checkpoint", "release", "--config", str(path))
        self.assertEqual(code, 2, mismatch)

    def test_one_command_run_accepts_all_configured_checkpoints_without_retargeting_prior_votes(self):
        conf = canonical.load_file(self.config)
        conf["review"]["checkpoints"] = ["interpretation", "formal_contract", "implementation", "release"]
        config = self.tmp.path / "all-checkpoints.json"
        config.write_bytes(canonical.dumps(conf))
        runs = self.tmp.path / "all-checkpoint-runs"
        code, result, output = run_cli("run", "--prompt-file", str(EX / "request.txt"), "--request-ref", "examples/request.txt",
            "--mode", "software", "--tier", "2", "--target", "vscore", "--config", str(config),
            "--draft-candidate", str(EX / "draft.json"), "--ledger-candidate", str(EX / "interpretation.json"),
            "--formalization-candidate", str(EX / "formalization"), "--implementation-candidate", str(EX / "vscore"),
            "--runs-dir", str(runs), "--run-id", "all-checkpoints", "--non-interactive", env=self.env)
        self.assertEqual(code, 0, (result, output))
        self.assertEqual(result["summary"]["mechanical_status"], "VERIFIED")
        self.assertEqual(result["summary"]["release_status"], "ACCEPTED")
        package = Package(runs / "all-checkpoints", resolve_root=False)
        report = canonical.load_file(package.path("report"))
        self.assertEqual(set(report["review"]["checkpoints"].values()), {"REVIEW_ACCEPTED"})
        packets = {canonical.load_file(p)["checkpoint"]: canonical.load_file(p)
                   for p in package.path("reviews").glob("rc-*/packet.json")}
        self.assertNotIn("implementation", packets["formal_contract"])
        self.assertNotIn("mechanical_snapshot", packets["implementation"])
        self.assertIn("mechanical_snapshot", packets["release"])
        self.assertEqual([row["stage"] for row in result["summary"]["stages"]].count("verify"), 1)


if __name__ == "__main__":
    unittest.main()
