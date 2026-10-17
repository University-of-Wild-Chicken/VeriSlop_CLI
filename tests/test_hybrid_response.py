"""Exercise the waiting consumer, including direct publisher bypass attempts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock, Thread
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from verislop import canonical
from verislop.errors import InfrastructureError
from synthetic_dataset.tools import hybrid_response
from synthetic_dataset.tools import run_local_hybrid as hybrid
from synthetic_dataset.tools.sol_data_pipeline_worker import MailboxTransport, MODEL, atomic_json


class HybridResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.task = "G01-inference-admission"
        self.protocol = {"tasks": [self.task], "relay_mode": "file",
                         "sol_routes": {"sol-prover": ["prove-vscore"]}}
        atomic_json(self.out / "protocol.json", self.protocol)
        self.verify = patch.object(hybrid, "verify_inputs", return_value=self.protocol)
        self.verify.start()
        self.addCleanup(self.verify.stop)

    def consume(self, mutate=lambda envelope, request: None, *, validator=True):
        mailbox = self.out / "tasks" / self.task / "mailbox"
        transport = MailboxTransport(mailbox, 1, poll_seconds=0.01,
            response_validator=(lambda path, envelope: hybrid_response.validate_response(
                self.out, self.task, path, envelope)) if validator else None)
        broker = SimpleNamespace(r=SimpleNamespace(diagnostics=[], agent=lambda _: {"max_output_tokens": 64}),
            model_for=lambda _: MODEL, budget=SimpleNamespace(lock=Lock(), calls={}, max_calls_per_instance=1),
            _log=lambda *args: None)
        result = {}

        def worker():
            try:
                result["completion"] = transport.call(broker, "sol-prover", "proof/1", "S", "U", "prove-vscore")
            except Exception as exc:
                result["error"] = exc

        thread = Thread(target=worker, daemon=True)
        thread.start()
        request_path = mailbox / "request-0001.json"
        deadline = time.monotonic() + 3
        while not request_path.is_file() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(request_path.is_file())
        request = canonical.load_file(request_path)
        binding = hybrid_response._relay_binding(self.out, self.task, request_path,
                                                 request, self.protocol, create_carrier=True)
        envelope = {"transport": "collaboration", "requested_model": MODEL, "request_id": "0001",
            "request_sha256": canonical.digest_file(request_path), "agent_task_id": "/root/fresh_sol",
            "text": "EXACT OUTPUT\n", "task": self.task,
            "protocol_sha256": canonical.digest_file(self.out / "protocol.json"),
            "model_override": MODEL, "fork_turns": "none", "model_identity_attested": False,
            **{key: binding[key] for key in ("carrier_path", "carrier_sha256", "spawn_message_sha256")}}
        mutate(envelope, request_path)
        atomic_json(mailbox / "response-0001.json", envelope)
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        return result, transport, mailbox

    def test_legitimate_exact_envelope_is_consumed_and_receipted(self):
        result, transport, mailbox = self.consume()
        self.assertEqual("EXACT OUTPUT\n", result["completion"].text)
        self.assertEqual(1, transport.state["responses"])
        self.assertTrue((mailbox / "response-receipt-0001.json").is_file())

    def test_direct_publisher_with_wrong_protocol_is_rejected_before_completion(self):
        result, transport, mailbox = self.consume(lambda env, _: env.update(protocol_sha256="sha256:wrong"))
        self.assertIsInstance(result["error"], InfrastructureError)
        self.assertNotIn("completion", result)
        self.assertEqual(0, transport.state["responses"])
        self.assertFalse((mailbox / "response-receipt-0001.json").exists())
        self.assertTrue((mailbox / "response-0001.json").exists())

    def test_direct_publisher_with_wrong_fork_is_rejected(self):
        result, _, _ = self.consume(lambda env, _: env.update(fork_turns="all"))
        self.assertIsInstance(result["error"], InfrastructureError)

    def test_direct_publisher_with_attestation_claim_is_rejected(self):
        result, _, _ = self.consume(lambda env, _: env.update(model_identity_attested=True))
        self.assertIsInstance(result["error"], InfrastructureError)

    def test_mutated_carrier_cannot_be_consumed(self):
        def mutate(envelope, _):
            path = Path(envelope["carrier_path"])
            path.chmod(0o600)
            path.write_bytes(path.read_bytes() + b"\n")
        result, _, _ = self.consume(mutate)
        self.assertIsInstance(result["error"], InfrastructureError)

    def test_missing_recorded_carrier_cannot_be_consumed(self):
        result, _, _ = self.consume(lambda env, _: Path(env["carrier_path"]).unlink())
        self.assertIsInstance(result["error"], InfrastructureError)

    def test_cross_task_agent_reuse_is_rejected(self):
        atomic_json(self.out / "tasks" / "prior" / "mailbox" / "response-0001.json",
                    {"agent_task_id": "/root/fresh_sol"})
        result, _, _ = self.consume()
        self.assertIsInstance(result["error"], InfrastructureError)

    def test_default_legacy_consumer_is_unchanged(self):
        result, _, _ = self.consume(lambda env, _: env.update(fork_turns="all"), validator=False)
        self.assertEqual("EXACT OUTPUT\n", result["completion"].text)


if __name__ == "__main__":
    unittest.main()
