"""Strict recovery retains failures and rechecks the same interpretation in a fresh package.

Controller tests use explicit fixture proposals rather than claiming real model performance.
The interpreter checks and evidence/lineage hashes are real in every package fixture.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, fsutil, interpret, recovery, run
from verislop.errors import Diagnostic, InfrastructureError, UsageError
from verislop.events import EventSink
from verislop.package import Package
from verislop.stage import StageResult

REPO = Path(__file__).resolve().parents[1]
EX = REPO / "examples"


class StrictRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-recovery-test-")
        self.root = Path(self.tmp.name)
        self.pkg = Package(self.root / "original")
        self.pkg.ensure("original")
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True)
        result = interpret.run(self.pkg, self.events, EX / "request.txt", mode="software",
                               request_ref="examples/request.txt", candidate=EX / "draft.json",
                               ledger_path=EX / "interpretation.json", interactive=False)
        self.assertEqual("PASS", result.status)
        self.params = {"config": str(EX / "ollama-review-config.json"), "repair_rounds": 2,
                       "formalization_candidate": None, "proof_candidate": None,
                       "draft_candidate": str(EX / "draft.json"), "ledger_candidate": str(EX / "interpretation.json"),
                       "prompt_file": str(EX / "request.txt"), "request_ref": "examples/request.txt", "mode": "software",
                       "tier": 0, "target": "python", "policy": "strict", "endpoint": "test_campaign",
                       "require_state": "TESTED", "attachments": [], "resolve": [], "non_interactive": True}
        self.pkg.set_meta("run_parameters", self.params)
        self.pkg.set_meta("requested", {"tier": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"})
        source = b"namespace Candidate\ntheorem broken : True := by sorry\nend Candidate\n"
        fsutil.atomic_write(self.pkg.path("contract") / "candidate/proposal.lean", source)
        fsutil.write_json(self.pkg.path("contract") / "candidate/formalization.json", {"bindings": []})

    def tearDown(self):
        self.events.close()
        self.tmp.cleanup()

    @staticmethod
    def failure(stage="formalize", code="CANDIDATE_BUILD_FAILURE"):
        d = Diagnostic(code, "Contract.lean:4: unknown identifier badName")
        return StageResult("run", "BLOCKED", "strict pipeline did not complete", diagnostics=[d],
                           summary={"stopped_at": stage, "failed_stage_diagnostics": [d.to_json()],
                                    "failed_stage_summary": {"errors": ["unsolved goal: n + 1 = n"]}})

    def create(self):
        return recovery.create(self.pkg, self.pkg, self.params, self.failure(), 1, self.events)

    def seal(self):
        child, params, record = self.create()
        recovery.write_journal(self.pkg, child, [record], 2)
        return child, params, record

    def test_budget_is_explicit_bounded_and_zero_disables(self):
        self.assertEqual(2, recovery.budget(self.params))
        self.assertEqual(0, recovery.budget({**self.params, "repair_rounds": 0}))
        self.assertEqual(3, recovery.budget({**self.params, "repair_rounds": None}))
        self.assertEqual(0, recovery.budget({**self.params, "config": None}))
        for n in (-1, 9, True, "2"):
            with self.subTest(value=n), self.assertRaises(UsageError):
                recovery.budget({**self.params, "repair_rounds": n})

    def test_only_agent_contract_proof_defects_restart(self):
        for stage in ("formalize", "prove", "accept"):
            self.assertTrue(recovery.eligible(self.failure(stage), self.params))
        for stage in ("interpret", "generate", "test", "verify", "review:formal_contract"):
            self.assertFalse(recovery.eligible(self.failure(stage), self.params))
        for code in recovery.NEVER_REPAIR_CODES:
            self.assertFalse(recovery.eligible(self.failure(code=code), self.params), code)
        for name in ("formalization_candidate", "proof_candidate"):
            self.assertFalse(recovery.eligible(self.failure(), {**self.params, name: "/explicit/fixture"}))
        self.assertFalse(recovery.eligible(self.failure(), {**self.params, "config": None}))
        result = self.failure()
        result.diagnostics.append(Diagnostic("PROVIDER_FAILURE", "offline", severity="infrastructure"))
        self.assertFalse(recovery.eligible(result, self.params))

    def test_advisory_profile_notes_do_not_veto_repair_of_an_actual_contract_failure(self):
        result = self.failure(stage="prove", code="PROOF_UNRESOLVED")
        result.diagnostics.append(Diagnostic("UNSUPPORTED_SEMANTICS", "auxiliary declaration is opaque", severity="warning"))
        self.assertTrue(recovery.eligible(result, self.params))
        result.diagnostics.append(Diagnostic("UNSUPPORTED_SEMANTICS", "required contract representation unavailable"))
        self.assertFalse(recovery.eligible(result, self.params))

    def test_resume_journal_cannot_raise_the_frozen_round_bound_above_eight(self):
        self.seal()
        path = self.pkg.root / "recovery.json"
        value = canonical.load_file(path)
        value["max_repair_rounds"] = 99
        fsutil.write_json(path, value)
        with self.assertRaises(UsageError):
            recovery.resolve_active(self.pkg)

    def test_mutating_only_journal_cannot_raise_a_selected_bound_from_two_to_three(self):
        child, params, _ = self.seal()
        path = self.pkg.root / "recovery.json"
        value = canonical.load_file(path)
        value["max_repair_rounds"] = 3
        fsutil.write_json(path, value)
        with patch.object(run, "_execute_once", return_value=self.failure()) as attempt, self.assertRaises(UsageError) as caught:
            run._execute(self.pkg, self.events, params, {"interpret"})
        attempt.assert_not_called()
        self.assertEqual("INPUT_MUTATION", caught.exception.diagnostics[0].code)
        self.assertFalse((self.root / "original-repair-02").exists())

    def test_explicit_resume_override_is_frozen_and_does_not_reset_spent_rounds(self):
        child, params, _ = self.seal()
        calls = []
        def failure(pkg, events, parameters, start_after):
            calls.append(pkg.root)
            return self.failure()
        with patch.object(run, "_execute_once", side_effect=failure):
            result = run._execute(self.pkg, self.events, {**params, "repair_rounds": 3, "_repair_rounds_override": 3}, {"interpret"})
        self.assertEqual(3, len(calls))  # existing child, round 2, round 3
        self.assertEqual(3, result.summary["recovery"]["consumed_rounds"])
        active, rounds, maximum = recovery.resolve_active(self.pkg)
        self.assertEqual(3, maximum)
        self.assertEqual(3, len(rounds))
        policy = canonical.load_file(self.pkg.root / "recovery-policy/decision-0002.json")
        self.assertEqual("explicit --repair-rounds override", policy["source"])
        self.assertEqual(3, policy["max_repair_rounds"])
        self.assertIsNotNone(policy["previous"])
        # A later resume without the CLI override uses the recorded selection,
        # even if an older parameter bundle still contains the old explicit flag.
        with patch.object(run, "_execute_once", return_value=self.failure()) as attempt:
            resumed = run._execute(self.pkg, self.events, params, {"interpret"})
        self.assertEqual(1, attempt.call_count)
        self.assertEqual(3, resumed.summary["recovery"]["max_rounds"])
        self.assertEqual(3, resumed.summary["recovery"]["consumed_rounds"])

    def test_interrupted_override_is_published_before_stage_dispatch_and_can_be_superseded(self):
        child, params, _ = self.seal()
        def interrupt(pkg, events, parameters, start_after):
            journal = canonical.load_file(self.pkg.root / "recovery.json")
            self.assertEqual(3, journal["max_repair_rounds"])
            self.assertEqual("recovery-policy/decision-0002.json", journal["budget_policy"]["ref"])
            self.assertEqual(1, len(journal["rounds"]))
            raise KeyboardInterrupt()
        with patch.object(run, "_execute_once", side_effect=interrupt) as attempt, self.assertRaises(KeyboardInterrupt):
            run._execute(self.pkg, self.events, {**params, "repair_rounds": 3, "_repair_rounds_override": 3}, {"interpret"})
        self.assertEqual(1, attempt.call_count)
        active, rounds, maximum = recovery.resolve_active(self.pkg)
        self.assertEqual(child.root, active.root)
        self.assertEqual(1, len(rounds))
        self.assertEqual(3, maximum)
        passed = StageResult("run", "PASS", "controller fixture; no new repair needed")
        with patch.object(run, "_execute_once", return_value=passed) as attempt:
            result = run._execute(self.pkg, self.events, {**params, "repair_rounds": 4, "_repair_rounds_override": 4}, {"interpret"})
        self.assertEqual(1, attempt.call_count)
        self.assertEqual(4, result.summary["recovery"]["max_rounds"])
        self.assertEqual(1, result.summary["recovery"]["consumed_rounds"])
        active, rounds, maximum = recovery.resolve_active(self.pkg)
        self.assertEqual(4, maximum)
        self.assertEqual(1, len(rounds))
        latest = canonical.load_file(self.pkg.root / "recovery-policy/decision-0003.json")
        self.assertEqual(4, latest["max_repair_rounds"])
        self.assertEqual("recovery-policy/decision-0002.json", latest["previous"]["ref"])

    def test_exact_request_interpretation_and_prior_proposal_are_preserved(self):
        paths = [self.pkg.path("prompt"), self.pkg.path("request"), self.pkg.path("draft"),
                 self.pkg.path("interpretation"), self.pkg.path("contract") / "candidate/proposal.lean"]
        before = {p: p.read_bytes() for p in paths}
        child, params, record = self.create()
        self.assertEqual(before, {p: p.read_bytes() for p in paths})
        for name in ("prompt", "request", "draft", "interpretation"):
            self.assertEqual(self.pkg.path(name).read_bytes(), child.path(name).read_bytes())
        self.assertEqual(self.pkg.interpretation_root(), child.interpretation_root())
        self.assertEqual(before[paths[-1]].decode(), params["recovery_context"]["previous_candidate"]["lean_source"])
        self.assertTrue(any("badName" in f for f in params["recovery_context"]["feedback"]))
        self.assertTrue(any("n + 1 = n" in f for f in params["recovery_context"]["feedback"]))
        self.assertEqual(1, record["round"])

    def test_repair_does_not_inherit_proof_accepted_implementation_or_release_evidence(self):
        poisoned = ["contract/proofs/candidate.lean", "accepted/accepted-ir.json", "implementation/old.py",
                    "bridges/bindings.json", "tests/results.json", "reviews/release/old.json", "closure/builds/old.json"]
        for rel in poisoned:
            fsutil.atomic_write(self.pkg.root / rel, b"obsolete artifact\n")
        self.pkg.evidence.record(claim_id="PROVED:O1@1", verifier_id="verislop.lean-acceptance", status="PASS",
                                 scope=["old rejected candidate"], input_root=canonical.digest(b"old"),
                                 result={"milestone_outcome": "PASS"}, invocation=["fixture"])
        child, _, _ = self.create()
        for rel in poisoned:
            self.assertFalse((child.root / rel).exists(), rel)
        self.assertTrue(child.evidence.load())
        self.assertTrue(all(e.record["verifier_id"] == "verislop.interpretation-recorder" for e in child.evidence.load()))
        self.assertEqual([], child.evidence.for_claim("PROVED:O1@1"))
        self.assertEqual(["interpret"], child.meta()["completed_stages"])

    def test_existing_repair_package_is_never_overwritten(self):
        child, _, _ = self.create()
        manifest = fsutil.manifest_tree(child.root)
        with self.assertRaises(UsageError):
            self.create()
        self.assertEqual(manifest, fsutil.manifest_tree(child.root))

    def test_recorded_routing_resolution_is_preserved_without_reinterpreting_the_request(self):
        from verislop import agents

        prompt = b"Make it better."
        proposed = agents.extract_json(agents.INTERPRETER_SYSTEM[agents.INTERPRETER_SYSTEM.index('{"obligations"'):])
        proposed["obligations"][0]["sources"][0]["quote"] = prompt.decode()
        proposed["clauses"][0]["quote"] = prompt.decode()
        d, ledger, issues = agents.assemble_interpretation(proposed, prompt, "uncertain.txt")
        self.assertEqual([], issues)
        source = self.root / "uncertain.txt"
        source.write_bytes(prompt)
        draft_path, ledger_path = self.root / "routing-draft.json", self.root / "routing-ledger.json"
        fsutil.write_json(draft_path, d, pretty=True)
        fsutil.write_json(ledger_path, ledger, pretty=True)
        parent = Package(self.root / "routing-root")
        parent.ensure("routing-root")
        events = EventSink(parent.run_id, parent.root, quiet=True)
        try:
            result = interpret.run(parent, events, source, mode="auto", request_ref="uncertain.txt",
                                   candidate=draft_path, ledger_path=ledger_path, resolutions={"routing": "software"})
            self.assertEqual("PASS", result.status)
            before = parent.path("routing").read_bytes()
            child, _, _ = recovery.create(parent, parent, {**self.params, "mode": "auto", "request_ref": "uncertain.txt"},
                                          self.failure(), 1, events)
        finally:
            events.close()
        self.assertEqual(before, child.path("routing").read_bytes())
        self.assertEqual(parent.interpretation_root(), child.interpretation_root())
        self.assertEqual("software", canonical.load_file(child.path("routing"))["resolution"]["selected"])

    def test_resume_read_only_validates_lineage_and_finds_active_child(self):
        child, _, record = self.seal()
        before = fsutil.manifest_tree(self.pkg.root)
        active, rounds, maximum = recovery.resolve_active(self.pkg)
        self.assertEqual(child.root, active.root)
        self.assertEqual([record], rounds)
        self.assertEqual(2, maximum)
        self.assertEqual(before, fsutil.manifest_tree(self.pkg.root))

    def test_parent_artifact_tamper_blocks_resume(self):
        self.seal()
        fsutil.atomic_write(self.pkg.path("contract") / "candidate/proposal.lean", b"changed parent\n")
        with self.assertRaises(UsageError) as caught:
            recovery.resolve_active(self.pkg)
        self.assertEqual("INPUT_MUTATION", caught.exception.diagnostics[0].code)

    def test_child_input_or_context_tamper_blocks_resume(self):
        for rel in ("draft.json", "recovery-context.json", "recovery-lineage.json"):
            with self.subTest(path=rel):
                child, _, _ = self.seal()
                fsutil.atomic_write(child.root / rel, b"{}")
                with self.assertRaises(UsageError) as caught:
                    recovery.resolve_active(self.pkg)
                self.assertEqual("INPUT_MUTATION", caught.exception.diagnostics[0].code)
                fsutil.remove_tree(child.root)
                (self.pkg.root / "recovery.json").unlink()

    def test_missing_lineage_or_malformed_journal_is_a_blocked_binding(self):
        child, _, _ = self.seal()
        (child.root / "recovery-lineage.json").unlink()
        with self.assertRaises(UsageError) as caught:
            recovery.resolve_active(self.pkg)
        self.assertEqual("INPUT_MUTATION", caught.exception.diagnostics[0].code)
        fsutil.atomic_write(self.pkg.root / "recovery.json", b"[]")
        with self.assertRaises(UsageError):
            recovery.resolve_active(self.pkg)

    def test_controller_recovers_then_preserves_only_final_success_diagnostics(self):
        calls = []
        def attempt(pkg, events, parameters, start_after):
            calls.append((pkg.root, parameters, start_after))
            if len(calls) == 1:
                fsutil.write_json(pkg.path("report"), {"terminal_status": "BLOCKED"})
                return self.failure()
            self.assertEqual({"interpret"}, start_after)
            self.assertEqual(self.pkg.interpretation_root(), pkg.interpretation_root())
            self.assertFalse(pkg.path("accepted_ir").exists())
            fsutil.write_json(pkg.path("report"), {"terminal_status": "VERIFIED"})
            return StageResult("run", "PASS", "fixture strict gates completed", summary={"package": str(pkg.root)})
        with patch.object(run, "_execute_once", side_effect=attempt):
            result = run._execute(self.pkg, self.events, self.params, set())
        self.assertEqual("PASS", result.status)
        self.assertEqual([], result.diagnostics)
        self.assertEqual(2, len(calls))
        self.assertEqual("BLOCKED", canonical.load_file(self.pkg.path("report"))["terminal_status"])
        self.assertEqual(1, result.summary["recovery"]["consumed_rounds"])
        self.assertNotEqual(result.summary["active_package"], result.summary["root_package"])
        self.assertEqual("PASS", canonical.load_file(self.pkg.root / "recovery.json")["active_status"])

    def test_controller_exhausts_round_bound_without_wall_time_deadline(self):
        calls = []
        def attempt(pkg, events, parameters, start_after):
            calls.append(pkg.root)
            return self.failure()
        with patch.object(run, "_execute_once", side_effect=attempt):
            result = run._execute(self.pkg, self.events, self.params, set())
        self.assertEqual("BLOCKED", result.status)
        self.assertEqual(3, len(calls))
        self.assertEqual(2, result.summary["recovery"]["consumed_rounds"])
        self.assertTrue(result.summary["recovery"]["exhausted"])
        active, rounds, maximum = recovery.resolve_active(self.pkg)
        self.assertEqual(calls[-1], active.root)
        self.assertEqual(2, maximum)
        self.assertEqual(2, len(rounds))

    def test_zero_rounds_and_unsupported_requests_make_no_repair_calls(self):
        for result, params in ((self.failure(), {**self.params, "repair_rounds": 0}),
                               (self.failure(code="UNSUPPORTED_CAPABILITY"), self.params)):
            with self.subTest(code=result.diagnostics[0].code), patch.object(run, "_execute_once", return_value=result) as attempt:
                actual = run._execute(self.pkg, self.events, params, set())
                self.assertIs(actual, result)
                self.assertEqual(1, attempt.call_count)
                self.assertFalse((self.pkg.root / "recovery.json").exists())

    def test_provider_failure_keeps_infrastructure_status_in_final_result_and_report(self):
        infra = Diagnostic("PROVIDER_FAILURE", "fixture provider unavailable", severity="infrastructure")
        def stage(name, pkg, events, parameters):
            if name == "formalize":
                raise InfrastructureError("fixture transport failed", [infra])
            self.assertEqual("verify", name)
            return StageResult("verify", "BLOCKED", "no accepted contract", diagnostics=[Diagnostic("VERIFIER_NOT_RUN", "missing IR")],
                               summary={"terminal_status": "BLOCKED"})
        with patch.object(run, "_run_stage", side_effect=stage):
            result = run._execute_once(self.pkg, self.events, self.params, {"interpret"})
        self.assertEqual("INFRASTRUCTURE_FAILURE", result.status)
        self.assertEqual("INFRASTRUCTURE_FAILURE", result.summary["terminal_status"])
        report = canonical.load_file(self.pkg.path("report"))
        self.assertEqual("INFRASTRUCTURE_FAILURE", report["terminal_status"])
        self.assertEqual("PROVIDER_FAILURE", report["infrastructure_errors"][0]["code"])
        self.assertIn("PROVIDER_FAILURE", report["qualified_result"])
        self.assertFalse(recovery.eligible(result, self.params))

    def test_release_infrastructure_failure_does_not_erase_a_mechanical_fact(self):
        from verislop import report, view

        infra = Diagnostic("PROVIDER_FAILURE", "review provider unavailable", severity="infrastructure")
        rep = report.build(self.pkg, view.derive(self.pkg), "BLOCKED", [], [], {"compared": [], "mismatches": []},
                           self.params, "restricted_source", "END_TO_END_VERIFIED", None, [], {}, None)
        rep.update({"mechanical_status": "VERIFIED", "release_status": "BLOCKED"})
        fsutil.write_json(self.pkg.path("report"), rep)
        result = StageResult("verify", "BLOCKED", "mechanics and release", diagnostics=[infra],
                             summary={"mechanical_status": "VERIFIED", "release_status": "BLOCKED"})
        run._record_aggregate_infrastructure(self.pkg, result, self.params)
        rewritten = canonical.load_file(self.pkg.path("report"))
        self.assertEqual("VERIFIED", rewritten["mechanical_status"])
        self.assertEqual("INFRASTRUCTURE_FAILURE", rewritten["release_status"])
        self.assertEqual("VERIFIED", result.summary["mechanical_status"])
        self.assertEqual("INFRASTRUCTURE_FAILURE", result.summary["release_status"])

    def review_fixture(self, *, status="CONFIRMED", claim_id="PROVED:O17@1"):
        from verislop import review_counterexamples

        campaign = "rc-concrete-fixture"
        receipt_ref = f"reviews/{campaign}/counterexamples/critic/1.json"
        receipt = {"schema_version": "0.2", "format": review_counterexamples.RECEIPT_FORMAT, "status": status,
                   "proposal": {"kind": "mechanical_failure", "claim_id": claim_id},
                   "proposal_hash": canonical.digest_json({"kind": "mechanical_failure", "claim_id": claim_id}),
                   "checkpoint": "formal_contract", "checker": {"id": review_counterexamples.VERIFIER,
                       "sha256": review_counterexamples.verifier_hash(review_counterexamples.VERIFIER)},
                   "input_bindings": {}, "claim": {"claim_id": claim_id}, "expected": {"outcome": "PASS"},
                   "observed": {"outcome": "FAIL"}, "diagnostics": []}
        fsutil.write_json(self.pkg.root / receipt_ref, receipt)
        ballot_ref = f"reviews/{campaign}/ballots/critic.json"
        fsutil.write_json(self.pkg.root / ballot_ref, {"counterexample_receipts": [{"status": status,
            "receipt_ref": receipt_ref, "receipt_hash": canonical.digest_file(self.pkg.root / receipt_ref)}]})
        components = {"candidate_root": canonical.digest(b"fixture"), "checkpoint": "formal_contract"}
        cert = {"checkpoint": "formal_contract", "final": "CHANGES_REQUESTED", "target_components": components,
                "review_target_root": canonical.digest_json(components), "tiers": [{"ballots": [{"ballot_ref": ballot_ref}]}]}
        fsutil.write_json(self.pkg.root / f"reviews/{campaign}/consensus-certificate.json", cert)
        fsutil.write_json(self.pkg.root / f"reviews/{campaign}/packet.json", {})
        result = self.failure("review:formal_contract", "REVIEW_REJECTED")
        result.summary["failed_stage_summary"] = {"campaign": campaign}
        return result, receipt_ref, components

    def review_checks(self, components, *, problems=None):
        """Fixture the separately tested consensus checker, never a live review claim."""
        from contextlib import ExitStack
        from verislop import review
        from verislop.providers import config

        stack = ExitStack()
        stack.enter_context(patch.dict(os.environ, {"OLLAMA_MODEL": "fixture-metadata"}))
        stack.enter_context(patch.object(config, "load_user_profiles", return_value={}))
        stack.enter_context(patch.object(review, "target_components", return_value=components))
        self.recheck = stack.enter_context(patch.object(review, "_recheck", return_value=problems or []))
        return stack

    def test_formal_review_repair_requires_confirmed_replayed_receipt(self):
        result, rel, components = self.review_fixture()
        with self.review_checks(components):
            self.assertTrue(recovery.eligible(result, self.params, self.pkg))
            self.recheck.assert_called_once()
            context = recovery.seed(self.pkg, result, self.params)
        self.assertEqual(rel, context["counterexamples"][0]["receipt_ref"])
        self.assertTrue(any("CONFIRMED CONTRACT COUNTEREXAMPLE" in line for line in context["feedback"]))
        self.assertFalse(recovery.eligible(result, self.params))

    def test_review_opinion_unsupported_probe_or_failed_replay_never_starts_repair(self):
        for status in ("UNSUPPORTED", "NOT_REPRODUCED", "INFRASTRUCTURE_FAILURE"):
            with self.subTest(status=status):
                result, _, components = self.review_fixture(status=status)
                with self.review_checks(components):
                    self.assertFalse(recovery.eligible(result, self.params, self.pkg))
        result, _, components = self.review_fixture()
        with self.review_checks(components, problems=["registered replay no longer reproduces the receipt"]):
            self.assertFalse(recovery.eligible(result, self.params, self.pkg))

    def test_immutable_interpretation_defect_is_not_repaired_as_a_contract_change(self):
        result, _, components = self.review_fixture(claim_id="INTERPRETATION:request")
        with self.review_checks(components):
            self.assertFalse(recovery.eligible(result, self.params, self.pkg))

    def test_tampered_review_receipt_cannot_trigger_contract_recovery(self):
        result, rel, components = self.review_fixture()
        receipt = canonical.load_file(self.pkg.root / rel)
        receipt["observed"]["outcome"] = "PASS"
        fsutil.write_json(self.pkg.root / rel, receipt)
        with self.review_checks(components):
            self.assertFalse(recovery.eligible(result, self.params, self.pkg))


class StrictRecoveryLeanIntegrationTests(unittest.TestCase):
    def test_unprovable_frozen_reference_restarts_and_passes_real_strict_gates(self):
        """Real HTTP adapters and Lean; provider responses are deliberate fixtures."""
        from tests.helpers import MockLLM, mock_config, run_cli, unanimous

        good = (EX / "formalization/Contract.lean").read_text()
        bad = good.replace("then .ok (input + 1)", "then .ok (input + 2)")
        self.assertNotEqual(good, bad)
        form = json.loads((EX / "formalization/formalization.json").read_text())
        formalizer_requests = []
        prover_requests = []
        review_requests = []

        def respond(system, user, model):
            if "VeriSlop formalizer" in system:
                formalizer_requests.append(user)
                return json.dumps({"lean_source": bad if len(formalizer_requests) == 1 else good,
                                   "formalization": form})
            if "CURRENT FILE:\n```lean\n" in user:
                prover_requests.append(user)
                current = re.search(r"```lean\n(.*?)\n```", user, re.S)
                self.assertIsNotNone(current)
                return json.dumps({"lean_source": current.group(1)})
            if "adversarial reviewer" in system:
                review_requests.append(user)
                packet_section = user.split("REVIEW PACKET (", 1)[1]
                packet = json.JSONDecoder().raw_decode(packet_section.split("\n", 1)[1])[0]
                ids = packet["counterexample_policy"]["mechanical_claim_ids"]
                probe = {"kind": "mechanical_failure", "claim_id": "INTERPRETATION:request" if "INTERPRETATION:request" in ids else ids[0]}
                return json.dumps({"verdict": "ACCEPT", "reviewed_obligations": packet["scope"], "findings": [],
                    "limitations": ["loopback fixture response, not a live-model measurement"], "rationale": "fixture probe replay",
                    "search": {"method": "attempt a registered required-claim failure", "attempted_cases": 1,
                               "probes": [probe], "conclusion": "NO_COUNTEREXAMPLE_FOUND"}})
            if "implementation agent" in system:
                return json.dumps({"files": {"bounded_increment.py": (EX / "python/bounded_increment.py").read_text()},
                                   "bindings": json.loads((EX / "python/bindings.json").read_text())})
            raise AssertionError("unexpected fixture role request")

        with tempfile.TemporaryDirectory(prefix="verislop-real-recovery-") as temporary:
            root = Path(temporary)
            server = MockLLM(respond)
            try:
                cfg, env = mock_config(root, server.port, [unanimous("R0", "critic", 1)], max_repair_rounds=1)
                conf = json.loads(cfg.read_text())
                conf["providers"]["mock"]["request_timeout_seconds"] = None
                conf["review"]["budgets"]["max_wall_seconds_per_tier"] = 0
                cfg.write_text(json.dumps(conf))
                code, result, stderr = run_cli("run", "--prompt-file", str(EX / "request.txt"),
                    "--request-ref", "examples/request.txt", "--mode", "software", "--config", str(cfg),
                    "--draft-candidate", str(EX / "draft.json"), "--ledger-candidate", str(EX / "interpretation.json"),
                    "--runs-dir", str(root / "runs"), "--run-id", "broken-first", "--tier", "0", "--target", "python",
                    "--endpoint", "test_campaign", "--require-state", "TESTED", "--require-tests", "--non-interactive",
                    "--policy", "strict", "--budget-seconds", "0", "--repair-rounds", "1", "--seed", "1701", "--cases", "32",
                    env=env)
                self.assertEqual(0, code, (result, stderr))
                self.assertEqual("PASS", result["status"])
                self.assertEqual(1, result["summary"]["recovery"]["consumed_rounds"])
                self.assertEqual(2, len(formalizer_requests))
                self.assertTrue(prover_requests)
                self.assertEqual(2, len(review_requests))
                original = Package(root / "runs/broken-first")
                active, rounds, _ = recovery.resolve_active(original)
                self.assertEqual("accept", rounds[0]["rejected_stage"])
                self.assertEqual(original.interpretation_root(), active.interpretation_root())
                self.assertIn("then .ok (input + 2)", (original.path("contract") / "challenge/Contract.lean").read_text())
                self.assertIn("then .ok (input + 1)", (active.path("contract") / "challenge/Contract.lean").read_text())
                self.assertTrue((original.path("contract") / "proofs/candidate.lean").is_file())
                self.assertEqual("BLOCKED", canonical.load_file(original.path("report"))["terminal_status"])
                report = canonical.load_file(active.path("report"))
                self.assertEqual("VERIFIED", report["terminal_status"])
                self.assertEqual("accepted_and_proved", canonical.load_file(active.path("accepted") / "acceptance.json")["gate"])
                self.assertEqual("PASS", report["obligations"]["O17"]["outcomes"]["TESTED"])
                self.assertEqual(2, len(report["builds"]))
                self.assertTrue(all(build["ok"] for build in report["builds"]))
                self.assertIn("input + 2", formalizer_requests[1])
                self.assertIn("PROOF_UNRESOLVED", formalizer_requests[1])
                self.assertTrue(all(stage["status"] == "PASS" for stage in result["summary"]["stages"]))
            finally:
                server.close()



if __name__ == "__main__":
    unittest.main()
