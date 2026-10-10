"""Actual Lean equality regressions using only freshly authored generic sources."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from verislop import canonical, contract, contract_refutation as cr, leanbridge, policy, reify
from verislop.exprjson import app, const, decl_hash, closure
from verislop.package import Package


EQUALITY_BODY = """fun a b => by
  cases a <;> cases b
  · exact isTrue rfl
  · exact isFalse (by intro equality; cases equality)
  · exact isFalse (by intro equality; cases equality)
  · exact isTrue rfl
"""
NAMESPACE = "RefutationEqualityRegression"
ENUM = NAMESPACE + ".Palette"
RECORD = NAMESPACE + ".Parcel"
INPUT = {"str": "ochre"}
RECORD_INPUT = {"dict": {"color": INPUT, "amount": {"int": "3"}}}
BINDING_ERROR = [{"message": "source/form/records do not match the supplied kernel-derived analysis"}]


def source_for(variant):
    source = "import Std\nnamespace " + NAMESPACE + "\ninductive Palette where | ochre | teal\n"
    if variant == "existing":
        source += "  deriving DecidableEq\nstructure Parcel where\n  color : Palette\n  amount : Nat\n  deriving DecidableEq\n"
    else:
        source += "private def hiddenEquality : DecidableEq Palette := " + EQUALITY_BODY
    source += """def swap (color : Palette) : Palette :=
  match color with | .ochre => .teal | .teal => .ochre
theorem wrongSwap (color : Palette) : swap color = color := by sorry
"""
    if variant == "existing":
        source += """def flipParcel (parcel : Parcel) : Parcel :=
  { color := swap parcel.color, amount := parcel.amount }
theorem wrongParcel (parcel : Parcel) : flipParcel parcel = parcel := by sorry
"""
    source += "end " + NAMESPACE + "\n"
    if variant == "private-public":
        source += "def zzUsableEquality : DecidableEq " + ENUM + " := " + EQUALITY_BODY
    return source.encode()


def records():
    return [{"id": oid, "revision": 1, "kind": kind, "role": role,
             "statement": "Authored equality regression", "required": True,
             "source_refs": [], "scope": ["equality-regression"], "dependencies": [],
             "acceptance_criteria": [], "origin": "interpreted", "blocked_by": []}
            for oid, kind, role in (("D1", "entity", "declaration"),
                                    ("O1", "postcondition", "guarantee"))]


class ContractRefutationEqualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-equality-regression-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.tc = leanbridge.resolve_toolchain()
        cls.pol = policy.get("strict")
        if (cls.pol["build_timeout_seconds"], cls.pol["kernel_timeout_seconds"]) != (300, 300):
            raise AssertionError("equality regressions require the existing strict 300-second limits")
        cls.kernel_options = {"timeout": cls.pol["kernel_timeout_seconds"],
            "memory_mb": cls.pol["memory_mb"],
            "require_network_isolation": cls.pol["require_network_isolation"],
            "require_filesystem_isolation": cls.pol["require_filesystem_isolation"]}
        cls.fixtures = {}
        for variant, theorem in (("existing", "wrongParcel"), ("private", "wrongSwap"),
                                 ("private-public", "wrongSwap")):
            source = source_for(variant)
            declarations = [ENUM, NAMESPACE + ".swap"]
            if variant == "existing":
                declarations += [RECORD, NAMESPACE + ".flipParcel"]
            form = {"schema_version": "0.1", "artifact_kind": "formalization_candidate",
                    "profile_id": "equality.regression", "lean_toolchain": cls.tc.pin,
                    "lean_file": "Contract.lean", "internal_obligations": [],
                    "bindings": [{"obligation": "D1", "declarations": declarations},
                                 {"obligation": "O1", "theorem": NAMESPACE + "." + theorem}]}
            base, _, problems = contract.compose_challenge(source,
                contract.registry_lean(records(), contract.binding_names(form)))
            if problems:
                raise AssertionError(problems)
            compiled = leanbridge.compile_module(cls.tc, base, cls.root / ("fixture-" + variant),
                timeout=cls.pol["build_timeout_seconds"], memory_mb=cls.pol["memory_mb"],
                require_network_isolation=cls.pol["require_network_isolation"],
                require_filesystem_isolation=cls.pol["require_filesystem_isolation"])
            if not compiled.ok:
                raise AssertionError(compiled.errors)
            exported = leanbridge.run_kernel_tool(cls.tc, compiled.olean,
                {"export": True, "axioms": True}, **cls.kernel_options)
            env = contract.Env.from_export(exported, cls.pol, "authored equality regression")
            analysis = contract.analyze(env, records(), form, cls.pol, cls.tc.pin, "authored equality regression")
            if env.diagnostics or analysis.diagnostics:
                raise AssertionError((env.diagnostics, analysis.diagnostics))
            cls.fixtures[variant] = source, form, base, env, analysis

    def run_check(self, variant, *, analysis=None, source=None, suffix=""):
        original_source, form, base, env, original_analysis = self.fixtures[variant]
        supplied_source = original_source if source is None else source
        supplied_analysis = original_analysis if analysis is None else analysis
        value = RECORD_INPUT if variant == "existing" else INPUT
        proposals = [{"obligation_id": "O1", "inputs": [value]}]
        pkg = Package(self.root / (self.id().split(".")[-1] + suffix))
        pkg.ensure()
        result = cr.check(pkg, supplied_source, form, records(), supplied_analysis, proposals=proposals)
        return result, pkg, {"source": supplied_source, "form": form, "base": base, "env": env,
                             "analysis": supplied_analysis, "proposals": proposals}

    def assert_bound_refutation(self, result, pkg, supplied):
        self.assertEqual("REFUTED", result["status"], result["diagnostics"])
        self.assertTrue(result["receipts"], result)
        for receipt in result["receipts"]:
            self.assertEqual("REFUTED", receipt["status"])
            self.assertEqual("guarantee_refutation", receipt["kind"])
            self.assertEqual(0, receipt["refutation_sorry_dependencies"])
            self.assertEqual([], receipt["axioms"])
            self.assertEqual({"ok": True, "typechecks": True, "defeq": True}, receipt["kernel_defeq"])
            for field, digest in {
                "candidate_source_hash": canonical.digest(supplied["source"]),
                "formalization_hash": canonical.digest_json(supplied["form"]),
                "records_hash": canonical.digest_json(records()),
                "analysis_hash": canonical.digest_json(cr._analysis_identity(supplied["analysis"])),
                "proposals_hash": canonical.digest_json(supplied["proposals"]),
            }.items():
                self.assertEqual(digest, receipt["binding"][field])
            self.assertEqual(supplied["proposals"][0]["inputs"], receipt["binding"]["inputs"])
            for artifact in receipt["artifacts"].values():
                self.assertEqual(artifact["sha256"], canonical.digest_file(pkg.root / artifact["path"]))
            proof_source = (pkg.root / receipt["artifacts"]["source"]["path"]).read_bytes()
            self.assertTrue(proof_source.startswith(supplied["base"]))
            exported = json.loads((pkg.root / receipt["artifacts"]["kernel_export"]["path"]).read_text())
            proof_env = contract.Env.from_export(exported, self.pol, "equality regression receipt")
            self.assertFalse(proof_env.diagnostics)
            for name, digest in supplied["env"].hashes.items():
                self.assertEqual(digest, proof_env.hashes.get(name), name)
            self.assertTrue(cr._clean_root(proof_env, receipt["lean_symbol"], self.pol)[0])
            self.assertEqual(decl_hash(proof_env.decls[receipt["lean_symbol"]]), receipt["declaration_hash"])
            self.assertEqual(canonical.digest_json({
                "module": receipt["artifacts"]["compiled_module"]["sha256"],
                "declaration": receipt["declaration_hash"], "proposition": receipt["proposition_hash"],
                "kernel_export": receipt["artifacts"]["kernel_export"]["sha256"],
                "kernel_tool": receipt["kernel_tool_hash"], "toolchain": receipt["toolchain"]}),
                receipt["kernel_proof_hash"])
            stripped = dict(receipt)
            del stripped["receipt_hash"]
            self.assertEqual(canonical.digest_json(stripped), receipt["receipt_hash"])
        return proof_source[len(supplied["base"]):].decode(), proof_env, receipt

    def audited_equalities(self, env, carrier):
        names = sorted(name for name, row in env.decls.items()
                       if row.get("type") == app(const("DecidableEq", [1]), const(carrier)))
        for name in names:
            self.assertEqual(env.hashes[name], reify._enum_equality_declaration(
                name, carrier, env.decls, env.hashes))
        return names

    def test_existing_enum_and_record_equalities_are_reused_by_clean_closed_proof(self):
        result, pkg, supplied = self.run_check("existing")
        tail, _, _ = self.assert_bound_refutation(result, pkg, supplied)
        for carrier in (ENUM, RECORD):
            names = self.audited_equalities(supplied["env"], carrier)
            self.assertTrue(names)
            self.assertIn(" := " + cr._qualified(names[0]), tail)
            self.assertNotIn("deriving instance _root_.DecidableEq for " + cr._qualified(carrier), tail)

    def test_private_numeric_equality_name_preserves_safe_deriving_fallback(self):
        result, pkg, supplied = self.run_check("private")
        names = self.audited_equalities(supplied["env"], ENUM)
        self.assertEqual(1, len(names))
        self.assertTrue(names[0].startswith("_private."))
        with self.assertRaisesRegex(ValueError, "unsupported Lean name component"):
            cr._qualified(names[0])
        tail, proof_env, receipt = self.assert_bound_refutation(result, pkg, supplied)
        self.assertIn("deriving instance _root_.DecidableEq for " + cr._qualified(ENUM), tail)
        self.assertNotIn("local instance", tail)
        self.assertNotIn(names[0], closure({receipt["lean_symbol"]}, proof_env.decls))

    def test_unprintable_first_candidate_uses_audited_printable_public_alternative(self):
        result, pkg, supplied = self.run_check("private-public")
        names = self.audited_equalities(supplied["env"], ENUM)
        self.assertEqual(2, len(names))
        self.assertTrue(names[0].startswith("_private."))
        self.assertEqual("zzUsableEquality", names[-1])
        tail, proof_env, receipt = self.assert_bound_refutation(result, pkg, supplied)
        self.assertIn(" := " + cr._qualified("zzUsableEquality"), tail)
        self.assertNotIn("deriving instance", tail)
        self.assertNotIn(names[0], closure({receipt["lean_symbol"]}, proof_env.decls))

    def test_mismatched_analysis_rejects_before_otherwise_available_refutation(self):
        matching, pkg, supplied = self.run_check("private", suffix="-matching")
        self.assert_bound_refutation(matching, pkg, supplied)
        mismatched = copy.deepcopy(supplied["analysis"])
        mismatched.statements["O1"]["formula_package"]["formula"] = {"tag": "true"}
        self.assertNotEqual(cr._analysis_identity(supplied["analysis"]), cr._analysis_identity(mismatched))
        result, _, _ = self.run_check("private", analysis=mismatched, suffix="-mismatch")
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual(BINDING_ERROR, result["diagnostics"])
        self.assertEqual(0, result["bounded_scan"]["proof_attempts"])
        self.assertEqual(0, result["bounded_scan"]["cases_evaluated"])
        self.assertEqual([], result["receipts"])

    def test_comment_equivalence_receipt_binds_the_exact_new_source_bytes(self):
        original = self.fixtures["private"][0]
        commented = original.replace(b"import Std\n", b"import Std\n-- same semantics, new bytes\n", 1)
        result, pkg, supplied = self.run_check("private", source=commented)
        self.assert_bound_refutation(result, pkg, supplied)
        self.assertNotEqual(canonical.digest(original), result["candidate_source_hash"])
        self.assertEqual(canonical.digest(commented), result["candidate_source_hash"])


if __name__ == "__main__":
    unittest.main()
