"""Phase-bound review regressions using unrelated metadata and identity fixtures.

These tests do not import corpus tasks, graders, candidate answers or model outputs.
Mechanical receipts use the real evidence authorization and replay boundaries.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import TempDir, unanimous
from verislop import canonical, closure, contract, fsutil, generate, lifecycle, review, schemas, segment
from verislop import review_counterexamples as rc
from verislop.backends import registry, vscore_closure
from verislop.errors import BlockedError
from verislop.package import Package

ZERO = "sha256:" + "0" * 64


class BootstrapReviewScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(self.tmp.path / "scope-metadata")
        self.pkg.ensure("scope-metadata")
        prompt = b"Do A. Do B."
        fsutil.atomic_write(self.pkg.path("prompt"), prompt)
        fsutil.write_json(self.pkg.path("draft"), {})
        fsutil.write_json(self.pkg.path("interpretation"), {
            "request": {"document_hash": canonical.digest(prompt), "byte_length": len(prompt)},
            "clauses": [{"start_byte": a, "end_byte": b} for a, b in segment.segments(prompt)],
        })
        self.params = {"tier": 0, "target": "python", "endpoint": "test_campaign",
                       "require_state": "TESTED", "require_tests": True}
        self.pkg.set_meta("requested", dict(self.params))
        fsutil.write_json(self.pkg.path("request"), {"schema_version": "0.1", **self.params})
        self.current = {"claim_id": "IMPLEMENTED:O1@1", "obligation": "O1", "milestone": "IMPLEMENTED",
                        "required": True, "applicable": True, "verifier": "verislop.python-materializer"}
        self.tested = {"claim_id": "TESTED:O1@1", "obligation": "O1", "milestone": "TESTED",
                       "required": True, "applicable": True, "verifier": "verislop.python-tier0-campaign"}
        self.optional = {"claim_id": "END_TO_END_VERIFIED:O1@1", "obligation": "O1",
                         "milestone": "END_TO_END_VERIFIED", "required": False, "applicable": True,
                         "verifier": "verislop.closure"}
        self.finalization = [{"claim_id": cid, "obligation": None, "milestone": None,
                              "required": True, "applicable": True, "verifier": "verislop.closure",
                              "pass_predicate": predicate}
                             for cid, predicate in generate.CLOSURE_CLAIMS]
        self.claims = [self.current, self.tested, self.optional, *self.finalization]
        self.write_claims()
        # This identity source and empty metadata establish roots without any proof fixture.
        fsutil.atomic_write(self.pkg.path("implementation") / "identity.py", b"def identity(value): return value\n")
        fsutil.write_json(self.pkg.path("claims"), {"claims": []})
        fsutil.write_json(self.pkg.path("accepted_ir"), {})
        fsutil.write_json(self.pkg.path("accepted") / "acceptance.json", {})
        fsutil.write_json(self.pkg.path("bridges") / "bindings.json", {})
        fsutil.write_json(contract.challenge_dir(self.pkg) / "challenge.json", {})
        fsutil.write_json(self.pkg.path("tests") / "campaign.json", {})

    def write_claims(self):
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {
            "schema_version": "0.1", "artifact_kind": "implementation_claims",
            "parameters": self.params, "claims": self.claims,
        })

    def probe(self, cid):
        return {"kind": "mechanical_failure", "claim_id": cid}

    def evidence(self, claim, outcome, *, root=None):
        if root is None:
            root = (self.pkg.implementation_root() if claim["milestone"] == "IMPLEMENTED"
                    else closure.closure_input_root(self.pkg))
        self.assertIsNotNone(root)
        return self.pkg.evidence.record(
            claim_id=claim["claim_id"], verifier_id=claim["verifier"],
            status="PASS" if outcome == "PASS" else "BLOCK", scope=["synthetic metadata regression"],
            input_root=root, result={"milestone_outcome": outcome}, invocation=["scope-regression"],
        )

    def policy(self):
        # Binder guidance is irrelevant to mechanical scope; no accepted oracle is supplied.
        with patch.object(review, "_target_case_binders", return_value={"obligations": {}}):
            return review._counterexample_policy(self.pkg, "release", ["O1"])

    def ballot(self, cid, verdict="ACCEPT"):
        return {"verdict": verdict, "reviewed_obligations": ["O1"], "findings": [],
                "search": {"method": "one synthetic mechanical probe", "attempted_cases": 1,
                           "probes": [self.probe(cid)],
                           "conclusion": "INCOMPLETE" if verdict == "ABSTAIN" else "NO_COUNTEREXAMPLE_FOUND"},
                "limitations": ["bounded fixture"], "rationale": "synthetic scoped judgment"}

    def schema_document(self, claims, *, kind="implementation_claims"):
        document = {"schema_version": "0.1", "artifact_kind": kind, "parameters": self.params,
                    "bound_to": {"accepted_ir": ZERO}, "obligations": [], "claims": claims}
        self.assertEqual([], schemas.validate("claims", document))
        return document

    def vscore_inheritance_fixture(self):
        original = {"claim_id": "INTERPRETED:O1@1", "obligation": "O1", "milestone": "INTERPRETED",
                    "required": True, "applicable": True, "verifier": "verislop.interpretation-recorder",
                    "pass_predicate": "synthetic per-obligation interpretation predicate",
                    "severity": "blocking", "reason": "synthetic inherited metadata"}
        enriched = {**original, "revision": 1, "accepted_statement_hash": ZERO,
                    "root_kind": "interpretation_root", "result_predicate": "milestone-pass/0.1",
                    "premises": [], "scope": ["synthetic metadata"],
                    "trusted_dependencies": ["accepted-contract-policy"]}
        params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source", "backend": registry.VSCORE_ID,
                  "language": "vscore/0.1", "semantics": "vscore-semantics/0.1",
                  "require_state": "END_TO_END_VERIFIED", "require_tests": False,
                  "bridge_id": "synthetic", "tier_default_applied": False}
        document = {"schema_version": "0.2", "format": "verislop.implementation-claims/0.2",
                    "artifact_kind": "implementation_claims", "backend": registry.VSCORE_ID,
                    "bound_to": {"accepted_ir": ZERO, "certificate": ZERO, "contract_input_root": ZERO},
                    "parameters": params, "obligations": [], "claims": [enriched]}
        self.assertEqual([], schemas.validate("implementation-claims-v2", document))
        fsutil.write_json(self.pkg.path("claims"), self.schema_document([original], kind="contract_claims"))
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", document)
        self.pkg.set_meta("requested", params)
        return original, enriched, document

    def assert_duplicate_has_no_selected_winner(self, cid):
        fixture_view = {"obligations": {"O1": {"role": "guarantee", "kind": "postcondition",
            "statement": "synthetic identity requirement", "required": True, "formal": None,
            "lifecycle": {m: {"outcome": "PENDING"} for m in lifecycle.MILESTONES}}}}
        with patch("verislop.view.derive", return_value=fixture_view), \
             patch.object(review.C, "challenge_dir", return_value=self.tmp.path / "absent-challenge"), \
             patch.object(review, "_target_case_binders", return_value={"obligations": {}}):
            for name, operation in (
                ("review_context", lambda: rc.review_context(self.pkg, "release")),
                ("mechanical_claim_ids", lambda: rc.mechanical_claim_ids(self.pkg, "release")),
                ("build_packet", lambda: review.build_packet(self.pkg, "release")),
            ):
                with self.subTest(public_operation=name):
                    with self.assertRaises(BlockedError) as raised:
                        operation()
                    self.assertIn("ORPHAN_CLAIM", [d.code for d in raised.exception.diagnostics])
        receipt = rc.replay(self.pkg, "release", self.probe(cid))
        self.assertEqual("UNSUPPORTED", receipt["status"], receipt)
        self.assertIsNone(receipt["claim"])
        self.assertIsNone(receipt["observed"])

    def test_native_release_discloses_future_finalization_and_optional_end_to_end(self):
        context = rc.review_context(self.pkg, "release")
        self.assertEqual("native_pre_finalization", context["review_phase"])
        self.assertEqual(self.params, context["resolved_assurance"])
        self.assertEqual(self.params, context["requested_assurance"])
        self.assertNotIn("END_TO_END_VERIFIED", context["current_milestones"])
        self.assertIn("END_TO_END_VERIFIED", context["outside_checkpoint_milestones"])
        self.assertEqual("OUT_OF_SCOPE", context["claims"][self.optional["claim_id"]]["disposition"])
        ids = rc.mechanical_claim_ids(self.pkg, "release")
        self.assertIn(self.current["claim_id"], ids)
        self.assertIn(self.tested["claim_id"], ids)
        self.assertNotIn(self.optional["claim_id"], ids)
        for claim in self.finalization:
            row = context["claims"][claim["claim_id"]]
            self.assertEqual("FUTURE", row["disposition"])
            self.assertTrue(row["required"])
            self.assertEqual("verify", row["producer_stage"])
            self.assertNotIn(claim["claim_id"], ids)
        self.assertEqual(set(ids), set(context["current_required_claim_ids"]))

    def test_future_claim_probe_cannot_replay_even_with_an_earlier_authorized_failure(self):
        before = rc.review_context(self.pkg, "release")
        claim = next(c for c in self.finalization if c["claim_id"] == "CLOSURE:endpoint")
        self.evidence(claim, "UNSUPPORTED")
        self.pkg.set_meta("completed_stages", ["verify"])
        self.pkg.set_meta("stage_history", [{"stage": "verify", "status": "BLOCKED"}])
        self.assertEqual(before, rc.review_context(self.pkg, "release"))
        receipt = rc.replay(self.pkg, "release", self.probe(claim["claim_id"]))
        self.assertEqual("UNSUPPORTED", receipt["status"], receipt)
        self.assertIsNone(receipt["claim"])

    def test_future_probe_is_a_protocol_error_and_a_current_probe_remains_valid(self):
        policy = self.policy()
        ballot, error = review.parse_ballot(self.ballot("CLOSURE:endpoint"), ["O1"], policy)
        self.assertIsNone(ballot)
        self.assertIn("outside", error)
        corrected, error = review.parse_ballot(self.ballot(self.current["claim_id"]), ["O1"], policy)
        self.assertIsNone(error)
        self.assertEqual("ACCEPT", corrected["reported_verdict"])

    def test_missing_and_stale_current_evidence_remain_unresolved_and_eligible(self):
        cid = self.current["claim_id"]
        self.assertIn(cid, rc.mechanical_claim_ids(self.pkg, "release"))
        missing = rc.replay(self.pkg, "release", self.probe(cid))
        self.assertEqual("UNSUPPORTED", missing["status"], missing)
        self.assertEqual("PENDING", missing["observed"]["outcome"])
        self.evidence(self.current, "PASS", root=ZERO)
        stale = rc.replay(self.pkg, "release", self.probe(cid))
        self.assertEqual("UNSUPPORTED", stale["status"], stale)
        self.assertEqual("STALE", stale["observed"]["outcome"])
        self.assertEqual("CURRENT", rc.review_context(self.pkg, "release")["claims"][cid]["disposition"])

    def test_current_authorized_failure_overrides_a_reported_acceptance(self):
        self.evidence(self.current, "FAIL")
        receipt = rc.replay(self.pkg, "release", self.probe(self.current["claim_id"]))
        self.assertEqual("CONFIRMED", receipt["status"], receipt)
        ballot, error = review.parse_ballot(self.ballot(self.current["claim_id"]), ["O1"], self.policy())
        self.assertIsNone(error)
        review._apply_replay_results(ballot, [receipt], ["O1"])
        self.assertEqual("ACCEPT", ballot["reported_verdict"])
        self.assertEqual("REJECT", ballot["verdict"])
        self.assertTrue(ballot["blocking"])

    def test_valid_current_abstention_is_preserved_after_successful_probe_replay(self):
        self.evidence(self.current, "PASS")
        receipt = rc.replay(self.pkg, "release", self.probe(self.current["claim_id"]))
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt)
        ballot, error = review.parse_ballot(self.ballot(self.current["claim_id"], "ABSTAIN"), ["O1"], self.policy())
        self.assertIsNone(error)
        review._apply_replay_results(ballot, [receipt], ["O1"])
        self.assertEqual("ABSTAIN", ballot["reported_verdict"])
        self.assertEqual("ABSTAIN", ballot["verdict"])
        ballot["unresolved_blocking_findings"] = []
        tally = review.tally_tier(unanimous("R0", "critic", 1), ["R0/critic#1"], {"R0/critic#1": ballot}, [])
        self.assertEqual("INCOMPLETE", tally["result"])
        self.assertEqual(0, tally["accepts"])

    def test_stored_receipt_recheck_survives_finalization_growth_but_not_a_current_failure(self):
        self.evidence(self.current, "PASS")
        cid = self.current["claim_id"]
        receipt = rc.replay(self.pkg, "release", self.probe(cid))
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt)
        self.assertEqual([], schemas.validate("review-counterexample-receipt", receipt))
        raw = self.ballot(cid)
        policy = self.policy()
        ballot, error = review.parse_ballot(raw, ["O1"], policy)
        self.assertIsNone(error)
        review._apply_replay_results(ballot, [receipt], ["O1"])
        campaign = "rc-synthetic-stability"
        raw_ref = f"reviews/{campaign}/raw.txt"
        receipt_ref = f"reviews/{campaign}/counterexamples/one.json"
        fsutil.atomic_write(self.pkg.root / raw_ref, json.dumps(raw).encode())
        fsutil.write_json(self.pkg.root / receipt_ref, receipt)
        record = {"campaign_id": campaign, "checkpoint": "release", "slot_id": "R0/critic#1",
                  "transcript_ref": raw_ref, "reported_verdict": ballot["reported_verdict"],
                  "search": ballot["search"], "counterexample_receipts": [{
                      "receipt_ref": receipt_ref, "receipt_hash": canonical.digest_file(self.pkg.root / receipt_ref),
                      "probe_hash": receipt["proposal_hash"], "status": receipt["status"]}],
                  "verdict": ballot["verdict"], "reviewed_obligations": ballot["reviewed_obligations"],
                  "finding_refs": [], "unresolved_blocking_findings": [],
                  "limitations": ballot["limitations"], "rationale": ballot["rationale"]}
        packet = {"scope": ["O1"], "counterexample_policy": policy}
        self.assertEqual([], review._recheck_counterexamples(self.pkg, record, packet))
        for claim in self.finalization:
            self.evidence(claim, "PASS")
        self.evidence(self.current, "PASS")
        self.assertEqual([], review._recheck_counterexamples(self.pkg, record, packet))
        self.evidence(self.current, "FAIL")
        problems = review._recheck_counterexamples(self.pkg, record, packet)
        self.assertTrue(any("no longer reproduces" in problem for problem in problems), problems)

    def test_unknown_internal_claims_are_not_exempted_from_current_failure_replay(self):
        for cid in ("CLOSURE:unexpected", "INTERNAL:metadata"):
            with self.subTest(claim=cid):
                internal = {"claim_id": cid, "obligation": None, "milestone": None,
                            "required": True, "applicable": True, "verifier": "verislop.closure"}
                self.claims.append(internal)
                self.write_claims()
                self.assertEqual("CURRENT", rc.review_context(self.pkg, "release")["claims"][cid]["disposition"])
                self.assertIn(cid, rc.mechanical_claim_ids(self.pkg, "release"))
                self.evidence(internal, "FAIL")
                self.assertEqual("CONFIRMED", rc.replay(self.pkg, "release", self.probe(cid))["status"])

    def test_malformed_known_finalization_ids_cannot_acquire_the_future_exemption(self):
        base = copy.deepcopy(self.finalization[0])
        for change in ({"verifier": "verislop.python-materializer"}, {"obligation": "O1"},
                       {"milestone": "TESTED"}, {"pass_predicate": "unregistered predicate"}):
            with self.subTest(change=change):
                malformed = {**base, **change}
                self.claims = [c for c in self.claims if c["claim_id"] != base["claim_id"]] + [malformed]
                self.write_claims()
                self.assertEqual("CURRENT", rc.review_context(self.pkg, "release")["claims"][base["claim_id"]]["disposition"])
                self.assertIn(base["claim_id"], rc.mechanical_claim_ids(self.pkg, "release"))
        for missing in ("obligation", "milestone", "pass_predicate"):
            with self.subTest(missing_field=missing):
                malformed = {k: value for k, value in base.items() if k != missing}
                self.claims = [c for c in self.claims if c["claim_id"] != base["claim_id"]] + [malformed]
                self.write_claims()
                self.assertEqual("CURRENT", rc.review_context(self.pkg, "release")["claims"][base["claim_id"]]["disposition"])
                self.assertIn(base["claim_id"], rc.mechanical_claim_ids(self.pkg, "release"))

    def test_unknown_backend_policy_cannot_exempt_finalization_claims(self):
        baseline = canonical.load_file(self.pkg.path("closure") / "implementation-claims.json")
        for mutation in ({"schema_version": "unknown"},
                         {"parameters": {**self.params, "endpoint": "unregistered_endpoint"}},
                         {"parameters": {**self.params, "target": "unregistered_target"}}):
            with self.subTest(mutation=mutation):
                fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {**baseline, **mutation})
                context = rc.review_context(self.pkg, "release")
                self.assertEqual("unresolved_release", context["review_phase"])
                ids = rc.mechanical_claim_ids(self.pkg, "release")
                for claim in self.finalization:
                    self.assertEqual("CURRENT", context["claims"][claim["claim_id"]]["disposition"])
                    self.assertIn(claim["claim_id"], ids)

    def test_schema_valid_optional_duplicate_cannot_conceal_required_failure_in_either_order(self):
        required = {**self.current, "pass_predicate": "synthetic materialization predicate",
                    "severity": "blocking", "reason": "synthetic required current claim"}
        optional = {**required, "required": False, "severity": "advisory"}
        path = self.pkg.path("closure") / "implementation-claims.json"
        fsutil.write_json(path, self.schema_document([required]))
        self.evidence(required, "FAIL")
        cid = required["claim_id"]
        self.assertEqual("CONFIRMED", rc.replay(self.pkg, "release", self.probe(cid))["status"])
        for order in ([required, optional], [optional, required]):
            with self.subTest(required_first=order[0]["required"]):
                fsutil.write_json(path, self.schema_document(order))
                self.assert_duplicate_has_no_selected_winner(cid)

    def test_schema_valid_duplicates_across_inventories_cannot_select_an_optional_winner(self):
        required = {**self.current, "pass_predicate": "synthetic materialization predicate",
                    "severity": "blocking", "reason": "synthetic duplicate current claim"}
        optional = {**required, "required": False, "severity": "advisory"}
        for contract_claim, implementation_claim in ((required, optional), (optional, required)):
            with self.subTest(contract_claim_required=contract_claim["required"]):
                fsutil.write_json(self.pkg.path("claims"), self.schema_document([contract_claim], kind="contract_claims"))
                fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json",
                                  self.schema_document([implementation_claim]))
                self.assert_duplicate_has_no_selected_winner(required["claim_id"])

    def test_schema_valid_inventory_cannot_collide_with_the_synthetic_request_claim(self):
        cid = "INTERPRETATION:request"
        row = {"claim_id": cid, "obligation": None, "milestone": "INTERPRETED", "required": True,
               "applicable": True, "verifier": "verislop.interpretation-recorder",
               "pass_predicate": "synthetic request coverage predicate", "severity": "blocking",
               "reason": "synthetic collision with supervisor-owned request identifier"}
        for inventory in ("contract", "implementation"):
            with self.subTest(inventory=inventory):
                fsutil.write_json(self.pkg.path("claims"), self.schema_document(
                    [row] if inventory == "contract" else [], kind="contract_claims"))
                fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", self.schema_document(
                    [row] if inventory == "implementation" else []))
                self.assert_duplicate_has_no_selected_winner(cid)

    def test_ambiguous_inventory_cannot_confirm_an_independent_missing_requirement_probe(self):
        required = {**self.current, "pass_predicate": "synthetic materialization predicate",
                    "severity": "blocking", "reason": "synthetic duplicate"}
        optional = {**required, "required": False, "severity": "advisory"}
        fsutil.write_json(self.pkg.path("claims"), self.schema_document([required, optional], kind="contract_claims"))
        prompt = self.pkg.path("prompt").read_bytes()
        spans = segment.segments(prompt)
        ledger = canonical.load_file(self.pkg.path("interpretation"))
        ledger["clauses"] = [{"start_byte": spans[0][0], "end_byte": spans[0][1]}]
        fsutil.write_json(self.pkg.path("interpretation"), ledger)
        a, b = spans[1]
        proposal = {"kind": "missing_requirement", "start_byte": a, "end_byte": b, "quoted": prompt[a:b].decode()}
        self.assertEqual([], rc.validate_proposal(proposal))
        receipt = rc.replay(self.pkg, "formal_contract", proposal)
        self.assertEqual("UNSUPPORTED", receipt["status"], receipt)
        self.assertIsNone(receipt["claim"])
        self.assertIsNone(receipt["observed"])

    def test_registered_vscore_inheritance_preserves_original_fields_and_uses_enriched_replay_record(self):
        original, enriched, _ = self.vscore_inheritance_fixture()
        context = rc.review_context(self.pkg, "release")
        cid = original["claim_id"]
        self.assertEqual("CURRENT", context["claims"][cid]["disposition"])
        self.assertEqual(1, rc.mechanical_claim_ids(self.pkg, "release").count(cid))
        root = self.pkg.interpretation_root()
        self.pkg.evidence.record(claim_id=cid, verifier_id=original["verifier"], status="PASS",
                                 scope=["synthetic inheritance regression"], input_root=root,
                                 result={"milestone_outcome": "PASS"}, invocation=["inheritance-regression"])
        roots = {"interpretation_root": root, "contract_input_root": None,
                 "implementation_root": None, "link_root": None, "test_root": None}
        # Isolation is limited to roots for absent VSCore execution artifacts; the
        # actual metadata reader, inherited definition and evidence checker run.
        with patch.object(self.pkg, "roots", return_value=roots), \
             patch.object(rc, "bound_roots", return_value=roots), \
             patch.object(closure, "closure_input_root", return_value=ZERO):
            receipt = rc.replay(self.pkg, "release", self.probe(cid))
        self.assertEqual("NOT_REPRODUCED", receipt["status"], receipt)
        self.assertEqual(enriched["revision"], receipt["claim"]["revision"])
        self.assertEqual(enriched["accepted_statement_hash"], receipt["claim"]["accepted_statement_hash"])

    def test_vscore_inheritance_rejects_changed_original_fields_and_repeated_enriched_rows(self):
        original, enriched, document = self.vscore_inheritance_fixture()
        roots = {"interpretation_root": self.pkg.interpretation_root(), "contract_input_root": None,
                 "implementation_root": None, "link_root": None, "test_root": None}
        mutations = (
            ([{**enriched, "required": False}], True),
            ([{**enriched, "verifier": "verislop.python-materializer"}], True),
            ([{**enriched, "required": 1}], False),
            ([enriched, copy.deepcopy(enriched)], True),
        )
        for rows, schema_valid in mutations:
            with self.subTest(rows=rows):
                mutated = {**document, "claims": rows}
                self.assertEqual(schema_valid, not bool(schemas.validate("implementation-claims-v2", mutated)))
                fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", mutated)
                with patch.object(self.pkg, "roots", return_value=roots), \
                     patch.object(rc, "bound_roots", return_value=roots), \
                     patch.object(closure, "closure_input_root", return_value=ZERO):
                    self.assert_duplicate_has_no_selected_winner(original["claim_id"])

    def test_explicit_unsupported_end_to_end_request_remains_current(self):
        self.params["require_state"] = "END_TO_END_VERIFIED"
        self.pkg.set_meta("requested", dict(self.params))
        self.optional["required"] = True
        self.write_claims()
        context = rc.review_context(self.pkg, "release")
        cid = self.optional["claim_id"]
        self.assertIn("END_TO_END_VERIFIED", context["current_milestones"])
        self.assertEqual("CURRENT", context["claims"][cid]["disposition"])
        self.assertIn(cid, rc.mechanical_claim_ids(self.pkg, "release"))
        self.assertEqual("UNSUPPORTED", rc.replay(self.pkg, "release", self.probe(cid))["status"])
        self.evidence(self.optional, "UNSUPPORTED")
        self.assertEqual("CONFIRMED", rc.replay(self.pkg, "release", self.probe(cid))["status"])

    def test_requested_prerequisites_remain_visible_without_their_artifacts(self):
        self.pkg.path("closure").joinpath("implementation-claims.json").unlink()
        requested = {**self.params, "require_state": "END_TO_END_VERIFIED"}
        self.pkg.set_meta("requested", requested)
        context = rc.review_context(self.pkg, "release")
        self.assertEqual(requested, context["requested_assurance"])
        self.assertIn("END_TO_END_VERIFIED", context["current_milestones"])
        self.pkg.set_meta("requested", {})
        unknown = rc.review_context(self.pkg, "release")
        self.assertEqual(list(lifecycle.MILESTONES), unknown["current_milestones"])
        self.assertIsNone(unknown["resolved_assurance"].get("tier"))
        self.assertIsNone(unknown["resolved_assurance"].get("require_state"))

    def test_stronger_requested_assurance_is_visible_beside_frozen_policy(self):
        requested = {**self.params, "require_state": "END_TO_END_VERIFIED"}
        self.pkg.set_meta("requested", requested)
        context = rc.review_context(self.pkg, "release")
        self.assertEqual("END_TO_END_VERIFIED", context["requested_assurance"]["require_state"])
        self.assertEqual("TESTED", context["resolved_assurance"]["require_state"])
        self.assertIn("END_TO_END_VERIFIED", context["current_milestones"])

    def test_packet_and_trusted_guidance_share_context_without_rewriting_outcomes(self):
        outcomes = {m: {"outcome": "PENDING" if m == "END_TO_END_VERIFIED" else "PASS"}
                    for m in lifecycle.MILESTONES}
        fixture_view = {"obligations": {"O1": {"role": "guarantee", "kind": "postcondition",
            "statement": "synthetic identity requirement", "required": True, "formal": None, "lifecycle": outcomes}}}
        with patch("verislop.view.derive", return_value=fixture_view), \
             patch.object(review.C, "challenge_dir", return_value=self.tmp.path / "absent-challenge"), \
             patch.object(review, "_target_case_binders", return_value={"obligations": {}}):
            packet = review.build_packet(self.pkg, "release")
        policy = packet["counterexample_policy"]
        context = rc.review_context(self.pkg, "release")
        self.assertEqual(context, packet["review_context"])
        self.assertEqual(context, policy["review_context"])
        text = review._checkpoint_guidance("release", policy)
        guidance = json.JSONDecoder().raw_decode(text.split("CURRENT CHECKPOINT RULES (supervisor-selected):", 1)[1].lstrip())[0]
        self.assertEqual(context, guidance["review_context"])
        self.assertEqual(context["current_milestones"], guidance["current_milestones"])
        self.assertEqual(context["outside_checkpoint_milestones"], guidance["outside_checkpoint_milestones"])
        self.assertEqual("PENDING", packet["obligations"]["O1"]["outcomes"]["END_TO_END_VERIFIED"])
        self.assertEqual("PASS", packet["obligations"]["O1"]["outcomes"]["TESTED"])

    def test_vscore_release_retains_current_closure_claims_and_pending_veto(self):
        params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                  "backend": registry.VSCORE_ID, "require_state": "END_TO_END_VERIFIED", "require_tests": False}
        e2e = {**self.optional, "required": True}
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {
            "schema_version": "0.2", "format": "verislop.implementation-claims/0.2",
            "parameters": params, "claims": [e2e, *self.finalization],
        })
        context = rc.review_context(self.pkg, "release")
        self.assertEqual("vscore_post_mechanical", context["review_phase"])
        ids = rc.mechanical_claim_ids(self.pkg, "release")
        for claim in [e2e, *self.finalization]:
            self.assertEqual("CURRENT", context["claims"][claim["claim_id"]]["disposition"])
            self.assertIn(claim["claim_id"], ids)
        snapshot = {"mechanical_status": "BLOCKED", "claims": [
            {"claim_id": "CLOSURE:provenance", "required": True, "outcome": "PENDING"}]}
        with patch.object(vscore_closure, "mechanical_snapshot", return_value=snapshot):
            veto = review._mechanical_veto(self.pkg, "release")
        self.assertIn("CLOSURE:provenance", veto)
        ballot = {"verdict": "ACCEPT", "unresolved_blocking_findings": []}
        tally = review.tally_tier(unanimous("R0", "critic", 1), ["R0/critic#1"], {"R0/critic#1": ballot}, veto)
        self.assertEqual("CHANGES_REQUESTED", tally["result"])


if __name__ == "__main__":
    unittest.main()
