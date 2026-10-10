"""Authored Sol protocol/transport fixtures; no model calls or measured results."""
from __future__ import annotations

from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from synthetic_dataset.arm_worker import RAW_SYSTEM
from synthetic_dataset.tools import sol_data_pipeline_poc as poc
from synthetic_dataset.tools import sol_data_pipeline_worker as worker
from synthetic_dataset.tools import luna_worker
from synthetic_dataset.tools.data_pipeline_oracle import TASKS
from verislop import canonical, schemas
from verislop.errors import InfrastructureError
from verislop.providers import config
from verislop.providers.broker import Broker

ZERO = "sha256:" + "0" * 64


class SolProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="authored-sol-protocol-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "fixture-repository"
        self.repo.mkdir()
        (self.repo / "fixture.py").write_bytes(b"# Authored source-freeze fixture only\n")
        self.frozen = {"fixture.py": canonical.digest_file(self.repo / "fixture.py")}
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(poc.native, "REPO", self.repo))
        stack.enter_context(patch.object(poc, "source_inventory", return_value=self.frozen))
        stack.enter_context(patch.object(poc.checker, "check_preregistration", return_value={"root": ZERO}))
        self.cohort = self.root / "fixture-paired-cohort"
        self.protocol = poc.prepare(self.cohort)

    def request(self, *, task=TASKS[0], arm="raw", request_id="0001"):
        directory = self.cohort / "artifacts" / task / arm / "mailbox"
        worker.atomic_json(self.cohort / "active-arm.json", {"task": task, "arm": arm, "phase": "generation"})
        request = {"format": "verislop.collaboration-request/0.1", "request_id": request_id,
                   "agent": "author", "instance": "raw/1" if arm == "raw" else "formalizer/1",
                   "purpose": "raw-coding" if arm == "raw" else "formalize", "system": "Exact SYSTEM λ\n",
                   "user": "Exact USER e\u0301 🐈\n", "requested_model": worker.MODEL, "transport": "collaboration",
                   "max_response_bytes": worker.MAX_RESPONSE_BYTES, "requested_max_output_tokens": 8192,
                   "output_token_limit_enforced": False}
        worker.atomic_json(directory / f"request-{request_id}.json", request)
        return poc.pending_request(self.cohort)

    def envelope(self, pending, *, agent="/root/authored_sol_protocol_leaf", text="Exact final λ\n"):
        result = {key: pending[key] for key in ("task", "arm", "request_sha256", "supplemental_protocol_root",
                                               "spawn_message_sha256", "model_override", "fork_turns", "carrier_path", "carrier_sha256")}
        result.update(transport="collaboration", requested_model=worker.MODEL, relay_mode="file",
                      request_id=pending["request"]["request_id"], agent_task_id=agent, text=text,
                      model_identity_attested=False)
        return result

    def test_exact_model_alternating_pairs_common_bounds_and_no_deadlines(self):
        self.assertEqual("gpt-6.1-sol", worker.MODEL)
        self.assertEqual(["raw", "strict", "strict", "raw", "raw", "strict"], [row["arm"] for row in poc.pair_order()])
        self.assertEqual(list(TASKS), self.protocol["tasks"])
        self.assertEqual((1, 128, 24, 2, 8192), tuple(self.protocol[key] for key in
                         ("raw_calls_per_task", "strict_calls_per_task", "max_calls_per_instance", "contract_repair_rounds", "schema_output_tokens_hint")))
        conf = worker.configuration()
        self.assertEqual(524288, conf["review"]["budgets"]["max_total_tokens"])
        self.assertEqual([], schemas.validate("review-config", conf))
        self.assertFalse(conf["review"]["require_fixed_model_snapshot"])
        self.assertEqual(1, conf["review"]["review_tiers"][0]["reviewers"][0]["count"])
        self.assertFalse(self.protocol["model_identity_attested"])
        self.assertFalse(self.protocol["output_token_limit_enforced"])
        self.assertEqual("none", self.protocol["fork_turns"])
        for field in ("model_generation_deadline", "proof_search_deadline", "review_tier_deadline", "returned_model", "input_tokens", "output_tokens"):
            self.assertIsNone(self.protocol[field])
        self.assertEqual(self.protocol, poc.verify_inputs(self.cohort))
        with self.assertRaises(ValueError):
            poc.prepare(self.cohort)
        self.assertEqual("gpt-6-luna", luna_worker.MODEL)
        self.assertEqual("gpt-6-luna", luna_worker.configuration()["agents"]["author"]["model_ref"])

    def test_exact_carrier_final_and_arm_binding_survive_submit(self):
        pending = self.request()
        carrier = canonical.load_file(Path(pending["carrier_path"]))
        self.assertEqual(pending["request"]["system"], carrier["system"])
        self.assertEqual(pending["request"]["user"], carrier["user"])
        self.assertEqual(pending["carrier_sha256"], canonical.digest_file(Path(pending["carrier_path"])))
        self.assertNotIn(pending["request"]["user"], pending["agent_message"])
        self.assertEqual(pending["spawn_message_sha256"], canonical.digest(pending["agent_message"].encode()))
        envelope = self.envelope(pending)
        publication = poc.submit_response(self.cohort, envelope)
        self.assertEqual(envelope, canonical.load_file(Path(publication["published"])))
        self.assertIsNone(poc.pending_request(self.cohort))
        with self.assertRaises(ValueError):
            poc.submit_response(self.cohort, envelope)

    def test_wrong_model_context_task_arm_hash_or_attestation_cannot_be_delivered(self):
        pending = self.request()
        original = self.envelope(pending)
        for key, value in (("requested_model", "gpt-6-luna"), ("model_override", "gpt-6-sol"), ("fork_turns", "all"),
                           ("task", TASKS[1]), ("arm", "strict"), ("request_sha256", ZERO),
                           ("spawn_message_sha256", ZERO), ("carrier_sha256", ZERO),
                           ("supplemental_protocol_root", ZERO), ("model_identity_attested", True), ("model_identity_attested", 0)):
            with self.subTest(key=key), self.assertRaises((ValueError, InfrastructureError)):
                poc.submit_response(self.cohort, {**original, key: value})
        with self.assertRaises(InfrastructureError):
            poc.submit_response(self.cohort, {**original, "text": "x" * (worker.MAX_RESPONSE_BYTES + 1)})
        self.assertFalse(Path(pending["request_path"]).with_name("response-0001.json").exists())

    def test_fresh_agent_cannot_be_reused_across_arms_or_tasks(self):
        first = self.request()
        poc.submit_response(self.cohort, self.envelope(first))
        next_arm = self.request(arm="strict")
        with self.assertRaisesRegex(ValueError, "already used"):
            poc.submit_response(self.cohort, self.envelope(next_arm))
        third = self.request(task=TASKS[1])
        with self.assertRaisesRegex(ValueError, "already used"):
            poc.submit_response(self.cohort, self.envelope(third))

    def test_empty_final_is_exact_error_receipt_never_a_replacement_answer(self):
        pending = self.request()
        original = self.envelope(pending, text="")
        publication = poc.submit_response(self.cohort, original)
        delivered = canonical.load_file(Path(publication["published"]))
        self.assertEqual("", delivered["text"])
        self.assertEqual(worker.EMPTY_FINAL_ERROR, delivered["transport_error"])
        self.assertNotIn("transport_error", original)
        self.assertEqual(0, publication["output_bytes"])

    def test_protocol_source_config_carrier_and_request_mutations_fail_closed(self):
        pending = self.request()
        carrier = Path(pending["carrier_path"])
        original = carrier.read_bytes()
        carrier.chmod(0o600)
        carrier.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "carrier differs"):
            poc.pending_request(self.cohort)
        carrier.write_bytes(original)
        (self.repo / "fixture.py").write_bytes(b"changed source\n")
        self.frozen["fixture.py"] = canonical.digest_file(self.repo / "fixture.py")
        with self.assertRaisesRegex(ValueError, "INPUT_MUTATION"):
            poc.verify_inputs(self.cohort)

    def test_hidden_material_is_refused_before_carrier_delivery(self):
        pending = self.request()
        request_path = Path(pending["request_path"])
        request = canonical.load_file(request_path)
        request["user"] += " expected_wire hidden oracle"
        worker.atomic_json(request_path, request)
        with self.assertRaisesRegex(ValueError, "Withheld"):
            poc.pending_request(self.cohort)

    def test_strict_cli_has_all_gates_no_positive_arguments_and_unlimited_proof_wait(self):
        argv = worker.cli_argv(self.cohort, TASKS[0])
        self.assertIn("--require-tests", argv)
        self.assertEqual("strict", argv[argv.index("--policy") + 1])
        self.assertEqual("0", argv[argv.index("--budget-seconds") + 1])
        self.assertEqual("2", argv[argv.index("--repair-rounds") + 1])
        self.assertEqual("TESTED", argv[argv.index("--require-state") + 1])
        self.assertFalse(any("candidate" in arg or arg.startswith("--bridge-") for arg in argv))

    def test_raw_extracts_exact_unedited_source_and_origin_not_formal_evidence(self):
        directory = self.root / "raw-extraction"
        directory.mkdir()
        source = "def solve(data):\n    return data\n\n# exact λ\n"
        text = canonical.dumps({"files": {"solution.py": source}}).decode()
        artifact = worker.raw_artifact(text, directory)
        self.assertEqual(source.encode(), (artifact / "solution.py").read_bytes())
        origin = poc.raw_origin(directory, [{"response": text}])
        self.assertEqual([], origin["issues"])
        self.assertFalse(origin["milestone_authority"])
        (artifact / "solution.py").write_text(source + "# changed\n")
        self.assertTrue(poc.raw_origin(directory, [{"response": text}])["issues"])
        for value in ({"files": {"solution.py": source}, "tests": []}, {"files": {"other.py": source}}):
            with self.assertRaises(ValueError):
                worker.raw_artifact(canonical.dumps(value).decode(), self.root)

    def test_authored_raw_grader_uses_two_real_isolated_harnesses_and_detects_wrong_value(self):
        # One authored identity case, independent of every withheld PoC corpus.
        # The controller/checker is exercised; no model/Lean call occurs.
        protocol = self.root / "authored-observation-protocol"
        (protocol / "withheld").mkdir(parents=True)
        case = {"case_id": "authored-C1", "input_wire": {"dict": {"value": {"int": "5"}}},
                "expected_wire": {"dict": {"value": {"int": "5"}}}}
        worker.atomic_json(protocol / "withheld" / f"{TASKS[0]}.json", {"cases": [case]})
        artifact = self.root / "authored-raw-identity-artifact"
        artifact.mkdir()
        (artifact / "solution.py").write_bytes(b"def solve(data):\n    return data\n")
        with patch.object(poc.checker, "PROTOCOL", protocol):
            observed = poc.observe_raw(artifact, TASKS[0])
            self.assertEqual("OBSERVATIONS_PASSED", observed["status"], observed["diagnostics"])
            self.assertEqual((1, 2, 2), (observed["passed_cases"], observed["observations"], observed["passed_observations"]))
            self.assertEqual(2, len(observed["isolation"]))
            self.assertFalse(observed["milestone_authority"])
            self.assertTrue(observed["input_bytes_unchanged"])
            case["expected_wire"]["dict"]["value"]["int"] = "6"
            worker.atomic_json(protocol / "withheld" / f"{TASKS[0]}.json", {"cases": [case]})
            wrong = poc.observe_raw(artifact, TASKS[0])
        self.assertEqual("BLOCKED", wrong["status"])
        self.assertEqual((0, 2, 0), (wrong["passed_cases"], wrong["observations"], wrong["passed_observations"]))

    def test_seal_keeps_all_six_denominators_and_durable_completed_result(self):
        row = {"task": TASKS[0], "arm": "raw", "status": "SUCCESS", "successful_task": True,
               "provider_calls": 1, "independent_cases_passed": 160, "observations": 320}
        native_path = self.cohort / "artifacts" / TASKS[0] / "raw/result.json"
        poc.native.write_once(native_path, row)
        pending = self.request(arm="strict")
        worker.atomic_json(Path(pending["request_path"]).parent / "usage.json", {"calls": 1, "responses": 0})
        poc.seal(self.cohort, [], self.protocol, reason="Explicitly interrupted fixture")
        summary = canonical.load_file(self.cohort / "SUMMARY.json")
        self.assertEqual(6, len(summary["tasks"]))
        self.assertEqual(1, summary["arms"]["raw"]["successful_tasks"])
        self.assertEqual(3, summary["arms"]["strict"]["total_tasks"])
        self.assertEqual(row, canonical.load_file(native_path))
        self.assertEqual("INTERRUPTED", summary["tasks"][1]["status"])
        self.assertEqual("UNSTARTED", summary["tasks"][2]["status"])
        manifest = canonical.load_file(self.cohort / "EVIDENCE-MANIFEST.json")
        self.assertNotIn("EVIDENCE-MANIFEST.json", manifest["files"])
        self.assertEqual(manifest["files_root"], canonical.digest_json(manifest["files"]))

    def test_consumed_receipts_bind_raw_natural_language_and_exact_unedited_source(self):
        directory = self.cohort / "artifacts" / TASKS[0] / "raw"
        transport = worker.MailboxTransport(directory / "mailbox", 1, poll_seconds=0.01)
        conf = worker.configuration()
        broker = Broker(config.resolve(conf, worker.endpoint_profiles()["profiles"]), directory / "transcripts")
        protocol = self.root / "authored-raw-prompt-protocol"
        protocol.mkdir()
        (protocol / f"{TASKS[0]}.txt").write_bytes(b"Authored identity request")
        text = canonical.dumps({"files": {"solution.py": "def solve(data):\n    return data\n"}}).decode()
        worker.atomic_json(self.cohort / "active-arm.json", {"task": TASKS[0], "arm": "raw", "phase": "generation"})
        results, failures = [], []
        def execute():
            try:
                results.append(transport.call(broker, "author", "raw/1", RAW_SYSTEM, "Authored identity request", "raw-coding"))
            except BaseException as error:
                failures.append(error)
        thread = threading.Thread(target=execute)
        thread.start()
        request_path = directory / "mailbox/request-0001.json"
        deadline = time.monotonic() + 5
        while not request_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(request_path.is_file())
        with patch.object(poc.checker, "PROTOCOL", protocol):
            pending = poc.pending_request(self.cohort)
            published = poc.submit_response(self.cohort, self.envelope(pending, text=text))
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual([], failures)
            worker.raw_artifact(results[0].text, directory)
            audit = poc.simulation_audit(self.cohort, TASKS[0], "raw", [])
            self.assertEqual("PASS", audit[0]["status"], audit)
            self.assertEqual(1, audit[0]["provider_calls"])
            envelope_path = Path(published["published"])
            changed = canonical.load_file(envelope_path)
            changed["text"] += "\nchanged final"
            worker.atomic_json(envelope_path, changed)
            rejected = poc.simulation_audit(self.cohort, TASKS[0], "raw", [])
            self.assertEqual("BLOCK", rejected[0]["status"])
            self.assertTrue(any("receipt differs" in issue for issue in rejected[0]["issues"]))
            # A different prompt cannot become direct-generation evidence merely
            # because its response and transcript hashes agree.
            (protocol / f"{TASKS[0]}.txt").write_bytes(b"Different authored request")
            wrong_prompt = poc.simulation_audit(self.cohort, TASKS[0], "raw", [])
            self.assertTrue(any("natural-language request" in issue for issue in wrong_prompt[0]["issues"]))


class SolTransportTests(unittest.TestCase):
    def test_actual_mailbox_transport_records_exact_final_and_honest_unknown_identity(self):
        with tempfile.TemporaryDirectory(prefix="authored-sol-transport-") as temp:
            root = Path(temp)
            conf = worker.configuration()
            profiles = worker.endpoint_profiles()["profiles"]
            broker = Broker(config.resolve(conf, profiles), root / "transcripts")
            transport = worker.MailboxTransport(root / "mailbox", 128, poll_seconds=0.01)
            results, failures = [], []
            def execute():
                try:
                    results.append(transport.call(broker, "author", "raw/1", RAW_SYSTEM, "Authored request", "raw-coding"))
                except BaseException as error:
                    failures.append(error)
            thread = threading.Thread(target=execute)
            thread.start()
            request_path = root / "mailbox/request-0001.json"
            deadline = time.monotonic() + 5
            while not request_path.is_file() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(request_path.is_file())
            response = {"transport": "collaboration", "requested_model": worker.MODEL,
                        "request_id": "0001", "request_sha256": canonical.digest_file(request_path),
                        "agent_task_id": "/root/authored_sol_transport_leaf", "text": "exact returned λ\n"}
            worker.atomic_json(root / "mailbox/response-0001.json", response)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual([], failures)
            self.assertEqual(response["text"], results[0].text)
            self.assertIsNone(results[0].returned_model)
            self.assertIsNone(results[0].input_tokens)
            receipt = canonical.load_file(root / "mailbox/response-receipt-0001.json")
            self.assertEqual(canonical.digest(response["text"].encode()), receipt["text_sha256"])
            self.assertFalse(receipt["model_identity_attested"])
            self.assertEqual(1, transport.state["calls"])
            self.assertEqual(1, transport.state["responses"])
            self.assertEqual(128, transport.state["max_calls"])
            transcript = canonical.load_file(next((root / "transcripts").glob("*.json")))
            self.assertEqual(response["text"], transcript["response"])
            self.assertEqual(worker.MODEL, transcript["requested_model"])
            self.assertIsNone(transcript["returned_model"])
            self.assertEqual("gpt-6-luna", luna_worker.MODEL)


if __name__ == "__main__":
    unittest.main()
