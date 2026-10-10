"""Simulation transport tests use local response fixtures and never call a model."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthetic_dataset.tools import luna_worker as worker
from verislop import canonical, review, schemas
from verislop.errors import InfrastructureError
from verislop.providers import config
from verislop.providers.broker import Broker


class LunaMailboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-luna-mailbox-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.conf = worker.configuration()
        self.profiles = worker.endpoint_profiles()["profiles"]
        self.resolved = config.resolve(self.conf, self.profiles)
        self.broker = Broker(self.resolved, self.root / "transcripts")

    def response(self, directory, text="exact final\n", *, model=worker.MODEL,
                 agent_task_id=None, request_sha256=None):
        requests = sorted(directory.glob("request-*.json"))
        request_path = requests[-1]
        request = json.loads(request_path.read_bytes())
        request_id = request["request_id"]
        envelope = {"text": text, "agent_task_id": agent_task_id or "/root/test_luna_" + request_id,
                    "requested_model": model, "transport": "collaboration",
                    "request_id": request_id,
                    "request_sha256": request_sha256 or canonical.digest(request_path.read_bytes())}
        worker.atomic_json(directory / f"response-{request_id}.json", envelope)

    def test_configuration_resolves_and_review_accepts_unknown_identity_as_alias(self):
        self.assertEqual(schemas.validate("review-config", self.conf), [])
        self.assertEqual(schemas.validate("endpoint-profiles", worker.endpoint_profiles()), [])
        self.assertEqual(self.resolved.diagnostics, [])
        manifest = review.model_resolution_manifest(self.conf, self.resolved, {"critic": worker.MODEL})
        self.assertFalse(manifest["require_fixed_snapshot"])
        self.assertEqual(manifest["models"][0]["mode"], "provider_alias")
        self.assertIsNone(manifest["models"][0]["expected_model"])
        self.assertTrue(review._model_matches(manifest, "critic", worker.MODEL, None))
        self.assertFalse(review._model_matches(manifest, "critic", "wrong-model", None))

    def test_exact_response_receipts_unknown_usage_and_no_api_or_credentials(self):
        directory = self.root / "arm"
        transport = worker.MailboxTransport(directory, 1)
        text = '{"files":{"solution.py":"def solve(data): return data\\n"}}\n'
        with patch.object(worker.time, "sleep", side_effect=lambda _: self.response(directory, text)), \
                patch.object(Broker, "_secret", side_effect=AssertionError("credentials must not be resolved")), \
                patch("verislop.providers.broker.complete", side_effect=AssertionError("API must not be called")):
            comp = transport.call(self.broker, "author", "raw/1", "exact system", "exact user", "raw-coding")
        self.assertEqual(comp.text, text)
        self.assertEqual(comp.requested_model, worker.MODEL)
        self.assertIsNone(comp.returned_model)
        self.assertIsNone(comp.input_tokens)
        self.assertIsNone(comp.output_tokens)
        request_path = directory / "request-0001.json"
        response_path = directory / "response-0001.json"
        request = json.loads(request_path.read_bytes())
        self.assertEqual((request["system"], request["user"]), ("exact system", "exact user"))
        self.assertFalse(request["output_token_limit_enforced"])
        receipt = json.loads((directory / "response-receipt-0001.json").read_bytes())
        self.assertEqual(receipt["request_sha256"], canonical.digest(request_path.read_bytes()))
        self.assertEqual(receipt["response_sha256"], canonical.digest(response_path.read_bytes()))
        self.assertEqual(receipt["text_sha256"], canonical.digest(text.encode()))
        self.assertFalse(receipt["model_identity_attested"])
        self.assertEqual(transport.state["unknown_usage_calls"], 1)
        self.assertEqual(transport.state["output_bytes"], len(text.encode()))
        self.assertIsNone(transport.state["output_tokens"])
        transcript = json.loads(next((self.root / "transcripts").glob("*.json")).read_bytes())
        self.assertEqual(transcript["response"], text)
        self.assertIsNone(transcript["returned_model"])

    def test_wrong_model_and_unbound_response_are_rejected(self):
        for label, settings in (("model", {"model": "wrong-model"}),
                                ("hash", {"request_sha256": "sha256:" + "0" * 64})):
            with self.subTest(label=label):
                directory = self.root / label
                transport = worker.MailboxTransport(directory, 1)
                with patch.object(worker.time, "sleep", side_effect=lambda _, d=directory, s=settings: self.response(d, **s)):
                    with self.assertRaises(InfrastructureError):
                        transport.call(self.broker, "author", label, "system", "user", "raw-coding")
                self.assertFalse((directory / "response-receipt-0001.json").exists())
                self.assertEqual(transport.state["responses"], 0)

    def test_utf8_byte_cap_is_enforced_and_usage_is_not_invented(self):
        envelope = {"text": "é" * (worker.MAX_RESPONSE_BYTES // 2 + 1),
                    "agent_task_id": "/root/test_luna", "requested_model": worker.MODEL,
                    "transport": "collaboration", "request_id": "0001", "request_sha256": "sha256:bound"}
        with self.assertRaises(InfrastructureError) as failure:
            worker.validate_response(envelope, "0001", "sha256:bound")
        self.assertEqual(failure.exception.diagnostics[0].code, "BUDGET_EXHAUSTED")

    def test_logical_call_limit_and_fresh_agent_requirement(self):
        directory = self.root / "one"
        transport = worker.MailboxTransport(directory, 1)
        with patch.object(worker.time, "sleep", side_effect=lambda _: self.response(directory)):
            transport.call(self.broker, "author", "first", "system", "user", "generate")
        with self.assertRaises(InfrastructureError) as failure:
            transport.call(self.broker, "author", "second", "system", "user", "generate")
        self.assertEqual(failure.exception.diagnostics[0].code, "BUDGET_EXHAUSTED")
        self.assertFalse((directory / "request-0002.json").exists())

        directory = self.root / "fresh"
        transport = worker.MailboxTransport(directory, 2)
        with patch.object(worker.time, "sleep", side_effect=lambda _: self.response(directory, agent_task_id="/root/reused")):
            transport.call(self.broker, "author", "third", "system", "user", "generate")
            with self.assertRaises(InfrastructureError):
                transport.call(self.broker, "author", "fourth", "system", "user", "generate")
        self.assertEqual(transport.state["calls"], 2)
        self.assertEqual(transport.state["responses"], 1)

    def test_raw_preserves_one_call_exact_prompt_source_and_restores_broker(self):
        config_path, prompt, directory = self.root / "config.json", self.root / "prompt.txt", self.root / "raw"
        worker.atomic_json(config_path, self.conf)
        prompt.write_text("Exact task prompt\n")
        text = json.dumps({"files": {"solution.py": "def solve(data):\n return data\n"}})
        original = Broker.call
        with patch.object(config, "load_user_profiles", return_value=self.profiles), \
                patch.object(worker.time, "sleep", side_effect=lambda _: self.response(directory, text)):
            status = worker.main(["--arm", "raw", "--task", str(prompt), "--out", str(directory),
                                  "--config", str(config_path), "--calls", "32"])
        self.assertEqual(status, 0)
        self.assertIs(Broker.call, original)
        self.assertEqual((directory / "artifact/solution.py").read_text(), "def solve(data):\n return data\n")
        request = json.loads((directory / "request-0001.json").read_bytes())
        self.assertEqual(request["system"], worker.RAW_SYSTEM)
        self.assertEqual(request["user"], prompt.read_text())
        self.assertEqual(json.loads((directory / "usage.json").read_bytes())["max_calls"], 1)

    def test_full_cli_uses_actual_strict_tested_workflow_and_zero_wall_budget(self):
        config_path, prompt, directory = self.root / "config.json", self.root / "prompt.txt", self.root / "full"
        worker.atomic_json(config_path, self.conf)
        prompt.write_text("task")
        original = Broker.call
        with patch.object(worker.cli, "main", return_value=2) as invoked:
            status = worker.main(["--arm", "verislop", "--task", str(prompt), "--out", str(directory),
                                  "--config", str(config_path), "--calls", "32"])
        self.assertEqual(status, 2)
        self.assertIs(Broker.call, original)
        argv = invoked.call_args.args[0]
        for flag, expected in (("--runs-dir", str(directory)), ("--run-id", "package"),
                               ("--tier", "0"), ("--target", "python"), ("--require-state", "TESTED"),
                               ("--endpoint", "test_campaign"), ("--policy", "strict"), ("--budget-seconds", "0"),
                               ("--repair-rounds", "2")):
            self.assertEqual(argv[argv.index(flag) + 1], expected)
        self.assertIn("--require-tests", argv)
        self.assertIn("--non-interactive", argv)
        for forbidden in ("--draft-candidate", "--formalization-candidate", "--proof-candidate",
                          "--implementation-candidate", "--bindings-candidate"):
            self.assertNotIn(forbidden, argv)


if __name__ == "__main__":
    unittest.main()
