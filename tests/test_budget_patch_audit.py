"""Additional offline integration checks for shared token reservations.

Exercise the retained Ollama options, failure settlement and opt-in review DSL
through the actual Broker. No model service or credentials are used.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from verislop import agent_effects, canonical
from verislop.errors import InfrastructureError, UsageError
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker, Budget
from verislop.providers.config import Resolved
from verislop.providers.review_format import ollama_review_schema


MODEL = "local-model:test"
DIGEST = "a" * 64


def make_broker(budget, *, transcript_dir=None, ollama=False):
    agent = {"provider": "p", "model_ref": MODEL, "max_output_tokens": 70,
             "tool_profile": "review_readonly"}
    if ollama:
        agent.update(context_window_tokens=40960, review_response_format="json_schema",
                     proof_response_format="theorem_fragment",
                     model_identity={"model_digest_sha256": DIGEST})
    conf = {
        "review": {"budgets": {"max_calls_per_instance": 8,
                               "max_total_tokens": 100,
                               "max_provider_retries": 0}},
        "providers": {"p": {"concurrency": 2,
                              "api_family": "ollama_chat" if ollama else "responses",
                              "request_timeout_seconds": None}},
        "agents": {"a": agent},
    }
    resolved = Resolved(conf, {"p": {"base_url": "unused", "auth_scheme": "none"}},
                        {"p"}, {"a"})
    return Broker(resolved, transcript_dir, budget)


def completion():
    return Completion("{}", MODEL, MODEL, None, 10, 10)


class BudgetPatchIntegrationTests(unittest.TestCase):
    def test_enabled_dsl_budget_and_native_ollama_schema_work_together(self):
        system, user = "Review the exact artifact. é", "Untrusted packet:\n{\"case\":\"λ\"}"
        response = ('{"verdict":"ABSTAIN","reviewed_obligations":["O1"],'
                    '"search":{"method":"bounded fixture probe","attempted_cases":1,'
                    '"probes":[{"kind":"mechanical_failure","claim_id":"CURRENT:fixture"}],'
                    '"conclusion":"INCOMPLETE"},"findings":[],"limitations":["fixture"],'
                    '"rationale":"No acceptance claimed"}\n')
        reservation = len(system.encode("utf-8")) + len(user.encode("utf-8")) + 70
        budget = Budget(max_total_tokens=reservation, max_retries=1)
        schema = ollama_review_schema()
        requests = []

        def request(method, base, path, headers, payload, timeout):
            requests.append((method, path, payload))
            self.assertEqual(reservation, budget.reserved_tokens)
            self.assertEqual({"slot": 1}, budget.calls)
            if method == "GET" and path == "/api/tags":
                return {"models": [{"name": MODEL, "model": MODEL, "digest": DIGEST}]}, {}
            self.assertEqual(("POST", "/api/chat"), (method, path))
            self.assertEqual(schema, payload["format"])
            self.assertEqual([{"role": "system", "content": system},
                              {"role": "user", "content": user}], payload["messages"])
            self.assertEqual({"num_predict": 70, "temperature": 0, "num_ctx": 40960}, payload["options"])
            return {"model": MODEL, "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": response},
                    "prompt_eval_count": 10, "eval_count": 20}, {}

        with tempfile.TemporaryDirectory() as tmp:
            broker = make_broker(budget, transcript_dir=Path(tmp), ollama=True)
            broker.r.conf["agent_effect_dsl"] = {"enabled": True}
            broker.r.profiles["p"].update(adapter="ollama", base_url="http://127.0.0.1:1",
                                          families=["ollama_chat"], allow_insecure_loopback=True)
            with patch("verislop.providers.adapters.request", side_effect=request):
                result = agent_effects.review_call(broker, "a", "slot", system, user,
                                                  "release", "sha256:" + "c" * 64)
            self.assertEqual(response, result.text)
            self.assertEqual(DIGEST, result.model_digest_sha256)
            record = canonical.load_file(next(Path(tmp).glob("*.json")))
            self.assertEqual((system, user, response), (record["system"], record["user"], record["response"]))
            self.assertEqual({"mode": "json_schema", "schema": schema,
                              "schema_sha256": canonical.digest_json(schema)}, record["response_format"])
        self.assertEqual([("GET", "/api/tags"), ("POST", "/api/chat"), ("GET", "/api/tags")],
                         [(method, path) for method, path, _ in requests])
        self.assertEqual((30, 0, {"slot": 1}),
                         (budget.used_tokens, budget.reserved_tokens, budget.calls))

    def test_reservation_preserves_review_schema_proof_mode_and_transcripts(self):
        for purpose in ("review:release", "prove"):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as tmp:
                budget = Budget(max_total_tokens=100)
                broker = make_broker(budget, transcript_dir=Path(tmp), ollama=True)
                with patch("verislop.providers.broker.ollama_model_digest", return_value=DIGEST), \
                        patch("verislop.providers.broker.complete", return_value=completion()) as dispatch:
                    broker.call("a", "slot", "é", "payload", purpose)
                kwargs = dispatch.call_args.kwargs
                self.assertEqual(40960, kwargs["ollama_context_tokens"])
                record = canonical.load_file(next(Path(tmp).glob("*.json")))
                if purpose == "review:release":
                    schema = ollama_review_schema()
                    self.assertEqual(schema, kwargs["ollama_response_schema"])
                    self.assertEqual(canonical.digest_json(schema), record["response_format"]["schema_sha256"])
                    self.assertNotIn("ollama_json_mode", kwargs)
                else:
                    self.assertIs(False, kwargs["ollama_json_mode"])
                    self.assertNotIn("ollama_response_schema", kwargs)
                    self.assertNotIn("response_format", record)
                self.assertEqual(DIGEST, record["model_digest_sha256"])
                self.assertEqual((20, 0, {"slot": 1}),
                                 (budget.used_tokens, budget.reserved_tokens, budget.calls))

    def test_post_completion_identity_failure_releases_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            budget = Budget(max_total_tokens=100, max_retries=0)
            broker = make_broker(budget, transcript_dir=Path(tmp), ollama=True)
            with patch("verislop.providers.broker.ollama_model_digest", side_effect=[DIGEST, "b" * 64]), \
                    patch("verislop.providers.broker.complete", return_value=completion()) as dispatch:
                with self.assertRaises(InfrastructureError):
                    broker.call("a", "slot", "", "", "review:release")
                dispatch.assert_called_once()
            # Existing accounting intentionally excludes identity-invalid completions.
            self.assertEqual((0, 0, {"slot": 1}),
                             (budget.used_tokens, budget.reserved_tokens, budget.calls))
            record = canonical.load_file(next(Path(tmp).glob("*.json")))
            self.assertIsNone(record["response"])
            self.assertIn("catalog changed", record["error"])

    def test_transcript_failure_preserves_usage_and_releases_reservation(self):
        budget = Budget(max_total_tokens=100)
        broker = make_broker(budget, transcript_dir=Path("unused"))
        with patch("verislop.providers.broker.complete", return_value=completion()), \
                patch("verislop.providers.broker.fsutil.write_json", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                broker.call("a", "slot", "", "", "test")
        self.assertEqual((20, 0, {"slot": 1}),
                         (budget.used_tokens, budget.reserved_tokens, budget.calls))

    def test_invalid_retained_schema_option_releases_without_consuming_call(self):
        budget = Budget(max_total_tokens=100)
        broker = make_broker(budget)
        broker.r.conf["agents"]["a"]["review_response_format"] = "json_schema"
        with patch("verislop.providers.broker.complete") as dispatch:
            with self.assertRaises(UsageError):
                broker.call("a", "slot", "", "", "review:release")
            dispatch.assert_not_called()
        self.assertEqual((0, 0, {}), (budget.used_tokens, budget.reserved_tokens, budget.calls))

    def test_keyboard_interrupt_releases_reserved_tokens(self):
        budget = Budget(max_total_tokens=100)
        broker = make_broker(budget)
        with patch("verislop.providers.broker.complete", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                broker.call("a", "slot", "", "", "test")
        self.assertEqual((0, 0, {"slot": 1}),
                         (budget.used_tokens, budget.reserved_tokens, budget.calls))

    def test_shared_instance_call_limit_remains_atomic_and_refunds_second_reservation(self):
        budget = Budget(max_total_tokens=140, max_calls_per_instance=1)
        first, second = make_broker(budget), make_broker(budget)
        entered, release = threading.Event(), threading.Event()

        def dispatch(*args, **kwargs):
            entered.set()
            if not release.wait(timeout=3):
                raise AssertionError("provider release timed out")
            return completion()

        with patch("verislop.providers.broker.complete", side_effect=dispatch) as provider:
            with ThreadPoolExecutor(2) as pool:
                pending = pool.submit(first.call, "a", "shared", "", "", "test")
                try:
                    self.assertTrue(entered.wait(timeout=3))
                    with self.assertRaisesRegex(InfrastructureError, "call budget exhausted"):
                        second.call("a", "shared", "", "", "test")
                    self.assertEqual(70, budget.reserved_tokens)
                finally:
                    release.set()
                pending.result(timeout=3)
            provider.assert_called_once()
        self.assertEqual((20, 0, {"shared": 1}),
                         (budget.used_tokens, budget.reserved_tokens, budget.calls))

    def test_effect_dsl_lowering_cannot_bypass_prompt_admission(self):
        budget = Budget(max_total_tokens=100)
        broker = make_broker(budget)
        broker.r.conf["agent_effect_dsl"] = {"enabled": True}
        with patch("verislop.providers.broker.complete") as dispatch:
            with self.assertRaisesRegex(InfrastructureError, "token admission budget exhausted"):
                agent_effects.review_call(broker, "a", "slot", "", "x" * 31,
                                          "release", "sha256:" + "c" * 64)
            dispatch.assert_not_called()
        self.assertEqual((0, 0, {}), (budget.used_tokens, budget.reserved_tokens, budget.calls))
