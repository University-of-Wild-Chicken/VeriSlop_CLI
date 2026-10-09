"""Authored protocol/transport fixtures; no live models, oracles or benchmark cases."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import ast
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from synthetic_dataset.tools import bootstrap_tier2_transport as transport
from synthetic_dataset.tools import bootstrap_tier2_worker as worker
from verislop import canonical, fsutil, lifecycle, review, schemas, view
from verislop.backends import vscore3_closure
from verislop.errors import Diagnostic
from verislop.package import Package
from verislop.providers import config
from verislop.providers.broker import Broker


class Tier2BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="authored-tier2-bootstrap-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "project"
        self.repo.mkdir()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(bootstrap, "REPO", self.repo))
        # Protocol fixtures stand in for root-owned expensive native kernel gates.
        # Real record validation is checked separately; these tests never assert a
        # kernel pass for the authored lightweight source files.
        self.stack.enter_context(patch.object(bootstrap, "verify_engineering_record", return_value=None))
        for name in bootstrap.TRANSPORT_FILES:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# authored frozen source fixture\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/bootstrap-tier2-data.md").write_text("Authored finite Tier 2 specification.\n")
        (self.repo / "verislop").mkdir()
        (self.repo / "verislop/fixture.py").write_text("# authored production fixture\n")
        (self.repo / "verislop/kernel.lean").write_text("-- authored kernel fixture\n")
        self.origins, self.prompts = {}, {}
        for task in bootstrap.TASK_ORDER:
            before = bootstrap.DELIVERY_EDITS[0 if task == "A23" else 1][0]
            text = (f"Software engineering task {task}: Authored identity fixture\n\n" + before +
                    " Return the exact input integer without narrowing its domain.\n\n"
                    "Input values remain immutable. Use exact integer arithmetic without external I/O.\n\n" +
                    bootstrap.DELIVERY_EDITS[2][0] + "\n\n" + bootstrap.DELIVERY_EDITS[3][0] +
                    '\n[{"input": -9, "output": -9}]\n')
            prompt = text.encode()
            path = self.root / f"{task}-public-prompt.txt"
            path.write_bytes(prompt)
            self.prompts[task] = path
            original = self.root / f"{task}-old-run"
            base = original / f"artifacts/{task}/verislop/package"
            base.mkdir(parents=True)
            start = prompt.index(b"Return the exact input")
            end = prompt.index(b"\n\n", start)
            row = {"id": "G-function", "role": "guarantee", "kind": "postcondition", "required": True,
                   "statement": "Old interpreter prose must not be copied.",
                   "source_refs": [{"start_byte": start, "end_byte": end}]}
            operational_start = prompt.index(b"Input values remain immutable.")
            operational_end = prompt.index(b"\n\n", operational_start)
            operational_rows = [{"id": oid, "role": "guarantee", "kind": "invariant" if oid == "I1" else "safety_property",
                "required": True, "statement": "Authored operational identity metadata, not copied into the revision.",
                "source_refs": [{"start_byte": operational_start, "end_byte": operational_end}]}
                for oid in bootstrap.SOURCE_ONLY_OPERATIONAL_IDS[task]]
            bootstrap.write_once(base / "draft.json", {"postconditions": [row], "operational": operational_rows})
            bootstrap.write_once(base / "interpretation.json", {
                "request": {"document_hash": canonical.digest(prompt)},
                "clauses": [{"start_byte": start, "end_byte": end, "refs": [row["id"]]},
                            {"start_byte": operational_start, "end_byte": operational_end,
                             "refs": [item["id"] for item in operational_rows]}]})
            bootstrap.write_once(base / "package.json", {"run_id": "package"})
            bootstrap.write_once(original / "protocol.json", {"format": "authored-old-python/0.1"})
            files = {p.relative_to(original).as_posix(): canonical.digest_file(p) for p in original.rglob("*") if p.is_file()}
            files[f"artifacts/{task}/verislop/package/request/prompt.txt"] = canonical.digest(prompt)
            # An original candidate is SEALED ONLY. Opening old positive contents
            # would fail because the file deliberately does not exist.
            files[f"artifacts/{task}/verislop/package/implementation/solution.py"] = "sha256:" + "c" * 64
            bootstrap.write_once(original / "BOOTSTRAP-EVIDENCE-MANIFEST.json", {
                "files": files, "files_root": canonical.digest_json(files)})
            self.origins[task] = original
        self.engineering = self.root / "engineering.json"
        bootstrap.write_once(self.engineering, {"format": "verislop.tier2-engineering-validation/0.1",
            "status": "VERIFIED", "source_root": canonical.digest_json(bootstrap.source_inventory()),
            "builds": [{"build": "A", "ok": True}, {"build": "B", "ok": True}],
            "determinism": {"mismatches": []}, "fresh_model_calls": 0})
        self.cohort = self.root / "run"
        self.protocol = bootstrap.prepare(self.cohort, "authored-tier2-001", self.origins,
                                           prompts=self.prompts, engineering_record=self.engineering)
        self.task = self.protocol["tasks"][0]
        self.directory = self.cohort / "artifacts/A23/verislop"

    def request(self, rid="0001", instance="formalizer/1"):
        selection = self.protocol["pair_order"][0]
        transport.atomic_json(self.cohort / "active-arm.json", {**selection, "phase": "generation"})
        request = {"format": "verislop.collaboration-request/0.1", "request_id": rid,
            "transport": "collaboration", "requested_model": transport.MODEL, "agent": "author",
            "instance": instance, "purpose": "formalize", "system": "Authored native system.",
            "user": "Authored native user data.", "max_response_bytes": transport.MAX_RESPONSE_BYTES,
            "requested_max_output_tokens": 8192, "output_token_limit_enforced": False}
        bootstrap.write_once(self.directory / f"mailbox/request-{rid}.json", request)
        return bootstrap.pending_request(self.cohort)

    def envelope(self, pending, text="Exact final λ\n", agent="/root/authored_tier2_leaf"):
        value = {key: pending[key] for key in bootstrap.BINDINGS}
        value.update(transport="collaboration", requested_model=transport.MODEL, relay_mode="file",
                     request_id=pending["request"]["request_id"], request_sha256=pending["request_sha256"],
                     agent_task_id=agent, text=text, model_identity_attested=False)
        return value

    def test_frozen_revision_preserves_functions_examples_ids_and_old_assurance(self):
        self.assertEqual(["A23", "D21"], self.protocol["task_order"])
        self.assertEqual(self.protocol, bootstrap.verify_inputs(self.cohort))
        self.assertEqual(2, self.protocol["tier"])
        self.assertEqual("restricted_source", self.protocol["endpoint"])
        self.assertEqual("END_TO_END_VERIFIED", self.protocol["require_state"])
        self.assertFalse(self.protocol["hidden_cases_loaded"])
        for task in self.protocol["tasks"]:
            revised = (self.cohort / task["revised_prompt_path"]).read_bytes()
            revision = bootstrap.load(self.cohort / task["revision_path"])
            metadata = bootstrap.load(self.cohort / task["metadata_path"])
            self.assertIn(b"Return the exact input integer without narrowing its domain.", revised)
            self.assertIn(b'[{"input": -9, "output": -9}]\n', revised)
            self.assertIn(b'"id":"G-function"', revised)
            self.assertNotIn(b"Old interpreter prose", revised)
            self.assertNotIn(b"Python", revised)
            self.assertNotIn(b"solution.py", revised)
            self.assertEqual(canonical.digest(self.prompts[task["id"]].read_bytes()), task["original_request_sha256"])
            self.assertFalse(revision["old_delivery_assurance_relabelled"])
            self.assertTrue(revision["functional_bytes_preserved"])
            self.assertFalse(metadata["old_positive_candidate_bytes_read"])
        with self.assertRaises(FileExistsError):
            bootstrap.prepare(self.cohort, "authored-tier2-001", self.origins, prompts=self.prompts, engineering_record=self.engineering)

    def test_snapshot_copies_exact_generic_source_and_no_dataset_or_history(self):
        forbidden = self.repo / "synthetic_dataset/tasks/A23/cases.json"
        forbidden.parent.mkdir(parents=True)
        forbidden.write_text("Authored forbidden sentinel, never opened by snapshot.")
        old = self.repo / "synthetic_dataset/bootstrap/stages/old/run/answer.txt"
        old.parent.mkdir(parents=True)
        old.write_text("Authored historical sentinel, never opened by snapshot.")
        target = self.root / "new-project"
        record = bootstrap.snapshot(target)
        self.assertEqual(bootstrap.source_inventory(self.repo), bootstrap.source_inventory(target))
        self.assertIn("verislop/kernel.lean", record["source_files"])
        self.assertFalse((target / "synthetic_dataset/tasks").exists())
        self.assertFalse((target / "synthetic_dataset/bootstrap").exists())
        with self.assertRaises(FileExistsError):
            bootstrap.snapshot(target)

    def test_missing_or_stale_pre_live_engineering_blocks_before_publication(self):
        target = self.root / "other-run"
        with self.assertRaisesRegex(ValueError, "engineering"):
            bootstrap.prepare(target, "authored-tier2-002", self.origins, prompts=self.prompts)
        self.assertFalse(target.exists())
        changed = bootstrap.load(self.engineering)
        changed["source_root"] = "sha256:" + "1" * 64
        path = self.root / "stale-engineering.json"
        bootstrap.write_once(path, changed)
        with self.assertRaisesRegex(ValueError, "stale"):
            bootstrap.prepare(target, "authored-tier2-002", self.origins, prompts=self.prompts, engineering_record=path)
        self.assertFalse(target.exists())

    def test_engineering_freeze_rejects_changed_sources_before_opening_any_package(self):
        frozen_path = self.root / "fresh-engineering-freeze.json"
        frozen = bootstrap.freeze_engineering(frozen_path)
        self.assertEqual(canonical.digest_json(bootstrap.source_inventory()), frozen["source_root"])
        with self.assertRaises(FileExistsError):
            bootstrap.freeze_engineering(frozen_path)
        (self.repo / "verislop/fixture.py").write_text("# changed after freeze\n")
        with self.assertRaisesRegex(ValueError, "changed after"):
            bootstrap.engineering_record(self.root / "must-not-be-opened", frozen_path)

    def test_invocation_requests_actual_tier2_closure_without_positive_inputs_or_timeouts(self):
        args = worker.cli_argv(self.cohort, self.task)
        for flag, value in (("--tier", "2"), ("--target", "vscore"), ("--backend-version", "0.3"),
                            ("--endpoint", "restricted_source"), ("--require-state", "END_TO_END_VERIFIED"),
                            ("--policy", "strict"), ("--budget-seconds", "0")):
            self.assertEqual(value, args[args.index(flag) + 1])
        self.assertIn("--no-tests", args)
        self.assertEqual(str(self.cohort / self.task["source_policy_path"]), args[args.index("--source-policy") + 1])
        self.assertFalse(any("candidate" in arg or arg.startswith("--bridge-") for arg in args))
        self.assertIsNone(transport.configuration()["providers"]["simulation"]["request_timeout_seconds"])
        self.assertEqual(0, transport.configuration()["review"]["budgets"]["max_wall_seconds_per_tier"])

    def test_required_source_policy_uses_only_original_required_guarantee_identities(self):
        identities = [
            {"id": "O1", "role": "guarantee", "kind": "postcondition", "required": True},
            {"id": "O2", "role": "guarantee", "kind": "postcondition", "required": True},
            {"id": "S1", "role": "guarantee", "kind": "safety_property", "required": True},
            {"id": "S2", "role": "guarantee", "kind": "safety_property", "required": True},
            {"id": "I1", "role": "guarantee", "kind": "invariant", "required": True},
            {"id": "A1", "role": "assumption", "kind": "precondition", "required": True},
            {"id": "N1", "role": "exclusion", "kind": "explicit_non_goal", "required": True},
            {"id": "NV1", "role": "internal", "kind": "non_vacuity", "required": True},
            {"id": "optional", "role": "guarantee", "kind": "postcondition", "required": False}]
        policy = bootstrap.source_policy(identities)
        self.assertEqual({"schema_version", "format", "obligations"}, set(policy))
        self.assertEqual("verislop.required-source-facets/0.1", policy["format"])
        self.assertEqual({"O1", "O2", "S1", "S2", "I1"}, set(policy["obligations"]))
        for oid, row in policy["obligations"].items():
            self.assertEqual({"file": "program.vscore.json", "entry": "solve", "arity": 1,
                              "properties": list(bootstrap.SOURCE_PROPERTIES), "value_required": True}, row)
        operational_policy = bootstrap.source_policy(identities, operational_ids=("I1", "S1", "S2"))
        self.assertEqual({"I1", "S1", "S2"}, {oid for oid, row in operational_policy["obligations"].items()
                                               if row["value_required"] is False})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            bootstrap.source_policy(identities + [identities[0]])
        for task in self.protocol["tasks"]:
            metadata = bootstrap.load(self.cohort / task["metadata_path"])
            expected = bootstrap.source_policy(metadata["identities"], operational_ids=bootstrap.SOURCE_ONLY_OPERATIONAL_IDS[task["id"]])
            path = self.cohort / task["source_policy_path"]
            self.assertEqual(canonical.dumps(expected), path.read_bytes())
            self.assertEqual(canonical.digest_file(path), task["source_policy_sha256"])
            self.assertEqual(canonical.digest_file(path), self.protocol["input_files"][task["source_policy_path"]])
            revision = bootstrap.load(self.cohort / task["revision_path"])
            self.assertEqual(task["source_policy_sha256"], revision["source_policy_sha256"])
            classification = {"value_required_default": True,
                              "source_only_operational_ids": list(bootstrap.SOURCE_ONLY_OPERATIONAL_IDS[task["id"]])}
            self.assertEqual(classification, revision["source_policy_classification"])
            self.assertEqual(classification, task["source_policy_classification"])
            revised = (self.cohort / task["revised_prompt_path"]).read_bytes()
            self.assertIn(canonical.dumps(expected), revised)
            self.assertIn(canonical.dumps(classification), revised)
            self.assertIn(b"a mathematical result-existence or equality theorem cannot replace", revised)
            self.assertIn(b"complete functional formula", revised)
            self.assertNotIn(b"Old interpreter prose", path.read_bytes())

    def test_operational_override_rejects_unknown_nonrequired_and_nonguarantee_ids(self):
        identities = [{"id": "G", "role": "guarantee", "kind": "safety_property", "required": True},
                      {"id": "optional", "role": "guarantee", "kind": "invariant", "required": False},
                      {"id": "A1", "role": "assumption", "kind": "precondition", "required": True},
                      {"id": "NV1", "role": "internal", "kind": "non_vacuity", "required": True}]
        for operational in (("unknown",), ("optional",), ("A1",), ("NV1",), ("G", "G")):
            with self.subTest(operational=operational), self.assertRaisesRegex(ValueError, "required guarantee"):
                bootstrap.source_policy(identities, operational_ids=operational)

    def test_unrelated_functional_invariant_and_safety_guarantees_keep_value_facets(self):
        identities = [{"id": "functional_invariant", "role": "guarantee", "kind": "invariant", "required": True},
                      {"id": "functional_safety", "role": "guarantee", "kind": "safety_property", "required": True}]
        self.assertTrue(all(row["value_required"] is True for row in bootstrap.source_policy(identities)["obligations"].values()))

    def test_frozen_source_policy_mutation_is_rejected(self):
        path = self.cohort / self.task["source_policy_path"]
        policy = bootstrap.load(path)
        policy["obligations"]["G-function"]["entry"] = "alternate_entry"
        path.write_bytes(canonical.dumps(policy))
        with self.assertRaisesRegex(ValueError, "INPUT_MUTATION"):
            bootstrap.verify_inputs(self.cohort)

    def test_profiles_use_canonical_loader_path_and_resolution_precedes_publication(self):
        profile = self.cohort / "provider-home" / config.DEFAULT_PROFILES_PATH
        self.assertEqual("provider-home/" + config.DEFAULT_PROFILES_PATH, self.protocol["endpoint_profiles_path"])
        self.assertEqual(canonical.digest_file(profile), self.protocol["endpoint_profiles_sha256"])
        self.assertEqual(canonical.digest_file(profile), self.protocol["input_files"][bootstrap.PROFILES_INPUT])
        self.assertFalse((self.cohort / "provider-home/providers.json").exists())
        with patch.dict(os.environ, {"VERISLOP_CONFIG_HOME": str(profile.parent)}):
            profiles = config.load_user_profiles(None)
            resolved = config.resolve(config.load(self.cohort / "config.json"), profiles)
        self.assertEqual(transport.endpoint_profiles()["profiles"], profiles)
        self.assertEqual([], resolved.diagnostics)
        target = self.root / "unresolvable-run"
        with patch.object(transport, "endpoint_profiles", return_value={
                "schema_version": "0.1", "artifact_kind": "endpoint_profiles", "profiles": {}}):
            with self.assertRaisesRegex(ValueError, "does not resolve"):
                bootstrap.prepare(target, "authored-tier2-unresolved", self.origins,
                                  prompts=self.prompts, engineering_record=self.engineering)
        self.assertFalse(target.exists())

    def test_actual_native_worker_reaches_and_consumes_exact_mailbox_interpreter_request(self):
        # No native stage, config resolver, Broker constructor or MailboxTransport
        # call is stubbed. An authored empty-final transport failure terminates the
        # real first request without making a model call or supplying a candidate.
        selection = self.protocol["pair_order"][0]
        transport.atomic_json(self.cohort / "active-arm.json", {**selection, "phase": "generation"})
        original_atomic_json = transport.atomic_json
        observed = []
        def provide_empty_final(path, value):
            original_atomic_json(path, value)
            if path.name.startswith("request-") and path.parent.name == "mailbox":
                pending = bootstrap.pending_request(self.cohort)
                observed.append(pending)
                bootstrap.submit_response(self.cohort, self.envelope(
                    pending, text="", agent="/root/authored_native_startup_" + value["request_id"]))
        output, error = io.StringIO(), io.StringIO()
        old_call = Broker.call
        with patch.dict(os.environ, {"VERISLOP_CONFIG_HOME": str(self.root / "unrelated-home")}), \
                patch.object(transport, "atomic_json", side_effect=provide_empty_final), \
                redirect_stdout(output), redirect_stderr(error):
            code = worker.execute(self.cohort, self.task)
            self.assertEqual(str(self.root / "unrelated-home"), os.environ["VERISLOP_CONFIG_HOME"])
        self.assertIs(old_call, Broker.call)
        self.assertEqual(1, len(observed), (code, output.getvalue(), error.getvalue()))
        self.assertEqual("interpret", observed[0]["request"]["purpose"])
        self.assertEqual("interpreter/1", observed[0]["request"]["instance"])
        self.assertIn((self.cohort / self.task["revised_prompt_path"]).read_text(), observed[0]["request"]["user"])
        receipt = bootstrap.load(self.directory / "mailbox/transport-error-receipt-0001.json")
        self.assertEqual(transport.EMPTY_FINAL_ERROR, receipt["transport_error"])
        self.assertEqual((1, 0, 1), tuple(bootstrap.load(self.directory / "mailbox/usage.json")[k]
                                            for k in ("calls", "responses", "transport_errors")))
        self.assertEqual("CLI_RETURNED", bootstrap.load(self.directory / "worker-result.json")["status"])
        self.assertEqual(3, code)
        pipeline = json.loads(output.getvalue())
        self.assertFalse(any(row["code"] == "CONFIGURATION_INVALID" for row in pipeline["diagnostics"]))
        report = bootstrap.load(Package(self.directory / "package").path("report"))
        self.assertEqual("0.2", report["schema_version"])
        self.assertEqual("verislop.backend.vscore/0.3", report["backend"])
        self.assertEqual((self.cohort / self.task["source_policy_path"]).read_bytes(),
                         (self.directory / "package/request/source-policy.json").read_bytes())
        self.assertEqual({"format": bootstrap.SOURCE_POLICY_FORMAT, "path": "request/source-policy.json",
                          "sha256": self.task["source_policy_sha256"]},
                         Package(self.directory / "package").meta()["source_policy"])

    def test_closed_envelope_rejects_wrong_bindings_extra_fields_and_agent_reuse(self):
        pending = self.request()
        valid = self.envelope(pending)
        for key in bootstrap.BINDINGS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                bootstrap.submit_response(self.cohort, {**valid, key: "wrong"})
        with self.assertRaisesRegex(ValueError, "closed"):
            bootstrap.submit_response(self.cohort, {**valid, "coaching": "never allowed"})
        published = bootstrap.submit_response(self.cohort, valid)
        self.assertEqual(valid["text"], bootstrap.load(Path(published["published"]))["text"])
        with self.assertRaisesRegex(ValueError, "No pending"):
            bootstrap.submit_response(self.cohort, valid)
        pending2 = self.request("0002")
        with self.assertRaisesRegex(ValueError, "fresh"):
            bootstrap.submit_response(self.cohort, self.envelope(pending2))

    def test_empty_final_remains_empty_bound_transport_error(self):
        pending = self.request()
        published = bootstrap.submit_response(self.cohort, self.envelope(pending, text=""))
        actual = bootstrap.load(Path(published["published"]))
        self.assertEqual("", actual["text"])
        self.assertEqual(transport.EMPTY_FINAL_ERROR, actual["transport_error"])

    def test_source_carrier_and_oracle_context_mutation_fail_closed(self):
        pending = self.request()
        carrier = Path(pending["carrier_path"])
        data = carrier.read_bytes()
        carrier.chmod(0o600)
        carrier.write_bytes(data + b" ")
        with self.assertRaisesRegex(ValueError, "carrier differs"):
            bootstrap.pending_request(self.cohort)
        carrier.write_bytes(data)
        request_path = Path(pending["request_path"])
        request = bootstrap.load(request_path)
        transport.atomic_json(request_path, {**request, "user": request["user"] + " tasks/A23/cases.json"})
        with self.assertRaisesRegex(ValueError, "Withheld"):
            bootstrap.pending_request(self.cohort)
        (self.repo / "verislop/fixture.py").write_text("# changed source\n")
        with self.assertRaisesRegex(ValueError, "INPUT_MUTATION"):
            bootstrap.verify_inputs(self.cohort)

    def test_mailbox_consumes_exact_final_and_audit_detects_changed_receipt(self):
        pkg = Package(self.directory / "package", resolve_root=False)
        pkg.ensure("package")
        bootstrap.write_bytes_once(pkg.path("prompt"), (self.cohort / self.task["revised_prompt_path"]).read_bytes())
        from verislop import source_policy as policy_backend
        policy_backend.stage(pkg, self.cohort / self.task["source_policy_path"])
        identities = bootstrap.load(self.cohort / self.task["metadata_path"])["identities"]
        bootstrap.write_once(pkg.path("draft"), {"authored_identities": identities})
        bootstrap.write_once(self.directory / "cli-invocation.json", {"argv": worker.cli_argv(self.cohort, self.task),
            "positive_candidate_arguments": [], "python_runtime_campaign": False})
        bootstrap.write_once(self.directory / "invocation.json", {
            "argv": [sys.executable, "-m", "synthetic_dataset.tools.bootstrap_tier2_worker", "--cohort", str(self.cohort), "--task", "A23"],
            "cwd": str(self.repo), "cli_argv": worker.cli_argv(self.cohort, self.task), "candidate_inputs": []})
        mailbox = transport.MailboxTransport(self.directory / "mailbox", 128, poll_seconds=0.01)
        broker = Broker(config.resolve(transport.configuration(), transport.endpoint_profiles()["profiles"]), pkg.root / "transcripts")
        transport.atomic_json(self.cohort / "active-arm.json", {**self.protocol["pair_order"][0], "phase": "generation"})
        values, failures = [], []
        def call():
            try:
                values.append(mailbox.call(broker, "author", "interpreter/1", "Authored system", "Authored user", "interpret"))
            except Exception as exc:
                failures.append(exc)
        thread = threading.Thread(target=call)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=2))
        deadline = time.monotonic() + 5
        request_path = self.directory / "mailbox/request-0001.json"
        while not request_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        pending = bootstrap.pending_request(self.cohort)
        final = "exact final with λ, `$()` and trailing spaces  \n\n"
        bootstrap.submit_response(self.cohort, self.envelope(pending, text=final))
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual([], failures)
        self.assertEqual(final, values[0].text)
        audit = bootstrap.response_audit(self.cohort, self.task)
        self.assertEqual("PASS", audit["status"], audit)
        self.assertEqual(1, audit["provider_calls"])
        native_policy = pkg.root / "request/source-policy.json"
        original_policy = native_policy.read_bytes()
        native_policy.chmod(0o600)
        native_policy.write_bytes(original_policy + b" ")
        self.assertEqual("BLOCK", bootstrap.response_audit(self.cohort, self.task)["status"])
        native_policy.write_bytes(original_policy)
        native_policy.chmod(0o444)
        receipt = self.directory / "mailbox/response-receipt-0001.json"
        transport.atomic_json(receipt, {**bootstrap.load(receipt), "text_sha256": "wrong"})
        self.assertEqual("BLOCK", bootstrap.response_audit(self.cohort, self.task)["status"])

    def test_transport_functions_are_identical_to_existing_generic_algorithms(self):
        source_root = Path(transport.__file__).resolve().parent
        def definitions(path):
            return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(path.read_text()).body
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        copied = definitions(source_root / "bootstrap_tier2_transport.py")
        sol = definitions(source_root / "sol_data_pipeline_worker.py")
        luna = definitions(source_root / "luna_worker.py")
        for name in ("_failure", "validate_response", "transport_error_message", "MailboxTransport"):
            self.assertEqual(sol[name], copied[name], name)
        for name in ("atomic_json", "endpoint_profiles"):
            self.assertEqual(luna[name], copied[name], name)

    def test_carrier_message_and_bytes_match_the_prior_generic_algorithm_exactly(self):
        pending = self.request()
        source_root = Path(transport.__file__).resolve().parent
        legacy_source = (source_root / "luna_data_pipeline_poc.py").read_text()
        node = next(node for node in ast.parse(legacy_source).body if isinstance(node, ast.FunctionDef) and node.name == "_relay_binding")
        # Evaluate ONLY the generic function; never import an oracle-bearing legacy
        # runner or evaluate any task/model protocol outside this authored request.
        namespace = {"Path": Path, "Any": object, "canonical": canonical, "json": json,
                     "CARRIER_FORMAT": bootstrap.CARRIER_FORMAT}
        exec(ast.get_source_segment(legacy_source, node), namespace)
        old = namespace["_relay_binding"](self.cohort, "A23", Path(pending["request_path"]), pending["request"],
                                           {"relay_mode": "file"}, create_carrier=False)
        self.assertEqual(old, {key: pending[key] for key in old})

    def test_native_verified_cannot_skip_required_e2e_or_configured_release(self):
        from verislop.backends import vscore3_closure
        report = {"terminal_status": "VERIFIED", "mechanical_status": "VERIFIED", "release_status": "ACCEPTED",
            "tier": {"requested": 2, "target": "vscore", "endpoint": "restricted_source", "requested_endpoint": "restricted_source", "require_state": "END_TO_END_VERIFIED"},
            "language": "vscore/0.3", "semantics": "vscore-semantics/0.3", "backend": "verislop.backend.vscore/0.3",
            "freshness": "current execution revalidated", "endpoint": {"established": "restricted_source"},
            "obligations": {"G": {"required": True, "role": "guarantee", "outcomes": {"END_TO_END_VERIFIED": "BLOCK"}}},
            "closure_id": "authored", "mechanical_result": "closure/executions/authored/mechanical-result.json",
            "roots": {"closure_input_root": "sha256:" + "0" * 64}, "builds": [], "determinism": {"mismatches": []},
            "review": {"configured": False, "checkpoints": {}}}
        snapshot = {"mechanical_status": "VERIFIED", "closure_id": report["closure_id"], "mechanical_result_path": report["mechanical_result"],
            "closure_root": report["roots"]["closure_input_root"], "builds": [], "determinism": report["determinism"], "claims": []}
        with patch.object(vscore3_closure, "mechanical_snapshot", return_value=snapshot):
            audit = bootstrap.native_audit(object(), report)
        self.assertEqual("BLOCK", audit["status"])
        self.assertFalse(audit["all_required_e2e"])
        self.assertEqual(0, audit["required_e2e_passed"])

    def test_partial_worker_is_retained_infrastructure_never_restarted(self):
        self.directory.mkdir(parents=True)
        with patch.object(bootstrap.subprocess, "Popen", side_effect=AssertionError("duplicate generation")):
            row = bootstrap.run_task(self.cohort, self.task, self.protocol["pair_order"][0])
        self.assertEqual("INFRASTRUCTURE_FAILURE", row["status"])
        self.assertFalse(row["successful_task"])
        self.assertEqual("CONTROLLER_INTERRUPTED", bootstrap.load(self.directory / "worker-result.json")["status"])

    def test_postworker_timing_and_terminal_publication_use_canonical_integer_milliseconds(self):
        class AuthoredProcess:
            pid = os.getpid()
            def wait(self):
                return 2

        def completed_worker(command, **kwargs):
            # This authored process fixture exits through the real postworker
            # publication path. No CLI/model subprocess is actually started.
            kwargs["stdout"].write(canonical.dumps({"command": "run", "status": "BLOCKED", "summary": {}}))
            bootstrap.write_once(self.directory / "cli-invocation.json", {
                "argv": worker.cli_argv(self.cohort, self.task), "positive_candidate_arguments": [],
                "python_runtime_campaign": False})
            bootstrap.write_once(self.directory / "worker-result.json", {"status": "CLI_RETURNED", "exit_code": 2})
            transport.MailboxTransport(self.directory / "mailbox", 128).save_usage()
            return AuthoredProcess()

        with patch.object(bootstrap.subprocess, "Popen", side_effect=completed_worker), \
                patch.object(bootstrap.time, "monotonic", side_effect=[100.0, 101.2345]):
            row = bootstrap.run_task(self.cohort, self.task, self.protocol["pair_order"][0])
        timing = bootstrap.load(self.directory / "timing.json")
        self.assertEqual({"generation_milliseconds": 1234}, timing)
        self.assertIs(type(timing["generation_milliseconds"]), int)
        self.assertEqual("INFRASTRUCTURE_FAILURE", row["status"])
        self.assertEqual(row, bootstrap.load(self.directory / "result.json"))
        self.assertEqual(timing, canonical.loads(canonical.dumps(timing)))

    def test_exact_startup_worker_error_without_prompt_or_stdout_is_durably_sealed(self):
        self.cohort = self.root / "startup-error-run"
        self.protocol = bootstrap.prepare(self.cohort, "authored-tier2-startup-error", {"A23": self.origins["A23"]},
                                           prompts=self.prompts, engineering_record=self.engineering)
        self.task = self.protocol["tasks"][0]
        self.directory = self.cohort / "artifacts/A23/verislop"
        worker_error = {"type": "RuntimeError", "message": "internal report failed schema validation: $.schema_version: expected constant '0.1'"}
        stderr_bytes = (json.dumps({"status": "WORKER_ERROR", "error": worker_error}) + "\n").encode()
        receipt = {}
        class StartupFailure:
            pid = os.getpid()
            def wait(self):
                return 3
        def failed_worker(command, **kwargs):
            pkg = Package(self.directory / "package", resolve_root=False)
            pkg.ensure("package")
            metadata = bootstrap.load(pkg.root / "package.json")
            metadata.update(requested={"schema_version": "0.1", "tier": 2, "target": "vscore", "endpoint": "restricted_source",
                                       "require_state": "END_TO_END_VERIFIED", "policy": "strict"},
                            stage_history=[{"stage": "interpret", "status": "BLOCKED", "seconds": 0,
                                            "codes": ["CONFIGURATION_INVALID"]}])
            transport.atomic_json(pkg.root / "package.json", metadata)
            bootstrap.write_once(self.directory / "cli-invocation.json", {
                "argv": worker.cli_argv(self.cohort, self.task), "positive_candidate_arguments": [],
                "python_runtime_campaign": False})
            mailbox = transport.MailboxTransport(self.directory / "mailbox", 128)
            mailbox.save_usage()
            receipt.update(status="WORKER_ERROR", error=worker_error, exit_code=3,
                           model_identity_attested=False, usage=mailbox.state)
            bootstrap.write_once(self.directory / "worker-result.json", receipt)
            kwargs["stderr"].write(stderr_bytes)
            return StartupFailure()
        with patch.object(bootstrap.subprocess, "Popen", side_effect=failed_worker):
            row = bootstrap.run_task(self.cohort, self.task, self.protocol["pair_order"][0])
        self.assertEqual("INFRASTRUCTURE_FAILURE", row["status"])
        self.assertTrue(row["startup_failure"])
        self.assertEqual(receipt, row["worker_receipt"])
        self.assertEqual(worker_error, row["primary_worker_error"])
        self.assertFalse(row["successful_task"])
        self.assertIsNone(row["package"])
        self.assertEqual([], row["origin_audit"]["agents"])
        self.assertEqual((0, 0, 0), tuple(row["origin_audit"][k] for k in ("provider_calls", "responses", "transport_errors")))
        self.assertEqual(["artifacts/A23/verislop/package/request/prompt.txt"], row["origin_audit"]["missing_native_prompts"])
        for package in row["origin_audit"]["packages"]:
            for key in ("formalization_origins", "restricted_source_origins", "proof_origins"):
                self.assertEqual([], package["origin"][key])
        self.assertEqual([], row["native"]["mechanical_claims"])
        self.assertEqual({}, row["native"]["per_obligation_outcomes"])
        self.assertEqual([], row["native"]["builds"])
        self.assertFalse((self.directory / "package/request/prompt.txt").exists())
        expected_bytes = {"stdout.json": b"", "stderr.log": stderr_bytes,
                          "worker-result.json": canonical.dumps(receipt)}
        for name, data in expected_bytes.items():
            self.assertEqual(data, (self.directory / name).read_bytes())
            self.assertEqual(canonical.digest(data), row["worker_outputs"][name]["sha256"])
            self.assertEqual(len(data), row["worker_outputs"][name]["bytes"])
        result = bootstrap.finalize(self.cohort)
        self.assertEqual("INFRASTRUCTURE_FAILURE", result["status"])
        self.assertEqual((0, 0, 0), tuple(result[k] for k in ("verified_tasks", "fresh_calls", "fresh_agents")))
        self.assertEqual(1, bootstrap.verify(self.cohort)["completed_tasks"])
        seal = bootstrap.load(self.cohort / "EVIDENCE-MANIFEST.json")
        self.assertEqual(seal, bootstrap.load(self.cohort / "BOOTSTRAP-EVIDENCE-MANIFEST.json"))
        for name, data in expected_bytes.items():
            self.assertEqual(canonical.digest(data), seal["files"][f"artifacts/A23/verislop/{name}"])
        with patch.object(bootstrap.subprocess, "Popen", side_effect=AssertionError("startup failure restarted")):
            self.assertEqual(result, bootstrap.run(self.cohort))
        (self.directory / "stderr.log").write_bytes(stderr_bytes + b"mutation")
        with self.assertRaisesRegex(ValueError, "retained terminal"):
            bootstrap.verify(self.cohort)

    def test_finalize_seals_all_retained_failures_resume_is_read_only_and_mutation_blocks(self):
        with patch.object(bootstrap.subprocess, "Popen", side_effect=AssertionError("duplicate generation")):
            for task, selection in zip(self.protocol["tasks"], self.protocol["pair_order"]):
                (self.cohort / "artifacts" / task["id"] / "verislop").mkdir(parents=True)
                bootstrap.run_task(self.cohort, task, selection)
            result = bootstrap.finalize(self.cohort)
            self.assertEqual("INFRASTRUCTURE_FAILURE", result["status"])
            self.assertTrue(result["complete"])
            self.assertEqual((0, 0, 0), (result["verified_tasks"], result["fresh_calls"], result["fresh_agents"]))
            before = bootstrap.evidence_files(self.cohort)
            with patch.object(bootstrap.transport, "atomic_json", side_effect=AssertionError("sealed cohort rewritten")):
                self.assertEqual(result, bootstrap.run(self.cohort))
                self.assertEqual(result, bootstrap.finalize(self.cohort))
            self.assertEqual(before, bootstrap.evidence_files(self.cohort))
            self.assertEqual(bootstrap.load(self.cohort / "EVIDENCE-MANIFEST.json"),
                             bootstrap.load(self.cohort / "BOOTSTRAP-EVIDENCE-MANIFEST.json"))
            self.assertEqual(2, bootstrap.verify(self.cohort)["completed_tasks"])
            bootstrap.write_once(self.cohort / "unaudited-proof.json", {"authored": "mutation fixture"})
            with self.assertRaisesRegex(ValueError, "seal membership"):
                bootstrap.verify(self.cohort)

    def test_missing_second_seal_resume_only_publishes_missing_seal(self):
        for task, selection in zip(self.protocol["tasks"], self.protocol["pair_order"]):
            (self.cohort / "artifacts" / task["id"] / "verislop").mkdir(parents=True)
            bootstrap.run_task(self.cohort, task, selection)
        result = bootstrap.finalize(self.cohort)
        (self.cohort / "BOOTSTRAP-EVIDENCE-MANIFEST.json").unlink()
        with patch.object(bootstrap.subprocess, "Popen", side_effect=AssertionError("generation restart")):
            self.assertEqual(result, bootstrap.run(self.cohort))
        self.assertTrue((self.cohort / "BOOTSTRAP-EVIDENCE-MANIFEST.json").is_file())


class Tier2NativeTerminalObservationUnits(unittest.TestCase):
    """Classifier/provider-context units; authored rows carry no kernel authority.

    The unrelated source-pipeline fixture separately exercises this reader with
    actual accepted proofs, both reviews and fresh native mechanical executions.
    """

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="authored-native-observation-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pkg = Package(self.root / "package")
        self.pkg.ensure("authored-native-observation")
        self.configuration = self.root / "provider-context/config.json"
        fsutil.write_json(self.configuration, transport.configuration())
        self.profile = self.configuration.parent / bootstrap.PROFILES_INPUT
        fsutil.write_json(self.profile, transport.endpoint_profiles())
        inputs = {"config.json": canonical.digest_file(self.configuration), bootstrap.PROFILES_INPUT: canonical.digest_file(self.profile)}
        root_hash = canonical.digest_json({})
        protocol = {"format": bootstrap.FORMAT, "source_root": root_hash, "input_root": canonical.digest_json(inputs),
                    "request_set_root": root_hash, "input_files": inputs, "configuration_sha256": inputs["config.json"],
                    "endpoint_profiles_path": bootstrap.PROFILES_INPUT, "endpoint_profiles_sha256": inputs[bootstrap.PROFILES_INPUT]}
        fsutil.write_json(self.configuration.parent / "protocol.json", protocol)
        fsutil.write_json(self.configuration.parent / "preregistration.json", {"format": bootstrap.FORMAT,
            "protocol_sha256": canonical.digest_file(self.configuration.parent / "protocol.json"),
            **{key: protocol[key] for key in ("source_root", "input_root", "request_set_root")}})
        fsutil.write_json(self.pkg.path("closure") / "review-config.json", transport.configuration())
        self.gate = {"configured": True, "checkpoints": {"formal_contract": "REVIEW_NOT_RUN", "release": "REVIEW_NOT_RUN"},
                     "diagnostics": [Diagnostic("REVIEW_NOT_RUN", "Authored unit has no accepted ballots")], "projection_reuse": {}}
        self.current = {"G": self.record("G", "postcondition"), "W": self.record("W", "non_vacuity")}
        self.snapshot = {"mechanical_status": "BLOCKED", "closure_id": "authored",
                         "mechanical_result_path": "closure/executions/authored/mechanical-result.json", "closure_root": root_hash,
                         "builds": [], "determinism": {"mismatches": []}, "claims": []}
        self.report = {"terminal_status": "BLOCKED", "mechanical_status": "BLOCKED", "release_status": "BLOCKED",
                       "closure_id": "authored", "mechanical_result": self.snapshot["mechanical_result_path"],
                       "roots": {"closure_input_root": root_hash}, "builds": [], "determinism": self.snapshot["determinism"],
                       "review": self.serialized_gate(), "review_target": None, "review_projection": {"reuse": {}}}
        self.refresh_records()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(schemas, "validate", return_value=[]))
        self.stack.enter_context(patch.object(view, "derive", side_effect=lambda pkg: {"obligations": copy.deepcopy(self.current)}))
        self.stack.enter_context(patch.object(vscore3_closure, "mechanical_snapshot", side_effect=lambda pkg: copy.deepcopy(self.snapshot)))
        self.no_call = self.stack.enter_context(patch.object(Broker, "call", side_effect=AssertionError("observation made a provider call")))

    def record(self, oid, kind):
        rec = {"id": oid, "role": "guarantee", "kind": kind, "revision": 1, "required": True}
        rec["lifecycle"] = {milestone: {"outcome": ("PASS" if applies else "NOT_APPLICABLE")}
                            for milestone, (applies, _) in lifecycle.applicability(rec).items()}
        if kind != "non_vacuity":
            rec["lifecycle"]["TESTED"]["outcome"] = "PENDING"
        return rec

    def serialized_gate(self):
        return {**copy.deepcopy(self.gate), "diagnostics": [d.to_json() for d in self.gate["diagnostics"]]}

    def refresh_records(self):
        self.report["obligations"] = {oid: {key: copy.deepcopy(rec[key]) for key in ("role", "kind", "revision", "required")}
                                      | {"outcomes": {m: row["outcome"] for m, row in rec["lifecycle"].items()}}
                                      for oid, rec in self.current.items()}
        self.snapshot["claims"] = [{"claim_id": f"{m}:{oid}@{rec['revision']}", "required": True, "outcome": rec["lifecycle"][m]["outcome"]}
                                   for oid, rec in self.current.items() for m in lifecycle.CONTRACT_MILESTONES
                                   if lifecycle.applicability(rec)[m][0]]
        self.snapshot["claims"] += [{"claim_id": f"END_TO_END_VERIFIED:{oid}@{rec['revision']}", "required": True,
                                     "outcome": rec["lifecycle"]["END_TO_END_VERIFIED"]["outcome"]}
                                    for oid, rec in self.current.items() if lifecycle.applicability(rec)["END_TO_END_VERIFIED"][0]]

    def observe(self, report=None, configuration=None):
        return bootstrap.native_audit(self.pkg, report or self.report, configuration)

    def test_counts_keep_nonvacuity_required_without_an_implementation_claim(self):
        audit = self.observe()
        self.assertEqual(2, audit["all_required_guarantees"])
        self.assertEqual(1, audit["required_guarantees"])
        self.assertEqual(1, audit["required_e2e_passed"])
        self.assertEqual(1, audit["required_non_vacuity_witnesses"])
        self.assertEqual("BLOCKED", audit["mechanical_status"])
        self.assertEqual("NOT_APPLICABLE", audit["per_obligation_outcomes"]["W"]["END_TO_END_VERIFIED"])

    def test_report_cannot_omit_or_change_registered_applicability_metadata(self):
        changes = (lambda r: r["obligations"]["G"].pop("kind"),
                   lambda r: r["obligations"]["G"].pop("required"),
                   lambda r: r["obligations"]["G"].update(required=False),
                   lambda r: r["obligations"]["G"].update(kind="non_vacuity"),
                   lambda r: r["obligations"]["G"].update(role="declaration"),
                   lambda r: r["obligations"].pop("G"),
                   lambda r: r["obligations"].update(extra=copy.deepcopy(r["obligations"]["G"])),
                   lambda r: r["obligations"]["G"]["outcomes"].update(END_TO_END_VERIFIED="NOT_APPLICABLE"))
        for index, edit in enumerate(changes):
            with self.subTest(change=index):
                report = copy.deepcopy(self.report)
                edit(report)
                audit = self.observe(report)
                self.assertEqual("BLOCK", audit["status"], audit)

    def test_registered_applicable_guarantee_outcomes_cannot_be_waived(self):
        for outcome in ("PENDING", "STALE", "UNSUPPORTED", "FAIL", "NOT_APPLICABLE"):
            with self.subTest(outcome=outcome):
                self.current["G"]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"] = outcome
                self.refresh_records()
                self.report["terminal_status"] = "VERIFIED"
                audit = self.observe()
                self.assertEqual("BLOCK", audit["status"], audit)
                self.assertEqual(1, audit["required_guarantees"])
                self.assertEqual(0, audit["required_e2e_passed"])
                self.assertFalse(audit["all_required_e2e"])

    def test_required_nonvacuity_needs_current_contract_proof_and_claim(self):
        self.report["terminal_status"] = "VERIFIED"
        proof_issue = "Required current native claim is missing or has not passed: PROVED:W@1"
        for outcome in ("PENDING", "STALE", "FAIL"):
            with self.subTest(proved=outcome):
                self.current["W"]["lifecycle"]["PROVED"]["outcome"] = outcome
                self.refresh_records()
                audit = self.observe()
                self.assertEqual("BLOCK", audit["status"], audit)
                self.assertEqual(1, audit["required_non_vacuity_witnesses"])
                self.assertIn(proof_issue, audit["issues"])
        self.current["W"]["lifecycle"]["PROVED"]["outcome"] = "PASS"
        self.refresh_records()
        self.snapshot["claims"] = [c for c in self.snapshot["claims"] if c["claim_id"] != "PROVED:W@1"]
        audit = self.observe()
        self.assertEqual("BLOCK", audit["status"], audit)
        self.assertIn(proof_issue, audit["issues"])

    def test_empty_applicable_implementation_set_cannot_establish_endpoint(self):
        self.current.pop("G")
        self.refresh_records()
        self.report["terminal_status"] = "VERIFIED"
        audit = self.observe()
        self.assertEqual("BLOCK", audit["status"], audit)
        self.assertEqual(1, audit["all_required_guarantees"])
        self.assertEqual(0, audit["required_guarantees"])
        self.assertEqual(0, audit["required_e2e_passed"])
        self.assertFalse(audit["all_required_e2e"])

    def test_frozen_profiles_override_wrong_ambient_home_and_restore_environment(self):
        def gate(pkg, configuration):
            self.assertEqual(str(self.profile.parent), os.environ["VERISLOP_CONFIG_HOME"])
            resolved = config.resolve(config.load(configuration), config.load_user_profiles(None))
            self.assertEqual([], resolved.diagnostics)
            return copy.deepcopy(self.gate)
        with patch.object(review, "gate", side_effect=gate) as observed:
            for home in ("absent-profile-home", "other-profile-home"):
                with self.subTest(ambient=home), patch.dict(os.environ, {"VERISLOP_CONFIG_HOME": str(self.root / home),
                                                                       "VERISLOP_COLLABORATION_UNUSED": "ambient-placeholder"}):
                    before = dict(os.environ)
                    audit = self.observe(configuration=self.configuration)
                    self.assertEqual(before, dict(os.environ))
                    self.assertFalse(any("release review" in issue for issue in audit["issues"]), audit)
            self.assertEqual(2, observed.call_count)
        self.no_call.assert_not_called()

    def test_changed_frozen_provider_inputs_block_before_context_selection(self):
        for path in (self.profile, self.configuration):
            with self.subTest(input=path.name), patch.object(review, "gate") as gate:
                old = path.read_bytes()
                fsutil.atomic_write(path, old + b"\n")
                try:
                    before = dict(os.environ)
                    audit = self.observe(configuration=self.configuration)
                    self.assertEqual("BLOCK", audit["status"], audit)
                    gate.assert_not_called()
                    self.assertEqual(before, dict(os.environ))
                finally:
                    fsutil.atomic_write(path, old)

    def test_current_gate_checkpoint_and_diagnostic_disagreements_block_forged_acceptance(self):
        with patch.object(review, "gate", side_effect=lambda *args: copy.deepcopy(self.gate)):
            for changed in ("checkpoint", "diagnostic", "accepted-flag", "extra-gate-field"):
                with self.subTest(changed=changed):
                    report = copy.deepcopy(self.report)
                    if changed == "checkpoint":
                        report["review"]["checkpoints"]["release"] = "REVIEW_ACCEPTED"
                    elif changed == "diagnostic":
                        report["review"]["diagnostics"] = []
                    elif changed == "accepted-flag":
                        report["release_status"] = "ACCEPTED"
                    else:
                        report["review"]["unregistered_observation"] = True
                    self.assertEqual("BLOCK", self.observe(report, self.configuration)["status"])

    def test_provider_observation_restores_present_and_absent_values_after_gate_exception(self):
        for absent in (False, True):
            with self.subTest(absent=absent), patch.dict(os.environ):
                if absent:
                    os.environ.pop("VERISLOP_CONFIG_HOME", None)
                    os.environ.pop("VERISLOP_COLLABORATION_UNUSED", None)
                else:
                    os.environ.update(VERISLOP_CONFIG_HOME=str(self.root / "ambient"), VERISLOP_COLLABORATION_UNUSED="ambient-placeholder")
                before = dict(os.environ)
                with patch.object(review, "gate", side_effect=RuntimeError("authored observation failure")):
                    audit = self.observe(configuration=self.configuration)
                self.assertEqual("BLOCK", audit["status"], audit)
                self.assertEqual(before, dict(os.environ))
                self.assertTrue(any("authored observation failure" in issue for issue in audit["issues"]), audit)


if __name__ == "__main__":
    unittest.main()
