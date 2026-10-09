"""Tier 2 implementation dispatch, frozen selection and proof-independent materialization."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import EX, TempDir, copy_pkg, run_cli, writable
from verislop import agents, canonical, fsutil, generate, schemas
from verislop.backends import admission, registry, vscore
from verislop.bridges import vscore_checker as checker
from verislop.events import EventSink
from verislop.package import Package

VS = EX / "vscore"
ZERO = "sha256:" + "0" * 64


class VSCoreImplementationUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.pkg = Package(self.tmp.path)
        self.pkg.ensure("tier2-units")

    def tearDown(self):
        self.tmp.cleanup()

    def test_test_policy_defaults_and_conflicts(self):
        params, diags = generate.resolve_parameters(self.pkg, 2, "vscore", "restricted-source", None, None)
        self.assertEqual(diags, [])
        self.assertEqual(params["require_state"], "END_TO_END_VERIFIED")
        self.assertFalse(params["require_tests"])
        self.assertEqual(params["backend"], registry.VSCORE_ID)
        _, rejected = generate.resolve_parameters(self.pkg, 2, "vscore", None, "TESTED", None, "no_tests")
        self.assertIn("CONFIGURATION_INVALID", {d.code for d in rejected})
        _, rejected = generate.resolve_parameters(self.pkg, 2, "vscore", None, None, None, "require_tests")
        self.assertIn("UNSUPPORTED_CAPABILITY", {d.code for d in rejected})
        python, diags = generate.resolve_parameters(self.pkg, 0, "python", None, None, None)
        self.assertEqual(diags, [])
        self.assertTrue(python["require_tests"])
        self.assertNotIn("backend", python)

    def test_requested_campaign_is_rejected_before_implementation_callback(self):
        for state, flag, expected in ((None, "require_tests", "UNSUPPORTED_CAPABILITY"),
                                      ("TESTED", "omitted", "UNSUPPORTED_CAPABILITY"),
                                      ("TESTED", "no_tests", "CONFIGURATION_INVALID")):
            with self.subTest(require_state=state, tests_flag=flag):
                callback = Mock(side_effect=AssertionError("implementation callback reached"))
                with patch.object(generate, "verified_ir", return_value=({"accepted": True}, ZERO, {}, [])), \
                     patch.object(vscore, "generate", side_effect=AssertionError("backend acquisition reached")):
                    result = generate.run(self.pkg, EventSink("admission", quiet=True), tier=2,
                                          target="vscore", require_state=state, tests_flag=flag, agent=callback)
                self.assertEqual(result.status, "BLOCKED")
                self.assertIn(expected, {d.code for d in result.diagnostics})
                callback.assert_not_called()
                self.assertFalse((self.pkg.path("closure") / "implementation-claims.json").exists())

    def test_roots_bind_claims_selection_and_exact_source_but_not_link_output(self):
        fsutil.write_json(self.pkg.path("closure") / "selection.json", {"input": "frozen"})
        fsutil.write_json(self.pkg.path("closure") / "implementation-claims.json", {"claims": []})
        fsutil.atomic_write(self.pkg.path("implementation") / "program.vscore.json", b"source")
        fsutil.write_json(self.pkg.path("implementation") / "materialization.json", {"inventory": []})
        fsutil.write_json(self.pkg.path("bridges") / "bindings.json", {"bindings": []})
        original = vscore.roots(self.pkg)
        fsutil.write_json(self.pkg.path("bridges") / "link.json", {"outcome": "candidate-owned"})
        self.assertEqual(vscore.roots(self.pkg), original)
        fsutil.atomic_write(self.pkg.path("implementation") / "program.vscore.json", b"source\n")
        changed = vscore.roots(self.pkg)
        self.assertNotEqual(changed["implementation_root"], original["implementation_root"])
        self.assertNotEqual(changed["link_root"], original["link_root"])

    def test_materialization_never_compiles_candidate_proof(self):
        ctx = SimpleNamespace(acceptance={"toolchain": {"pin": "pinned"}}, edge={"expected_proposition_hash": ZERO})
        build = SimpleNamespace(proposition_hash=ZERO)
        inv = {"source_hash": ZERO}
        with patch.object(vscore, "selection"), patch.object(checker, "derive_goal", return_value=object()), \
             patch.object(vscore.leanbridge, "resolve_toolchain", return_value=object()), \
             patch.object(checker, "run_build", return_value=build) as replay, \
             patch.object(vscore, "materialization_inventory", return_value=inv), \
             patch.object(vscore, "_schema"), patch.object(vscore, "roots", return_value={"implementation_root": ZERO}):
            self.assertEqual(vscore._materialize(self.pkg, EventSink("unit", quiet=True), ctx, {"claims": []}), [])
        self.assertEqual(replay.call_args.kwargs, {"with_proof": False})

    def test_refs_escape_entry_and_use_vscore_source_identity(self):
        obj = {"source_path": "implementation/program.vscore.json", "entry": "entry#a/b", "source_hash": ZERO}
        self.assertEqual(vscore.implementation_ref(obj), f"vscore:implementation/program.vscore.json#entry/entry%23a%2Fb@{ZERO}")

    def test_binding_format_is_closed_and_does_not_accept_python_objects(self):
        proposal = {"schema_version": "0.2", "format": "verislop.implementation-bindings/0.2",
                    "artifact_kind": "implementation_bindings", "backend": registry.VSCORE_ID,
                    "accepted_ir": ZERO, "bridge_id": "implementation", "source_slot": "vscore-source",
                    "bindings": [{"binding_id": "B1", "symbol": "increment", "entry": "increment"}]}
        self.assertEqual(schemas.validate("implementation-bindings-v2", proposal), [])
        proposal["bindings"][0]["object"] = {"file": "main.py", "qualname": "increment"}
        self.assertTrue(schemas.validate("implementation-bindings-v2", proposal))

    def test_unsupported_features_keep_required_covered_set(self):
        feature = {"id": "R1", "required": True, "role": "guarantee", "kind": "resource_constraint",
                   "e2e_applicable": True, "contract_dsl": True, "mentions_symbol": True,
                   "call_in_range_bound": False, "representable_sorts": True, "decl_representable": True}
        self.assertEqual(admission.covered([feature]), ["R1"])
        self.assertEqual(admission.unsupported([feature]), ["R1"])
        self.assertEqual(admission.admit(2, None, "omitted", [feature]), ("rejected", "UNSUPPORTED_CAPABILITY", ["R1"]))


    def test_claims_preserve_requiredness_with_unsupported_and_optional_records(self):
        params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source", "backend": registry.VSCORE_ID,
                  "language": "vscore/0.1", "semantics": "vscore-semantics/0.1", "require_state": "IMPLEMENTED",
                  "require_tests": False, "bridge_id": "implementation", "tier_default_applied": False}
        def record(oid, kind="postcondition", required=True):
            return {"id": oid, "revision": 1, "kind": kind, "role": "guarantee", "statement": "accepted statement",
                    "required": required, "source_refs": [{"kind": "prompt", "ref": "request/prompt.txt", "span": {"start": 0, "end": 1}}],
                    "scope": ["pure values"], "dependencies": [], "acceptance_criteria": ["exact theorem"],
                    "formal": {"representation": "lean_expr", "statement_hash": ZERO}}
        ir = {"contract_input_root": ZERO, "obligations": {"R1": record("R1", "resource_constraint"),
              "O2": record("O2", required=False), "W1": record("W1", "non_vacuity")}}
        inventory = vscore.implementation_claims(self.pkg, ir, ZERO, ZERO, params, {"symbols": {}}, {})
        by_id = {c["claim_id"]: c for c in inventory["claims"]}
        for milestone in ("IMPLEMENTED", "LINKED", "END_TO_END_VERIFIED"):
            self.assertTrue(by_id[f"{milestone}:R1@1"]["required"])
            self.assertTrue(by_id[f"{milestone}:R1@1"]["applicable"])
            self.assertFalse(by_id[f"{milestone}:O2@1"]["required"])
            self.assertFalse(by_id[f"{milestone}:W1@1"]["applicable"])
        self.assertFalse(by_id["TESTED:R1@1"]["required"])
        self.assertEqual(by_id["TESTED:R1@1"]["reason"], "campaign not required by frozen policy")

    def test_accepted_enum_constructors_are_interface_declarations(self):
        metadata = {"encoding": "verislop.typed-metadata/0.1", "bindings": {"Accepted.Error.bad": ZERO}}
        data = canonical.dumps(metadata)
        digest = canonical.digest(data)
        fsutil.atomic_write(self.pkg.path("accepted") / "expressions" / (digest[7:] + ".json"), data)
        rec = {"id": "D1", "role": "declaration", "kind": "entity", "required": True,
               "formal": {"representation": "typed_metadata", "formula_ref": "artifact:metadata@" + digest}}
        profile = {"profile_id": "p", "symbols": {}, "enums": {"Error": {"lean_decl": "Accepted.Error",
                   "constructors": ["bad"], "lean_constructors": ["Accepted.Error.bad"]}}}
        features, reasons = admission.features(self.pkg, {"obligations": {"D1": rec}}, profile)
        self.assertTrue(features[0]["decl_representable"])
        self.assertEqual(reasons, {})


class VSCoreAgentUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.pkg = Package(self.tmp.path)
        self.pkg.ensure("agent-units")
        source = b"import Std\nnamespace Accepted\ndef increment (x limit : Nat) := x + 1\nend Accepted\n"
        fsutil.atomic_write(self.pkg.path("accepted") / "Contract.lean", source)
        fsutil.write_json(self.pkg.path("accepted") / "acceptance.json", {
            "artifacts": {"source": {"path": "accepted/Contract.lean", "sha256": canonical.digest(source)}},
            "toolchain": {"pin": "leanprover/lean4:v4.34.1"}})
        package = {"encoding": "verislop.contract-dsl/0.1", "semantic_profile": "accepted-profile",
                   "formula": {"tag": "true"}}
        data = canonical.dumps(package)
        digest = canonical.digest(data)
        fsutil.atomic_write(self.pkg.path("accepted") / "expressions" / (digest[7:] + ".json"), data)
        self.ctx = {"parameters": {"target": "vscore", "backend": registry.VSCORE_ID, "tier": 2, "endpoint": "restricted_source"},
                    "profile": {"symbols": {}, "enums": {}}, "required_obligations": ["O17"],
                    "ir": {"acceptance_certificate_ref": "accepted/acceptance.json", "obligations": {
                        "O17": {"revision": 1, "formal": {"statement_hash": ZERO, "formula_ref": "artifact:O17@" + digest}}}}}
        self.proposal = {"program": canonical.load_file(VS / "program.vscore.json"), "relation": canonical.load_file(VS / "relation.json")}
        self.conf = {"roles": {"implementer": "source-model", "prover": "proof-model"}}
        self.events = EventSink("agent-units", quiet=True)

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self, pkg, source, relation, proof=None):
        if proof is not None and proof != b"good proof":
            raise checker.EdgeFailure([agents.Diagnostic("CANDIDATE_BUILD_FAILURE", "proof is wrong")])
        return SimpleNamespace(text="EXACT SUPERVISOR GOAL"), object(), {
            "proposition_hash": ZERO, "model": b"{}", "profile": b"{}"}

    def test_vscore_roles_get_exact_packages_and_fixed_goal_with_bounded_feedback(self):
        broker = Mock()
        broker.call.side_effect = [SimpleNamespace(text=canonical.dumps(self.proposal).decode()),
                                   SimpleNamespace(text="```lean\nbad proof```"), SimpleNamespace(text="```lean\ngood proof```")]
        with patch.object(agents, "_broker", return_value=(broker, self.conf)),              patch.object(checker, "preview", side_effect=self.preview) as preview,              patch.object(agents, "_role", side_effect=lambda conf, role: conf["roles"][role]),              patch.object(vscore.T, "library_sources", return_value={"VSCore": b"NORMATIVE LIBRARY"}):
            callback = agents.implementer_agent("config", self.pkg, self.events, attempts=1, proof_attempts=2)
            files, proposal = callback(self.ctx)
        self.assertEqual(files["program.vscore.json"], (VS / "program.vscore.json").read_bytes())
        self.assertEqual(files["relation.json"], canonical.dumps(self.proposal["relation"]))
        self.assertEqual(files["Proof.lean"], b"good proof")
        self.assertEqual(proposal, {})
        self.assertEqual(broker.call.call_count, 3)
        self.assertEqual([call.args[0] for call in broker.call.call_args_list], ["source-model", "proof-model", "proof-model"])
        source_user = broker.call.call_args_list[0].args[3]
        self.assertIn(self.ctx["ir"]["obligations"]["O17"]["formal"]["formula_ref"], source_user)
        self.assertIn("verislop.contract-dsl/0.1", source_user)
        proof_user = broker.call.call_args_list[2].args[3]
        for text in ("EXACT SUPERVISOR GOAL", "NORMATIVE LIBRARY", "accepted/Contract.lean", "proof is wrong", "restricted_source"):
            self.assertIn(text, proof_user)
        self.assertEqual([call.kwargs["proof"] for call in preview.call_args_list], [None, b"bad proof", b"good proof"])
        self.assertTrue((self.pkg.root / "agents/vscore-attempts/source-1/proofs/1.lean").is_file())
        self.assertTrue((self.pkg.root / "agents/vscore-attempts/source-1/proofs/2.lean").is_file())
        self.assertFalse(self.pkg.path("closure").exists())

    def test_exhausted_proof_search_returns_source_without_acceptance(self):
        broker = Mock()
        broker.call.side_effect = [SimpleNamespace(text=canonical.dumps(self.proposal).decode()),
                                   SimpleNamespace(text="bad proof"), SimpleNamespace(text="another bad proof")]
        with patch.object(agents, "_broker", return_value=(broker, self.conf)),              patch.object(checker, "preview", side_effect=self.preview),              patch.object(vscore.T, "library_sources", return_value={"VSCore": b"library"}):
            files, _ = agents.implementer_agent("config", self.pkg, self.events, attempts=1, proof_attempts=2)(self.ctx)
        self.assertEqual(files["program.vscore.json"], (VS / "program.vscore.json").read_bytes())
        self.assertEqual(files["Proof.lean"], b"another bad proof")
        self.assertEqual(broker.call.call_count, 3)
        self.assertTrue(canonical.load_file(self.pkg.root / "agents/vscore-attempts/source-1/proof-diagnostics.json")["proof_search_exhausted"])
        self.assertEqual(self.pkg.evidence.load(), [])

    def test_candidate_cannot_assign_goal_hash_or_lifecycle_fields(self):
        forbidden = {**self.proposal, "expected_proposition_hash": ZERO, "lifecycle": "PASS"}
        corrected = {**self.proposal, "proof_source": "good proof"}
        broker = Mock()
        broker.call.side_effect = [SimpleNamespace(text=canonical.dumps(forbidden).decode()), SimpleNamespace(text=canonical.dumps(corrected).decode())]
        with patch.object(agents, "_broker", return_value=(broker, self.conf)),              patch.object(checker, "preview", side_effect=self.preview):
            files, _ = agents.implementer_agent("config", self.pkg, self.events, attempts=2, proof_attempts=0)(self.ctx)
        self.assertEqual(files["Proof.lean"], b"good proof")
        self.assertEqual(broker.call.call_count, 2)
        self.assertIn("must contain only program, relation", broker.call.call_args_list[1].args[3])
        self.assertTrue((self.pkg.root / "agents/vscore-attempts/source-1/source-diagnostics.json").is_file())

    def test_python_proposal_callback_keeps_existing_format(self):
        expected = {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python"}
        broker = Mock()
        broker.call.return_value = SimpleNamespace(text=canonical.dumps({"files": {"main.py": "def f(x): return x"}, "bindings": expected}).decode())
        ctx = {"parameters": {"target": "python", "tier": 0, "endpoint": "test_campaign"},
               "profile": {"symbols": {}, "enums": {}}, "statements": {}}
        with patch.object(agents, "_broker", return_value=(broker, self.conf)), patch.object(checker, "preview") as preview:
            files, bindings = agents.implementer_agent("config", self.pkg, self.events)(ctx)
        self.assertEqual(files, {"main.py": b"def f(x): return x"})
        self.assertEqual(bindings, expected)
        self.assertIn("Python", broker.call.call_args.args[2])
        preview.assert_not_called()


class VSCoreImplementationIntegrationTests(unittest.TestCase):
    """Fresh accepted packages; run after registered source/schema hashes have been frozen."""
    @classmethod
    def setUpClass(cls):
        from test_vscore import accepted_run
        cls.tmp = TempDir()
        cls.base = accepted_run(cls.tmp.path)
        cls.package = copy_pkg(cls.base, cls.tmp.path / "selected")
        cls.generated = run_cli("generate", "--package", str(cls.package), "--tier", "2", "--target", "vscore", "--candidate", str(VS))
        cls.linked = run_cli("link", "--package", str(cls.package))
        cls.accepted = run_cli("bridge", "accept", "--package", str(cls.package), "--bridge-id", "implementation")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_complete_frozen_claims_binding_and_delivery(self):
        for result in (self.generated, self.linked, self.accepted):
            self.assertEqual(result[0], 0, result)
        selected = vscore.selection(Package(self.package))
        self.assertEqual([o["id"] for o in selected["covered"]], ["E1", "I2", "O17"])
        self.assertEqual((self.package / "implementation" / "program.vscore.json").read_bytes(), (VS / "program.vscore.json").read_bytes())
        claims = canonical.load_file(self.package / "closure" / "implementation-claims.json")
        self.assertEqual(schemas.validate("implementation-claims-v2", claims), [])
        self.assertTrue(all(c["required"] for c in claims["claims"] if c["milestone"] == "END_TO_END_VERIFIED" and c["obligation"] in {"E1", "I2", "O17"}))
        inventory = canonical.load_file(self.package / "implementation" / "materialization.json")
        self.assertFalse(inventory["proof_checked"])
        link, diags = vscore.checked_link(Package(self.package))
        self.assertEqual(diags, [])
        self.assertEqual(link["correspondence"], "structural")
        self.assertTrue(link["declarations"][0]["objects"])
        self.assertEqual({o["kind"] for o in link["declarations"][0]["objects"]}, {"accepted_enum", "accepted_function_type"})
        view = canonical.load_file(self.package / "obligation-view.json")
        self.assertTrue(all(view["obligations"][oid]["lifecycle"]["TESTED"]["outcome"] == "PENDING" for oid in ("E1", "I2", "O17")))
        self.assertTrue(all(view["obligations"][oid]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"] != "PASS" for oid in ("E1", "I2", "O17")))

    def test_explicit_prepared_bridge_adoption_needs_no_candidate(self):
        package = copy_pkg(self.base, self.tmp.path / "adopted")
        shutil.copytree(self.package / "bridges" / "implementation", package / "bridges" / "implementation")
        # The selection is explicit; package bookkeeping is not its authority.
        code, result, output = run_cli("generate", "--package", str(package), "--tier", "2", "--target", "vscore",
                                       "--bridge-id", "implementation")
        self.assertEqual(code, 0, (result, output))
        self.assertEqual(vscore.selection(Package(package))["bridge_id"], "implementation")
        code, result, output = run_cli("link", "--package", str(package))
        self.assertEqual(code, 0, (result, output))

    def test_bad_candidate_proof_preserves_materialized_and_linked_source(self):
        package = copy_pkg(self.base, self.tmp.path / "bad-proof")
        candidate = self.tmp.path / "bad-candidate"
        candidate.mkdir()
        for name in ("program.vscore.json", "relation.json"):
            (candidate / name).write_bytes((VS / name).read_bytes())
        (candidate / "Proof.lean").write_text("import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ntheorem edge : VeriSlopBridgeGoal.EdgeProp := by exact False.elim (by decide)\n")
        code, result, output = run_cli("generate", "--package", str(package), "--tier", "2", "--target", "vscore", "--candidate", str(candidate))
        self.assertEqual(code, 0, (result, output))
        code, result, output = run_cli("link", "--package", str(package))
        self.assertEqual(code, 0, (result, output))
        code, _, _ = run_cli("bridge", "accept", "--package", str(package), "--bridge-id", "implementation")
        self.assertNotEqual(code, 0)
        from verislop import view
        current = view.derive(Package(package))["obligations"]
        for oid in ("E1", "I2", "O17"):
            self.assertEqual(current[oid]["lifecycle"]["IMPLEMENTED"]["outcome"], "PASS")
            self.assertEqual(current[oid]["lifecycle"]["LINKED"]["outcome"], "PASS")
            self.assertNotEqual(current[oid]["lifecycle"]["END_TO_END_VERIFIED"]["outcome"], "PASS")

    def test_frozen_source_and_link_mutation_fail_closed(self):
        package = copy_pkg(self.package, self.tmp.path / "mutated-delivery")
        source = package / "implementation" / "program.vscore.json"
        writable(source)
        source.write_bytes(source.read_bytes() + b"\n")
        with self.assertRaises(checker.EdgeFailure):
            vscore.selection(Package(package))
        package = copy_pkg(self.package, self.tmp.path / "mutated-link")
        path = package / "bridges" / "link.json"
        writable(path)
        record = canonical.load_file(path)
        record["covered"] = record["covered"][:-1]
        fsutil.write_json(path, record)
        link, diags = vscore.checked_link(Package(package))
        self.assertIsNone(link)
        self.assertIn("INPUT_MUTATION", {d.code for d in diags})


if __name__ == "__main__":
    unittest.main()
