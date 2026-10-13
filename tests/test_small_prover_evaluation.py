"""Small-prover evaluation configuration and evidence gates; no inference or Lean mocks counted as measurements."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from synthetic_dataset.tools import evaluate_small_prover as evaluation
from verislop import agent_memory, canonical, leanbridge, schemas
from verislop.errors import Diagnostic, UsageError
from verislop.providers.adapters import Completion
from verislop.stage import StageResult


class SmallProverEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def args(self, **overrides):
        values = {"config": None, "model": "test-prover:4b", "model_digest": "a" * 64,
                  "context_window": 32768, "max_output_tokens": 8192,
                  "endpoint": "http://127.0.0.1:11435", "stop_file": None}
        return SimpleNamespace(**{**values, **overrides})

    def configure(self, args):
        with patch.object(evaluation.provider_config, "load_user_profiles", return_value={}):
            path = evaluation.configuration(self.root, args)
        return canonical.load_file(path)

    def test_catalog_digest_pin_has_required_schema_and_exact_model(self):
        conf = self.configure(self.args())
        agent = conf["agents"][conf["roles"]["prover"]]
        self.assertEqual({"mode": "pinned", "resolved_model": "test-prover:4b", "model_digest_sha256": "a" * 64}, agent["model_identity"])
        self.assertEqual([], schemas.validate("review-config", conf))
        self.assertIsNone(conf["providers"][agent["provider"]]["request_timeout_seconds"])

    def test_environment_model_is_resolved_and_frozen_before_inference(self):
        with patch.dict(os.environ, {"SMALL_PROVER_TEST_MODEL": "chosen-local:4b"}):
            conf = self.configure(self.args(model="env:SMALL_PROVER_TEST_MODEL"))
        agent = conf["agents"][conf["roles"]["prover"]]
        self.assertEqual("chosen-local:4b", agent["model_ref"])
        self.assertEqual("chosen-local:4b", agent["model_identity"]["resolved_model"])

    def test_unset_environment_model_exposes_exact_configuration_path(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(UsageError) as caught:
            self.configure(self.args(model="env:SMALL_PROVER_TEST_UNSET"))
        self.assertEqual("$.agents.local-author.model_ref", caught.exception.diagnostics[0].details["path"])

    def test_invalid_catalog_digest_reports_schema_field_instead_of_generic_error(self):
        with self.assertRaises(UsageError) as caught:
            self.configure(self.args(model_digest="sha256:" + "a" * 64))
        self.assertTrue(any("model_digest_sha256" in d.details.get("path", "") for d in caught.exception.diagnostics))
        self.assertTrue(all(d.details.get("schema") == "review-config" for d in caught.exception.diagnostics))

    def test_direct_arm_strips_both_optional_router_keys(self):
        source = canonical.load_file(evaluation.ROOT / "examples/ollama-review-config.json")
        source.update(proof_search={"enabled": True}, proof_routing={"enabled": True})
        with patch.object(evaluation.provider_config, "load", return_value=source):
            conf = self.configure(self.args(config=Path("unused-test-config.json")))
        self.assertNotIn("proof_search", conf)
        self.assertNotIn("proof_routing", conf)

    def test_fragment_mode_is_an_explicit_schema_valid_agent_setting(self):
        conf = self.configure(self.args(proof_response_format="theorem_fragment"))
        agent = conf["agents"][conf["roles"]["prover"]]
        self.assertEqual("theorem_fragment", agent["proof_response_format"])
        self.assertEqual([], schemas.validate("review-config", conf))

    def test_frozen_source_and_input_mutations_are_detected(self):
        source = self.root / "verislop/source.py"
        source.parent.mkdir(); source.write_bytes(b"original source")
        cohort = self.root / "cohort.json"; cohort.write_bytes(b"original input")
        freeze = {"source_hashes": {"verislop/source.py": canonical.digest_file(source)},
                  "output": str(self.root), "run_inputs": {"cohort.json": canonical.digest_file(cohort)}}
        with patch.object(evaluation, "ROOT", self.root):
            evaluation.unchanged(freeze)
            source.write_bytes(b"changed source")
            with self.assertRaisesRegex(RuntimeError, "source changed after freeze"):
                evaluation.unchanged(freeze)
            source.write_bytes(b"original source"); cohort.write_bytes(b"changed input")
            with self.assertRaisesRegex(RuntimeError, "input changed after freeze"):
                evaluation.unchanged(freeze)

    def test_usage_observer_delegates_and_preserves_completion(self):
        completion = Completion("actual delegated response", "model", "model", "request", 17, 23)
        calls = []
        def provider(broker, agent, instance, system, user, purpose):
            calls.append((agent, instance, system, user, purpose))
            return completion
        fake = SimpleNamespace(transcripts=self.root / "transcripts")
        freeze = {"source_hashes": {}, "run_inputs": {}, "output": str(self.root)}
        with patch.object(evaluation.Broker, "call", new=provider):
            with evaluation.usage_capture(self.root, self.args(), freeze) as usage:
                returned = evaluation.Broker.call(fake, "agent", "instance", "system", "user", "prove")
            self.assertIs(provider, evaluation.Broker.call)
        self.assertIs(completion, returned)
        self.assertEqual(1, len(calls))
        self.assertEqual((17, 23), (usage[0]["input_tokens"], usage[0]["output_tokens"]))

    def test_completed_candidate_and_mock_stage_passes_cannot_bypass_statement_identity(self):
        pkg = SimpleNamespace(run_id="test-no-real-verification-claim", root=self.root,
                              path=lambda kind: self.root / kind)
        frozen = {"expected_statement_hashes": {"O1": "sha256:" + "a" * 64}, "required_ids": ["O1"]}
        ir = {"obligations": {"O1": {"formal": {"statement_hash": "sha256:" + "b" * 64}}}}
        sink = SimpleNamespace(close=lambda: None)
        with patch.object(evaluation, "EventSink", return_value=sink), \
             patch.object(evaluation.prove, "run", return_value=StageResult("prove", "PASS", "unit test", summary={"complete": True})), \
             patch.object(evaluation.accept, "run", return_value=StageResult("accept", "PASS", "unit test")), \
             patch.object(evaluation.export, "run", return_value=StageResult("export", "PASS", "unit test")), \
             patch.object(evaluation.export, "verified_ir", return_value=(ir, "unused", {"gate": "unused"}, [])):
            result = evaluation.evaluated_arm(self.root, pkg, frozen, self.args(), Path("unused"), portfolio=True)
        self.assertFalse(result["accepted"])
        self.assertEqual("EVALUATION_FAILURE", result["status"])
        self.assertIn("statement hash changed", result["exception"]["message"])

    def tokenizer(self, count):
        return SimpleNamespace(get_chat_template=lambda: "frozen test template", apply_chat_template=lambda _messages, *, tokenize, **_options:
                               list(range(count)) if tokenize else "exact locally rendered prompt")

    def test_tokenizer_guard_counts_complete_messages_and_output_budget(self):
        seen = []
        def render(messages, *, tokenize, add_generation_prompt, enable_thinking, **options):
            seen.append((messages, add_generation_prompt, enable_thinking))
            if tokenize:
                self.assertIs(False, options.get("return_dict"))
            return [1] * 7 if tokenize else "rendered exact prompt"
        tokenizer = SimpleNamespace(get_chat_template=lambda: "template", apply_chat_template=render)
        broker = SimpleNamespace(r=SimpleNamespace(agent=lambda _: {"context_window_tokens": 12, "max_output_tokens": 5}))
        preflight = evaluation.prompt_preflight(tokenizer, broker, "agent", "system bytes", "user bytes")
        self.assertEqual(12, preflight["total_budget_tokens"])
        self.assertTrue(preflight["fits"])
        self.assertEqual([{"role": "system", "content": "system bytes"}, {"role": "user", "content": "user bytes"}], seen[0][0])
        self.assertEqual((True, False), seen[0][1:])

    def test_transformers_mapping_return_counts_input_ids_not_fields(self):
        tokenizer = SimpleNamespace(get_chat_template=lambda: "template", apply_chat_template=lambda _messages, *, tokenize, **_options:
            {"input_ids": [[1, 2, 3, 4, 5]], "attention_mask": [[1] * 5]} if tokenize else "rendered prompt")
        broker = SimpleNamespace(r=SimpleNamespace(agent=lambda _: {"context_window_tokens": 12, "max_output_tokens": 5}))
        preflight = evaluation.prompt_preflight(tokenizer, broker, "agent", "system", "user")
        self.assertEqual(5, preflight["input_tokens"])
        self.assertEqual(10, preflight["total_budget_tokens"])

    def test_oversize_tokenizer_budget_blocks_dispatch_without_trimming(self):
        broker = SimpleNamespace(r=SimpleNamespace(agent=lambda _: {"context_window_tokens": 10, "max_output_tokens": 5}),
                                 transcripts=self.root / "transcripts")
        freeze = {"source_hashes": {}, "run_inputs": {}, "output": str(self.root)}
        with patch.object(evaluation.Broker, "call") as provider:
            with evaluation.usage_capture(self.root, self.args(), freeze, self.tokenizer(6)) as usage:
                with self.assertRaises(UsageError) as caught:
                    evaluation.Broker.call(broker, "agent", "instance", "system", "user", "prove")
        provider.assert_not_called()
        self.assertEqual("context_budget_exceeded", caught.exception.diagnostics[0].details["kind"])
        self.assertFalse(usage[0]["completed"])

    def test_substantial_native_token_difference_is_context_infrastructure(self):
        broker = SimpleNamespace(r=SimpleNamespace(agent=lambda _: {"context_window_tokens": 1000, "max_output_tokens": 5}),
                                 transcripts=self.root / "transcripts")
        freeze = {"source_hashes": {}, "run_inputs": {}, "output": str(self.root)}
        completion = Completion("unit-test response", "model", "model", None, 500, 5)
        with patch.object(evaluation.Broker, "call", return_value=completion) as provider:
            with evaluation.usage_capture(self.root, self.args(), freeze, self.tokenizer(20)) as usage:
                with self.assertRaises(UsageError) as caught:
                    evaluation.Broker.call(broker, "agent", "instance", "system", "user", "prove")
        provider.assert_called_once()
        self.assertTrue(usage[0]["completed"])
        self.assertEqual("native_prompt_context_mismatch", caught.exception.diagnostics[0].details["kind"])

    def test_new_measurement_requires_identical_frozen_contracts(self):
        prior = self.root / "prior"; prior.mkdir()
        current = self.root / "current"; current.mkdir()
        cohort = [{"id": "nat", "request": "public proof-free cohort"}]
        evaluation.write(prior / "cohort.json", cohort); evaluation.write(current / "cohort.json", cohort)
        info = {"challenge_hash": "sha256:" + "a" * 64, "required_ids": ["O1"], "expected_statement_hashes": {"O1": "sha256:" + "b" * 64}}
        evaluation.write(prior / "summary.json", {"cases": {"nat": {"setup": {"model": info}}}})
        bindings = evaluation.compare_frozen_contracts(current, prior / "summary.json", {"nat": {"model": (None, info)}})
        self.assertIn(str((prior / "summary.json").resolve()), bindings)
        changed = {**info, "challenge_hash": "sha256:" + "c" * 64}
        with self.assertRaisesRegex(RuntimeError, "frozen contract changed"):
            evaluation.compare_frozen_contracts(current, prior / "summary.json", {"nat": {"model": (None, changed)}})

    def test_failure_taxonomy_separates_scaffold_lean_and_context_failures(self):
        failure = {"status": "PROOF_UNRESOLVED", "accepted": False, "attempt_evidence": [
            {"initial_scaffold_preserved": False, "ok": False, "errors": ["unknown tactic 'ring_nf'"]}]}
        self.assertEqual(["LEAN_ELABORATION_OR_TACTIC_FAILURE", "LEAN_UNAVAILABLE_TACTIC", "MODEL_SOURCE_SCAFFOLD_MISMATCH"], evaluation.failure_taxonomy(failure))
        failure = {"accepted": False, "exception": {"diagnostics": [{"code": "PROVIDER_FAILURE", "details": {"kind": "native_prompt_context_mismatch"}}]}}
        self.assertEqual(["CONTEXT_OR_TOKENIZER_INFRASTRUCTURE"], evaluation.failure_taxonomy(failure))

    def test_machine_flagged_fragment_rejection_is_never_lean_elaboration(self):
        failure = {"status": "PROOF_UNRESOLVED", "accepted": False, "attempt_evidence": [
            {"protocol_rejected": True, "initial_scaffold_preserved": False, "ok": False,
             "errors": ["frozen theorem header differs"]}],
            "proof_search": {"summary": {"errors": ["frozen theorem header differs"]}}}
        self.assertEqual(["MODEL_RESPONSE_ENVELOPE_OR_FRAGMENT_REJECTED"], evaluation.failure_taxonomy(failure))

    def test_legacy_fragment_prefix_is_protocol_rejection_with_separate_syntax_label(self):
        error = "fragment protocol: proof body is not exactly one Lean term: unexpected end of input"
        failure = {"status": "PROOF_UNRESOLVED", "accepted": False, "attempt_evidence": [
            {"initial_scaffold_preserved": False, "ok": False, "errors": [error]}],
            "proof_search": {"summary": {"errors": [error]}}}
        self.assertEqual(["FRAGMENT_TERM_SYNTAX_REJECTION", "MODEL_RESPONSE_ENVELOPE_OR_FRAGMENT_REJECTED"], evaluation.failure_taxonomy(failure))

    def test_mixed_protocol_and_actual_lean_failures_keep_both_categories(self):
        failure = {"status": "PROOF_UNRESOLVED", "accepted": False, "attempt_evidence": [
            {"protocol_rejected": True, "ok": False, "errors": ["frozen header mismatch"]},
            {"protocol_rejected": False, "initial_scaffold_preserved": True, "ok": False,
             "errors": ["unknown tactic 'ring_nf'"]}]}
        self.assertEqual(["LEAN_ELABORATION_OR_TACTIC_FAILURE", "LEAN_UNAVAILABLE_TACTIC", "MODEL_RESPONSE_ENVELOPE_OR_FRAGMENT_REJECTED"], evaluation.failure_taxonomy(failure))

    def test_bridge_uses_production_fragment_protocol_and_retains_baseline_after_rejection(self):
        """Only protocol/control-flow evidence: every proposed proof remains invalid."""
        pkg = SimpleNamespace(run_id="unit-test-bridge-protocol", root=self.root,
                              path=lambda kind: self.root / kind)
        evaluation.write(pkg.path("accepted") / "acceptance.json",
                         {"artifacts": {"profile": {"path": "profile.json"}}})
        evaluation.write(self.root / "profile.json", {})
        info = {"readable_candidate_artifacts": {}, "required_obligations": ["O1"],
                "readable_source_view": {}, "readable_selection": {}, "proposition_hash": "frozen-proposition"}
        workflow = {"parameters": {}, "accepted_reference": {}, "accepted_packages": {},
                    "accepted_profile": {}, "lean_toolchain": leanbridge.DEFAULT_TOOLCHAIN}
        conf = {"roles": {"prover": "small"},
                "agents": {"small": {"proof_response_format": "theorem_fragment"}}}
        responses = ["theorem edge : True := by exact missing_proof_1",
                     "theorem edge : VeriSlopBridgeGoal.EdgeProp := by exact missing_proof_2",
                     "theorem edge : VeriSlopBridgeGoal.EdgeProp := by exact missing_proof_3"]
        calls, checked = [], []
        def completion(broker, package, agent, instance, system, user, purpose):
            calls.append((system, user, purpose))
            return Completion(responses[len(calls) - 1], "model", "model", None, 8, 6)
        def preview(package, source, relation, proof=None, **kwargs):
            if proof is not None:
                checked.append(proof)
                raise evaluation.checker.EdgeFailure([Diagnostic("CANDIDATE_BUILD_FAILURE", "unknown missing_proof")])
            return SimpleNamespace(text="frozen goal", refinement_symbols=[]), None, info
        freeze = {"source_hashes": {}, "run_inputs": {}, "output": str(self.root)}
        directory = self.root / "bridge"
        with patch.object(evaluation, "EventSink", return_value=SimpleNamespace(close=lambda: None)), \
             patch.object(evaluation.checker, "preview", side_effect=preview), \
             patch.object(evaluation.export, "verified_ir", return_value=({}, None, None, [])), \
             patch.object(evaluation.agents, "_vscore_context", return_value=workflow), \
             patch.object(evaluation.agents, "_broker", return_value=(None, conf)), \
             patch.object(evaluation.agents, "recorded_call", side_effect=completion), \
             patch.object(evaluation.target, "library_sources", return_value={}), \
             patch.object(evaluation.target, "proof_support_catalog", return_value={}), \
             patch.object(agent_memory, "capture_context"):
            result = evaluation.bridge_arm(directory, pkg, {"bridge_program": {}}, Path("unused"), self.args(), freeze)
        self.assertEqual("PROOF_UNRESOLVED", result["status"])
        self.assertFalse(result["accepted"])
        self.assertEqual([True, False, False], [attempt["protocol_rejected"] for attempt in result["attempts"]])
        self.assertEqual(["prove-vscore"] * 3, [call[2] for call in calls])
        self.assertTrue(all(call[0] == evaluation.agents.FRAGMENT_PROVER_SYSTEM for call in calls))
        self.assertTrue(all("EXACT FROZEN THEOREM HEADERS" in call[1] for call in calls))
        self.assertIn("by sorry", calls[1][1])
        self.assertNotIn("theorem edge : True", calls[1][1])
        self.assertIn("unknown missing_proof", calls[2][1])
        self.assertIn("by exact missing_proof_2", calls[2][1])
        self.assertEqual(2, len(checked))
        self.assertTrue(all(proof.startswith(b"import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\n") for proof in checked))
        self.assertTrue(all(proof.endswith(b"end VeriSlopBridgeProof\n") for proof in checked))
        for number, response in enumerate(responses, 1):
            self.assertEqual(response, (directory / f"attempt-{number}/response.txt").read_text())
        self.assertFalse((directory / "attempt-1/Proof.lean").exists())
        self.assertEqual(checked[0], (directory / "attempt-2/Proof.lean").read_bytes())


if __name__ == "__main__":
    unittest.main()
