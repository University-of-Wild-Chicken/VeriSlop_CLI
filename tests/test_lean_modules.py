"""Lean 4.34 module-system acceptance preserves private definitions and proofs."""

from __future__ import annotations

import sys
import os
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import EX, TempDir, build, codes, copy_pkg, formalization_variant, stage
from verislop import canonical, contract, leanbridge, policy
from verislop.errors import InfrastructureError
from verislop.exprjson import name_str


def as_module(source: str) -> str:
    source = source.replace("import Std", "module\npublic import Std\n\npublic section", 1)
    source = source.replace("namespace VeriSlop.BoundedIncrement", """namespace VeriSlop.BoundedIncrement

section
private def incrementAmount : Nat := 1
end
""", 1)
    return source.replace("then .ok (input + 1)", "then .ok (input + incrementAmount)")


PROOF_CORE = (EX / "lean" / "BoundedIncrement.lean").read_text().split("inductive ObligationKind where")[0]
PROOF = as_module(PROOF_CORE + "end VeriSlop.BoundedIncrement\n")


class ModuleHeader(unittest.TestCase):
    def test_module_import_modifiers_and_sections(self):
        source = """/- outer /- inner -/ -/
module
public import Std
meta import Lean
import all Init
public meta import Lean.Elab
public section
def x := 1
"""
        composed, imports, problems = contract.compose_challenge(source.encode(), contract.registry_lean([], {}))
        self.assertFalse(problems)
        self.assertEqual(imports, ["Std", "Lean", "Init", "Lean.Elab"])
        text = composed.decode()
        self.assertLess(text.index("public meta import Lean.Elab"), text.index(contract.REGISTRY_BEGIN))
        self.assertIn("end\n\npublic section\ndef x", text)

    def test_header_comments_and_section_with_private_definition_are_preserved(self):
        source = "module\nimport /- nested /- c -/ -/ Std\nsection\nprivate def x := 1\n"
        composed, imports, problems = contract.compose_challenge(source.encode(), contract.registry_lean([], {}))
        self.assertEqual(imports, ["Std"])
        self.assertFalse(problems)
        self.assertIn("section\nprivate def x := 1", composed.decode())

    def test_unterminated_comment_and_prelude_stay_rejected(self):
        self.assertTrue(contract.split_header("module /- unfinished")[2])
        self.assertTrue(contract.split_header("module\nprelude\nimport Init")[2])
        self.assertTrue(contract.split_header("public import Std")[2])

    def test_exported_only_environment_is_rejected(self):
        env = contract.Env.from_export({"import": {"ok": True, "is_module_system": True,
                                                    "load_level": "exported"}}, policy.get("strict"), "test")
        self.assertIn("KERNEL_REJECTION", {d.code for d in env.diagnostics})

    def test_import_closure_binds_all_loaded_private_and_ir_parts(self):
        tmp = TempDir()
        try:
            lib = tmp.path / "lib"
            lib.mkdir()
            for suffix in (".olean", ".olean.server", ".olean.private", ".ir.sig", ".ir"):
                (lib / ("Std" + suffix)).write_bytes(suffix.encode())
            tc = SimpleNamespace(libdir=lib, identity=lambda: {"githash": "module-closure-test"})
            modules = [{"name": ["Std"], "olean": str(lib / "Std.olean"), "is_module_system": True}]
            with patch.object(leanbridge, "_cache_dir", return_value=tmp.path):
                old, diagnostics = leanbridge.olean_closure_identity(tc, modules)
                self.assertFalse(diagnostics)
                for suffix in (".olean.server", ".olean.private", ".ir.sig", ".ir"):
                    (lib / ("Std" + suffix)).write_bytes(b"changed " + suffix.encode())
                    current, diagnostics = leanbridge.olean_closure_identity(tc, modules)
                    self.assertFalse(diagnostics)
                    self.assertNotEqual(old, current, suffix)
                    old = current
                (lib / "Std.olean.private").unlink()
                _, diagnostics = leanbridge.olean_closure_identity(tc, modules)
                self.assertIn("UNDECLARED_DEPENDENCY", {d.code for d in diagnostics})
        finally:
            tmp.cleanup()

    def test_host_bundle_write_replaces_candidate_symlink_without_touching_target(self):
        tmp = TempDir()
        try:
            stage_dir = tmp.path / "build"
            stage_dir.mkdir()
            outside = tmp.path / "outside-sentinel"
            outside.write_bytes(b"host contents")
            outside.chmod(0o640)
            for member in leanbridge.MODULE_PARTS:
                (stage_dir / member).write_bytes(member.encode())
            bundle_path = stage_dir / "VeriSlopContract.vslean"
            bundle_path.symlink_to(outside)
            result = leanbridge._bundle_module(stage_dir / "VeriSlopContract.olean")
            self.assertEqual(result, bundle_path)
            self.assertFalse(bundle_path.is_symlink())
            self.assertEqual(outside.read_bytes(), b"host contents")
            self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o640)
            self.assertTrue(bundle_path.read_bytes().startswith(leanbridge.MODULE_BUNDLE_MAGIC))
            linked = stage_dir / "linked"
            os.link(outside, linked)
            self.assertFalse(leanbridge._regular_artifact(linked, 1024))
        finally:
            tmp.cleanup()


class LeanModuleAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        formal = formalization_variant(cls.tmp.path, "module-formalization", lean_edit=as_module)
        proof = cls.tmp.path / "module-proof.lean"
        proof.write_text(PROOF)
        cls.base = cls.tmp.path / "module-base"
        results = build(cls.base, "verify", formalization=formal, proof=proof)
        for name, (code, response) in results.items():
            if code != 0:
                raise AssertionError((name, code, response))
        cls.cert = canonical.load_file(cls.base / "accepted" / "acceptance.json")
        cls.closure = results["verify"][1]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_private_body_survives_acceptance_storage_and_reexport(self):
        self.assertEqual(self.closure["summary"]["terminal_status"], "VERIFIED", self.closure)
        artifact = self.base / self.cert["artifacts"]["olean"]["path"]
        self.assertTrue(artifact.read_bytes().startswith(leanbridge.MODULE_BUNDLE_MAGIC))
        # Use only the persisted artifact; no build-directory sidecars are available here.
        exported = leanbridge.run_kernel_tool(self.tc, artifact, {"export": True, "axioms": True})
        self.assertTrue(exported["import"]["is_module_system"])
        self.assertEqual(exported["import"]["load_level"], "private")
        self.assertTrue(exported["replay"]["ok"], exported)
        declarations = {name_str(c["name"]): c for c in exported["constants"]}
        helper = next(c for n, c in declarations.items() if n.endswith("incrementAmount"))
        self.assertEqual(helper["kind"], "definition")
        self.assertIn("value", helper)
        self.assertEqual(declarations["VeriSlop.BoundedIncrement.success_is_successor"]["kind"], "theorem")
        self.assertIn("VeriSlop.Registry.entries", declarations)
        self.assertEqual(exported["replay"]["constants"], len(declarations))
        before = (self.base / "accepted" / "accepted-ir.json").read_bytes()
        code, response = stage(self.base, "export")
        self.assertEqual(code, 0, response)
        self.assertEqual(before, (self.base / "accepted" / "accepted-ir.json").read_bytes())

    def accept_variant(self, name, source):
        pkg = copy_pkg(self.base, self.tmp.path / name)
        proof = self.tmp.path / f"{name}.lean"
        proof.write_text(source)
        code, response = stage(pkg, "prove", "--candidate", str(proof), "--no-portfolio")
        self.assertIn(code, (0, 2), response)
        self.assertNotIn("CANDIDATE_BUILD_FAILURE", codes(response), response)
        return stage(pkg, "accept")

    def test_hidden_private_axiom_is_rejected(self):
        source = PROOF.replace("private def incrementAmount", "private axiom concealed : False\n\nprivate def incrementAmount", 1)
        code, response = self.accept_variant("hidden-axiom", source)
        self.assertEqual(code, 2, response)
        self.assertIn("INADMISSIBLE_AXIOM", codes(response))

    def test_hidden_private_sorry_dependency_is_rejected(self):
        source = PROOF.replace("private def incrementAmount", "private theorem concealed : False := by sorry\n\nprivate def incrementAmount", 1)
        source = source.replace("  unfold increment at h\n  split at h\n  · exact (Except.ok.inj h).symm\n  · contradiction",
                                "  exact False.elim concealed", 1)
        code, response = self.accept_variant("hidden-sorry", source)
        self.assertEqual(code, 2, response)
        self.assertIn("PROOF_UNRESOLVED", codes(response))

    def test_private_definition_drift_is_rejected(self):
        # Definitionally equal output is still a different frozen semantic declaration.
        source = PROOF.replace("incrementAmount : Nat := 1", "incrementAmount : Nat := 2 - 1")
        code, response = self.accept_variant("hidden-drift", source)
        self.assertEqual(code, 2, response)
        self.assertIn("STATEMENT_MISMATCH", codes(response))

    def test_missing_or_replaced_private_bundle_member_is_rejected(self):
        artifact = self.base / self.cert["artifacts"]["olean"]["path"]
        original = canonical.loads(artifact.read_bytes()[len(leanbridge.MODULE_BUNDLE_MAGIC):])
        for mode in ("missing", "replaced", "path"):
            bundle = canonical.loads(canonical.dumps(original))
            if mode == "missing":
                bundle["files"].pop()
            elif mode == "replaced":
                bundle["files"][-1]["content_b64"] = "AA=="
            else:
                bundle["files"][-1]["name"] = "../escape"
            path = self.tmp.path / f"{mode}.vslean"
            path.write_bytes(leanbridge.MODULE_BUNDLE_MAGIC + canonical.dumps(bundle))
            stage_dir = self.tmp.path / f"{mode}-stage"
            stage_dir.mkdir()
            with self.subTest(mode=mode), self.assertRaises(InfrastructureError):
                leanbridge._stage_module(path, stage_dir)
            self.assertEqual(list(stage_dir.iterdir()), [])

    def test_third_party_import_stays_rejected_before_build(self):
        form = formalization_variant(self.tmp.path, "unlocked-import", lean_edit=lambda s:
                                     as_module(s).replace("public import Std", "public import Mathlib"))
        pkg = self.tmp.path / "unlocked-package"
        results = build(pkg, "formalize", formalization=form)
        self.assertEqual(results["formalize"][0], 2)
        self.assertIn("UNDECLARED_DEPENDENCY", codes(results["formalize"][1]))


if __name__ == "__main__":
    unittest.main()
