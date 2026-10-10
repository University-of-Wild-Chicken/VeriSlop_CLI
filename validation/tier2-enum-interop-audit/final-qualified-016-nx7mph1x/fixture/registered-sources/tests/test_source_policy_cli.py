"""Fresh source-policy CLI and author-context fixtures, without provider requests.

Startup/resume use the real configuration loader and broker; stage-routing checks
and author-response fixtures exercise their own narrower boundaries explicitly.
"""
from __future__ import annotations

import json
import sys
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir, codes, mock_config, run_cli, unanimous
from test_source_frontend import frozen_records, source_proposal

from verislop import agents, canonical, cli, formalize, fsutil, interpret, source_contract, source_policy
from verislop.errors import Diagnostic, InfrastructureError, UsageError
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers.broker import Broker
from verislop.stage import StageResult


def policy_fixture():
    return {"schema_version": "0.1", "format": "verislop.required-source-facets/0.1", "obligations": {
        "G1": {"file": "program.vscore.json", "entry": "plus", "arity": 1,
               "properties": ["typed_total", "deterministic", "input_preserved", "no_external_io",
                              "no_floating_point", "pure_data", "restricted_runtime_only"],
               "value_required": True}}}


class SourcePolicyCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.path
        self.policy = policy_fixture()
        self.input = self.root / "required-source.json"
        # Exact bytes matter; the frozen input must not be rewritten canonically.
        self.policy_bytes = (json.dumps(self.policy, indent=3) + "\n").encode()
        self.input.write_bytes(self.policy_bytes)
        self.prompt = self.root / "request.txt"
        self.prompt.write_text("Return the integer input plus two.\n")
        self.pkg = Package(self.root / "standalone")
        self.pkg.ensure("fresh-policy-context")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)

    def _cli(self, *args, env=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            return run_cli(*args, env=env)

    def _configured(self):
        config, env = mock_config(self.root, 9, [unanimous("fresh-review", "reviewer", 1)],
                                  checkpoints=["interpretation"], max_repair_rounds=0)
        conf = canonical.load_file(config)
        conf.update({"bridge_tier": 2, "endpoint": "restricted_source"})
        fsutil.write_json(config, conf, pretty=True)
        return config, env

    def _run_until_transport(self):
        config, env = self._configured()
        received = []

        def transport(broker, agent, instance, system, user, purpose):
            received.append((broker, user, purpose))
            raise InfrastructureError("fresh policy transport marker", [Diagnostic(
                "PROVIDER_FAILURE", "fresh policy transport marker", severity="infrastructure")])

        with patch.object(Broker, "call", autospec=True, side_effect=transport):
            code, result, error = self._cli(
                "run", "--prompt-file", str(self.prompt), "--runs-dir", str(self.root / "runs"),
                "--run-id", "fresh-policy-run", "--mode", "software", "--tier", "2", "--target", "vscore",
                "--endpoint", "restricted_source", "--backend-version", "0.3",
                "--source-policy", str(self.input), "--config", str(config), "--repair-rounds", "0",
                "--non-interactive", env=env)
        self.assertEqual((code, result["status"], error), (3, "INFRASTRUCTURE_FAILURE", ""))
        self.assertEqual(len(received), 1)
        pkg = Package(self.root / "runs" / "fresh-policy-run")
        self.assertEqual((pkg.root / "request/source-policy.json").read_bytes(), self.policy_bytes)
        self.assertEqual(pkg.meta()["source_policy"], {"format": self.policy["format"],
            "path": "request/source-policy.json", "sha256": canonical.digest(self.policy_bytes)})
        self.assertEqual(pkg.meta()["run_parameters"]["source_policy"], str(self.input.resolve()))
        self.assertEqual(pkg.meta()["requested"]["backend_version"], "0.3")
        broker, user, purpose = received[0]
        self.assertIsInstance(broker, Broker)
        self.assertEqual(broker.r.profiles["mock"]["base_url"], "http://127.0.0.1:9/v1")
        self.assertEqual(purpose, "interpret")
        self.assertIn("REQUIRED SOURCE FACETS", user)
        self.assertIn('"G1"', user)
        self.assertIn('"value_required": true', user)
        self.assertIn("Do not convert these requirements into assumptions", user)
        self.assertFalse((pkg.path("accepted") / "acceptance.json").exists())
        return pkg, env, transport, received

    def test_run_freezes_before_author_and_resume_uses_only_the_frozen_copy(self):
        pkg, env, transport, received = self._run_until_transport()
        self.input.unlink()
        received.clear()
        with patch.object(Broker, "call", autospec=True, side_effect=transport):
            code, result, error = self._cli("resume", "--runs-dir", str(self.root / "runs"),
                                          "--run-id", pkg.run_id, env=env)
        self.assertEqual((code, result["status"], error), (3, "INFRASTRUCTURE_FAILURE", ""))
        self.assertEqual(len(received), 1)
        self.assertIn('"entry": "plus"', received[0][1])
        self.assertEqual(source_policy.context(pkg), self.policy)
        self.assertEqual((pkg.root / "request/source-policy.json").read_bytes(), self.policy_bytes)

    def test_resume_changed_frozen_policy_blocks_before_any_author(self):
        pkg, env, _transport, received = self._run_until_transport()
        frozen = pkg.root / "request/source-policy.json"
        fsutil.make_writable_tree(pkg.root)
        frozen.write_bytes(self.policy_bytes + b" \n")
        received.clear()
        with patch.object(Broker, "call", autospec=True, side_effect=AssertionError("changed policy reached broker")) as broker:
            code, result, error = self._cli("resume", "--runs-dir", str(self.root / "runs"),
                                          "--run-id", pkg.run_id, env=env)
        self.assertEqual((code, result["status"], error), (2, "BLOCKED", ""))
        broker.assert_not_called()
        self.assertIn("INPUT_MUTATION", codes(result))
        self.assertFalse(result["asserts_closure_verified"])

    def test_direct_interpret_and_formalize_stage_before_agent_factories(self):
        for command in ("interpret", "formalize"):
            root = self.root / command
            pkg = Package(root)
            pkg.ensure("direct-" + command)
            if command == "formalize":
                source_policy.stage(pkg, self.input)
                fsutil.write_json(pkg.path("interpretation"), {"untrusted_fixture_marker": True})
            observed = []

            def factory(_config, active, _events):
                observed.append(source_policy.context(active))
                return object()

            flags = [command, "--package", str(root), "--config", "unused", "--source-policy", str(self.input)]
            if command == "interpret":
                flags += ["--prompt-file", str(self.prompt), "--mode", "software", "--non-interactive"]
            args = cli.build_parser().parse_args(flags)
            factory_name = "interpreter_agent" if command == "interpret" else "formalizer_agent"
            with patch.object(agents, factory_name, side_effect=factory), \
                 patch.object(cli, "_events", return_value=self.events), \
                 patch.object(interpret if command == "interpret" else formalize, "run", return_value=StageResult(
                     command, "BLOCKED", "fresh stage routing only")), \
                 patch("verislop.autonomous.critic_agent", return_value=None):
                result = args.func(args)
            self.assertEqual(result.status, "BLOCKED")
            self.assertEqual(observed, [self.policy])
            self.assertEqual((root / "request/source-policy.json").read_bytes(), self.policy_bytes)

    def test_formalize_flag_cannot_replace_policy_after_interpretation(self):
        source_policy.stage(self.pkg, self.input)
        fsutil.write_json(self.pkg.path("interpretation"), {"untrusted_fixture_marker": True})
        changed = {**self.policy, "obligations": {"G1": {**self.policy["obligations"]["G1"], "entry": "other"}}}
        self.input.write_bytes(canonical.dumps(changed))
        with patch.object(agents, "formalizer_agent", side_effect=AssertionError("changed policy reached author")):
            code, result, error = self._cli("formalize", "--package", str(self.pkg.root),
                "--source-policy", str(self.input), "--config", "unused")
        self.assertEqual((code, result["status"], error), (64, "INVALID_INVOCATION", ""))
        self.assertIn("INPUT_MUTATION", codes(result))
        self.assertEqual((self.pkg.root / "request/source-policy.json").read_bytes(), self.policy_bytes)

    def _formalizer_context(self, requested):
        return {"records": frozen_records(), "ledger": {}, "requested": requested,
                "feedback": [], "attempt": 1, "source_policy": {"obligations": {"Fake": {}}}}

    def test_typed_author_receives_exact_policy_and_generates_real_source_conjunction(self):
        source_policy.stage(self.pkg, self.input)
        requested = {"tier": 2, "target": "vscore", "endpoint": "restricted_source", "backend_version": "0.3"}
        with patch.object(agents, "_broker", return_value=(None, {})), patch.object(agents, "_role", return_value="author"), \
             patch.object(agents, "recorded_call", return_value=SimpleNamespace(
                 text=json.dumps(source_proposal(mixed=True)), request_id="fresh-policy-response")) as called:
            author = agents.formalizer_agent("unused", self.pkg, self.events)
            source, form = author(self._formalizer_context(requested))
        system, user = called.call_args.args[4:6]
        self.assertEqual(system, agents.TYPED_FORMALIZER_SYSTEM)
        self.assertIn("POLICY AUTHORING WIRE", user)
        self.assertIn('"entry": "plus"', user)
        self.assertIn('"value_required": true', user)
        self.assertNotIn('"Fake"', user)
        self.assertIn("SourceBoundary Contract conjunction", user)
        self.assertIn(b"VeriSlop.Source.Contract", source)
        self.assertIn(b".1", source)
        binding = form["bindings"][0]
        self.assertEqual(binding["obligation"], "G1")
        self.assertEqual(binding["source_requirements"], ["VeriSlopAST.Delivery"])
        self.assertEqual(binding["value_projection"], "VeriSlopAST._vs_value_Spec")

    def test_raw_author_gets_pinned_model_and_actual_contract_projection_shapes(self):
        source_policy.stage(self.pkg, self.input)
        response = json.dumps({"lean_source": "-- fresh unaccepted raw proposal\n", "formalization": {"bindings": []}})
        with patch.object(agents, "_broker", return_value=(None, {})), patch.object(agents, "_role", return_value="author"), \
             patch.object(agents, "recorded_call", return_value=SimpleNamespace(text=response, request_id="fresh-raw-policy")) as called:
            author = agents.formalizer_agent("unused", self.pkg, self.events)
            author(self._formalizer_context({}))
        system, user = called.call_args.args[4:6]
        self.assertEqual(system, agents.FORMALIZER_SYSTEM)
        self.assertIn("RAW LEAN SOURCE POLICY", user)
        self.assertIn(source_contract.library_source().decode(), user)
        self.assertIn("VeriSlop.Source.SourceDefinition", system)
        self.assertIn("by exact original_guarantee.1", system)
        self.assertIn("source_requirements", system)
        self.assertIn("value_projection", system)
        self.assertIn("Math-only existence/equality proxies omit required", system)

    def test_changed_policy_author_context_is_rejected_before_provider_request(self):
        source_policy.stage(self.pkg, self.input)
        fsutil.make_writable_tree(self.pkg.root)
        (self.pkg.root / "request/source-policy.json").write_bytes(self.policy_bytes + b"\n")
        with patch.object(agents, "_broker", return_value=(None, {})), patch.object(agents, "_role", return_value="author"), \
             patch.object(agents, "recorded_call", side_effect=AssertionError("changed policy reached author")) as called:
            interpreter = agents.interpreter_agent("unused", self.pkg, self.events)
            formalizer = agents.formalizer_agent("unused", self.pkg, self.events)
            for invoke in (lambda: interpreter(self.prompt.read_bytes(), "request.txt", {}),
                           lambda: formalizer(self._formalizer_context({}))):
                with self.assertRaises(UsageError) as raised:
                    invoke()
                self.assertEqual(raised.exception.diagnostics[0].code, "INPUT_MUTATION")
        called.assert_not_called()


if __name__ == "__main__":
    unittest.main()
