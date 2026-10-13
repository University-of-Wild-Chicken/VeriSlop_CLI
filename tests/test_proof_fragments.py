"""Fragment protocol fixtures are authored tests, never live-model successes."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verislop import leanbridge, proof_fragments


FROZEN = ('import Std\nnamespace FragmentFixture\ndef identity (n : Nat) : Nat := n\n'
          'theorem keeps (n : Nat) : identity n = n := by sorry\n'
          '-- Frozen trailing comment: theorem fake : False := by sorry\n'
          'theorem witness : ∃ n : Nat, identity n = 0 := by\n  sorry\n'
          'end FragmentFixture\n')
FIRST = 'theorem keeps (n : Nat) : identity n = n := by rfl'
SECOND = 'theorem witness : ∃ n : Nat, identity n = 0 := by exact ⟨0, rfl⟩'


class ProofFragmentTests(unittest.TestCase):
    def test_exact_scaffold_and_frozen_comments_survive_partial_and_cumulative_fragments(self):
        first = proof_fragments.assemble(FIRST, FROZEN)
        self.assertEqual(FROZEN.replace('by sorry', 'by rfl', 1), first)
        result = proof_fragments.assemble(SECOND, FROZEN, first)
        self.assertEqual(first.replace('by\n  sorry', 'by exact ⟨0, rfl⟩'), result)
        self.assertIn('-- Frozen trailing comment:', result)

    def test_header_token_whitespace_and_nested_comments_are_harmless(self):
        response = 'theorem keeps (n/- nested /- def attack -/ -/:Nat): identity n=n:= by rfl'
        result = proof_fragments.assemble(response, FROZEN)
        self.assertEqual(FROZEN.replace('by sorry', 'by rfl', 1), result)

    def test_single_fence_and_multiple_theorems_preserve_frozen_bytes(self):
        response = '```lean\n' + FIRST + '\n' + SECOND + '\n```'
        result = proof_fragments.assemble(response, FROZEN)
        self.assertEqual(FROZEN.replace('by sorry', 'by rfl', 1).replace('by\n  sorry', 'by exact ⟨0, rfl⟩'), result)

    def test_explicit_applications_in_header_and_body_survive_assembly_and_resume(self):
        header = 'theorem application : ∀ (n : Nat), @Eq Nat (@id Nat n) n :='
        frozen = ('import Std\nnamespace ExplicitApplicationFixture\n' + header + ' by sorry\n'
                  'theorem next : True := by sorry\nend ExplicitApplicationFixture\n')
        body = ' by\n  intro n\n  exact @Eq.refl Nat n'
        previous = proof_fragments.assemble(header + body, frozen)
        self.assertEqual(frozen.replace(' by sorry', body, 1), previous)
        result = proof_fragments.assemble('theorem next : True := by trivial', frozen, previous)
        self.assertEqual(previous.replace('by sorry', 'by trivial'), result)
        tc = leanbridge.resolve_toolchain()
        with tempfile.TemporaryDirectory(prefix='verislop-fragment-application-') as tmp:
            build = leanbridge.compile_module(tc, result.encode(), Path(tmp), timeout=30,
                                               memory_mb=512, require_network_isolation=True)
        self.assertTrue(build.ok, build.errors)
        self.assertEqual([], build.sorry_positions)

    def test_command_keywords_in_a_single_term_are_not_extra_commands(self):
        frozen = 'import Std\ntheorem local_open : True := by sorry\n'
        proposal = 'theorem local_open : True := open Nat in by trivial'
        result = proof_fragments.assemble(proposal, frozen)
        self.assertEqual(frozen.replace('by sorry', 'open Nat in by trivial'), result)
        proof_fragments.validate_previous(result, frozen)

    def test_changed_headers_unknown_duplicate_and_extra_commands_are_rejected(self):
        cases = [FIRST.replace('identity n = n', 'True'), FIRST.replace('n : Nat', 'n : Int'),
                 FIRST.replace('keeps', 'unknown'), FIRST + '\n' + FIRST,
                 'import Std\n' + FIRST, 'namespace Attack\n' + FIRST + '\nend Attack',
                 FIRST + '\ndef injected : Nat := 7', '@[simp]\n' + FIRST,
                 FIRST + '\n@[simp]\n' + SECOND,
                 FIRST + '\n  @[simp] theorem injected : True := by trivial',
                 FIRST + '\nmacro_rules | `(tactic| unused) => `(tactic| trivial)',
                 FIRST + '\n  run_cmd pure ()', FIRST + '\n  run_meta Lean.logInfo "extra"',
                 FIRST + '\n  run_elab Lean.logInfo "extra"',
                 FIRST + '\nunsupported_command arbitrary_text',
                 'prose before theorem\n' + FIRST, FIRST + '\n/- unterminated']
        for response in cases:
            with self.subTest(response=response), self.assertRaises(proof_fragments.FragmentError):
                proof_fragments.assemble(response, FROZEN)

    def test_unsupported_frozen_macro_scaffold_is_rejected_without_deleting_it(self):
        for indent in ('', '  '):
            frozen = ('theorem t : True := by sorry\n' + indent +
                      'macro_rules | `(tactic| unused) => `(tactic| trivial)\ndef x : Nat := 7\n')
            with self.subTest(indent=indent), self.assertRaises(proof_fragments.FragmentError):
                proof_fragments.assemble('theorem t : True := by trivial', frozen)

    def test_strings_characters_quoted_names_and_comment_decoys_are_not_commands(self):
        frozen = ('import Std\nnamespace Fixture\n'
                  'theorem «quoted theorem» : "def -- theorem" = "def -- theorem" := by sorry\n'
                  "theorem prime' : 'a' = 'a' := by sorry\nend Fixture\n")
        response = ('-- theorem forged : False := by sorry\n'
                    'theorem «quoted theorem» : "def -- theorem" = "def -- theorem" := by rfl\n'
                    "theorem prime' : 'a' = 'a' := by rfl")
        self.assertEqual(frozen.replace('by sorry', 'by rfl'), proof_fragments.assemble(response, frozen))

    def test_changed_prior_scaffold_or_header_cannot_be_preserved(self):
        previous = proof_fragments.assemble(FIRST, FROZEN)
        for changed in (previous.replace(':= n', ':= n + 1'),
                        previous.replace('identity n = n', 'True'),
                        previous + '\ndef injected := 1\n'):
            with self.subTest(changed=changed), self.assertRaises(proof_fragments.FragmentError):
                proof_fragments.assemble(SECOND, FROZEN, changed)

    def test_actual_pinned_lean_accepts_generated_fragments_with_definitions_and_witness(self):
        source = proof_fragments.assemble(FIRST + '\n' + SECOND, FROZEN)
        tc = leanbridge.resolve_toolchain()
        with tempfile.TemporaryDirectory(prefix='verislop-fragment-lean-') as tmp:
            build = leanbridge.compile_module(tc, source.encode(), Path(tmp), timeout=30,
                                               memory_mb=512, require_network_isolation=True)
        self.assertTrue(build.ok, build.errors)
        self.assertEqual([], build.sorry_positions)
        with self.assertRaises(proof_fragments.FragmentError):
            proof_fragments.assemble(FIRST.replace('identity n = n', 'True'), FROZEN)


if __name__ == '__main__':
    unittest.main()
