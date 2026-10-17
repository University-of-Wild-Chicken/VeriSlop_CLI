"""Unrelated native proof-retention fixtures; no live model qualification."""
from __future__ import annotations

import base64
import contextlib
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import agents, agent_memory, canonical, contract, leanbridge, proof_fragments, proof_retention as R, prove
from verislop.errors import BlockedError, InfrastructureError
from verislop.events import EventSink
from verislop.package import Package
from verislop.providers.adapters import Completion
from verislop.providers.broker import Broker

POLICY = {"build_timeout_seconds": 30, "memory_mb": 2048, "require_network_isolation": True}
FROZEN = ('import Std\ndef retained_label : String := "é😀\u0085\u2028\u2029"\n'
          'theorem first : 1 = 1 := by sorry\n'
          'theorem second : True := by sorry\n'
          'theorem third : 3 = 3 := by sorry\n')
PROPOSAL = FROZEN.replace('1 = 1 := by sorry', '1 = 1 := by rfl').replace(
    'True := by sorry', 'True := by exact «missing\u2028identifier»').replace('3 = 3 := by sorry', '3 = 3 := by rfl')
MECHANICAL = PROPOSAL.replace('by exact «missing\u2028identifier»', 'by sorry')
CASCADE = ('import Lean\nimport Std\ntheorem retention_a : True := by sorry\n'
           'theorem retention_b : True := by sorry\ntheorem retention_c : True := by sorry\n')
CASCADE_PROPOSAL = CASCADE.replace('theorem retention_a : True := by sorry', '''theorem retention_a : True := by
  run_tac do
    Lean.addDecl (.thmDecl {
      name := `retention_a.helper
      levelParams := []
      type := Lean.mkConst ``True
      value := Lean.mkConst ``True.intro
    })
  exact missing_retention_witness''').replace('theorem retention_b : True := by sorry',
    'theorem retention_b : True := by\n  exact retention_a.helper').replace(
    'theorem retention_c : True := by sorry', 'theorem retention_c : True := by\n  trivial')


class RetentionNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tc = leanbridge.resolve_toolchain()
        cls.base = prove.evaluate(cls.tc, POLICY, FROZEN, retain_native=True)
        cls.failed = prove.evaluate(cls.tc, POLICY, PROPOSAL, retain_native=True)
        cls.promoted = prove.evaluate(cls.tc, POLICY, MECHANICAL, retain_native=True)
        assert cls.base['ok'] and not cls.failed['ok'] and cls.promoted['ok']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='verislop-retention-test-')
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / 'package')
        self.pkg.ensure('unrelated-retention')
        self.calls = []

    def search(self, frozen=FROZEN):
        return R.Search(self.pkg, {'kind': 'contract', 'frozen_sha256': canonical.digest(frozen.encode())},
                        frozen, self.tc.identity(), POLICY)

    def evaluate(self, source, timeout):
        self.calls.append(source)
        return prove.evaluate(self.tc, POLICY, source, retain_native=True, timeout_seconds=timeout)

    def attempt(self, search=None, **overrides):
        search = search or self.search()
        args = dict(baseline=FROZEN, baseline_result=self.base, proposal=PROPOSAL,
                    raw_response=json.dumps({'lean_source': PROPOSAL}, ensure_ascii=False), failed_result=self.failed,
                    selected=['first', 'second', 'third'], proposal_id=1, evaluate=self.evaluate)
        args.update(overrides)
        return search, search.attempt(**args)

    def test_independent_edits_exact_native_unicode_and_full_receipt_restoration(self):
        self.assertIn('missing\u2028identifier', self.failed['errors'][0])
        search, output = self.attempt()
        self.assertEqual(MECHANICAL, output[0])
        self.assertEqual(1, output[1]['sorries'])
        self.assertEqual([MECHANICAL], self.calls)
        receipt = search.last_receipt
        self.assertEqual('promoted', receipt['status'])
        self.assertEqual(['second'], [r['name'] for r in receipt['rounds'][0]['reverted']])
        restored = self.search()
        self.assertEqual(search.summary(), restored.summary())
        artifacts = agent_memory.restore(self.pkg, search.ref)
        self.assertEqual(PROPOSAL, artifacts['original-proposal.lean'].decode())
        self.assertEqual(self.failed, canonical.loads(artifacts['original-result.json']))
        self.assertFalse(canonical.loads(artifacts['original-result.json'])['ok'])
        self.assertIn('no proof', search.summary()['authority'])
        self.assertFalse(self.pkg.path('accepted').exists())

    def test_actual_cascade_requires_second_whole_module_native_recheck(self):
        baseline = prove.evaluate(self.tc, POLICY, CASCADE, retain_native=True)
        failed = prove.evaluate(self.tc, POLICY, CASCADE_PROPOSAL, retain_native=True)
        self.assertEqual(1, len(failed['errors']))
        search, output = self.attempt(self.search(CASCADE), baseline=CASCADE, baseline_result=baseline,
            proposal=CASCADE_PROPOSAL, failed_result=failed, selected=['retention_a', 'retention_b', 'retention_c'])
        self.assertIsNotNone(output)
        self.assertEqual(2, search.used)
        self.assertEqual(2, output[1]['sorries'])
        self.assertEqual([['retention_a'], ['retention_b']],
            [[r['name'] for r in row['reverted']] for row in search.last_receipt['rounds']])
        self.assertIn('retention_c : True := by\n  trivial', output[0])
        first = canonical.loads(agent_memory.restore(self.pkg, search.ref)['round-0-result.json'])
        self.assertFalse(first['ok'])
        self.assertIn('helper', first['errors'][0])
        self.assertEqual(search.summary(), self.search(CASCADE).summary())

    def test_genuine_three_stage_cascade_stops_at_two_rechecks(self):
        frozen = CASCADE + 'theorem retention_d : True := by sorry\n'
        source = CASCADE_PROPOSAL.replace('theorem retention_b : True := by\n  exact retention_a.helper',
            'theorem retention_b : True := by\n  run_tac do\n    Lean.addDecl (.thmDecl {\n'
            '      name := `retention_b.helper\n      levelParams := []\n'
            '      type := Lean.mkConst ``True\n      value := Lean.mkConst ``True.intro\n    })\n'
            '  exact retention_a.helper').replace('theorem retention_c : True := by\n  trivial',
            'theorem retention_c : True := by\n  exact retention_b.helper') + 'theorem retention_d : True := by trivial\n'
        baseline = prove.evaluate(self.tc, POLICY, frozen, retain_native=True)
        failed = prove.evaluate(self.tc, POLICY, source, retain_native=True)
        self.assertEqual(1, len(failed['errors']))
        search, output = self.attempt(self.search(frozen), baseline=frozen, baseline_result=baseline,
            proposal=source, failed_result=failed, selected=None)
        self.assertIsNone(output)
        self.assertEqual(2, len(self.calls))
        self.assertEqual(2, search.used)
        self.assertEqual('budget_exhausted', search.last_receipt['status'])
        result = canonical.loads(agent_memory.restore(self.pkg, search.ref)['round-1-result.json'])
        self.assertFalse(result['ok'])
        self.assertIn('helper', result['errors'][0])
        self.assertIsNone(self.search(frozen).promoted_source)

    def test_malformed_nested_observations_are_ineligible_not_host_crashes(self):
        for key in ('process', 'messages', 'toolchain'):
            for malformed in (None, [], 'wrong', True):
                failed = copy.deepcopy(self.failed)
                failed['native_observation'][key] = malformed
                with self.subTest(key=key, malformed=malformed), self.assertRaises(R.Ineligible):
                    R.native(PROPOSAL, failed, self.tc.identity(), POLICY)
        for key in ('input', 'requested_limits', 'stdout', 'stderr'):
            failed = copy.deepcopy(self.failed)
            failed['native_observation']['process'][key] = []
            with self.subTest(key=key), self.assertRaises(R.Ineligible):
                R.native(PROPOSAL, failed, self.tc.identity(), POLICY)

    def test_dependency_on_sorry_is_only_search_progress(self):
        for proposition in ('True', 'False'):
            with self.subTest(proposition=proposition):
                frozen = ('import Std\ntheorem pending : ' + proposition + ' := by sorry\n'
                    'theorem dependent : ' + proposition + ' := by sorry\n'
                    'theorem faulty : True := by sorry\ntheorem independent : True := by sorry\n')
                proposal = frozen.replace('theorem dependent : ' + proposition + ' := by sorry',
                    'theorem dependent : ' + proposition + ' := by exact pending').replace(
                    'theorem faulty : True := by sorry', 'theorem faulty : True := by exact missing_bad').replace(
                    'theorem independent : True := by sorry', 'theorem independent : True := by trivial')
                baseline = prove.evaluate(self.tc, POLICY, frozen, retain_native=True)
                failed = prove.evaluate(self.tc, POLICY, proposal, retain_native=True)
                search, output = self.attempt(self.search(frozen), baseline=frozen, baseline_result=baseline,
                    proposal=proposal, failed_result=failed, selected=None)
                self.assertEqual(['pending', 'faulty'], search.last_receipt['new_unresolved'])
                instrumented = prove.evaluate(self.tc, POLICY, output[0] + '#print axioms dependent\n', retain_native=True)
                self.assertTrue(any('depends on axioms: [sorryAx]' in m['data']
                    for m in instrumented['native_observation']['messages']))
                self.assertFalse(output[1]['complete'])

    def test_all_native_errors_reverted_and_no_progress_not_promoted(self):
        proposal = FROZEN.replace('by sorry', 'by exact missing_everywhere')
        failed = prove.evaluate(self.tc, POLICY, proposal, retain_native=True)
        self.assertEqual(3, len(failed['errors']))
        search, output = self.attempt(proposal=proposal, failed_result=failed)
        self.assertIsNone(output)
        self.assertEqual([FROZEN], self.calls)
        self.assertEqual('no_progress', search.last_receipt['status'])
        self.assertEqual(1, self.search().used)

    def test_changed_frozen_or_solved_bytes_never_dispatch_recheck(self):
        baseline = FROZEN.replace('1 = 1 := by sorry', '1 = 1 := by first | rfl | sorry')
        evaluated = prove.evaluate(self.tc, POLICY, baseline, retain_native=True)
        self.assertEqual(2, evaluated['sorries'])
        good_shape = baseline.replace('True := by sorry', 'True := by exact absent').replace('3 = 3 := by sorry', '3 = 3 := by rfl')
        changed = [good_shape.replace('String :=', 'String := "x" ++'),
                   good_shape.replace('import Std', 'import Lean'), good_shape + '\n',
                   good_shape.replace('first : 1 = 1', 'first : 2 = 2'),
                   good_shape.replace('by first | rfl | sorry', 'by rfl'),
                   good_shape + 'def added : Nat := 0\n']
        for serial, source in enumerate(changed, 1):
            search, output = self.attempt(baseline=baseline, baseline_result=evaluated, proposal=source,
                selected=['second', 'third'], proposal_id=serial)
            self.assertIsNone(output)
            self.assertEqual('ineligible', search.last_receipt['status'])
        self.assertEqual([], self.calls)

    def test_stale_malformed_incomplete_and_process_errors_are_ineligible(self):
        changes = [lambda r: r.pop('native_observation'),
            lambda r: r['native_observation'].update(source_sha256='changed'),
            lambda r: r['native_observation'].update(policy_sha256='changed'),
            lambda r: r['native_observation'].update(toolchain={}),
            lambda r: r['native_observation']['process'].update(timed_out=True),
            lambda r: r['native_observation']['process'].update(returncode=-9),
            lambda r: r['native_observation']['process']['stdout'].update(byte_count=True),
            lambda r: r['native_observation']['process']['stdout'].update(sha256='changed'),
            lambda r: r['native_observation'].update(messages=[]),
            lambda r: r['errors'].append('synthetic timeout'),
            lambda r: r.update(errors=[]), lambda r: r.update(sorries=True)]
        for serial, change in enumerate(changes, 1):
            failed = copy.deepcopy(self.failed)
            change(failed)
            search, output = self.attempt(failed_result=failed, proposal_id=serial)
            self.assertIsNone(output)
            self.assertEqual('ineligible', search.last_receipt['status'])
        self.assertEqual([], self.calls)

    def test_bound_but_outside_or_malformed_locations_never_guess(self):
        for serial, location in enumerate(({'line': True, 'column': 0}, {'line': 1, 'column': 0},
                {'line': 4, 'column': 0}, {'line': 999, 'column': 0}, {'line': 4, 'column': 999}), 1):
            failed = copy.deepcopy(self.failed)
            messages = failed['native_observation']['messages']
            for msg in messages:
                if msg['severity'] == 'error':
                    msg['pos'] = location
            raw = b'\n'.join(canonical.dumps(m) for m in messages) + b'\n'
            failed['native_observation']['process']['stdout'] = leanbridge._output_evidence(raw)
            failed['errors'] = [f"{m['pos']['line']}:{m['pos']['column']}: {m['data']}" for m in messages if m['severity'] == 'error']
            search, output = self.attempt(failed_result=failed, proposal_id=serial)
            self.assertIsNone(output)
        self.assertEqual([], self.calls)

    def test_information_trace_is_not_native_sorry_warning(self):
        source = 'import Std\ntheorem trace_only : True := by\n  trace "declaration uses `sorry`"\n  trivial\n'
        result = prove.evaluate(self.tc, POLICY, source, retain_native=True)
        self.assertTrue(result['complete'])
        self.assertEqual([], result['native_diagnostics']['sorry_positions'])
        self.assertEqual([], R.native(source, result, self.tc.identity(), POLICY)[1])

    def test_job_caps_survive_resume_and_proposal_reentry_is_rejected(self):
        all_bad = FROZEN.replace('by sorry', 'by exact missing_cap')
        failed = prove.evaluate(self.tc, POLICY, all_bad, retain_native=True)
        for serial in range(1, 6):
            search, output = self.attempt(self.search(), proposal=all_bad, failed_result=failed, proposal_id=serial)
            self.assertIsNone(output)
            self.assertEqual(min(serial, 4), search.used)
        self.assertEqual(4, len(self.calls))
        self.assertEqual('budget_exhausted', search.last_receipt['status'])
        with self.assertRaises(BlockedError):
            self.attempt(self.search(), proposal_id=5)

    def test_interrupted_dispatch_is_consumed_without_mechanical_success(self):
        with self.assertRaises(KeyboardInterrupt):
            self.attempt(evaluate=lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        restored = self.search()
        self.assertEqual(1, restored.used)
        self.assertEqual('infrastructure_failure', restored.last_receipt['status'])
        self.assertIsNone(restored.last_receipt['rounds'][0]['result'])
        self.assertEqual(1, self.search().used)
        search, output = self.attempt(self.search(), proposal_id=2)
        self.assertEqual(2, search.used)
        self.assertIsNotNone(output)

    def test_expired_deadline_dispatches_nothing(self):
        search, output = self.attempt(deadline=time.monotonic() - 1)
        self.assertIsNone(output)
        self.assertEqual(0, search.used)
        self.assertEqual('budget_exhausted', search.last_receipt['status'])
        self.assertEqual([], self.calls)

    def test_deadline_expiring_during_checkpoint_never_starts_native_build(self):
        search = self.search()
        save = search._save
        def delayed_save(receipt, artifacts):
            save(receipt, artifacts)
            time.sleep(0.02)
        with patch.object(search, '_save', side_effect=delayed_save), patch.object(R.time, 'monotonic', side_effect=[1, 3]):
            search, result = self.attempt(search, deadline=2)
        self.assertIsNone(result)
        self.assertEqual([], self.calls)
        self.assertEqual(1, self.search().used)
        self.assertEqual('budget_exhausted', search.last_receipt['status'])
        self.assertIsNone(search.last_receipt['rounds'][0]['result'])

    def test_committed_history_cannot_be_abandoned_to_refund_budget(self):
        search, _ = self.attempt()
        artifacts = agent_memory.restore(self.pkg, search.ref)
        state = canonical.loads(artifacts.pop('payload.json'))
        state.update(used=0, previous=None)
        state['receipt'].update(status='ineligible', reason='counter reset attempt', rounds=[], proposal_id=2)
        agent_memory.capture_context(self.pkg, search.stage, state, extra_artifacts=artifacts)
        with self.assertRaisesRegex(BlockedError, 'journal predecessors'):
            self.search()

    def test_pre_dispatch_infrastructure_failure_restores_without_corruption(self):
        with patch.object(proof_fragments, 'validate_focused_candidate', side_effect=InfrastructureError('helper unavailable')):
            with self.assertRaises(InfrastructureError):
                self.attempt()
        restored = self.search()
        self.assertEqual(0, restored.used)
        self.assertEqual('infrastructure_failure', restored.last_receipt['status'])

    def test_bound_receipt_tampering_cannot_promote_or_refund(self):
        search, _ = self.attempt()
        original = agent_memory.restore(self.pkg, search.ref)
        state = canonical.loads(original['payload.json'])
        changes = [lambda s: s.update(used=0),
            lambda s: s['receipt'].update(selected=['third']),
            lambda s: s['receipt']['rounds'][0]['reverted'][0].update(candidate_span=[0, 1]),
            lambda s: s['receipt']['rounds'][0].update(ordinal=4),
            lambda s: s['receipt'].update(new_unresolved=[]),
            lambda s: s['receipt']['original_result'].update(sha256='changed')]
        for change in changes:
            changed = copy.deepcopy(state)
            change(changed)
            payload = {**original, 'payload.json': canonical.dumps(changed)}
            # Coherently replaced payload still faces semantic receipt checks;
            # ordinary blob tampering is already rejected by agent_memory.
            real_restore = agent_memory.restore
            with patch.object(agent_memory, 'restore', side_effect=lambda pkg, ref: payload if ref == search.ref else real_restore(pkg, ref)):
                with self.assertRaises(BlockedError):
                    self.search()


class RetentionDispatchTests(unittest.TestCase):
    def test_actual_recorded_call_keeps_raw_rejection_separate_and_resume_rechecks_baseline(self):
        self._dispatch_trial()

    def test_committed_promotion_survives_crash_before_best_checkpoint(self):
        self._dispatch_trial(interrupt=True)

    def test_opt_in_resumes_legacy_feedback_without_inventing_native_telemetry(self):
        with tempfile.TemporaryDirectory(prefix='verislop-retention-legacy-') as tmp:
            root = Path(tmp); pkg = Package(root / 'package'); pkg.ensure('retention-legacy')
            events = EventSink(pkg.run_id, quiet=True); self.addCleanup(events.close)
            source = FROZEN + contract.REGISTRY_BEGIN + '\n' + contract.REGISTRY_END + '\n'
            challenge = root / 'challenge'; challenge.mkdir()
            (challenge / 'Contract.lean').write_text(source)
            (challenge / 'lean-toolchain').write_text(leanbridge.DEFAULT_TOOLCHAIN + '\n')
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(contract, 'load_frozen', return_value=({}, [])))
                stack.enter_context(patch.object(contract, 'challenge_dir', return_value=challenge))
                stack.enter_context(patch.object(contract, 'frozen_json', side_effect=lambda p, n: {
                    'statements.json': {'statements': {}}, 'profile.json': {}, 'policy.json': POLICY, 'formalization.json': {}}[n]))
                prove.run(pkg, events, candidate=challenge / 'Contract.lean', portfolio=False, max_attempts=0, budget_seconds=0)
                for _ in range(2):
                    result = prove.run(pkg, events, portfolio=False, max_attempts=0, budget_seconds=0, retain_proof_bodies=True)
                    self.assertEqual('BLOCKED', result.status)
                    self.assertEqual(0, result.summary['proof_retention']['rechecks_used'])
                    restored = agent_memory.restore(pkg, agent_memory.latest_snapshot(pkg, stage_prefix='prove/attempt'))
                    saved = canonical.loads(restored['payload.json'])
                    self.assertNotIn('latest-native-diagnostics.json', restored)
                    self.assertNotIn('latest-raw-response.txt', restored)
                    self.assertNotIn('native_result_ref', saved['result'])
                    self.assertIsNone(saved['latest_raw_response'])
                    self.assertEqual(source, saved['candidate'])

    def _dispatch_trial(self, *, interrupt=False):
        with tempfile.TemporaryDirectory(prefix='verislop-retention-dispatch-') as tmp:
            root = Path(tmp); pkg = Package(root / 'package'); pkg.ensure('retention-dispatch')
            events = EventSink(pkg.run_id, quiet=True)
            self.addCleanup(events.close)
            frozen = FROZEN + contract.REGISTRY_BEGIN + '\n' + contract.REGISTRY_END + '\n'
            failed = PROPOSAL + contract.REGISTRY_BEGIN + '\n' + contract.REGISTRY_END + '\n'
            mechanical = MECHANICAL + contract.REGISTRY_BEGIN + '\n' + contract.REGISTRY_END + '\n'
            challenge = root / 'challenge'; challenge.mkdir()
            (challenge / 'Contract.lean').write_text(frozen)
            (challenge / 'lean-toolchain').write_text(leanbridge.DEFAULT_TOOLCHAIN + '\n')
            config = json.loads((Path(__file__).resolve().parents[1] / 'examples/ollama-review-config.json').read_text())
            for agent in config['agents'].values():
                agent['model_ref'] = 'mock:retention'
            config['agents'][config['roles']['prover']]['proof_retention'] = True
            cfg = root / 'config.json'; cfg.write_text(json.dumps(config))
            calls, raw = [], json.dumps({'lean_source': failed}, ensure_ascii=False)
            def complete(broker, agent, instance, system, user, purpose):
                calls.append(user)
                # The second provider response leaves only the same pending hole;
                # the first failure remains observable in its dispatch context.
                response = raw if len(calls) == 1 else json.dumps({'lean_source': mechanical})
                return Completion(response, broker.model_for(agent), broker.model_for(agent), None, 11, 7)
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(contract, 'load_frozen', return_value=({}, [])))
                stack.enter_context(patch.object(contract, 'challenge_dir', return_value=challenge))
                stack.enter_context(patch.object(contract, 'frozen_json', side_effect=lambda p, n: {
                    'statements.json': {'statements': {}}, 'profile.json': {}, 'policy.json': POLICY, 'formalization.json': {}}[n]))
                stack.enter_context(patch.object(Broker, 'call', new=complete))
                role = agents.prover_agent(cfg, pkg, events)
                if interrupt:
                    attempt = R.Search.attempt
                    def crash_after_promotion(search, **kwargs):
                        result = attempt(search, **kwargs)
                        self.assertIsNotNone(result)
                        raise KeyboardInterrupt()
                    with patch.object(R.Search, 'attempt', new=crash_after_promotion):
                        with self.assertRaises(KeyboardInterrupt):
                            prove.run(pkg, events, portfolio=False, budget_seconds=0, max_attempts=1, agent=role)
                else:
                    outcome = prove.run(pkg, events, portfolio=False, budget_seconds=0, max_attempts=1, agent=role)
                    self.assertEqual('BLOCKED', outcome.status)
                    self.assertEqual(1, outcome.summary['proof_retention']['rechecks_used'])
                latest = agent_memory.restore(pkg, agent_memory.latest_snapshot(pkg, stage_prefix='prove/attempt'))
                saved = canonical.loads(latest['payload.json'])
                self.assertEqual(frozen if interrupt else mechanical, saved['best'])
                self.assertEqual(failed, saved['candidate'])
                self.assertEqual(raw, saved['latest_raw_response'])
                self.assertFalse(saved['result']['ok'])
                original_errors = saved['result']['errors']
                # A fresh prove invocation rechecks B; it does not re-evaluate or
                # relabel the previous raw failed provider completion.
                with patch.object(prove, 'evaluate', wraps=prove.evaluate) as native:
                    role = agents.prover_agent(cfg, pkg, events)
                    prove.run(pkg, events, portfolio=False, budget_seconds=0, max_attempts=1, agent=role)
                    self.assertEqual(frozen if interrupt else mechanical, native.call_args_list[0].args[2])
                    if interrupt:
                        self.assertEqual(mechanical, native.call_args_list[1].args[2])
                projection = agent_memory.restore(pkg, agent_memory.latest_snapshot(pkg, stage_prefix='proof-context/projection'))
                from verislop import proof_focus
                restored = proof_focus.restore_context(canonical.loads(projection['payload.json']))
                self.assertEqual(mechanical, restored['current_file'])
                self.assertEqual(failed, restored['previous_attempt']['lean_source'])
                self.assertEqual(raw, restored['previous_attempt']['raw_response'])
                self.assertEqual(original_errors, restored['errors'])
                self.assertNotIn('content_b64', calls[1])
                self.assertNotIn('requested_argv', calls[1])
                self.assertIn('native_result_ref', restored['previous_attempt']['result'])
                retained_native = canonical.loads(latest['latest-native-diagnostics.json'])
                self.assertEqual(original_errors, retained_native['errors'])
                self.assertEqual('verislop.proof-retention-native/0.1', retained_native['native_observation']['format'])
                self.assertEqual('promoted', restored['mechanical_retention']['last']['status'])
                self.assertIn('MECHANICAL PROOF RETENTION', calls[1])
                self.assertEqual(frozen, (challenge / 'Contract.lean').read_text())
                self.assertFalse(pkg.path('accepted').exists())


class RetentionPromptTests(unittest.TestCase):
    def test_per_agent_option_is_boolean_and_default_disabled(self):
        from verislop import schemas
        from verislop.providers import config as provider_config
        config = json.loads((Path(__file__).resolve().parents[1] / 'examples/ollama-review-config.json').read_text())
        name = config['roles']['prover']
        for value in (False, True):
            config['agents'][name]['proof_retention'] = value
            self.assertEqual([], schemas.validate('review-config', config))
        for value in (None, 0, 1, 'true', [], {}):
            config['agents'][name]['proof_retention'] = value
            self.assertTrue(schemas.validate('review-config', config))
            resolved = provider_config.resolve(config, {})
            self.assertTrue(any('proof_retention must be a boolean' in d.message for d in resolved.diagnostics))

    def test_raw_source_sharing_follows_actual_rendered_order(self):
        from verislop import proof_focus
        raw = '{"lean_source":"raw rejected source"}'
        data = {'current_file': 'baseline', 'previous_attempt': {'lean_source': 'rejected', 'raw_response': raw},
                'errors': ['exact native error'], 'critique': None, 'focus': None,
                'retained_rejection': {'candidate': 'rejected', 'raw_response': raw}, 'mechanical_retention': {}}
        envelope = proof_focus.project_context(data)
        self.assertEqual(raw, envelope['context']['previous_attempt']['raw_response'])
        self.assertEqual(['previous_attempt', 'raw_response'],
                         envelope['context']['retained_rejection']['raw_response']['exact_content_ref'])
        rendered = proof_focus.render_context(envelope)
        self.assertLess(rendered.index('PREVIOUS PROOF ATTEMPT'), rendered.index('EXACT RETAINED PROOF REJECTION'))
        self.assertEqual(data, proof_focus.restore_context(envelope))


if __name__ == '__main__':
    unittest.main()
