"""Authoring transport boundaries; no model calls or proof credit."""
import copy
import unittest

from verislop import agents, canonical, capabilities, formal_frontend


def primitive_proposal(version):
    obj = {
        "encoding": version,
        "records": {},
        "symbols": {"answer": {"args": [], "result": "Int",
                               "body": {"tag": "int", "value": "7"}}},
        "predicates": {},
        "theorems": {"observable": {"formula": {
            "tag": "eq", "left": {"tag": "call", "symbol": "answer", "args": []},
            "right": {"tag": "int", "value": "7"}}}},
        "obligations": {"G1": {"theorem": "observable"}},
        "witness_obligations": {},
    }
    if version.endswith("/0.2"):
        obj["enums"] = {}
    return obj


FROZEN = [{"id": "G1", "origin": "interpreted", "blocked_by": [],
           "kind": "postcondition", "role": "guarantee", "required": True}]


class EnumAuthoringWorkflowUnits(unittest.TestCase):
    def test_both_exact_versions_reach_real_compiler_with_literal_origin(self):
        for version in ("verislop.formalizer-ast/0.1", "verislop.formalizer-ast/0.2"):
            with self.subTest(version=version):
                obj = primitive_proposal(version)
                text = canonical.dumps(obj).decode()
                source, bindings, compiled = agents.assemble_formalization_response(
                    text, FROZEN, "captured-response.json")
                self.assertEqual(compiled.proposal, obj)
                self.assertEqual(compiled.source, source)
                self.assertEqual(compiled.formalization, bindings)
                self.assertTrue(formal_frontend.reconstruct_origin(
                    text.encode(), FROZEN, source, bindings, compiled.receipt))
                self.assertIn(b"by sorry", source)
                mutated = copy.deepcopy(obj)
                mutated["symbols"]["answer"]["body"]["value"] = "8"
                self.assertFalse(formal_frontend.reconstruct_origin(
                    canonical.dumps(mutated), FROZEN, source, bindings, compiled.receipt))

    def test_version_dispatch_never_silently_downgrades_wrong_closed_envelope(self):
        old = primitive_proposal("verislop.formalizer-ast/0.1")
        old["enums"] = {}
        new = primitive_proposal("verislop.formalizer-ast/0.2")
        del new["enums"]
        for obj in (old, new):
            with self.subTest(version=obj["encoding"]), self.assertRaises(formal_frontend.FrontendError):
                agents.assemble_formalization_response(canonical.dumps(obj).decode(), FROZEN, "capture.json")

    def test_default_prompt_exposes_nominal_enum_declaration_sort_term_and_guard(self):
        prompt = agents.TYPED_FORMALIZER_SYSTEM
        for fragment in ('"encoding":"verislop.formalizer-ast/0.2"', '"enums":',
                         '"constructors":', '{"enum":"EnumName"}',
                         '"tag":"enum"', '"constructor":"alpha"',
                         'identical enum sorts', 'kind may also be enum',
                         'constructor names are its exact wire', 'Legacy typed /0.1'):
            self.assertIn(fragment, prompt)
        self.assertIn("kernel replay", prompt)
        self.assertIn("never remove requirements", prompt)

    def test_capability_catalog_separates_current_and_legacy_authoring_versions(self):
        catalog = capabilities.FORMAL["formalizer_frontend"]
        self.assertEqual(catalog["encoding"], "verislop.formalizer-ast/0.2")
        self.assertEqual(catalog["legacy_encodings"], ["verislop.formalizer-ast/0.1"])


if __name__ == "__main__":
    unittest.main()
