"""Exact metadata rules, authenticated boundary and recorded mock dispatch."""
from __future__ import annotations

import contextlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import agents, agent_memory, canonical, export, fsutil, relation_authoring as R
from verislop.bridges import vscore3_checker as checker
from verislop.errors import BlockedError, Diagnostic, UsageError, blocked
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore3_source as source, vscore3_target as target


def profile(table=None):
    table = table or {'shift': 'Fixture.shift'}
    return {'profile_id': 'relation-fixture', 'dsl': 'verislop.contract-dsl/0.2', 'enums': {}, 'records': {},
            'predicates': {}, 'symbols': {sid: {'lean_decl': decl, 'args': ['Int'], 'result': 'Int',
                'level_params': [], 'decl_hash': 'sha256:' + 'b' * 64} for sid, decl in table.items()}}


def relation(bindings=None):
    return {'schema_version': '0.3', 'format': 'verislop.vscore-relation/0.3',
            'template': 'vscore.reference_refinement/0.3', 'source_slot': 'vscore-source',
            'proof_slot': 'vscore-proof', 'bindings': bindings or [{'symbol': 'shift', 'entry': 'shift'}]}


def metadata_fixture(pkg, accepted=None):
    """Only tests mock verified_ir; production never accepts these synthetic certs."""
    accepted = accepted or profile()
    root = 'sha256:' + 'a' * 64
    raw_profile = canonical.dumps(accepted)
    profile_path = 'fixture/accepted-profile.json'
    cert = {'artifact_kind': 'acceptance_certificate', 'gate': 'accepted_and_proved',
            'contract_input_root': root, 'toolchain': {'pin': 'fixture-toolchain'},
            'artifacts': {'profile': {'path': profile_path, 'sha256': canonical.digest(raw_profile)}}}
    cert_bytes = canonical.dumps(cert)
    cert_path = 'fixture/' + canonical.sha256_hex(cert_bytes) + '.json'
    ir = {'artifact_kind': 'accepted_semantic_ir', 'contract_input_root': root,
          'lean_toolchain': 'fixture-toolchain', 'acceptance_certificate_ref': cert_path}
    ir_bytes = canonical.dumps(ir)
    fsutil.write_once(pkg.root / profile_path, raw_profile)
    fsutil.write_once(pkg.root / cert_path, cert_bytes)
    fsutil.write_once(pkg.path('accepted_ir'), ir_bytes)
    fixed = {'accepted_ir': ir, 'accepted_profile': accepted, 'lean_toolchain': 'fixture-toolchain',
             'accepted_reference': {'lean_source': '-- unchanged reference'}, 'accepted_packages': {},
             'required_obligations': [], 'parameters': {'backend': 'verislop.backend.vscore/0.3',
                'backend_version': '0.3', 'target': 'vscore', 'tier': 2, 'endpoint': 'restricted_source'}}
    return fixed, (ir, canonical.digest(ir_bytes), cert, [])


class RelationMetadataTests(unittest.TestCase):
    def normalized(self, rel=None, prof=None):
        return R._normalize(canonical.dumps(rel or relation()), prof or profile())

    def test_identity_unique_alias_and_same_id_dual_match(self):
        for prof, name, expected_modes in ((profile(), 'shift', ['profile_id']),
                (profile(), 'Fixture.shift', ['lean_decl']), (profile({'shift': 'shift'}), 'shift', ['profile_id', 'lean_decl'])):
            raw = relation([{'symbol': name, 'entry': 'shift'}])
            result, rows, errors = self.normalized(raw, prof)
            self.assertEqual([], errors)
            self.assertEqual(canonical.dumps(relation()), result)
            self.assertEqual(expected_modes, rows[0]['candidates'][0]['match_modes'])
            self.assertEqual(result, R._normalize(result, prof)[0])
            self.assertEqual(name, raw['bindings'][0]['symbol'])

    def test_alias_resolution_resorts_only_symbols_and_keeps_entry_pairing(self):
        prof = profile({'z': 'A.fn', 'a': 'Z.fn'})
        raw = relation([{'symbol': 'A.fn', 'entry': 'first'}, {'symbol': 'Z.fn', 'entry': 'second'}])
        result, rows, errors = self.normalized(raw, prof)
        self.assertEqual([], errors)
        self.assertEqual([{'symbol': 'a', 'entry': 'second'}, {'symbol': 'z', 'entry': 'first'}], canonical.loads(result)['bindings'])
        self.assertEqual(['A.fn', 'Z.fn'], [r['submitted_symbol'] for r in rows])
        for key in set(raw) - {'bindings'}:
            self.assertEqual(raw[key], canonical.loads(result)[key])

    def test_unknown_and_near_match_spellings_do_not_infer_aliases(self):
        prof = profile({'shift': 'Fixture.café'})
        for name in ('unknown', ' shift', 'shift ', 'SHIFT', 'shift\n', 'café', 'Fixture.cafe\u0301',
                     'Fixture.cafÉ', 'Other.shift', 'Fixture.Packet', 'Fixture.Packet.field', 'Fixture.contract', 'Fixture.valid'):
            result, _, errors = self.normalized(relation([{'symbol': name, 'entry': 'shift'}]), prof)
            self.assertIsNone(result)
            self.assertEqual('unknown_symbol', errors[0].details['reason'])
            self.assertEqual([], errors[0].details['candidates'])

    def test_duplicate_alias_and_direct_id_conflicts_reject(self):
        cases = [(profile({'left': 'Shared.fn', 'right': 'Shared.fn'}), 'Shared.fn', 'ambiguous_symbol'),
                 (profile({'left': 'Other.fn', 'right': 'left'}), 'left', 'ambiguous_symbol'),
                 (profile({'S': 'q', 'T': 'S'}), 'q', 'ambiguous_canonical_id')]
        for prof, name, reason in cases:
            result, rows, errors = self.normalized(relation([{'symbol': name, 'entry': 'go'}]), prof)
            self.assertIsNone(result)
            self.assertEqual(reason, errors[0].details['reason'])
            self.assertIsNone(rows[0]['selected_id'])

    def test_two_raw_spellings_cannot_merge_after_mapping(self):
        raw = relation([{'symbol': 'Fixture.shift', 'entry': 'first'}, {'symbol': 'shift', 'entry': 'second'}])
        result, rows, errors = self.normalized(raw)
        self.assertIsNone(result)
        self.assertEqual('normalization_collision', errors[0].details['reason'])
        self.assertEqual(['shift', 'shift'], [row['selected_id'] for row in rows])

    def test_descriptor_shape_order_slots_and_unique_entries_stay_strict(self):
        cases = []
        for key, value in (('schema_version', '0.1'), ('source_slot', 'source'), ('proof_slot', 'Proof.lean'),
                           ('bindings', []), ('bindings', [{'symbol': 1, 'entry': 'a'}])):
            cases.append({**relation(), key: value})
        cases += [{**relation(), 'extra': True}, relation([{'symbol': 'z', 'entry': 'a'}, {'symbol': 'a', 'entry': 'b'}]),
                  relation([{'symbol': 'a', 'entry': 'same'}, {'symbol': 'z', 'entry': 'same'}])]
        for raw in cases:
            result, _, errors = self.normalized(raw)
            self.assertIsNone(result)
            self.assertEqual('invalid_descriptor', errors[0].details['reason'])

    def test_missing_or_malformed_metadata_and_real_polymorphism_distinct(self):
        for key, value in (('lean_decl', None), ('args', 'Int'), ('level_params', None), ('decl_hash', 'unknown')):
            prof = profile(); prof['symbols']['shift'][key] = value
            self.assertEqual('malformed_accepted_metadata', self.normalized(prof=prof)[2][0].details['reason'])
        prof = profile(); del prof['symbols']['shift']['lean_decl']
        self.assertEqual('malformed_accepted_metadata', self.normalized(prof=prof)[2][0].details['reason'])
        prof = profile(); prof['symbols']['shift']['level_params'] = ['u']
        self.assertEqual('unsupported_polymorphism', self.normalized(prof=prof)[2][0].details['reason'])


class RelationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='verislop-relation-authoring-')
        self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / 'package'); self.pkg.ensure('relation-fixture')
        self.fixed, verified = metadata_fixture(self.pkg)
        self.verified = patch.object(export, 'verified_ir', return_value=verified)
        self.verified.start(); self.addCleanup(self.verified.stop)
        self.authority = R.prepare(self.pkg, self.fixed)
        self.stage = self.pkg.root / 'agents/vscore-attempts/source-1'
        self.raw = canonical.dumps(relation([{'symbol': 'Fixture.shift', 'entry': 'shift'}]))
        self.response = ('  {"relation": ' + self.raw.decode() + ', "program": {}}  \n').encode()

    def run_normalization(self):
        return R.normalize_attempt(self.pkg, self.stage, self.authority, self.response, self.raw)

    def document(self):
        return canonical.load_file(self.stage / 'relation-normalization.json')

    def test_exact_authority_response_raw_normalized_and_reentry(self):
        result = self.run_normalization()
        self.assertEqual(canonical.dumps(relation()), result)
        self.assertEqual(self.response, (self.stage / 'response.txt').read_bytes())
        self.assertEqual(self.raw, (self.stage / 'relation.raw.json').read_bytes())
        document = self.document()
        receipt, replayed = R.restore(self.pkg, document, expected=self.authority)
        self.assertEqual(result, replayed)
        self.assertEqual('normalized', receipt['outcome'])
        self.assertIn('no proof', receipt['authority'])
        count = len(list((self.pkg.root / 'agents/memory/snapshots').glob('*.json')))
        self.assertEqual(result, self.run_normalization())
        self.assertEqual(count, len(list((self.pkg.root / 'agents/memory/snapshots').glob('*.json'))))

    def test_missing_normalized_publication_can_finish_exactly_after_receipt_commit(self):
        normalized = self.run_normalization()
        (self.stage / 'relation.json').unlink()
        self.assertEqual(normalized, self.run_normalization())
        self.assertEqual(normalized, (self.stage / 'relation.json').read_bytes())

    def test_mapping_failure_retains_full_raw_and_reason_without_normalized_output(self):
        self.raw = canonical.dumps(relation([{'symbol': 'unknown', 'entry': 'shift'}]))
        self.response = canonical.dumps({'program': {}, 'relation': canonical.loads(self.raw)})
        with self.assertRaises(R.NormalizationError) as caught:
            self.run_normalization()
        self.assertEqual('unknown_symbol', caught.exception.diagnostics[0].details['reason'])
        self.assertFalse((self.stage / 'relation.json').exists())
        receipt, normalized = R.restore(self.pkg, self.document())
        self.assertIsNone(normalized)
        self.assertEqual('rejected', receipt['outcome'])
        self.assertEqual(self.raw, (self.stage / 'relation.raw.json').read_bytes())
        with self.assertRaises(R.NormalizationError):
            self.run_normalization()

    def test_unaccepted_or_fixed_context_supplied_profile_never_authorizes_mapping(self):
        changed = copy.deepcopy(self.fixed)
        changed['accepted_profile']['symbols']['shift']['lean_decl'] = 'Model.supplied'
        with self.assertRaises(BlockedError):
            R.prepare(self.pkg, changed)
        with patch.object(export, 'verified_ir', return_value=(None, None, None, [Diagnostic('VERIFIER_NOT_RUN', 'unaccepted')])):
            with self.assertRaises(BlockedError):
                R.prepare(self.pkg, self.fixed)
        changed = copy.deepcopy(self.fixed); changed['accepted_ir']['contract_input_root'] = 'changed'
        with self.assertRaises(BlockedError):
            R.prepare(self.pkg, changed)

    def test_profile_byte_mutation_and_in_memory_authority_mutation_fail_closed(self):
        self.authority.profile['symbols']['shift']['lean_decl'] = 'Changed'
        with self.assertRaises(BlockedError):
            self.run_normalization()
        path = self.pkg.root / self.authority.binding['profile']['path']
        path.chmod(0o600); path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(BlockedError):
            R.prepare(self.pkg, self.fixed)

    def test_stale_ir_or_certificate_bytes_cannot_reuse_authority(self):
        for key in ('ir', 'certificate'):
            path = self.pkg.root / self.authority.binding[key]['path']
            original = path.read_bytes()
            path.chmod(0o600); path.write_bytes(original + b' ')
            try:
                with self.subTest(key=key), self.assertRaises(BlockedError):
                    self.run_normalization()
                self.assertFalse((self.stage / 'relation.json').exists())
            finally:
                path.write_bytes(original); path.chmod(0o444)

    def test_raw_relation_must_be_the_decoded_exact_provider_relation(self):
        self.raw = canonical.dumps(relation())
        with self.assertRaises(BlockedError):
            self.run_normalization()
        self.assertFalse((self.stage / 'relation.json').exists())

    def test_public_raw_and_normalized_corruption_reject(self):
        self.run_normalization()
        for name in ('response.txt', 'relation.raw.json', 'relation.json'):
            path = self.stage / name
            original = path.read_bytes()
            path.chmod(0o600); path.write_bytes(original + b' ')
            with self.subTest(name=name), self.assertRaises(BlockedError):
                R.restore(self.pkg, self.document())
            path.write_bytes(original); path.chmod(0o444)

    def test_coherent_receipt_or_output_tampering_cannot_change_mapping(self):
        self.run_normalization()
        document = self.document()
        original = agent_memory.restore(self.pkg, document['snapshot_ref'])
        cases = []
        changed = copy.deepcopy(document); changed['receipt']['rows'][0]['selected_id'] = 'wrong'; cases.append(changed)
        changed = copy.deepcopy(document); changed['receipt']['accepted_binding']['contract_input_root'] = 'wrong'; cases.append(changed)
        changed = copy.deepcopy(document); changed['receipt']['normalizer']['format'] = 'future'; cases.append(changed)
        changed = copy.deepcopy(document); changed['receipt']['normalized_relation']['sha256'] = 'wrong'; cases.append(changed)
        for changed in cases:
            artifacts = {**original, 'receipt.json': canonical.dumps(changed['receipt'])}
            snapshot = agent_memory.checkpoint(self.pkg, 'test/coherent-tamper', artifacts)
            changed['snapshot_ref'] = snapshot['snapshot_ref']
            with self.assertRaises(BlockedError):
                R.restore(self.pkg, changed)
        for name in ('relation.raw.json', 'relation.json', 'receipt.json'):
            artifacts = {k: v for k, v in original.items() if k != name}
            changed = copy.deepcopy(document)
            changed['snapshot_ref'] = agent_memory.checkpoint(self.pkg, 'test/missing-artifact', artifacts)['snapshot_ref']
            with self.assertRaises(BlockedError):
                R.restore(self.pkg, changed)

    def test_persistence_failure_does_not_publish_normalized_relation(self):
        with patch.object(agent_memory, 'checkpoint', side_effect=blocked('BUDGET_EXHAUSTED', 'fixture memory bound')):
            with self.assertRaises(BlockedError):
                self.run_normalization()
        self.assertTrue((self.stage / 'response.txt').exists())
        self.assertTrue((self.stage / 'relation.raw.json').exists())
        self.assertFalse((self.stage / 'relation.json').exists())
        self.assertFalse((self.stage / 'relation-normalization.json').exists())


class RelationDispatchTests(unittest.TestCase):
    def test_raw_retry_and_canonical_surface_parity_preserve_proof_bytes(self):
        for mode in ('canonical_json', 'surface'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='verislop-relation-dispatch-') as tmp:
                pkg = Package(Path(tmp) / 'package'); pkg.ensure('relation-dispatch')
                fixed, verified = metadata_fixture(pkg)
                events = EventSink(pkg.run_id, quiet=True)
                surface = 'program "vscore/0.3" profile "data-pipeline/0.3"; entry shift(x:Int)->Int{x+int(2)}'
                program = source.compile_surface(surface)
                proof = 'import VeriSlopBridgeGoal\r\n-- exact submitted proof é😀\r\n'
                base = {'program_source': surface} if mode == 'surface' else {'program': canonical.loads(program)}
                raw_bad = json.dumps({**base, 'relation': relation([{'symbol': 'unknown', 'entry': 'shift'}]), 'proof_source': proof}, ensure_ascii=False)
                raw_good = json.dumps({**base, 'relation': relation([{'symbol': 'Fixture.shift', 'entry': 'shift'}]), 'proof_source': proof}, ensure_ascii=False)
                responses = iter([raw_bad, raw_good]); calls = []; previews = []
                def completion(*args):
                    calls.append((broker, pkg, *args)); return SimpleNamespace(text=next(responses))
                broker = SimpleNamespace(call=completion)
                def preview(_pkg, got_source, got_relation, proof=None, **kwargs):
                    previews.append((got_source, got_relation, proof))
                    self.assertEqual(program, got_source)
                    self.assertEqual(canonical.dumps(relation()), got_relation)
                    return SimpleNamespace(text='unchanged goal'), None, {'proposition_hash': 'sha256:' + 'e'*64, 'model': b'{}', 'profile': b'{}'}
                conf = {'roles': {'implementer': 'author'}, 'agents': {'author': {'vscore_authoring_format': mode}}}
                try:
                    with patch.object(export, 'verified_ir', return_value=verified), \
                         patch.object(agents, '_vscore_context', return_value=fixed), \
                         patch('verislop.surface_context.project_fixed_context', return_value=fixed), \
                         patch.object(checker, 'preview', side_effect=preview):
                        files, _ = agents._vscore_implementation(broker, conf, pkg, events, {'parameters': fixed['parameters']}, 2, 0)
                    self.assertEqual(2, len(calls)); self.assertEqual(2, len(previews))
                    inputs = agent_memory.snapshot_refs(pkg, stage="agent/generate/input")
                    outputs = agent_memory.snapshot_refs(pkg, stage="agent/generate/response")
                    self.assertEqual(2, len(inputs)); self.assertEqual(2, len(outputs))
                    for index in range(2):
                        saved_input = agent_memory.restore(pkg, inputs[index])
                        self.assertEqual(calls[index][4].encode(), saved_input['system.txt'])
                        self.assertEqual(calls[index][5].encode(), saved_input['user.txt'])
                        self.assertEqual([raw_bad, raw_good][index].encode(),
                                         agent_memory.restore(pkg, outputs[index])['response.txt'])
                    self.assertEqual(proof.encode(), previews[1][2])
                    self.assertEqual(proof.encode(), files['Proof.lean'])
                    from verislop import exact_context
                    retry = exact_context.restore_prompt(calls[1][5])
                    self.assertEqual(raw_bad, retry['previous_response'])
                    self.assertEqual('raw_authoring_relation', retry['previous_diagnostic_record']['relation_input_kind'])
                    self.assertEqual('unknown_symbol', retry['previous_diagnostic_record']['diagnostics'][0]['details']['reason'])
                    first = pkg.root / 'agents/vscore-attempts/source-1'
                    self.assertEqual(raw_bad.encode(), (first/'response.txt').read_bytes())
                    self.assertEqual(proof.encode(), (first/'proofs/initial.lean').read_bytes())
                    self.assertFalse((first/'relation.json').exists())
                    self.assertIn('existing accepted_profile.symbols', calls[0][4])
                    self.assertEqual(canonical.dumps(relation()), files['relation.json'])
                finally:
                    events.close()

    def test_real_recording_prover_receives_only_normalized_relation_and_hash(self):
        with tempfile.TemporaryDirectory(prefix='verislop-relation-proof-dispatch-') as tmp:
            pkg = Package(Path(tmp) / 'package'); pkg.ensure('proof-dispatch')
            fixed, verified = metadata_fixture(pkg); events = EventSink(pkg.run_id, quiet=True)
            self.addCleanup(events.close)
            program = source.compile_surface('program "vscore/0.3" profile "data-pipeline/0.3"; entry shift(x:Int)->Int{x+int(2)}')
            raw_relation = relation([{'symbol': 'Fixture.shift', 'entry': 'shift'}])
            response = json.dumps({'program': canonical.loads(program), 'relation': raw_relation})
            proof = 'import VeriSlopBridgeGoal\n-- exact unrelated mock response\n'
            responses = iter([response, proof]); calls = []; previews = []
            def completion(*args):
                calls.append(args); return SimpleNamespace(text=next(responses))
            broker = SimpleNamespace(call=completion)
            def preview(_pkg, src, rel, proof=None, **kwargs):
                previews.append((src, rel, proof))
                return SimpleNamespace(text='unchanged unrelated fixture goal'), None, {'proposition_hash': 'sha256:' + 'e'*64, 'model': b'{}', 'profile': b'{}'}
            conf = {'roles': {'implementer': 'author', 'prover': 'prover'}, 'agents': {}}
            with patch.object(export, 'verified_ir', return_value=verified), \
                 patch.object(agents, '_vscore_context', return_value=fixed), \
                 patch.object(checker, 'preview', side_effect=preview):
                files, _ = agents._vscore_implementation(broker, conf, pkg, events, {'parameters': fixed['parameters']}, 1, 1)
            self.assertEqual(['generate', 'prove-vscore'], [call[4] for call in calls])
            proof_data = json.JSONDecoder().raw_decode(calls[1][3].split('FIXED VSCORE PROOF CONTEXT (data):\n', 1)[1])[0]
            expected = canonical.dumps(relation())
            self.assertEqual(relation(), proof_data['relation'])
            self.assertEqual(canonical.digest(expected), proof_data['relation_hash'])
            self.assertEqual(fixed['accepted_profile'], proof_data['accepted_profile'])
            self.assertEqual(fixed['accepted_reference'], proof_data['accepted_reference'])
            self.assertTrue(all(src == program and rel == expected for src, rel, _ in previews))
            self.assertEqual(proof.encode(), files['Proof.lean'])
            saved = agent_memory.latest_snapshot(pkg, stage_prefix='agent/prove-vscore/input')
            self.assertEqual(calls[1][3].encode(), agent_memory.restore(pkg, saved)['user.txt'])
            stage = pkg.root / 'agents/vscore-attempts/source-1'
            self.assertEqual(canonical.dumps(raw_relation), (stage/'relation.raw.json').read_bytes())
            self.assertEqual(expected, (stage/'relation.json').read_bytes())

    def test_unaccepted_authority_blocks_before_any_model_call(self):
        with tempfile.TemporaryDirectory(prefix='verislop-relation-no-authority-') as tmp:
            pkg = Package(Path(tmp) / 'package'); pkg.ensure('no-authority')
            fixed, _ = metadata_fixture(pkg); events = EventSink(pkg.run_id, quiet=True)
            self.addCleanup(events.close)
            with patch.object(export, 'verified_ir', return_value=(None, None, None, [Diagnostic('VERIFIER_NOT_RUN', 'unaccepted')])), \
                 patch.object(agents, '_vscore_context', return_value=fixed), \
                 patch.object(agents, 'recorded_call') as call:
                with self.assertRaises(BlockedError):
                    agents._vscore_implementation(None, {'roles': {'implementer': 'author'}}, pkg, events,
                                                 {'parameters': fixed['parameters']}, 1, 0)
                call.assert_not_called()

    def test_invalid_source_retains_raw_relation_and_submitted_proof_without_native_dispatch(self):
        with tempfile.TemporaryDirectory(prefix='verislop-relation-invalid-source-') as tmp:
            pkg = Package(Path(tmp) / 'package'); pkg.ensure('invalid-source')
            fixed, verified = metadata_fixture(pkg); events = EventSink(pkg.run_id, quiet=True)
            proof = 'exact original invalid-source proof\r\n'
            response = json.dumps({'program_source': 'not a program', 'relation': relation(), 'proof_source': proof})
            conf = {'roles': {'implementer': 'author'}, 'agents': {'author': {'vscore_authoring_format': 'surface'}}}
            try:
                with patch.object(export, 'verified_ir', return_value=verified), \
                     patch.object(agents, '_vscore_context', return_value=fixed), \
                     patch.object(agents, 'recorded_call', return_value=SimpleNamespace(text=response)), \
                     patch('verislop.surface_context.project_fixed_context', return_value=fixed), \
                     patch.object(checker, 'preview', side_effect=AssertionError('invalid source reached native checker')):
                    with self.assertRaises(UsageError):
                        agents._vscore_implementation(None, conf, pkg, events, {'parameters': fixed['parameters']}, 1, 0)
                stage = pkg.root / 'agents/vscore-attempts/source-1'
                self.assertEqual(canonical.dumps(relation()), (stage/'relation.raw.json').read_bytes())
                self.assertEqual(proof.encode(), (stage/'proofs/initial.lean').read_bytes())
                self.assertFalse((stage/'relation.json').exists())
            finally:
                events.close()


if __name__ == '__main__':
    unittest.main()
