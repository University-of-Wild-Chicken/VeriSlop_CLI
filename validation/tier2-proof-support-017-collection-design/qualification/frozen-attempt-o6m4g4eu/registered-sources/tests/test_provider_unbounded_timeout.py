"""Explicit no-deadline provider requests, using mocked transports only."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from verislop import schemas
from verislop.providers import adapters, config, conformance, http
from verislop.providers.broker import Broker, Budget


ROOT = Path(__file__).resolve().parents[1]
MODEL = "arbitrary-local-model:example"
DIGEST = "a" * 64


class ProviderUnboundedTimeoutTests(unittest.TestCase):
    def configuration(self, timeout=None):
        conf = json.loads((ROOT / "examples/ollama-review-config.json").read_text())
        conf["providers"]["local"]["request_timeout_seconds"] = timeout
        for agent in conf["agents"].values():
            agent["model_ref"] = MODEL
            agent["model_identity"] = {"mode": "pinned", "resolved_model": MODEL,
                                       "model_digest_sha256": DIGEST}
        return conf

    def test_null_survives_configuration_load_and_resolution(self):
        conf = self.configuration()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(conf))
            loaded = config.load(path)
        resolved = config.resolve(loaded, {})
        self.assertIsNone(resolved.provider("local")["request_timeout_seconds"])
        self.assertFalse([d for d in resolved.diagnostics if d.severity == "blocking"])

    def test_positive_timeouts_remain_valid_and_unmodified(self):
        for value in (1, 30, 120):
            with self.subTest(timeout=value):
                conf = self.configuration(value)
                self.assertEqual([], schemas.validate("review-config", conf))
                self.assertEqual(value, config.resolve(conf, {}).provider("local")["request_timeout_seconds"])
        original = json.loads((ROOT / "examples/ollama-review-config.json").read_text())
        self.assertEqual(120, original["providers"]["local"]["request_timeout_seconds"])

    def test_zero_negative_boolean_string_and_fractional_provider_timeouts_rejected(self):
        for value in (0, -1, True, "none", 1.5):
            with self.subTest(timeout=value):
                self.assertTrue(schemas.validate("review-config", self.configuration(value)))

    def test_review_zero_disables_only_review_wall_budget_schema(self):
        conf = self.configuration()
        conf["review"]["budgets"]["max_wall_seconds_per_tier"] = 0
        self.assertEqual([], schemas.validate("review-config", conf))
        conf["review"]["budgets"]["max_wall_seconds_per_tier"] = -1
        self.assertTrue(schemas.validate("review-config", conf))

    def test_http_forwards_none_explicitly_to_urllib(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"ok":true}'
        response.headers = {"Content-Type": "application/json"}
        with patch.object(http._OPENER, "open", return_value=response) as opened:
            body, _ = http.request("POST", "http://127.0.0.1:1", "/api/chat", {}, {}, None)
        self.assertEqual({"ok": True}, body)
        self.assertIn("timeout", opened.call_args.kwargs)
        self.assertIsNone(opened.call_args.kwargs["timeout"])

    def test_http_preserves_finite_timeout(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{}'
        response.headers = {}
        with patch.object(http._OPENER, "open", return_value=response) as opened:
            http.request("GET", "http://127.0.0.1:1", "/api/tags", {}, None, 7)
        self.assertEqual(7, opened.call_args.kwargs["timeout"])

    def test_unbounded_transport_timeout_exception_has_accurate_diagnostic(self):
        with patch.object(http._OPENER, "open", side_effect=TimeoutError()):
            with self.assertRaises(http.ProviderError) as raised:
                http.request("GET", "http://127.0.0.1:1", "/api/tags", {}, None, None)
        self.assertEqual("timeout", raised.exception.kind)
        self.assertEqual("provider request timed out", raised.exception.message)

    def test_broker_passes_none_to_both_catalog_checks_and_native_inference(self):
        resolved = config.resolve(self.configuration(), {})
        calls = []

        def transport(method, base, path, headers, payload, timeout):
            calls.append((method, path, timeout))
            if path == "/api/tags":
                return {"models": [{"name": MODEL, "digest": DIGEST}]}, {}
            self.assertEqual("/api/chat", path)
            self.assertEqual(MODEL, payload["model"])
            return {"model": MODEL, "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": '{"ok":true}'},
                    "prompt_eval_count": 10, "eval_count": 4}, {}

        with patch.object(adapters, "request", side_effect=transport):
            completion = Broker(resolved, transcript_dir=None, budget=Budget(max_retries=0)).call(
                "local-author", "example", "system", "user", "test-no-deadline")
        self.assertEqual(DIGEST, completion.model_digest_sha256)
        self.assertEqual([("GET", "/api/tags", None), ("POST", "/api/chat", None),
                          ("GET", "/api/tags", None)], calls)

    def test_cloud_adapter_also_preserves_none(self):
        profile = {"adapter": "openai", "base_url": "https://example.invalid/v1", "auth_scheme": "bearer"}
        body = {"model": MODEL, "output_text": '{"ok":true}', "usage": {"input_tokens": 1, "output_tokens": 2}}
        with patch.object(adapters, "request", return_value=(body, {})) as transport:
            completion = adapters.complete("responses", profile, "test-secret", MODEL, "system", "user", 32, None)
        self.assertEqual('{"ok":true}', completion.text)
        self.assertIsNone(transport.call_args.args[-1])

    def test_direct_catalog_auth_check_preserves_none(self):
        profile = config.resolve(self.configuration(), {}).profiles["local"]
        with patch.object(adapters, "request", return_value=({"models": [{"name": MODEL, "digest": DIGEST}]}, {})) as transport:
            result = adapters.auth_check(profile, "", None)
        self.assertTrue(result["ok"])
        self.assertIsNone(transport.call_args.args[-1])

    def test_explicit_conformance_probe_keeps_its_own_disclosed_cap(self):
        conf = self.configuration()
        observed_timeouts = []

        def completion(broker, agent, instance, system, user, purpose):
            observed_timeouts.append(broker.r.provider("local")["request_timeout_seconds"])
            challenge = json.loads(user.split("\n", 1)[1])
            return adapters.Completion(json.dumps(challenge), MODEL, MODEL, None, 10, 4, DIGEST)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(conf))
            with patch.object(Broker, "call", new=completion), patch.object(config, "load_user_profiles", return_value={}):
                result = conformance.run(path, ["local-author"], live=True)
        self.assertEqual("PASS", result.status)
        self.assertEqual([conformance.MAX_TIMEOUT_SECONDS], observed_timeouts)
        self.assertIsNone(conf["providers"]["local"]["request_timeout_seconds"])


if __name__ == "__main__":
    unittest.main()
