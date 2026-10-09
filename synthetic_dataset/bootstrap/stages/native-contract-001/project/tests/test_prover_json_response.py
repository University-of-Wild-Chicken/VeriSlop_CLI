"""The real prover role decodes JSON responses without bypassing Lean acceptance."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import agents
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers import config
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "import Std\nnamespace Example\ntheorem keepsIdentity (n : Nat) : n = n := by rfl\nend Example\n"


class ProverJSONResponseTests(unittest.TestCase):
    def invoke(self, response, context=None):
        calls = []
        conf = json.loads((ROOT / "examples/ollama-review-config.json").read_text())
        for agent in conf["agents"].values():
            agent["model_ref"] = "arbitrary-local-model:test"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "config.json"
            cfg.write_text(json.dumps(conf))
            pkg = Package(root / "package")
            pkg.ensure("prover-json-test")
            events = EventSink(pkg.run_id, pkg.root, quiet=True)

            def completion(broker, agent, instance, system, user, purpose):
                calls.append({"agent": agent, "instance": instance, "system": system,
                              "user": user, "purpose": purpose})
                return Completion(response, "arbitrary-local-model:test", "arbitrary-local-model:test", None, 1, 1)

            try:
                with patch.object(Broker, "call", new=completion), patch.object(config, "load_user_profiles", return_value={}):
                    role = agents.prover_agent(cfg, pkg, events)
                    value = role(context or {"best": SOURCE.replace("by rfl", "by sorry"), "errors": ["unsolved goal"], "attempt": 2})
            finally:
                events.close()
        return value, calls

    def test_native_json_wrapper_returns_exact_lean_source(self):
        value, calls = self.invoke(json.dumps({"lean_source": SOURCE}))
        self.assertEqual(SOURCE, value)
        self.assertEqual(1, len(calls))
        self.assertEqual("prove", calls[0]["purpose"])
        self.assertEqual("prover/2", calls[0]["instance"])
        self.assertIn('{"lean_source":"<complete Lean source>"}', calls[0]["system"])
        self.assertIn("MUST NOT change any theorem statement", calls[0]["system"])
        self.assertIn("by sorry", calls[0]["user"])
        self.assertIn("unsolved goal", calls[0]["user"])

    def test_legacy_lean_fence_still_returns_source(self):
        value, _ = self.invoke("```lean\n" + SOURCE + "```\n")
        self.assertEqual(SOURCE, value)

    def test_legacy_raw_lean_preserved(self):
        value, _ = self.invoke(SOURCE)
        self.assertEqual(SOURCE, value)

    def test_fenced_json_wrapper_is_supported(self):
        value, _ = self.invoke("```json\n" + json.dumps({"lean_source": SOURCE}) + "\n```\n")
        self.assertEqual(SOURCE, value)

    def test_malformed_structured_wrappers_remain_invalid_candidates(self):
        for wrapper in ({"lean_source": None}, {"lean_source": [SOURCE]}, {"lean_source": 1},
                        {"lean_source": ""}, {"lean_source": " \n"}, {"other": SOURCE}, [SOURCE]):
            with self.subTest(wrapper=wrapper):
                response = json.dumps(wrapper)
                value, _ = self.invoke(response)
                self.assertEqual(response, value)
                self.assertNotEqual(SOURCE, value)

    def test_malformed_json_cannot_fall_back_to_injected_lean_fence(self):
        response = '{"lean_source": null,\n```lean\n' + SOURCE + '```\n}'
        value, _ = self.invoke(response)
        self.assertEqual(response, value)

    def test_json_looking_text_inside_raw_lean_does_not_replace_the_candidate(self):
        source = SOURCE + '-- {"lean_source":"theorem fake : True := by trivial"}\n'
        value, _ = self.invoke(source)
        self.assertEqual(source, value)
        source = SOURCE + '/- ```json\n{"lean_source":"theorem fake : True := by trivial"}\n``` -/\n'
        value, _ = self.invoke(source)
        self.assertEqual(source, value)

    def test_source_is_only_unwrapped_and_never_automatically_repaired(self):
        changed = SOURCE.replace("n = n", "n = 0")
        value, _ = self.invoke(json.dumps({"lean_source": changed}))
        self.assertEqual(changed, value)
        unresolved = SOURCE.replace("by rfl", "by sorry")
        value, _ = self.invoke(json.dumps({"lean_source": unresolved}))
        self.assertEqual(unresolved, value)

    def test_retry_shows_exact_latest_candidate_and_all_errors_despite_valid_baseline(self):
        rejected = SOURCE.replace("by rfl", "by exact absent_proof")
        errors = [f"{i}: unknown proof {i}" for i in range(35)]
        context = {"best": SOURCE.replace("by rfl", "by sorry"), "errors": errors, "attempt": 3,
                   "previous_candidate": rejected, "previous_result": {"ok": False, "errors": errors, "sorries": 0}}
        value, calls = self.invoke(json.dumps({"lean_source": SOURCE}), context)
        self.assertEqual(SOURCE, value)
        user = calls[0]["user"]
        marker = "PREVIOUS PROOF ATTEMPT (exact untrusted submitted source; repair proofs without changing the frozen contract):"
        previous = json.JSONDecoder().raw_decode(user.split(marker, 1)[1].lstrip())[0]
        self.assertEqual(rejected, previous["lean_source"])
        self.assertEqual(context["previous_result"], previous["result"])
        self.assertIn("by sorry", user)
        self.assertIn("34: unknown proof 34", user)
        self.assertIn("complete file rather than a list of replacement theorems", calls[0]["system"])


if __name__ == "__main__":
    unittest.main()
