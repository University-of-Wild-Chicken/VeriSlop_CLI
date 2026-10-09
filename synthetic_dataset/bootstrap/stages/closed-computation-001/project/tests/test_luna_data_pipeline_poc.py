"""Authored supplemental-controller fixtures; no agents or native PoC runs.

Mailbox and identity assertions are exercised directly. Artifact-origin auditing is
mocked where noted; these unit fixtures never enter the three-task denominator.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from synthetic_dataset.tools import luna_data_pipeline_poc as poc
from synthetic_dataset.tools import luna_data_pipeline_worker as worker
from synthetic_dataset.tools import luna_worker as mailbox
from synthetic_dataset.tools import check_data_pipeline_poc as checker
from synthetic_dataset.tools.luna_worker import atomic_json
from synthetic_dataset.tools.data_pipeline_oracle import TASKS
from verislop import canonical, fsutil, schemas
from verislop.package import Package
from verislop.providers import config
from verislop.providers.broker import Broker

ZERO = "sha256:" + "0" * 64


class LunaSupplementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="authored-luna-supplement-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "fixture-repository"
        self.repo.mkdir()
        (self.repo / "fixture.py").write_text('"Only a source-freeze unit fixture"\n')
        self.frozen = {"fixture.py": canonical.digest_file(self.repo / "fixture.py")}
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(poc.native, "REPO", self.repo))
        stack.enter_context(patch.object(poc, "source_inputs", return_value=self.frozen))
        stack.enter_context(patch.object(poc.checker, "check_preregistration", return_value={"root": ZERO}))
        self.cohort = self.root / "fixture-supplement"
        self.protocol = poc.prepare(self.cohort)

    def request(self, task=TASKS[0], rid="0001"):
        directory = self.cohort / task / "mailbox"
        atomic_json(self.cohort / "active-task.json", {"task": task, "phase": "generation"})
        request = {"format": "verislop.collaboration-request/0.1", "request_id": rid,
            "system": "Exact system with é and a newline\n", "user": "Exact user: preserve e\u0301 and 🐈\n",
            "requested_model": "gpt-6-luna", "transport": "collaboration", "agent": "author",
            "instance": "formalizer/1", "purpose": "formalize", "max_response_bytes": 1 << 20,
            "requested_max_output_tokens": 8192, "output_token_limit_enforced": False}
        atomic_json(directory / f"request-{rid}.json", request)
        return poc.pending_request(self.cohort)

    def envelope(self, pending, agent="/root/fresh_luna_supplement_unit"):
        result = {"transport": "collaboration", "requested_model": "gpt-6-luna",
            "request_id": pending["request"]["request_id"], "request_sha256": pending["request_sha256"],
            "task": pending["task"], "supplemental_protocol_root": pending["supplemental_protocol_root"],
            "spawn_message_sha256": pending["spawn_message_sha256"], "model_override": "gpt-6-luna",
            "fork_turns": "none", "agent_task_id": agent, "text": 'Exact agent final é\n',
            "model_identity_attested": False}
        if pending.get("relay_mode") == "file":
            result.update(relay_mode="file", carrier_path=pending["carrier_path"],
                          carrier_sha256=pending["carrier_sha256"])
        return result

    def file_request(self):
        self.cohort = self.root / "fixture-file-supplement"
        self.protocol = poc.prepare(self.cohort, relay_mode="file")
        return self.request()

    def test_protocol_is_exact_three_tasks_with_unattested_identity_and_finite_calls_no_deadlines(self):
        self.assertEqual(list(TASKS), self.protocol["tasks"])
        self.assertEqual((160, 2, 32), (self.protocol["independent_cases_per_task"], self.protocol["independent_repeats"], self.protocol["max_calls_per_task"]))
        self.assertFalse(self.protocol["model_identity_attested"])
        self.assertFalse(self.protocol["token_usage_available"])
        self.assertFalse(self.protocol["output_token_limit_enforced"])
        self.assertEqual(poc.EMPTY_FINAL_POLICY, self.protocol["empty_final_policy"])
        self.assertFalse(poc.configuration()["review"]["require_fixed_model_snapshot"])
        for name in ("returned_model", "model_digest_sha256", "input_tokens", "output_tokens",
                     "model_generation_deadline", "proof_search_deadline", "review_tier_deadline"):
            self.assertIsNone(self.protocol[name])
        self.assertEqual([], schemas.validate("review-config", poc.configuration()))
        self.assertEqual(self.protocol, poc.verify_inputs(self.cohort))
        with self.assertRaises(ValueError):
            poc.prepare(self.cohort)

    def test_worker_cli_is_full_strict_workflow_without_candidate_flags(self):
        argv = worker.cli_argv(self.cohort, TASKS[0])
        for flag in ("--require-tests", "--non-interactive", "--json", "--quiet"):
            self.assertIn(flag, argv)
        self.assertEqual("strict", argv[argv.index("--policy") + 1])
        self.assertEqual("0", argv[argv.index("--budget-seconds") + 1])
        self.assertEqual("2", argv[argv.index("--repair-rounds") + 1])
        self.assertEqual("32", argv[argv.index("--cases") + 1])
        self.assertEqual(TASKS[0].lower(), argv[argv.index("--run-id") + 1])
        self.assertFalse(any("candidate" in arg or arg.startswith("--bridge-") for arg in argv))
        with self.assertRaises(ValueError):
            worker.cli_argv(self.cohort, "A01")

    def test_pending_and_submit_preserve_exact_system_user_message_and_final(self):
        pending = self.request()
        self.assertTrue(pending["agent_message"].endswith('SYSTEM:\n' + pending["request"]["system"] + '\n\nUSER:\n' + pending["request"]["user"]))
        self.assertEqual(canonical.digest(pending["agent_message"].encode()), pending["spawn_message_sha256"])
        envelope = self.envelope(pending)
        published = poc.submit_response(self.cohort, envelope)
        self.assertEqual(envelope, canonical.load_file(Path(published["published"])))
        self.assertEqual(envelope["text"], canonical.load_file(Path(published["published"]))["text"])
        self.assertIsNone(poc.pending_request(self.cohort))
        with self.assertRaises(ValueError):
            poc.submit_response(self.cohort, envelope)

    def test_submit_rejects_wrong_model_context_message_request_task_protocol_or_attestation(self):
        pending = self.request()
        envelope = self.envelope(pending)
        for key, wrong in (("model_override", "gpt-6-sol"), ("fork_turns", "all"),
            ("spawn_message_sha256", ZERO), ("request_sha256", ZERO), ("request_id", "0002"),
            ("task", TASKS[1]), ("supplemental_protocol_root", ZERO), ("model_identity_attested", True)):
            with self.subTest(key=key), self.assertRaises(Exception):
                poc.submit_response(self.cohort, {**envelope, key: wrong})
        self.assertFalse((Path(pending["request_path"]).parent / "response-0001.json").exists())
        with self.assertRaises(Exception):
            poc.submit_response(self.cohort, {**envelope, "text": "x" * ((1 << 20) + 1)})

    def test_submit_rejects_agent_reuse_across_fixed_tasks(self):
        first = self.request(TASKS[0])
        poc.submit_response(self.cohort, self.envelope(first))
        second = self.request(TASKS[1])
        with self.assertRaisesRegex(ValueError, "already used"):
            poc.submit_response(self.cohort, self.envelope(second))

    def test_file_relay_preregisters_explicit_read_policy_and_exact_unicode_carrier(self):
        pending = self.file_request()
        self.assertEqual("file", self.protocol["relay_mode"])
        self.assertEqual(poc.FILE_TOOL_POLICY, self.protocol["tool_policy"])
        self.assertIn("sole hash-bound current carrier", self.protocol["policy_departure"])
        self.assertFalse(self.protocol["model_identity_attested"])
        path = Path(pending["carrier_path"])
        self.assertTrue(path.is_absolute())
        self.assertEqual(0o444, path.stat().st_mode & 0o777)
        self.assertEqual(canonical.digest_file(path), pending["carrier_sha256"])
        carrier = canonical.load_file(path)
        self.assertEqual({"format": poc.CARRIER_FORMAT, "request_id": "0001",
            "request_sha256": pending["request_sha256"], "system": pending["request"]["system"],
            "user": pending["request"]["user"]}, carrier)
        self.assertNotIn(pending["request"]["user"], pending["agent_message"])
        self.assertIn(str(path), pending["agent_message"])
        self.assertIn(pending["carrier_sha256"], pending["agent_message"])
        self.assertIn("carrier file's raw bytes", pending["agent_message"])
        self.assertIn("Compare the carrier.request_sha256 metadata field", pending["agent_message"])
        self.assertIn("whole original request document", pending["agent_message"])
        self.assertIn("not asked to recompute it", pending["agent_message"].replace("\n", " "))
        self.assertIn("Never compare a hash of the system or user field", pending["agent_message"])
        self.assertIn("read exact successive chunks until complete", pending["agent_message"])
        self.assertEqual(canonical.digest(pending["agent_message"].encode()), pending["spawn_message_sha256"])
        self.assertEqual(pending, poc.pending_request(self.cohort))
        published = poc.submit_response(self.cohort, self.envelope(pending))
        self.assertEqual(self.envelope(pending), canonical.load_file(Path(published["published"])))

    def test_file_relay_rejects_missing_or_wrong_mode_path_digest_and_spawn_binding(self):
        pending = self.file_request()
        envelope = self.envelope(pending)
        for key, wrong in (("relay_mode", "inline"), ("carrier_path", "/tmp/another-carrier.json"),
                           ("carrier_sha256", ZERO), ("spawn_message_sha256", ZERO)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                poc.submit_response(self.cohort, {**envelope, key: wrong})
            missing = {k: v for k, v in envelope.items() if k != key}
            with self.subTest(missing=key), self.assertRaises(ValueError):
                poc.submit_response(self.cohort, missing)
        self.assertFalse(Path(pending["request_path"]).with_name("response-0001.json").exists())

    def test_empty_actual_final_is_preserved_as_bound_transport_error_and_never_replaced(self):
        pending = self.file_request()
        envelope = {**self.envelope(pending), "text": ""}
        receipt = poc.submit_response(self.cohort, envelope)
        published = canonical.load_file(Path(receipt["published"]))
        self.assertEqual("", published["text"])
        self.assertEqual(mailbox.EMPTY_FINAL_ERROR, published["transport_error"])
        self.assertEqual(mailbox.EMPTY_FINAL_ERROR, receipt["transport_error"])
        self.assertNotIn("transport_error", envelope)
        self.assertEqual(0, receipt["output_bytes"])
        self.assertEqual(envelope, {k: v for k, v in published.items() if k != "transport_error"})
        self.assertIsNone(poc.pending_request(self.cohort))
        with self.assertRaises(ValueError):
            poc.submit_response(self.cohort, envelope)

    def test_empty_final_error_rejects_forged_kind_nonempty_text_and_stale_context(self):
        pending = self.file_request()
        envelope = {**self.envelope(pending), "text": "", "transport_error": dict(mailbox.EMPTY_FINAL_ERROR)}
        for key, value in (("transport_error", {**mailbox.EMPTY_FINAL_ERROR, "code": "OTHER"}),
                           ("text", "invented substitute"), ("task", TASKS[1]),
                           ("supplemental_protocol_root", ZERO), ("carrier_sha256", ZERO),
                           ("spawn_message_sha256", ZERO), ("agent_task_id", None)):
            with self.subTest(key=key), self.assertRaises(Exception):
                poc.submit_response(self.cohort, {**envelope, key: value})
        self.assertFalse(Path(pending["request_path"]).with_name("response-0001.json").exists())

    def test_inline_relay_rejects_file_claims_or_wrong_mode(self):
        pending = self.request()
        for extra in ({"relay_mode": "file"}, {"carrier_sha256": ZERO}, {"carrier_path": "/tmp/fake"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                poc.submit_response(self.cohort, {**self.envelope(pending), **extra})

    def test_file_relay_carrier_or_native_request_mutation_is_never_overwritten(self):
        pending = self.file_request()
        path = Path(pending["carrier_path"])
        original = path.read_bytes()
        path.chmod(0o644)
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "carrier differs"):
            poc.pending_request(self.cohort)
        self.assertEqual(original + b" ", path.read_bytes())
        with self.assertRaisesRegex(ValueError, "carrier differs"):
            poc.submit_response(self.cohort, self.envelope(pending))
        path.write_bytes(original)
        native = Path(pending["request_path"])
        native_bytes = native.read_bytes()
        native.write_bytes(native_bytes + b" ")
        with self.assertRaisesRegex(ValueError, "carrier binding differs"):
            poc.pending_request(self.cohort)
        self.assertEqual(original, path.read_bytes())

    def test_file_relay_rejects_symlink_carrier_and_audit_never_recreates_missing_carrier(self):
        pending = self.file_request()
        path = Path(pending["carrier_path"])
        native = Path(pending["request_path"])
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(native)
        with self.assertRaisesRegex(ValueError, "symlink"):
            poc.pending_request(self.cohort)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            poc._relay_binding(self.cohort, pending["task"], native, pending["request"],
                               self.protocol, create_carrier=False)
        self.assertFalse(path.exists())
        path.write_bytes(original)

    def test_file_relay_never_recreates_deleted_carrier_or_binding_after_exposure(self):
        pending = self.file_request()
        path = Path(pending["carrier_path"])
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "carrier is missing"):
            poc.pending_request(self.cohort)
        with self.assertRaisesRegex(ValueError, "carrier is missing"):
            poc.submit_response(self.cohort, self.envelope(pending))
        self.assertFalse(path.exists())
        path.write_bytes(original)
        binding = path.with_name("carrier-binding-0001.json")
        binding.unlink()
        with self.assertRaisesRegex(ValueError, "binding is missing"):
            poc.pending_request(self.cohort)
        self.assertFalse(binding.exists())

    def test_file_relay_mode_is_frozen_and_unknown_modes_are_rejected(self):
        self.file_request()
        protocol_path = self.cohort / "protocol.json"
        original = protocol_path.read_bytes()
        protocol = canonical.load_file(protocol_path)
        protocol["relay_mode"] = "inline"
        atomic_json(protocol_path, protocol)
        with self.assertRaises(ValueError):
            poc.pending_request(self.cohort)
        protocol_path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            poc.prepare(self.root / "invalid-mode", relay_mode="replace-output")

    def test_withheld_material_is_refused_before_any_agent_message_is_exposed(self):
        pending = self.request()
        path = Path(pending["request_path"])
        request = pending["request"]
        for key in ("system", "user"):
            malicious = copy.deepcopy(request)
            malicious[key] += " withheld/cases.json expected_wire"
            atomic_json(path, malicious)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Withheld"):
                poc.pending_request(self.cohort)
        atomic_json(path, request)

    def test_changed_frozen_configuration_source_copy_or_protocol_blocks_controller(self):
        for relative in ("config.json", "execution-source/fixture.py", "protocol.json"):
            path = self.cohort / relative
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                poc.verify_inputs(self.cohort)
            path.write_bytes(original)
        with patch.object(poc, "source_inputs", return_value={"different.py": ZERO}), self.assertRaises(ValueError):
            poc.verify_inputs(self.cohort)

    def audit_fixture(self, *, file_relay=False):
        pending = self.file_request() if file_relay else self.request()
        envelope = self.envelope(pending)
        published = poc.submit_response(self.cohort, envelope)
        directory = Path(published["published"]).parent
        receipt = {"format": "verislop.collaboration-response-receipt/0.1", "request_id": "0001",
            "request_sha256": pending["request_sha256"], "response_sha256": canonical.digest_file(Path(published["published"])),
            "text_sha256": canonical.digest(envelope["text"].encode()), "output_bytes": len(envelope["text"].encode()),
            "agent_task_id": envelope["agent_task_id"], "requested_model": "gpt-6-luna", "returned_model": None,
            "input_tokens": None, "output_tokens": None, "transport": "collaboration", "model_identity_attested": False}
        atomic_json(directory / "response-receipt-0001.json", receipt)
        atomic_json(directory / "usage.json", {"calls": 1, "responses": 1, "output_bytes": receipt["output_bytes"],
            "input_tokens": None, "output_tokens": None, "token_usage_available": False})
        pkg = Package(self.cohort / TASKS[0] / "runs" / TASKS[0].lower(), resolve_root=False)
        pkg.ensure(TASKS[0].lower())
        request = pending["request"]
        transcript = {key: request[key] for key in ("agent", "instance", "purpose", "system", "user", "requested_model")}
        transcript.update(system_sha256=canonical.digest(request["system"].encode()), user_sha256=canonical.digest(request["user"].encode()),
            response=envelope["text"], request_id=envelope["agent_task_id"], returned_model=None, model_digest_sha256=None)
        path = pkg.root / "agents/transcripts/unit.json"
        fsutil.write_json(path, transcript)
        return pkg, directory, path

    def test_file_relay_audit_binds_carrier_request_spawn_final_and_rejects_post_submit_tamper(self):
        pkg, directory, _ = self.audit_fixture(file_relay=True)
        with patch.object(poc.native, "artifact_origin_audit", return_value={"issues": []}, create=True):
            self.assertEqual("PASS", poc.simulation_audit(self.cohort, TASKS[0], [pkg])[0]["status"])
            carrier = directory / "carrier-0001.json"
            original = carrier.read_bytes()
            carrier.chmod(0o644)
            carrier.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "carrier differs"):
                poc.simulation_audit(self.cohort, TASKS[0], [pkg])
            carrier.write_bytes(original)
            envelope_path = directory / "response-0001.json"
            envelope = canonical.load_file(envelope_path)
            envelope["carrier_sha256"] = ZERO
            atomic_json(envelope_path, envelope)
            with self.assertRaisesRegex(ValueError, "carrier path and digest"):
                poc.simulation_audit(self.cohort, TASKS[0], [pkg])

    def test_simulation_provenance_binds_actual_transcript_to_exact_fresh_final_and_keeps_identity_unknown(self):
        pkg, directory, path = self.audit_fixture()
        with patch.object(poc.native, "artifact_origin_audit", return_value={"issues": [], "proof_origin": "deterministic portfolio allowed"}, create=True) as artifacts:
            result = poc.simulation_audit(self.cohort, TASKS[0], [pkg])
            self.assertEqual("PASS", result[0]["status"], result)
            self.assertEqual(1, artifacts.call_count)
            changed = canonical.load_file(path)
            changed["response"] += "unrecorded rewrite"
            fsutil.write_json(path, changed)
            result = poc.simulation_audit(self.cohort, TASKS[0], [pkg])
            self.assertEqual("BLOCK", result[0]["status"])
            self.assertIn("Delivered native response has no exact mailbox/fresh-agent origin", result[0]["issues"])

    def test_empty_final_native_cli_fails_explicitly_and_supervisor_continues_all_three_tasks(self):
        # Authored empty-final fixtures exercise the real CLI and mailbox worker;
        # no agents, positive proposals or hidden evaluation cases are used.
        self.cohort = self.root / "fixture-empty-final-native-workers"
        self.protocol = poc.prepare(self.cohort, relay_mode="file")
        prompt_dir = self.root / "authored-failure-prompts"
        prompt_dir.mkdir()
        for task in TASKS:
            (prompt_dir / f"{task}.txt").write_text("Return the input integer unchanged.")
        launched, captures = [], []

        def provide_empty(_seconds):
            pending = poc.pending_request(self.cohort)
            self.assertIsNotNone(pending)
            envelope = self.envelope(pending, agent=f"/root/authored_empty_{len(captures) + 1}")
            envelope["text"] = ""
            captures.append(poc.submit_response(self.cohort, envelope))

        def launch(argv, **kwargs):
            task = argv[argv.index("--task") + 1]
            launched.append(task)
            stream = io.StringIO()
            with patch.dict(os.environ, kwargs["env"]), redirect_stdout(stream):
                code = worker.main(["--cohort", str(self.cohort), "--task", task])
            return SimpleNamespace(returncode=code, communicate=Mock(return_value=(stream.getvalue().encode(), b"")))

        original = Broker.call
        with patch.object(poc.subprocess, "Popen", side_effect=launch), \
                patch.object(checker, "PROTOCOL", prompt_dir), \
                patch.object(config, "load_user_profiles", return_value=mailbox.endpoint_profiles()["profiles"]), \
                patch.object(mailbox.time, "sleep", side_effect=provide_empty), \
                patch.object(mailbox, "Completion", side_effect=AssertionError("empty finals must never become Completions")), \
                patch.object(Broker, "_secret", side_effect=AssertionError("no credentials or APIs")), \
                patch.object(poc.native, "artifact_origin_audit", return_value={"issues": []}), \
                patch.object(poc.checker, "run_check", return_value={"status": "BLOCKED"}) as oracle:
            self.assertEqual(2, poc.run(self.cohort))
        self.assertIs(original, Broker.call)
        self.assertEqual(list(TASKS), launched)
        self.assertEqual(3, len(captures))
        self.assertEqual(3, oracle.call_count)
        summary = canonical.load_file(self.cohort / "SUMMARY.json")
        self.assertEqual((3, 0), (summary["total_tasks"], summary["verified_tasks"]))
        for task in TASKS:
            directory = self.cohort / task
            output = canonical.load_file(directory / "stdout.json")
            self.assertEqual("INFRASTRUCTURE_FAILURE", output["status"])
            self.assertIn("PROVIDER_FAILURE", [d["code"] for d in output["diagnostics"]])
            self.assertTrue(any("EMPTY_AGENT_FINAL" in d["message"] for d in output["diagnostics"]))
            usage = canonical.load_file(directory / "mailbox/usage.json")
            self.assertEqual((1, 0, 1, 0), (usage["calls"], usage["responses"], usage["transport_errors"], usage["output_bytes"]))
            self.assertFalse((directory / "mailbox/response-receipt-0001.json").exists())
            error_receipt = canonical.load_file(directory / "mailbox/transport-error-receipt-0001.json")
            self.assertEqual(canonical.digest(b""), error_receipt["text_sha256"])
            self.assertEqual(mailbox.EMPTY_FINAL_ERROR, error_receipt["transport_error"])
            self.assertEqual("PASS", canonical.load_file(directory / "origin-audit.json")[0]["status"])
            self.assertFalse(any((directory / "runs").glob("*/implementation/*.py")))

        # A receipt with no corresponding actual native failure must fail provenance.
        directory = self.cohort / TASKS[0]
        packages = [Package(p, resolve_root=False) for p in (directory / "runs").glob("*")]
        usage_path = directory / "mailbox/usage.json"
        usage = canonical.load_file(usage_path)
        with patch.object(poc.native, "artifact_origin_audit", return_value={"issues": []}):
            for key, value in (("responses", 1), ("transport_errors", 0), ("output_bytes", 1)):
                with self.subTest(counter=key):
                    atomic_json(usage_path, {**usage, key: value})
                    audit = poc.simulation_audit(self.cohort, TASKS[0], packages)
                    self.assertEqual("BLOCK", audit[0]["status"])
            atomic_json(usage_path, usage)
            error_path = directory / "mailbox/transport-error-receipt-0001.json"
            normal_path = error_path.with_name("response-receipt-0001.json")
            error_path.rename(normal_path)
            audit = poc.simulation_audit(self.cohort, TASKS[0], packages)
            self.assertEqual("BLOCK", audit[0]["status"])
            self.assertIn("Empty agent final was counted as a normal response", audit[0]["issues"])
            normal_path.rename(error_path)
        transcript_path = next(packages[0].root.rglob("transcripts/*.json"))
        transcript = canonical.load_file(transcript_path)
        self.assertIsNone(transcript["response"])
        self.assertIn(error_receipt["request_id"], transcript["error"])
        transcript["error"] = "unbound failure"
        fsutil.write_json(transcript_path, transcript)
        with patch.object(poc.native, "artifact_origin_audit", return_value={"issues": []}):
            audit = poc.simulation_audit(self.cohort, TASKS[0], packages)
        self.assertEqual("BLOCK", audit[0]["status"])
        self.assertIn("Mailbox final inventory differs from actually delivered native transcripts", audit[0]["issues"])

    def test_simulation_audit_rejects_invented_token_usage_and_attestation(self):
        pkg, directory, _ = self.audit_fixture()
        usage_path = directory / "usage.json"
        usage = canonical.load_file(usage_path)
        usage["input_tokens"] = 123
        atomic_json(usage_path, usage)
        receipt_path = directory / "response-receipt-0001.json"
        receipt = canonical.load_file(receipt_path)
        receipt["model_identity_attested"] = True
        atomic_json(receipt_path, receipt)
        with patch.object(poc.native, "artifact_origin_audit", return_value={"issues": []}, create=True):
            result = poc.simulation_audit(self.cohort, TASKS[0], [pkg])
        self.assertEqual("BLOCK", result[0]["status"])
        self.assertTrue(any("invent" in issue for issue in result[0]["issues"]))
        self.assertTrue(any("receipt differs" in issue for issue in result[0]["issues"]))

    def test_worker_patches_only_broker_call_and_restores_it_without_spawning_agents(self):
        original = Broker.call
        delivered = []
        class Transport:
            state = {"calls": 0, "responses": 0, "input_tokens": None, "output_tokens": None}
            def __init__(self, _directory, limit):
                self.limit = limit
            def call(self, broker, agent, instance, system, user, purpose):
                delivered.append((agent, instance, system, user, purpose))
            def save_usage(self):
                pass
        def cli_stub(argv):
            Broker.call(SimpleNamespace(), "author", "formalizer/1", "exact system", "exact user", "formalize")
            return 0
        with patch.object(worker, "MailboxTransport", Transport), patch.object(worker.cli, "main", side_effect=cli_stub):
            self.assertEqual(0, worker.main(["--cohort", str(self.cohort), "--task", TASKS[0]]))
        self.assertIs(original, Broker.call)
        self.assertEqual([("author", "formalizer/1", "exact system", "exact user", "formalize")], delivered)
        result = canonical.load_file(self.cohort / TASKS[0] / "worker-result.json")
        self.assertFalse(result["model_identity_attested"])

    def test_pending_and_submit_cli_do_not_launch_models(self):
        pending = self.request()
        envelope = self.envelope(pending)
        path = self.root / "captured-unit-final.json"
        fsutil.write_json(path, envelope)
        with patch.object(poc.subprocess, "Popen") as launcher, redirect_stdout(io.StringIO()):
            self.assertEqual(0, poc.main(["pending", "--cohort", str(self.cohort)]))
            self.assertEqual(0, poc.main(["submit", "--cohort", str(self.cohort), "--response-file", str(path)]))
        launcher.assert_not_called()

    def test_controller_refuses_request_inventory_over_finite_call_budget(self):
        pending = self.request()
        directory = Path(pending["request_path"]).parent
        for index in range(2, 34):
            request = {**pending["request"], "request_id": f"{index:04d}"}
            atomic_json(directory / f"request-{index:04d}.json", request)
        with self.assertRaisesRegex(ValueError, "logical-call budget"):
            poc.pending_request(self.cohort)

    def test_full_supplement_keeps_exit2_unsuccessful_despite_passing_mock_oracle_and_uses_no_deadline(self):
        processes = []
        def start(argv, **kwargs):
            task = argv[argv.index("--task") + 1]
            pkg = Package(self.cohort / task / "runs" / task.lower(), resolve_root=False)
            pkg.ensure(task.lower())
            stdout = canonical.dumps({"status": "PASS", "summary": {"active_package": str(pkg.root)}})
            process = SimpleNamespace(returncode=2, communicate=Mock(return_value=(stdout, b"")))
            processes.append(process)
            return process
        with patch.object(poc.subprocess, "Popen", side_effect=start), \
                patch.object(poc, "simulation_audit", return_value=[{"status": "PASS", "provider_calls": 1}]), \
                patch.object(poc.checker, "run_check", return_value={"status": "VERIFIED", "distinct_cases": 160, "passed_cases": 160, "observations": 320}):
            self.assertEqual(2, poc.run(self.cohort))
        summary = canonical.load_file(self.cohort / "SUMMARY.json")
        self.assertEqual((3, 0), (summary["total_tasks"], summary["verified_tasks"]))
        self.assertFalse(summary["model_identity_attested"])
        self.assertTrue(all(row["status"] == "BLOCKED" and row["independent_cases_passed"] == 160 for row in summary["tasks"]))
        self.assertEqual(3, len(processes))
        for process in processes:
            process.communicate.assert_called_once_with()

    def test_initial_source_mutation_seals_all_tasks_before_launch(self):
        with patch.object(poc, "verify_inputs", side_effect=ValueError("INPUT_MUTATION: fixture changed")), \
                patch.object(poc.subprocess, "Popen") as launch:
            self.assertEqual(2, poc.run(self.cohort))
        launch.assert_not_called()
        summary = canonical.load_file(self.cohort / "SUMMARY.json")
        self.assertEqual("BLOCKED", summary["status"])
        self.assertEqual(list(TASKS), [row["task"] for row in summary["tasks"]])
        self.assertTrue(all((self.cohort / task / "result.json").is_file() for task in TASKS))

    def test_interruption_seal_keeps_durable_results_and_unfinished_mailbox_counts(self):
        row = {"task": TASKS[0], "status": "VERIFIED", "provider_calls": 3}
        native_path = self.cohort / TASKS[0] / "result.json"
        fsutil.write_json(native_path, row)
        atomic_json(self.cohort / TASKS[1] / "mailbox/usage.json", {"calls": 4, "responses": 3})
        self.assertEqual(2, poc.seal(self.cohort, [], self.protocol, reason="Explicit interruption unit fixture"))
        summary = canonical.load_file(self.cohort / "SUMMARY.json")
        self.assertEqual(0, summary["verified_tasks"])
        self.assertEqual("VERIFIED", summary["tasks"][0]["retained_result_status"])
        self.assertEqual("BLOCKED", summary["tasks"][0]["status"])
        self.assertEqual(4, summary["tasks"][1]["provider_calls"])
        self.assertEqual(row, canonical.load_file(native_path))


if __name__ == "__main__":
    unittest.main()
