"""Kernel replay quarantines executable recursion companions, never proof roots."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import EX, TempDir, build, codes, formalization_variant
from verislop import canonical, contract, leanbridge, policy
from verislop.exprjson import name_str


def recursive_reference(source: str) -> str:
    source = source.replace("import Std", "module\npublic import Std\n\npublic section", 1)
    source = source.replace("namespace VeriSlop.BoundedIncrement", """namespace VeriSlop.BoundedIncrement

def countUp : Nat → Nat
  | 0 => 0
  | n + 1 => countUp n + 1
""", 1)
    return source.replace("then .ok (input + 1)", "then .ok (input + countUp 1)")


PROOF_CORE = (EX / "lean" / "BoundedIncrement.lean").read_text().split("inductive ObligationKind where")[0]


class RecursiveReplayAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        formal = formalization_variant(cls.tmp.path, "recursive-formalization", lean_edit=recursive_reference)
        proof = cls.tmp.path / "recursive-proof.lean"
        proof.write_text(recursive_reference(PROOF_CORE + "end VeriSlop.BoundedIncrement\n"))
        cls.base = cls.tmp.path / "recursive-package"
        cls.results = build(cls.base, "export", formalization=formal, proof=proof)
        for name, (code, response) in cls.results.items():
            if code != 0:
                raise AssertionError((name, code, response))
        cls.cert = canonical.load_file(cls.base / "accepted" / "acceptance.json")
        artifact = cls.base / cls.cert["artifacts"]["olean"]["path"]
        cls.exported = leanbridge.run_kernel_tool(cls.tc, artifact, {"export": True, "axioms": True})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_recursive_contract_is_accepted_and_ast_ir_contains_only_replayed_semantics(self):
        exported = self.exported
        self.assertTrue(exported["replay"]["ok"], exported)
        declarations = {name_str(c["name"]): c for c in exported["constants"]}
        parent = "VeriSlop.BoundedIncrement.countUp"
        helper = parent + "._unsafe_rec"
        self.assertEqual(declarations[parent]["kind"], "definition")
        self.assertEqual(declarations[parent]["safety"], "safe")
        self.assertEqual(declarations[helper], {
            "name": ["VeriSlop", "BoundedIncrement", "countUp", "_unsafe_rec"],
            "kind": "missing_after_replay", "replay_exclusion": "runtime_auxiliary",
            "omitted_kind": "definition", "safety": "partial",
            "replayed_parent": ["VeriSlop", "BoundedIncrement", "countUp"],
        })
        env = contract.Env.from_export(exported, policy.get("strict"), "test")
        self.assertFalse(env.diagnostics, env.diagnostics)
        self.assertIn(parent, env.decls)
        self.assertNotIn(helper, env.decls)
        self.assertNotIn(helper, env.hashes)
        statements = canonical.load_file(self.base / self.cert["artifacts"]["statements"]["path"])["statements"]
        self.assertTrue(any(parent in s["semantic_closure"] for s in statements.values()))
        self.assertFalse(any(helper in s["semantic_closure"] for s in statements.values()))
        ir = canonical.load_file(self.base / "accepted" / "accepted-ir.json")["obligations"]
        for oid, item in ir.items():
            self.assertEqual(item["formal"]["semantic_closure_hash"], statements[oid]["semantic_closure_hash"])

    def test_omitted_helper_cannot_be_used_as_a_denotation_or_witness_root(self):
        artifact = self.base / self.cert["artifacts"]["olean"]["path"]
        name = ["VeriSlop", "BoundedIncrement", "countUp", "_unsafe_rec"]
        exported = leanbridge.run_kernel_tool(self.tc, artifact, {
            "defeq": [{"id": "bad-root", "theorem": name, "expr": {"const": ["True"], "levels": []}}],
            "witnesses": [name],
        })
        self.assertFalse(exported["defeq"][0]["result"]["ok"])
        self.assertEqual(exported["defeq"][0]["result"]["error"], "theorem not found in replayed environment")
        self.assertFalse(exported["witnesses"][0]["ok"])
        self.assertEqual(exported["witnesses"][0]["error"], "not a replayed theorem")

    def test_invalid_quarantine_markers_are_rejected(self):
        for mutation in ("not-skipped", "safe-helper", "wrong-kind", "wrong-name", "opaque-parent", "missing-parent"):
            exported = copy.deepcopy(self.exported)
            helper = next(c for c in exported["constants"] if c.get("replay_exclusion") == "runtime_auxiliary")
            parent = next(c for c in exported["constants"] if c["name"] == helper["replayed_parent"])
            if mutation == "not-skipped":
                exported["replay"]["not_replayed_unsafe_or_partial"] = []
            elif mutation == "safe-helper":
                helper["safety"] = "safe"
            elif mutation == "wrong-kind":
                helper["omitted_kind"] = "axiom"
            elif mutation == "wrong-name":
                helper["name"][-1] = "other"
            elif mutation == "opaque-parent":
                parent["kind"] = "opaque"
            else:
                exported["constants"].remove(parent)
            with self.subTest(mutation=mutation):
                env = contract.Env.from_export(exported, policy.get("strict"), "test")
                self.assertIn("KERNEL_REJECTION", {d.code for d in env.diagnostics})

    def test_unexpected_missing_safe_constant_remains_rejected(self):
        exported = copy.deepcopy(self.exported)
        parent = next(c for c in exported["constants"] if name_str(c["name"]) == "VeriSlop.BoundedIncrement.countUp")
        parent["kind"] = "missing_after_replay"
        env = contract.Env.from_export(exported, policy.get("strict"), "test")
        self.assertIn("KERNEL_REJECTION", {d.code for d in env.diagnostics})

    def test_quarantined_helper_cannot_satisfy_a_contract_binding(self):
        def bind_helper(form):
            form["bindings"][0]["declarations"].append("VeriSlop.BoundedIncrement.countUp._unsafe_rec")
            return form

        formal = formalization_variant(self.tmp.path, "helper-binding-formalization",
                                       lean_edit=recursive_reference, form_edit=bind_helper)
        results = build(self.tmp.path / "helper-binding-package", "formalize", formalization=formal)
        self.assertEqual(results["formalize"][0], 2, results)
        self.assertIn("STATEMENT_MISMATCH", codes(results["formalize"][1]))
        self.assertNotIn("CANDIDATE_BUILD_FAILURE", codes(results["formalize"][1]))

    def test_unsafe_and_partial_user_declarations_remain_rejected(self):
        for safety, declaration in (
            ("unsafe", "unsafe def unchecked (n : Nat) : Nat := n"),
            ("partial", "partial def unchecked (n : Nat) : Nat := unchecked n"),
        ):
            formal = formalization_variant(self.tmp.path, safety + "-formalization", lean_edit=lambda s:
                s.replace("namespace VeriSlop.BoundedIncrement", "namespace VeriSlop.BoundedIncrement\n" + declaration, 1))
            results = build(self.tmp.path / (safety + "-package"), "formalize", formalization=formal)
            with self.subTest(safety=safety):
                self.assertEqual(results["interpret"][0], 0, results)
                self.assertEqual(results["formalize"][0], 2, results)
                self.assertIn("KERNEL_REJECTION", codes(results["formalize"][1]))
                self.assertNotIn("CANDIDATE_BUILD_FAILURE", codes(results["formalize"][1]))

    def test_unsafe_axiom_with_helper_name_is_not_quarantined(self):
        source = "import Std\nnamespace Adversarial\ndef trusted : Nat := 0\nunsafe axiom trusted._unsafe_rec : Nat\nend Adversarial\n"
        result = leanbridge.compile_module(self.tc, source.encode(), self.tmp.path / "helper-name-axiom")
        self.assertTrue(result.ok, result.errors)
        exported = leanbridge.run_kernel_tool(self.tc, result.olean, {"export": True, "axioms": True})
        axiom = next(c for c in exported["constants"] if name_str(c["name"]) == "Adversarial.trusted._unsafe_rec")
        self.assertEqual(axiom["kind"], "missing_after_replay")
        self.assertNotIn("replay_exclusion", axiom)
        env = contract.Env.from_export(exported, policy.get("strict"), "test")
        self.assertIn("KERNEL_REJECTION", {d.code for d in env.diagnostics})


if __name__ == "__main__":
    unittest.main()
