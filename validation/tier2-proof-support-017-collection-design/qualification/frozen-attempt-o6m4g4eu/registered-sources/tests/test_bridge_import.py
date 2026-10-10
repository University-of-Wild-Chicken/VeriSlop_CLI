"""Real accepted-contract replay and rejection of forged provenance/import inputs."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import TempDir, build, copy_pkg, writable
from verislop import canonical, export, fsutil
from verislop.bridges.import_contract import BridgeImportError, import_contract
from verislop.errors import Diagnostic, InfrastructureError
from verislop.package import Package


class BridgeImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.base = cls.tmp.path / "source"
        stages = build(cls.base, "export")
        if any(code for code, _ in stages.values()):
            raise AssertionError(stages)
        before = {r: (cls.base / r).read_bytes() for r in fsutil.list_files(cls.base)}
        cls.imported = import_contract(cls.base)
        after = {r: (cls.base / r).read_bytes() for r in fsutil.list_files(cls.base)}
        if before != after:
            raise AssertionError("contract import mutated its source run")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copied(self, name):
        return copy_pkg(self.base, self.tmp.path / name)

    def rejected(self, root, code=None):
        with self.assertRaises(BridgeImportError) as caught:
            import_contract(root)
        self.assertEqual(caught.exception.status, "BLOCKED")
        if code:
            self.assertIn(code, {d.code for d in caught.exception.diagnostics})
        return caught.exception

    def test_actual_replay_returns_stable_inputs_without_mutable_history(self):
        imported = self.imported
        self.assertTrue(imported.replay_receipt["accepted_contract_replayed"])
        self.assertFalse(imported.replay_receipt["semantic_bridge_acceptance"])
        self.assertEqual(canonical.digest(imported.files[imported.ir_path]), imported.replay_receipt["source_ir_hash"])
        self.assertEqual(canonical.digest(imported.files[imported.certificate_path]), imported.replay_receipt["source_certificate_hash"])
        self.assertIn("contract/challenge/Contract.lean", imported.files)
        self.assertIn("claims.json", imported.files)
        self.assertFalse(any(p == "package.json" or p.startswith("evidence/") or p == "events.jsonl" for p in imported.files))

    def test_replay_identity_ignores_new_package_bookkeeping_and_unrelated_history(self):
        root = self.copied("bookkeeping")
        pkg = Package(root)
        pkg.set_meta("bridge_preparations", {"new": {"state": "prepared"}})
        pkg.evidence.record(claim_id="BRIDGE:other", verifier_id="verislop.bridge-envelope-checker", status="PASS",
                            scope=["unrelated metadata"], input_root="sha256:" + "1" * 64,
                            result={"structural_acceptance": True, "semantic_acceptance": False}, invocation=["test"])
        imported = import_contract(root)
        self.assertEqual(imported.files, self.imported.files)
        self.assertEqual(imported.replay_receipt, self.imported.replay_receipt)

    def replace_evidence(self, root, cid, *, issuer=None, status="PASS", root_hash=None, mutate=None):
        pkg = Package(root)
        old = pkg.evidence.for_claim(cid)[-1]
        for ev in pkg.evidence.for_claim(cid):
            (root / "evidence" / f"{ev.id}.json").unlink()
        pkg.reset_evidence_cache()
        raw = dict(old.result)
        if mutate:
            mutate(raw)
        pkg.evidence.record(claim_id=cid, verifier_id=issuer or old.record["verifier_id"], status=status,
                            scope=old.record["scope"], input_root=root_hash or old.record["input_root_hash"],
                            result=raw, invocation=["forged-test-record"])
        return pkg

    def test_wrong_reifier_issuer_and_missing_obligation_coverage_reject(self):
        root = self.copied("wrong-reifier")
        pkg = self.replace_evidence(root, "REIFIED:O17@1", issuer="verislop.review-consensus")
        self.assertTrue(export.verified_ir(pkg)[3])
        self.rejected(root, "STALE_OR_UNBOUND_EVIDENCE")
        root = self.copied("missing-reification")
        pkg = Package(root)
        for ev in pkg.evidence.for_claim("REIFIED:O17@1"):
            (root / "evidence" / f"{ev.id}.json").unlink()
        self.rejected(root, "VERIFIER_NOT_RUN")

    def test_acceptance_requires_exact_root_and_typed_pass(self):
        root = self.copied("wrong-acceptance-root")
        self.replace_evidence(root, "PROVED:O17@1", root_hash="sha256:" + "2" * 64)
        self.rejected(root, "STALE_OR_UNBOUND_EVIDENCE")
        root = self.copied("wrong-acceptance-result")
        self.replace_evidence(root, "PROVED:O17@1", mutate=lambda r: r.update(milestone_outcome="FAIL"))
        self.rejected(root, "STALE_OR_UNBOUND_EVIDENCE")

    def test_tampered_source_and_symlink_input_reject(self):
        root = self.copied("tampered-source")
        rel = self.imported.certificate["artifacts"]["source"]["path"]
        writable(root / rel)
        (root / rel).write_bytes((root / rel).read_bytes() + b"\n")
        self.rejected(root, "INPUT_MUTATION")
        root = self.copied("linked-source")
        outside = self.tmp.path / "outside-source"
        outside.write_bytes((root / rel).read_bytes())
        (root / rel).unlink()
        (root / rel).symlink_to(outside)
        self.rejected(root)

    def test_fully_hash_consistent_forged_compiled_artifact_is_rejected_by_replay(self):
        root = self.copied("forged-module")
        cert = copy.deepcopy(self.imported.certificate)
        fake = b"This is not a Lean artifact, despite matching all supplied hashes.\n"
        fake_hash = canonical.digest(fake)
        fake_path = f"accepted/olean/{fake_hash[7:]}.olean"
        fsutil.write_once(root / fake_path, fake)
        cert["artifacts"]["olean"] = {"path": fake_path, "sha256": fake_hash}
        cert_bytes = canonical.dumps(cert)
        cert_hash = canonical.digest(cert_bytes)
        cert_path = f"accepted/certificates/{cert_hash[7:]}.json"
        fsutil.write_once(root / cert_path, cert_bytes)
        ir = copy.deepcopy(self.imported.ir)
        ir["acceptance_certificate_ref"] = cert_path
        pkg = Package(root)
        reifications = {}
        for oid, rec in ir["obligations"].items():
            old = pkg.evidence.for_claim(f"REIFIED:{oid}@{rec['revision']}")[-1]
            check = {**old.result["check"], "certificate": cert_hash}
            ref = f"reification:{oid}@{canonical.digest_json(check)}"
            rec["formal"]["reification_evidence_ref"] = ref
            reifications[oid] = check, ref
        ir_bytes = canonical.dumps(ir)
        ir_hash = canonical.digest(ir_bytes)
        fsutil.atomic_write(pkg.path("accepted_ir"), ir_bytes)
        for oid, rec in cert["obligations"].items():
            for milestone, outcome in (("TYPECHECKED", rec["typechecked"]), ("PROVED", rec["proved"])):
                if outcome == "NOT_APPLICABLE":
                    continue
                pkg.evidence.record(claim_id=f"{milestone}:{oid}@{rec['revision']}", verifier_id="verislop.lean-acceptance",
                                    status="PASS", scope=["forged metadata"], input_root=cert["contract_input_root"],
                                    result={"milestone_outcome": outcome, "certificate_hash": cert_hash,
                                            "statement_hash": rec["statement_hash"], "axioms": rec["axioms"],
                                            "policy": cert["policy"]["id"], "binding_root": "contract_input_root"},
                                    invocation=["forged-test-record"])
        for oid, rec in ir["obligations"].items():
            check, ref = reifications[oid]
            pkg.evidence.record(claim_id=f"REIFIED:{oid}@{rec['revision']}", verifier_id="verislop.reifier", status="PASS",
                                scope=["forged metadata"], input_root=cert_hash,
                                result={"milestone_outcome": "PASS", "check": check, "reification_ref": ref, "ir_hash": ir_hash},
                                invocation=["forged-test-record"])
        # Provenance metadata alone is perfectly consistent. Fresh execution still must reject.
        self.assertEqual(export.verified_ir(pkg)[3], [])
        self.rejected(root, "STATEMENT_MISMATCH")

    def test_replay_service_failure_retains_infrastructure_classification(self):
        error = InfrastructureError("checker unavailable", [Diagnostic("VERIFIER_FAILURE", "checker unavailable", severity="infrastructure")])
        with patch("verislop.bridges.import_contract.accept.run", side_effect=error):
            with self.assertRaises(BridgeImportError) as caught:
                import_contract(self.base)
        self.assertEqual(caught.exception.status, "INFRASTRUCTURE_FAILURE")
        self.assertTrue(any(d.severity == "infrastructure" for d in caught.exception.diagnostics))

