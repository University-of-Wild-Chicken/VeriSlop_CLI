"""Generic readiness regressions; retained authored proposals are not live benchmarks."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_formal_frontend_workflow as frontend_fixture
from verislop import agent_memory, agents, autonomous, canonical, contract, dsl, formal_frontend, formalize, fsutil, leanbridge, policy

REQUESTED = {'tier': 0, 'target': 'python', 'endpoint': 'test_campaign', 'require_state': 'TESTED'}
AST = frontend_fixture.AST
RECORD = {'id': 'O1', 'role': 'guarantee', 'kind': 'postcondition', 'required': True, 'blocked_by': []}
PROFILE = {'profile_id': 'readiness.v0_2', 'dsl': dsl.ENCODING_V2,
    'enums': {'Color': {'constructors': ['red', 'blue']}},
    'records': {'Finite': {'fields': [{'name': 'flag', 'sort': 'Bool'}]},
                'Input': {'fields': [{'name': 'value', 'sort': 'Int'}]}},
    'symbols': {'step': {'lean_decl': 'Ready.step', 'args': ['Int'], 'result': 'Int'}}, 'predicates': {}}
GROUND = {'tag': 'eq', 'left': {'tag': 'call', 'symbol': 'step', 'args': [{'tag': 'int', 'value': '0'}]},
          'right': {'tag': 'int', 'value': '1'}}
POINTWISE = {'tag': 'eq', 'left': {'tag': 'call', 'symbol': 'step', 'args': [{'tag': 'var', 'index': 0}]},
    'right': {'tag': 'int_add', 'left': {'tag': 'var', 'index': 0}, 'right': {'tag': 'int', 'value': '1'}}}


def analysis(formula, profile=PROFILE, encoding=dsl.ENCODING_V2):
    return contract.Analysis(profile, {'O1': {'representation': 'contract_dsl',
        'semantic_closure': {'Ready.step': 'sha256:authored-fixture'},
        'formula_package': dsl.make_package(formula, profile['profile_id'], encoding=encoding)}}, [], [], [])


class QuantifierReadinessTests(unittest.TestCase):
    def check(self, formula, profile=PROFILE, records=None, requested=REQUESTED, encoding=dsl.ENCODING_V2):
        if encoding == dsl.ENCODING_V2:
            dsl.type_formula(formula, [], dsl.Profile.from_json(profile))
        return formalize.executable_readiness(records or [RECORD], analysis(formula, profile, encoding), requested)

    def test_residual_unbounded_quantifiers_have_exact_reconstructed_paths_tags_sorts(self):
        for tag in ('forall', 'exists'):
            for sort in ('Nat', 'Int', 'String', {'list': 'Int'}, {'record': 'Input'}, {'option': 'Int'}, {'result': {'error': 'Bool', 'ok': 'Int'}}):
                formula = {'tag': 'forall', 'sort': 'Int', 'body': {'tag': 'and', 'left': GROUND,
                    'right': {'tag': 'not', 'body': {'tag': tag, 'sort': sort, 'body': GROUND}}}}
                with self.subTest(tag=tag, sort=sort):
                    diagnostics = self.check(formula)
                    self.assertEqual(1, len(diagnostics))
                    self.assertEqual('INVALID_CANDIDATE', diagnostics[0].code)
                    self.assertEqual({'path': '/formula/body/right/body', 'tag': tag, 'sort': sort},
                                     diagnostics[0].details['residual_quantifier'])
                    self.assertIn('not a counterexample', diagnostics[0].message)

    def test_equivalent_pointwise_conjunction_under_leading_prefix_is_admitted(self):
        negative = {'tag': 'and', 'left': GROUND, 'right': {'tag': 'forall', 'sort': 'Int', 'body': POINTWISE}}
        positive = {'tag': 'forall', 'sort': 'Int', 'body': {'tag': 'and', 'left': GROUND, 'right': POINTWISE}}
        self.assertTrue(self.check(negative))
        self.assertEqual([], self.check(positive))
        leading_exists = {'tag': 'exists', 'sort': 'Int', 'body': POINTWISE}
        self.assertEqual('/formula', self.check(leading_exists)[0].details['residual_quantifier']['path'])

    def test_finite_quantifiers_and_explicit_ranges_remain_admitted_without_materialization(self):
        finite = ['Bool', 'Unit', {'enum': 'Color'}, {'record': 'Finite'}, {'option': 'Bool'},
                  {'result': {'error': {'enum': 'Color'}, 'ok': {'record': 'Finite'}}}]
        with patch.object(dsl, 'finite_values', side_effect=AssertionError('readiness must never enumerate finite domains')):
            for tag in ('forall', 'exists'):
                for sort in finite:
                    with self.subTest(tag=tag, sort=sort):
                        self.assertEqual([], self.check({'tag': 'and', 'left': GROUND,
                            'right': {'tag': tag, 'sort': sort, 'body': GROUND}}))
            for tag in ('forall_range', 'exists_range'):
                formula = {'tag': 'and', 'left': GROUND, 'right': {'tag': tag,
                    'lower': {'tag': 'nat', 'value': '0'}, 'upper': {'tag': 'nat', 'value': '2'}, 'body': GROUND}}
                self.assertEqual([], self.check(formula))

    def test_finite_shared_record_graph_is_memoized_without_product_expansion(self):
        profile = copy.deepcopy(PROFILE)
        profile['records'] = {'R0': {'fields': [{'name': 'flag', 'sort': 'Bool'}]}}
        for i in range(1, 36):
            profile['records'][f'R{i}'] = {'fields': [{'name': 'left', 'sort': {'record': f'R{i-1}'}},
                                                    {'name': 'right', 'sort': {'record': f'R{i-1}'}}]}
        formula = {'tag': 'and', 'left': GROUND, 'right': {'tag': 'exists', 'sort': {'record': 'R35'}, 'body': GROUND}}
        with patch.object(dsl, 'finite_values', side_effect=AssertionError('do not expand this finite record product')):
            self.assertEqual([], self.check(formula, profile))

    def test_residual_quantifiers_inside_range_bodies_are_still_inspected(self):
        formula = {'tag': 'forall_range', 'lower': {'tag': 'nat', 'value': '0'}, 'upper': {'tag': 'nat', 'value': '2'},
                   'body': {'tag': 'forall', 'sort': 'String', 'body': GROUND}}
        self.assertEqual('/formula/body', self.check(formula)[0].details['residual_quantifier']['path'])

    def test_legacy_and_excluded_modes_or_obligations_are_unchanged(self):
        formula = {'tag': 'and', 'left': GROUND, 'right': {'tag': 'forall', 'sort': 'Int', 'body': POINTWISE}}
        self.assertEqual([], self.check(formula, encoding=dsl.ENCODING))
        for requested in ({}, {'tier': 2, 'target': 'vscore', 'require_state': 'END_TO_END_VERIFIED'},
                          {'tier': 1, 'target': 'python', 'endpoint': 'instrumented_runtime', 'require_state': 'PROVED'},
                          {'tier': 0, 'target': 'other', 'endpoint': 'test_campaign'}):
            with self.subTest(requested=requested):
                self.assertEqual([], self.check(formula, requested=requested))
        for change in ({'required': False}, {'blocked_by': ['Q1']}, {'role': 'declaration'}, {'kind': 'non_vacuity'}):
            self.assertEqual([], self.check(formula, records=[{**RECORD, **change}]))
        self.assertTrue(self.check(formula, requested={**REQUESTED, 'tier': 1}))

    def test_readiness_traversal_is_explicitly_bounded(self):
        formula = {'tag': 'and', 'left': GROUND, 'right': {'tag': 'forall', 'sort': 'Int', 'body': POINTWISE}}
        with patch.dict(dsl.LIMITS, {'max_nodes': 3}):
            diagnostics = formalize.executable_readiness([RECORD], analysis(formula), REQUESTED)
        self.assertTrue(any(item.details.get('readiness_traversal_limit') for item in diagnostics))


class RealAgentQuantifierRepairTests(unittest.TestCase):
    setUp = frontend_fixture.FrontendWorkflowTests.setUp
    assert_pass = frontend_fixture.FrontendWorkflowTests.assert_pass

    def proposals(self):
        bad, good = copy.deepcopy(AST), copy.deepcopy(AST)
        pointwise = copy.deepcopy(AST['theorems']['result']['formula'])
        ground = {'tag': 'eq', 'left': {'tag': 'call', 'symbol': 'bump', 'args': [{
            'tag': 'record', 'sort': 'Input', 'fields': [{'tag': 'int', 'value': '0'}]}]},
            'right': {'tag': 'int', 'value': '1'}}
        bad['theorems']['result']['formula'] = {'tag': 'and', 'left': ground, 'right': pointwise}
        good['theorems']['result']['formula'] = {'tag': 'forall', 'sort': pointwise['sort'],
            'body': {'tag': 'and', 'left': ground, 'right': pointwise['body']}}
        return bad, good

    def role(self, responses, captured):
        responses = iter(responses)
        def call(*args):
            captured.append({'system': args[2], 'user': args[3]})
            return SimpleNamespace(text=next(responses), request_id='authored-quantifier-repair')
        with patch.object(agents, '_broker', return_value=(SimpleNamespace(call=call), {'roles': {'formalizer': 'author'}})):
            return agents.formalizer_agent('unused', self.pkg, self.events)

    def critic(self, captured):
        conf = json.loads((Path(__file__).resolve().parents[1] / 'examples/ollama-review-config.json').read_text())
        conf['review']['review_tiers'] = conf['review']['review_tiers'][:1]
        conf['review']['review_tiers'][0]['reviewers'] = [{'agent': 'critic', 'count': 1, 'focus': 'actual representation diagnostics'}]
        def call(*args):
            packet = json.loads(args[3]); captured.append(packet)
            if packet['diagnostics']:
                value = {'encoding': autonomous.VERSION, 'verdict': 'REPAIR', 'counterexamples': [],
                    'corrections': [{'diagnostic_index': 0, 'artifact': 'proposal.lean',
                        'explanation': 'Construct an equivalent pointwise conjunction under the leading Input binder, preserving the closed example.'}]}
            else:
                value = {'encoding': autonomous.VERSION, 'verdict': 'ACCEPT', 'corrections': [],
                    'counterexamples': [{'obligation_id': 'O1', 'inputs': [{'dict': {'value': {'int': '0'}}}]}]}
            return SimpleNamespace(text=canonical.dumps(value).decode())
        with patch.object(agents, '_broker', return_value=(SimpleNamespace(call=call), conf)):
            return autonomous.critic_agent('unused', self.pkg, self.events)

    def test_actual_reconstruction_critic_and_bounded_agent_repair_preserve_rejected_artifacts(self):
        bad, good = self.proposals()
        bad_raw = ' \n' + canonical.dumps(bad).decode() + '\n  '
        good_raw = canonical.dumps(good).decode()
        calls, packets = [], []
        with patch.object(formalize, 'attempt', wraps=formalize.attempt) as checker:
            result = formalize.run(self.pkg, self.events, agent=self.role([bad_raw, good_raw], calls),
                                   critic=self.critic(packets), max_attempts=2)
        self.assert_pass(result); self.assertEqual(2, checker.call_count)
        self.assertEqual(2, len(calls)); self.assertEqual(2, len(packets))
        shape = packets[0]['diagnostics'][0]['details']['residual_quantifier']
        self.assertEqual({'path': '/formula/right', 'tag': 'forall', 'sort': {'record': 'Input'}}, shape)
        self.assertEqual(bad_raw, packets[0]['raw_formalizer_response'])
        self.assertIn('CAMPAIGN QUANTIFIER SHAPE', calls[0]['user'])
        self.assertIn(bad_raw, calls[1]['user']); self.assertIn('/formula/right', calls[1]['user'])
        history = agent_memory.context_for(self.pkg, stages=['formalize/attempt'], last=2)['snapshots']
        first = canonical.loads(history[0]['artifacts']['payload.json']['content'])
        self.assertTrue(first['diagnostics'][0]['details']['campaign_quantifier_shape'])
        self.assertEqual(bad_raw, first['candidate']['raw_response'])
        frozen = contract.frozen_json(self.pkg, 'statements.json')['statements']['O1']['formula_package']['formula']
        self.assertEqual('forall', frozen['tag']); self.assertEqual('and', frozen['body']['tag'])
        self.assertEqual(good, canonical.load_file(self.pkg.path('contract') / 'candidate/typed-proposal.json'))

    def test_repeated_nested_shape_blocks_before_freeze_but_explicit_candidate_is_unchanged(self):
        bad, _ = self.proposals(); raw = canonical.dumps(bad).decode()
        result = formalize.run(self.pkg, self.events, agent=self.role([raw], []), max_attempts=1)
        self.assertEqual('BLOCKED', result.status)
        self.assertFalse((contract.challenge_dir(self.pkg) / 'challenge.json').exists())
        self.assertTrue(any(item.details.get('campaign_quantifier_shape') for item in result.diagnostics))
        draft, ledger, _ = formalize.require_interpretation(self.pkg)
        compiled = formal_frontend.compile_response(canonical.dumps(bad), formalize._records(draft, ledger, None), 'explicit.v0_2')
        directory = Path(self.tmp.name) / 'explicit-candidate'
        fsutil.atomic_write(directory / 'Contract.lean', compiled.source)
        fsutil.write_json(directory / 'formalization.json', compiled.formalization)
        self.assert_pass(formalize.run(self.pkg, self.events, candidate=directory))

    def test_pointwise_conjunction_equivalence_is_kernel_accepted_for_inhabited_input(self):
        source = b'''import Std
namespace QuantifierFixture
structure Input where
  value : Int
theorem pointwise_equivalent (P : Prop) (Q : Input -> Prop) :
    (P /\\ (forall x, Q x)) <-> (forall x, P /\\ Q x) := by
  constructor
  . intro h x
    exact And.intro h.1 (h.2 x)
  . intro h
    exact And.intro (h (Input.mk 0)).1 (fun x => (h x).2)
end QuantifierFixture
'''
        tc = leanbridge.resolve_toolchain(leanbridge.DEFAULT_TOOLCHAIN)
        compiled = leanbridge.compile_module(tc, source, Path(self.tmp.name) / 'equivalence')
        self.assertTrue(compiled.ok, compiled.errors)
        exported = leanbridge.run_kernel_tool(tc, compiled.olean, {'export': True, 'axioms': True})
        environment = contract.Env.from_export(exported, policy.get('strict'), 'quantifier-equivalence')
        self.assertEqual([], environment.diagnostics)
        self.assertIn('QuantifierFixture.pointwise_equivalent', environment.decls)
        self.assertNotIn('sorryAx', environment.axioms('QuantifierFixture.pointwise_equivalent'))


if __name__ == '__main__':
    unittest.main()
