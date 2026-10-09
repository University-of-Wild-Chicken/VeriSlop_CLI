"""Assigned-issuer, root and typed-result checks for authoritative claim evidence."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import EX, TempDir, build, codes, copy_pkg, stage, writable
from verislop import canonical, formalize, view
from verislop.claimcheck import evaluate_claim
from verislop.evidence import Evidence
from verislop.package import Package
from verislop.verifiers import verifier_hash

ROOT = "sha256:" + "1" * 64
OTHER = "sha256:" + "2" * 64
ISSUER = "verislop.lean-acceptance"
CLAIM = {"claim_id": "PROVED:O17@1", "verifier": ISSUER}


def evidence(*, issuer=ISSUER, root=ROOT, status="PASS", outcome="PASS", sequence=1,
             result=None, problems=(), exit_code=0):
    return Evidence(
        {"evidence_id": f"ev-{sequence}", "claim_id": CLAIM["claim_id"], "verifier_id": issuer,
         "verifier_hash": verifier_hash(issuer), "input_root_hash": root, "status": status,
         "scope": ["test"], "exit_code": exit_code},
        {"sequence": sequence, "milestone_outcome": outcome, **(result or {})}, list(problems))


class ClaimCheckTests(unittest.TestCase):
    def check(self, records, claim=CLAIM, roots=None):
        return evaluate_claim(claim, records, roots or {"contract_input_root": ROOT}, "contract_input_root")

    def test_current_exact_issuer_and_root_pass(self):
        checked = self.check([evidence()])
        self.assertEqual(checked.outcome, "PASS")
        self.assertTrue(checked.authorized)
        self.assertEqual(checked.entry()["evidence_refs"], ["evidence:ev-1"])

    def test_wrong_registered_issuer_cannot_supply_proof(self):
        checked = self.check([evidence(issuer="verislop.review-consensus")])
        self.assertEqual(checked.outcome, "STALE")
        self.assertFalse(checked.authorized)

    def test_raw_binding_root_cannot_choose_weaker_root(self):
        checked = self.check([evidence(root=OTHER, result={"binding_root": "implementation_root"})],
                             roots={"contract_input_root": ROOT, "implementation_root": OTHER})
        self.assertEqual(checked.outcome, "STALE")
        # Even coincidentally identical digests cannot change a frozen root's kind.
        checked = self.check([evidence(result={"binding_root": "implementation_root"})],
                             roots={"contract_input_root": ROOT, "implementation_root": ROOT})
        self.assertEqual(checked.outcome, "STALE")

    def test_claim_decides_new_root_kind_and_issuer_spelling(self):
        claim = {"claim_id": CLAIM["claim_id"], "verifier_id": ISSUER, "root_kind": "semantic_edge"}
        self.assertEqual(self.check([evidence()], claim, {"semantic_edge": ROOT}).outcome, "PASS")

    def test_conflicting_assigned_issuers_fail_closed(self):
        claim = {**CLAIM, "verifier_id": "verislop.review-consensus"}
        self.assertEqual(self.check([evidence()], claim).outcome, "FAIL")

    def test_changed_verifier_and_bad_integrity_are_stale(self):
        e = evidence()
        e.record["verifier_hash"] = OTHER
        self.assertEqual(self.check([e]).outcome, "STALE")
        self.assertEqual(self.check([evidence(problems=["raw result hash mismatch"])]).outcome, "STALE")

    def test_latest_current_failure_is_not_hidden_by_old_pass_or_wrong_issuer(self):
        records = [evidence(), evidence(status="BLOCK", outcome="FAIL", sequence=2),
                   evidence(issuer="verislop.review-consensus", sequence=3)]
        checked = self.check(records)
        self.assertEqual(checked.outcome, "FAIL")
        self.assertEqual(checked.evidence.id, "ev-2")
        records.append(evidence(root=OTHER, sequence=4))
        self.assertEqual(self.check(records).outcome, "FAIL")

    def test_malformed_latest_authorized_record_never_falls_back_to_pass(self):
        records = [evidence(), evidence(sequence=2, problems=["tampered"])]
        self.assertEqual(self.check(records).outcome, "STALE")
        records[-1] = evidence(sequence=2, outcome="FAIL")
        self.assertEqual(self.check(records).outcome, "FAIL")

    def test_typed_pass_and_zero_exit_are_required(self):
        for outcome in (None, True, "FAIL", "NOT_APPLICABLE"):
            with self.subTest(outcome=outcome):
                self.assertEqual(self.check([evidence(outcome=outcome)]).outcome, "FAIL")
        for code in (1, True, None):
            self.assertEqual(self.check([evidence(exit_code=code)]).outcome, "FAIL")

    def test_no_evidence_infra_and_unsupported_remain_distinct(self):
        self.assertEqual(self.check([]).outcome, "PENDING")
        checked = self.check([evidence(status="INFRASTRUCTURE_FAILURE")])
        self.assertEqual(checked.outcome, "PENDING")
        self.assertEqual(checked.diagnostics[0].severity, "infrastructure")
        self.assertEqual(self.check([evidence(status="BLOCK", outcome="UNSUPPORTED")]).outcome, "UNSUPPORTED")

    def test_structural_predicate_never_accepts_semantic_claim(self):
        claim = {**CLAIM, "result_predicate": "bridge-structural/0.1"}
        e = evidence(result={"structural_acceptance": True, "semantic_acceptance": False})
        self.assertEqual(self.check([e], claim).outcome, "PASS")
        e.result["semantic_acceptance"] = True
        self.assertEqual(self.check([e], claim).outcome, "FAIL")
        claim["result_predicate"] = "bridge-semantic-edge/0.1"
        checked = self.check([e], claim)
        self.assertEqual(checked.outcome, "UNSUPPORTED")
        self.assertTrue(checked.authorized)  # provenance is not proof soundness

    def test_interpretation_predicate_requires_typed_complete_coverage(self):
        claim = {**CLAIM, "result_predicate": "interpretation-coverage/0.1"}
        for coverage in (None, {}, [], {"uncovered_segments": [1]}):
            self.assertEqual(self.check([evidence(result={"coverage": coverage})], claim).outcome, "FAIL")
        self.assertEqual(self.check([evidence(result={"coverage": {"uncovered_segments": []}})], claim).outcome, "PASS")


class PhaseBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.path = self.tmp.path / "run"
        result = build(self.path, "interpret")
        self.assertEqual(result["interpret"][0], 0, result)
        self.pkg = Package(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejected_prefreeze_candidate_retains_failure_root(self):
        self.pkg.set_meta("contract_candidate_root", OTHER)
        self.pkg.evidence.record(claim_id="FORMALIZED:O17@1", verifier_id="verislop.formal-statement-checker",
                                 status="BLOCK", scope=["rejected candidate"], input_root=OTHER,
                                 result={"milestone_outcome": "FAIL", "binding_root": "contract_candidate_root"},
                                 invocation=["verislop", "formalize"])
        life = view.derive(self.pkg)["obligations"]["O17"]["lifecycle"]
        self.assertEqual(life["FORMALIZED"]["outcome"], "FAIL")
        # A claim to success before the frozen inventory exists cannot pass.
        self.pkg.evidence.record(claim_id="FORMALIZED:O17@1", verifier_id="verislop.formal-statement-checker",
                                 status="PASS", scope=["candidate"], input_root=OTHER,
                                 result={"milestone_outcome": "PASS", "binding_root": "contract_candidate_root"},
                                 invocation=["verislop", "formalize"])
        self.assertNotEqual(view.derive(self.pkg)["obligations"]["O17"]["lifecycle"]["FORMALIZED"]["outcome"], "PASS")

    def test_formalization_request_gate_rejects_wrong_issuer(self):
        for path in (self.path / "evidence").glob("ev-*.json"):
            path.unlink()
        self.pkg.reset_evidence_cache()
        self.pkg.evidence.record(claim_id="INTERPRETATION:request", verifier_id="verislop.review-consensus",
                                 status="PASS", scope=["forged interpretation"], input_root=self.pkg.interpretation_root(),
                                 result={"milestone_outcome": "PASS", "coverage": {"uncovered_segments": []}},
                                 invocation=["test"])
        _draft, _ledger, diagnostics = formalize.require_interpretation(self.pkg)
        self.assertIn("STALE_OR_UNBOUND_EVIDENCE", {d.code for d in diagnostics})


class ClosureClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.base = cls.tmp.path / "base"
        cls.results = build(cls.base, "verify")
        if cls.results["verify"][0] != 0:
            raise AssertionError(cls.results["verify"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_finalization_claims_pass_without_self_dependency_and_derived_issuer_matches(self):
        report = canonical.load_file(self.base / "report.json")
        final = [p for p in report["provenance"] if p["claim_id"].startswith("CLOSURE:")]
        self.assertEqual(len(final), 4)
        self.assertTrue(all(p["outcome"] == "PASS" for p in final))
        claims = canonical.load_file(self.base / "claims.json")
        derived = {r["id"] for r in claims["obligations"] if r["origin"] == "derived"}
        self.assertTrue(derived)
        for c in claims["claims"]:
            if c["obligation"] in derived and c["milestone"] == "INTERPRETED":
                self.assertEqual(c["verifier"], "verislop.formal-statement-checker")
                self.assertEqual(report["obligations"][c["obligation"]]["outcomes"]["INTERPRETED"], "PASS")

    def test_required_null_obligation_claim_is_checked(self):
        path = copy_pkg(self.base, self.tmp.path / "internal")
        claims_path = path / "closure" / "implementation-claims.json"
        claims = canonical.load_file(claims_path)
        cid = "BRIDGE:unproved-premise"
        claims["claims"].append({"claim_id": cid, "obligation": None, "milestone": None, "required": True,
                                 "applicable": True, "verifier": "verislop.closure", "pass_predicate": "missing proof",
                                 "severity": "blocking", "reason": "required internal correspondence"})
        writable(claims_path)
        claims_path.write_bytes(canonical.dumps(claims))
        code, result = stage(path, "verify")
        self.assertEqual(code, 2, result)
        self.assertTrue(any(cid in d.get("claims", []) for d in result["diagnostics"]))
        report = canonical.load_file(path / "report.json")
        row = next(p for p in report["provenance"] if p["claim_id"] == cid)
        self.assertEqual(row["outcome"], "PENDING")
        final = next(p for p in report["provenance"] if p["claim_id"] == "CLOSURE:provenance")
        self.assertNotEqual(final["outcome"], "PASS")

    def test_bound_lifecycle_infrastructure_failure_is_not_reported_as_missing_verifier(self):
        path = copy_pkg(self.base, self.tmp.path / "bound-infrastructure")
        pkg = Package(path)
        cid = "PROVED:O17@1"
        pkg.evidence.record(claim_id=cid, verifier_id=ISSUER, status="INFRASTRUCTURE_FAILURE",
                            scope=["checker unavailable"], input_root=pkg.contract_input_root(),
                            result={"milestone_outcome": "PENDING", "binding_root": "contract_input_root"},
                            invocation=["verislop", "accept"])
        # Reuse the fixture's successful build observations: this test targets evidence
        # classification, while the same fixture already exercises actual clean builds.
        builds = canonical.load_file(self.base / "report.json")["builds"]
        with patch("verislop.closure.clean_build", side_effect=builds):
            code, result = stage(path, "verify")
        self.assertEqual(code, 3, result)
        relevant = [d for d in result["diagnostics"] if cid in d.get("claims", [])]
        self.assertTrue(any(d["code"] == "VERIFIER_FAILURE" and d["severity"] == "infrastructure" for d in relevant))
        self.assertFalse(any(d["code"] == "VERIFIER_NOT_RUN" for d in relevant))
        report = canonical.load_file(path / "report.json")
        self.assertEqual(report["terminal_status"], "INFRASTRUCTURE_FAILURE")
        self.assertEqual(report["obligations"]["O17"]["outcomes"]["PROVED"], "PENDING")

    def test_unknown_closure_claim_does_not_get_finalization_exemption(self):
        path = copy_pkg(self.base, self.tmp.path / "unknown-closure")
        claims_path = path / "closure" / "implementation-claims.json"
        claims = canonical.load_file(claims_path)
        c = dict(next(c for c in claims["claims"] if c["claim_id"] == "CLOSURE:provenance"))
        c["claim_id"] = "CLOSURE:invented"
        claims["claims"].append(c)
        writable(claims_path)
        claims_path.write_bytes(canonical.dumps(claims))
        code, result = stage(path, "verify")
        self.assertEqual(code, 2, result)
        self.assertIn("ORPHAN_CLAIM", codes(result))
        self.assertTrue(any(c["claim_id"] in d.get("claims", []) for d in result["diagnostics"]))
