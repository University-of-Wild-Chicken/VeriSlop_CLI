"""Generic authored citation fixtures; no benchmark answers or live model calls."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from verislop import agent_memory, agents, canonical, draft, interpret
from verislop.errors import BlockedError
from verislop.events import EventSink
from verislop.package import Package

REQUEST = 'Return the text "café\\tail" unchanged.\n\n- Preserve λ🙂 and literal \\n characters.\n- Keep this line break:\nαβ.\n'.encode('utf-8')
REF = 'authored-request.txt'


def proposal(prompt=REQUEST):
    manifest = agents._request_clauses(prompt)
    return {'obligations': [{'id': 'O1', 'kind': 'postcondition', 'role': 'guarantee',
        'statement': 'Preserve the requested observable text behavior.', 'required': True,
        'scope': ['the requested domain'], 'dependencies': [],
        'acceptance_criteria': ['The returned text preserves every specified character and line break.'],
        'sources': [{'clause_id': row['clause_id'], 'origin': 'explicit',
                     'interpretation': 'Authored citation of requested text behavior.'} for row in manifest]}],
        'category_review': {key: 'reviewed' for key in agents.DRAFT_CATEGORIES},
        'clauses': [{'clause_id': row['clause_id'], 'disposition': 'obligations', 'refs': ['O1']} for row in manifest],
        'assumptions': [], 'ambiguities': [], 'selected_defaults': []}


class ClauseCitationTests(unittest.TestCase):
    def validate(self, candidate, prompt=REQUEST, attachments=None):
        assembled, ledger, problems = agents.assemble_interpretation(candidate, prompt, REF, attachments)
        diagnostics = draft.validate_draft(assembled, prompt, REF, attachments)
        ledger_diagnostics, coverage = draft.validate_ledger(ledger, assembled, prompt, REF)
        return assembled, ledger, problems, diagnostics + ledger_diagnostics, coverage

    def test_id_only_sources_and_clauses_resolve_exact_utf8_spans_and_hashes(self):
        candidate = proposal()
        before = copy.deepcopy(candidate)
        assembled, ledger, problems, diagnostics, coverage = self.validate(candidate)
        self.assertEqual(before, candidate)
        self.assertEqual([], problems)
        self.assertEqual([], diagnostics)
        self.assertEqual([], coverage['uncovered_segments'])
        manifest = agents._request_clauses(REQUEST)
        self.assertTrue(any(row['end_byte'] > len(REQUEST[:row['end_byte']].decode()) for row in manifest))
        for row, source, clause in zip(manifest, assembled['postconditions'][0]['source_refs'], ledger['clauses']):
            self.assertEqual((row['start_byte'], row['end_byte']), (source['start_byte'], source['end_byte']))
            self.assertEqual((row['start_byte'], row['end_byte']), (clause['start_byte'], clause['end_byte']))
            self.assertEqual(row['quote'].encode(), REQUEST[source['start_byte']:source['end_byte']])
            self.assertEqual(canonical.digest(REQUEST), source['document_hash'])
            self.assertEqual(REF, source['document_ref'])

    def test_optional_quote_requires_exact_equality_and_never_unescapes(self):
        manifest = agents._request_clauses(REQUEST)
        for location in ('clauses', 'sources'):
            good = proposal()
            rows = good['clauses'] if location == 'clauses' else good['obligations'][0]['sources']
            rows[0]['quote'] = manifest[0]['quote']
            self.assertEqual([], self.validate(good)[2:4][0])
            for wrong in (json.dumps(manifest[0]['quote'])[1:-1], manifest[0]['quote'].replace('"', '\\"'), 'other text'):
                bad = copy.deepcopy(good); target = bad['clauses'] if location == 'clauses' else bad['obligations'][0]['sources']
                target[0]['quote'] = wrong
                self.assertNotEqual(manifest[0]['quote'], wrong)
                with self.subTest(location=location, wrong=wrong):
                    result = self.validate(bad)
                    self.assertTrue(any('ID/quote' in item for item in result[2]))
                    self.assertEqual(wrong, target[0]['quote'])

    def test_unknown_ids_do_not_fall_back_to_matching_supplied_quote(self):
        for location in ('clauses', 'sources'):
            candidate = proposal(); rows = candidate['clauses'] if location == 'clauses' else candidate['obligations'][0]['sources']
            rows[0].update(clause_id='C9999', quote=agents._request_clauses(REQUEST)[0]['quote'])
            with self.subTest(location=location):
                self.assertTrue(any('ID does not match' in item for item in self.validate(candidate)[2]))

    def test_duplicate_and_missing_clause_ids_leave_unchanged_coverage_checker_blocked(self):
        duplicate = proposal(); duplicate['clauses'].append(copy.deepcopy(duplicate['clauses'][0]))
        assembled, ledger, problems, diagnostics, coverage = self.validate(duplicate)
        self.assertTrue(any('duplicate request clause ID' in item for item in problems))
        self.assertIn('UNCOVERED_SOURCE_CLAUSE', {item.code for item in diagnostics})
        missing = proposal(); missing['clauses'].pop()
        self.assertIn('UNCOVERED_SOURCE_CLAUSE', {item.code for item in self.validate(missing)[3]})

    def test_request_ids_cannot_be_used_as_attachment_ids(self):
        attachment = {'attachment.txt': b'Different text in an attachment.'}
        for location in ('clauses', 'sources'):
            candidate = proposal(); rows = candidate['clauses'] if location == 'clauses' else candidate['obligations'][0]['sources']
            rows[0]['document'] = 'attachment.txt'
            with self.subTest(location=location):
                self.assertTrue(any('cannot cite another document' in item for item in self.validate(candidate, attachments=attachment)[2]))
        candidate = proposal()
        candidate['obligations'][0]['sources'].append({'document': 'attachment.txt', 'quote': attachment['attachment.txt'].decode(),
            'origin': 'inferred', 'interpretation': 'Authored supporting context.'})
        result = self.validate(candidate, attachments=attachment)
        self.assertEqual([], result[2]); self.assertEqual([], result[3])
        self.assertEqual(canonical.digest(attachment['attachment.txt']), result[0]['postconditions'][0]['source_refs'][-1]['document_hash'])
        explicit_request = proposal()
        explicit_request['clauses'][0]['document'] = REF
        explicit_request['obligations'][0]['sources'][0]['document'] = REF
        self.assertEqual([], self.validate(explicit_request)[2])

    def test_legacy_quote_only_citations_produce_identical_artifacts(self):
        candidate = proposal(); manifest = agents._request_clauses(REQUEST)
        for rows in (candidate['clauses'], candidate['obligations'][0]['sources']):
            for row, clause in zip(rows, manifest):
                del row['clause_id']; row['quote'] = clause['quote']
        self.assertEqual(self.validate(proposal())[:2], self.validate(candidate)[:2])
        self.assertEqual([], self.validate(candidate)[2]); self.assertEqual([], self.validate(candidate)[3])

    def test_model_authored_dispositions_and_refs_still_need_existing_ledger_validation(self):
        for disposition, refs in (('wrong-disposition', ['O1']), ('obligations', ['absent']), ('ambiguity', ['O1']), ('context', [])):
            candidate = proposal(); candidate['clauses'][0].update(disposition=disposition, refs=refs)
            with self.subTest(disposition=disposition, refs=refs):
                self.assertTrue(self.validate(candidate)[3])

    def test_prompt_examples_and_field_guidance_prefer_current_request_id_citations(self):
        example = agents.extract_json(agents.INTERPRETER_SYSTEM[agents.INTERPRETER_SYSTEM.index('{"obligations"'):])
        self.assertEqual('C1', example['clauses'][0]['clause_id'])
        self.assertNotIn('quote', example['clauses'][0])
        self.assertEqual('C1', example['obligations'][0]['sources'][0]['clause_id'])
        self.assertNotIn('quote', example['obligations'][0]['sources'][0])
        fields = agents._interpreter_wire_schema()
        self.assertIn('clause_id', fields['request_source_item'])
        self.assertIn('clause_id', fields['request_clause_item'])
        self.assertIn('never unescape', fields['citation_rules'])


class RetainedCitationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.pkg = Package(Path(self.tmp.name) / 'package'); self.pkg.ensure('authored-clause-citations')
        self.events = EventSink(self.pkg.run_id, self.pkg.root, quiet=True); self.addCleanup(self.events.close)

    def role(self, responses, captured):
        responses = iter(responses)
        def call(*args):
            captured.append({'user': args[3], 'purpose': args[4]})
            return SimpleNamespace(text=next(responses), requested_model='authored-mock', returned_model=None)
        with patch.object(agents, '_broker', return_value=(SimpleNamespace(call=call), {'roles': {'interpreter': 'author'}})):
            return agents.interpreter_agent('unused', self.pkg, self.events, attempts=3)

    def test_real_recording_preserves_exact_raw_response_and_assembled_provenance(self):
        raw = ' \n' + json.dumps(proposal(), ensure_ascii=False, indent=2) + '\n   '
        captured = []; role = self.role([raw], captured)
        prompt_path = Path(self.tmp.name) / REF; prompt_path.write_bytes(REQUEST)
        result = interpret.run(self.pkg, self.events, prompt_path, mode='software', request_ref=REF, agent=role, interactive=False)
        self.assertEqual('PASS', result.status, [item.to_json() for item in result.diagnostics])
        snapshots = agent_memory.context_for(self.pkg, last=1, stages=['interpret/attempt'])['snapshots']
        retained = snapshots[0]['artifacts']; payload = canonical.loads(retained['payload.json']['content'])
        self.assertEqual(raw, retained['response.txt']['content'])
        self.assertEqual(canonical.load_file(self.pkg.path('draft')), canonical.loads(retained['draft.json']['content']))
        self.assertEqual(canonical.load_file(self.pkg.path('interpretation')), canonical.loads(retained['interpretation.json']['content']))
        self.assertEqual(raw.encode(), agent_memory.restore(self.pkg, payload['response_snapshot'])['response.txt'])
        self.assertEqual([], payload['assembly_problems']); self.assertEqual([], payload['diagnostics'])
        self.assertIn(canonical.digest(REQUEST), captured[0]['user'])

    def test_exhausted_assembly_errors_cannot_disappear_through_valid_remaining_coverage(self):
        candidate = proposal(); candidate['clauses'].append({'clause_id': 'unknown', 'disposition': 'obligations', 'refs': ['O1']})
        # Removing only the invalid extra citation leaves full valid coverage. The
        # final callback still has to reject its source proposal, never accept it.
        self.assertEqual([], draft.validate_ledger(self.validate(candidate)[1], self.validate(candidate)[0], REQUEST, REF)[0])
        raw = json.dumps(candidate, ensure_ascii=False); captured = []
        with self.assertRaises(BlockedError) as caught:
            self.role([raw] * 3, captured)(REQUEST, REF, {})
        self.assertEqual(3, len(captured))
        self.assertEqual('INVALID_CANDIDATE', caught.exception.diagnostics[0].code)
        histories = agent_memory.context_for(self.pkg, last=3, stages=['interpret/attempt'])['snapshots']
        self.assertEqual(3, len(histories))
        self.assertTrue(all(canonical.loads(row['artifacts']['payload.json']['content'])['assembly_problems'] for row in histories))
        self.assertFalse(self.pkg.path('draft').exists())

    def test_malformed_response_retains_actual_error_without_fabricated_assembled_artifacts(self):
        malformed = '  {"obligations": [broken λ}\n'
        captured = []
        self.role([malformed, json.dumps(proposal(), ensure_ascii=False)], captured)(REQUEST, REF, {})
        history = agent_memory.context_for(self.pkg, last=2, stages=['interpret/attempt'])['snapshots']
        first = history[0]['artifacts']; payload = canonical.loads(first['payload.json']['content'])
        self.assertEqual(malformed, first['response.txt']['content'])
        self.assertEqual('INVALID_CANDIDATE', payload['diagnostics'][0]['code'])
        self.assertNotIn('draft.json', first); self.assertNotIn('interpretation.json', first)
        self.assertIn(malformed, captured[1]['user'])
        self.assertIn('draft.json', history[1]['artifacts'])

    validate = ClauseCitationTests.validate


if __name__ == '__main__':
    unittest.main()
