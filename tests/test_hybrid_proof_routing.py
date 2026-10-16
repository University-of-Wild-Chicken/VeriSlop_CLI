"""Concrete grouped local-proof/refinement/fallback fixtures, not model benchmarks."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_small_prover_routing as fixture

from verislop import canonical, proof_routing, schemas
from verislop.errors import BlockedError, Diagnostic, InfrastructureError
from verislop.providers import config
from verislop.providers.broker import Broker


class HybridProofRoutingTests(unittest.TestCase):
    inputs = fixture.SmallProverRoutingTests.inputs
    run_proofs = fixture.SmallProverRoutingTests.run_proofs

    def setUp(self):
        fixture.SmallProverRoutingTests.setUp(self)
        self.conf['agents']['refiner'] = {**self.conf['agents']['small'], 'model_ref': 'refiner:test'}
        self.conf['proof_routing'].update(refinement_agent='refiner', refinement_attempts=3)

    def router(self, fallback_budget=2):
        return proof_routing.create(Broker(config.resolve(self.conf, {}), None), self.conf,
            self.pkg, self.events, {'kind': 'hybrid-fixture', 'source': canonical.digest(fixture.SOURCE.encode())},
            fallback_budget)

    def test_refinement_uses_real_lean_and_exact_rejected_fragment_without_changing_frozen_source(self):
        before = (self.challenge / 'Contract.lean').read_bytes()
        result, calls = self.run_proofs(lambda agent, n: fixture.BAD if agent == 'small' else fixture.GOOD,
                                        real_lean=True)
        self.assertEqual('PASS', result.status, result.to_json())
        self.assertEqual(['small'] * 3 + ['refiner'], [c['agent'] for c in calls])
        self.assertIn('EXACT RETAINED PROOF REJECTION', calls[-1]['user'])
        self.assertIn(fixture.BAD, calls[-1]['user'])
        self.assertIn('fragment protocol:', calls[-1]['user'])
        self.assertEqual(1, result.summary['proof_routing']['refinement_attempts'])
        self.assertEqual(0, result.summary['proof_routing']['fallback_attempts'])
        self.assertEqual(before, (self.challenge / 'Contract.lean').read_bytes())

    def test_repeated_local_rejections_allow_full_refinement_and_preserve_fallback_budget(self):
        def response(agent, n):
            if agent in {'small', 'refiner'}:
                return fixture.BAD
            return fixture.SOURCE.replace('by sorry', 'by exact missing_' + str(n))
        result, calls = self.run_proofs(response, fallback_budget=2)
        self.assertEqual('BLOCKED', result.status)

        self.assertEqual(['small'] * 3 + ['refiner'] * 3 + ['local-author'] * 2,
                         [c['agent'] for c in calls])
        summary = result.summary['proof_routing']
        self.assertEqual((3, 3, 2), tuple(summary[k] for k in
                         ('initial_attempts', 'refinement_attempts', 'fallback_attempts')))
        self.assertEqual(['refinement', 'fallback'], [t['to'] for t in summary['transitions']])
        result, resumed = self.run_proofs(lambda *a: self.fail('resume reset consumed proof slots'), fallback_budget=2)
        self.assertEqual([], resumed)
        self.assertEqual('BLOCKED', result.status)

    def test_refiner_gets_actual_lean_compiler_failure_with_unchanged_goal(self):
        rejected = fixture.GOOD.replace('by rfl', 'by exact missing_hybrid_proof')
        result, calls = self.run_proofs(lambda agent, n: rejected if agent == 'small' else fixture.GOOD,
                                        real_lean=True)
        self.assertEqual('PASS', result.status, result.to_json())
        self.assertEqual(['small'] * 3 + ['refiner'], [c['agent'] for c in calls])
        self.assertIn(rejected, calls[-1]['user'])
        self.assertIn('Unknown identifier', calls[-1]['user'])
        self.assertIn('missing_hybrid_proof', calls[-1]['user'])

    def test_feedback_and_reserved_refinement_slot_survive_resume(self):
        route = self.router()
        for number in range(3):
            route.next()
            route.evaluation(False, ['actual diagnostic ' + str(number)], candidate='compiled candidate',
                             response='raw response ' + str(number))
        resumed = self.router()
        self.assertEqual('raw response 2', resumed.feedback()['raw_response'])
        self.assertEqual(['actual diagnostic 2'], resumed.feedback()['diagnostics'])
        self.assertEqual(('refiner', 1), (resumed.next()[0], resumed.state['refinement_used']))
        interrupted = self.router()
        self.assertEqual('interrupted_dispatch', interrupted.state['last_outcome']['kind'])
        self.assertEqual(('refiner', 2), (interrupted.next()[0], interrupted.state['refinement_used']))
        self.assertEqual('raw response 2', interrupted.feedback()['raw_response'])

    def test_local_context_overflow_advances_each_phase_without_claiming_dispatch(self):
        route = self.router()
        failure = InfrastructureError('exact prompt does not fit', [Diagnostic('PROVIDER_FAILURE', 'context overflow',
            severity='infrastructure', details={'kind': 'context_budget_exceeded', 'call_dispatched': False})])
        self.assertEqual('small', route.next()[0])
        self.assertTrue(route.failure(failure))
        self.assertIs(False, route.state['last_outcome']['call_dispatched'])
        self.assertEqual('refiner', route.next()[0])
        self.assertTrue(route.failure(failure))
        self.assertEqual('local-author', route.next()[0])
        self.assertEqual((1, 1, 1), tuple(route.state[k] for k in ('initial_used', 'refinement_used', 'fallback_used')))
        self.assertEqual(['initial_context_budget_exceeded', 'refinement_context_budget_exceeded'],
                         [t['reason'] for t in route.summary()['transitions']])

    def test_refiner_global_budget_error_remains_terminal_across_resume(self):
        route = self.router()
        route.escalate('initial_attempts_exhausted')
        self.assertEqual('refiner', route.next()[0])
        failure = InfrastructureError('provider total token budget exhausted', [Diagnostic('BUDGET_EXHAUSTED', 'tokens')])
        self.assertFalse(route.failure(failure))
        with self.assertRaisesRegex(InfrastructureError, 'retained terminal proof-routing failure'):
            self.router()

    def test_refiner_configuration_is_paired_bounded_and_required_when_enabled(self):
        self.assertEqual([], schemas.validate('review-config', self.conf))
        self.assertIn('refiner', config.resolve(self.conf, {}).used_agents)
        for key in ('refinement_agent', 'refinement_attempts'):
            changed = copy.deepcopy(self.conf)
            del changed['proof_routing'][key]
            self.assertTrue(schemas.validate('review-config', changed))
        for value in (0, 4, True):
            changed = copy.deepcopy(self.conf)
            changed['proof_routing']['refinement_attempts'] = value
            self.assertTrue(schemas.validate('review-config', changed))
        self.conf['agents']['refiner']['tool_profile'] = 'candidate_writer'
        self.assertTrue(any('refinement agent refiner must use tool_profile proof_sandbox' in d.message
                            for d in config.resolve(self.conf, {}).diagnostics))
        self.conf['proof_routing']['enabled'] = False
        self.assertNotIn('refiner', config.resolve(self.conf, {}).used_agents)


if __name__ == '__main__':
    unittest.main()
