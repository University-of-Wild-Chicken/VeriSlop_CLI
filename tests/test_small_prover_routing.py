"""Optional route policy, persistent allocation, concrete repair and bounded fallback."""
from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import agents, canonical, contract, leanbridge, proof_routing, prove, schemas
from verislop.errors import Diagnostic, InfrastructureError, UsageError, BlockedError
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers import config
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ('import Std\nnamespace RouteFixture\ndef identity (n : Nat) : Nat := n\n'
          'theorem keeps (n : Nat) : identity n = n := by sorry\nend RouteFixture\n')
REGISTRY = contract.REGISTRY_BEGIN + '\n' + contract.REGISTRY_END + '\n'
BAD = 'theorem keeps (n : Nat) : True := by trivial'
GOOD = 'theorem keeps (n : Nat) : identity n = n := by rfl'


class SmallProverRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='verislop-small-route-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pkg = Package(self.root / 'package')
        self.pkg.ensure('small-route-unit')
        self.events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(self.events.close)
        self.conf = json.loads((ROOT / 'examples/ollama-review-config.json').read_text())
        for agent in self.conf['agents'].values():
            agent['model_ref'] = 'fallback:test'
        self.conf['agents']['small'] = {'provider': 'local', 'model_ref': 'small:test',
                                      'tool_profile': 'proof_sandbox', 'max_output_tokens': 4096,
                                      'proof_response_format': 'theorem_fragment'}
        self.conf['proof_routing'] = {'enabled': True, 'initial_agent': 'small', 'initial_attempts': 3}
        self.cfg = self.root / 'config.json'
        self.challenge = self.root / 'challenge'
        self.challenge.mkdir()
        (self.challenge / 'Contract.lean').write_text(SOURCE + REGISTRY)
        (self.challenge / 'lean-toolchain').write_text(leanbridge.DEFAULT_TOOLCHAIN + '\n')
        self.policy = {'build_timeout_seconds': 30, 'memory_mb': 512, 'require_network_isolation': True}

    def inputs(self, *, real_lean=False):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(contract, 'load_frozen', return_value=({}, [])))
        stack.enter_context(patch.object(contract, 'challenge_dir', return_value=self.challenge))
        stack.enter_context(patch.object(contract, 'frozen_json', side_effect=lambda pkg, name: {
            'statements.json': {'statements': {}}, 'profile.json': {}, 'policy.json': self.policy,
            'formalization.json': {}}[name]))
        if not real_lean:
            def evaluated(tc, policy, source):
                errors = ['unknown proof ' + source.split('missing_')[-1].split()[0]] if 'missing_' in source else []
                holes = len(prove.sorry_sites(source))
                return {'ok': not errors, 'errors': errors, 'sorries': holes,
                        'complete': not errors and not holes, 'wall_ms': 1}
            stack.enter_context(patch.object(prove, 'evaluate', side_effect=evaluated))
        return stack

    def run_proofs(self, response, *, fallback_budget=4, real_lean=False):
        self.cfg.write_text(json.dumps(self.conf))
        calls = []
        def complete(broker, agent, instance, system, user, purpose):
            calls.append({'agent': agent, 'instance': instance, 'system': system, 'user': user, 'purpose': purpose})
            text = response(agent, len(calls)) if callable(response) else response
            return Completion(text, broker.model_for(agent), broker.model_for(agent), None, 11, 7)
        with self.inputs(real_lean=real_lean), patch.object(Broker, 'call', new=complete):
            role = agents.prover_agent(self.cfg, self.pkg, self.events)
            result = prove.run(self.pkg, self.events, portfolio=False, budget_seconds=0,
                               max_attempts=fallback_budget, agent=role)
        return result, calls

    def test_local_success_avoids_fallback_and_preserves_frozen_bytes(self):
        before = (self.challenge / 'Contract.lean').read_bytes()
        result, calls = self.run_proofs(GOOD)
        self.assertEqual('PASS', result.status)
        self.assertEqual(['small'], [c['agent'] for c in calls])
        self.assertEqual(1, result.summary['proof_routing']['initial_attempts'])
        self.assertEqual(0, result.summary['proof_routing']['fallback_attempts'])
        self.assertIn('EXACT FROZEN THEOREM HEADERS', calls[0]['user'])
        self.assertEqual(before, (self.challenge / 'Contract.lean').read_bytes())

    def test_three_duplicate_rejections_escalate_instead_of_stopping_before_fallback(self):
        result, calls = self.run_proofs(lambda agent, number: BAD if agent == 'small' else SOURCE.replace('by sorry', 'by rfl'))
        self.assertEqual('PASS', result.status)
        self.assertEqual(['small'] * 3 + ['local-author'], [c['agent'] for c in calls])
        self.assertEqual(3, result.summary['proof_routing']['initial_attempts'])
        self.assertEqual(1, result.summary['proof_routing']['fallback_attempts'])
        self.assertIn(BAD, calls[-1]['user'])
        self.assertIn('fragment protocol:', calls[-1]['user'])

    def test_protocol_rejection_cannot_poison_next_correct_fragment_with_real_lean(self):
        result, calls = self.run_proofs(lambda agent, number: BAD if number == 1 else GOOD, real_lean=True)
        self.assertEqual('PASS', result.status, result.to_json())
        self.assertEqual(['small', 'small'], [c['agent'] for c in calls])
        self.assertIn(BAD, calls[1]['user'])
        records = [canonical.loads(line) for line in (self.pkg.path('contract') / 'proofs/attempts.jsonl').read_bytes().splitlines()]
        self.assertTrue(records[0]['protocol_rejected'])
        self.assertFalse(records[0]['complete'])
        self.assertTrue(records[1]['complete'])

    def test_early_transport_escalation_never_inherits_unused_initial_slots(self):
        fallback_calls = []
        def response(agent, number):
            if agent == 'small':
                raise InfrastructureError('local server unavailable', [Diagnostic('PROVIDER_FAILURE', 'network failure',
                    severity='infrastructure', details={'kind': 'network'})])
            fallback_calls.append(number)
            return SOURCE.replace('by sorry', 'by exact missing_' + str(number))
        result, calls = self.run_proofs(response, fallback_budget=4)
        self.assertEqual('BLOCKED', result.status)
        self.assertEqual(4, len(fallback_calls))
        self.assertEqual(['small'] + ['local-author'] * 4, [c['agent'] for c in calls])
        self.assertEqual(1, result.summary['proof_routing']['initial_attempts'])
        self.assertEqual(4, result.summary['proof_routing']['fallback_attempts'])
        self.assertEqual('initial_provider_failure', result.summary['proof_routing']['escalation_reason'])

    def test_global_budget_and_identity_failures_do_not_fallback(self):
        for code, kind in [('BUDGET_EXHAUSTED', None), ('PROVIDER_FAILURE', 'bad_response'),
                           ('PROVIDER_FAILURE', 'auth_invalid'), ('VERIFIER_FAILURE', None)]:
            with self.subTest(code=code, kind=kind):
                # Distinct package/job keeps this failure independent of prior subtests.
                self.pkg = Package(self.root / (code + str(kind)))
                self.pkg.ensure('failure-route-unit')
                def response(agent, number):
                    raise InfrastructureError('explicit failure', [Diagnostic(code, 'failure', severity='infrastructure',
                        details=({'kind': kind, **({'binding_failure': True} if kind == 'bad_response' else {})}
                                 if kind else {}))])
                with self.assertRaises(InfrastructureError):
                    self.run_proofs(response)

    def test_local_truncated_service_response_escalates_with_recorded_failure(self):
        def response(agent, number):
            if agent == 'small':
                raise InfrastructureError('local completion truncated', [Diagnostic('PROVIDER_FAILURE', 'truncated response',
                    severity='infrastructure', details={'kind': 'bad_response'})])
            return SOURCE.replace('by sorry', 'by rfl')
        result, calls = self.run_proofs(response)
        self.assertEqual('PASS', result.status)
        self.assertEqual(['small', 'local-author'], [c['agent'] for c in calls])
        self.assertEqual('initial_provider_failure', result.summary['proof_routing']['escalation_reason'])

    def test_terminal_model_binding_failure_cannot_turn_into_fallback_on_resume(self):
        called = []
        def response(agent, number):
            called.append(agent)
            raise InfrastructureError('model pin differs', [Diagnostic('PROVIDER_FAILURE', 'pin mismatch',
                severity='infrastructure', details={'kind': 'bad_response', 'binding_failure': True})])
        with self.assertRaises(InfrastructureError):
            self.run_proofs(response)
        for _ in range(3):
            with self.assertRaisesRegex(InfrastructureError, 'retained terminal proof-routing failure'):
                self.run_proofs(lambda *a: self.fail('terminal failure dispatched another model'))
        self.assertEqual(['small'], called)

    def test_exhausted_protocol_only_failure_resumes_without_compiling_raw_or_resetting_slots(self):
        self.conf['agents']['local-author']['proof_response_format'] = 'theorem_fragment'
        result, calls = self.run_proofs(BAD, fallback_budget=1)
        self.assertEqual('BLOCKED', result.status)
        self.assertEqual(4, len(calls))
        # No proof file was compiled or promoted as a valid baseline.
        result, calls = self.run_proofs(lambda *a: self.fail('resume reset the route budget'), fallback_budget=1)
        self.assertEqual('BLOCKED', result.status)
        self.assertEqual([], calls)
        self.assertEqual(3, result.summary['proof_routing']['initial_attempts'])
        self.assertEqual(1, result.summary['proof_routing']['fallback_attempts'])

    def test_disabled_or_absent_route_and_zero_budget_make_no_optional_call(self):
        for routing in (None, {'enabled': False}, {'enabled': True, 'initial_agent': 'small', 'initial_attempts': 3}):
            self.pkg = Package(self.root / ('default-' + str(routing)))
            self.pkg.ensure('default-route-unit')
            if routing is None:
                self.conf.pop('proof_routing', None)
            else:
                self.conf['proof_routing'] = routing
            budget = 0 if routing and routing['enabled'] else 1
            result, calls = self.run_proofs(SOURCE.replace('by sorry', 'by rfl'), fallback_budget=budget)
            self.assertNotIn('small', [c['agent'] for c in calls])
            self.assertEqual([] if budget == 0 else ['local-author'], [c['agent'] for c in calls])

    def test_router_resumes_consumed_interrupted_dispatch_and_blocks_changed_configuration(self):
        broker = Broker(config.resolve(self.conf, {}), None)
        job = {'kind': 'contract', 'challenge_sha256': canonical.digest(SOURCE.encode())}
        router = proof_routing.create(broker, self.conf, self.pkg, self.events, job, 4)
        self.assertEqual(('small', 1), (router.next()[0], router.state['initial_used']))
        resumed = proof_routing.create(broker, self.conf, self.pkg, self.events, job, 4)
        self.assertFalse(resumed.state['pending'])
        self.assertEqual('interrupted_dispatch', resumed.state['last_outcome']['kind'])
        self.assertEqual(2, resumed.next()[1]['ordinal'])
        self.conf['agents']['small']['max_output_tokens'] += 1
        changed = Broker(config.resolve(self.conf, {}), None)
        with self.assertRaises(BlockedError):
            proof_routing.create(changed, self.conf, self.pkg, self.events, job, 4)
        different = proof_routing.create(changed, self.conf, self.pkg, self.events, {'kind': 'different'}, 4)
        self.assertEqual(1, different.next()[1]['ordinal'])

    def test_schema_and_usage_resolution_are_explicit(self):
        self.assertEqual([], schemas.validate('review-config', self.conf))
        resolved = config.resolve(self.conf, {})
        self.assertIn('small', resolved.used_agents)
        self.assertFalse([d for d in resolved.diagnostics if d.severity == 'blocking'])
        self.conf['agents']['small']['tool_profile'] = 'candidate_writer'
        self.assertTrue(any('proof_sandbox' in d.message for d in config.resolve(self.conf, {}).diagnostics))
        self.conf['proof_routing']['initial_agent'] = 'unknown'
        self.assertTrue(any('unknown initial agent' in d.message for d in config.resolve(self.conf, {}).diagnostics))
        self.conf['proof_routing']['initial_attempts'] = 2
        self.assertTrue(schemas.validate('review-config', self.conf))
        self.conf['agents']['small']['proof_response_format'] = 'guessed'
        self.assertTrue(schemas.validate('review-config', self.conf))


if __name__ == '__main__':
    unittest.main()
