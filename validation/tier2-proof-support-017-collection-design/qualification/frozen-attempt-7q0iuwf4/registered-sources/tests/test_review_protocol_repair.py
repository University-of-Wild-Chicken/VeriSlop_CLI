"""Ballot corrections use a fixed packet and finite slots, independently of HTTP retries."""
from __future__ import annotations

import json
import copy
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import MockLLM, TempDir, build, codes, mock_config, run_cli, unanimous
from test_providers_review import accepted_review, review_packet
from verislop import canonical, dsl, fsutil, review, review_counterexamples
from verislop.errors import Diagnostic, InfrastructureError, UsageError
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker


class ReviewProtocolRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.handler = lambda system, user, model: json.dumps(accepted_review(user, review_packet(user)["scope"]))
        self.mock = MockLLM(lambda *args: self.handler(*args))
        self.addCleanup(self.mock.close)
        self.config, self.env = mock_config(self.tmp.path, self.mock.port, [unanimous("R0", "critic", 1)],
                                           checkpoints=["interpretation"])
        self.configure(max_provider_retries=0, max_calls_per_instance=8, max_wall_seconds_per_tier=0)
        self.pkg = self.tmp.path / "package"
        self.assertEqual(0, build(self.pkg, "interpret")["interpret"][0])

    def configure(self, **budgets):
        conf = canonical.load_file(self.config)
        conf["review"]["budgets"].update(budgets)
        self.config.write_bytes(canonical.dumps(conf))
        return conf

    def invoke(self):
        code, result, output = run_cli("review", "--package", str(self.pkg), "--config", str(self.config),
                                       "--checkpoint", "interpretation", env=self.env)
        campaign = next((self.pkg / "reviews").glob("rc-*"))
        certificate = canonical.load_file(campaign / "consensus-certificate.json")
        return code, result, output, campaign, certificate

    def test_zero_transport_retries_still_corrects_missing_search_with_exact_context(self):
        bad_responses = []
        def respond(system, user, model):
            ballot = accepted_review(user, review_packet(user)["scope"])
            if not bad_responses:
                del ballot["search"]
                ballot["rationale"] = "retain this exact first response"
                bad_responses.append(json.dumps(ballot))
                return bad_responses[0]
            return json.dumps(ballot)
        self.handler = respond
        code, result, output, campaign, cert = self.invoke()
        self.assertEqual(0, code, (result, output))
        self.assertEqual("REVIEW_ACCEPTED", cert["final"])
        self.assertEqual(2, len(self.mock.requests))
        first_user, corrected_user = [x["body"]["messages"][1]["content"] for x in self.mock.requests]
        self.assertEqual(review_packet(first_user), review_packet(corrected_user))
        self.assertIn(bad_responses[0], corrected_user)
        self.assertIn("search must record method, attempted_cases, constructed probes and conclusion", corrected_user)
        attempt = campaign / "ballot-attempts/R0_critic#1"
        self.assertEqual(bad_responses[0], (attempt / "1.raw.txt").read_text())
        self.assertEqual("invalid_protocol", canonical.load_file(attempt / "1.json")["status"])
        self.assertEqual("valid_protocol", canonical.load_file(attempt / "2.json")["status"])
        tally = cert["tiers"][0]["tally"]
        self.assertEqual(1, tally["members"])
        self.assertEqual(1, tally["accepts"])
        self.assertEqual([], tally["missing"])

    def test_invalid_json_and_wrong_checkpoint_probe_receive_bounded_correction(self):
        users = []
        def respond(system, user, model):
            users.append(user)
            if len(users) == 1:
                return "{unclosed ballot"
            ballot = accepted_review(user, review_packet(user)["scope"])
            if len(users) == 2:
                # This is closed probe syntax, but interpretation has no implementation to execute.
                ballot["search"]["probes"] = [{"kind": "target_case", "obligation_id": "O17", "assignment": []}]
            return json.dumps(ballot)
        self.handler = respond
        code, result, output, _, cert = self.invoke()
        self.assertEqual(0, code, (result, output))
        self.assertEqual(3, len(users))
        self.assertIn("{unclosed ballot", users[1])
        self.assertIn("probe kind target_case is outside the admitted checkpoint proposals", users[2])
        self.assertTrue(all(review_packet(u) == review_packet(users[0]) for u in users))
        for user in users:
            guidance = json.JSONDecoder().raw_decode(user.split("CURRENT CHECKPOINT RULES (supervisor-selected):", 1)[1].lstrip())[0]
            self.assertEqual(["mechanical_failure", "missing_requirement"], guidance["allowed_probe_kinds"])
            self.assertIn("cannot execute a Lean reference", guidance["restriction"])
        self.assertEqual(2, users[2].count("CURRENT CHECKPOINT RULES (supervisor-selected):"))
        self.assertIn("Discard probes of an invalid kind and reconstruct an allowed probe", users[2])
        self.assertEqual("REVIEW_ACCEPTED", cert["final"])

    def test_exhausted_protocol_budget_never_reduces_the_denominator(self):
        self.handler = lambda *_: "no JSON object"
        code, result, _, campaign, cert = self.invoke()
        self.assertEqual(2, code)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))
        self.assertEqual(3, len(self.mock.requests))
        self.assertEqual("INCOMPLETE", cert["final"])
        tally = cert["tiers"][0]["tally"]
        self.assertEqual(1, tally["members"])
        self.assertEqual(0, tally["accepts"])
        self.assertEqual(["R0/critic#1"], tally["missing"])
        self.assertEqual(3, len(list((campaign / "ballot-attempts/R0_critic#1").glob("*.raw.txt"))))

    def test_explicit_call_cap_still_limits_protocol_correction(self):
        self.configure(max_calls_per_instance=1)
        self.handler = lambda *_: "no JSON object"
        code, result, _, _, cert = self.invoke()
        self.assertEqual(2, code)
        self.assertEqual(1, len(self.mock.requests))
        self.assertEqual("INCOMPLETE", cert["final"])

    def test_valid_abstention_is_preserved_without_protocol_retry_or_acceptance(self):
        raw = []
        def respond(system, user, model):
            ballot = accepted_review(user, review_packet(user)["scope"])
            ballot["verdict"] = "ABSTAIN"
            ballot["search"]["conclusion"] = "INCOMPLETE"
            ballot["rationale"] = "uncertainty about the current scoped interpretation remains"
            raw.append(json.dumps(ballot))
            return raw[-1]
        self.handler = respond
        code, result, _, campaign, cert = self.invoke()
        self.assertEqual(2, code)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))
        self.assertEqual(1, len(self.mock.requests))
        self.assertEqual("INCOMPLETE", cert["final"])
        ballot = canonical.load_file(campaign / "ballots/R0_critic#1.json")
        self.assertEqual("ABSTAIN", ballot["reported_verdict"])
        self.assertEqual("ABSTAIN", ballot["verdict"])
        self.assertEqual(raw[0], (campaign / "ballot-attempts/R0_critic#1/1.raw.txt").read_text())
        self.assertEqual(["NOT_REPRODUCED"], [receipt["status"] for receipt in ballot["counterexample_receipts"]])

    def test_confirmed_counterexample_cannot_be_corrected_into_acceptance(self):
        pkg = Package(self.pkg)
        pkg.evidence.record(claim_id="INTERPRETATION:request", verifier_id="verislop.interpretation-recorder",
                            status="BLOCK", scope=["confirmed failed mechanical interpretation claim"],
                            input_root=pkg.interpretation_root(), result={"milestone_outcome": "FAIL"},
                            invocation=["regression fixture"])
        code, result, _, campaign, cert = self.invoke()
        self.assertEqual(2, code)
        self.assertIn("REVIEW_REJECTED", codes(result))
        self.assertEqual(1, len(self.mock.requests))
        self.assertEqual("CHANGES_REQUESTED", cert["final"])
        ballot_path = campaign / "ballots/R0_critic#1.json"
        ballot = canonical.load_file(ballot_path)
        self.assertEqual("ACCEPT", ballot["reported_verdict"])
        self.assertEqual("REJECT", ballot["verdict"])
        self.assertTrue(ballot["unresolved_blocking_findings"])
        self.assertEqual(["CONFIRMED"], [r["status"] for r in ballot["counterexample_receipts"]])

    def test_provider_failure_is_not_retried_as_a_ballot_defect(self):
        error = InfrastructureError("service unavailable", [Diagnostic("PROVIDER_FAILURE", "offline", severity="infrastructure")])
        with patch.object(Broker, "call", side_effect=error) as call:
            code, result, _, campaign, cert = self.invoke()
        self.assertEqual(3, code)
        self.assertEqual(1, call.call_count)
        self.assertIn("PROVIDER_FAILURE", codes(result))
        self.assertEqual("INCOMPLETE", cert["final"])
        attempt = canonical.load_file(campaign / "ballot-attempts/R0_critic#1/1.json")
        self.assertEqual("provider_failure", attempt["status"])

    def test_model_identity_mismatch_is_not_retried_or_counted(self):
        conf = canonical.load_file(self.config)
        conf["agents"]["critic"]["model_identity"] = {"mode": "pinned", "resolved_model": "pinned-model"}
        self.config.write_bytes(canonical.dumps(conf))
        completion = Completion("{}", "mock-reviewer", "different-model", None, 1, 1)
        with patch.object(Broker, "call", return_value=completion) as call:
            code, result, _, campaign, cert = self.invoke()
        self.assertEqual(2, code)
        self.assertEqual(1, call.call_count)
        self.assertEqual(0, cert["tiers"][0]["tally"]["accepts"])
        self.assertEqual("model_identity_mismatch", canonical.load_file(campaign / "ballot-attempts/R0_critic#1/1.json")["status"])

    def test_parallel_reviewers_only_see_their_own_previous_response(self):
        conf = canonical.load_file(self.config)
        tier = unanimous("R0", "critic", 1)
        tier["reviewers"].append({"agent": "second-critic", "count": 1, "focus": "counterexamples"})
        conf["review"]["review_tiers"] = [tier]
        conf["agents"]["critic"]["model_ref"] = "review-one"
        conf["agents"]["second-critic"] = {**conf["agents"]["critic"], "model_ref": "review-two"}
        self.config.write_bytes(canonical.dumps(conf))
        counts = {}
        originals = {}
        lock = threading.Lock()
        def respond(system, user, model):
            with lock:
                counts[model] = counts.get(model, 0) + 1
                number = counts[model]
            ballot = accepted_review(user, review_packet(user)["scope"])
            if number == 1:
                del ballot["search"]
                ballot["rationale"] = f"private prior ballot for {model}"
                originals[model] = json.dumps(ballot)
                return originals[model]
            other = "review-two" if model == "review-one" else "review-one"
            self.assertIn(originals[model], user)
            self.assertNotIn(f"private prior ballot for {other}", user)
            return json.dumps(ballot)
        self.handler = respond
        code, result, output, _, cert = self.invoke()
        self.assertEqual(0, code, (result, output))
        self.assertEqual({"review-one": 2, "review-two": 2}, counts)
        self.assertEqual(2, cert["tiers"][0]["tally"]["members"])
        self.assertEqual(2, cert["tiers"][0]["tally"]["accepts"])

    def test_checkpoint_policy_never_advertises_unavailable_target_execution(self):
        pkg = Package(self.pkg)
        for checkpoint in ("interpretation", "formal_contract"):
            policy = review._counterexample_policy(pkg, checkpoint, ["O17"])
            self.assertEqual({"mechanical_failure", "missing_requirement"}, set(policy["proposals"]))
        policy = review._counterexample_policy(pkg, "release", ["O17"])
        self.assertNotIn("missing_requirement", policy["proposals"])
        with patch("verislop.backends.registry.is_vscore", return_value=True):
            policy = review._counterexample_policy(pkg, "release", ["O17"])
        self.assertEqual({"mechanical_failure"}, set(policy["proposals"]))

    def test_formal_contract_checkpoint_guidance_has_only_closed_mechanical_and_clause_shapes(self):
        pkg = Package(self.pkg)
        policy = review._counterexample_policy(pkg, "formal_contract", ["O17"])
        text = review._checkpoint_guidance("formal_contract", policy)
        guidance = json.JSONDecoder().raw_decode(text.split("CURRENT CHECKPOINT RULES (supervisor-selected):", 1)[1].lstrip())[0]
        self.assertEqual("formal_contract", guidance["checkpoint"])
        self.assertEqual(["mechanical_failure", "missing_requirement"], guidance["allowed_probe_kinds"])
        self.assertNotIn("target_case", guidance["closed_proposal_templates"])
        self.assertIn("target_case cannot execute a Lean reference", guidance["restriction"])
        self.assertIn("interpretation and formal_contract allow ONLY mechanical_failure and missing_requirement", review.REVIEW_SYSTEM)
        self.assertIn("Python implementation/release ONLY", review.REVIEW_SYSTEM)
        self.assertEqual(["INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED"], guidance["current_milestones"])
        self.assertEqual(["IMPLEMENTED", "LINKED", "TESTED", "END_TO_END_VERIFIED"], guidance["outside_checkpoint_milestones"])
        self.assertIn("future Python implementation/testing/closure are outside this checkpoint", guidance["decision_scope"])
        self.assertIn("actual current uncertainty still warrants ABSTAIN", guidance["future_artifact_rule"])
        release = review._checkpoint_guidance("release", review._counterexample_policy(pkg, "release", ["O17"]))
        release_rules = json.JSONDecoder().raw_decode(release.split("CURRENT CHECKPOINT RULES (supervisor-selected):", 1)[1].lstrip())[0]
        self.assertEqual(list(review.MILESTONES), release_rules["current_milestones"])
        self.assertEqual([], release_rules["outside_checkpoint_milestones"])
        self.assertIn("full current requested release evidence", release_rules["decision_scope"])
        self.assertFalse(any("target_case supports" in line for line in policy["limitations"]))
        self.assertNotIn("assignment_wire_format", policy)
        self.assertNotIn("target_case_binders", policy)
        for template in policy["proposals"].values():
            self.assertEqual([], review_counterexamples.validate_proposal(template), template)
        clause = policy["proposals"]["missing_requirement"]
        prompt = pkg.path("prompt").read_bytes()
        self.assertEqual(clause["quoted"], prompt[clause["start_byte"]:clause["end_byte"]].decode())


class TargetAssignmentGuidanceTests(unittest.TestCase):
    """Formula shape is fixture-isolated; expression-byte hashes use the real reader."""
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(self.tmp.path / "packet-fixture")
        self.pkg.ensure("packet-fixture")
        error = {"enum": "Failure"}
        result = {"result": {"error": error, "ok": {"result": {"error": "Unit", "ok": "Nat"}}}}
        self.sorts = ["Nat", "Bool", "Unit", error, result]
        self.profile = {"profile_id": "assignment-fixture", "predicates": {},
                        "enums": {"Failure": {"constructors": ["failed"]}},
                        "symbols": {"mixed": {"lean_decl": "Model.mixed", "args": self.sorts, "result": "Nat"},
                                    "diagonal": {"lean_decl": "Model.diagonal", "args": ["Nat", "Nat"], "result": "Nat"}}}
        args = [{"tag": "var", "index": i} for i in reversed(range(len(self.sorts)))]
        body = {"tag": "eq", "left": {"tag": "call", "symbol": "mixed", "args": args}, "right": {"tag": "nat", "value": "0"}}
        mixed = self.quantified(self.sorts, body)
        diagonal = {"tag": "eq", "left": {"tag": "call", "symbol": "diagonal", "args": [{"tag": "var", "index": 0}] * 2},
                    "right": {"tag": "nat", "value": "0"}}
        self.ir = {"obligations": {"O1": self.record("O1", mixed),
                                   "O4": self.record("O4", self.quantified(["Nat"], diagonal))}}
        residual = {"tag": "exists", "sort": "Nat", "body": {
            "tag": "eq", "left": {"tag": "call", "symbol": "diagonal",
                                     "args": [{"tag": "var", "index": 1}, {"tag": "var", "index": 0}]},
            "right": {"tag": "nat", "value": "0"}}}
        self.ir["obligations"]["Residual"] = self.record("Residual", self.quantified(["Nat"], residual))
        for oid, role, kind, representation in (("D1", "declaration", "entity", "typed_metadata"),
                ("Opaque", "guarantee", "postcondition", "lean_expr"), ("Witness", "guarantee", "non_vacuity", "contract_dsl"),
                ("Liveness", "guarantee", "liveness_property", "contract_dsl"), ("Resource", "guarantee", "resource_constraint", "contract_dsl")):
            self.ir["obligations"][oid] = {"id": oid, "required": True, "role": role, "kind": kind,
                                           "formal": {"representation": representation}}
        fsutil.write_json(self.pkg.path("accepted_ir"), self.ir)
        self.checked_hash = canonical.digest_json(self.ir)
        self.accepted = patch("verislop.export.verified_ir", return_value=(self.ir, self.checked_hash, {}, []))
        self.accepted.start()
        self.addCleanup(self.accepted.stop)
        profile = patch.object(review.C, "frozen_json", return_value=self.profile)
        profile.start()
        self.addCleanup(profile.stop)

    def quantified(self, sorts, body):
        for sort in reversed(sorts):
            body = {"tag": "forall", "sort": sort, "body": body}
        return body

    def record(self, oid, formula):
        package = dsl.make_package(formula, self.profile["profile_id"])
        dsl.check_package(package, dsl.Profile.from_json(self.profile))
        digest = canonical.digest_json(package)
        fsutil.write_json(self.pkg.path("accepted") / "expressions" / (digest[7:] + ".json"), package)
        return {"id": oid, "required": True, "role": "guarantee", "kind": "postcondition",
                "formal": {"representation": "contract_dsl", "formula_ref": f"artifact:accepted-expressions/{oid}@{digest}"}}

    def policy(self):
        return review._counterexample_policy(self.pkg, "release", list(self.ir["obligations"]))

    def test_binder_shapes_use_hash_bound_accepted_formulas_and_universal_arity(self):
        policy = self.policy()
        guidance = policy["target_case_binders"]
        self.assertEqual(self.checked_hash, guidance["accepted_ir_sha256"])
        mixed = guidance["obligations"]["O1"]
        self.assertEqual("supported", mixed["status"])
        self.assertEqual(self.sorts, mixed["leading_universal_sorts"])
        self.assertEqual(5, mixed["assignment_arity"])
        self.assertEqual(self.ir["obligations"]["O1"]["formal"]["formula_ref"], mixed["formula_ref"])
        diagonal = guidance["obligations"]["O4"]
        self.assertEqual(1, diagonal["assignment_arity"])
        self.assertEqual(["Nat"], diagonal["leading_universal_sorts"])
        self.assertEqual(2, len(self.profile["symbols"]["diagonal"]["args"]))
        profile = dsl.Profile.from_json(self.profile)
        for oid in ("O1", "O4"):
            item = guidance["obligations"][oid]
            proposal = {"kind": "target_case", "obligation_id": oid, "assignment": item["assignment_example"]}
            self.assertEqual([], review_counterexamples.validate_proposal(proposal))
            for value, sort in zip(item["assignment_example"], item["leading_universal_sorts"]):
                self.assertTrue(dsl.value_has_sort(review_counterexamples._decode(value, sort, profile), sort, profile))

    def test_published_templates_and_wire_examples_use_closed_probe_syntax(self):
        policy = self.policy()
        templates = [policy["proposals"], review._counterexample_policy(self.pkg, "interpretation", ["O1"])["proposals"]]
        for proposals in templates:
            for kind, template in proposals.items():
                example = copy.deepcopy(template)
                if kind == "target_case":
                    example.update(obligation_id="O1", assignment=policy["target_case_binders"]["obligations"]["O1"]["assignment_example"])
                elif kind == "mechanical_failure":
                    example["claim_id"] = "INTERPRETATION:request"
                elif kind == "missing_requirement":
                    example.update(start_byte=0, end_byte=5, quoted="Do A.")
                elif kind == "source_violation":
                    example.update(obligation_id="O1", file="identity.py", ast_path="/body/0")
                else:
                    self.fail("published probe kind has no closed illustration: " + kind)
                self.assertEqual([], review_counterexamples.validate_proposal(example), example)
        wire = policy["assignment_wire_format"]
        values = [wire[key]["example"] for key in ("Nat", "Bool", "Unit")]
        values += [wire["Result"]["ok_example"], wire["Result"]["error_example"]]
        for value in values:
            self.assertEqual([], review_counterexamples.validate_proposal({"kind": "target_case", "obligation_id": "O1", "assignment": [value]}))
        for invalid in wire["forbidden_examples"]:
            self.assertTrue(review_counterexamples.validate_proposal({"kind": "target_case", "obligation_id": "O1", "assignment": invalid}))
        self.assertIn("NEVER a string", review.REVIEW_SYSTEM)
        self.assertIn('"assignment":[{"int":"0"},{"int":"3"}]', review.REVIEW_SYSTEM)

    def test_opaque_metadata_witness_and_unsupported_residuals_have_no_target_hint(self):
        guidance = self.policy()["target_case_binders"]["obligations"]
        for oid in ("D1", "Opaque", "Witness", "Liveness", "Resource", "Residual"):
            self.assertEqual("unsupported", guidance[oid]["status"])
            self.assertNotIn("assignment_example", guidance[oid])
        self.assertIn("unbounded residual", guidance["Residual"]["reason"])
        self.assertIn("mechanical_failure", self.policy()["proposals"])

    def test_changed_expression_bytes_and_infrastructure_fail_immediately(self):
        record = self.ir["obligations"]["O1"]
        digest = record["formal"]["formula_ref"].rsplit("@", 1)[-1]
        path = self.pkg.path("accepted") / "expressions" / (digest[7:] + ".json")
        fsutil.atomic_write(path, b"{}")
        with self.assertRaises(UsageError) as raised:
            self.policy()
        self.assertEqual("INPUT_MUTATION", raised.exception.diagnostics[0].code)
        infra = Diagnostic("VERIFIER_FAILURE", "fixture unavailable", severity="infrastructure")
        with patch("verislop.export.verified_ir", return_value=(None, None, None, [infra])), self.assertRaises(InfrastructureError):
            self.policy()


if __name__ == "__main__":
    unittest.main()
