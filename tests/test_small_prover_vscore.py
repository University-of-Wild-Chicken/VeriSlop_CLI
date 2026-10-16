"""Authored VSCore orchestration fixtures; no model inference or bridge acceptance claims."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_small_prover_routing as route_fixture

from verislop import agents, canonical, leanbridge
from verislop.bridges import vscore3_checker
from verislop.errors import Diagnostic
from verislop.providers import config
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker


class SmallProverVSCoreTests(unittest.TestCase):
    setUp = route_fixture.SmallProverRoutingTests.setUp

    def fixture(self):
        params = {'tier': 2, 'target': 'vscore', 'endpoint': 'restricted_source',
                  'backend': 'verislop.backend.vscore/0.3', 'backend_version': '0.3',
                  'require_state': 'END_TO_END_VERIFIED', 'require_tests': False}
        relation = {'schema_version': '0.3', 'format': 'verislop.vscore-relation/0.3',
                    'template': 'vscore.reference_refinement/0.3', 'source_slot': 'source',
                    'proof_slot': 'proof', 'bindings': [{'symbol': 'plus', 'entry': 'plus'}]}
        from verislop.targets import vscore3_source
        source = vscore3_source.compile_surface('program "vscore/0.3" profile "data-pipeline/0.3"; entry plus(x:Int)->Int{x+int(2)}')
        fixed = {'parameters': params, 'accepted_reference': {}, 'accepted_packages': {},
                 'accepted_profile': {}, 'lean_toolchain': leanbridge.DEFAULT_TOOLCHAIN}
        info = {'proposition_hash': 'sha256:' + 'a' * 64, 'model': b'{}', 'profile': b'{}'}
        return params, relation, source, fixed, info

    def test_entire_proof_subprocess_uses_dedicated_wire_purpose_and_persisted_fallback(self):
        params, relation, source, fixed, info = self.fixture()
        broker = Broker(config.resolve(self.conf, {}), None)
        calls = []
        def completion(broker, agent, instance, system, user, purpose):
            calls.append((agent, instance, purpose, user))
            if instance.startswith('implementer/'):
                text = json.dumps({'program': canonical.loads(source), 'relation': relation})
            elif agent == 'small':
                text = 'theorem edge : VeriSlopBridgeGoal.EdgeProp := by exact missing_proof'
            else:
                text = ('import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\n'
                        'theorem edge : VeriSlopBridgeGoal.EdgeProp := by rfl\nend VeriSlopBridgeProof\n')
            return Completion(text, broker.model_for(agent), broker.model_for(agent), None, 8, 6)
        def preview(pkg, source, relation, proof=None, **kw):
            if proof is not None and b'missing_proof' in proof:
                raise vscore3_checker.EdgeFailure([Diagnostic('CANDIDATE_BUILD_FAILURE', 'fixture: unknown missing_proof')])
            return SimpleNamespace(text='fixed generated goal', refinement_symbols=[]), None, info
        with patch.object(agents, '_vscore_context', return_value=fixed), \
             patch.object(Broker, 'call', new=completion), \
             patch.object(vscore3_checker, 'preview', side_effect=preview), \
             patch.object(agents._vscore_components(params)['target'], 'library_sources', return_value={}):
            files, _ = agents._vscore_implementation(broker, self.conf, self.pkg, self.events,
                                                    {'parameters': params}, 1, 3)
            first_calls = list(calls)
            # A second source proposal with identical immutable semantics cannot reset three local slots.
            files2, _ = agents._vscore_implementation(broker, self.conf, self.pkg, self.events,
                                                     {'parameters': params}, 1, 3)
        self.assertEqual(['local-author', 'small', 'small', 'small', 'local-author'], [c[0] for c in first_calls])
        self.assertEqual(['generate', 'prove-vscore', 'prove-vscore', 'prove-vscore', 'generate'], [c[2] for c in first_calls])
        self.assertEqual(['local-author', 'local-author'], [c[0] for c in calls[len(first_calls):]])
        self.assertIn(b'by rfl', files['Proof.lean'])
        self.assertEqual(files['Proof.lean'], files2['Proof.lean'])
        self.assertIn('fixture: unknown missing_proof', first_calls[-1][3])

    def test_invalid_initial_complete_file_is_feedback_without_poisoning_fragment_baseline(self):
        params, relation, source, fixed, info = self.fixture()
        broker = Broker(config.resolve(self.conf, {}), None)
        initial = ('import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\ndef helper := 1\n'
                   'theorem edge : VeriSlopBridgeGoal.EdgeProp := by exact missing_proof\nend VeriSlopBridgeProof\n')
        calls = []
        def completion(broker, agent, instance, system, user, purpose):
            calls.append((agent, user))
            text = (json.dumps({'program': canonical.loads(source), 'relation': relation, 'proof_source': initial})
                    if instance.startswith('implementer/') else 'theorem edge : VeriSlopBridgeGoal.EdgeProp := by rfl')
            return Completion(text, broker.model_for(agent), broker.model_for(agent), None, 8, 6)
        def preview(pkg, source, relation, proof=None, **kw):
            if proof is not None and b'missing_proof' in proof:
                raise vscore3_checker.EdgeFailure([Diagnostic('CANDIDATE_BUILD_FAILURE', 'fixture: initial proof failed')])
            return SimpleNamespace(text='fixed generated goal', refinement_symbols=[]), None, info
        with patch.object(agents, '_vscore_context', return_value=fixed), patch.object(Broker, 'call', new=completion), \
             patch.object(vscore3_checker, 'preview', side_effect=preview), \
             patch.object(agents._vscore_components(params)['target'], 'library_sources', return_value={}):
            files, _ = agents._vscore_implementation(broker, self.conf, self.pkg, self.events, {'parameters': params}, 1, 3)
        self.assertEqual(['local-author', 'small'], [c[0] for c in calls])
        self.assertIn('fixture: initial proof failed', calls[1][1])
        self.assertNotIn(b'def helper', files['Proof.lean'])
        self.assertIn(b'by rfl', files['Proof.lean'])

    def test_hybrid_refiner_receives_rejected_raw_fragment_and_restores_it_for_identical_job(self):
        params, relation, source, fixed, info = self.fixture()
        self.conf['agents']['refiner'] = {**self.conf['agents']['small'], 'model_ref': 'refiner:test'}
        self.conf['proof_routing'].update(refinement_agent='refiner', refinement_attempts=3)
        broker = Broker(config.resolve(self.conf, {}), None)
        rejected = 'theorem edge : True := by trivial'
        calls = []
        def completion(broker, agent, instance, system, user, purpose):
            calls.append((agent, instance, purpose, user))
            if instance.startswith('implementer/'):
                text = json.dumps({'program': canonical.loads(source), 'relation': relation})
            elif agent == 'small':
                text = rejected
            else:
                text = 'theorem edge : VeriSlopBridgeGoal.EdgeProp := by rfl'
            return Completion(text, broker.model_for(agent), broker.model_for(agent), None, 8, 6)
        def preview(pkg, source, relation, proof=None, **kw):
            return SimpleNamespace(text='fixed generated goal', refinement_symbols=[]), None, info
        with patch.object(agents, '_vscore_context', return_value=fixed), patch.object(Broker, 'call', new=completion), \
             patch.object(vscore3_checker, 'preview', side_effect=preview), \
             patch.object(agents._vscore_components(params)['target'], 'library_sources', return_value={}):
            files, _ = agents._vscore_implementation(broker, self.conf, self.pkg, self.events, {'parameters': params}, 1, 3)
            first_calls = list(calls)
            resumed, _ = agents._vscore_implementation(broker, self.conf, self.pkg, self.events, {'parameters': params}, 1, 3)
        self.assertEqual(['local-author'] + ['small'] * 3 + ['refiner'], [c[0] for c in first_calls])
        self.assertEqual(['local-author', 'refiner'], [c[0] for c in calls[len(first_calls):]])
        for call in (first_calls[-1], calls[-1]):
            self.assertIn('EXACT RETAINED PROOF REJECTION', call[3])
            self.assertIn(rejected, call[3])
            self.assertIn('fragment header does not match a frozen theorem: edge', call[3])
            self.assertEqual('prove-vscore', call[2])
        self.assertEqual(files['Proof.lean'], resumed['Proof.lean'])
        self.assertNotIn(b': True :=', files['Proof.lean'])


if __name__ == '__main__':
    unittest.main()
