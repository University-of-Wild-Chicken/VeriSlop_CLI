"""Fresh universal proof-support and complete diagnostic fixtures; no model calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from verislop import agents, canonical, export, leanbridge, policy, schemas
from verislop.bridges import vscore3_checker as checker
from verislop.errors import Diagnostic, InfrastructureError
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore3_source as source, vscore3_target as target


class ProofSupportCatalogTests(unittest.TestCase):
    def test_pinned_catalog_signatures_clean_builds_and_kernel_replay(self):
        tc = leanbridge.resolve_toolchain()
        catalog = target.proof_support_catalog()
        transport = target.library_sources()[catalog["module"]]
        self.assertEqual(catalog["source_hash"], canonical.digest(transport))
        self.assertFalse(catalog["global_simp_rules"])
        self.assertEqual(len(catalog["lemmas"]), 6)
        proof = "import VSCore3\nuniverse u v\nnamespace GenericProofSupport\n"
        for i, row in enumerate(catalog["lemmas"]):
            proof += f"theorem signature_{i} : {row['signature']} := @{row['name']}\n"
        proof += "theorem closed_precondition : (2 : Nat) < 5 := by decide +kernel\n"
        proof += "end GenericProofSupport\n"
        inventories = []
        for _ in range(2):
            with tempfile.TemporaryDirectory(prefix="verislop-generic-proof-support-") as tmp:
                root = Path(tmp)
                env = {**os.environ, "LEAN_PATH": str(root)}
                modules = {}
                sources = dict(target.library_sources(), GenericProofSupport=proof.encode())
                for module, data in sources.items():
                    rel = Path(module.replace(".", "/") + ".lean")
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    result = subprocess.run([str(tc.lean), "-o", str(rel.with_suffix(".olean")), str(rel)],
                                            cwd=root, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn("declaration uses `sorry`", result.stdout + result.stderr)
                    modules[module] = leanbridge.module_parts(root, module)
                replay = leanbridge.run_kernel_tool_modules(tc, modules, "GenericProofSupport",
                                                           {"export": True, "axioms": True})
                self.assertTrue(replay.get("import", {}).get("ok"), replay)
                self.assertTrue(replay.get("replay", {}).get("ok"), replay)
                self.assertNotIn("sorryAx", str(replay))
                inventories.append({module: canonical.digest_json(
                    {suffix: canonical.digest(part) for suffix, part in parts.items()})
                    for module, parts in modules.items()})
                bad = root / "BadUniversal.lean"
                bad.write_text("import VSCore3\nexample : ∀ (p : Prop), p := by intro p; rfl\n")
                rejected = subprocess.run([str(tc.lean), str(bad)], cwd=root, env=env,
                                          capture_output=True, text=True)
                self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(inventories[0], inventories[1])


class CompleteProofDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-generic-proof-diagnostics-")
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / "run")
        self.pkg.ensure("generic-proof-diagnostics")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)
        self.params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                       "backend": "verislop.backend.vscore/0.3", "backend_version": "0.3"}
        self.source = source.compile_surface(
            'program "vscore/0.3" profile "data-pipeline/0.3"; entry echo(x:Bool)->Bool{x}')
        self.relation = {"schema_version": "0.3", "format": target.RELATION_FORMAT,
                         "template": target.TEMPLATE, "source_slot": "vscore-source",
                         "proof_slot": "vscore-proof", "bindings": [{"symbol": "echo", "entry": "echo"}]}
        self.relation_bytes = canonical.dumps(self.relation)
        self.fixed = {"parameters": self.params, "accepted_reference": {}, "accepted_packages": {},
                      "accepted_profile": {}, "lean_toolchain": leanbridge.DEFAULT_TOOLCHAIN}
        self.info = {"proposition_hash": "sha256:" + "a" * 64, "model": b"{}", "profile": b"{}"}
        self.spec = SimpleNamespace(text="generic generated goal", refinement_symbols={"echo"})

    def compile_failure(self, proof: bytes, errors: list[str], severity="blocking"):
        messages = [{"severity": "error", "data": error, "pos": {"line": i + 1, "column": 0}}
                    for i, error in enumerate(errors)]
        result = leanbridge.CompileResult(False, None, messages, errors, [], False, 0,
                                         raw_stderr="available stderr tail")
        ctx = SimpleNamespace(claim={"claim_id": "GENERIC"}, inputs={
            "source": ("vscore-source", self.source), "relation": ("vscore-relation", self.relation_bytes),
            "proof_source": ("vscore-proof", proof)})
        return checker._compile_failure("CANDIDATE_BUILD_FAILURE", "generic compile failed", ctx, self.spec,
                                        target.PROOF_MODULE, proof, result, severity=severity)

    def test_complete_error_inventory_and_explicit_message_compaction(self):
        proof = b"generic rejected proof"
        errors = [f"{i}: missing_generic_{i}" for i in range(35)]
        errors[7] += "x" * 2500
        exc = self.compile_failure(proof, errors)
        details = exc.diagnostics[0].details
        self.assertEqual(details["errors"], errors)
        self.assertEqual(details["error_count"], 35)
        self.assertEqual(len(details["messages"]), 35)
        self.assertEqual(details["module_source_hash"], canonical.digest(proof))
        self.assertEqual(details["input_hashes"]["source"], canonical.digest(self.source))
        self.assertEqual(details["goal_hash"], canonical.digest(self.spec.text.encode()))
        self.assertTrue(details["stderr_retention"]["may_be_truncated"])
        record = agents._vscore_failure_record(exc, self.source, self.relation_bytes, proof)
        feedback = agents._vscore_failure_feedback(record, "full-errors.json")
        self.assertEqual(feedback["error_count"], len(errors))
        self.assertEqual([row["number"] for row in feedback["errors"]], list(range(1, 36)))
        self.assertEqual(feedback["errors"][-1]["message_excerpt"], errors[-1])
        self.assertTrue(feedback["compacted"])
        self.assertEqual(feedback["errors"][7]["omitted_chars"], len(errors[7]) - 384)
        self.assertEqual(feedback["full_diagnostics"]["sha256"], canonical.digest_json(record))

    def test_run_build_preserves_all_errors_for_each_compile_failure_stage(self):
        errors = [f"{i}: generic compile error" for i in range(31)]
        failed = leanbridge.CompileResult(False, None, [], errors, [], False, 0)
        passed = leanbridge.CompileResult(True, None, [], [], [], False, 0)
        ctx = SimpleNamespace(claim={"claim_id": "GENERIC"}, policy={
            "build_timeout_seconds": 60, "memory_mb": 512, "require_network_isolation": True,
            "require_filesystem_isolation": True}, inputs={
            "source": ("vscore-source", self.source), "relation": ("vscore-relation", self.relation_bytes),
            "proof_source": ("vscore-proof", b"generic proof")}, contract_module=b"generic contract bundle")
        for stage, inventory, results, code, severity in (
            ("GenericLibrary", {"GenericLibrary": b"generic library"}, [(failed, {})], "VERIFIER_FAILURE", "infrastructure"),
            (target.GOAL_MODULE, {}, [(failed, {})], "UNSUPPORTED_CAPABILITY", "blocking"),
            (target.PROOF_MODULE, {}, [(passed, {}), (failed, {})], "CANDIDATE_BUILD_FAILURE", "blocking"),
        ):
            with self.subTest(stage=stage), patch.object(target, "library_sources", return_value=inventory), \
                 patch.object(leanbridge, "compile_named_module", side_effect=results), \
                 patch.object(leanbridge, "_stage_module"), patch.object(leanbridge, "module_parts", return_value={}), \
                 self.assertRaises(checker.EdgeFailure) as rejected:
                checker.run_build(SimpleNamespace(), ctx, self.spec)
            diagnostic = rejected.exception.diagnostics[0]
            self.assertEqual(diagnostic.code, code)
            self.assertEqual(diagnostic.severity, severity)
            self.assertEqual(diagnostic.details["module"], stage)
            self.assertEqual(diagnostic.details["errors"], errors)
            self.assertEqual(diagnostic.details["error_count"], len(errors))

    def test_latest_proof_and_full_durable_errors_reach_each_repair(self):
        initial = "generic initial proof"
        replacement = "generic replacement proof\n"
        final = "generic final proof\n"
        errors1 = [f"{i}: missing_first_{i}" for i in range(35)]
        errors2 = [f"{i}: missing_second_{i}" for i in range(24)]
        responses = iter([json.dumps({"program": canonical.loads(self.source), "relation": self.relation,
                                      "proof_source": initial}), replacement, final])

        def preview(_pkg, got_source, got_relation, proof=None):
            self.assertEqual(got_source, self.source)
            self.assertEqual(got_relation, self.relation_bytes)
            if proof == initial.encode():
                raise self.compile_failure(proof, errors1)
            if proof == replacement.encode():
                raise self.compile_failure(proof, errors2)
            return self.spec, None, self.info

        with patch.object(agents, "_vscore_context", return_value=self.fixed), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", side_effect=lambda *args: SimpleNamespace(text=next(responses))) as calls, \
             patch.object(checker, "preview", side_effect=preview):
            files, _ = agents._vscore_implementation(None, {"roles": {"prover": "prover"}}, self.pkg,
                                                     self.events, {"parameters": self.params}, 1, 2)
        self.assertEqual(files["Proof.lean"], final.encode())
        for call, label, proof, errors in zip(calls.call_args_list[1:], ["initial-proof", "proof-1"],
                                             [initial, replacement], [errors1, errors2]):
            user = call.args[5]
            context = json.loads(user.split("FIXED VSCORE PROOF CONTEXT (data):\n", 1)[1].split(
                "\nCURRENT CANDIDATE PROOF:", 1)[0])
            feedback = json.loads(user.split("CHECKER ERROR INVENTORY (excerpts; full artifact referenced):\n", 1)[1])
            self.assertEqual(context["proof_hash"], canonical.digest(proof.encode()))
            self.assertEqual(context["source_hash"], canonical.digest(self.source))
            self.assertEqual(context["relation_hash"], canonical.digest(self.relation_bytes))
            self.assertEqual(context["goal_hash"], canonical.digest(self.spec.text.encode()))
            self.assertEqual(context["proof_support"], target.proof_support_catalog())
            self.assertEqual(feedback["proof_hash"], context["proof_hash"])
            self.assertEqual(feedback["error_count"], len(errors))
            artifact = self.pkg.root / feedback["full_diagnostics"]["path"]
            self.assertEqual(canonical.digest(artifact.read_bytes()), feedback["full_diagnostics"]["sha256"])
            full = canonical.load_file(artifact)
            self.assertEqual(full["diagnostics"][0]["details"]["errors"], errors)
            check = canonical.load_file(artifact.parent.parent / "checks" / f"{label}.json")
            self.assertFalse(check["passed"])
            self.assertEqual(check["proof_hash"], context["proof_hash"])
            self.assertEqual(check["diagnostics"][0]["details"]["errors"], errors)

    def test_more_than_twenty_structured_diagnostics_are_retained(self):
        exc = checker.EdgeFailure([Diagnostic("KERNEL_REJECTION", f"generic failure {i}") for i in range(29)])
        record = agents._vscore_failure_record(exc, self.source, self.relation_bytes, b"proof")
        self.assertEqual(len(record["diagnostics"]), 29)
        feedback = agents._vscore_failure_feedback(record, "all.json")
        self.assertEqual(feedback["error_count"], 29)
        self.assertEqual(feedback["errors"][-1]["message_excerpt"], "generic failure 28")

    def test_schema_invalid_source_retains_every_issue_and_exact_proposal(self):
        invalid = {}
        issues = schemas.validate("vscore-source-v3", invalid)
        self.assertGreater(len(issues), 1)
        responses = iter([json.dumps({"program": invalid, "relation": self.relation}),
                          json.dumps({"program": canonical.loads(self.source), "relation": self.relation})])
        with patch.object(agents, "_vscore_context", return_value=self.fixed), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", side_effect=lambda *args: SimpleNamespace(text=next(responses))) as calls, \
             patch.object(checker, "preview", return_value=(self.spec, None, self.info)):
            agents._vscore_implementation(None, {"roles": {}}, self.pkg, self.events,
                                          {"parameters": self.params}, 2, 0)
        feedback = json.loads(calls.call_args_list[1].args[5].split(
            "CHECKER ERROR INVENTORY FROM THE PREVIOUS ATTEMPT (excerpts; full artifact referenced):\n", 1)[1])
        self.assertEqual(feedback["error_count"], len(issues))
        artifact = self.pkg.root / feedback["full_diagnostics"]["path"]
        self.assertEqual(canonical.digest(artifact.read_bytes()), feedback["full_diagnostics"]["sha256"])
        full = canonical.load_file(artifact)
        expected = [f"vscore-source-v3: {issue}" for issue in issues]
        self.assertEqual([row["message"] for row in full["diagnostics"]], expected)
        self.assertEqual([row["message_excerpt"] for row in feedback["errors"]], expected)
        stage = artifact.parent.parent
        self.assertEqual((stage / "program.vscore.json").read_bytes(), canonical.dumps(invalid))
        self.assertEqual(feedback["source_hash"], canonical.digest(canonical.dumps(invalid)))
        self.assertEqual(feedback["relation_hash"], canonical.digest(self.relation_bytes))

    def test_malformed_response_after_valid_source_has_no_stale_source_hash(self):
        malformed = "generic unparseable response with no source object"
        responses = iter([json.dumps({"program": canonical.loads(self.source), "relation": self.relation}), malformed])
        with patch.object(agents, "_vscore_context", return_value=self.fixed), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", side_effect=lambda *args: SimpleNamespace(text=next(responses))), \
             patch.object(checker, "preview", return_value=(self.spec, None, self.info)):
            files, _ = agents._vscore_implementation(None, {"roles": {}}, self.pkg, self.events,
                                                     {"parameters": self.params}, 2, 0)
        self.assertEqual(files["program.vscore.json"], self.source)
        stage = self.pkg.root / "agents/vscore-attempts/source-2"
        record = canonical.load_file(stage / "diagnostics/source.json")
        for key in ("source_hash", "relation_hash", "proof_hash"):
            self.assertIsNone(record[key])
        response = self.pkg.root / record["response_artifact"]["path"]
        self.assertEqual(response.read_text(), malformed)
        self.assertEqual(record["response_artifact"]["sha256"], canonical.digest(malformed.encode()))
        feedback = canonical.load_file(stage / "source-diagnostics.json")
        self.assertEqual(feedback["response_artifact"], record["response_artifact"])
        self.assertEqual(feedback["full_diagnostics"]["sha256"], canonical.digest_json(record))

    def test_oversized_proof_keeps_exact_raw_response_and_latest_proof_binding(self):
        initial = "generic initial proof"
        oversized = "generic oversized proof " * 10
        raw_response = f"```lean\n{oversized}\n```\n"
        final = "generic final proof\n"
        responses = iter([json.dumps({"program": canonical.loads(self.source), "relation": self.relation,
                                      "proof_source": initial}), raw_response, final])

        def preview(_pkg, _source, _relation, proof=None):
            if proof == initial.encode():
                raise self.compile_failure(proof, ["generic initial failure"])
            return self.spec, None, self.info

        with patch.object(agents, "_vscore_context", return_value=self.fixed), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", side_effect=lambda *args: SimpleNamespace(text=next(responses))) as calls, \
             patch.object(checker, "preview", side_effect=preview) as previews, \
             patch.object(target, "MAX_PROOF_BYTES", 32):
            files, _ = agents._vscore_implementation(None, {"roles": {"prover": "prover"}}, self.pkg,
                                                     self.events, {"parameters": self.params}, 1, 2)
        self.assertEqual(files["Proof.lean"], final.encode())
        self.assertEqual(previews.call_count, 3)  # source, initial failure, final; oversized bytes never compiled
        user = calls.call_args_list[2].args[5]
        context = json.loads(user.split("FIXED VSCORE PROOF CONTEXT (data):\n", 1)[1].split(
            "\nCURRENT CANDIDATE PROOF:", 1)[0])
        feedback = json.loads(user.split("CHECKER ERROR INVENTORY (excerpts; full artifact referenced):\n", 1)[1])
        proof = (oversized + "\n").encode()
        self.assertEqual(context["proof_hash"], canonical.digest(proof))
        self.assertEqual(feedback["proof_hash"], context["proof_hash"])
        self.assertEqual(feedback["source_hash"], canonical.digest(self.source))
        self.assertEqual(feedback["relation_hash"], canonical.digest(self.relation_bytes))
        self.assertIn("proof exceeds", feedback["errors"][0]["message_excerpt"])
        artifact = self.pkg.root / feedback["full_diagnostics"]["path"]
        self.assertEqual(canonical.digest(artifact.read_bytes()), feedback["full_diagnostics"]["sha256"])
        record = canonical.load_file(artifact)
        response = self.pkg.root / record["response_artifact"]["path"]
        self.assertEqual(response.read_text(), raw_response)
        self.assertEqual(record["response_artifact"]["sha256"], canonical.digest(raw_response.encode()))
        self.assertEqual((artifact.parent.parent / "proofs/1.lean").read_bytes(), proof)

    def test_infrastructure_errors_remain_infrastructure_and_durable(self):
        exc = self.compile_failure(b"", ["generic library failure"], severity="infrastructure")
        response = json.dumps({"program": canonical.loads(self.source), "relation": self.relation})
        with patch.object(agents, "_vscore_context", return_value=self.fixed), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", return_value=SimpleNamespace(text=response)), \
             patch.object(checker, "preview", side_effect=exc), self.assertRaises(InfrastructureError):
            agents._vscore_implementation(None, {"roles": {}}, self.pkg, self.events,
                                          {"parameters": self.params}, 1, 0)
        record = canonical.load_file(self.pkg.root / "agents/vscore-attempts/source-1/checks/source.json")
        self.assertFalse(record["passed"])
        self.assertEqual(record["diagnostics"][0]["severity"], "infrastructure")
        self.assertEqual(record["diagnostics"][0]["details"]["errors"], ["generic library failure"])

    def test_helper_still_rejects_invented_relation_slots(self):
        selected_policy = next(iter(policy.POLICIES.values()))
        certificate = {"policy": {"id": selected_policy["id"], "hash": policy.policy_hash(selected_policy)}}
        bad_relation = dict(self.relation, source_slot="program.vscore.json", proof_slot="Proof.lean")
        with patch.object(export, "verified_ir", return_value=({}, "unused", certificate, [])), \
             self.assertRaises(checker.EdgeFailure) as rejected:
            checker.preview(self.pkg, self.source, canonical.dumps(bad_relation))
        self.assertEqual(rejected.exception.diagnostics[0].code, "INVALID_CANDIDATE")
        self.assertIn("vscore-source and vscore-proof", str(rejected.exception))
        self.assertIn('source_slot="vscore-source"', agents.VSCORE3_IMPLEMENTER_SYSTEM)
        self.assertIn('proof_slot="vscore-proof"', agents.VSCORE3_IMPLEMENTER_SYSTEM)


if __name__ == "__main__":
    unittest.main()
