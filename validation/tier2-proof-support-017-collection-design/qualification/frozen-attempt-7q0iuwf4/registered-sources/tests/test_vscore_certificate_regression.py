"""Semantic-certificate identity regressions against one shared, real accepted bridge."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import TempDir, codes, copy_pkg, run_cli, writable  # noqa: E402
from test_vscore import BRIDGE, VS, accepted_run, certificate_dir  # noqa: E402
from verislop import canonical  # noqa: E402
from verislop.bridges import vscore_checker as vc  # noqa: E402
from verislop.bridges.manifest import PackageReader  # noqa: E402
from verislop.package import Package  # noqa: E402


class VSCoreCertificateRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.package = accepted_run(cls.tmp.path)
        candidate = cls.tmp.path / "candidate"
        commands = [
            ("vscore", "goal", "--package", str(cls.package), "--source", str(VS / "program.vscore.json"),
             "--relation", str(VS / "relation.json"), "--proof", str(VS / "Proof.lean"), "--out", str(candidate),
             "--bridge-id", BRIDGE),
            ("bridge", "prepare", "--package", str(cls.package), "--proposal", str(candidate / "proposal.json"),
             "--candidate-dir", str(candidate)),
            ("bridge", "accept", "--package", str(cls.package), "--bridge-id", BRIDGE),
        ]
        for command in commands:
            code, result, output = run_cli(*command)
            if code != 0:
                raise AssertionError((command, result, output))

    def copy(self, label: str) -> Path:
        return copy_pkg(self.package, self.tmp.path / (self.id().rsplit(".", 1)[-1] + "-" + label))

    def mutate_certificate(self, package: Path, edit) -> dict:
        path = certificate_dir(package) / vc.CERTIFICATE
        certificate = canonical.load_file(path)
        edit(certificate)
        writable(path)
        path.write_bytes(canonical.dumps(certificate))
        return certificate

    def check_bindings(self, package: Path) -> set[str]:
        accepted, pending, diagnostics = vc.verify_published(Package(package, resolve_root=False), BRIDGE, rebuild=False)
        self.assertEqual(accepted, [])
        self.assertEqual(len(pending), 1)
        self.assertTrue(diagnostics)
        return {d.code for d in diagnostics}

    def test_complete_certificate_reproduces_in_full_verify(self):
        code, result, output = run_cli("bridge", "verify", "--package", str(self.package), "--bridge-id", BRIDGE)
        self.assertEqual(code, 0, (result, output))
        self.assertTrue(result["summary"]["semantic_acceptance"])
        self.assertTrue(result["summary"]["semantic_certificates"][0]["rechecked"])
        self.assertFalse(result["summary"]["assigns_end_to_end_verified"])
        folder = certificate_dir(self.package)
        a, b = (canonical.load_file(folder / "builds" / f"{label}.json") for label in "AB")
        self.assertEqual(a, b)
        self.assertEqual(set(a), set(vc.DETERMINISTIC))
        cert = canonical.load_file(folder / vc.CERTIFICATE)
        paths = {row["path"] for row in cert["accepted_modules"]}
        self.assertEqual(paths, {str(path.relative_to(folder)) for path in (folder / "accepted").iterdir()})
        evidence = canonical.load_file(folder / cert["evidence"]["path"])
        raw = canonical.load_file(folder / evidence["raw_result_ref"])
        descriptor = {key: value for key, value in cert.items() if key != "evidence"}
        self.assertEqual(raw["certificate_descriptor_hash"], canonical.digest_json(descriptor))

    def test_wrong_obligation_revision_is_rejected_by_full_verify(self):
        package = self.copy("revision")
        def edit(cert):
            obligation = next(row for row in cert["obligations"] if row["id"] == "E1")
            self.assertEqual(obligation["revision"], 1)
            obligation["revision"] = 101
        self.mutate_certificate(package, edit)
        code, result, output = run_cli("bridge", "verify", "--package", str(package), "--bridge-id", BRIDGE)
        self.assertEqual(code, 2, (result, output))
        self.assertIn("STATEMENT_MISMATCH", codes(result))
        self.assertFalse(result["summary"]["semantic_acceptance"])
        self.assertTrue(result["summary"]["pending_semantic_claims"])

    def test_semantic_metadata_is_rederived_for_binding_checks(self):
        zero_hash = "sha256:" + "0" * 64
        cases = {
            "revision": lambda c: c["obligations"][0].update(revision=101),
            "obligation_id": lambda c: c["obligations"][0].update(id="Unproved"),
            "statement_hash": lambda c: c["obligations"][0].update(accepted_statement_hash=zero_hash),
            "accepted_theorem": lambda c: c["obligations"][0].update(accepted_theorem="Different.theorem"),
            "transfer": lambda c: c["obligations"][0].update(transfer="Different.Transfer"),
            "transfer_theorem": lambda c: c["obligations"][0].update(transfer_theorem="Different.transfer"),
            "symbol_declaration": lambda c: c["symbols"][0].update(lean_decl="Different.reference"),
            "symbol_entry": lambda c: c["symbols"][0].update(entry="differentEntry"),
            "statement_inventory": lambda c: c["statement_identity"].pop(),
            "accepted_ir": lambda c: c.update(accepted_ir=zero_hash),
            "acceptance_certificate": lambda c: c.update(acceptance_certificate=zero_hash),
            "lean_toolchain": lambda c: c.update(lean_toolchain="leanprover/lean4:incorrect"),
            "kernel_tool_hash": lambda c: c.update(kernel_tool_hash=zero_hash),
        }
        for label, edit in cases.items():
            with self.subTest(field=label):
                package = self.copy(label)
                self.mutate_certificate(package, edit)
                self.assertIn("STATEMENT_MISMATCH", self.check_bindings(package))

    def test_module_part_mutation_is_rejected(self):
        package = self.copy("changed-module-part")
        path = certificate_dir(package) / "accepted/VeriSlopBridgeProof.olean"
        writable(path)
        path.write_bytes(path.read_bytes() + b"changed")
        self.assertIn("INPUT_MUTATION", self.check_bindings(package))

    def test_duplicate_module_part_inventory_is_rejected(self):
        package = self.copy("duplicate-module-part")
        self.mutate_certificate(package, lambda c: c["accepted_modules"].append(c["accepted_modules"][0]))
        self.assertIn("STATEMENT_MISMATCH", self.check_bindings(package))

    def test_descriptor_binds_every_synthetic_module_sidecar(self):
        # Exercise only descriptor/file consistency. These deliberately synthetic
        # parts are not Lean artifacts: no verifier evidence is issued, no public
        # certificate is rewritten, and no semantic acceptance is asserted.
        package = self.copy("synthetic-sidecars")
        folder = certificate_dir(package)
        ctx = vc.load_context(package / "bridges" / BRIDGE, BRIDGE, "reference-to-vscore")
        spec = vc.derive_goal(ctx)
        cert = canonical.load_file(folder / vc.CERTIFICATE)
        writable(folder / "accepted")
        for suffix in (".olean.private", ".olean.server"):
            path = "accepted/VeriSlopBridgeProof" + suffix
            data = ("synthetic inventory fixture " + suffix).encode()
            (folder / path).write_bytes(data)
            cert["accepted_modules"].append({"module": "VeriSlopBridgeProof", "path": path,
                                              "sha256": canonical.digest(data)})
        cert["accepted_modules"].sort(key=lambda row: (row["module"], row["path"]))
        proof_parts = {row["path"].removeprefix("accepted/VeriSlopBridgeProof"): (folder / row["path"]).read_bytes()
                       for row in cert["accepted_modules"] if row["module"] == "VeriSlopBridgeProof"}
        for ref in cert["builds"]:
            path = folder / ref["path"]
            observation = canonical.load_file(path)
            observation["modules"]["VeriSlopBridgeProof"] = vc._parts_digest(proof_parts)
            writable(path)
            path.write_bytes(canonical.dumps(observation))
            ref["sha256"] = canonical.digest(path.read_bytes())

        def check_descriptor():
            reader = PackageReader(folder)
            try:
                vc._check_descriptor(ctx, spec, cert, reader)
            finally:
                reader.close()

        check_descriptor()
        private = folder / "accepted/VeriSlopBridgeProof.olean.private"
        original = private.read_bytes()
        private.write_bytes(original + b"changed")
        with self.assertRaises(vc.EdgeFailure) as changed:
            check_descriptor()
        self.assertIn("INPUT_MUTATION", {d.code for d in changed.exception.diagnostics})
        private.write_bytes(original)
        cert["accepted_modules"] = [row for row in cert["accepted_modules"] if not row["path"].endswith(".private")]
        with self.assertRaises(vc.EdgeFailure) as omitted:
            check_descriptor()
        self.assertIn("INPUT_MUTATION", {d.code for d in omitted.exception.diagnostics})

    def test_second_build_disagreement_is_rejected(self):
        package = self.copy("build-b")
        folder = certificate_dir(package)
        path = folder / "builds/B.json"
        observation = canonical.load_file(path)
        observation["proposition_closure_size"] += 1
        writable(path)
        path.write_bytes(canonical.dumps(observation))
        # Keep the public file hash self-consistent. The two build observations
        # themselves must still agree, independently of those hashes.
        self.mutate_certificate(package, lambda c: c["builds"][1].update(sha256=canonical.digest(path.read_bytes())))
        self.assertIn("NONDETERMINISM", self.check_bindings(package))


if __name__ == "__main__":
    unittest.main()
