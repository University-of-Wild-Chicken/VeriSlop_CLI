from pathlib import Path
from types import SimpleNamespace
import os
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from verislop import canonical
from verislop.errors import Diagnostic, InfrastructureError, UsageError
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker
from synthetic_dataset.tools import run_local_hybrid as hybrid
from synthetic_dataset.tools import sol_data_pipeline_worker as sol_worker


class HybridTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "trial"
        self.out.mkdir()
        self.task = hybrid.TASKS[0]
        self.protocol = {"tasks": [self.task], "native_calls_per_task": 2, "sol_calls_per_task": 2,
                         "pyth_agent": "pythagoras", "relay_mode": "file",
                         "sol_routes": {"sol": ["prove", "prove-vscore"]}}
        hybrid.once(self.out / "protocol.json", self.protocol)
        self.verify = patch.object(hybrid, "verify_inputs", return_value=self.protocol)
        self.verify.start()
        self.addCleanup(self.verify.stop)

    def transport(self):
        return hybrid.HybridTransport(self.out, self.task, self.protocol, object())

    def broker(self, model="local-qwen"):
        broker = Mock()
        broker.model_for.return_value = model
        return broker

    def completion(self, model="local-qwen"):
        return Completion("exact response", model, model, "request-1", 21, 7)

    def test_strict_invocation_has_no_candidate_injection_or_wall_timeout(self):
        argv = hybrid.cli_argv(self.out, self.task)
        self.assertEqual("TESTED", argv[argv.index("--require-state") + 1])
        self.assertEqual("0", argv[argv.index("--budget-seconds") + 1])
        self.assertEqual("2", argv[argv.index("--repair-rounds") + 1])
        self.assertIn("--require-tests", argv)
        self.assertFalse(any("candidate" in item for item in argv))

    def test_tier2_project_invocation_keeps_strict_restricted_source_boundary(self):
        argv = hybrid.cli_argv(self.out, hybrid.PROJECT_TASKS[0], {"trial_mode": "tier2-project"})
        for key, value in (("--tier", "2"), ("--target", "vscore"), ("--backend-version", "0.3"),
                           ("--endpoint", "restricted_source"), ("--require-state", "END_TO_END_VERIFIED"),
                           ("--budget-seconds", "0"), ("--policy", "strict")):
            self.assertEqual(value, argv[argv.index(key) + 1])
        self.assertIn("--no-tests", argv)
        self.assertNotIn("--require-tests", argv)
        self.assertFalse(any("candidate" in item for item in argv))
        with self.assertRaisesRegex(ValueError, "task is outside"):
            hybrid.cli_argv(self.out, self.task, {"trial_mode": "tier2-project"})

    def test_partial_run_never_resets_logical_budgets(self):
        hybrid.once(self.out / "run-started.json", {"interrupted": True})
        with self.assertRaises(FileExistsError), patch.object(hybrid.cli, "main") as run:
            hybrid.run(self.out)
        run.assert_not_called()

    def test_local_calls_delegate_exact_prompts_and_keep_usage(self):
        transport, broker = self.transport(), self.broker()
        completion = self.completion()
        original = Mock(return_value=completion)
        actual = transport.call(original, broker, "qwen", "i/1", "SYSTEM", "USER", "formalize")
        self.assertIs(actual, completion)
        original.assert_called_once_with(broker, "qwen", "i/1", "SYSTEM", "USER", "formalize")
        self.assertEqual(21, transport.rows[0]["input_tokens"])
        self.assertEqual(7, transport.rows[0]["output_tokens"])
        self.assertEqual(1, transport.native_used)

    def test_native_budget_is_shared_across_roles(self):
        transport, broker = self.transport(), self.broker()
        original = Mock(return_value=self.completion())
        for role in ("qwen-author", "qwen-reviewer"):
            transport.call(original, broker, role, "i/1", "S", "U", "critic")
        with self.assertRaisesRegex(InfrastructureError, "budget exhausted"):
            transport.call(original, broker, "qwen-proof", "i/2", "S", "U", "prove")
        self.assertEqual(2, original.call_count)
        self.assertFalse(transport.rows[-1]["call_dispatched"])

    def test_pyth_context_rejection_never_dispatches_and_is_explicit(self):
        transport, broker = self.transport(), self.broker("pyth")
        rejected = UsageError("too large", [Diagnostic("BUDGET_EXHAUSTED", "large", details={
            "kind": "context_budget_exceeded", "input_tokens": 16000})])
        original = Mock()
        with patch.object(hybrid, "prompt_preflight", side_effect=rejected):
            with self.assertRaises(InfrastructureError) as caught:
                transport.call(original, broker, "pythagoras", "proof/1", "S", "U", "prove")
        original.assert_not_called()
        self.assertEqual("context_budget_exceeded", caught.exception.diagnostics[0].details["kind"])
        self.assertFalse(caught.exception.diagnostics[0].details["call_dispatched"])
        self.assertEqual(0, transport.native_used)

    def test_pyth_native_token_disagreement_is_binding_failure(self):
        transport, broker = self.transport(), self.broker("pyth")
        with patch.object(hybrid, "prompt_preflight", return_value={"input_tokens": 400,
                "total_budget_tokens": 8592, "context_window_tokens": 16384, "declared_max_output_tokens": 8192}):
            with self.assertRaises(InfrastructureError) as caught:
                transport.call(Mock(return_value=self.completion()), broker, "pythagoras", "proof/1", "S", "U", "prove")
        self.assertTrue(caught.exception.diagnostics[0].details["binding_failure"])
        self.assertEqual(1, transport.native_used)

    def test_qwen_preflight_checks_author_and_reviewer_without_changing_prompt(self):
        self.protocol.update(qwen_tokenizer="frozen-qwen", qwen_agents=["qwen-author", "qwen-reviewer"],
                             prompt_capacity_safety_margin=128)
        qwen_tokenizer = object()
        transport = hybrid.HybridTransport(self.out, self.task, self.protocol, object(), qwen_tokenizer)
        broker, original = self.broker(), Mock(return_value=self.completion())
        with patch.object(hybrid, "prompt_preflight", return_value={"input_tokens": 21,
                "total_budget_tokens": 8213, "context_window_tokens": 32768,
                "declared_max_output_tokens": 8192}) as preflight:
            for agent in self.protocol["qwen_agents"]:
                transport.call(original, broker, agent, "i/1", "S", "U", "critic")
        self.assertEqual(2, preflight.call_count)
        for call in preflight.call_args_list:
            self.assertIs(qwen_tokenizer, call.args[0])
        self.assertEqual([0, 0], [r["native_input_token_difference"] for r in transport.rows])

    def test_serialization_margin_overflow_does_not_dispatch(self):
        self.protocol["prompt_capacity_safety_margin"] = 128
        transport, original = self.transport(), Mock()
        with patch.object(hybrid, "prompt_preflight", return_value={"input_tokens": 8190,
                "total_budget_tokens": 16382, "context_window_tokens": 16384,
                "declared_max_output_tokens": 8192}):
            with self.assertRaises(InfrastructureError) as caught:
                transport.call(original, self.broker("pyth"), "pythagoras", "i", "S", "U", "prove")
        original.assert_not_called()
        self.assertEqual("context_budget_exceeded", caught.exception.diagnostics[0].details["kind"])
        self.assertFalse(caught.exception.diagnostics[0].details["call_dispatched"])

    def test_frozen_qwen_tokenizer_cannot_be_omitted_at_runtime(self):
        self.protocol["qwen_tokenizer"] = "frozen-qwen"
        with self.assertRaisesRegex(ValueError, "frozen Qwen tokenizer"):
            self.transport()

    def test_only_declared_sol_agent_and_purpose_use_mailbox(self):
        transport, broker = self.transport(), self.broker(hybrid.MODEL)
        original = Mock()
        transport.mailbox.call = Mock(return_value=self.completion(hybrid.MODEL))
        transport.call(original, broker, "sol", "proof/1", "S", "U", "prove")
        original.assert_not_called()
        transport.mailbox.call.assert_called_once_with(broker, "sol", "proof/1", "S", "U", "prove")
        self.assertEqual(0, transport.native_used)
        for agent, purpose in (("sol", "review"), ("sol", "critic"), ("sol", "generate"), ("undeclared-sol", "prove")):
            with self.subTest(agent=agent, purpose=purpose), self.assertRaisesRegex(InfrastructureError, "declared fallback route"):
                transport.call(original, broker, agent, "review/1", "S", "U", purpose)
        self.assertEqual(1, transport.mailbox.call.call_count)

    def test_declared_critic_fallback_uses_exact_agent_and_prompt(self):
        self.protocol["sol_routes"]["sol-critic"] = ["critic"]
        transport, broker = self.transport(), self.broker(hybrid.MODEL)
        original = Mock()
        transport.mailbox.call = Mock(return_value=self.completion(hybrid.MODEL))
        instance = "critic/formalize/1/R0/group-0/qwen-reviewer/1/fallback/sol-critic"
        transport.call(original, broker, "sol-critic", instance, "EXACT SYSTEM", "EXACT USER", "critic")
        original.assert_not_called()
        transport.mailbox.call.assert_called_once_with(broker, "sol-critic", instance, "EXACT SYSTEM", "EXACT USER", "critic")
        self.assertEqual("sol-critic", transport.rows[0]["agent"])
        self.assertEqual(instance, transport.rows[0]["instance"])
        self.assertEqual(0, transport.native_used)
        with self.assertRaisesRegex(InfrastructureError, "declared fallback route"):
            transport.call(original, broker, "sol-critic", "proof/1", "S", "U", "prove")
        self.assertEqual(1, transport.mailbox.call.call_count)

    def test_credentials_and_broker_are_restored_after_failure(self):
        original = Broker.call
        with patch.dict(os.environ, {"VERISLOP_CONFIG_HOME": "original-home", "VERISLOP_COLLABORATION_UNUSED": "original-value"}):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                with hybrid.transport_environment(self.out, self.transport()):
                    self.assertEqual(str(self.out / "provider-home"), os.environ["VERISLOP_CONFIG_HOME"])
                    self.assertEqual(hybrid.SIMULATION_CREDENTIAL, os.environ["VERISLOP_COLLABORATION_UNUSED"])
                    raise RuntimeError("boom")
            self.assertEqual("original-home", os.environ["VERISLOP_CONFIG_HOME"])
            self.assertEqual("original-value", os.environ["VERISLOP_COLLABORATION_UNUSED"])
        self.assertIs(original, Broker.call)

    def make_request(self, number=1):
        hybrid.atomic_json(self.out / "active-task.json", {"task": self.task, "phase": "generation"})
        rid = f"{number:04d}"
        path = self.out / "tasks" / self.task / "mailbox" / f"request-{rid}.json"
        hybrid.once(path, {"request_id": rid, "transport": "collaboration", "requested_model": hybrid.MODEL,
                           "system": "Exact SYSTEM", "user": "Exact USER"})
        return hybrid.pending(self.out)

    def envelope(self, current, agent="/root/fresh_sol_1"):
        return {k: current[k] for k in ("task", "protocol_sha256", "carrier_path", "carrier_sha256",
            "spawn_message_sha256", "model_override", "fork_turns", "request_id", "request_sha256")} | {
            "model_identity_attested": False, "transport": "collaboration", "requested_model": hybrid.MODEL,
            "agent_task_id": agent, "text": "EXACT FINAL\n"}

    def test_carrier_contains_exact_request_and_response_is_verbatim(self):
        current = self.make_request()
        carrier = canonical.load_file(Path(current["carrier_path"]))
        self.assertEqual("Exact SYSTEM", carrier["system"])
        self.assertEqual("Exact USER", carrier["user"])
        result = hybrid.respond(self.out, self.envelope(current))
        self.assertEqual("EXACT FINAL\n", canonical.load_file(Path(result["published"]))["text"])
        self.assertIsNone(hybrid.pending(self.out))

    def test_carrier_mutation_and_wrong_response_binding_are_rejected(self):
        current = self.make_request()
        wrong = self.envelope(current) | {"carrier_sha256": "sha256:bad"}
        with self.assertRaisesRegex(ValueError, "binding"):
            hybrid.respond(self.out, wrong)
        path = Path(current["carrier_path"])
        path.chmod(0o600)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "carrier differs"):
            hybrid.pending(self.out)

    def test_each_sol_call_requires_fresh_agent(self):
        hybrid.respond(self.out, self.envelope(self.make_request()))
        current = self.make_request(2)
        with self.assertRaisesRegex(ValueError, "fresh agent"):
            hybrid.respond(self.out, self.envelope(current))

    def test_empty_final_retained_as_transport_error(self):
        current = self.make_request()
        result = hybrid.respond(self.out, self.envelope(current) | {"text": ""})
        envelope = canonical.load_file(Path(result["published"]))
        self.assertEqual("", envelope["text"])
        self.assertEqual(hybrid.EMPTY_FINAL_ERROR, envelope["transport_error"])

    def test_cli_cancel_without_json_is_stopped_and_skips_checker_and_remaining_tasks(self):
        self.protocol.update(tasks=list(hybrid.TASKS), tokenizer="unused-test-tokenizer", independent_check=True)
        tokenizer_module = SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=Mock(return_value=object())))
        with patch.dict(sys.modules, {"transformers": tokenizer_module}), patch.object(hybrid.cli, "main", return_value=130) as native, patch.object(hybrid.subprocess, "run") as checker:
            summary = hybrid.run(self.out)
        self.assertEqual("EXTERNALLY_STOPPED", summary["status"])
        self.assertEqual(1, native.call_count)
        checker.assert_not_called()
        self.assertEqual(0, summary["native_passes"])
        self.assertEqual(1, len(summary["results"]))
        self.assertEqual(130, summary["results"][0]["exit_code"])
        self.assertIsNone(summary["results"][0]["native_result"])
        self.assertEqual("stopped", canonical.load_file(self.out / "active-task.json")["phase"])
        self.assertEqual("EXTERNALLY_STOPPED", canonical.load_file(self.out / "tasks" / self.task / "result.json")["status"])

    def test_run_command_preserves_interrupted_exit_code(self):
        with patch.object(hybrid, "run", return_value={"status": "EXTERNALLY_STOPPED"}), patch("builtins.print"):
            self.assertEqual(130, hybrid.main(["run", "--out", str(self.out)]))


class HybridFreezeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.conf = canonical.load_file(hybrid.ROOT / "examples/local-hybrid-config.json")
        self.profiles = canonical.load_file(hybrid.ROOT / "examples/aix-ollama-endpoint-profiles.json")
        simulation = sol_worker.configuration()
        self.conf["providers"] = {"local": self.conf["providers"]["local"],
                                  "simulation": simulation["providers"]["simulation"]}
        self.profiles["profiles"].update(sol_worker.endpoint_profiles()["profiles"])
        for name, agent in self.conf["agents"].items():
            if agent["model_ref"] == hybrid.MODEL:
                agent["provider"] = "simulation"
                continue
            model = "pyth-local" if name == "pythagoras" else "qwen-local"
            agent["model_ref"] = model
            agent["model_identity"] = {"mode": "pinned", "resolved_model": model,
                                       "model_digest_sha256": "a" * 64}
        self.config = self.root / "config.json"
        self.profile = self.root / "profiles.json"
        hybrid.once(self.config, self.conf)
        hybrid.once(self.profile, self.profiles)

    def test_valid_configuration_and_route_bypass_rejection(self):
        hybrid.validate_configuration(self.conf, self.profiles, "pythagoras")
        self.conf["proof_routing"]["initial_agent"] = "qwen-proof-refiner"
        with self.assertRaisesRegex(ValueError, "Pythagoras 3"):
            hybrid.validate_configuration(self.conf, self.profiles, "pythagoras")

    def test_tier2_mode_requires_exact_tier_and_endpoint(self):
        with self.assertRaisesRegex(ValueError, "Tier 2 restricted_source"):
            hybrid.validate_configuration(self.conf, self.profiles, "pythagoras", trial_mode="tier2-project")
        self.conf.update(bridge_tier=2, endpoint="restricted_source")
        hybrid.validate_configuration(self.conf, self.profiles, "pythagoras", trial_mode="tier2-project")
        with self.assertRaisesRegex(ValueError, "Tier 0 test_campaign"):
            hybrid.validate_configuration(self.conf, self.profiles, "pythagoras")

    def test_tier2_prepare_freezes_project_spec_and_grammar_and_excludes_python_checker(self):
        self.conf.update(bridge_tier=2, endpoint="restricted_source")
        self.config.write_bytes(canonical.dumps(self.conf))
        out = self.root / "trial"
        def fake_tokenizer(args, directory):
            hybrid.once(directory / "prompt-tokenizer-freeze.json", {"test": True})
            return object(), {}
        with patch.object(hybrid, "load_prompt_tokenizer", side_effect=fake_tokenizer):
            protocol = hybrid.prepare(out, self.config, self.profile, self.root, trial_mode="tier2-project")
        self.assertEqual([hybrid.PROJECT_TASKS[0]], protocol["tasks"])
        self.assertEqual("END_TO_END_VERIFIED", protocol["required_state"])
        self.assertEqual("0.3", protocol["backend_version"])
        self.assertIn("docs/bootstrap-local-projects.md", protocol["source_hashes"])
        self.assertTrue(any(path.startswith("grammar/") for path in protocol["source_hashes"]))
        prompt = f"examples/project-bootstrap/{hybrid.PROJECT_TASKS[0]}.txt"
        self.assertIn(prompt, protocol["source_hashes"])
        self.assertEqual((hybrid.ROOT / prompt).read_bytes(), (out / "prompts" / f"{hybrid.PROJECT_TASKS[0]}.txt").read_bytes())
        self.assertEqual(protocol, hybrid.verify_inputs(out))
        for kwargs in ({"tasks": [hybrid.TASKS[0]]}, {"independent_check": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                hybrid.prepare(self.root / "invalid", self.config, self.profile, self.root,
                               trial_mode="tier2-project", **kwargs)
        with self.assertRaises(ValueError):
            hybrid.prepare(self.root / "invalid", self.config, self.profile, self.root, trial_mode="tier9")

    def test_modified_project_prompt_blocks_frozen_trial(self):
        self.conf.update(bridge_tier=2, endpoint="restricted_source")
        self.config.write_bytes(canonical.dumps(self.conf))
        out = self.root / "trial"
        def fake_tokenizer(args, directory):
            hybrid.once(directory / "prompt-tokenizer-freeze.json", {"test": True})
            return object(), {}
        with patch.object(hybrid, "load_prompt_tokenizer", side_effect=fake_tokenizer):
            hybrid.prepare(out, self.config, self.profile, self.root, trial_mode="tier2-project")
        prompt = out / "prompts" / f"{hybrid.PROJECT_TASKS[0]}.txt"
        prompt.chmod(0o600)
        prompt.write_text("weaker prompt")
        with self.assertRaisesRegex(ValueError, "trial input changed"):
            hybrid.verify_inputs(out)

    def test_declared_critic_route_requires_sol_but_never_changes_review_membership(self):
        self.conf["agents"]["sol-critic"] = {**self.conf["agents"]["sol-prover"], "tool_profile": "review_readonly"}
        self.conf["critic_routing"] = {"enabled": True, "fallback_agent": "sol-critic", "fallback_attempts": 2}
        hybrid.validate_configuration(self.conf, self.profiles, "pythagoras")
        self.assertEqual({"sol-prover": ["prove", "prove-vscore"], "sol-critic": ["critic"]}, hybrid.sol_routes(self.conf))
        self.conf["review"]["review_tiers"][0]["reviewers"][0]["agent"] = "sol-critic"
        with self.assertRaisesRegex(ValueError, "ordinary reviewer membership"):
            hybrid.validate_configuration(self.conf, self.profiles, "pythagoras")

    def test_critic_route_to_another_local_agent_is_not_labeled_sol(self):
        self.conf["critic_routing"] = {"enabled": True, "fallback_agent": "qwen-reviewer", "fallback_attempts": 2}
        with self.assertRaisesRegex(ValueError, "explicit read-only Sol agent"):
            hybrid.validate_configuration(self.conf, self.profiles, "pythagoras")

    def test_prepare_freezes_source_prompt_config_and_tokenizer(self):
        source = self.root / "source.py"
        source.write_text("immutable source")
        tokenizer = self.root / "tokenizer.json"
        tokenizer.write_text("immutable tokenizer")
        out = self.root / "trial"
        def fake_tokenizer(args, directory):
            hybrid.once(directory / "prompt-tokenizer-freeze.json", {"test": True})
            return object(), {str(tokenizer): canonical.digest_file(tokenizer)}
        def sources():
            return {"source.py": canonical.digest_file(source)}
        with patch.object(hybrid, "ROOT", self.root), patch.object(hybrid, "source_inventory", side_effect=sources), patch.object(hybrid, "load_prompt_tokenizer", side_effect=fake_tokenizer):
            protocol = hybrid.prepare(out, self.config, self.profile, self.root)
            self.assertEqual(["P03-unicode-labels"], protocol["tasks"])
            self.assertEqual([], protocol["positive_candidate_arguments"])
            self.assertEqual(hybrid.sol_routes(self.conf), protocol["sol_routes"])
            archive_path = out / protocol["source_archive"]["path"]
            self.assertEqual(canonical.digest_file(archive_path), protocol["source_archive"]["sha256"])
            with tarfile.open(archive_path) as archive:
                self.assertEqual(["source.py"], archive.getnames())
                self.assertEqual(b"immutable source", archive.extractfile("source.py").read())
            self.assertEqual(protocol, hybrid.verify_inputs(out))
            with self.assertRaisesRegex(ValueError, "write-once"):
                hybrid.prepare(out, self.config, self.profile, self.root)
            tokenizer.write_text("changed tokenizer")
            with self.assertRaisesRegex(ValueError, "tokenizer input changed"):
                hybrid.verify_inputs(out)
            tokenizer.write_text("immutable tokenizer")
            source.write_text("changed source")
            with self.assertRaisesRegex(ValueError, "runtime changed"):
                hybrid.verify_inputs(out)
            source.write_text("immutable source")
            (out / "config.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "trial input changed"):
                hybrid.verify_inputs(out)

    def test_source_archive_is_deterministic_and_detects_inventory_race(self):
        source = self.root / "source.py"
        source.write_text("frozen source")
        sources = {"source.py": canonical.digest_file(source)}
        first, second, third = [self.root / name for name in ("first", "second", "third")]
        for out in (first, second, third):
            out.mkdir()
        with patch.object(hybrid, "ROOT", self.root):
            archive = hybrid.freeze_sources(first, sources)
            second_archive = hybrid.freeze_sources(second, sources)
            self.assertEqual(archive.read_bytes(), second_archive.read_bytes())
            source.write_text("mutated source")
            with self.assertRaisesRegex(ValueError, "source changed while archiving"):
                hybrid.freeze_sources(third, sources)

    def test_optional_qwen_template_file_is_frozen(self):
        qwen = self.root / "qwen"
        qwen.mkdir()
        template = qwen / "chat_template.jinja"
        template.write_text("frozen template")
        out = self.root / "trial"
        def fake_tokenizer(args, directory):
            hybrid.once(directory / "prompt-tokenizer-freeze.json", {"test": True})
            return object(), {}
        with patch.object(hybrid, "load_prompt_tokenizer", side_effect=fake_tokenizer):
            protocol = hybrid.prepare(out, self.config, self.profile, self.root, qwen_tokenizer=qwen)
        self.assertEqual(str(qwen), protocol["qwen_tokenizer"])
        self.assertIn("qwen-tokenizer/prompt-tokenizer-freeze.json", protocol["run_inputs"])
        self.assertIn(str(template), protocol["external_inputs"])
        self.assertEqual(128, protocol["prompt_capacity_safety_margin"])
        self.assertEqual(protocol, hybrid.verify_inputs(out))
        template.write_text("modified template")
        with self.assertRaisesRegex(ValueError, "tokenizer input changed"):
            hybrid.verify_inputs(out)

    def test_optional_runtime_manifest_is_retained_and_bound(self):
        manifest = self.root / "runtime.json"
        hybrid.once(manifest, {"kv_cache": "q8_0", "context": 32768})
        out = self.root / "trial"
        def fake_tokenizer(args, directory):
            hybrid.once(directory / "prompt-tokenizer-freeze.json", {"test": True})
            return object(), {}
        with patch.object(hybrid, "load_prompt_tokenizer", side_effect=fake_tokenizer):
            protocol = hybrid.prepare(out, self.config, self.profile, self.root, runtime_manifest=manifest)
        self.assertEqual("runtime-manifest.json", protocol["runtime_manifest"]["retained"])
        self.assertEqual({"kv_cache": "q8_0", "context": 32768}, canonical.load_file(out / "runtime-manifest.json"))
        self.assertIn(str(manifest), protocol["external_inputs"])
        manifest.write_text('{"kv_cache":"f16"}')
        with self.assertRaisesRegex(ValueError, "input changed"):
            hybrid.verify_inputs(out)

    def test_added_preferred_tokenizer_template_is_rejected(self):
        snapshot = self.root / "snapshot"
        snapshot.mkdir()
        out = self.root / "trial"
        def fake_tokenizer(args, directory):
            hybrid.once(directory / "prompt-tokenizer-freeze.json", {"test": True})
            return object(), {}
        with patch.object(hybrid, "load_prompt_tokenizer", side_effect=fake_tokenizer):
            hybrid.prepare(out, self.config, self.profile, snapshot)
        (snapshot / "chat_template.jinja").write_text("new preferred template")
        with self.assertRaisesRegex(ValueError, "tokenizer input inventory changed"):
            hybrid.verify_inputs(out)


if __name__ == "__main__":
    unittest.main()
