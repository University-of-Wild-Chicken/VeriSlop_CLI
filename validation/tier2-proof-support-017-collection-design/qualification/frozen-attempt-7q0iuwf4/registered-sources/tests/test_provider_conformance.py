"""Inference probes use real broker/HTTP adapters against representative loopback services.

No external service, real credential, model download, or paid inference is used here.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from verislop.errors import UsageError
from verislop.providers import conformance, http
from verislop.providers.broker import Broker
from verislop.providers import config as cfg
from helpers import run_cli


SECRET = "conformance-test-secret-7d70eb"
CONFIG = Path(__file__).resolve().parents[1] / "examples" / "review-config.json"
FAMILIES = {
    "openai": ("openai", "responses", "bearer"),
    "claude": ("anthropic", "anthropic_messages", "x-api-key"),
    "gemini": ("google_gemini", "gemini_generate_content", "x-goog-api-key"),
    "deepseek": ("deepseek", "chat_completions", "bearer"),
    "qwen": ("alibaba_model_studio", "chat_completions", "bearer"),
    "glm": ("zai", "chat_completions", "bearer"),
    "kimi": ("moonshot", "chat_completions", "bearer"),
    "grok": ("xai", "responses", "bearer"),
    "muse": ("meta", "responses", "bearer"),
}


class ProtocolServer:
    def __init__(self):
        self.requests = []
        self.behavior = lambda body: body
        self.status = 200
        self.raw_response = None
        self.response_headers = {}
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802
                request_body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                mock.requests.append({"path": self.path, "headers": dict(self.headers), "body": request_body})
                if self.path.endswith("/responses"):
                    user, model = request_body["input"], request_body["model"]
                    text = user.split("\n", 1)[1]
                    response = {"id": "mock-response", "model": model, "status": "completed",
                                "output": [{"type": "reasoning", "summary": []},
                                           {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}],
                                "usage": {"input_tokens": 21, "output_tokens": 25}}
                elif self.path.endswith("/chat/completions"):
                    user, model = request_body["messages"][-1]["content"], request_body["model"]
                    text = user.split("\n", 1)[1]
                    response = {"id": "mock-chat", "model": model,
                                "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                                "usage": {"prompt_tokens": 21, "completion_tokens": 25}}
                elif self.path.endswith("/messages"):
                    user, model = request_body["messages"][-1]["content"], request_body["model"]
                    text = user.split("\n", 1)[1]
                    response = {"id": "mock-message", "model": model, "stop_reason": "end_turn",
                                "content": [{"type": "text", "text": text}],
                                "usage": {"input_tokens": 21, "output_tokens": 25}}
                else:
                    user = request_body["contents"][0]["parts"][0]["text"]
                    model = self.path.split("/models/", 1)[1].split(":", 1)[0]
                    text = user.split("\n", 1)[1]
                    response = {"responseId": "mock-generate", "modelVersion": model,
                                "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
                                "usageMetadata": {"promptTokenCount": 21, "candidatesTokenCount": 25}}
                body = mock.raw_response if mock.raw_response is not None else json.dumps(mock.behavior(response)).encode()
                self.send_response(mock.status)
                self.send_header("Content-Type", "application/json")
                for key, value in mock.response_headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (ConnectionResetError, BrokenPipeError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ProviderConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ProtocolServer()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-provider-probe-")
        self.root = Path(self.tmp.name)
        self.server.requests.clear()
        self.server.behavior = lambda body: body
        self.server.status = 200
        self.server.raw_response = None
        self.server.response_headers = {}
        self.conf = json.loads(CONFIG.read_text())
        self.conf["providers"] = {}
        self.conf["agents"] = {}
        self.profiles = {"schema_version": "0.1", "artifact_kind": "endpoint_profiles", "profiles": {}}
        for name, (adapter, family, scheme) in FAMILIES.items():
            self.conf["providers"][name] = {
                "adapter": adapter, "api_family": family, "endpoint_profile": f"local-{name}",
                "credential_ref": "env:VERISLOP_PROBE_TEST_KEY", "concurrency": 2, "request_timeout_seconds": 120,
            }
            self.conf["agents"][name] = {"provider": name, "model_ref": f"mock-{name}", "tool_profile": "review_readonly", "max_output_tokens": 8000}
            self.profiles["profiles"][f"local-{name}"] = {
                "adapter": adapter, "base_url": f"http://127.0.0.1:{self.server.port}/v1", "auth_scheme": scheme,
                "families": [family], "allow_insecure_loopback": True,
            }
            if scheme == "x-api-key":
                self.profiles["profiles"][f"local-{name}"]["api_version"] = "2023-06-01"
        self.conf["roles"] = {role: "openai" for role in self.conf["roles"]}
        self.conf["review"]["review_tiers"] = [{
            "id": "R0", "reviewers": [{"agent": "claude", "count": 1, "focus": "general"}],
            "consensus": {"mode": "unanimous", "require_all_responses": True, "max_soft_rejects": 0,
                          "max_abstentions": 0, "blocking_findings_veto": True},
        }]
        self.config_path = self.root / "config.json"
        self.profiles_path = self.root / "profiles.json"
        self.save()
        self.environ = patch.dict(os.environ, {"VERISLOP_PROBE_TEST_KEY": SECRET})
        self.environ.start()

    def tearDown(self):
        self.environ.stop()
        self.tmp.cleanup()

    def save(self):
        self.config_path.write_text(json.dumps(self.conf))
        self.profiles_path.write_text(json.dumps(self.profiles))

    def probe(self, agents=None, **kwargs):
        return conformance.run(self.config_path, agents or ["openai"], live=True, profiles=self.profiles_path, **kwargs)

    def test_all_requested_provider_families_use_real_protocol_and_broker(self):
        result = self.probe(list(FAMILIES))
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertFalse(result.to_json()["asserts_closure_verified"])
        self.assertEqual(result.summary["inference_calls_attempted"], 9)
        self.assertEqual(result.summary["completed_responses"], 9)
        self.assertEqual(len(self.server.requests), 9)
        self.assertNotIn(SECRET, json.dumps(result.to_json()))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["config.json", "profiles.json"])
        for name, request in zip(FAMILIES, self.server.requests):
            family, scheme = FAMILIES[name][1:]
            headers, body = {key.lower(): value for key, value in request["headers"].items()}, request["body"]
            self.assertNotIn(SECRET, json.dumps(body))
            if scheme == "bearer":
                self.assertEqual(headers["authorization"], f"Bearer {SECRET}")
            elif scheme == "x-api-key":
                self.assertEqual(headers["x-api-key"], SECRET)
                self.assertEqual(headers["anthropic-version"], "2023-06-01")
            else:
                self.assertEqual(headers["x-goog-api-key"], SECRET)
            if family == "responses":
                self.assertEqual(body["max_output_tokens"], 128)
            elif family == "gemini_generate_content":
                self.assertEqual(body["generationConfig"]["maxOutputTokens"], 128)
            else:
                self.assertEqual(body["max_tokens"], 128)
            entry = result.summary["agents"][name]
            self.assertEqual(entry["inference_check"], "PASS")
            self.assertEqual(entry["model_identity"], "exact")
            self.assertEqual(entry["effective_timeout_seconds"], 30)
            self.assertEqual(entry["usage"], {"input_tokens": 21, "output_tokens": 25})

    def test_cli_requires_explicit_live_opt_in(self):
        with patch("verislop.providers.conformance.auth.resolve") as resolve:
            with self.assertRaises(UsageError):
                conformance.run(self.config_path, ["openai"], profiles=self.profiles_path)
            resolve.assert_not_called()
        code, result, _ = run_cli("providers", "probe", "--config", str(self.config_path), "--agent", "openai",
                                  "--endpoint-profiles", str(self.profiles_path))
        self.assertEqual(code, 64, result)
        self.assertEqual(self.server.requests, [])

    def test_cli_live_probe_selects_exact_agents(self):
        code, result, err = run_cli("providers", "probe", "--config", str(self.config_path), "--agent", "openai",
                                   "--agent", "gemini", "--endpoint-profiles", str(self.profiles_path), "--live")
        self.assertEqual(code, 0, (result, err))
        self.assertEqual(set(result["summary"]["agents"]), {"openai", "gemini"})
        self.assertEqual(len(self.server.requests), 2)

    def test_unselected_provider_does_not_need_credential_or_endpoint(self):
        self.conf["providers"]["muse"]["endpoint_profile"] = "meta-model-api"
        self.conf["providers"]["muse"]["credential_ref"] = "env:ABSENT_PROBE_KEY"
        self.save()
        result = self.probe()
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertEqual(len(self.server.requests), 1)

    def test_selected_unresolved_meta_and_qwen_do_not_guess_endpoints(self):
        for name, profile in (("muse", "meta-model-api"), ("qwen", "user-selected-dashscope-region-workspace")):
            with self.subTest(provider=name):
                self.conf["providers"][name]["endpoint_profile"] = profile
                self.save()
                result = self.probe([name])
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.summary["inference_calls_attempted"], 0)
        self.assertEqual(self.server.requests, [])

    def test_all_selected_references_preflight_before_any_inference(self):
        self.conf["providers"]["gemini"]["credential_ref"] = "env:ABSENT_PROBE_KEY"
        self.conf["agents"]["claude"]["model_ref"] = "env:ABSENT_PROBE_MODEL"
        self.save()
        with patch.dict(os.environ, {"ABSENT_PROBE_KEY": "", "ABSENT_PROBE_MODEL": ""}):
            result = self.probe(["openai", "gemini", "claude"])
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.summary["inference_calls_attempted"], 0)
        self.assertEqual(self.server.requests, [])

    def test_selection_and_output_limits_fail_before_requests(self):
        for agents, cap in (([], 128), (["openai", "openai"], 128), (["unknown"], 128), (["openai"], 0), (["openai"], 1025)):
            with self.subTest(agents=agents, cap=cap), self.assertRaises(UsageError):
                conformance.run(self.config_path, agents, live=True, profiles=self.profiles_path, max_output_tokens=cap)
        self.assertEqual(self.server.requests, [])

    def test_configured_output_limit_is_not_increased(self):
        self.conf["agents"]["openai"]["max_output_tokens"] = 32
        self.save()
        self.assertEqual(self.probe(max_output_tokens=128).status, "PASS")
        self.assertEqual(self.server.requests[0]["body"]["max_output_tokens"], 32)

    def test_alias_is_recorded_without_claiming_equivalence(self):
        self.server.behavior = lambda body: {**body, "model": "provider-snapshot-2026-10-01"}
        result = self.probe()
        self.assertEqual(result.status, "PASS")
        self.assertFalse(result.summary["asserts_model_alias_equivalence"])
        self.assertEqual(result.summary["agents"]["openai"]["model_identity"], "different; alias equivalence unverified")
        self.assertTrue(any(d.details.get("kind") == "model_alias_unverified" and d.severity == "warning" for d in result.diagnostics))

    def test_invalid_json_stale_challenge_and_boolean_impostor_fail(self):
        for text in ('not JSON', '{"ok":true,"challenge":"old"}', '{"ok":true,"ok":true,"challenge":"old"}',
                     '[' * 1500 + '0' + ']' * 1500):
            with self.subTest(text=text):
                self.server.behavior = lambda body: {**body, "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}
                result = self.probe()
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.summary["agents"]["openai"]["inference_check"], "FAIL")
        def impostor(body):
            item = body["output"][1]["content"][0]
            item["text"] = item["text"].replace("true", "1")
            return body
        self.server.behavior = impostor
        self.assertEqual(self.probe().status, "BLOCKED")

    def test_model_usage_missing_or_over_budget_fail(self):
        variants = [({"model": None}, "model_metadata_missing"), ({"usage": {}}, "usage_metadata_missing"),
                    ({"usage": {"input_tokens": 21, "output_tokens": 129}}, "output_budget_exceeded")]
        for update, kind in variants:
            with self.subTest(kind=kind):
                self.server.behavior = lambda body: {**body, **update}
                result = self.probe()
                self.assertEqual(result.status, "BLOCKED")
                self.assertEqual(result.summary["agents"]["openai"]["failure_kind"], kind)

    def test_malformed_protocol_shapes_return_safe_diagnostics(self):
        variants = [("openai", {"output": ["invalid"]}), ("claude", {"content": [None]}),
                    ("gemini", {"candidates": [{"content": {"parts": [False]}}]}),
                    ("deepseek", {"choices": [{"message": {"content": {"wrong": "shape"}}}]}),
                    ("openai", {"usage": []}), ("openai", {"usage": {"input_tokens": True}}),
                    ("openai", {"usage": {"output_tokens": -1}}),
                    ("openai", {"usage": {"input_tokens": "21"}}), ("openai", {"model": 42}),
                    ("openai", {"model": "\ud800"}), ("openai", {"id": "\udfff"})]
        for name, update in variants:
            with self.subTest(provider=name, update=update):
                self.server.behavior = lambda body: {**body, **update}
                result = self.probe([name])
                self.assertEqual(result.status, "INFRASTRUCTURE_FAILURE")
                self.assertEqual(result.summary["agents"][name]["failure_kind"], "bad_response")

    def test_invalid_utf8_top_level_array_and_size_bound_are_rejected(self):
        for raw in (b"\xff", b"[]", b'{"deep":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'):
            with self.subTest(raw=raw):
                self.server.raw_response = raw
                self.assertEqual(self.probe().summary["agents"]["openai"]["failure_kind"], "bad_response")
        self.server.raw_response = b" " * 1025
        with patch.object(http, "MAX_RESPONSE_BYTES", 1024):
            result = self.probe()
        self.assertEqual(result.summary["agents"]["openai"]["failure_kind"], "bad_response")

    def test_no_retries_and_provider_specific_failure_categories(self):
        for status, body, kind in [(401, b"bad key", "auth_invalid"), (404, b"model missing", "not_found"),
                                   (429, b"rate limit", "rate_limited"), (429, b"quota exceeded", "quota_exhausted"),
                                   (503, b"unavailable", "provider_error")]:
            with self.subTest(status=status, kind=kind):
                before = len(self.server.requests)
                self.server.status, self.server.raw_response = status, body
                result = self.probe()
                self.assertEqual(len(self.server.requests) - before, 1)
                self.assertEqual(result.status, "INFRASTRUCTURE_FAILURE")
                self.assertEqual(result.summary["agents"]["openai"]["failure_kind"], kind)
                self.assertEqual(result.summary["agents"]["openai"]["http_status"], status)

    def test_echoed_credentials_in_text_model_request_id_or_headers_are_suppressed(self):
        variants = [{"model": SECRET}, {"id": SECRET}, {"extra": SECRET},
                    {"output": [{"type": "message", "content": [{"type": "output_text", "text": SECRET}]}]}]
        for update in variants:
            with self.subTest(update=list(update)):
                self.server.behavior = lambda body: {**body, **update}
                result = self.probe()
                self.assertEqual(result.summary["agents"]["openai"]["failure_kind"], "credential_leak")
                self.assertNotIn(SECRET, json.dumps(result.to_json()))
        self.server.behavior = lambda body: body
        self.server.response_headers = {"x-request-id": SECRET}
        self.assertNotIn(SECRET, json.dumps(self.probe().to_json()))

    def test_credential_used_as_model_is_refused_before_network_or_output(self):
        self.conf["agents"]["openai"]["model_ref"] = "env:VERISLOP_PROBE_TEST_KEY"
        self.save()
        with self.assertRaises(UsageError) as raised:
            self.probe()
        self.assertNotIn(SECRET, str(raised.exception))
        self.assertEqual(self.server.requests, [])

    def test_general_broker_transcripts_never_receive_credential_echoes(self):
        self.server.behavior = lambda body: {**body, "id": SECRET}
        resolved = cfg.resolve(self.conf, self.profiles["profiles"])
        broker = Broker(resolved, self.root / "transcripts")
        from verislop.errors import InfrastructureError
        with self.assertRaises(InfrastructureError):
            broker.call("openai", "test", conformance.SYSTEM_PROMPT, 'Return:\n{"ok":true}', "test")
        for path in (self.root / "transcripts").glob("*.json"):
            self.assertNotIn(SECRET, path.read_text())

    def test_error_body_and_redirect_never_echo_secret_or_follow_location(self):
        for status in (400, 302, 304):
            with self.subTest(status=status):
                before = len(self.server.requests)
                self.server.status = status
                self.server.raw_response = SECRET.encode()
                self.server.response_headers = {"Location": f"http://127.0.0.1:{self.server.port}/{SECRET}"}
                result = self.probe()
                self.assertEqual(len(self.server.requests) - before, 1)
                self.assertNotIn(SECRET, json.dumps(result.to_json()))
                self.assertEqual(result.summary["agents"]["openai"]["failure_kind"], "bad_request")
        with patch.object(http, "MAX_ERROR_BYTES", 16):
            self.server.status = 400
            self.server.raw_response = SECRET.encode() * 100
            self.assertNotIn(SECRET, json.dumps(self.probe().to_json()))


if __name__ == "__main__":
    unittest.main()
