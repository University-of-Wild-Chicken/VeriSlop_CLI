"""Compiler subprocess observations with fresh fixtures; no Lean or resource stress."""
from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from verislop import canonical, export, leanbridge, policy, sandbox
from verislop.bridges import vscore3_checker as checker
from verislop.bridges.check import _evidence
from verislop.bridges.manifest import PackageReader, InvalidPackage
from verislop.evidence import EvidenceStore
from verislop.errors import Diagnostic, InfrastructureError


class CompileProcessEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verislop-process-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tc = leanbridge.Toolchain("synthetic-pin", self.root / "toolchain")

    def compile(self, *, named=True, source=b"generic source", stdout=b"", stderr=b"",
                returncode=0, timed_out=False, artifact=True, elapsed=1.125):
        stage = self.root / ("named" if named else "legacy")
        profile = {"filesystem_backend": "synthetic-wrapper", "network_namespace": True,
                   "read_only_paths": ["synthetic-grant"], "nested": {"retained": ["all"]}}
        observed = {}

        def completed(argv, cwd, **kwargs):
            observed.update(argv=list(argv), cwd=cwd, kwargs=kwargs)
            if artifact:
                path = cwd / argv[argv.index("-o") + 1]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic compiled bytes")
            return sandbox.SandboxResult(["synthetic-wrapper", "--", *argv], returncode,
                                         stdout, stderr, timed_out, elapsed, profile)

        with patch.object(sandbox, "run", side_effect=completed):
            if named:
                result, parts = leanbridge.compile_named_module(
                    self.tc, stage, "Generic.Process", source, {}, read_only=[], timeout=17.5, memory_mb=32)
            else:
                result = leanbridge.compile_module(self.tc, source, stage, timeout=17.5, memory_mb=32)
                parts = None
        return result, parts, observed, profile

    def assert_output(self, record, data):
        self.assertEqual(set(record), {"byte_count", "sha256", "content_b64"})
        self.assertEqual(record["byte_count"], len(data))
        self.assertEqual(record["sha256"], canonical.digest(data))
        self.assertEqual(base64.b64decode(record["content_b64"], validate=True), data)

    def test_success_retains_closed_record_and_distinct_requested_limits(self):
        result, parts, observed, _ = self.compile(stdout=b"ordinary output\n", stderr=b"warning\n")
        self.assertTrue(result.ok)
        self.assertEqual(parts, {".olean": b"synthetic compiled bytes"})
        record = result.process_evidence
        self.assertEqual(set(record), {"format", "input", "requested_argv", "launcher_argv",
                                      "working_directory", "returncode", "timed_out", "requested_limits",
                                      "elapsed_seconds", "sandbox_profile", "stdout", "stderr",
                                      "reported_stderr_panics"})
        self.assertEqual(record["format"], "verislop.lean-compile-process/1")
        self.assertEqual(record["input"], {"module": "Generic.Process",
                                          "module_source_sha256": canonical.digest(b"generic source"),
                                          "setup_sha256": canonical.digest((observed["cwd"] / "setup.json").read_bytes())})
        self.assertEqual(record["requested_argv"], observed["argv"])
        self.assertEqual(record["launcher_argv"], ["synthetic-wrapper", "--", *observed["argv"]])
        self.assertEqual(record["working_directory"], str(observed["cwd"].resolve()))
        self.assertEqual(record["returncode"], 0)
        self.assertFalse(record["timed_out"])
        self.assertEqual(record["elapsed_seconds"], "1.125")
        self.assertEqual(record["requested_limits"], {
            "lean_heap_mb": 32, "sandbox_address_space_bytes": (32 + 16384) * 1024 * 1024,
            "sandbox_cpu_soft_seconds": 22, "sandbox_cpu_hard_seconds": 27,
            "sandbox_file_size_bytes": 1024 * 1024 * 1024, "sandbox_core_bytes": 0,
            "wall_timeout_seconds": "17.5"})
        self.assertEqual(observed["kwargs"]["memory_mb"], 32 + 16384)
        self.assertEqual(observed["kwargs"]["cpu_seconds"], 22)
        self.assertEqual(observed["kwargs"]["fsize_mb"], 1024)
        self.assert_output(record["stdout"], b"ordinary output\n")
        self.assert_output(record["stderr"], b"warning\n")
        # Strict JSON roundtrip also establishes durations were not emitted as floats.
        self.assertEqual(canonical.loads(canonical.dumps(record)), record)

    def test_legacy_compile_api_fields_and_consumer_contract_remain_compatible(self):
        result, _, _, _ = self.compile(named=False)
        self.assertTrue(result.ok)
        self.assertEqual(result.olean.name, "VeriSlopContract.olean")
        self.assertEqual(result.messages, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.sorry_positions, [])
        self.assertFalse(result.timed_out)
        self.assertEqual(int(result.wall_seconds * 1000), 1125)
        self.assertEqual(result.raw_stderr, "")
        self.assertEqual(result.process_evidence["input"], {
            "module": leanbridge.MODULE, "module_source_sha256": canonical.digest(b"generic source"),
            "setup_sha256": None})
        synthetic = leanbridge.CompileResult(True, Path("legacy.olean"), [], [], [], False, 0, {}, "tail")
        self.assertIsNone(synthetic.process_evidence)
        self.assertEqual(synthetic.raw_stderr, "tail")

    def test_parsed_lean_error_and_full_stderr_panic_coexist(self):
        message = {"severity": "error", "data": "generic unification rejected", "pos": {"line": 7, "column": 2}}
        stdout = json.dumps(message).encode() + b"\nnon-json output\xff\n"
        stderr = b"INTERNAL PANIC: out of memory\n" + b"x" * 5000 + b"\x00\xffend"
        result, parts, _, _ = self.compile(stdout=stdout, stderr=stderr, returncode=1)
        self.assertFalse(result.ok)
        self.assertEqual(parts, {})
        self.assertEqual(result.messages, [message])
        self.assertEqual(result.errors, ["7:2: generic unification rejected"])
        self.assertNotIn("INTERNAL PANIC", result.raw_stderr)  # Legacy tail remains compatible.
        record = result.process_evidence
        self.assertEqual(record["reported_stderr_panics"], [
            {"kind": "out_of_memory", "report": "INTERNAL PANIC: out of memory"}])
        self.assert_output(record["stdout"], stdout)
        self.assert_output(record["stderr"], stderr)
        self.assertEqual(record["returncode"], 1)
        self.assertFalse(record["timed_out"])

    def test_nonzero_exit_with_no_parsed_error_preserves_existing_fallback(self):
        result, _, _, _ = self.compile(stderr=b"generic failed process", returncode=3)
        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["lean exited with code 3: generic failed process"])
        self.assertEqual(result.process_evidence["returncode"], 3)
        self.assertEqual(result.process_evidence["reported_stderr_panics"], [])

    def test_timeout_flag_and_negative_returncode_are_separate_observations(self):
        for timed_out in (False, True):
            with self.subTest(timed_out=timed_out):
                result, _, _, _ = self.compile(returncode=-9, timed_out=timed_out)
                self.assertFalse(result.ok)
                record = result.process_evidence
                self.assertEqual(record["returncode"], -9)
                self.assertIs(record["timed_out"], timed_out)
                self.assertEqual(record["reported_stderr_panics"], [])
                self.assertEqual(result.errors, ["elaboration timed out after 17.5s"] if timed_out else
                                 ["lean exited with code -9: "])
                self.assertNotIn("termination_signal", record)
                self.assertNotIn("peak_rss", record)
                self.assertNotIn("resource_cause", record)

    def test_zero_exit_with_parsed_error_still_rejects(self):
        stdout = b'{"severity":"error","data":"generic error"}\n'
        result, _, _, _ = self.compile(stdout=stdout)
        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["?:?: generic error"])
        self.assertEqual(result.process_evidence["returncode"], 0)

    def test_missing_artifact_still_rejects_and_keeps_process_evidence(self):
        result, parts, _, _ = self.compile(artifact=False)
        self.assertFalse(result.ok)
        self.assertEqual(parts, {})
        self.assertEqual(result.errors, ["compiled Lean artifact is missing, linked, non-regular, or oversized"])
        self.assertEqual(result.process_evidence["returncode"], 0)

    def test_sorry_warning_preserves_existing_caller_gate(self):
        stdout = b'{"severity":"warning","data":"declaration uses `sorry`","pos":{"line":3,"column":1}}\n'
        result, _, _, _ = self.compile(stdout=stdout)
        self.assertTrue(result.ok)  # Existing callers reject via sorry_positions.
        self.assertEqual(result.sorry_positions, [{"line": 3, "column": 1}])
        self.assertFalse(result.ok and not result.sorry_positions)

    def test_panic_report_does_not_change_existing_acceptance_predicate(self):
        result, _, _, _ = self.compile(stderr=b"INTERNAL PANIC: out of memory\n")
        self.assertTrue(result.ok)  # Telemetry is additive; no new classification rule.
        self.assertEqual(len(result.process_evidence["reported_stderr_panics"]), 1)

    def test_profile_is_fully_retained_and_detached(self):
        result, _, _, profile = self.compile()
        self.assertEqual(result.process_evidence["sandbox_profile"], profile)
        profile["nested"]["retained"].append("later mutation")
        self.assertEqual(result.process_evidence["sandbox_profile"]["nested"], {"retained": ["all"]})

    def test_unmeasured_elapsed_is_explicitly_unavailable(self):
        result, _, _, _ = self.compile(elapsed=None)
        self.assertIsNone(result.process_evidence["elapsed_seconds"])
        canonical.dumps(result.process_evidence)

    def failure_details(self, result, source=b"generic proof", *, severity="blocking"):
        ctx = SimpleNamespace(claim={"claim_id": "GENERIC"}, inputs={
            "source": ("vscore-source", b"generic current source"),
            "relation": ("vscore-relation", b"generic relation"),
            "proof_source": ("vscore-proof", source)})
        exc = checker._compile_failure("CANDIDATE_BUILD_FAILURE", "generic rejected compile", ctx,
                                       SimpleNamespace(text="generic goal"), "Generic.Process", source,
                                       result, severity=severity)
        return exc.diagnostics[0]

    def test_diagnostic_binds_current_attempt_inputs_and_exact_output_artifact(self):
        proof = b"fresh rejected generic proof"
        result, _, _, _ = self.compile(source=proof, returncode=1, stderr=b"retained\xffstderr")
        diagnostic = self.failure_details(result, proof)
        self.assertEqual(diagnostic.severity, "blocking")
        details = diagnostic.details
        self.assertEqual(details["module_source_hash"], canonical.digest(proof))
        self.assertEqual(details["input_hashes"]["proof_source"], canonical.digest(proof))
        self.assertEqual(details["input_hashes"]["source"], canonical.digest(b"generic current source"))
        record = details["process_evidence"]["record"]
        self.assertEqual(details["process_evidence"]["availability"], "available")
        self.assertEqual(record["input"]["module_source_sha256"], details["module_source_hash"])
        self.assert_output(record["stderr"], b"retained\xffstderr")
        # This is the same canonical artifact path used by existing bridge diagnostics.
        retained = canonical.loads(canonical.dumps(details))
        self.assertEqual(retained, details)
        result.process_evidence["stderr"]["content_b64"] = "later change"
        self.assert_output(record["stderr"], b"retained\xffstderr")

    def test_missing_telemetry_is_explicit_and_never_inherits_prior_attempt(self):
        old, _, _, _ = self.compile(source=b"old proof", returncode=1, stderr=b"old panic")
        self.assertEqual(self.failure_details(old, b"old proof").details["process_evidence"]["availability"], "available")
        current = leanbridge.CompileResult(False, None, [], ["new synthetic failure"], [], False, 0)
        diagnostic = self.failure_details(current, b"new proof", severity="infrastructure")
        self.assertEqual(diagnostic.severity, "infrastructure")
        self.assertEqual(diagnostic.details["process_evidence"], {"availability": "unavailable", "record": None})
        self.assertEqual(diagnostic.details["module_source_hash"], canonical.digest(b"new proof"))

    def test_fresh_compile_cannot_inherit_stderr_or_source_from_prior_compile(self):
        first, _, _, _ = self.compile(source=b"first", returncode=1, stderr=b"INTERNAL PANIC: out of memory\n")
        second, _, _, _ = self.compile(source=b"second", stdout=b"fresh output")
        self.assertNotEqual(first.process_evidence["input"], second.process_evidence["input"])
        self.assert_output(second.process_evidence["stderr"], b"")
        self.assert_output(second.process_evidence["stdout"], b"fresh output")
        self.assertEqual(second.process_evidence["reported_stderr_panics"], [])

    def test_failure_before_invocation_has_no_prior_process_record(self):
        self.compile(source=b"prior", returncode=1)
        with patch.object(sandbox, "run") as run, self.assertRaises(InfrastructureError) as failure:
            leanbridge.compile_named_module(self.tc, self.root / "invalid", "Invalid-Module", b"next", {}, read_only=[])
        run.assert_not_called()
        self.assertEqual(failure.exception.diagnostics[0].details, {})

    def test_completed_process_keeps_evidence_on_changed_stage_infrastructure_error(self):
        stage = self.root / "changed-stage"

        def completed(argv, cwd, **kwargs):
            cwd.rename(self.root / "old-stage")
            cwd.mkdir()
            return sandbox.SandboxResult(argv, 0, b"completed output", b"", False, 0.5, {})

        with patch.object(sandbox, "run", side_effect=completed), self.assertRaises(InfrastructureError) as failure:
            leanbridge.compile_module(self.tc, b"stage fixture", stage)
        diagnostic = failure.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "VERIFIER_FAILURE")
        self.assertEqual(diagnostic.severity, "infrastructure")
        self.assertIn("stage identity changed", diagnostic.message)
        process = diagnostic.details["process_evidence"]["record"]
        self.assertEqual(process["returncode"], 0)
        self.assertEqual(process["input"]["module_source_sha256"], canonical.digest(b"stage fixture"))
        self.assertEqual(process["working_directory"], str(stage.resolve()))
        self.assert_output(process["stdout"], b"completed output")

    def test_completed_process_keeps_evidence_on_unsafe_compiled_part(self):
        for named in (False, True):
            with self.subTest(named=named):
                stage = self.root / ("unsafe-named" if named else "unsafe-legacy")

                def completed(argv, cwd, **kwargs):
                    path = cwd / argv[argv.index("-o") + 1]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic compiled bytes")
                    path.with_name(path.name + ".server").symlink_to(path)
                    return sandbox.SandboxResult(argv, 0, b"", b"artifact validation fixture", False, 0.25, {})

                with patch.object(sandbox, "run", side_effect=completed), self.assertRaises(InfrastructureError) as failure:
                    if named:
                        leanbridge.compile_named_module(self.tc, stage, "Generic.Unsafe", b"fresh fixture", {}, read_only=[])
                    else:
                        leanbridge.compile_module(self.tc, b"fresh fixture", stage)
                diagnostic = failure.exception.diagnostics[0]
                self.assertEqual(diagnostic.code, "VERIFIER_FAILURE")
                self.assertEqual(diagnostic.severity, "infrastructure")
                process = diagnostic.details["process_evidence"]["record"]
                self.assertEqual(process["returncode"], 0)
                self.assertEqual(process["input"]["module_source_sha256"], canonical.digest(b"fresh fixture"))
                self.assert_output(process["stderr"], b"artifact validation fixture")

    def build_fixture(self, *, proof_failure=False, unsafe_proof_part=False, audit_failure=False, kernel_failure=False):
        ctx = SimpleNamespace(claim={"claim_id": "GENERIC"}, policy={
            "build_timeout_seconds": 17.5, "kernel_timeout_seconds": 17.5, "memory_mb": 32,
            "require_network_isolation": True, "require_filesystem_isolation": True},
            inputs={"source": ("vscore-source", b"generic program"),
                    "relation": ("vscore-relation", b"generic relation"),
                    "proof_source": ("vscore-proof", b"generic proof")}, contract_module=b"synthetic accepted bundle")
        spec = SimpleNamespace(text="generic goal")

        def stage_contract(artifact, directory):
            leanbridge.write_module_parts(directory, checker.T.CONTRACT_MODULE, {".olean": b"synthetic accepted bytes"})

        def completed(argv, cwd, **kwargs):
            path = cwd / argv[argv.index("-o") + 1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic compiled bytes")
            is_proof = path.stem == checker.T.PROOF_MODULE
            if unsafe_proof_part and is_proof:
                path.with_name(path.name + ".server").symlink_to(path)
            return sandbox.SandboxResult(["synthetic-launcher", *argv], 1 if proof_failure and is_proof else 0,
                                         b"", b"INTERNAL PANIC: out of memory\n" if proof_failure and is_proof else b"",
                                         False, 0.25, {"read_only_paths": []})

        observed_audit = {}

        def audited(tc, got_ctx, got_spec, resp, modules, compiles, isolation, with_proof):
            observed_audit.update(compiles=copy.deepcopy(compiles))
            if audit_failure:
                raise checker.EdgeFailure([Diagnostic("KERNEL_REJECTION", "generic audit rejected")])
            return checker.Build({"compiles": compiles}, {}, modules, canonical.digest(b"fixture proposition"), {}, [])

        with patch.object(checker.T, "library_sources", return_value={"Generic.Support": b"generic library"}), \
             patch.object(leanbridge, "_stage_module", side_effect=stage_contract), \
             patch.object(sandbox, "run", side_effect=completed), \
             patch.object(leanbridge, "run_kernel_tool_modules", return_value={},
                          side_effect=leanbridge._infra("generic kernel unavailable") if kernel_failure else None), \
             patch.object(checker, "_audit", side_effect=audited):
            build = checker.run_build(self.tc, ctx, spec)
        return build, observed_audit

    def test_successful_build_inventory_preserves_every_compiler_and_deterministic_fields(self):
        build, observed = self.build_fixture()
        self.assertEqual(set(build.process_evidence), {"Generic.Support", checker.T.GOAL_MODULE, checker.T.PROOF_MODULE})
        for module, wrapper in build.process_evidence.items():
            self.assertEqual(wrapper["availability"], "available")
            self.assertEqual(wrapper["record"]["input"]["module"], module)
            self.assertEqual(wrapper["record"]["returncode"], 0)
        self.assertEqual(build.observation, {"compiles": observed["compiles"]})
        self.assertNotIn("process_evidence", checker.DETERMINISTIC)
        self.assertNotIn("compile_process_evidence", checker.DETERMINISTIC)
        old = checker.Build({}, {}, {}, "fixture", {}, [])
        self.assertEqual(old.process_evidence, {})

    def test_rejected_build_retains_current_and_preceding_completed_compilers(self):
        with self.assertRaises(checker.EdgeFailure) as failure:
            self.build_fixture(proof_failure=True)
        diagnostic = failure.exception.diagnostics[0]
        self.assertEqual((diagnostic.code, diagnostic.severity), ("CANDIDATE_BUILD_FAILURE", "blocking"))
        inventory = diagnostic.details["build_process_evidence"]
        self.assertEqual(set(inventory), {"Generic.Support", checker.T.GOAL_MODULE, checker.T.PROOF_MODULE})
        self.assertEqual(inventory[checker.T.PROOF_MODULE], diagnostic.details["process_evidence"])
        self.assertEqual(inventory["Generic.Support"]["record"]["returncode"], 0)
        self.assertEqual(inventory[checker.T.PROOF_MODULE]["record"]["returncode"], 1)

    def test_build_infrastructure_diagnostic_retains_completed_inventory(self):
        with self.assertRaises(InfrastructureError) as failure:
            self.build_fixture(unsafe_proof_part=True)
        diagnostic = failure.exception.diagnostics[0]
        self.assertEqual((diagnostic.code, diagnostic.severity), ("VERIFIER_FAILURE", "infrastructure"))
        inventory = diagnostic.details["build_process_evidence"]
        self.assertEqual(set(inventory), {"Generic.Support", checker.T.GOAL_MODULE, checker.T.PROOF_MODULE})
        self.assertEqual(inventory[checker.T.PROOF_MODULE], diagnostic.details["process_evidence"])

    def test_later_kernel_or_audit_failure_retains_compiler_inventory_without_kernel_telemetry(self):
        for phase, expected_type, expected_code, expected_severity in (
            ("kernel", InfrastructureError, "VERIFIER_FAILURE", "infrastructure"),
            ("audit", checker.EdgeFailure, "KERNEL_REJECTION", "blocking"),
        ):
            with self.subTest(phase=phase), self.assertRaises(expected_type) as failure:
                self.build_fixture(kernel_failure=phase == "kernel", audit_failure=phase == "audit")
            diagnostic = failure.exception.diagnostics[0]
            self.assertEqual((diagnostic.code, diagnostic.severity), (expected_code, expected_severity))
            self.assertEqual(set(diagnostic.details["build_process_evidence"]),
                             {"Generic.Support", checker.T.GOAL_MODULE, checker.T.PROOF_MODULE})
            self.assertNotIn("process_evidence", diagnostic.details)

    def test_preview_returns_detached_optional_inventory_with_existing_info(self):
        pol = next(iter(policy.POLICIES.values()))
        profile_path = self.root / "generic-profile.json"
        profile_path.write_bytes(canonical.dumps({"profile_id": "generic-profile"}))
        (self.root / "generic-contract.bundle").write_bytes(b"synthetic accepted module")
        cert = {"policy": {"id": pol["id"], "hash": policy.policy_hash(pol)},
                "toolchain": {"pin": "synthetic-pin"}, "artifacts": {
                    "profile": {"path": profile_path.name, "sha256": canonical.digest(profile_path.read_bytes())},
                    "olean": {"path": "generic-contract.bundle"}}}
        pkg = SimpleNamespace(root=self.root, path=lambda name: self.root / name)
        relation = {"schema_version": "0.3", "format": checker.T.RELATION_FORMAT, "template": checker.T.TEMPLATE,
                    "source_slot": checker.SLOTS["source"], "proof_slot": checker.SLOTS["proof"],
                    "bindings": [{"symbol": "generic", "entry": "generic"}]}
        inventory = {"Generic.Process": {"availability": "unavailable", "record": None}}
        build = checker.Build({}, {}, {}, "generic proposition", {}, [], inventory)
        spec = SimpleNamespace(symbols=[])
        with patch.object(export, "verified_ir", return_value=({"obligations": {}}, "generic IR", cert, [])), \
             patch.object(checker, "derive_goal", return_value=spec), \
             patch.object(leanbridge, "resolve_toolchain", return_value=self.tc), \
             patch.object(checker, "run_build", return_value=build):
            got_spec, got_build, info = checker.preview(pkg, b"generic source", canonical.dumps(relation), b"generic proof")
        self.assertIs(got_spec, spec)
        self.assertIs(got_build, build)
        self.assertEqual(info["compile_process_evidence"], inventory)
        self.assertTrue(info["proof_checked"])
        self.assertEqual(info["proposition_hash"], "generic proposition")
        self.assertIsInstance(info["model"], bytes)
        self.assertIsInstance(info["profile"], bytes)
        inventory["Generic.Process"]["availability"] = "later mutation"
        self.assertEqual(info["compile_process_evidence"]["Generic.Process"]["availability"], "unavailable")

    def test_success_inventory_is_durable_hash_bound_and_outside_descriptor_comparison(self):
        build, _ = self.build_fixture()
        # Semantic descriptor/schema checks are outside this serialization fixture.
        # EvidenceStore and the registered raw-evidence reader remain real.
        ctx = SimpleNamespace(bridge_id="generic", edge={"edge_id": "generic-edge"}, claim={"claim_id": "GENERIC"},
                              inputs={"source": ("source-slot", b"generic program")},
                              plan={"accepted_ir": {}, "acceptance_certificate": {}})
        spec = SimpleNamespace(text="generic goal", source_bytes=b"generic program")
        build.ir = {"program": {}, "signatures": [], "enums": [], "bindings": []}
        baseline = {"semantic_acceptance": True, "fixture_binding": canonical.digest(b"generic semantic descriptor")}
        publication = self.root / "publication"
        with patch.object(checker, "_schema"), \
             patch.object(checker, "_semantic_descriptor", return_value={"semantic_edge_root": canonical.digest(b"generic root")}), \
             patch.object(checker, "_evidence_result", return_value=baseline):
            files = checker.outputs(ctx, spec, build, build, "generic-run", self.root / "evidence-stage")
            changed = copy.deepcopy(build)
            changed.process_evidence[checker.T.PROOF_MODULE]["record"]["elapsed_seconds"] = "9.75"
            fresh = checker.outputs(ctx, spec, changed, changed, "generic-run", self.root / "fresh-evidence-stage")
        cert = canonical.loads(files[checker.CERTIFICATE])
        self.assertEqual(checker._certificate_descriptor(cert),
                         checker._certificate_descriptor(canonical.loads(fresh[checker.CERTIFICATE])))
        self.assertEqual(files["builds/A.json"], fresh["builds/A.json"])
        self.assertEqual(files["builds/B.json"], fresh["builds/B.json"])
        for name, data in files.items():
            path = publication / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        reader = PackageReader(publication)
        self.addCleanup(reader.close)
        evidence = _evidence(reader, cert["evidence"])
        inventory = evidence.result["compile_process_evidence"]
        self.assertEqual(inventory, {"format": "verislop.vscore-compile-process-inventory/1",
                                     "builds": {"A": build.process_evidence, "B": build.process_evidence}})
        self.assertEqual({k: evidence.result[k] for k in baseline}, baseline)
        self.assertTrue(EvidenceStore(publication, "generic-run").load()[0].valid)
        # Existing verification accepts additive raw fields but still rejects byte tampering.
        raw_path = publication / evidence.record["raw_result_ref"]
        raw_path.write_bytes(raw_path.read_bytes() + b" ")
        with self.assertRaises(InvalidPackage):
            with_reader = PackageReader(publication)
            try:
                _evidence(with_reader, cert["evidence"])
            finally:
                with_reader.close()


if __name__ == "__main__":
    unittest.main()
