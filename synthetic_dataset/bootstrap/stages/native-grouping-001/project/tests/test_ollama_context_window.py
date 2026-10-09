"""Per-agent Ollama context overrides, with HTTP mocks and no real inference."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ollama_provider import DIGEST, MODEL, OllamaServer

from verislop import canonical, schemas
from verislop.errors import InfrastructureError, UsageError
from verislop.providers import adapters, config, conformance
from verislop.providers.broker import Broker, Budget
from verislop.providers.http import ProviderError


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = "Return JSON only."
USER = 'Return only this JSON object:\n{"ok":true}'


class OllamaContextWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = OllamaServer()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-ollama-context-")
        self.root = Path(self.tmp.name)
        self.server.requests.clear()
        self.server.catalog = [{"name": MODEL, "model": MODEL, "digest": DIGEST}]
        self.server.behavior = lambda body: body
        self.server.after_chat = lambda: None
        self.conf = json.loads((ROOT / "examples/ollama-review-config.json").read_text())
        provider = self.conf["providers"]["local"]
        provider["endpoint_profile"] = "context-test"
        provider["request_timeout_seconds"] = None
        for agent in self.conf["agents"].values():
            agent["model_ref"] = MODEL
            agent["max_output_tokens"] = 128
            agent["model_identity"] = {"mode": "pinned", "resolved_model": MODEL,
                                       "model_digest_sha256": DIGEST}
        self.profiles = {"context-test": {"adapter": "ollama", "base_url": f"http://127.0.0.1:{self.server.port}",
                                         "auth_scheme": "none", "families": ["ollama_chat"],
                                         "allow_insecure_loopback": True}}

    def tearDown(self):
        self.tmp.cleanup()

    def broker(self, *, retries=0):
        return Broker(config.resolve(self.conf, self.profiles), self.root / "transcripts",
                      Budget(max_retries=retries))

    def call(self, agent="local-author", *, broker=None):
        return (broker or self.broker()).call(agent, agent + "/0", SYSTEM, USER, "context-test")

    def transcripts(self):
        return [canonical.load_file(path) for path in sorted((self.root / "transcripts").glob("*.json"))]

    def chats(self):
        return [request[3] for request in self.server.requests if request[0] == "POST"]

    def test_explicit_agent_context_is_sent_with_model_and_existing_options(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        completion = self.call()
        self.assertEqual(MODEL, completion.returned_model)
        self.assertEqual(DIGEST, completion.model_digest_sha256)
        self.assertEqual({"num_predict": 128, "temperature": 0, "num_ctx": 32768}, self.chats()[0]["options"])
        self.assertEqual(MODEL, self.chats()[0]["model"])
        self.assertIs(self.chats()[0]["stream"], False)
        self.assertIs(self.chats()[0]["think"], False)
        self.assertEqual(32768, self.transcripts()[0]["context_window_tokens"])
        self.assertEqual([("GET", "/api/tags"), ("POST", "/api/chat"), ("GET", "/api/tags")],
                         [request[:2] for request in self.server.requests])

    def test_omission_preserves_default_payload_and_records_no_override(self):
        self.call()
        self.assertEqual({"num_predict": 128, "temperature": 0}, self.chats()[0]["options"])
        self.assertNotIn("num_ctx", self.chats()[0]["options"])
        self.assertIsNone(self.transcripts()[0]["context_window_tokens"])
        self.assertNotIn("context_window_tokens", self.conf["agents"]["local-author"])

    def test_each_agent_uses_its_own_override(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        self.conf["agents"]["local-critic"]["context_window_tokens"] = 65536
        broker = self.broker()
        self.call(broker=broker)
        self.call("local-critic", broker=broker)
        self.assertEqual([32768, 65536], [body["options"]["num_ctx"] for body in self.chats()])
        self.assertEqual({"local-author": 32768, "local-critic": 65536},
                         {row["agent"]: row["context_window_tokens"] for row in self.transcripts()})

    def test_schema_load_and_resolve_preserve_context_boundaries(self):
        for value in (1024, 32768, 262144):
            with self.subTest(value=value):
                self.conf["agents"]["local-author"]["context_window_tokens"] = value
                self.assertEqual([], schemas.validate("review-config", self.conf))
                path = self.root / "config.json"
                path.write_bytes(canonical.dumps(self.conf))
                loaded = config.load(path)
                resolved = config.resolve(loaded, self.profiles)
                self.assertEqual(value, resolved.agent("local-author")["context_window_tokens"])
                self.assertFalse([d for d in resolved.diagnostics if d.severity == "blocking"], resolved.diagnostics)

    def test_noninteger_and_out_of_range_contexts_are_rejected_by_schema_and_resolution(self):
        for value in (0, -1, 1023, 262145, True, False, None, "32768", 1024.0, 32768.5):
            with self.subTest(value=value):
                self.conf["agents"]["local-author"]["context_window_tokens"] = value
                self.assertTrue(schemas.validate("review-config", self.conf))
                resolved = config.resolve(self.conf, self.profiles)
                self.assertTrue(any("context_window_tokens must be an integer" in d.message for d in resolved.diagnostics))
                with self.assertRaises(UsageError):
                    self.call(broker=Broker(resolved, None))
                self.assertEqual([], self.server.requests)

    def test_context_override_rejected_on_nonollama_agents_even_when_unused(self):
        cloud = json.loads((ROOT / "examples/review-config.json").read_text())
        for family in ("responses", "chat_completions", "anthropic_messages", "gemini_generate_content"):
            with self.subTest(family=family):
                conf = json.loads(json.dumps(cloud))
                provider = next(name for name, row in conf["providers"].items() if row["api_family"] == family)
                conf["agents"]["unused-context-agent"] = {"provider": provider, "model_ref": "mock-model",
                    "tool_profile": "candidate_writer", "max_output_tokens": 128, "context_window_tokens": 32768}
                self.assertEqual([], schemas.validate("review-config", conf))
                resolved = config.resolve(conf, {})
                self.assertTrue(any("agent unused-context-agent: context_window_tokens is supported only for Ollama" == d.message
                                    and d.severity == "blocking" for d in resolved.diagnostics))

    def test_direct_adapter_rejects_invalid_contexts_before_transport(self):
        profile = self.profiles["context-test"]
        for value in (0, 1023, 262145, -1, True, False, "32768", 32768.0):
            with self.subTest(value=value), patch.object(adapters, "request") as request:
                with self.assertRaises(ProviderError) as raised:
                    adapters.complete("ollama_chat", profile, "", MODEL, SYSTEM, USER, 128, None,
                                      ollama_context_tokens=value)
                self.assertEqual("bad_request", raised.exception.kind)
                request.assert_not_called()

    def test_direct_adapter_rejects_context_for_every_nonollama_family_before_transport(self):
        for family in ("responses", "chat_completions", "anthropic_messages", "gemini_generate_content"):
            with self.subTest(family=family), patch.object(adapters, "request") as request:
                with self.assertRaises(ProviderError) as raised:
                    adapters.complete(family, {}, "", MODEL, SYSTEM, USER, 128, None, ollama_context_tokens=32768)
                self.assertEqual("bad_request", raised.exception.kind)
                request.assert_not_called()

    def test_direct_adapter_accepts_context_limits(self):
        for value in (1024, 262144):
            with self.subTest(value=value):
                adapters.complete("ollama_chat", self.profiles["context-test"], "", MODEL, SYSTEM, USER, 128, None,
                                  ollama_context_tokens=value)
                self.assertEqual(value, self.chats()[-1]["options"]["num_ctx"])

    def test_inference_failure_transcript_retains_sent_context(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        self.server.behavior = lambda body: {**body, "done_reason": "length"}
        with self.assertRaises(InfrastructureError):
            self.call()
        row = self.transcripts()[0]
        self.assertEqual(32768, self.chats()[0]["options"]["num_ctx"])
        self.assertEqual(32768, row["context_window_tokens"])
        self.assertIn("bad_response", row["error"])
        self.assertIsNone(row["response"])

    def test_catalog_failure_before_inference_records_configured_context(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        self.server.catalog[0]["digest"] = "b" * 64
        with self.assertRaises(InfrastructureError):
            self.call()
        self.assertEqual([], self.chats())
        self.assertEqual(32768, self.transcripts()[0]["context_window_tokens"])
        self.assertIn("differs from the configured pin", self.transcripts()[0]["error"])

    def test_transcript_binds_call_context_even_if_configuration_changes_after_inference(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        self.server.after_chat = lambda: self.conf["agents"]["local-author"].update(context_window_tokens=65536)
        self.call()
        self.assertEqual(32768, self.chats()[0]["options"]["num_ctx"])
        self.assertEqual(32768, self.transcripts()[0]["context_window_tokens"])
        self.assertEqual(65536, self.conf["agents"]["local-author"]["context_window_tokens"])

    def test_failure_transcript_binds_call_context_when_catalog_changes(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        def change():
            self.conf["agents"]["local-author"]["context_window_tokens"] = 65536
            self.server.catalog[0]["digest"] = "b" * 64
        self.server.after_chat = change
        with self.assertRaises(InfrastructureError):
            self.call()
        self.assertEqual(32768, self.chats()[0]["options"]["num_ctx"])
        self.assertEqual(32768, self.transcripts()[0]["context_window_tokens"])
        self.assertIn("changed during inference", self.transcripts()[0]["error"])

    def test_conformance_probe_preserves_configured_context(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        path = self.root / "config.json"
        profiles = self.root / "profiles.json"
        path.write_bytes(canonical.dumps(self.conf))
        profiles.write_bytes(canonical.dumps({"schema_version": "0.1", "artifact_kind": "endpoint_profiles", "profiles": self.profiles}))
        result = conformance.run(path, ["local-author"], live=True, profiles=profiles)
        self.assertEqual("PASS", result.status, result.to_json())
        self.assertEqual(32768, self.chats()[0]["options"]["num_ctx"])

    def test_retry_uses_same_context_and_transcript_records_final_attempt_count(self):
        self.conf["agents"]["local-author"]["context_window_tokens"] = 32768
        contexts = []
        def transport(method, base, path, headers, payload, timeout):
            if method == "GET":
                return {"models": self.server.catalog}, {}
            contexts.append(payload["options"]["num_ctx"])
            if len(contexts) == 1:
                self.conf["agents"]["local-author"]["context_window_tokens"] = 65536
                raise ProviderError("provider_error", "mock retryable failure", 500, retryable=True)
            return {"model": MODEL, "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": '{"ok":true}'},
                    "prompt_eval_count": 10, "eval_count": 4}, {}
        with patch.object(adapters, "request", side_effect=transport), patch("verislop.providers.broker.time.sleep"):
            self.call(broker=self.broker(retries=1))
        self.assertEqual([32768, 32768], contexts)
        self.assertEqual(32768, self.transcripts()[0]["context_window_tokens"])
        self.assertEqual(2, self.transcripts()[0]["attempts"])


if __name__ == "__main__":
    unittest.main()
