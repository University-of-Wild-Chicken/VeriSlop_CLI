"""Authored fragment fixtures cross actual Lean acceptance; these are not model evals."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers

from verislop import accept, canonical, contract, proof_fragments, prove
from verislop.events import EventSink
from verislop.package import Package


class ProofFragmentAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='verislop-fragment-acceptance-')
        cls.root = Path(cls.tmp.name)
        cls.base = cls.root / 'frozen-base'
        results = helpers.build(cls.base, upto='formalize')
        for name, (exit_code, result) in results.items():
            if exit_code != 0:
                raise AssertionError((name, result))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def package(self, name):
        pkg = Package(helpers.copy_pkg(self.base, self.root / name))
        events = EventSink(pkg.run_id, quiet=True)
        self.addCleanup(events.close)
        challenge = (contract.challenge_dir(pkg) / 'Contract.lean').read_text()
        statements = contract.frozen_json(pkg, 'statements.json')['statements']
        profile = contract.frozen_json(pkg, 'profile.json')
        portfolio = prove.apply_portfolio(challenge, statements, profile)
        fragments = '\n'.join(t.header_text + ':=' + portfolio[t.body_start:t.body_end]
                              for t in proof_fragments.declarations(portfolio))
        return pkg, events, challenge, portfolio, fragments

    def test_generated_fragment_candidate_passes_actual_acceptance_and_preserves_frozen_inputs(self):
        pkg, events, challenge, portfolio, fragments = self.package('positive')
        frozen = {p.name: p.read_bytes() for p in contract.challenge_dir(pkg).iterdir() if p.is_file()}
        assembled = proof_fragments.assemble(fragments, challenge)
        self.assertEqual(portfolio, assembled)
        candidate = self.root / 'positive.lean'
        candidate.write_text(assembled)
        searched = prove.run(pkg, events, candidate=candidate, portfolio=False, budget_seconds=0)
        self.assertEqual('PASS', searched.status, searched.to_json())
        accepted = accept.run(pkg, events)
        self.assertEqual('PASS', accepted.status, accepted.to_json())
        self.assertEqual(frozen, {p.name: p.read_bytes() for p in contract.challenge_dir(pkg).iterdir() if p.is_file()})
        self.assertTrue(pkg.path('accepted').is_dir())

    def test_changed_theorem_is_rejected_by_fragment_protocol_and_actual_acceptance(self):
        pkg, events, challenge, portfolio, fragments = self.package('negative')
        changed_fragment = fragments.replace('output ≤ limit', 'True')
        self.assertNotEqual(fragments, changed_fragment)
        with self.assertRaises(proof_fragments.FragmentError):
            proof_fragments.assemble(changed_fragment, challenge)
        # Independently demonstrate that a compiling weakened complete file cannot gain acceptance.
        declarations = proof_fragments.declarations(portfolio)
        target = next(t for t in declarations if t.name == 'success_preserves_bound')
        changed = (portfolio[:target.start] + target.header_text.replace('output ≤ limit', 'True')
                   + ':= by trivial' + portfolio[target.body_end:])
        candidate = self.root / 'negative.lean'
        candidate.write_text(changed)
        searched = prove.run(pkg, events, candidate=candidate, portfolio=False, budget_seconds=0)
        self.assertEqual('PASS', searched.status, searched.to_json())
        accepted = accept.run(pkg, events)
        self.assertEqual('BLOCKED', accepted.status)
        self.assertTrue(any(d.code in {'STATEMENT_MISMATCH', 'CLAIM_MUTATION', 'IR_REIFICATION_MISMATCH'}
                            for d in accepted.diagnostics), accepted.to_json())
        certificate = canonical.load_file(pkg.path('accepted') / 'acceptance.json')
        self.assertEqual('blocked', certificate['gate'])
        self.assertNotEqual('PASS', certificate['obligations']['I2']['proved'])


if __name__ == '__main__':
    unittest.main()
