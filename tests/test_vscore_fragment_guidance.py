"""Changing a proof response envelope must retain the bridge environment."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from verislop import agents


class VSCoreFragmentGuidanceTests(unittest.TestCase):
    def test_fragment_keeps_checked_readable_and_transport_guidance(self):
        conf = {"agents": {"pyth": {"proof_response_format": "theorem_fragment"}}}
        with patch.object(agents, "recorded_call", return_value=SimpleNamespace(text="response")) as call, \
             patch("verislop.proof_fragments.expected_headers", return_value=["theorem edge : True"]), \
             patch("verislop.proof_fragments.assemble", return_value="assembled"), \
             patch("verislop.agent_memory.capture_context"):
            result = agents._proof_completion(None, conf, None, None, "pyth", "i",
                agents.VSCORE3_PROVER_SYSTEM, "EXACT CONTEXT", "prove-vscore", "frozen", None,
                lambda x: x)
        self.assertEqual(("assembled", "response"), result)
        self.assertEqual(agents.FRAGMENT_PROVER_SYSTEM, call.call_args.args[4])
        user = call.call_args.args[5]
        self.assertTrue(user.startswith("EXACT CONTEXT"))
        self.assertIn("Readable.source_eq_<symbol>", user)
        self.assertIn("foldl_transport", user)
        self.assertNotIn("Return ONLY the complete proof module", user)
        self.assertEqual("prove-vscore", call.call_args.args[6])

    def test_complete_file_keeps_original_system_and_context(self):
        conf = {"agents": {"sol": {}}}
        with patch.object(agents, "recorded_call", return_value=SimpleNamespace(text="exact module")) as call:
            result = agents._proof_completion(None, conf, None, None, "sol", "i",
                agents.VSCORE3_PROVER_SYSTEM, "EXACT CONTEXT", "prove-vscore", "frozen", None,
                lambda x: x)
        self.assertEqual(("exact module", "exact module"), result)
        self.assertEqual(agents.VSCORE3_PROVER_SYSTEM, call.call_args.args[4])
        self.assertEqual("EXACT CONTEXT", call.call_args.args[5])


if __name__ == "__main__":
    unittest.main()
