"""Native local Ollama protocol, identity checks, and credential-free CLI probes."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, schemas
from verislop.errors import InfrastructureError, UsageError
from verislop.providers import check, config, conformance
from verislop.providers.broker import Broker


MODEL = "local-qwen:27b-q3"
DIGEST = "a" * 64
ROOT = Path(__file__).resolve().parents[1]


class OllamaServer:
    def __init__(self):
        self.requests = []
        self.catalog = [{"name": MODEL, "model": MODEL, "digest": DIGEST}]
        self.behavior = lambda body: body
        self.after_chat = lambda: None
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, response):
                data = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                mock.requests.append(("GET", self.path, dict(self.headers), None))
                self.respond({"models": mock.catalog})

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                mock.requests.append(("POST", self.path, dict(self.headers), body))
                text = body["messages"][-1]["content"].split("\n", 1)[1]
                self.respond(mock.behavior({"model": body["model"], "done": True, "done_reason": "stop",
                                           "message": {"role": "assistant", "content": text},
                                           "prompt_eval_count": 31, "eval_count": 20}))
                mock.after_chat()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class OllamaProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = OllamaServer()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-ollama-")
        self.root = Path(self.tmp.name)
        self.server.requests.clear()
        self.server.catalog = [{"name": MODEL, "model": MODEL, "digest": DIGEST}]
        self.server.behavior = lambda body: body
        self.server.after_chat = lambda: None
        self.conf = json.loads((ROOT / "examples/review-config.json").read_text())
        self.conf["providers"] = {"local": {"adapter": "ollama", "api_family": "ollama_chat",
                                            "endpoint_profile": "local-test", "concurrency": 1,
                                            "request_timeout_seconds": 5}}
        self.conf["agents"] = {"qwen": {"provider": "local", "model_ref": MODEL,
                                         "tool_profile": "review_readonly", "max_output_tokens": 128,
                                         "model_identity": {"mode": "pinned", "resolved_model": MODEL,
                                                            "model_digest_sha256": DIGEST}}}
        self.conf["roles"] = {role: "qwen" for role in self.conf["roles"]}
        self.conf["review"]["review_tiers"] = [{"id": "R0", "reviewers": [{"agent": "qwen", "count": 1, "focus": "counterexamples"}],
                                                  "consensus": {"mode": "unanimous", "require_all_responses": True,
                                                                "max_soft_rejects": 0, "max_abstentions": 0,
                                                                "blocking_findings_veto": True}}]
        self.profiles = {"schema_version": "0.1", "artifact_kind": "endpoint_profiles", "profiles": {
            "local-test": {"adapter": "ollama", "base_url": f"http://127.0.0.1:{self.server.port}",
                           "auth_scheme": "none", "families": ["ollama_chat"],
                           "auth_check": "GET /api/tags", "allow_insecure_loopback": True}}}
        self.config_path = self.root / "config.json"
        self.profiles_path = self.root / "profiles.json"
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.config_path.write_text(json.dumps(self.conf))
        self.profiles_path.write_text(json.dumps(self.profiles))

    def broker(self):
        return Broker(config.resolve(config.load(self.config_path), config.load_user_profiles(self.profiles_path)), self.root / "transcripts")

    def call(self):
        return self.broker().call("qwen", "qwen-0", "Return JSON only.", 'Return only this JSON object:\n{"ok":true}', "test")

    def test_offline_check_does_not_read_credentials_or_use_network(self):
        with patch("verislop.auth.resolve", side_effect=AssertionError("no local credential")):
            result = check.run(self.config_path, profiles=self.profiles_path)
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertEqual(self.server.requests, [])
        self.assertEqual(result.summary["providers"]["local"]["credential_ref"], "none")

    def test_builtin_profile_and_explicit_none_credential(self):
        self.conf["providers"]["local"]["endpoint_profile"] = "ollama-local"
        self.conf["providers"]["local"]["credential_ref"] = "none"
        self.save()
        result = check.run(self.config_path)
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertEqual(result.summary["providers"]["local"]["base_url"], "http://localhost:11434")

    def test_live_check_lists_models_without_inference_or_auth_header(self):
        self.profiles["profiles"]["local-test"].pop("auth_check")
        self.save()
        result = check.run(self.config_path, live=True, profiles=self.profiles_path)
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertTrue(result.summary["providers"]["local"]["live_check"]["ok"])
        self.assertEqual(result.summary["providers"]["local"]["live_check"]["available_models"],
                         [{"name": MODEL, "model_digest_sha256": DIGEST, "installed_on_configured_server": True}])
        self.assertEqual([r[:2] for r in self.server.requests], [("GET", "/api/tags")])
        self.assertNotIn("Authorization", self.server.requests[0][2])

    def test_probe_uses_native_json_api_and_records_installed_digest(self):
        result = conformance.run(self.config_path, ["qwen"], live=True, profiles=self.profiles_path)
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertEqual(result.summary["agents"]["qwen"]["model_digest_sha256"], DIGEST)
        self.assertEqual([r[:2] for r in self.server.requests], [("GET", "/api/tags"), ("POST", "/api/chat"), ("GET", "/api/tags")])
        _, _, headers, body = self.server.requests[1]
        self.assertNotIn("Authorization", headers)
        self.assertEqual(body["format"], "json")
        self.assertIs(body["stream"], False)
        self.assertIs(body["think"], False)
        self.assertEqual(body["options"], {"num_predict": 128, "temperature": 0})
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertFalse((self.root / "transcripts").exists())

    def test_broker_logs_model_digest(self):
        comp = self.call()
        self.assertEqual(comp.model_digest_sha256, DIGEST)
        transcript = canonical.load_file(next((self.root / "transcripts").glob("*.json")))
        self.assertEqual(transcript["model_digest_sha256"], DIGEST)

    def test_wrong_pinned_digest_prevents_inference(self):
        self.conf["agents"]["qwen"]["model_identity"]["model_digest_sha256"] = "b" * 64
        self.save()
        with self.assertRaisesRegex(InfrastructureError, "differs from the configured pin"):
            self.call()
        self.assertEqual([r[0] for r in self.server.requests], ["GET"])

    def test_catalog_replacement_during_inference_is_rejected(self):
        def replace():
            self.server.catalog[0]["digest"] = "b" * 64
        self.server.after_chat = replace
        with self.assertRaisesRegex(InfrastructureError, "changed during inference"):
            self.call()

    def test_missing_or_remote_models_are_not_pulled_or_sent(self):
        for catalog in ([], [{"name": MODEL, "digest": DIGEST, "remote_host": "https://ollama.com"}]):
            with self.subTest(catalog=catalog):
                self.server.requests.clear()
                self.server.catalog = catalog
                with self.assertRaises(InfrastructureError):
                    self.call()
                self.assertEqual([r[:2] for r in self.server.requests], [("GET", "/api/tags")])

    def test_truncated_unfinished_error_tool_and_model_mismatch_are_rejected(self):
        for change in ({"done": False}, {"done_reason": "length"}, {"error": "failure"}, {"model": "another:tag"},
                       {"message": {"role": "assistant", "content": "{}", "tool_calls": [{}]}}):
            with self.subTest(change=change):
                self.server.behavior = lambda body, change=change: {**body, **change}
                with self.assertRaises(InfrastructureError):
                    self.call()

    def test_server_url_rejects_queries_and_embedded_credentials(self):
        for url in ("https://localhost/?x=1", "https://user:pass@localhost", "https://localhost:70000"):
            with self.subTest(url=url):
                self.profiles["profiles"]["local-test"]["base_url"] = url
                self.save()
                result = check.run(self.config_path, live=True, profiles=self.profiles_path)
                self.assertEqual(result.status, "BLOCKED", result.to_json())
                self.assertEqual(self.server.requests, [])
                with self.assertRaises(UsageError):
                    self.call()

    def test_direct_live_check_cannot_bypass_endpoint_validation(self):
        self.profiles["profiles"]["local-test"]["base_url"] = "https://remote.example/?query=1"
        self.save()
        with patch("verislop.providers.adapters.request", side_effect=AssertionError("invalid endpoint must not run")):
            result = check.live_auth_check("local-test", "none", self.profiles_path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["kind"], "bad_request")

    def test_cloud_credentials_stay_required(self):
        for adapter, credential in (("openai", None), ("openai", "none")):
            with self.subTest(adapter=adapter, credential=credential):
                self.conf["providers"]["local"]["adapter"] = adapter
                self.conf["providers"]["local"].pop("credential_ref", None)
                if credential is not None:
                    self.conf["providers"]["local"]["credential_ref"] = credential
                self.assertTrue(schemas.validate("review-config", self.conf))

    def test_user_selects_another_installed_model_without_a_digest_pin(self):
        selected = "my-organization/custom-model:experimental"
        self.conf["agents"]["qwen"]["model_ref"] = selected
        self.conf["agents"]["qwen"].pop("model_identity")
        self.server.catalog = [{"name": selected, "digest": "c" * 64}]
        self.save()
        comp = self.call()
        self.assertEqual(comp.requested_model, selected)
        self.assertEqual(comp.returned_model, selected)
        self.assertEqual(comp.model_digest_sha256, "c" * 64)
        self.assertEqual(self.server.requests[1][3]["model"], selected)

    def test_user_server_https_and_http_opt_in_configuration(self):
        prof = self.profiles["profiles"]["local-test"]
        prof["base_url"] = "https://my-ollama.example/ollama"
        self.save()
        result = check.run(self.config_path, profiles=self.profiles_path)
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertEqual(self.server.requests, [])
        prof["base_url"] = "http://my-ollama.example:11434/ollama"
        self.save()
        with self.assertRaisesRegex(UsageError, "allow_insecure_http"):
            config.load_user_profiles(self.profiles_path)
        prof["allow_insecure_http"] = True
        self.save()
        result = check.run(self.config_path, profiles=self.profiles_path)
        self.assertEqual(result.status, "PASS", result.to_json())

    def test_server_url_prefix_is_used_for_native_requests(self):
        self.profiles["profiles"]["local-test"]["base_url"] += "/user-ollama"
        self.save()
        comp = self.call()
        self.assertEqual(comp.requested_model, MODEL)
        self.assertEqual([r[1] for r in self.server.requests],
                         ["/user-ollama/api/tags", "/user-ollama/api/chat", "/user-ollama/api/tags"])

    def test_custom_https_server_is_used_by_broker_without_model_substitution(self):
        chosen_server = "https://my-ollama.example/team-models"
        self.profiles["profiles"]["local-test"]["base_url"] = chosen_server
        self.save()
        observed = []
        def request(method, base, path, headers, payload, timeout):
            observed.append((method, base, path, headers))
            if method == "GET":
                return {"models": self.server.catalog}, {}
            self.assertEqual(payload["model"], MODEL)
            return {"model": MODEL, "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": '{"ok":true}'},
                    "prompt_eval_count": 10, "eval_count": 5}, {}
        with patch("verislop.providers.adapters.request", side_effect=request):
            comp = self.call()
        self.assertEqual(comp.requested_model, MODEL)
        self.assertEqual(observed, [("GET", chosen_server, "/api/tags", {}),
                                    ("POST", chosen_server, "/api/chat", {}),
                                    ("GET", chosen_server, "/api/tags", {})])

    def test_optional_bearer_auth_applies_to_catalog_and_inference(self):
        self.profiles["profiles"]["local-test"]["auth_scheme"] = "bearer"
        self.conf["providers"]["local"]["credential_ref"] = "env:OLLAMA_TEST_TOKEN"
        self.save()
        with patch.dict("os.environ", {"OLLAMA_TEST_TOKEN": "protected-ollama-test-token"}):
            comp = self.call()
        self.assertEqual(comp.returned_model, MODEL)
        self.assertTrue(all(r[2].get("Authorization") == "Bearer protected-ollama-test-token" for r in self.server.requests))

    def test_auth_scheme_and_credential_reference_must_agree(self):
        self.conf["providers"]["local"]["credential_ref"] = "env:UNUSED_OLLAMA_TOKEN"
        self.save()
        result = check.run(self.config_path, profiles=self.profiles_path)
        self.assertEqual(result.status, "BLOCKED", result.to_json())
        self.conf["providers"]["local"].pop("credential_ref")
        self.profiles["profiles"]["local-test"]["auth_scheme"] = "bearer"
        self.save()
        result = check.run(self.config_path, profiles=self.profiles_path)
        self.assertEqual(result.status, "BLOCKED", result.to_json())

    def test_unresolved_server_profile_without_credentials_is_an_explicit_error(self):
        self.conf["providers"]["local"]["endpoint_profile"] = "unknown-user-server"
        self.save()
        result = check.run(self.config_path, profiles=self.profiles_path)
        self.assertEqual(result.status, "BLOCKED", result.to_json())
        probe = conformance.run(self.config_path, ["qwen"], live=True, profiles=self.profiles_path)
        self.assertEqual(probe.status, "BLOCKED", probe.to_json())
        self.assertEqual(self.server.requests, [])


if __name__ == "__main__":
    unittest.main()
