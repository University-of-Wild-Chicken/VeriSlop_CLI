"""Fresh-fixture version dispatch and retained agent repair, without inference or kernel calls."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import agents, canonical, capabilities, cli, fsutil, generate
from verislop.backends import admission, registry, vscore3_admission
# Load prepare before PackageReader is patched; its module-local alias must stay real.
from verislop.bridges import prepare, vscore_checker, vscore3_checker
from verislop.errors import Diagnostic, UsageError
from verislop.events import EventSink
from verislop.package import Package
from verislop.stage import StageResult
from verislop.targets import vscore_source, vscore2_source, vscore2_check, vscore3_source, vscore3_check


class VSCore3WorkflowUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-vscore3-workflow-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pkg = Package(self.root / "run")
        self.pkg.ensure("vscore3-workflow-unit")
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)
        self.parser = cli.build_parser()
        self.params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                       "backend": "verislop.backend.vscore/0.3", "backend_version": "0.3",
                       "require_state": "END_TO_END_VERIFIED", "require_tests": False}
        self.relation = {"schema_version": "0.3", "format": "verislop.vscore-relation/0.3",
                         "template": "vscore.reference_refinement/0.3", "source_slot": "source",
                         "proof_slot": "proof", "bindings": [{"symbol": "plus", "entry": "plus"}]}
        self.info = {"proposition_hash": "sha256:" + "a" * 64, "model": b"{}", "profile": b"{}"}

    def source(self):
        return vscore3_source.compile_surface(
            'program "vscore/0.3" profile "data-pipeline/0.3"; entry plus(x:Int)->Int{x+int(2)}')

    def fixed_context(self):
        return {"parameters": self.params, "accepted_reference": {}, "accepted_packages": {},
                "accepted_profile": {}, "lean_toolchain": "fixture-pin"}

    def test_agents_require_the_exact_frozen_backend_version(self):
        selected = agents._vscore_components(self.params)
        self.assertIs(selected["checker"], vscore3_checker)
        self.assertEqual(selected["source_schema"], "vscore-source-v3")
        self.assertEqual(selected["relation_schema"], "vscore-relation-v3")
        self.assertIn("data-pipeline/0.3", selected["implementer_system"])
        self.assertIs(agents._vscore_components({"backend": registry.VSCORE_ID})["checker"], vscore_checker)
        for parameters in ({"backend": registry.VSCORE3_ID},
                           dict(self.params, backend_version="0.1"),
                           dict(self.params, backend_version="future"),
                           {"backend": "verislop.backend.vscore/0.2", "backend_version": "0.2"}):
            with self.subTest(parameters=parameters), self.assertRaises(UsageError) as raised:
                agents._vscore_components(parameters)
            self.assertEqual(raised.exception.diagnostics[0].code, "UNSUPPORTED_CAPABILITY")

    def test_cli_compilation_parse_and_check_dispatch_by_source_version(self):
        for version, profile, entry, source_module, checker in (
            ("0.2", "pure-data/0.2", "entry plus(x:Nat)->Nat{x+2}", vscore2_source, vscore2_check),
            ("0.3", "data-pipeline/0.3", "entry plus(x:Int)->Int{x+int(2)}", vscore3_source, vscore3_check),
        ):
            with self.subTest(version=version):
                surface = self.root / (version + ".vsc")
                surface.write_text(f'program "vscore/{version}" profile "{profile}"; {entry}')
                delivered = self.root / (version + ".json")
                result = cli.cmd_vscore(self.parser.parse_args([
                    "vscore", "compile", "--source", str(surface), "--out", str(delivered)]))
                self.assertEqual(result.status, "PASS", result.diagnostics)
                self.assertEqual(result.summary["language"], source_module.LANGUAGE)
                self.assertFalse(result.summary["authoritative"])
                self.assertEqual(delivered.read_bytes(), source_module.compile_surface(surface.read_text()))
                result = cli.cmd_vscore(self.parser.parse_args(["vscore", "parse", "--source", str(delivered)]))
                self.assertEqual(result.status, "PASS", result.diagnostics)
                self.assertEqual(result.summary["program"]["language"], source_module.LANGUAGE)
                self.assertFalse(result.summary["authoritative"])
                with patch.object(checker, "check", return_value=StageResult("check", "PASS", "fixture")) as checked:
                    result = cli.cmd_vscore(self.parser.parse_args(["vscore", "check", "--source", str(delivered)]))
                self.assertEqual(result.status, "PASS")
                checked.assert_called_once_with(delivered.read_bytes(), {}, None)
        # A fresh legacy fixture preserves its original authoring route.
        old = canonical.dumps({"language": "vscore/0.1", "entries": [
            {"id": "plus", "params": ["nat"], "result": "nat", "body": {"tag": "var", "index": 0}}]})
        self.assertIs(cli._vscore_source_module(old), vscore_source)
        delivered = self.root / "legacy.json"
        delivered.write_bytes(old)
        result = cli.cmd_vscore(self.parser.parse_args(["vscore", "parse", "--source", str(delivered)]))
        self.assertEqual(result.status, "PASS", result.diagnostics)
        self.assertEqual(result.summary["program"]["language"], "vscore/0.1")

    def test_unknown_versions_and_uncertified_surfaces_fail_without_fallback(self):
        out = self.root / "out"
        for language in ("vscore/future", ["vscore/0.3"], None):
            path = self.root / "unknown.json"
            path.write_bytes(canonical.dumps({"language": language}))
            for command in ("parse", "check", "goal"):
                options = ["vscore", command, "--source", str(path)]
                if command == "goal":
                    options += ["--relation", str(self.root / "missing.json"), "--out", str(out)]
                with self.subTest(language=language, command=command):
                    result = cli.cmd_vscore(self.parser.parse_args(options))
                    self.assertEqual(result.status, "BLOCKED")
                    self.assertIn(result.diagnostics[0].code, ("INVALID_CANDIDATE", "UNSUPPORTED_CAPABILITY"))
                    self.assertFalse(out.exists())
        surface = self.root / "unknown.vsc"
        surface.write_text('program "vscore/future" profile "future"; entry go()->Nat{0}')
        result = cli.cmd_vscore(self.parser.parse_args([
            "vscore", "compile", "--source", str(surface), "--out", str(out)]))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "UNSUPPORTED_CAPABILITY")
        self.assertFalse(out.exists())
        for command in ("parse", "check"):
            result = cli.cmd_vscore(self.parser.parse_args(["vscore", command, "--source", str(surface)]))
            self.assertEqual(result.status, "BLOCKED")
            self.assertEqual(result.diagnostics[0].code, "INVALID_CANDIDATE")

    def test_goal_uses_the_exact_source_checker_and_keeps_source_admission_separate(self):
        source = self.root / "program.json"
        source.write_bytes(self.source())
        relation = self.root / "relation.json"
        relation.write_bytes(canonical.dumps(self.relation))
        out = self.root / "goal"
        with patch.object(vscore3_checker, "preview", return_value=(SimpleNamespace(text="fixture goal"), None, self.info)) as preview, \
             patch.object(vscore_checker, "preview", side_effect=AssertionError("wrong checker")):
            result = cli.cmd_vscore(self.parser.parse_args([
                "vscore", "goal", "--package", str(self.pkg.root), "--source", str(source),
                "--relation", str(relation), "--out", str(out)]))
        self.assertEqual(result.status, "PASS")
        preview.assert_called_once()
        self.assertEqual(preview.call_args.args[0].root, self.pkg.root)
        self.assertEqual(preview.call_args.args[1:], (source.read_bytes(), relation.read_bytes(), None, None))
        self.assertFalse(result.summary["authoritative"])
        self.assertEqual((out / "VeriSlopBridgeGoal.lean").read_text(), "fixture goal")
        source.write_bytes(vscore2_source.compile_surface(
            'program "vscore/0.2" profile "pure-data/0.2"; entry plus(x:Nat)->Nat{x+2}'))
        with patch.object(vscore3_checker, "preview", side_effect=AssertionError("0.2 has no bridge")), \
             patch.object(vscore_checker, "preview", side_effect=AssertionError("0.2 has no bridge")):
            result = cli.cmd_vscore(self.parser.parse_args([
                "vscore", "goal", "--source", str(source), "--relation", str(relation), "--out", str(out)]))
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.diagnostics[0].code, "UNSUPPORTED_CAPABILITY")

    def test_bridge_accept_dispatch_is_fixed_by_a_single_registered_edge_checker(self):
        for checker in (vscore_checker, vscore3_checker):
            plan = {"claims": [{"claim_id": "edge", "verifier_id": checker.VERIFIER}],
                    "edges": [{"claim_id": "edge"}]}
            other = vscore_checker if checker is vscore3_checker else vscore3_checker
            with self.subTest(checker=checker.VERIFIER), \
                 patch("verislop.bridges.manifest.PackageReader") as Reader, \
                 patch("verislop.bridges.check._schema"), \
                 patch.object(checker, "accept", return_value=StageResult("bridge accept", "PASS", "fixture")) as accept, \
                 patch.object(other, "accept", side_effect=AssertionError("wrong checker")):
                Reader.return_value.json.return_value = (plan, None)
                result = cli._vscore_bridge_accept(self.pkg, "fixture", self.events)
                self.assertEqual(result.status, "PASS")
                accept.assert_called_once_with(self.pkg, "fixture", self.events)
                Reader.return_value.recheck.assert_called_once()
                Reader.return_value.close.assert_called_once()
        for verifiers in ((vscore_checker.VERIFIER, vscore3_checker.VERIFIER), ("future-checker",), ()):
            plan = {"claims": [{"claim_id": str(i), "verifier_id": v} for i, v in enumerate(verifiers)],
                    "edges": [{"claim_id": str(i)} for i in range(len(verifiers))]}
            with self.subTest(verifiers=verifiers), patch("verislop.bridges.manifest.PackageReader") as Reader, \
                 patch("verislop.bridges.check._schema"), \
                 patch.object(vscore3_checker, "accept", side_effect=AssertionError("unsupported checker")), \
                 patch.object(vscore_checker, "accept", side_effect=AssertionError("unsupported checker")):
                Reader.return_value.json.return_value = (plan, None)
                result = cli._vscore_bridge_accept(self.pkg, "fixture", self.events)
            self.assertEqual(result.status, "BLOCKED")
            self.assertEqual(result.diagnostics[0].code, "UNSUPPORTED_CAPABILITY")
            self.assertFalse(result.summary["semantic_acceptance"])

    def test_cli_exposes_and_forwards_an_explicit_backend_version(self):
        args = self.parser.parse_args(["run", "--prompt-file", "request.txt", "--backend-version", "0.3"])
        self.assertEqual(args.backend_version, "0.3")
        args = self.parser.parse_args([
            "generate", "--package", str(self.pkg.root), "--tier", "2", "--target", "vscore",
            "--endpoint", "restricted_source", "--backend-version", "0.3", "--no-tests"])
        with patch.object(generate, "run", return_value=StageResult("generate", "PASS", "fixture")) as generated, \
             patch.object(cli, "_events", return_value=self.events):
            self.assertEqual(cli.cmd_generate(args).status, "PASS")
        self.assertEqual(generated.call_args.kwargs["backend_version"], "0.3")

    def test_frozen_backend_cannot_omit_or_substitute_its_version(self):
        path = self.pkg.path("closure") / "implementation-claims.json"
        for parameters, expected in ((self.params, registry.VSCORE3_ID),
                                     ({k: v for k, v in self.params.items() if k != "backend_version"}, None),
                                     (dict(self.params, backend_version="0.1"), None),
                                     (dict(self.params, backend_version="future"), None)):
            with self.subTest(parameters=parameters):
                fsutil.write_json(path, {"schema_version": "0.2", "format": "verislop.implementation-claims/0.2",
                                         "parameters": parameters})
                descriptor, diagnostics = registry.frozen_backend(self.pkg)
                if expected is None:
                    self.assertIsNone(descriptor)
                    self.assertEqual(diagnostics[0].code, "UNSUPPORTED_CAPABILITY")
                else:
                    self.assertEqual(descriptor["id"], expected)
                    self.assertEqual(descriptor["backend_version"], "0.3")
                    self.assertEqual(diagnostics, [])

    def write_package(self, package):
        data = canonical.dumps(package)
        digest = canonical.digest(data)
        path = self.pkg.path("accepted") / "expressions" / (digest[7:] + ".json")
        fsutil.atomic_write(path, data)
        return str(path.relative_to(self.pkg.root)) + "@" + digest

    def test_agent_context_binds_exact_schemas_accepted_packages_and_reference_bytes(self):
        package = {"encoding": "verislop.contract-dsl/0.2", "semantic_profile": "fixture", "formula": {"tag": "true"}}
        ref = self.write_package(package)
        reference = b"-- fresh unrelated accepted reference fixture\n"
        fsutil.atomic_write(self.pkg.root / "Contract.lean", reference)
        fsutil.write_json(self.pkg.root / "certificate.json", {
            "artifacts": {"source": {"path": "Contract.lean", "sha256": canonical.digest(reference)}},
            "toolchain": {"pin": "fixture-pin"}})
        ctx = {"parameters": self.params, "ir": {"acceptance_certificate_ref": "certificate.json", "obligations": {
            "F1": {"revision": 1, "formal": {"statement_hash": "fixture-hash", "formula_ref": ref}}}},
               "profile": {}, "required_obligations": ["F1"]}
        fixed = agents._vscore_context(self.pkg, ctx)
        self.assertEqual(fixed["source_grammar"]["properties"]["language"]["const"], "vscore/0.3")
        self.assertEqual(fixed["relation_format"]["properties"]["format"]["const"], "verislop.vscore-relation/0.3")
        self.assertEqual(fixed["parameters"]["backend_version"], "0.3")
        self.assertEqual(fixed["accepted_packages"]["F1"]["package"], package)
        self.assertEqual(fixed["accepted_reference"]["lean_source"], reference.decode())
        fsutil.atomic_write(self.pkg.root / "Contract.lean", reference + b"-- changed\n")
        with self.assertRaises(UsageError) as raised:
            agents._vscore_context(self.pkg, ctx)
        self.assertEqual(raised.exception.diagnostics[0].code, "INPUT_MUTATION")

    def test_autonomous_source_and_proof_repairs_retain_every_rejected_proposal(self):
        source = self.source()
        responses = [
            json.dumps({"program": {}, "relation": self.relation}),
            json.dumps({"program": canonical.loads(source), "relation": self.relation,
                        "proof_source": "fixture initial rejected proof"}),
            "```lean\nfixture rejected repair\n```",
            "```lean\nfixture successful repair\n```",
        ]
        iterator = iter(responses)

        def proposal(*_args, **_kwargs):
            return SimpleNamespace(text=next(iterator))

        def preview(_pkg, got_source, got_relation, proof=None):
            self.assertEqual(got_source, source)
            self.assertEqual(got_relation, canonical.dumps(self.relation))
            if proof is not None and proof != b"fixture successful repair\n":
                raise vscore3_checker.EdgeFailure([Diagnostic("KERNEL_REJECTION", "fixture repair needed")])
            return SimpleNamespace(text="fixture generated goal"), None, self.info

        with patch.object(agents, "_vscore_context", return_value=self.fixed_context()), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", side_effect=proposal) as calls, \
             patch.object(vscore3_checker, "preview", side_effect=preview), \
             patch.object(agents._vscore_components(self.params)["target"], "library_sources", return_value={"VSCore3": b"fixture library"}):
            files, bindings = agents._vscore_implementation(None, {"roles": {"prover": "prover"}}, self.pkg,
                                                           self.events, {"parameters": self.params}, 2, 2)
        self.assertEqual(files["program.vscore.json"], source)
        self.assertEqual(files["Proof.lean"], b"fixture successful repair\n")
        self.assertEqual(bindings, {})
        self.assertEqual(calls.call_count, 4)
        attempts = self.pkg.root / "agents/vscore-attempts"
        self.assertEqual((attempts / "source-1/response.txt").read_text(), responses[0])
        self.assertTrue((attempts / "source-1/source-diagnostics.json").is_file())
        self.assertEqual((attempts / "source-2/response.txt").read_text(), responses[1])
        for path, text in (("proofs/initial.lean", "fixture initial rejected proof"),
                           ("proofs/1.lean", "fixture rejected repair\n"),
                           ("proofs/2.lean", "fixture successful repair\n")):
            self.assertEqual((attempts / "source-2" / path).read_text(), text)
        self.assertFalse(canonical.load_file(attempts / "source-2/checks/initial-proof.json")["passed"])
        self.assertFalse(canonical.load_file(attempts / "source-2/checks/proof-1.json")["passed"])
        self.assertTrue(canonical.load_file(attempts / "source-2/checks/proof-2.json")["passed"])
        self.assertEqual(calls.call_args_list[0].args[4], agents.VSCORE3_IMPLEMENTER_SYSTEM)
        self.assertEqual(calls.call_args_list[2].args[4], agents.VSCORE3_PROVER_SYSTEM)
        self.assertIn("vscore-source-v3", calls.call_args_list[1].args[5])
        self.assertIn("fixture repair needed", calls.call_args_list[2].args[5])
        self.assertIn("fixture rejected repair", calls.call_args_list[3].args[5])
        self.assertIn("fixture repair needed", calls.call_args_list[3].args[5])

    def test_unproved_source_fallback_never_records_a_successful_proof(self):
        source = self.source()
        response = json.dumps({"program": canonical.loads(source), "relation": self.relation})
        with patch.object(agents, "_vscore_context", return_value=self.fixed_context()), \
             patch.object(agents, "_role", return_value="implementer"), \
             patch.object(agents, "recorded_call", return_value=SimpleNamespace(text=response)), \
             patch.object(vscore3_checker, "preview", return_value=(SimpleNamespace(text="fixture goal"), None, self.info)) as preview, \
             patch.object(agents._vscore_components(self.params)["target"], "library_sources", return_value={}):
            files, _ = agents._vscore_implementation(None, {"roles": {}}, self.pkg, self.events,
                                                   {"parameters": self.params}, 1, 0)
        self.assertEqual(files["program.vscore.json"], source)
        self.assertIn(b"by sorry", files["Proof.lean"])
        preview.assert_called_once_with(self.pkg, source, canonical.dumps(self.relation), proof=None)
        stage = self.pkg.root / "agents/vscore-attempts/source-1"
        self.assertTrue(canonical.load_file(stage / "proof-diagnostics.json")["proof_search_exhausted"])
        self.assertEqual(sorted(p.name for p in (stage / "checks").iterdir()), ["source.json"])

    def test_native_facets_remain_required_and_requested_tested_is_unsupported(self):
        profile = {"profile_id": "workflow-fixture", "dsl": "verislop.contract-dsl/0.2", "enums": {},
                   "records": {}, "predicates": {}, "symbols": {
                       "plus": {"lean_decl": "Fixture.plus", "args": ["Int"], "result": "Int"}}}
        value = {"encoding": "verislop.contract-dsl/0.2", "semantic_profile": profile["profile_id"],
                 "formula": {"tag": "forall", "sort": "Int", "body": {"tag": "eq",
                     "left": {"tag": "call", "symbol": "plus", "args": [{"tag": "var", "index": 0}]},
                     "right": {"tag": "int_add", "left": {"tag": "var", "index": 0},
                               "right": {"tag": "int", "value": "2"}}}}}
        pure_ref = self.write_package(value)
        pure = {"id": "F1", "role": "guarantee", "kind": "functional_correctness", "required": True,
                "formal": {"representation": "contract_dsl", "formula_ref": pure_ref}}
        features, _ = vscore3_admission.features(self.pkg, {"obligations": {"F1": pure}}, profile)
        self.assertEqual(vscore3_admission.admit(2, None, "no_tests", features), ("admitted", None, ["F1"]))
        for native_value in (None, value):
            projection = {"lean_symbol": "Fixture.valueProjection", "decl_hash": canonical.digest(b"fixture projection"),
                          "source_theorem": "Fixture.nativeGuarantee", "projection": "left"} if native_value else None
            package = {"encoding": "verislop.contract-facets/0.1", "semantic_profile": profile["profile_id"],
                       "value": native_value, "value_projection": projection, "native": [{
                           "definition": "delivery", "symbol": "plus", "lean_decl": "Fixture.plus",
                           "requirements": [{"tag": "entry", "file": "solution.py", "qualname": "plus", "arity": 1}]}]}
            rec = {**pure, "id": "N1", "formal": {"representation": "contract_facets", "formula_ref": self.write_package(package)}}
            with self.subTest(mixed=native_value is not None):
                features, reasons = vscore3_admission.features(self.pkg, {"obligations": {"N1": rec}}, profile)
                self.assertTrue(features[0]["required"])
                self.assertTrue(features[0]["e2e_applicable"])
                self.assertEqual(vscore3_admission.covered(features), ["N1"])
                decision = vscore3_admission.admit(2, None, "no_tests", features)
                self.assertEqual(decision, ("rejected", "UNSUPPORTED_CAPABILITY", ["N1"]))
                self.assertEqual(vscore3_admission.admission_diagnostics(decision, reasons)[0].obligations, ["N1"])
                self.assertFalse(capabilities.capability(2, "vscore", "restricted_source", backend_version="0.3",
                                                         obligations=features)[0])
                features, _ = vscore3_admission.features(self.pkg, {"obligations": {"F1": pure, "N1": rec}}, profile)
                self.assertEqual(vscore3_admission.covered(features), ["F1", "N1"])
                self.assertEqual(vscore3_admission.admit(2, None, "no_tests", features),
                                 ("rejected", "UNSUPPORTED_CAPABILITY", ["N1"]))
        for state, flag, code in (("TESTED", "omitted", "UNSUPPORTED_CAPABILITY"),
                                  (None, "require_tests", "UNSUPPORTED_CAPABILITY"),
                                  ("TESTED", "no_tests", "CONFIGURATION_INVALID")):
            with self.subTest(state=state, flag=flag):
                self.assertEqual(admission.resolve_params(2, "vscore", "restricted_source", "0.3", state, flag),
                                 (code, None))
        self.assertFalse(capabilities.capability(2, "vscore", "restricted_source", backend_version="0.3", require_tests=True)[0])


if __name__ == "__main__":
    unittest.main()
