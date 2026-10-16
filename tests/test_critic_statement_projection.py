"""Audit metadata projection retains the exact semantic inputs and bound full context."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_autonomous_probe_signal as fixture

from verislop import agent_memory, agents, autonomous, canonical, contract_refutation as cr, leanbridge
from verislop.errors import BlockedError, Diagnostic
from verislop.package import Package


class CriticStatementProjectionTests(unittest.TestCase):
    def setUp(self):
        fixture.AutonomousProbeSignalTests.setUp(self)
        self.ctx['analysis'].statements = copy.deepcopy(self.ctx['analysis'].statements)
        self.ctx['form'] = {'lean_toolchain': '  ' + leanbridge.DEFAULT_TOOLCHAIN + '\n'}
        for st in self.ctx['analysis'].statements.values():
            st['semantic_closure'] = {name: 'sha256:' + 'a' * 64 for name in st['semantic_closure']}
            st['semantic_closure_hash'] = canonical.digest_json({
                'toolchain': leanbridge.DEFAULT_TOOLCHAIN, 'declarations': st['semantic_closure']})

    def test_projection_changes_only_audit_maps_and_restores_full_analysis_after_resume(self):
        data = autonomous.packet(self.pkg, self.ctx)
        original = canonical.dumps(data)
        wire = autonomous.project_critic_prompt(self.pkg, data)
        self.assertEqual(original, canonical.dumps(data))
        self.assertEqual({k: v for k, v in data.items() if k != 'statements'},
                         {k: v for k, v in wire.items() if k not in {'statements', 'statement_analysis_ref'}})
        for oid, statement in data['statements'].items():
            self.assertEqual({k: v for k, v in statement.items() if k != 'semantic_closure'},
                             wire['statements'][oid])
        restored = autonomous.restore_statement_analysis(Package(self.pkg.root), wire['statement_analysis_ref'])
        self.assertEqual(data['statements'], restored)
        self.assertEqual(leanbridge.DEFAULT_TOOLCHAIN, wire['statement_analysis_ref']['lean_toolchain'])

    def test_missing_or_wrong_digest_and_changed_map_are_rejected_before_retention(self):
        for kind in ('missing', 'wrong', 'changed'):
            with self.subTest(kind=kind):
                data = autonomous.packet(self.pkg, self.ctx)
                data = copy.deepcopy(data)
                st = data['statements']['O1']
                if kind == 'missing':
                    del st['semantic_closure_hash']
                elif kind == 'wrong':
                    st['semantic_closure_hash'] = 'sha256:' + 'b' * 64
                else:
                    st['semantic_closure']['Fixture.shift'] = 'sha256:' + 'b' * 64
                with self.assertRaises(BlockedError):
                    autonomous.project_critic_prompt(self.pkg, data)
        self.assertIsNone(agent_memory.latest_snapshot(self.pkg, stage_prefix='critic/statement-analysis'))

    def test_missing_toolchain_keeps_full_legacy_packet_without_guessing_a_binding(self):
        data = autonomous.packet(self.pkg, self.ctx)
        data['formalization'] = {}
        self.assertIs(data, autonomous.project_critic_prompt(self.pkg, data))
        self.assertIn('semantic_closure', data['statements']['O1'])
        self.assertIsNone(agent_memory.latest_snapshot(self.pkg, stage_prefix='critic/statement-analysis'))

    def test_changed_reference_or_retained_full_blob_cannot_be_restored(self):
        wire = autonomous.project_critic_prompt(self.pkg, autonomous.packet(self.pkg, self.ctx))
        ref = wire['statement_analysis_ref']
        for change in ({'sha256': 'sha256:' + 'b' * 64}, {'lean_toolchain': 'wrong-pin'}):
            with self.subTest(change=change), self.assertRaises(BlockedError):
                autonomous.restore_statement_analysis(self.pkg, {**ref, **change})
        snapshot = canonical.load_file(self.pkg.root / ref['snapshot_ref']['path'])
        blob = self.pkg.root / snapshot['artifacts'][0]['blob_ref']['path']
        data = blob.read_bytes()
        blob.chmod(0o600)
        blob.write_bytes(data + b' ')
        with self.assertRaises(BlockedError):
            autonomous.restore_statement_analysis(Package(self.pkg.root), ref)

    def test_critic_sends_projected_wire_but_replays_full_authoritative_analysis(self):
        value = fixture.response([{'obligation_id': 'O1', 'inputs': [fixture.INPUT]}])
        captured = []
        def call(*args):
            captured.append(json.loads(args[3]))
            return SimpleNamespace(text=canonical.dumps(value).decode())
        analysis = self.ctx['analysis']
        def check(pkg, source, form, records, supplied, **kw):
            self.assertIs(analysis, supplied)
            self.assertIn('Fixture.shift', supplied.statements['O1']['semantic_closure'])
            return {'status': 'UNKNOWN', 'receipts': [], 'diagnostics': [],
                    'execution_observations': [{'obligation_id': 'O1', 'calls': [{'symbol': 'shift'}]}]}
        with patch.object(agents, '_broker', return_value=(SimpleNamespace(call=call), self.conf)):
            critic = autonomous.critic_agent('unused', self.pkg, self.events)
        with patch.object(cr, 'check', side_effect=check):
            result = critic(self.ctx)
        self.assertEqual('SEARCH_COMPLETED', result['status'])
        self.assertEqual(1, len(captured))
        self.assertNotIn('semantic_closure', captured[0]['statements']['O1'])
        self.assertIn('Fixture.shift', analysis.statements['O1']['semantic_closure'])
        self.assertEqual(analysis.statements, autonomous.restore_statement_analysis(
            self.pkg, captured[0]['statement_analysis_ref']))

    def test_proof_phase_signature_validation_keeps_full_closure(self):
        analysis = self.ctx['analysis']
        self.ctx.update(phase='prove', analysis=None, profile=analysis.profile, statements=analysis.statements,
                        diagnostics=[Diagnostic('CANDIDATE_BUILD_FAILURE', 'actual fixture error')])
        value = fixture.response([{'obligation_id': 'O1', 'inputs': [fixture.INPUT]}])
        value['corrections'] = [{'diagnostic_index': 0, 'artifact': 'proposal.lean', 'explanation': 'Repair this error.'}]
        call = lambda *args: SimpleNamespace(text=canonical.dumps(value).decode())
        validate = cr.validate_proposals
        def checked_validate(signatures, proposals):
            self.assertIn('Fixture.shift', signatures.statements['O1']['semantic_closure'])
            return validate(signatures, proposals)
        with patch.object(agents, '_broker', return_value=(SimpleNamespace(call=call), self.conf)):
            critic = autonomous.critic_agent('unused', self.pkg, self.events)
        with patch.object(cr, 'validate_proposals', side_effect=checked_validate) as checked:
            result = critic(self.ctx)
        self.assertEqual(1, checked.call_count)
        self.assertEqual('REPAIR', result['status'])


if __name__ == '__main__':
    unittest.main()
