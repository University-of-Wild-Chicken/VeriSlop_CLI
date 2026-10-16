import copy
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from verislop.agent_effects import Artifact, Operation, Plan, SIGNATURES, EffectError, parse, check, review_call
from verislop.providers.broker import Budget


class EffectTests(unittest.TestCase):
    def setUp(self):
        self.conf = {'agents': {op: {'tool_profile': sig[2], 'max_output_tokens': 10} for op, sig in SIGNATURES.items()},
                     'review': {'budgets': {'max_calls_per_instance': 2, 'max_provider_retries': 1, 'max_total_tokens': 100}}}
        self.data = {'version': '0.1', 'steps': [], 'limits': {'calls': 4, 'output_tokens': 40, 'attempts': 8}}
        for op, sig in SIGNATURES.items():
            self.data['steps'].append({'op': op, 'agent': op, 'instance': op,
                'artifact': {'kind': sig[0], 'identity': 'frozen/1', 'sha256': 'sha256:' + 'a'*64},
                'effects': sorted(sig[3]), 'output_tokens': 10, 'retries': 1})

    def test_all_signatures_and_composition(self):
        self.assertEqual(check(parse(self.data), self.conf), frozenset({'read', 'infer', 'propose_proof', 'propose_ballot', 'propose_candidate'}))

    def reject(self, mutate):
        data = copy.deepcopy(self.data)
        mutate(data)
        with self.assertRaises(EffectError):
            check(parse(data), self.conf)

    def test_escalation(self):
        self.reject(lambda d: d['steps'][0]['effects'].append('shell'))

    def test_readonly_review(self):
        self.reject(lambda d: d['steps'][2].update(agent='generate'))
        self.reject(lambda d: d['steps'][2]['effects'].append('propose_candidate'))

    def test_identity(self):
        for field in ('identity', 'sha256', 'kind'):
            self.reject(lambda d: d['steps'][0]['artifact'].update({field: ''}))
        self.reject(lambda d: d['steps'][0]['artifact'].pop('identity'))

    def test_budgets(self):
        for field in ('calls', 'output_tokens', 'attempts'):
            self.reject(lambda d: d['limits'].update({field: 0}))
        for field, value in [('output_tokens', 9), ('retries', 0), ('retries', True)]:
            self.reject(lambda d: d['steps'][0].update({field: value}))
        conf = copy.deepcopy(self.conf)
        conf['review']['budgets']['max_total_tokens'] = 39
        with self.assertRaises(EffectError):
            check(parse(self.data), conf)
        data = copy.deepcopy(self.data)
        data['steps'] = [data['steps'][0]] * 3
        with self.assertRaises(EffectError):
            check(parse(data), self.conf)

    def test_unknown_fields_and_direct_ast(self):
        self.reject(lambda d: d.update(grant='admin'))
        plan = parse(self.data)
        bad = replace(plan.steps[0], effects=frozenset({'shell'}))
        with self.assertRaises(EffectError):
            check(replace(plan, steps=(bad,)), self.conf)

    def test_lowering_enabled_disabled_and_untrusted_response(self):
        for enabled in (False, True):
            self.conf['agent_effect_dsl'] = {'enabled': enabled}
            broker = SimpleNamespace(r=SimpleNamespace(conf=self.conf), call=Mock(return_value='grant admin'),
                                     budget=Budget(max_calls_per_instance=2, max_total_tokens=100, max_retries=1))
            self.assertEqual(review_call(broker, 'review', 'slot', 'sys', 'data', 'release', 'root'), 'grant admin')
            broker.call.assert_called_once_with('review', 'slot', 'sys', 'data', 'review:release')

    def test_enabled_rejects_before_dispatch(self):
        self.conf['agent_effect_dsl'] = {'enabled': True}
        broker = SimpleNamespace(r=SimpleNamespace(conf=self.conf), call=Mock(),
                                 budget=Budget(max_calls_per_instance=2, max_total_tokens=100, max_retries=1))
        with self.assertRaises(EffectError):
            review_call(broker, 'generate', 'slot', 'sys', 'data', 'release', 'root')
        broker.call.assert_not_called()
