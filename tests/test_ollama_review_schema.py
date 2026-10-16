"""Opt-in raw ballot schema transport; HTTP fixtures, not live model capability scores."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import test_ollama_context_window as fixture
from test_ollama_provider import MODEL, OllamaServer
from verislop import canonical, review, review_counterexamples, schemas
from verislop.errors import InfrastructureError, UsageError
from verislop.providers import adapters, config, review_format
from verislop.providers.http import ProviderError


def ballot(verdict="ACCEPT", probe=None):
    probe = probe or {"kind": "mechanical_failure", "claim_id": "CURRENT:fixture"}
    findings = [{"id": "F1", "severity": "blocking", "obligations": ["O1"],
                 "statement": "Replay this constructed case", "counterexample": copy.deepcopy(probe)}] if verdict == "REJECT" else []
    return {"verdict": verdict, "reviewed_obligations": ["O1"], "search": {
        "method": "Constructed a concrete probe", "attempted_cases": 1, "probes": [probe],
        "conclusion": {"ACCEPT": "NO_COUNTEREXAMPLE_FOUND", "REJECT": "COUNTEREXAMPLE_CANDIDATE",
                       "ABSTAIN": "INCOMPLETE"}[verdict]}, "findings": findings,
        "limitations": [], "rationale": "Untested generated proposal"}


class RawReviewSchemaTests(unittest.TestCase):
    def test_all_verdicts_conclusions_and_probe_kinds_remain_available(self):
        for verdict in ("ACCEPT", "REJECT", "ABSTAIN"):
            value = ballot(verdict)
            self.assertEqual([], schemas.validate("review-model-response", value))
            self.assertIsNotNone(review.parse_ballot(value, ["O1"])[0])
        probes = [{"kind": "target_case", "obligation_id": "O1", "assignment": [{"dict": {
            "arbitrary_field": {"list": [{"tuple": [{"str": "ok"}, {"int": "-1"}]}]}}}]},
            {"kind": "source_violation", "obligation_id": "O1", "file": "source.py", "ast_path": "body[0]", "rule": "RULE"},
            {"kind": "missing_requirement", "start_byte": 0, "end_byte": 4, "quoted": "text"},
            {"kind": "mechanical_failure", "claim_id": "CURRENT:fixture"}]
        for probe in probes:
            with self.subTest(kind=probe["kind"]):
                self.assertEqual([], schemas.validate("review-model-response", ballot(probe=probe)))
                self.assertEqual([], review_counterexamples.validate_proposal(probe))

    def test_closed_fields_reject_notes_at_both_probe_locations_without_mutation(self):
        for location in ("search", "findings"):
            value = ballot("REJECT", {"kind": "target_case", "obligation_id": "O1", "assignment": []})
            probe = value["search"]["probes"][0] if location == "search" else value["findings"][0]["counterexample"]
            probe["note"] = "unsupported metadata"
            before = canonical.dumps(value)
            self.assertTrue(schemas.validate("review-model-response", value))
            self.assertIsNone(review.parse_ballot(value, ["O1"])[0])
            self.assertEqual(before, canonical.dumps(value))

    def test_every_count_and_verdict_is_available_but_mismatched_counts_are_rejected(self):
        for count in range(1, 9):
            for verdict in ("ACCEPT", "REJECT", "ABSTAIN"):
                value = ballot(verdict)
                value["search"]["probes"] = [{"kind": "mechanical_failure", "claim_id": f"CURRENT:case-{i}"}
                                             for i in range(count)]
                value["search"]["attempted_cases"] = count
                if value["findings"]:
                    value["findings"][0]["counterexample"] = copy.deepcopy(value["search"]["probes"][0])
                self.assertEqual([], schemas.validate("review-model-response", value))
                self.assertIsNotNone(review.parse_ballot(value, ["O1"])[0])
                value["search"]["attempted_cases"] = 1 if count != 1 else 8
                self.assertTrue(schemas.validate("review-model-response", value))
                parsed, error = review.parse_ballot(value, ["O1"])
                self.assertIsNone(parsed)
                self.assertIn(f"search.probes contains {count}", error)

    def test_count_alternatives_keep_all_probe_shapes_and_leave_distinctness_to_validator(self):
        schema = review_format.ollama_review_schema()
        alternatives = schema["properties"]["search"]["oneOf"]
        self.assertEqual(8, len(alternatives))
        for count, branch in enumerate(alternatives, 1):
            self.assertEqual(count, branch["properties"]["attempted_cases"]["const"])
            probes = branch["properties"]["probes"]
            self.assertEqual((count, count), (probes["minItems"], probes["maxItems"]))
            self.assertEqual({"$ref": "#/$defs/probe"}, probes["items"])
        value = ballot()
        value["search"]["probes"] *= 2
        value["search"]["attempted_cases"] = 2
        self.assertEqual([], schemas.validate("review-model-response", value))
        parsed, error = review.parse_ballot(value, ["O1"])
        self.assertIsNone(parsed)
        self.assertIn("duplicate constructed probes", error)

    def test_schema_is_self_contained_task_independent_and_owned_per_call(self):
        schema = review_format.ollama_review_schema()
        self.assertEqual(set(review_counterexamples.PROPOSAL_FIELDS), {
            branch["properties"]["kind"]["const"] for branch in schema["$defs"]["probe"]["oneOf"]})
        for branch in schema["$defs"]["probe"]["oneOf"]:
            kind = branch["properties"]["kind"]["const"]
            self.assertEqual(review_counterexamples.PROPOSAL_FIELDS[kind], set(branch["required"]))
            self.assertFalse(branch["additionalProperties"])
        pending = [schema]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if "$ref" in node:
                    self.assertTrue(node["$ref"].startswith("#/"))
                self.assertNotIn("default", node)
                self.assertNotIn("examples", node)
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
        schema["properties"]["verdict"]["enum"] = ["ACCEPT"]
        self.assertEqual(["ACCEPT", "REJECT", "ABSTAIN"],
                         review_format.ollama_review_schema()["properties"]["verdict"]["enum"])

    def test_structure_does_not_replace_wire_scope_or_checkpoint_validation(self):
        value = ballot(probe={"kind": "target_case", "obligation_id": "O1", "assignment": [42]})
        self.assertEqual([], schemas.validate("review-model-response", value))
        self.assertIsNone(review.parse_ballot(value, ["O1"])[0])
        value["search"]["probes"][0]["assignment"] = [{"int": "0"}]
        self.assertIsNone(review.parse_ballot(value, ["OTHER"])[0])
        policy = {"proposals": {"mechanical_failure": {}}, "mechanical_claim_ids": []}
        self.assertIsNone(review.parse_ballot(value, ["O1"], policy)[0])


class OllamaReviewSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = OllamaServer()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    setUp = fixture.OllamaContextWindowTests.setUp
    tearDown = fixture.OllamaContextWindowTests.tearDown
    broker = fixture.OllamaContextWindowTests.broker
    transcripts = fixture.OllamaContextWindowTests.transcripts
    chats = fixture.OllamaContextWindowTests.chats

    def call(self, purpose="review:release", broker=None):
        return (broker or self.broker()).call("local-critic", "slot/" + purpose,
                                             fixture.SYSTEM, fixture.USER, purpose)

    def enable(self):
        self.conf["agents"]["local-critic"]["review_response_format"] = "json_schema"

    def test_enabled_reviews_send_exact_schema_and_log_schema_hash(self):
        self.enable()
        self.conf["agents"]["local-critic"]["context_window_tokens"] = 40960
        expected = review_format.ollama_review_schema()
        for purpose in sorted(review_format.REVIEW_PURPOSES):
            self.call(purpose)
        self.assertEqual(4, len(self.chats()))
        for body, record in zip(self.chats(), self.transcripts()):
            self.assertEqual(expected, body["format"])
            self.assertEqual({"mode": "json_schema", "schema": expected,
                              "schema_sha256": canonical.digest_json(expected)}, record["response_format"])
            self.assertEqual(40960, body["options"]["num_ctx"])
            self.assertEqual(fixture.SYSTEM, body["messages"][0]["content"])
            self.assertEqual(fixture.USER, body["messages"][1]["content"])

    def test_omitted_option_preserves_existing_json_mode(self):
        self.call()
        self.assertEqual("json", self.chats()[0]["format"])
        self.assertNotIn("response_format", self.transcripts()[0])

    def test_enabled_agent_other_purposes_keep_existing_protocol_including_proofs(self):
        self.enable()
        self.conf["agents"]["local-critic"]["proof_response_format"] = "theorem_fragment"
        for purpose in ("critic", "formalize", "generate", "review:other", "review:release-extra", "prove", "prove-vscore"):
            self.call(purpose)
        self.assertEqual(["json"] * 5, [row["format"] for row in self.chats()[:5]])
        self.assertTrue(all("format" not in row for row in self.chats()[5:]))
        self.assertTrue(all("response_format" not in row for row in self.transcripts()))

    def test_invalid_configuration_fails_before_network(self):
        self.enable()
        self.assertEqual([], schemas.validate("review-config", self.conf))
        for mode in ("json", False, None, {}):
            self.conf["agents"]["local-critic"]["review_response_format"] = mode
            self.assertTrue(schemas.validate("review-config", self.conf))
            with self.assertRaises(UsageError):
                self.call()
        self.enable()
        self.conf["agents"]["local-critic"]["tool_profile"] = "candidate_writer"
        with self.assertRaises(UsageError):
            self.call()
        self.conf["agents"]["local-critic"]["tool_profile"] = "review_readonly"
        self.conf["providers"]["local"]["api_family"] = "responses"
        with self.assertRaises(UsageError):
            self.call()
        self.assertEqual([], self.server.requests)

    def test_direct_adapter_rejects_nonollama_or_conflicting_schema_mode(self):
        expected = review_format.ollama_review_schema()
        for kwargs in ({"ollama_response_schema": expected, "ollama_json_mode": False},
                       {"ollama_response_schema": "json"}, {"ollama_response_schema": []}):
            with patch.object(adapters, "request") as request, self.assertRaises(ProviderError):
                adapters.complete("ollama_chat", self.profiles["context-test"], "", MODEL,
                                  fixture.SYSTEM, fixture.USER, 128, None, **kwargs)
            request.assert_not_called()
        with patch.object(adapters, "request") as request, self.assertRaises(ProviderError):
            adapters.complete("responses", {}, "", MODEL, fixture.SYSTEM, fixture.USER, 128, None,
                              ollama_response_schema=expected)
        request.assert_not_called()

    def test_schema_transport_error_is_explicit_and_not_downgraded(self):
        self.enable()
        self.server.behavior = lambda body: {**body, "error": "schema format unavailable"}
        with self.assertRaises(InfrastructureError):
            self.call()
        self.assertEqual(1, len(self.chats()))
        self.assertEqual(review_format.ollama_review_schema(), self.chats()[0]["format"])
        record = self.transcripts()[0]
        self.assertIsNotNone(record["error"])
        self.assertEqual(self.chats()[0]["format"], record["response_format"]["schema"])
        self.assertEqual(canonical.digest_json(record["response_format"]["schema"]),
                         record["response_format"]["schema_sha256"])

    def test_schema_retained_on_catalog_failure_and_configuration_mutation(self):
        self.enable()
        def change():
            self.conf["agents"]["local-critic"].pop("review_response_format")
            self.server.catalog[0]["digest"] = "b" * 64
        self.server.after_chat = change
        with self.assertRaises(InfrastructureError):
            self.call()
        self.assertEqual(self.chats()[0]["format"], self.transcripts()[0]["response_format"]["schema"])

    def test_service_ignoring_constraints_cannot_bypass_existing_ballot_parser(self):
        self.enable()
        value = ballot(probe={"kind": "target_case", "obligation_id": "O1", "assignment": [], "note": "still invalid"})
        raw = json.dumps(value)
        self.server.behavior = lambda body: {**body, "message": {"role": "assistant", "content": raw}}
        comp = self.call()
        self.assertEqual(raw, comp.text)
        self.assertEqual(raw, self.transcripts()[0]["response"])
        self.assertIsNone(review.parse_ballot(json.loads(comp.text), ["O1"])[0])


if __name__ == "__main__":
    unittest.main()
