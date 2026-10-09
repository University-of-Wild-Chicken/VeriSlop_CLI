"""Review packets distinguish a proof template from the accepted proof bytes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir, build, writable
from verislop import canonical, review
from verislop.errors import UsageError
from verislop.package import Package


class AcceptedReviewSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.root = cls.tmp.path / "accepted"
        results = build(cls.root, "export")
        for name, (code, result) in results.items():
            if code:
                raise AssertionError((name, result))
        cls.pkg = Package(cls.root, resolve_root=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_packet_contains_only_exact_accepted_proof_source(self):
        packet = review.build_packet(self.pkg, "formal_contract")
        certificate = canonical.load_file(self.pkg.path("accepted") / "acceptance.json")
        ref = certificate["artifacts"]["source"]
        accepted = packet["lean_accepted_source"]
        self.assertEqual(ref["sha256"], accepted["sha256"])
        self.assertEqual(ref["path"], accepted["path"])
        self.assertEqual((self.root / ref["path"]).read_text(), accepted["text"])
        self.assertNotIn("lean_challenge", packet)
        self.assertNotIn("lean_challenge_role", packet)
        for key in ("scope", "request", "obligations", "ledger", "formal_statements", "evidence", "counterexample_policy"):
            self.assertIn(key, packet)
        self.assertEqual("accepted_and_proved", packet["acceptance"]["gate"])

    def test_before_acceptance_retains_frozen_challenge(self):
        root = self.tmp.path / "preacceptance"
        results = build(root, "formalize")
        self.assertTrue(all(code == 0 for code, _ in results.values()), results)
        pkg = Package(root, resolve_root=False)
        packet = review.build_packet(pkg, "formal_contract")
        self.assertEqual((root / "contract/challenge/Contract.lean").read_text(), packet["lean_challenge"])
        self.assertIn("pre-proof template", packet["lean_challenge_role"])
        self.assertNotIn("lean_accepted_source", packet)
        self.assertNotIn("acceptance", packet)

    def test_stale_accepted_source_cannot_fall_back_to_challenge(self):
        certificate = canonical.load_file(self.pkg.path("accepted") / "acceptance.json")
        path = self.root / certificate["artifacts"]["source"]["path"]
        original = path.read_bytes()
        writable(path)
        try:
            path.write_bytes(original + b"\n-- changed accepted proof\n")
            with self.assertRaises(UsageError):
                review.build_packet(self.pkg, "formal_contract")
        finally:
            path.write_bytes(original)

    def test_modified_accepted_source_is_not_shown_as_a_valid_proof(self):
        certificate = canonical.load_file(self.pkg.path("accepted") / "acceptance.json")
        path = self.root / certificate["artifacts"]["source"]["path"]
        original = path.read_bytes()
        writable(path)
        try:
            path.write_bytes(original + b"\n-- mutation\n")
            with self.assertRaises(UsageError) as error:
                review._accepted_reference_source(self.pkg, certificate)
            self.assertEqual("INPUT_MUTATION", error.exception.diagnostics[0].code)
        finally:
            path.write_bytes(original)

    def test_outside_package_source_is_rejected(self):
        outside = self.tmp.path / "outside.lean"
        outside.write_text("theorem wrong : True := by trivial\n")
        certificate = {"artifacts": {"source": {"path": "../outside.lean",
                                                "sha256": canonical.digest(outside.read_bytes())}}}
        with self.assertRaises(UsageError):
            review._accepted_reference_source(self.pkg, certificate)

    def test_repointing_mutable_certificate_alias_cannot_substitute_sorry_template(self):
        alias = self.pkg.path("accepted") / "acceptance.json"
        original = alias.read_bytes()
        certificate = canonical.loads(original)
        template = self.root / "contract/challenge/Contract.lean"
        certificate["artifacts"]["source"] = {
            "path": template.relative_to(self.root).as_posix(), "sha256": canonical.digest(template.read_bytes())}
        writable(alias)
        try:
            alias.write_bytes(canonical.dumps(certificate))
            with self.assertRaises(UsageError) as error:
                review.build_packet(self.pkg, "formal_contract")
            self.assertEqual("INPUT_MUTATION", error.exception.diagnostics[0].code)
        finally:
            alias.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
