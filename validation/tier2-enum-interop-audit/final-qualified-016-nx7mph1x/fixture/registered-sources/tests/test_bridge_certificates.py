"""Hostile bridge envelopes never substitute matching metadata for a proof.

Fixtures are deliberately fabricated, structurally valid records. No Lean theorem
or semantic backend is run by these tests, and no external service is contacted.
"""

from __future__ import annotations

import copy
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge_helpers import make_bridge_fixture, write_json, CLAIM_ID
from helpers import run_cli
from verislop import canonical
from verislop.bridges import validate_package
from verislop.bridges.check import semantic_edge_root
from verislop.bridges.manifest import PackageReader, MAX_ARTIFACT_BYTES, MAX_COLLECTION_ITEMS, MAX_JSON_DEPTH
from verislop.verifiers import verifier_hash


class BridgeCertificateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "package"
        self.plan, self.manifest, self.cert = make_bridge_fixture(self.root)

    def check(self, cert=False):
        return validate_package(self.root, Path("plan.json"), Path("artifacts.json"),
                                [Path("edge.json")] if cert else [])

    def blocked(self, result, code=None):
        self.assertEqual(result.status, "BLOCKED", result.to_json())
        self.assertFalse(result.summary["semantic_acceptance"])
        self.assertFalse(result.summary["assigns_end_to_end_verified"])
        self.assertEqual(result.summary["accepted_semantic_certificates"], [])
        if code:
            self.assertIn(code, {d.code for d in result.diagnostics}, result.to_json())

    def save_plan(self):
        self.manifest["plan_hash"] = canonical.digest(write_json(self.root, "plan.json", self.plan))
        write_json(self.root, "artifacts.json", self.manifest)

    def save_cert(self):
        write_json(self.root, "edge.json", self.cert)

    def update_artifact(self, slot, value):
        artifact = next(a for a in self.manifest["artifacts"] if a["slot_id"] == slot)
        data = write_json(self.root, artifact["path"], value)
        artifact.update(size=len(data), sha256=canonical.digest(data))
        write_json(self.root, "artifacts.json", self.manifest)

    def update_evidence(self, mutate_record=None, mutate_raw=None):
        record = canonical.load_file(self.root / self.cert["evidence"]["path"])
        if mutate_record:
            mutate_record(record)
        if mutate_raw:
            raw = canonical.load_file(self.root / record["raw_result_ref"])
            mutate_raw(raw)
            record["raw_result_hash"] = canonical.digest(write_json(self.root, record["raw_result_ref"], raw))
        body = {k: v for k, v in record.items() if k != "evidence_id"}
        record["evidence_id"] = "ev-" + canonical.sha256_hex(canonical.dumps(body))[:32]
        path = f"evidence/{record['evidence_id']}.json"
        self.cert["evidence"] = {"path": path, "sha256": canonical.digest(write_json(self.root, path, record))}
        self.save_cert()

    def test_structural_pass_is_explicitly_not_proof_and_read_only(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = self.check()
        self.assertEqual(result.status, "PASS", result.to_json())
        self.assertTrue(result.summary["structural_acceptance"])
        self.assertFalse(result.summary["semantic_acceptance"])
        self.assertFalse(result.summary["accepted_contract_replayed"])
        self.assertFalse(result.summary["proof_inventory_completeness_checked"])
        self.assertFalse(result.summary["assigns_end_to_end_verified"])
        self.assertEqual(result.summary["pending_semantic_claims"], [CLAIM_ID])
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_hash_consistent_forged_pass_is_not_a_semantic_certificate(self):
        # The issuer is registered, the byte roots/current checker hash match,
        # and the raw result deliberately asserts success. None is a proof.
        self.update_evidence(mutate_raw=lambda r: r.update(milestone_outcome="PASS", semantic_acceptance=True))
        result = self.check(cert=True)
        self.blocked(result, "UNSUPPORTED_CAPABILITY")
        self.assertTrue(result.summary["certificates"][0]["evidence_binding_valid"])
        self.assertTrue(result.summary["structural_acceptance"])

    def test_registry_entry_alone_still_cannot_enable_semantics(self):
        # Even when the relation names a registered template, an envelope certificate is not
        # acceptance: registered checkers publish their own outputs through `bridge accept`.
        with patch("verislop.bridges.check.relation_checker", return_value="verislop.vscore-checker"):
            result = self.check(cert=True)
            self.blocked(result, "UNSUPPORTED_CAPABILITY")
            self.assertIn("bridge accept", result.summary["certificates"][0]["reason"])

    def test_cli_structural_roundtrip_and_tampered_artifact(self):
        args = ("bridge", "check", "--package", str(self.root), "--plan", "plan.json", "--artifacts", "artifacts.json")
        code, result, err = run_cli(*args)
        self.assertEqual(code, 0, err)
        self.assertFalse(result["summary"]["semantic_acceptance"])
        (self.root / "artifacts/program.vscore.json").write_bytes(b"tampered")
        code, result, err = run_cli(*args)
        self.assertEqual(code, 2, err)
        self.assertIn("INPUT_MUTATION", {d["code"] for d in result["diagnostics"]})

    def test_cli_supplied_certificate_blocks(self):
        code, result, err = run_cli("bridge", "check", "--package", str(self.root), "--plan", "plan.json",
                                     "--artifacts", "artifacts.json", "--certificate", "edge.json")
        self.assertEqual(code, 2, err)
        self.assertFalse(result["summary"]["semantic_acceptance"])

    def test_whitespace_reformat_invalidates_exact_plan_hash(self):
        p = self.root / "plan.json"
        p.write_bytes(p.read_bytes() + b"\n")
        self.blocked(self.check(), "INPUT_MUTATION")

    def test_whitespace_reformat_invalidates_certificate_manifest_hash(self):
        p = self.root / "artifacts.json"
        p.write_bytes(p.read_bytes() + b"\n")
        self.blocked(self.check(cert=True), "STALE_OR_UNBOUND_EVIDENCE")

    def test_manifest_size_and_hash_are_supervisor_checked(self):
        self.manifest["artifacts"][0]["size"] += 1
        write_json(self.root, "artifacts.json", self.manifest)
        self.blocked(self.check(), "INPUT_MUTATION")

    def test_manifest_slot_coverage_is_exact(self):
        self.manifest["artifacts"].pop()
        write_json(self.root, "artifacts.json", self.manifest)
        self.blocked(self.check(), "UNMAPPED_IMPLEMENTATION_OBJECT")

    def test_symlink_leaf_is_rejected(self):
        p = self.root / "artifacts/Proof.olean"
        target = Path(self.temp.name) / "outside"
        target.write_bytes(p.read_bytes())
        p.unlink()
        p.symlink_to(target)
        self.blocked(self.check())

    def test_symlink_directory_is_rejected(self):
        p = self.root / "artifacts"
        target = Path(self.temp.name) / "outside"
        p.rename(target)
        p.symlink_to(target, target_is_directory=True)
        self.blocked(self.check())

    def test_symlink_package_root_and_ancestor_are_rejected(self):
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.blocked(validate_package(alias, Path("plan.json"), Path("artifacts.json")))
        ancestor = Path(self.temp.name) / "alias-parent"
        ancestor.symlink_to(Path(self.temp.name), target_is_directory=True)
        self.blocked(validate_package(ancestor / "package", Path("plan.json"), Path("artifacts.json")))

    def test_hardlinked_regular_file_is_rejected(self):
        os.link(self.root / "artifacts/Proof.olean", Path(self.temp.name) / "second-link")
        self.blocked(self.check())

    def test_fifo_is_rejected_without_reading(self):
        p = self.root / "artifacts/Proof.olean"
        p.unlink()
        os.mkfifo(p)
        self.blocked(self.check())

    def test_socket_is_rejected(self):
        p = self.root / "artifacts/Proof.olean"
        p.unlink()
        sock = socket.socket(socket.AF_UNIX)
        self.addCleanup(sock.close)
        sock.bind(str(p))
        self.blocked(self.check())

    def test_missing_and_escaping_paths_are_rejected(self):
        self.blocked(validate_package(self.root, Path("../plan.json"), Path("artifacts.json")))
        self.blocked(validate_package(self.root, Path(self.temp.name) / "outside.json", Path("artifacts.json")))
        (self.root / "artifacts/Proof.olean").unlink()
        self.blocked(self.check())

    def test_casefold_path_collision_is_rejected(self):
        self.manifest["artifacts"][-1]["path"] = self.manifest["artifacts"][0]["path"].upper()
        write_json(self.root, "artifacts.json", self.manifest)
        self.blocked(self.check(), "AMBIGUOUS_CORRESPONDENCE")

    def test_oversized_sparse_artifact_is_rejected_before_read(self):
        with (self.root / "artifacts/Proof.olean").open("wb") as out:
            out.truncate(MAX_ARTIFACT_BYTES + 1)
        self.blocked(self.check())

    def test_json_and_total_read_budgets_are_bounded(self):
        with patch("verislop.bridges.manifest.MAX_JSON_BYTES", 8):
            self.blocked(self.check())
        with patch("verislop.bridges.manifest.MAX_PACKAGE_BYTES", 8):
            self.blocked(self.check())

    def test_hostile_cardinality_and_depth_are_rejected_before_schema(self):
        for hostile in (["duplicate"] * (MAX_COLLECTION_ITEMS + 1),
                        "[" * (MAX_JSON_DEPTH + 1) + "0" + "]" * (MAX_JSON_DEPTH + 1)):
            data = hostile.encode() if isinstance(hostile, str) else canonical.dumps(hostile)
            (self.root / "plan.json").write_bytes(data)
            with patch("verislop.bridges.check._schema", side_effect=AssertionError("schema must not run")):
                self.blocked(self.check(), "INVALID_CANDIDATE")

    def test_concurrent_path_substitution_is_detected_at_final_recheck(self):
        original = PackageReader.recheck
        def substitute(reader):
            p = self.root / "artifacts/Proof.olean"
            p.write_bytes(b"changed between validation and return")
            original(reader)
        with patch.object(PackageReader, "recheck", substitute):
            self.blocked(self.check(), "INPUT_MUTATION")

    def test_cycle_and_missing_premise_rejected(self):
        self.plan["claims"][0]["premises"] = [CLAIM_ID]
        self.save_plan()
        self.blocked(self.check(), "ORPHAN_CLAIM")
        self.plan["claims"][0]["premises"] = ["undeclared"]
        self.save_plan()
        self.blocked(self.check(), "ORPHAN_CLAIM")

    def test_orphan_claim_rejected(self):
        self.plan["claims"].append({"claim_id": "orphan", "verifier_id": "verislop.bridge-envelope-checker",
                                    "root_kind": "bridge_plan", "result_predicate": "bridge-structural/0.1", "premises": []})
        self.save_plan()
        self.blocked(self.check(), "ORPHAN_CLAIM")

    def test_detached_selected_endpoint_rejected(self):
        source_node = self.plan["nodes"][1]
        source_node["kind"] = "intermediate_source"
        source_node["artifact_slots"].remove("source")
        next(slot for slot in self.plan["artifact_slots"] if slot["slot_id"] == "source")["node_id"] = "detached"
        self.plan["nodes"].append({"node_id": "detached", "kind": "restricted_source", "artifact_slots": ["source"],
                                   "model_ref": copy.deepcopy(source_node["model_ref"]),
                                   "profile_ref": copy.deepcopy(source_node["profile_ref"])})
        self.save_plan()
        self.blocked(self.check(), "ORPHAN_CLAIM")

    def test_ambiguous_endpoint_and_split_contract_owner_rejected(self):
        self.plan["nodes"][0]["kind"] = "restricted_source"
        self.save_plan()
        self.blocked(self.check())
        self.plan["nodes"][0]["kind"] = "accepted_contract"
        self.plan["nodes"][0]["artifact_slots"].remove("acceptance_certificate")
        self.plan["nodes"][1]["artifact_slots"].append("acceptance_certificate")
        next(s for s in self.plan["artifact_slots"] if s["slot_id"] == "acceptance_certificate")["node_id"] = "source"
        self.save_plan()
        self.blocked(self.check())

    def test_structural_predicate_cannot_be_assigned_to_edge(self):
        self.plan["claims"][0].update(root_kind="bridge_plan", result_predicate="bridge-structural/0.1")
        self.save_plan()
        self.blocked(self.check(), "ORPHAN_CLAIM")

    def test_extra_or_stale_obligation_rejected(self):
        self.plan["obligations"].append({**self.plan["obligations"][0], "id": "unexpected"})
        self.save_plan()
        self.blocked(self.check(), "ORPHAN_CLAIM")
        self.plan["obligations"].pop()
        self.plan["obligations"][0]["revision"] += 1
        self.save_plan()
        self.blocked(self.check(), "STATEMENT_MISMATCH")

    def test_duplicate_identity_and_wrong_node_ownership_rejected(self):
        node = copy.deepcopy(self.plan["nodes"][0])
        node["kind"] = "duplicate"
        self.plan["nodes"].append(node)
        self.save_plan()
        self.blocked(self.check())
        self.plan["nodes"].pop()
        self.plan["nodes"][0]["artifact_slots"].append("source")
        self.save_plan()
        self.blocked(self.check())

    def test_model_profile_relation_binding_rejected(self):
        original = copy.deepcopy(self.plan)
        for field in ("model_refs", "profile_refs", "relation"):
            with self.subTest(field=field):
                self.plan = copy.deepcopy(original)
                ref = self.plan["edges"][0][field]
                if isinstance(ref, list):
                    ref = ref[0]
                ref["sha256"] = "sha256:" + "0" * 64
                self.save_plan()
                self.blocked(self.check(), "STATEMENT_MISMATCH")

    def test_inventory_duplicate_symbol_and_missing_module_rejected(self):
        inv = canonical.load_file(self.root / "artifacts/proof-inventory.json")
        inv["theorems"].append({**inv["theorems"][0], "type_hash": "sha256:" + "0" * 64})
        self.update_artifact("proof_inventory", inv)
        self.blocked(self.check())
        inv["theorems"].pop()
        inv["module_slot"] = "source"
        self.update_artifact("proof_inventory", inv)
        self.blocked(self.check(), "STATEMENT_MISMATCH")

    def test_certificate_wrong_checker_type_and_inventory_rejected(self):
        original = copy.deepcopy(self.cert)
        for change in (lambda c: c["checker"].update(verifier_id="verislop.lean-kernel"),
                       lambda c: c["proof"].update(type_hash="sha256:" + "0" * 64),
                       lambda c: c["proof"].update(symbol="Missing.theorem"),
                       lambda c: c["proof"].update(module_slot="source")):
            self.cert = copy.deepcopy(original)
            change(self.cert)
            self.save_cert()
            self.blocked(self.check(cert=True))

    def test_certificate_success_field_is_not_accepted(self):
        self.cert["status"] = "PASS"
        self.save_cert()
        self.blocked(self.check(cert=True), "INVALID_CANDIDATE")

    def test_wrong_registered_issuer_cannot_satisfy_assigned_claim(self):
        issuer = "verislop.reifier"
        self.update_evidence(mutate_record=lambda r: r.update(verifier_id=issuer, verifier_hash=verifier_hash(issuer)))
        self.blocked(self.check(cert=True), "STALE_OR_UNBOUND_EVIDENCE")

    def test_evidence_cannot_choose_root_or_forge_proof_identity(self):
        self.update_evidence(mutate_raw=lambda r: r.update(binding_root="bridge_plan"))
        self.blocked(self.check(cert=True), "STALE_OR_UNBOUND_EVIDENCE")
        self.update_evidence(mutate_raw=lambda r: r.update(binding_root="semantic_edge", proof_symbol="Other.theorem"))
        self.blocked(self.check(cert=True), "STALE_OR_UNBOUND_EVIDENCE")

    def test_stale_evidence_root_and_raw_tamper_rejected(self):
        self.update_evidence(mutate_record=lambda r: r.update(input_root_hash="sha256:" + "0" * 64))
        self.blocked(self.check(cert=True), "STALE_OR_UNBOUND_EVIDENCE")
        record = canonical.load_file(self.root / self.cert["evidence"]["path"])
        (self.root / record["raw_result_ref"]).write_bytes(b"{}")
        self.blocked(self.check(cert=True), "STALE_OR_UNBOUND_EVIDENCE")

    def test_raw_evidence_traversal_rejected(self):
        self.update_evidence(mutate_record=lambda r: r.update(raw_result_ref="../outside.json"))
        self.blocked(self.check(cert=True))

    def test_raw_evidence_absolute_path_rejected_even_inside_package(self):
        self.update_evidence(mutate_record=lambda r: r.update(raw_result_ref=str(self.root / r["raw_result_ref"])))
        self.blocked(self.check(cert=True))

    def test_semantic_root_includes_exact_plan_manifest_and_full_edge(self):
        edge = self.plan["edges"][0]
        root = semantic_edge_root(self.cert["plan_hash"], self.cert["artifacts_hash"], edge)
        record = canonical.load_file(self.root / self.cert["evidence"]["path"])
        self.assertEqual(root, record["input_root_hash"])
        changed = copy.deepcopy(edge)
        changed["expected_proposition_hash"] = "sha256:" + "0" * 64
        self.assertNotEqual(root, semantic_edge_root(self.cert["plan_hash"], self.cert["artifacts_hash"], changed))


if __name__ == "__main__":
    unittest.main()
