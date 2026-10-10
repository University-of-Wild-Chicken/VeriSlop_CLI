"""Concrete counterexample construction and replay in the live CLI reviewer workflow.

The provider is a loopback mock. Target counterexamples execute the actual linked Python
candidate; a reviewer assertion is never substituted for the supervisor's observation.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import MockLLM, TempDir, build, codes, copy_pkg, impl_variant, mock_config, run_cli, unanimous, writable
from test_providers_review import accepted_review, rejected_boundary_review, review_packet
from verislop import canonical, review


def example_ballot() -> dict:
    return {"verdict": "ACCEPT", "reviewed_obligations": ["O1"], "findings": [], "limitations": [],
            "rationale": "bounded concrete search completed",
            "search": {"method": "replay a required mechanical claim", "attempted_cases": 1,
                       "probes": [{"kind": "mechanical_failure", "claim_id": "TYPECHECKED:O1@1"}],
                       "conclusion": "NO_COUNTEREXAMPLE_FOUND"}}


class CounterexampleBallotUnitTests(unittest.TestCase):
    def test_accepted_ballot_must_construct_a_probe(self):
        missing = example_ballot()
        del missing["search"]
        self.assertIsNone(review.parse_ballot(missing, ["O1"])[0])
        empty = example_ballot()
        empty["search"].update(attempted_cases=0, probes=[])
        self.assertIsNone(review.parse_ballot(empty, ["O1"])[0])

    def test_reported_search_count_must_equal_constructed_probes(self):
        ballot = example_ballot()
        ballot["search"]["attempted_cases"] = 500
        self.assertIsNone(review.parse_ballot(ballot, ["O1"])[0])
        ballot["search"]["attempted_cases"] = True
        self.assertIsNone(review.parse_ballot(ballot, ["O1"])[0])

    def test_repeated_or_over_budget_probes_cannot_complete_search(self):
        duplicate = example_ballot()
        duplicate["search"]["probes"] *= 2
        duplicate["search"]["attempted_cases"] = 2
        self.assertIsNone(review.parse_ballot(duplicate, ["O1"])[0])
        excessive = example_ballot()
        excessive["search"]["probes"] = [{"kind": "mechanical_failure", "claim_id": f"TYPECHECKED:O{i}@1"}
                                         for i in range(9)]
        excessive["search"]["attempted_cases"] = 9
        self.assertIsNone(review.parse_ballot(excessive, ["O1"])[0])

    def test_speculative_rejection_is_not_a_valid_ballot(self):
        ballot = example_ballot()
        ballot["verdict"] = "REJECT"
        ballot["search"]["conclusion"] = "COUNTEREXAMPLE_CANDIDATE"
        ballot["findings"] = [{"id": "F1", "severity": "blocking", "obligations": ["O1"],
                               "statement": "the generator might be unreliable",
                               "counterexample": "an untested edge case could exist"}]
        self.assertIsNone(review.parse_ballot(ballot, ["O1"])[0])

    def test_candidate_finding_must_be_one_of_the_constructed_probes(self):
        ballot = example_ballot()
        ballot["verdict"] = "REJECT"
        ballot["search"]["conclusion"] = "COUNTEREXAMPLE_CANDIDATE"
        ballot["findings"] = [{"id": "F1", "severity": "blocking", "obligations": ["O1"],
                               "statement": "a concrete target case fails",
                               "counterexample": {"kind": "target_case", "obligation_id": "O1",
                                                  "assignment": [{"int": "0"}]}}]
        self.assertIsNone(review.parse_ballot(ballot, ["O1"])[0])


class CounterexampleReviewWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.behavior = {"handler": accepted_review}

        def handler(system, user, model):
            packet = review_packet(user)
            return json.dumps(cls.behavior["handler"](user, packet["scope"]))

        cls.mock = MockLLM(handler)
        cls.config, cls.env = mock_config(cls.tmp.path, cls.mock.port,
                                         [unanimous("R0", "critic", 2), unanimous("R1", "final-critic", 1)],
                                         checkpoints=["release"])
        cls.good = cls.tmp.path / "good"
        built = build(cls.good, "link")
        if built["link"][0] != 0:
            raise AssertionError(built)
        cls.bad = copy_pkg(cls.good, cls.tmp.path / "bad")
        candidate = impl_variant(cls.tmp.path, "wrong-boundary",
                                 "def increment(limit, input):\n"
                                 "    return ('ok', input + 1) if input <= limit else ('error', 'limitReached')\n")
        for stage, extra in (("generate", ["--candidate", str(candidate), "--tier", "0"]), ("link", [])):
            code, result, output = run_cli(stage, "--package", str(cls.bad), *extra)
            if code:
                raise AssertionError((stage, result, output))

    @classmethod
    def tearDownClass(cls):
        cls.mock.close()
        cls.tmp.cleanup()

    def setUp(self):
        self.behavior["handler"] = accepted_review
        self.mock.requests.clear()

    def run_review(self, *, bad=False):
        package = copy_pkg(self.bad if bad else self.good, self.tmp.path / self._testMethodName)
        code, result, output = run_cli("review", "--package", str(package), "--config", str(self.config),
                                       "--checkpoint", "release", env=self.env)
        campaign = next((package / "reviews").glob("rc-*"))
        certificate = canonical.load_file(campaign / "consensus-certificate.json")
        return code, result, output, package, campaign, certificate

    @staticmethod
    def receipt_statuses(campaign):
        return [data["status"] for path in campaign.rglob("*.json")
                if isinstance((data := canonical.load_file(path)), dict)
                and data.get("status") in {"CONFIRMED", "NOT_REPRODUCED", "UNSUPPORTED", "INFRASTRUCTURE_FAILURE"}]

    def test_every_tier_and_instance_constructs_probes_before_acceptance(self):
        code, result, output, _, campaign, certificate = self.run_review()
        self.assertEqual(code, 0, (result, output))
        self.assertEqual([t["result"] for t in certificate["tiers"]], ["TIER_ACCEPTED", "TIER_ACCEPTED"])
        self.assertEqual(len(self.mock.requests), 3)
        for request in self.mock.requests:
            system, user = [m["content"] for m in request["body"]["messages"]]
            self.assertIn("construct", system.lower())
            self.assertIn("counterexample", system.lower())
            self.assertIn("probes", system)
            self.assertTrue(review_packet(user)["counterexample_policy"]["mechanical_claim_ids"])
        for path in (campaign / "ballots").glob("*.json"):
            ballot = canonical.load_file(path)
            self.assertEqual(ballot["schema_version"], "0.2")
            self.assertEqual(ballot["verdict"], "ACCEPT")
            self.assertIn("search", ballot)
        self.assertIn("NOT_REPRODUCED", self.receipt_statuses(campaign))

    def test_vague_blocking_reject_is_incomplete_not_a_confirmed_rejection(self):
        def speculative(user, scope):
            ballot = accepted_review(user, scope)
            ballot["verdict"] = "REJECT"
            ballot["search"]["conclusion"] = "COUNTEREXAMPLE_CANDIDATE"
            ballot["findings"] = [{"id": "F1", "severity": "blocking", "obligations": ["E1"],
                                   "statement": "the implementation might be unreliable",
                                   "counterexample": "a boundary might be wrong"}]
            return ballot

        self.behavior["handler"] = speculative
        code, result, _, _, campaign, certificate = self.run_review()
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))
        self.assertNotIn("REVIEW_REJECTED", codes(result))
        self.assertEqual([t["result"] for t in certificate["tiers"]], ["INCOMPLETE", "NOT_REACHED"])
        self.assertEqual(certificate["tiers"][0]["tally"]["rejects"], 0)
        self.assertNotIn("CONFIRMED", self.receipt_statuses(campaign))

    def test_unreproduced_target_candidate_becomes_abstention(self):
        self.behavior["handler"] = lambda user, scope: rejected_boundary_review(scope)
        code, result, _, _, campaign, certificate = self.run_review()
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))
        self.assertNotIn("REVIEW_REJECTED", codes(result))
        self.assertEqual(certificate["tiers"][0]["result"], "INCOMPLETE")
        self.assertIn("NOT_REPRODUCED", self.receipt_statuses(campaign))
        for path in (campaign / "ballots").glob("*.json"):
            self.assertEqual(canonical.load_file(path)["verdict"], "ABSTAIN")

    def test_unsupported_declaration_target_replay_stays_incomplete(self):
        def unsupported(user, scope):
            ballot = rejected_boundary_review(scope)
            probe = {"kind": "target_case", "obligation_id": "D1", "assignment": []}
            ballot["search"]["probes"] = [probe]
            ballot["findings"][0].update(obligations=["D1"], counterexample=probe,
                                         statement="attempt to execute a declaration as a guarantee")
            return ballot

        self.behavior["handler"] = unsupported
        code, result, _, _, campaign, certificate = self.run_review()
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))
        self.assertNotIn("REVIEW_REJECTED", codes(result))
        self.assertEqual(certificate["tiers"][0]["result"], "INCOMPLETE")
        self.assertIn("UNSUPPORTED", self.receipt_statuses(campaign))
        for path in (campaign / "ballots").glob("*.json"):
            self.assertEqual(canonical.load_file(path)["verdict"], "ABSTAIN")

    def test_confirmed_false_target_case_rejects_without_escalation(self):
        self.behavior["handler"] = lambda user, scope: rejected_boundary_review(scope)
        code, result, _, package, campaign, certificate = self.run_review(bad=True)
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_REJECTED", codes(result))
        self.assertEqual([t["result"] for t in certificate["tiers"]], ["CHANGES_REQUESTED", "NOT_REACHED"])
        self.assertFalse(certificate["mechanical_veto"], "this rejection must come from the concrete target replay")
        self.assertIn("CONFIRMED", self.receipt_statuses(campaign))
        self.assertEqual(len(self.mock.requests), 2)
        for path in (campaign / "ballots").glob("*.json"):
            self.assertEqual(canonical.load_file(path)["verdict"], "REJECT")
        code, result, output = run_cli("review", "tally", "--package", str(package), env=self.env)
        self.assertEqual(code, 0, (result, output))
        self.assertEqual(result["summary"][campaign.name]["final"], "CHANGES_REQUESTED")

    def test_confirmed_probe_overrides_reported_acceptance(self):
        def hides_counterexample(user, scope):
            ballot = accepted_review(user, scope)
            ballot["search"]["probes"] = [{"kind": "target_case", "obligation_id": "E1",
                                            "assignment": [{"int": "0"}, {"int": "0"}]}]
            return ballot

        self.behavior["handler"] = hides_counterexample
        code, result, _, package, campaign, certificate = self.run_review(bad=True)
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_REJECTED", codes(result))
        self.assertEqual([t["result"] for t in certificate["tiers"]], ["CHANGES_REQUESTED", "NOT_REACHED"])
        self.assertIn("CONFIRMED", self.receipt_statuses(campaign))
        for path in (campaign / "ballots").glob("*.json"):
            ballot = canonical.load_file(path)
            self.assertEqual(ballot["verdict"], "REJECT")
            reported = canonical.loads((package / ballot["transcript_ref"]).read_bytes())
            self.assertEqual(reported["verdict"], "ACCEPT")
            self.assertEqual(reported["findings"], [])
        code, result, output = run_cli("review", "tally", "--package", str(package), env=self.env)
        self.assertEqual(code, 0, (result, output))
        self.assertEqual(result["summary"][campaign.name]["final"], "CHANGES_REQUESTED")

    def test_changed_counterexample_receipt_cannot_re_tally(self):
        self.behavior["handler"] = lambda user, scope: rejected_boundary_review(scope)
        code, result, _, package, campaign, _ = self.run_review(bad=True)
        self.assertEqual(code, 2, result)
        confirmed = next(path for path in campaign.rglob("*.json")
                         if canonical.load_file(path).get("status") == "CONFIRMED")
        receipt = canonical.load_file(confirmed)
        receipt["status"] = "NOT_REPRODUCED"
        writable(confirmed)
        confirmed.write_bytes(canonical.dumps(receipt))
        code, result, _ = run_cli("review", "tally", "--package", str(package), env=self.env)
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))

    def test_rehashed_false_receipt_still_fails_independent_replay(self):
        self.behavior["handler"] = lambda user, scope: rejected_boundary_review(scope)
        code, result, _, package, campaign, certificate = self.run_review(bad=True)
        self.assertEqual(code, 2, result)
        receipt_path = next(path for path in campaign.rglob("*.json")
                            if canonical.load_file(path).get("status") == "CONFIRMED")
        receipt = canonical.load_file(receipt_path)
        receipt["status"] = "NOT_REPRODUCED"
        receipt["observed"]["predicate"] = True
        writable(receipt_path)
        receipt_bytes = canonical.dumps(receipt)
        receipt_path.write_bytes(receipt_bytes)
        receipt_ref = receipt_path.relative_to(package).as_posix()

        # Recompute every enclosing reference, so merely checking hashes cannot detect this lie.
        changed_ballot = None
        for ballot_path in (campaign / "ballots").glob("*.json"):
            ballot = canonical.load_file(ballot_path)
            matching = [r for r in ballot["counterexample_receipts"] if r["receipt_ref"] == receipt_ref]
            if not matching:
                continue
            matching[0].update(receipt_hash=canonical.digest(receipt_bytes), status=receipt["status"])
            writable(ballot_path)
            ballot_bytes = canonical.dumps(ballot)
            ballot_path.write_bytes(ballot_bytes)
            changed_ballot = (ballot_path.relative_to(package).as_posix(), canonical.digest(ballot_bytes))
            break
        self.assertIsNotNone(changed_ballot)
        for tier in certificate["tiers"]:
            for reference in tier["ballots"]:
                if reference["ballot_ref"] == changed_ballot[0]:
                    reference["ballot_hash"] = changed_ballot[1]
        certificate_path = campaign / "consensus-certificate.json"
        writable(certificate_path)
        certificate_path.write_bytes(canonical.dumps(certificate))

        code, result, _ = run_cli("review", "tally", "--package", str(package), env=self.env)
        self.assertEqual(code, 2, result)
        self.assertIn("REVIEW_INCOMPLETE", codes(result))
        self.assertTrue(any("registered replay no longer reproduces the stored receipt" in problem
                            for item in result["summary"].values() for problem in item["problems"]), result)


if __name__ == "__main__":
    unittest.main()
