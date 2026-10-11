#!/usr/bin/env python3
"""Finite independent evidence admission. No imports/execution of target verifiers."""
from pathlib import Path
import argparse
import ast
import copy
import base64
import datetime
import hashlib
import json
import importlib.util
import re
import sys

ROOT = Path(__file__).absolute().parents[2]
HERE = Path(__file__).absolute().parent
GATE = None
FINAL = None
CLOSURE = None
ADDITIONAL = dict(zip(['Q019-%02d'%i for i in range(1,10)], ['equality_original','equality_private','carrier_pure','carrier_full','carrier_faults','carrier_empty','fresh_author','authority_boundary','whole_audit']))
UNAVAILABLE = {'hidden_native_outer_http_mcp_envelope':'UNAVAILABLE','separated_stdout':'UNAVAILABLE','separated_stderr':'UNAVAILABLE','pid':'UNAVAILABLE'}
COLLECTION = 'tests.test_vscore3_collection_bridge.CollectionRegisteredTier2Tests.test_actual_frozen_collection_closure_and_retained_release_probe'

class Block(ValueError):
    pass

def need(ok, code):
    if not ok:
        raise Block(code)

def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def wire(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8', 'strict')

def digest(x):
    # Source/input/Lean identities use the repository's declared JCS contract.
    # Transport records retain their distinct Python sort_keys wire contract.
    def encode(value):
        if value is None: return 'null'
        if value is True: return 'true'
        if value is False: return 'false'
        if type(value) is int:
            need(abs(value)<=2**53-1,'NONCANONICAL_INTEGER')
            return str(value)
        if type(value) is str:
            value.encode('utf-8','strict')
            return json.dumps(value,ensure_ascii=False,separators=(',',':'))
        if type(value) in (list,tuple): return '['+','.join(encode(v) for v in value)+']'
        need(type(value) is dict and all(type(k) is str for k in value), 'NONCANONICAL_JSON_VALUE')
        return '{'+','.join(encode(k)+':'+encode(value[k]) for k in sorted(value,key=lambda k:k.encode('utf-16-be')))+'}'
    return sha(encode(x).encode('utf-8','strict'))

def unique(pairs):
    x = {}
    for k, v in pairs:
        need(k not in x, 'DUPLICATE_JSON_KEY:' + k)
        x[k] = v
    return x

def parse(data):
    try:
        return json.loads(data.decode('utf-8', 'strict'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(Block('NONFINITE_JSON')))
    except (UnicodeError, json.JSONDecodeError) as e:
        raise Block('MALFORMED_JSON:' + str(e)) from e

def number(x, minimum=0):
    need(type(x) is int and x >= minimum, 'EXPECTED_INTEGER')
    return x

def date(x):
    need(isinstance(x, str), 'TIMESTAMP_NOT_TEXT')
    try:
        t = datetime.datetime.fromisoformat(x.replace('Z', '+00:00'))
    except ValueError as e:
        raise Block('INVALID_TIMESTAMP') from e
    need(t.utcoffset() == datetime.timedelta(0), 'TIMESTAMP_NOT_UTC')
    return t

class Reader:
    def __init__(self, args):
        global GATE, FINAL, CLOSURE
        self.args, self.evidence, self.groups = args, {}, {}
        GATE = Path(args.qualification_root)
        need(GATE.is_absolute() and GATE.parent == ROOT / 'validation' and
             GATE.resolve() == GATE and GATE.name.startswith('tier2-support-019-qualification-'), 'QUALIFICATION_ROOT_NOT_CANONICAL_NEW_ROOT')
        FINAL = GATE / 'final-reconciliation'
        self.spec = self.doc(GATE / 'qualification-specification.json')
        self.adapters = self.spec['adapters']
        CLOSURE = self.spec['closure_id']
        need(self.adapters['closure_id'] == CLOSURE and self.adapters['qualification_root'] == GATE.relative_to(ROOT).as_posix(), 'ADAPTER_SCOPE_NOT_CURRENT')
        self.plan = self.registered_doc(self.adapters['predicate_reader_specification'])
        claim_doc = self.doc(self.adapters['claims_file'])
        self.original_claims = self.plan['original18']
        need([{k:c[k] for k in ('id','statement','pass_condition','verifier','dependencies_trusted')} for c in self.original_claims] ==
             [{k:c[k] for k in ('id','statement','pass_condition','verifier','dependencies_trusted')} for c in claim_doc['original_claims']], 'ORIGINAL_CLAIMS_CHANGED')
        self.claims = self.original_claims + [dict(c, audit_groups=['freeze','phases', ADDITIONAL[c['id']]]) for c in claim_doc['additional_claims']]
        need([c['id'] for c in self.claims] == ['Q018-%02d'%i for i in range(1,19)] + ['Q019-%02d'%i for i in range(1,10)], 'EXACT27_CLAIM_ORDER')
        self.report, self.hashes = {}, {}
        self.input_root = self.source_root = None
        self.processes, self.phase_receipts = [], []
        self.runtime_representation = self.adapters['runtime_representation']
        self.collection_representation = self.adapters['collection_representation']
        self.floor = self.doc(self.adapters['mandatory_floor'])
        self.index_hashes = {'equality':args.equality_index_sha256,'carrier':args.carrier_index_sha256,
                             'author':args.author_index_sha256,'pure':args.pure_index_sha256}
        self.equality_cache = None

    def registered_doc(self, entry):
        if isinstance(entry, dict):
            return parse(self.ref(entry))
        return self.doc(entry)

    def path(self, value, base=ROOT):
        need(isinstance(value, (str, Path)), 'PATH_NOT_TEXT')
        p = Path(value)
        if not p.is_absolute():
            need('..' not in p.parts and p.as_posix() == str(value), 'NONCANONICAL_PATH')
            p = base / p
        need('..' not in p.parts and p.is_file() and not p.is_symlink() and p.resolve() == p.absolute(),
             'MISSING_OR_INDIRECT_EVIDENCE:' + str(p))
        return p

    def read(self, value, expected=None, size=None, base=ROOT):
        p = self.path(value, base)
        data = p.read_bytes()
        row = {'sha256': sha(data), 'byte_count': len(data)}
        need(str(p) not in self.evidence or self.evidence[str(p)] == row, 'EVIDENCE_MUTATED:' + str(p))
        if expected is not None:
            need(isinstance(expected, str) and row['sha256'] == ('sha256:' + expected.removeprefix('sha256:')),
                 'HASH_MISMATCH:' + str(p))
        if size is not None:
            need(len(data) == number(size), 'SIZE_MISMATCH:' + str(p))
        self.evidence[str(p)] = row
        return data

    def doc(self, value, expected=None, base=ROOT):
        return parse(self.read(value, expected, base=base))

    def ref(self, ref, base=ROOT):
        return self.read(ref['path'], ref['sha256'], ref.get('byte_count', ref.get('bytes', ref.get('size'))), base)

    def execute(self, group, fn):
        before = set(self.evidence)
        try:
            detail = fn()
            result = {'status': 'VERIFIED', 'actual_predicates': detail, 'blocking_reasons': []}
        except (Block, KeyError, ValueError, TypeError, IndexError, AttributeError) as e:
            result = {'status': 'BLOCKED', 'actual_predicates': {}, 'blocking_reasons': [str(e)]}
        except Exception as e:
            result = {'status': 'INFRASTRUCTURE_FAILURE', 'actual_predicates': {}, 'blocking_reasons': [type(e).__name__ + ':' + str(e)]}
        result['evidence'] = sorted(set(self.evidence) - before)
        self.groups[group] = result

    def inventory(self):
        spec = self.registered_doc(self.adapters['source_inventory_registration'])
        names=set(spec['transport_files'])
        for directory,suffixes in spec['directory_suffixes'].items():
            names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*') if p.suffix in suffixes)
        names.update(n for n in spec['optional_root_files'] if (ROOT/n).exists())
        need(spec['required_source_file'] in names,'SOURCE_SPECIFICATION_MISSING')
        return names

    def finalizer(self):
        reg = self.registered_doc(self.adapters['reconciler_registration'])
        receipt = self.doc(self.args.finalizer_receipt)
        bindings={'python':sys.executable,'verifier':str(self.path(reg['verifier']['path'])),'qualification_root':str(GATE),
                  'equality_index_sha256':self.args.equality_index_sha256,'carrier_index_sha256':self.args.carrier_index_sha256,
                  'author_index_sha256':self.args.author_index_sha256,'pure_index_sha256':self.args.pure_index_sha256}
        expected_argv=[part.format(**bindings) for part in reg['invocation']['argv_template']]
        need(receipt['argv']==expected_argv and receipt['cwd']==str(ROOT) and reg['invocation']['accepted_exit_code']==0 and
             reg['invocation']['output']=='final-reconciliation', 'FINALIZER_COMMAND_NOT_REGISTERED')
        number(receipt['pid'], 1)
        need(number(receipt['returncode']) == 0 and receipt['timed_out'] is False, 'FINALIZER_PROCESS_NOT_COMPLETED_SUCCESSFULLY')
        need(receipt['input_root'] == self.input_root and receipt['source_root'] == self.source_root, 'FINALIZER_PROCESS_STALE')
        need(date(self.prereg['created_utc']) <= date(receipt['started_utc']) <= date(receipt['completed_utc']), 'FINALIZER_INTERVAL_INVALID')
        stdout = parse(self.ref(receipt['stdout'])); self.ref(receipt['stderr'])
        report_path = self.path(self.args.final_report)
        need(report_path == FINAL / 'report.json' and self.path(receipt['report']['path']) == report_path and stdout['report'] == str(report_path), 'FINAL_REPORT_PATH_NOT_CURRENT_REGISTERED')
        self.report = self.doc(report_path, receipt['report']['sha256']); r = self.report
        need(stdout == {'status':r['status'],'source_root':self.source_root,'input_root':self.input_root,'report':str(report_path),'claim_count':27}, 'FINALIZER_STDOUT_REPORT_DISAGREES')
        need(r['closure_id']==CLOSURE and r['source_root']==self.source_root and r['input_root']==self.input_root, 'FINAL_REPORT_STALE')
        need(r['verifier_id']==reg['verifier_id'] and r['verifier_sha256']==reg['verifier']['sha256'] and
             r['specification_sha256']==reg['specification']['sha256'] and r['report_schema_sha256']==reg['report_schema']['sha256'], 'FINALIZER_IMPLEMENTATION_UNBOUND')
        for key in ('verifier','specification','report_schema'): self.ref(reg[key])
        need([c['claim_id'] for c in r['claims']]==[c['id'] for c in self.claims], 'EXACT27_FINALIZER_CLAIM_INVENTORY_CHANGED')
        for claim,row in zip(self.claims,r['claims']):
            names=['guards' if g=='freeze' else g for g in claim['audit_groups'] if g!='provenance']
            need(row['status']=='VERIFIED' and row['blocking_reasons']==[] and row['actual_predicates']==
                 {g:r['actual_predicate_groups'][g]['actual_predicates'] for g in names} and
                 all(r['actual_predicate_groups'][g]['status']=='VERIFIED' for g in names), 'CLAIM_NOT_DERIVED_FROM_CURRENT_REGISTERED_RAW_GROUPS:'+claim['id'])
            need(row['original_statement']==claim['statement'] and row['original_pass_condition']==claim['pass_condition'] and
                 row['registered_verifier']==claim['verifier'] and row['trusted_dependencies']==claim['dependencies_trusted'], 'ORIGINAL_PREDICATE_OR_TRUST_CHANGED:'+claim['id'])
        need(r['status']=='VERIFIED' and number(r['decision']['exit_code'])==receipt['returncode'] and r['decision']['manual_override_allowed'] is False, 'FINALIZER_DECISION_PROCESS_CONTRADICTION')
        need(r['dependencies']['trusted']==[x['id'] for x in self.plan['tcb']['trusted']]+['TCB-TOOL-FORWARDING'] and r['dependencies']['undeclared']==[], 'FINALIZER_UNDECLARED_OR_CHANGED_DEPENDENCY')
        for p,row in r['evidence'].items(): self.read(p,row['sha256'],row['byte_count'])
        need(r['scope']['finite_qualification_only'] is True and all(r['scope'][k] is False for k in
             ('llm_consumption_attested','semantic_acceptance_authority','production_task_inputs','prior_pass_inheritance','activation_authority')) and
             r['scope']['model_identity']==r['scope']['semantic_consumption']=='UNATTESTED' and r['scope']['hidden_outer_native_envelope']=='UNAVAILABLE', 'FINALIZER_SCOPE_LEAK')
        return {'exact_registered_process':receipt,'raw_finalizer_evidence_count':len(r['evidence'])}

    def freeze(self):
        self.input = self.doc(GATE / 'qualification-inputs.json')
        self.frozen = self.doc(GATE / 'source-freeze.json')
        self.prereg = self.doc(GATE / 'preregistration.json')
        self.hashes = self.input['source_hashes']; self.input_root = self.input['input_root']; self.source_root = self.frozen['source_root']
        need(all(isinstance(v,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in (self.input_root,self.source_root)), 'RUNTIME_REGISTERED_ROOT_INVALID')
        need(self.spec['closure_id']==CLOSURE and self.input['source_root']==self.source_root==self.spec['source_root'], 'RUNTIME_CLOSURE_SOURCE_MISMATCH')
        need(self.hashes and digest(self.hashes)==self.input_root and self.frozen['source_files'] and digest(self.frozen['source_files'])==self.source_root, 'CURRENT_INPUT_SOURCE_MAP_MISMATCH')
        ids=self.spec['registered_test_ids']; modules=self.spec['test_modules']
        need(self.spec['test_sources'] and len(ids)==len(set(ids))==number(self.spec['registered_test_count']) and
             set(self.floor['registered_test_ids']).issubset(ids) and set(self.floor['test_modules']).issubset(modules), 'EXACT180_ALL15_FLOOR_MISSING')
        for p,h in self.hashes.items(): self.read(p,h)
        representation={**self.collection_representation['source_bindings'],**self.runtime_representation['source_bindings']}
        need(representation and all(self.hashes.get(p)==h for p,h in representation.items()), 'CURRENT_COLLECTION_RUNTIME_REPRESENTATION_UNBOUND')
        for p,h in representation.items(): self.read(p,h)
        for source_map in (self.frozen['source_files'],self.spec['test_sources']):
            need(all(self.hashes.get(p)==h for p,h in source_map.items()), 'INCOMPLETE_SOURCE_TEST_HASH_MAP')
        need(self.inventory()==set(self.frozen['source_files']), 'PRODUCTION_FILE_ADDED_OR_REMOVED')
        need({p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').rglob('*.py')}==set(self.spec['test_sources']), 'TEST_FILE_ADDED_OR_REMOVED')
        need(self.prereg['format']=='verislop.support019-final-preregistration/1' and
             self.prereg['closure_id']==CLOSURE and type(self.prereg['external_bindings']) is dict and
             set(self.prereg['external_bindings'])=={'qualification-specification.json','source-freeze.json','qualification-inputs.json'},
             'PREREGISTRATION_COMPLETE_CURRENT_BINDINGS_REQUIRED')
        for p,h in self.prereg['external_bindings'].items(): self.read(p,h,base=GATE)
        driver=self.path(self.adapters['gate_driver']); driver_name=driver.relative_to(ROOT).as_posix()
        need(driver_name in self.hashes, 'CURRENT_GATE_DRIVER_NOT_FROZEN')
        self.read(driver,self.hashes[driver_name])
        need(self.prereg['input_root']==self.input_root and self.prereg['source_root']==self.source_root and self.prereg['generation_started'] is False and self.frozen['generation_started'] is False, 'FREEZE_NOT_PREEXECUTION')
        claims_path=self.path(self.adapters['claims_file']); claims_name=claims_path.relative_to(ROOT).as_posix()
        need(self.hashes.get(claims_name)==self.spec['claims_sha256'], 'CURRENT_CLAIM_REGISTRATION_NOT_FROZEN')
        self.read(claims_path,self.spec['claims_sha256'])
        need(isinstance(self.spec['toolchain'],dict) and all(k in self.spec['toolchain'] for k in ('pin','version','githash','lean_binary_sha256')) and
             all(isinstance(v,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in (self.spec['toolchain']['lean_binary_sha256'],self.spec['kernel_tool_hash'],self.spec['policy_hash'])), 'RUNTIME_TOOL_OR_POLICY_BINDING_INVALID')
        need(self.spec['core_model_calls']==0 and self.spec['ancillary_fresh_author_calls']==1 and self.spec['task_inputs'] is False and self.spec['prior_pass_inheritance'] is False, 'PROHIBITED_AUTHORITY')
        for p,h in self.spec['external_runtime_files'].items(): self.read(p,h)
        self.reader_registration = self.registered_doc(self.adapters['predicate_reader_registration'])
        need(self.reader_registration['verifier']['path']==Path(__file__).relative_to(ROOT).as_posix() and self.reader_registration['verifier']['sha256']==sha(self.read(Path(__file__))), 'READER_SOURCE_NOT_INSTALLED_REGISTERED')
        for key in ('verifier','specification','report_schema'): self.ref(self.reader_registration[key])
        for p in list(self.evidence):
            path=Path(p)
            if path.is_relative_to(ROOT):
                name=path.relative_to(ROOT).as_posix()
                # Runtime external gate preregistration files are separately hash-bound.
                if not path.is_relative_to(GATE): need(self.hashes.get(name)==self.evidence[p]['sha256'], 'VERIFICATION_INPUT_NOT_IN_WHOLE_FROZEN_MAP:'+name)
        self.finalizer()
        for g in ('guards','guards_after'):
            raw=self.report['actual_predicate_groups'][g]
            need(raw['status']=='VERIFIED' and raw['actual_predicates']['source_root']==self.source_root and raw['actual_predicates']['input_root']==self.input_root and
                 raw['actual_predicates']['input_files']==len(self.hashes) and raw['actual_predicates']['source_files']==len(self.frozen['source_files']) and
                 raw['actual_predicates']['test_files']==len(self.spec['test_sources']) and raw['actual_predicates']['environment']=={'toolchain':self.spec['toolchain'],'kernel_tool_hash':self.spec['kernel_tool_hash'],'policy_hash':self.spec['policy_hash']}, 'FINALIZER_COMPLETE_GUARDS_ABSENT')
        need(self.report['actual_predicate_groups']['guards']['actual_predicates']==self.report['actual_predicate_groups']['guards_after']['actual_predicates'], 'FINALIZER_ENTRY_EXIT_DIFFER')
        return {'input_count':len(self.hashes),'source_count':len(self.frozen['source_files']),'test_count':len(self.spec['test_sources']),'source_root':self.source_root,'input_root':self.input_root,'registered_verifier_execution_authenticated':True}

    def phases(self):
        invocation = self.doc(GATE / 'phase-launcher-invocation.json')
        need(invocation['phases'] == self.spec['execution_phases'] == self.prereg['execution_phases'] and
             invocation['input_root'] == self.input_root and invocation['source_root'] == self.source_root and
             invocation['model_calls'] == 0 and invocation['task_inputs'] is False and invocation['inference_timeout'] is None,
             'PHASE_LAUNCHER_STALE')
        previous = date(invocation['started_utc'])
        need(date(self.frozen['created_at_utc']) <= date(self.prereg['created_utc']) <= previous, 'PHASE_STARTED_BEFORE_FREEZE')
        for phase in self.spec['execution_phases']:
            row = self.doc(GATE / (phase['id'] + '-actual-process-receipt.json'))
            need(row['id'] == phase['id'] and row['argv'] == phase['argv'] and row['registered_environment'] == phase['environment'] and
                 row['cwd'] == str(ROOT) and number(row['returncode']) == phase['accepted_exit_code'] == 0 and row['timed_out'] is False,
                 'PHASE_COMMAND_OR_NUMERIC_EXIT_MISMATCH:' + phase['id'])
            number(row['pid'],1)
            need(row['source_root'] == self.source_root and row['input_root'] == self.input_root, 'PHASE_STALE')
            need(previous <= date(row['started_utc']) <= date(row['completed_utc']), 'PHASE_SERIAL_ORDER')
            previous = date(row['completed_utc'])
            for stream in ('stdout','stderr'):
                need(row[stream]['path'] == (GATE / (phase['id'] + '.' + stream + '.log')).relative_to(ROOT).as_posix(), 'PHASE_LOG_SUBSTITUTION')
                self.ref(row[stream])
            self.phase_receipts.append(row)
        self.final_spec = self.registered_doc(self.adapters['specification'])
        return {'exact_current_numeric_processes':4,'registered_serial_order':self.final_spec['phase_order']}

    def suite(self):
        s = self.doc(GATE / 'run-result.json'); inv = self.doc(GATE / 'invocation.json'); ids = self.spec['registered_test_ids']
        need(len(ids) == len(set(ids)) == self.spec['registered_test_count'] and COLLECTION in ids and
             s['registered_test_ids'] == s['started_ids'] == inv['registered_test_ids'] == ids and
             number(s['tests_run']) == s['registered_test_count'] == self.spec['registered_test_count'] and
             s['test_observations'] == [{'test_id':i,'status':'PASS'} for i in ids], 'EXACT_SUITE_NOT_EXECUTED')
        for k in ('failures','errors','skipped','expected_failures','unexpected_successes'):
            need(number(s[k]) == 0, 'NONZERO_SUITE_RESULT:' + k)
        need(s['source_root_before'] == s['source_root_after'] == inv['source_root'] == self.source_root and
             s['input_root'] == inv['input_root'] == self.input_root and
             s['external_bindings_before'] == s['external_bindings_after'], 'SUITE_CURRENT_BINDING_MISMATCH')
        driver=self.path(self.adapters['gate_driver'])
        need(inv['driver_sha256']==sha(self.read(driver,self.hashes[driver.relative_to(ROOT).as_posix()])), 'SUITE_CONFIGURED_DRIVER_HASH_MISMATCH')
        required={p.relative_to(ROOT).as_posix() for p in [driver]+[GATE/name for name in
                  ('qualification-specification.json','qualification-inputs.json','source-freeze.json','preregistration.json')]}
        need(set(s['external_bindings_before'])==required, 'SUITE_COMPLETE_EXTERNAL_BINDING_INVENTORY_MISMATCH')
        for p,h in s['external_bindings_before'].items(): self.read(p,h)
        need(all(s[k] is True for k in ('source_unchanged','tests_unchanged','qualification_inputs_unchanged')) and
             all(any(i.startswith(m+'.') for i in ids) for m in self.spec['test_modules']), 'SUITE_INVENTORY_GUARD_MISSING')
        self.suite_ids = ids
        return {'ordered_tests':len(ids),'modules':len(self.spec['test_modules']),'all_exact_individual_outcomes':'PASS'}

    def carrier(self):
        r = self.doc(GATE / 'carrier-fixtures/report.json'); c = self.final_spec['carrier']
        need(r['tests_run'] == 19 and r['failures'] == r['errors'] == 0 and
             set(r['test_outcomes']) == set(c['methods']) and all(v=='PASS' for v in r['test_outcomes'].values()), 'CARRIER_19_RESULTS')
        need(all(c['class_prefix']+m in self.suite_ids for m in c['methods']), 'CARRIER_METHOD_NOT_ACTUAL_SUITE')
        self.read(GATE / 'verification-source-manifest.json',r['manifest_sha256'])
        need(set(r['checks']) == set(c['mandatory_checks']) and set(r['negative_controls']) == set(c['control_ids']), 'CARRIER_CHECK_CONTROL_INVENTORY')
        for k, methods in c['check_test_map'].items():
            need(r['checks'][k]['tests'] == methods and r['checks'][k]['local_status'] == 'PASS' and
                 r['checks'][k]['disposition'] == ('UNRESOLVED' if k in ('CV-004','CV-008') else 'PASS'), 'CARRIER_ORIGINAL_CHECK_MAPPING:'+k)
        for i,k in enumerate(c['control_ids'],1):
            need(r['negative_controls'][k]['tests'] == [m for m in c['methods'] if m.startswith('test_n%03d_' % i)] and
                 r['negative_controls'][k]['local_status']=='PASS','CARRIER_CONTROL_NOT_EXACT:'+k)
        need(r['model_calls']==r['native_runs']==0 and r['llm_consumption_attested'] is False and
             r['semantic_acceptance_or_lifecycle_authority'] is False,'CARRIER_SCOPE_LEAK')
        log = self.read(GATE / 'carrier-fixtures/unittest.log').decode('utf-8','strict')
        need(re.search(r'Ran 19 tests in ',log) and re.search(r'\nOK\s*$',log),'CARRIER_ACTUAL_LOG_MISSING')
        return {'methods':c['methods'],'checks':c['check_test_map'],'controls':c['control_ids'],'finite_six_families_only':True}

    def channel(self):
        directory = ROOT / self.adapters['original_channel']['capture_root']; p = self.doc(directory / 'channel-case-plan.json'); ix = self.doc(directory / 'capture-index.json')
        need(p['required_case_ids'] == ['intact','truncated','retry'] and p['required_complete_fields']==[] and
             [r['id'] for r in ix['cases']]==p['required_case_ids'] and ix['closure_id']==CLOSURE and
             ix['input_root_hash']==self.input_root and ix['source_root_hash']==self.source_root,'CHANNEL_CASE_SCOPE_OR_ROOT')
        rows=[]
        for plan, actual, bounds in zip(p['cases'],ix['cases'],[(8192,2048,16384),(8192,2048,100),(4096,2048,16384)]):
            need(all(actual[k]==v for k,v in plan.items()) and
                 (plan['output_cap_bytes'],plan['metadata_reserve_bytes'],plan['max_output_tokens'])==bounds and
                 plan['selector']=='/user' and plan['start_char']==0,'CHANNEL_FROZEN_CASE_CHANGED')
            expected = self.read(plan['expected_stdout_ref'],plan['expected_stdout_sha256'],base=directory)
            tool = self.doc(actual['actual_tool_result_ref'],actual['actual_tool_result_sha256'],base=directory)
            self.read(plan['carrier_ref'],plan['carrier_ref_sha256'],base=directory)
            need(actual['forwarded_tool_result_sha256']==actual['actual_tool_result_sha256'] and number(tool['exit_code'])==0,'CHANNEL_TOOL_RESULT_NOT_FORWARDED')
            received = tool['output'].encode('utf-8','strict')
            if plan['expected_delivery']=='truncated':
                need(received!=expected and actual['accepted_next_char'] is None and
                     type(tool['original_token_count']) is int and tool['original_token_count']>plan['max_output_tokens'] and
                     re.search(r'Warning: truncated output \(original token count: [0-9]+\)',tool['output']), 'CHANNEL_TRUNCATION_NOT_EXPLICIT')
                rows.append({'id':plan['id'],'delivery':'truncated','original_token_count':tool['original_token_count']})
            else:
                need(received==expected,'CHANNEL_RECEIVED_BYTES_DIFFER')
                response = parse(expected); metadata = dict(response,content='')
                whole=len(expected); meta=len(wire(metadata))+1; payload=len(json.dumps(response['content'],ensure_ascii=False,separators=(',',':')).encode('utf-8'))
                need(whole<=bounds[0] and meta<=bounds[1] and payload<=bounds[0]-bounds[1] and
                     actual['accepted_next_char']==response['next_char'],'CHANNEL_WIRE_RESERVE_PAYLOAD_OR_CURSOR')
                rows.append({'id':plan['id'],'delivery':'intact','wire_bytes':whole,'metadata_bytes':meta,'content_token_bytes':payload})
        need(ix['cases'][1]['retry_case_id']=='retry' and ix['cases'][1]['start_char']==ix['cases'][2]['start_char']==0,'CHANNEL_RETRY_ADVANCED')
        result=self.doc(directory/'channel-result.json'); receipt=self.doc(directory/'comparator-actual-process-receipt.json')
        need(number(receipt['returncode'])==0 and receipt['timed_out'] is False and receipt['source_root']==self.source_root and receipt['input_root']==self.input_root,
             'CHANNEL_COMPARATOR_RECEIPT_STALE')
        need(parse(self.ref(receipt['stdout']))==result,'CHANNEL_ACTUAL_COMPARATOR_STDOUT_DIFFERS');self.ref(receipt['stderr'])
        need(result['raw_result_hash']==sha(self.read(directory/'capture-index.json')) and result['verifier_hash']==self.hashes[
             self.adapters['original_channel']['comparator']] and result['raw_result']['complete_fields']==[] and
             result['raw_result']['llm_consumption_attested'] is False and result['raw_result']['accept_or_lifecycle_authority'] is False,'CHANNEL_RESULT_UNBOUND_OR_OVERCLAIM')
        return {'exact_three_cases':rows,'complete_field_channel_coverage':False,'consumption_or_acceptance':False}

    def compile_process(self, p):
        need(p['format']=='verislop.lean-compile-process/1' and type(p['returncode']) is int and type(p['timed_out']) is bool and
             p['requested_argv'] and p['launcher_argv'] and p['sandbox_profile'],'NUMERIC_COMPILE_PROCESS_MISSING')
        for stream in ('stdout','stderr'):
            r=p[stream]
            try:data=base64.b64decode(r['content_b64'],validate=True)
            except (ValueError,TypeError) as e:raise Block('COMPILE_RAW_OUTPUT_MALFORMED') from e
            need(number(r['byte_count'])==len(data) and r['sha256']==sha(data),'COMPILE_OUTPUT_HASH_OR_SIZE')
        need(number(p['requested_limits']['lean_heap_mb'],1)>0 and float(p['requested_limits']['wall_timeout_seconds'])>0,'COMPILE_REQUESTED_LIMITS_MISSING')
        self.processes.append(p)

    def unicode(self):
        d=ROOT/self.adapters['unicode_directory'];r=self.doc(d/'report.json')
        need(r['fixture_counts']=={'positive':182,'legacy':95,'invalid_surrogate':6,'lean_negative':5} and
             r['builds']=={'required':2,'passed':2} and r['claims']['statuses']=={'UL18-C%d'%i:'PASS' for i in range(1,6)},'UNICODE_FINITE_COUNTS_OR_CLAIMS')
        manifest=self.doc(d/'manifest.json')
        for row in manifest['files']: self.read(row['path'],row['sha256'],row['bytes'])
        rows=self.doc(d/'correspondence-input.json');host=self.doc(d/'host-checks.json')
        need(len(rows)==182 and host['positive_count']==182 and len(host['legacy_ids'])==95 and len(host['invalid'])==6 and
             all(x['rejected_paths']==5 for x in host['invalid']),'UNICODE_CORRESPONDENCE_SURROGATE_DOMAIN')
        builds=self.doc(d/'builds.json')
        need([x['id'] for x in builds]==['A','B'] and builds[0]['artifacts']==builds[1]['artifacts'] and
             builds[0]['inventory_sha256']==builds[1]['inventory_sha256'] and builds[0]['correspondence_sha256']==builds[1]['correspondence_sha256'],
             'UNICODE_AB_DIFFER')
        processes=self.doc(d/'processes.json')
        for row in processes:
            need(type(row['returncode']) is int and row['timed_out'] is False and row['isolation'],'UNICODE_UNRUN_PROCESS')
            self.ref(row['stdout'],d); self.ref(row['stderr'],d)
            if 'kernel_evidence' in row:
                ke=row['kernel_evidence'];request=parse(self.ref(ke['request'],d));response=parse(self.ref(ke['response'],d))
                self.ref(ke['kernel_tool'],d)
                need(request['export'] is True and request['axioms'] is True and request['module']=='VeriSlopContract' and
                     response.get('constants') and response.get('replay'),'UNICODE_KERNEL_RAW_REQUEST_RESPONSE_MISSING')
        negatives=self.doc(d/'negative-summary.json');need(len(negatives)==5,'UNICODE_NEGATIVE_MISSING')
        for n in negatives:
            c=self.doc(d/(n['id']+'.json'));self.compile_process(c['process_evidence'])
            need(c['ok'] is False and c['errors'] and c['timed_out'] is False and c['process_evidence']['returncode']!=0,'UNICODE_NEGATIVE_NOT_ACTUAL_REJECTION')
        raw=self.report['actual_predicate_groups']['unicode']['actual_predicates']
        need(raw['two_kernel_rounds']==[182,182] and len(raw['actual_kernel_batches'])>0 and raw['deterministic_artifacts_and_exact_Expr_inventories'] is True and
             raw['universal_unicode_claim'] is False,'UNICODE_REGISTERED_EXACT_KERNEL_PROJECTION_MISSING')
        return {'finite_literals':182,'legacy':95,'surrogates':6,'surrogate_paths':5,'compiler_negatives':5,'rounds':['A','B'],'kernel_batches':raw['actual_kernel_batches']}

    def ground(self):
        d=GATE/'ground-kernel';r=self.doc(d/'report.json');f=self.doc(d/'frozen-inputs.json');g=self.final_spec['ground']
        need(r['caller_source_freeze']==f['caller_source_freeze']==self.source_root and r['input_root']==f['file_map_hash']==digest(f['files']) and
             all(self.hashes.get(p)==h for p,h in f['files'].items()),'GROUND_FROZEN_ROOT_UNBOUND')
        need(f['toolchain']==self.spec['toolchain'] and f['kernel_tool_hash']==self.spec['kernel_tool_hash'] and f['policy_hash']==self.spec['policy_hash'], 'GROUND_TOOLCHAIN_CHANGED')
        recipe_path=self.path(Path(self.adapters['ground_design'])/'recipe-001.json')
        need(self.hashes.get(recipe_path.relative_to(ROOT).as_posix())==g['recipe_sha256'], 'GROUND_RECIPE_NOT_EXACT_FROZEN_SOURCE')
        recipe=self.doc(recipe_path,g['recipe_sha256'])
        need(r['recipe']==recipe['proof'] and r['strategy']=='S-GR-001' and r['optional_strategy']=='S-GR-002_UNAVAILABLE' and
             recipe['options']=={'maxHeartbeats':2000000,'maxRecDepth':100000,'smartUnfolding':False} and recipe['polarity_order']==[False,True] and
             recipe['max_polarity_compilations']==2 and recipe['whole_probe_deadline_seconds']==30,'GROUND_RECIPE_OR_BUDGET_CHANGED')
        need([x['id'] for x in r['steps']]==g['steps'] and all(type(x['rc']) is int and x['rc']==0 for x in r['steps']),'GROUND_REQUIRED_STEP_NOT_RUN')
        for p,h in r['evidence'].items():self.read(p,h,base=d)
        definitive=0
        for label,current in [('baseline',False),('clean-001',True),('clean-002',True)]:
            outcomes=self.doc(d/label/'outcomes.json');need([[x['fixture'],x['assignment']] for x in outcomes]==g['case_pairs'],'GROUND_CASE_PAIRS_CHANGED')
            expected=g['expected_current' if current else 'expected_baseline']
            for x in outcomes:
                need(x['status']==expected[x['fixture']],'GROUND_ORIGINAL_DISPOSITION_CHANGED')
                if not current:continue
                o=x['observed'];a=d/label/x['fixture']/('assignment-%d'%x['assignment'])
                need(o is not None and o['proof_attempts'] and o['proof_dependencies'] and o['strategy_id']=='kernel-ground-normalization/1','GROUND_MANDATORY_OBSERVATION_EVIDENCE_ABSENT')
                attempts=o['proof_attempts'];need(len(attempts)<=2 and [t['polarity'] for t in attempts]==[False,True][:len(attempts)] and
                     len(wire(attempts))<=16384,'GROUND_ATTEMPTS_OR_WIRE_BOUND')
                for t in attempts:
                    need(len(t['errors'])<=8 and all(len(v.encode('utf-8','strict'))<=512 for v in t['errors']) and len(wire(t))<=8190,
                         'GROUND_DIAGNOSTIC_ROWS_OR_RESERVE')
                compiles=[(path,self.doc(path)) for path in sorted(a.glob('compile-*.json'))]
                compiles=[(path,record) for path,record in compiles if record['module']==self.runtime_representation['ground_result_module']]
                need(len(compiles)==len(attempts),'GROUND_NUMERIC_ATTEMPT_COUNT_MISMATCH')
                for t,(path,record) in zip(attempts,compiles):
                    source=self.read(path.with_suffix('.lean'));process=record['process'];self.compile_process(process)
                    need(t['probe_source_hash']==process['input']['module_source_sha256']==sha(source) and
                         type(t['compiler_exit_code']) is int and t['compiler_exit_code']==process['returncode'] and
                         t['compiler_ok']==record['ok'] and t['timed_out']==record['timed_out']==process['timed_out'],
                         'GROUND_EXACT_ATTEMPT_SOURCE_PROCESS_DIAGNOSTIC_UNBOUND')
                response=self.doc(a/'kernel-response.json');request=self.doc(a/'kernel-request.json')
                theorem=[t for t in response['constants'] if t['name']==[self.runtime_representation['ground_result_module'],'result']]
                need(len(theorem)==1 and theorem[0]['kind']=='theorem' and theorem[0]['safety']=='safe' and theorem[0]['level_params']==[] and
                     theorem[0]['unresolved_constants']==[] and len(response['defeq'])==1 and response['defeq'][0]['id']=='ground-result' and
                     request['defeq'][0]['theorem']==[self.runtime_representation['ground_result_module'],'result'],'GROUND_EXACT_SAFE_RESULT_OR_DEFEQ_MISSING')
                definitive+=1
        need(definitive==16,'GROUND_CURRENT_OBSERVATIONS_MISSING')
        comparison=self.doc(d/'clean-comparison.json');need(comparison['clean_builds']==2 and len(comparison['exact_inventory'])==8 and
             comparison['inventory_hash']==digest(comparison['exact_inventory']),'GROUND_CLEAN_PROJECTION_HASH')
        units=self.doc(d/'units-results.json');need(units['registry']==g['unit_ids'] and units['executed']==15 and
             set(units['results'])==set(g['unit_ids']) and all(x['status']=='PASS' for x in units['results'].values()),'GROUND_EXACT_UNIT_CONTROLS_NOT_EXECUTED')
        need([x['id'] for x in r['controls']]==[x['id'] for x in g['negative_controls']],'GROUND_16_CONTROL_INVENTORY')
        for control in r['controls']:
            self.doc(d/control['evidence'])
            if control['evidence']=='units-results.json':need(control['executed_test_ids'] and all(t in g['unit_ids'] for t in control['executed_test_ids']),'GROUND_CONTROL_UNMAPPED')
        raw=self.report['actual_predicate_groups']['ground']['actual_predicates']
        need(raw['current_exact_case_count']==[8,8] and raw['exact_controls']==r['controls'] and raw['actual_axioms']==r['actual_axioms'] and
             raw['omission_guards']['status']=='VERIFIED','GROUND_REGISTERED_RAW_ADMISSION_PROJECTION_MISSING')
        need(r['inputs_unchanged'] is True and r['environment_unchanged'] is True and r['native_or_model_calls']==0 and r['forbidden_task_oracles_read'] is False,'GROUND_AUTHORITY_OR_INPUT_MUTATION')
        return {'current_exact_observations':16,'baseline_cases':8,'registered_control_ids':[x['id'] for x in r['controls']],
                'registered_source_ast_dependency_frontier_admission':raw,'exact_kernel_theorem_rows_checked':True}

    def collection_marker_paths(self, stdout):
        """Only standalone markers or exact registered unittest display prefixes."""
        marker_spec = self.registered_doc(self.adapters['marker_specification'])
        need(marker_spec['collection_id'] == COLLECTION and marker_spec['closure_id'] == CLOSURE,
             'MARKER_SPECIFICATION_WRONG_COLLECTION_OR_ROOT')
        class_name, method_name = COLLECTION.rsplit('.', 1)
        prefix = method_name + ' (' + class_name + ') ... '
        need(marker_spec['exact_display_prefix'] == prefix, 'MARKER_PREFIX_NOT_DERIVED_FROM_COLLECTION_ID')
        markers = ('COLLECTION_TIER2_FROZEN_ATTEMPT_CAPTURE', 'COLLECTION_TIER2_RETAINED_CHECK_CAPTURE')
        need(marker_spec['markers'] == list(markers), 'REGISTERED_MARKER_INVENTORY_CHANGED')
        found = {marker: [] for marker in markers}
        for line in stdout.splitlines():
            if not any(marker in line for marker in markers):
                continue
            admitted = False
            for marker in markers:
                match = re.fullmatch('(?:' + re.escape(prefix) + ')?' + re.escape(marker) + r' (\S+)', line)
                if match is None:
                    continue
                value = match.group(1)
                path = Path(value)
                need(path.is_absolute() and '..' not in path.parts and path.as_posix() == value,
                     'COLLECTION_MARKER_PATH_NOT_CANONICAL_ABSOLUTE')
                found[marker].append(value)
                admitted = True
                break
            need(admitted, 'COLLECTION_MARKER_LINE_NOT_EXACT_REGISTERED_FORM')
        need(all(len(found[marker]) == 1 for marker in markers), 'FRESH_COLLECTION_MARKERS_MISSING_OR_DUPLICATED')
        return tuple(found[marker][0] for marker in markers)

    def collection(self):
        log=self.read(GATE/'registered-suite.stdout.log').decode('utf-8','strict')
        capture_value,annex_value=self.collection_marker_paths(log)
        capture,annex=Path(capture_value),Path(annex_value);need(capture.parent==annex.parent and capture.is_relative_to(ROOT/'validation') and
             capture.name.startswith('frozen-attempt-') and annex.name.startswith('retained-check-'),'COLLECTION_MARKER_PATH_INVALID')
        receipt=self.doc(capture/'capture.json');retained=self.doc(annex/'result.json')
        need(receipt['source_hashes']==self.hashes and receipt['source_root']==self.input_root and receipt['source_freeze_hash']==sha(self.read(GATE/'qualification-inputs.json')),
             'COLLECTION_NOT_FRESH_WHOLE_ROOT')
        for p,h in receipt['files'].items():self.read(p,h,base=capture)
        need(retained['attempt']==capture.relative_to(ROOT).as_posix() and retained['capture_hash']==sha(self.read(capture/'capture.json')) and
             retained['original_temporary_root_removed'] is True and retained['registered_actual_builds']=='A,B' and retained['error'] is None,
             'RETAINED_REMOVAL_OR_BUILD_BINDING_MISSING')
        engineering=self.doc(FINAL/'engineering-record.json');pkg=Path(engineering['package'])
        need(pkg==capture/'package' and engineering['source_root']==self.source_root and engineering['source_freeze']==str(GATE/'source-freeze.json') and
             engineering['source_freeze_sha256']==sha(self.read(GATE/'source-freeze.json')),'ENGINEERING_SOURCE_OR_PACKAGE_STALE')
        members=engineering['package_files'];need(digest(members)==engineering['package_files_root'],'ENGINEERING_PACKAGE_MAP_ROOT')
        for p,h in members.items():self.read(p,h,base=pkg)
        actual={p.relative_to(pkg).as_posix() for p in pkg.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith(('.pyc','.lock'))}
        need(actual==set(members),'ENGINEERING_PACKAGE_MAP_INCOMPLETE')
        meta=self.doc(pkg/'package.json');report_member=meta.get('artifacts',{}).get('report','report.json')
        need(report_member in members and members[report_member]==engineering['report_sha256'],'ENGINEERING_NATIVE_REPORT_UNBOUND')
        native=self.doc(report_member,engineering['report_sha256'],base=pkg)
        pointer=self.doc(pkg/'closure/current.json');member=engineering['mechanical_result']
        need(pointer['mechanical_result']==member and member in members and members[member]==engineering['mechanical_result_sha256'],'ENGINEERING_MECHANICAL_RESULT_UNBOUND')
        mechanical=self.doc(member,engineering['mechanical_result_sha256'],base=pkg);execution=(pkg/member).parent
        need(mechanical['closure_root']==engineering['closure_root'] and mechanical['closure_id']==engineering['closure_id'] and
             native['builds']==engineering['builds']==mechanical['builds'] and native['determinism']==engineering['determinism']==mechanical['determinism'],
             'NATIVE_ENGINEERING_MECHANICAL_CHAIN_DISAGREES')
        rows=mechanical['execution_inventory'];need([r['path'] for r in rows]==sorted(set(r['path'] for r in rows)),'MECHANICAL_INVENTORY_DUPLICATE')
        for row in rows:self.read(row['path'],row['sha256'],row['size'],execution)
        builds=mechanical['builds'];need([b['build'] for b in builds]==['A','B'] and builds[0]['outputs']==builds[1]['outputs'] and
             mechanical['determinism']['mismatches']==[] and mechanical['dependencies']['undeclared']==[],'OUTER_AB_OR_DETERMINISM_UNRESOLVED')
        outer_receipts={}
        for b in builds:
            label=b['build'];need(b['ok'] is True and b['errors']==[] and b['closure_root']==engineering['closure_root'] and b['producer']['verifier_hash'],'OUTER_BUILD_FAILED_OR_UNBOUND')
            need(self.doc(execution/'builds'/(label+'.json'))==b,'BUILD_OBSERVATION_CHANGED')
            semantic=execution/'builds'/label/'semantic';certificate=self.doc(semantic/'certificate.json')
            record=self.doc(certificate['evidence']['path'],certificate['evidence']['sha256'],base=semantic)
            raw=self.doc(record['raw_result_ref'],record['raw_result_hash'],base=semantic)
            inventory=raw['result']['compile_process_evidence'] if 'result' in raw else raw['compile_process_evidence']
            need(inventory['format']=='verislop.vscore-compile-process-inventory/1' and set(inventory['builds'])=={'A','B'},'OUTER_PROCESS_INVENTORY_MISSING')
            need(inventory['builds']['A']==inventory['builds']['B'],'EXPECTED_INNER_RECEIPT_ALIAS_CHANGED')
            process_map=inventory['builds']['A'];need(process_map,'OUTER_BUILD_HAS_NO_NUMERIC_COMPILER_RECEIPTS')
            for module,envelope in process_map.items():
                need(envelope['availability']=='available' and envelope['record'] is not None,'OUTER_COMPILER_PROCESS_UNAVAILABLE')
                self.compile_process(envelope['record'])
                need(envelope['record']['input']['module']==module.removeprefix('BASE::').removeprefix('SELECTED::'),'COMPILE_MODULE_IDENTITY_UNBOUND')
            support=b['outputs']['readable_support']['descriptor']
            need(support['mode']=='CHECKED' and support==certificate['readable_support'],'REGISTERED_CHECKED_FIXTURE_SELECTION_MISSING')
            admitted=b['outputs']['semantic_build']['compiles']
            need(admitted,'ADMITTED_SEMANTIC_COMPILE_INVENTORY_MISSING')
            for module,observation in admitted.items():
                need(observation['ok'] is True and observation['errors']==[] and observation['sorries']==0,'ADMITTED_COMPILE_NOT_SUCCESS')
                envelope=process_map.get('SELECTED::'+module)
                need(envelope and envelope['record']['returncode']==0 and envelope['record']['timed_out'] is False,'ADMITTED_SELECTED_NUMERIC_PROCESS_MISSING')
            outer_receipts[label]={m:process_map['SELECTED::'+m] for m in admitted}
        # Each outer A/B is independently produced; inner aliases never count as clean builds.
        directories={label:{v['record']['working_directory'] for v in entries.values()} for label,entries in outer_receipts.items()}
        need(directories['A'] and directories['B'] and not directories['A']&directories['B'],'OUTER_A_B_PROCESS_DIRECTORIES_REUSED')
        required=[c for c in mechanical['claims'] if c['required']]
        need(required==engineering['required_claim_observations'] and all(c['outcome']=='PASS' and c['evidence_refs'] for c in required),'REQUIRED_NATIVE_CLAIM_EVIDENCE_MISSING')
        for path in (capture/'release-probe.json',annex/'retained-release-probe.json',FINAL/'actual-retained-release-probe.json'):
            probe=self.doc(path);need(probe['status']=='NOT_REPRODUCED' and probe['expected']['outcome']==probe['observed']['outcome']=='PASS','RETAINED_CONCRETE_RELEASE_PROBE_UNRESOLVED')
        need(self.doc(capture/'release-probe.json')==self.doc(annex/'retained-release-probe.json')==self.doc(FINAL/'actual-retained-release-probe.json'),'RETAINED_RELEASE_PROBE_BINDING_DIFFERS')
        need(engineering['fresh_model_calls']==0 and engineering['fixture_only'] is True and engineering['model_authoring_input'] is False,'ENGINEERING_SCOPE_LEAK')
        return {'capture':str(capture),'annex':str(annex),'authenticated_native_report':report_member,'authenticated_mechanical_result':member,
                'outer_independent_builds':['A','B'],'inner_aliases_counted_as_extra_builds':False,'numeric_compiler_module_counts':{k:len(v) for k,v in outer_receipts.items()},
                'package_files_root':engineering['package_files_root'],'original_removal_via_exact_executed_test_and_annex':True}

    def provenance(self):
        p=self.doc(FINAL/'provenance.json')
        need(len(p)==27 and [x['claim_id'] for x in p]==[c['id'] for c in self.claims], 'PROVENANCE_CLAIM_INVENTORY')
        for row,claim in zip(p,self.claims):
            need(row['registered_verifier']==claim['verifier'] and row['trusted_dependencies']==claim['dependencies_trusted'] and
                 row['inputs']['source_root']==self.source_root and row['inputs']['input_root']==self.input_root and
                 row['inputs']['registered_files']==self.hashes and row['evidence'], 'PUBLIC_CLAIM_PROVENANCE_UNBOUND:'+claim['id'])
            for e in row['evidence']: need(str(self.path(e)) in self.evidence, 'PROVENANCE_EVIDENCE_NOT_ADMITTED')
        for public in self.plan['public_claims']:
            need(public['claims'] and all(i in {c['id'] for c in self.claims} for i in public['claims']), 'ORPHAN_PUBLIC_CLAIM')
        self.rehash()
        return {'internal_claims':27,'public_claims':len(self.plan['public_claims']),'all_read_evidence_rehashed_on_exit':True}

    def rehash(self):
        need(self.inventory()==set(self.frozen['source_files']) and
             {p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').rglob('*.py')}==set(self.spec['test_sources']), 'ENTRY_EXIT_SOURCE_TEST_MAP_MUTATION')
        for path,row in list(self.evidence.items()): self.read(path,row['sha256'],row['byte_count'])

    def fresh_ref(self, entry):
        path=self.path(entry['path'])
        need(any(path.is_relative_to(ROOT/prefix) for prefix in self.spec['fresh_evidence_prefixes']), 'EVIDENCE_NOT_NEW_CURRENT_RUN:'+str(path))
        raw=self.ref(entry)
        if not path.is_relative_to(GATE):
            need(self.hashes.get(path.relative_to(ROOT).as_posix())==sha(raw), 'EXTERNAL_FRESH_FIXTURE_NOT_EXACT_FROZEN_INPUT')
        return raw

    def bound(self, value, closure=True):
        need(value['source_root']==self.source_root and value['input_root']==self.input_root and
             (not closure or value['closure_id']==CLOSURE), 'STALE_OR_UNBOUND_EVIDENCE')

    def index(self, key):
        spec_key={'equality':'actual_equality_evidence_path','carrier':'actual_channel_evidence_path',
                  'author':'actual_author_evidence_path','pure':'actual_pure_evidence_path'}[key]
        path=self.path(self.spec[spec_key]); raw=self.read(path,self.index_hashes[key])
        need(any(path.is_relative_to(ROOT/prefix) for prefix in self.spec['fresh_evidence_prefixes']), 'INDEX_NOT_CURRENT_FRESH_ROOT')
        return parse(raw)

    def actual_process(self, receipt, contract, success=True):
        self.bound(receipt,False)
        need(receipt['argv']==contract['argv'] and receipt['cwd']==str(ROOT) and
             receipt['registered_environment']==contract['environment'], 'ACTUAL_PROCESS_COMMAND_ENVIRONMENT_MISMATCH')
        number(receipt['pid'],1)
        need(type(receipt['returncode']) is int and receipt['timed_out'] is False and
             (not success or receipt['returncode']==contract['accepted_exit_code']==0), 'ACTUAL_PROCESS_NOT_NUMERIC_COMPLETION')
        need(date(self.prereg['created_utc'])<=date(receipt['started_utc'])<=date(receipt['completed_utc']), 'ACTUAL_PROCESS_PRECEDES_FREEZE')
        for stream in ('stdout','stderr'): self.fresh_ref(receipt[stream])
        return receipt

    @staticmethod
    def query(value, path):
        need(type(path) is list, 'PREDICATE_PATH_NOT_REGISTERED_LIST')
        for component in path:
            need(type(component) in (str,int), 'PREDICATE_PATH_COMPONENT_INVALID')
            if isinstance(value,list): number(component)
            value=value[component]
        return value

    def predicates(self, predicates, witnesses):
        need(type(predicates) is list and predicates, 'NO_INDEPENDENT_SEMANTIC_PREDICATE')
        for predicate in predicates:
            left=self.query(witnesses[predicate['left']['role']],predicate['left']['path'])
            right=(self.query(witnesses[predicate['right']['role']],predicate['right']['path'])
                   if 'right' in predicate else predicate.get('value'))
            op=predicate['op']
            if op=='eq': ok=type(left) is type(right) and left==right
            elif op=='ne': ok=type(left) is not type(right) or left!=right
            elif op=='length': ok=type(right) is int and len(left)==right
            elif op=='seteq': ok=type(left) is list and type(right) is list and {wire(v) for v in left}=={wire(v) for v in right}
            elif op=='contains': ok=right in left
            elif op=='empty': ok=left in ([],{},'')
            elif op=='positive': ok=type(left) is int and left>0
            elif op=='positive_length': ok=len(left)>0
            elif op=='count_kind': ok=type(left) is list and sum(row.get('kind')==right['kind'] for row in left)==number(right['count'])
            elif op=='any_field_eq': ok=type(left) is list and any(type(row.get(right['field'])) is type(right['value']) and row.get(right['field'])==right['value'] for row in left)
            else: raise Block('UNREGISTERED_PREDICATE_OPERATOR:'+str(op))
            need(ok,'INDEPENDENT_RAW_WITNESS_PREDICATE_FAILED:'+str(predicate))
        return len(predicates)

    def recipe_literals(self):
        literals=self.registered_doc(self.adapters['predicate_reader_carrier_literals'])
        source=self.read(literals['source']['path'],literals['source']['sha256'])
        protocol=self.author_protocol_module(literals)
        if "compact_protocol" in literals:
            protocol.validate_literals(source,literals,self.author_protocol_sources(literals))
        else:
            protocol.validate_literals(source,literals)
        return literals

    def author_protocol_module(self, literals):
        identity=literals['author_protocol']['reconstruction_source']
        need(type(identity) is dict and set(identity)=={'path','sha256'} and
             self.hashes.get(identity['path'])==identity['sha256'], 'AUTHOR_RECONSTRUCTION_SOURCE_NOT_FROZEN')
        path=self.path(identity['path']); self.read(path,identity['sha256'])
        definition=importlib.util.spec_from_file_location('support019_independent_author_protocol006',path)
        module=importlib.util.module_from_spec(definition)
        definition.loader.exec_module(module)
        return module

    def author_protocol_sources(self, literals):
        if "compact_protocol" not in literals:
            return {}
        identities=literals["compact_protocol"]["sources"]
        need(type(identities) is dict and set(identities)=={"generator","reader","runtime","descriptor"}, "COMPACT_SOURCE_ROLES_NOT_CLOSED")
        sources={}
        for role, identity in identities.items():
            need(type(identity) is dict and set(identity)=={"path","sha256"} and self.hashes.get(identity["path"])==identity["sha256"], "COMPACT_SOURCE_NOT_FROZEN:"+role)
            sources[role]=self.read(identity["path"],identity["sha256"])
        return sources

    def author_message(self, reference):
        literals=self.recipe_literals()
        protocol=self.author_protocol_module(literals)
        if "compact_protocol" in literals:
            return protocol.author_message(literals,reference,self.author_protocol_sources(literals))
        return protocol.author_message(literals,reference)

    def closed_view(self, view):
        need(type(view) is dict and view.get('operation') in ('inventory','field'), 'VIEW_NOT_CLOSED')
        keys={'operation','output_cap_bytes','metadata_reserve_bytes'}
        if view['operation']=='field': keys|={'selector','start_char'}
        need(set(view)==keys and 256<=number(view['output_cap_bytes'])<=8192 and
             128<=number(view['metadata_reserve_bytes'])<view['output_cap_bytes'], 'VIEW_FIELDS_OR_BOUNDS')
        if view['operation']=='field':
            need(view['selector'] in ('/system','/user') and number(view['start_char'])<=2**53-1, 'VIEW_SELECTOR_OR_CURSOR')

    def recipe(self, reference, view, first=False, outer=20000, nested=16384):
        self.closed_view(view); literal=self.recipe_literals(); c=literal['constants']
        key='verislop.exact-carrier-session/0.1:'+json.dumps({'path':reference['path'],'sha256':reference['sha256']},sort_keys=True,ensure_ascii=True,separators=(',',':'))
        pragma='// @exec: '+json.dumps({'max_output_tokens':outer},separators=(',',':'))+'\n'
        # Preserve the registered pragma's formatting exactly.
        if outer==20000: pragma=c['_EXEC_PRAGMA']
        if first:
            need(view=={'operation':'inventory','output_cap_bytes':8192,'metadata_reserve_bytes':2048}, 'FIRST_VIEW_CHANGED')
            prefix="python -I -B - <<'VERISLOP_EXACT_CARRIER_VIEW'\n"+c['READER_SOURCE']+'\nREFERENCE = json.loads('+repr(json.dumps(reference,sort_keys=True,ensure_ascii=True))+')\n'
            result=(pragma+'const OWN_KEY = '+json.dumps(key,ensure_ascii=True)+';\n'+
                    'const PREFIX = '+json.dumps(prefix,ensure_ascii=True)+';\nstore(OWN_KEY, PREFIX);\n'+
                    'const VIEW = '+json.dumps(view,sort_keys=True,ensure_ascii=True)+';\n'+c['_VIEW_GUARD'])
        else:
            result=(pragma+'const PREFIX = load('+json.dumps(key,ensure_ascii=True)+');\n'+
                    'if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }\n'+
                    'const VIEW = '+json.dumps(view,sort_keys=True,ensure_ascii=True)+';\n'+c['_NEXT_EMIT'])
        if nested!=16384:
            need(nested==256, 'UNREGISTERED_NESTED_FAULT_BUDGET')
            need(result.count('max_output_tokens: 16384')==1, 'RECIPE_FORWARD_OCCURRENCE_CHANGED')
            result=result.replace('max_output_tokens: 16384','max_output_tokens: 256')
        return result.encode('utf-8','strict')

    def fresh_fixture(self, entry):
        doc=parse(self.fresh_ref(entry['identity'])); reference=entry['reference']
        need(doc['format']=='verislop.collaboration-carrier/0.1' and reference['path']==str(self.path(entry['identity']['path'])) and
             reference['sha256']==entry['identity']['sha256'] and reference['request_sha256']==doc['request_sha256'] and
             type(doc['system']) is str and type(doc['user']) is str, 'FRESH_OWN_CARRIER_IDENTITY')
        for key in ('system','user'): doc[key].encode('utf-8','strict')
        return doc,reference

    def intact_view(self, call, fixture, reference):
        self.closed_view(call['view']); view=call['view']
        result=parse(self.fresh_ref(call['nested_result_ref'])); raw=self.fresh_ref(call['returned_output_ref'])
        need(type(result.get('exit_code')) is int and result['exit_code']==0 and 'session_id' not in result and
             type(result['output']) is str and result['output'].encode('utf-8','strict')==raw and
             'Warning: truncated output' not in result['output'], 'ACTUAL_INTACT_VIEW_NOT_COMPLETED')
        record=parse(raw)
        need(record['format']=='verislop.exact-carrier-view/0.1' and record['status']=='ok' and record['carrier_path']==reference['path'] and
             record['carrier_sha256']==reference['sha256'] and record['request_sha256']==reference['request_sha256'] and
             record['request_id']==fixture['request_id'] and record['output_cap_bytes']==view['output_cap_bytes'] and
             record['metadata_reserve_bytes']==view['metadata_reserve_bytes'] and raw==wire(record)+b'\n' and
             len(raw)<=view['output_cap_bytes'], 'ACTUAL_VIEW_IDENTITY_OR_CANONICAL_WIRE')
        if view['operation']=='inventory':
            need(record['operation']=='inventory' and len(raw)<=view['metadata_reserve_bytes'] and record['fields']==[
                 {'selector':'/'+key,'field_chars':len(fixture[key]),'field_utf8_bytes':len(fixture[key].encode('utf-8','strict')),
                  'start_char':0,'end_char':len(fixture[key])} for key in ('system','user')], 'ACTUAL_INVENTORY_MISMATCH')
            need(call['decision']=='ACCEPT' and call['cursor_before'] is None and call['cursor_after'] is None, 'INVENTORY_CURSOR_OR_DECISION')
            return record
        selector,start=view['selector'],view['start_char']; text=fixture[selector[1:]]; end=number(record['end_char'])
        need(start<=end<=len(text) and (end>start or start==len(text)), 'ACTUAL_VIEW_RANGE_OR_PROGRESS')
        numeric={'start_char':start,'end_char':end,'next_char':end,'field_chars':len(text),'field_utf8_bytes':len(text.encode('utf-8')),
                 'start_utf8_byte':len(text[:start].encode('utf-8')),'end_utf8_byte':len(text[:end].encode('utf-8')),
                 'content_chars':end-start,'content_utf8_bytes':len(text[start:end].encode('utf-8'))}
        need(all(type(record[k]) is int and record[k]==v for k,v in numeric.items()) and
             record['operation']=='field' and record['selector']==selector and record['content']==text[start:end] and
             record['field_eof'] is (end==len(text)), 'ACTUAL_ORIGINAL_SLICE_UTF8_OR_EOF_MISMATCH')
        token=len(wire(record['content']))
        need(token<=view['output_cap_bytes']-view['metadata_reserve_bytes'] and len(raw)-token+2<=view['metadata_reserve_bytes'], 'ACTUAL_VIEW_PAYLOAD_METADATA_BOUNDS')
        need(call['decision']=='ACCEPT' and type(call['cursor_before']) is int and type(call['cursor_after']) is int and
             call['cursor_before']==start and call['cursor_after']==end, 'ACTUAL_VIEW_UNVALIDATED_CURSOR')
        return record

    def channel_capture(self):
        capture=self.index('carrier'); self.bound(capture)
        need(capture['format']=='verislop.support019-observable-channel-capture/1' and capture['unavailable']==UNAVAILABLE and
             capture['cases']==['AC002-001','AC002-002','AC002-003','AC002-004'], 'CHANNEL_CAPTURE_SCOPE')
        large,large_ref=self.fresh_fixture(capture['fresh_fixture']); empty,empty_ref=self.fresh_fixture(capture['empty_fixture'])
        need(len(large['user'])>400000 and empty['system']==empty['user']=='', 'FRESH_CHANNEL_FIXTURE_DOMAIN')
        calls=capture['calls']; need(type(calls) is list and calls, 'ACTUAL_CHANNEL_CALLS_MISSING')
        for case in capture['cases']:
            need([c['case_id'] for c in calls].count(case)>0, 'CHANNEL_CASE_UNEXECUTED')
        need([c['case_id'] for c in calls]==sorted([c['case_id'] for c in calls]), 'CHANNEL_CASE_ORDER_OR_INTERLEAVING')
        for call in calls:
            need(call['unavailable']==UNAVAILABLE and type(call['actual_result_forwards']) is int and call['actual_result_forwards']==1 and call['recipe_identity_verified'] is True, 'ACTUAL_FORWARD_SCOPE')
            reference=empty_ref if call['case_id']=='AC002-004' else large_ref
            first=call['kind']=='inventory'
            expected=self.collector_recipe(reference,call['view'],call['case_id'],first,call['outer_max_output_tokens'],call['nested_max_output_tokens'])
            need(self.fresh_ref(call['submitted_code_ref'])==expected, 'ACTUAL_SUBMITTED_RECIPE_BYTES_CHANGED')
        return capture,large,large_ref,empty,empty_ref

    def capture_literals(self):
        literal=self.registered_doc(self.adapters['predicate_reader_capture_literals'])
        tree=ast.parse(self.read(literal['source']['path'],literal['source']['sha256']).decode('utf-8','strict'))
        constants={}; functions={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in literal['constants']:
                value=ast.literal_eval(node.value); constants[node.targets[0].id]=list(value) if isinstance(value,tuple) else value
            if isinstance(node,ast.FunctionDef) and node.name in literal['function_ast_hashes']:
                functions[node.name]=sha(ast.dump(node,include_attributes=False).encode())
        need(constants==literal['constants'] and functions==literal['function_ast_hashes'], 'CAPTURE_LITERAL_OR_SOURCE_FUNCTION_CHANGED')
        return literal

    def collector_recipe(self, reference, view, case_id, first=False, outer=20000, nested=16384):
        c=self.capture_literals()['constants']; need(case_id in c['CASE_IDS'], 'UNREGISTERED_COLLECTOR_CASE')
        recipe=self.recipe(reference,view,first).decode('utf-8')
        key='verislop.observable-carrier-collector-result/0.1:'+json.dumps({'case_id':case_id,'path':reference['path'],'sha256':reference['sha256']},sort_keys=True,ensure_ascii=True,separators=(',',':'))
        observer=(c['NORMAL_ACTUAL_RESULT']+'\ntext(ACTUAL_RESULT);\nstore('+json.dumps(key,ensure_ascii=True)+', {result: ACTUAL_RESULT, view: VIEW});')
        lines=recipe.split('\n'); need(lines.count(c['NORMAL_FORWARD'])==1, 'EXACT_FORWARDING_SOURCE_LINE_NOT_UNIQUE')
        recipe='\n'.join(observer if line==c['NORMAL_FORWARD'] else line for line in lines)
        if (outer,nested)!=(20000,16384):
            need(not first and view==c['FAULT_VIEW'], 'FAULT_VIEW_NOT_REGISTERED')
            if (case_id,outer,nested)==('AC002-002',20000,256):
                lines=recipe.split('\n'); need(lines.count(c['NORMAL_ACTUAL_RESULT'])==1, 'EXACT_NESTED_FAULT_LINE_NOT_UNIQUE')
                recipe='\n'.join(c['FAULT_ACTUAL_RESULT'] if line==c['NORMAL_ACTUAL_RESULT'] else line for line in lines)
            else:
                need((case_id,outer,nested)==('AC002-003',256,16384) and recipe.startswith(c['NORMAL_PRAGMA']), 'FAULT_OUTER_BUDGET_NOT_REGISTERED')
                recipe=c['FAULT_PRAGMA']+recipe[len(c['NORMAL_PRAGMA']):]
        return recipe.encode('utf-8','strict')

    def carrier_full(self):
        capture,fixture,reference,_,_=self.channel_capture()
        full=[c for c in capture['calls'] if c['case_id']=='AC002-001']
        need(full[0]['kind']=='inventory' and full[0]['view']['operation']=='inventory' and all(c['outer_max_output_tokens']==20000 and
             c['nested_max_output_tokens']==16384 and c['view']['output_cap_bytes']==8192 and c['view']['metadata_reserve_bytes']==2048 for c in full), 'FULL_FIELD_NORMAL_CAPS')
        self.intact_view(full[0],fixture,reference)
        selector,cursor='/system',0; complete=[]; reconstructed={'/system':'','/user':''}
        for call in full[1:]:
            need(len(complete)<2 and call['kind']=='intact' and call['view']['selector']==selector and call['view']['start_char']==cursor, 'FULL_FIELD_ORDER_GAP_OR_DUPLICATE')
            record=self.intact_view(call,fixture,reference); reconstructed[selector]+=record['content']; cursor=record['next_char']
            if record['field_eof']:
                complete.append(selector); selector,cursor='/user',0
        need(complete==['/system','/user'] and reconstructed=={'/'+key:fixture[key] for key in ('system','user')}, 'FULL_FIELD_UNION_OR_TAIL_MISSING')
        return {'full_field_call_count':len(full),'user_decoded_chars':len(fixture['user']),'field_roots':{'/'+key:sha(fixture[key].encode()) for key in ('system','user')},'explicit_EOF':['/system','/user']}

    def carrier_faults(self):
        capture,fixture,reference,_,_=self.channel_capture(); checked=[]
        for case,kind,outer,nested in [('AC002-002','nested-fault',20000,256),('AC002-003','outer-fault',256,16384)]:
            pair=[c for c in capture['calls'] if c['case_id']==case]; need(len(pair)==2, 'ACTUAL_FAULT_RETRY_PAIR')
            fault,retry=pair
            need(fault['kind']==kind and fault['outer_max_output_tokens']==outer and fault['nested_max_output_tokens']==nested and
                 fault['decision']=='REJECT' and all(type(fault[k]) is int and fault[k]==0 for k in ('cursor_before','cursor_after')) and
                 fault['view']=={'operation':'field','selector':'/user','start_char':0,'output_cap_bytes':8192,'metadata_reserve_bytes':2048}, 'FAULT_ADVANCED_OR_BUDGET_VIEW_CHANGED')
            actual=parse(self.fresh_ref(fault['nested_result_ref'])); raw=self.fresh_ref(fault['returned_output_ref'])
            need(type(actual.get('exit_code')) is int and actual['exit_code']==0 and 'session_id' not in actual and
                 raw==actual['output'].encode('utf-8','strict'), 'FAULT_NUMERIC_COMPLETION_OR_OUTPUT_UNBOUND')
            if kind=='nested-fault':
                need(type(actual.get('original_token_count')) is int and actual['original_token_count']>nested and
                     re.search(r'Warning: truncated output \(original token count: [0-9]+\)',actual['output']), 'ACTUAL_NESTED_FAULT_NOT_OBSERVED')
            else:
                observed=self.fresh_ref(fault['rendered_observation_ref'])
                need(fault['rendered_outer_truncation_observed'] is True and fault['observation_scope']=='rendered_items_only' and
                     b'truncat' in observed.lower(), 'ACTUAL_RENDERED_OUTER_FAULT_NOT_OBSERVED')
            need(retry['kind']=='retry' and retry['outer_max_output_tokens']==20000 and retry['nested_max_output_tokens']==16384 and
                 retry['view']=={'operation':'field','selector':'/user','start_char':0,'output_cap_bytes':4096,'metadata_reserve_bytes':2048}, 'EXACT_SAME_CURSOR_RETRY_CHANGED')
            self.intact_view(retry,fixture,reference); checked.append(case)
        return {'actual_fault_retry_cases':checked,'hidden_envelope':'UNAVAILABLE','cursor_advanced_on_fault':False}

    def carrier_empty(self):
        capture,_,_,fixture,reference=self.channel_capture()
        zero=[c for c in capture['calls'] if c['case_id']=='AC002-004']
        need(len(zero)==3 and zero[0]['kind']=='inventory' and zero[0]['view']['operation']=='inventory' and
             all(c['outer_max_output_tokens']==20000 and c['nested_max_output_tokens']==16384 for c in zero), 'ACTUAL_EMPTY_INVENTORY_PLUS_TWO_FIELDS')
        self.intact_view(zero[0],fixture,reference)
        for call,selector in zip(zero[1:],('/system','/user')):
            need(call['kind']=='intact' and call['view']['selector']==selector and call['view']['start_char']==0, 'EMPTY_FIELD_ORDER')
            record=self.intact_view(call,fixture,reference)
            need(record['content']=='' and record['next_char']==record['field_chars']==record['field_utf8_bytes']==0 and record['field_eof'] is True, 'EMPTY_EXPLICIT_EOF')
        need(len(capture['calls'])==len([c for c in capture['calls'] if c['case_id']=='AC002-001'])+7, 'EXTRA_CHANNEL_CALL')
        return {'both_empty_fields_actual':True,'explicit_EOF':['/system','/user']}

    @staticmethod
    def name(components):
        need(type(components) is list and components and all(type(v) in (str,int) for v in components), 'KERNEL_NAME_NOT_STRUCTURED')
        return '.'.join(str(v) for v in components)

    def canon(self, expr, levels):
        if isinstance(expr,list): return [self.canon(v,levels) for v in expr]
        if not isinstance(expr,dict): return expr
        if 'param' in expr and len(expr)==1:
            name=self.name(expr['param'])
            return {'param_index':levels.index(name)} if name in levels else {'param':name}
        if 'const' in expr: return {'const':self.name(expr['const']),'levels':self.canon(expr['levels'],levels)}
        return {k:self.canon(v,levels) for k,v in expr.items() if k!='name'}

    def declaration_hash(self, row):
        levels=[self.name(n) for n in row.get('level_params',[])]
        identity={'kind':row['kind'],'safety':row.get('safety'),'num_level_params':len(levels),'type':self.canon(row['type'],levels)}
        if row['kind'] in ('definition','opaque'): identity['value']=self.canon(row['value'],levels)
        if row['kind']=='inductive':
            identity['inductive']=dict(row['inductive'])
            for k in ('all','ctors'): identity['inductive'][k]=[self.name(n) for n in identity['inductive'][k]]
        if row['kind']=='constructor':
            identity['constructor']=dict(row['constructor']); identity['constructor']['induct']=self.name(identity['constructor']['induct'])
        return digest(identity)

    def environment(self, exported, policy):
        imp=exported['import']; replay=exported['replay']
        need(imp['ok'] is True and replay['ok'] is True and
             (not imp.get('is_module_system') or imp['load_level']=='private'), 'EQUALITY_KERNEL_IMPORT_OR_REPLAY_REJECTED')
        for imported in imp.get('direct_imports',[]):
            need(imported and str(imported[0]) in policy['allowed_import_roots'], 'EQUALITY_UNDECLARED_IMPORT')
        constants=exported['constants']; need(type(constants) is list and constants, 'EQUALITY_EXPORTED_DECLARATIONS_MISSING')
        declarations={}; skipped={self.name(n) for n in replay.get('not_replayed_unsafe_or_partial',[])}
        actual={self.name(r['name']):r for r in constants if r.get('kind')!='missing_after_replay' and 'export_error' not in r}
        need(len(actual)==len([r for r in constants if r.get('kind')!='missing_after_replay' and 'export_error' not in r]), 'EQUALITY_DUPLICATE_DECLARATION')
        for row in constants:
            name=self.name(row['name']); need('export_error' not in row, 'EQUALITY_DECLARATION_EXPORT_ERROR')
            if row['kind']=='missing_after_replay':
                parent=self.name(row['replayed_parent']); p=actual.get(parent,{})
                need(row['replay_exclusion']=='runtime_auxiliary' and name in skipped and row['omitted_kind']=='definition' and
                     row['safety'] in ('unsafe','partial') and name==parent+'._unsafe_rec' and p.get('kind')=='definition' and p.get('safety')=='safe', 'EQUALITY_INVALID_RUNTIME_EXCLUSION')
                continue
            need(not (row['kind']=='axiom' and policy['forbid_module_axioms']), 'EQUALITY_MODULE_AXIOM')
            declarations[name]=row
        return declarations,{name:self.declaration_hash(row) for name,row in declarations.items()}

    def constants_in(self, expr):
        if isinstance(expr,list): return set().union(*(self.constants_in(v) for v in expr)) if expr else set()
        if not isinstance(expr,dict): return set()
        result={self.name(expr['const'])} if 'const' in expr else set()
        for value in expr.values(): result|=self.constants_in(value)
        return result

    def semantic_closure(self, root, declarations):
        pending=[root]; seen=set()
        while pending:
            name=pending.pop()
            if name in seen or name not in declarations: continue
            seen.add(name); row=declarations[name]; refs=self.constants_in(row['type'])
            if row['kind'] in ('definition','opaque'): refs|=self.constants_in(row['value'])
            if row['kind']=='inductive': refs|={self.name(v) for v in row['inductive']['ctors']}
            if row['kind']=='constructor': refs.add(self.name(row['constructor']['induct']))
            pending.extend(refs-seen)
        return seen

    def equality_file(self, entry, index):
        if isinstance(entry,str): path=self.path(entry); name=path.relative_to(ROOT).as_posix(); expected=index['files'][name]
        else:
            path=self.path(entry['path']); name=path.relative_to(ROOT).as_posix(); expected=index['files'][name]
            if 'sha256' in entry: need(entry['sha256']==expected, 'EQUALITY_WITNESS_REF_NOT_PRODUCER_MANIFEST')
        return self.fresh_ref({'path':name,'sha256':expected})

    @staticmethod
    def normalized_kernel_response(response):
        response=copy.deepcopy(response)
        for module in response.get('import',{}).get('modules',[]):
            if module.get('name')==['VeriSlopContract']: module['olean']='<staged candidate module>'
        return response

    def module_parts(self, raw):
        magic=b'VERISLOP-LEAN-MODULE-BUNDLE-1\n'
        if not raw.startswith(magic): return {'VeriSlopContract.olean':raw}
        bundle=parse(raw[len(magic):])
        need(set(bundle)=={'format','module','files'} and bundle['format']=='verislop.lean-module/1' and
             bundle['module']=='VeriSlopContract' and wire(bundle)==raw[len(magic):], 'EQUALITY_MODULE_BUNDLE_ENVELOPE')
        names=['VeriSlopContract.olean','VeriSlopContract.olean.server','VeriSlopContract.olean.private']
        need(type(bundle['files']) is list and len(bundle['files'])==3, 'EQUALITY_MODULE_BUNDLE_PART_COUNT')
        parts={}
        for row,name in zip(bundle['files'],names):
            need(set(row)=={'name','sha256','content_b64'} and row['name']==name, 'EQUALITY_MODULE_BUNDLE_PART_ORDER')
            data=base64.b64decode(row['content_b64'],validate=True)
            need(len(data)<=64*1024*1024 and sha(data)==row['sha256'], 'EQUALITY_MODULE_BUNDLE_PART_HASH_SIZE')
            parts[name]=data
        return parts

    def equality_inputs(self):
        if self.equality_cache is not None:
            # Reauthenticate cached input identities; cache is a parsed byte snapshot only.
            for path,row in list(self.evidence.items()): self.read(path,row['sha256'],row['byte_count'])
            return self.equality_cache
        ix=self.index('equality'); self.bound(ix,False)
        need(ix['format']=='verislop.support019-equality-observations/1' and ix['status']=='OBSERVED' and
             ix['models_called']==0 and ix['task_inputs'] is False and ix['qualification_authority'] is False, 'EQUALITY_PRODUCER_SCHEMA_OR_SCOPE')
        need(ix['installed_source_sha256']==self.hashes['verislop/contract_refutation.py'], 'EQUALITY_INSTALLED_SOURCE_HASH')
        self.read('verislop/contract_refutation.py',ix['installed_source_sha256'])
        producer=self.adapters['equality_producer_path']; self.read(producer,self.hashes[producer])
        need(set(ix['reports'])=={'original-main','original-additional','private-binding'} and len(ix['processes'])==3, 'EQUALITY_RUN_INVENTORY')
        contracts=self.adapters['equality_case_contracts']; registration=self.doc(self.adapters['control_registration'])
        labels=registration['equality_original44']+registration['equality_new11']
        need(len(labels)==len(set(labels))==55 and set(contracts)==set(labels), 'EQUALITY_EXACT55_CONTRACT_INVENTORY')
        files=ix['files']; need(type(files) is dict and files, 'EQUALITY_FILE_MANIFEST_MISSING')
        for path,expected in files.items(): self.equality_file(path,ix)
        allcases={}; runs={}; previous=date(self.prereg['created_utc'])
        for run_id,receipt in zip(('original-main','original-additional','private-binding'),ix['processes']):
            expected=self.adapters['equality_child_processes'][run_id]
            need(receipt['argv']==expected['argv'] and receipt['cwd']==str(ROOT) and receipt['timeout_seconds'] is None and
                 number(receipt['pid'],1)>0 and type(receipt['returncode']) is int and receipt['returncode']==0 and receipt['timed_out'] is False, 'EQUALITY_CHILD_PROCESS_NOT_COMPLETED')
            self.bound(receipt,False)
            need(previous<=date(receipt['started_utc'])<=date(receipt['completed_utc']), 'EQUALITY_CHILD_SERIAL_OR_FREEZE')
            previous=date(receipt['completed_utc'])
            for stream in ('stdout','stderr'): self.equality_file(receipt[stream],ix)
            report=parse(self.equality_file(ix['reports'][run_id],ix)); rows=report['cases']
            need(type(report['failed']) is int and report['failed']==0 and report['qualification_authority'] is False and
                 report['status'] in ('DEVELOPMENT_ONLY','DEVELOPMENT_ONLY_RELEVANT_REGRESSIONS'), 'EQUALITY_RUN_CASE_FAILURE_OR_AUTHORITY')
            directory=self.path(ix['reports'][run_id]['path']).parent
            environment=parse(self.equality_file((directory/'environment.json').relative_to(ROOT).as_posix(),ix))
            need(environment['toolchain']==self.spec['toolchain'] and environment['kernel_tool_hash']==self.spec['kernel_tool_hash'], 'EQUALITY_ENVIRONMENT_STALE')
            source_freeze=parse(self.equality_file((directory/'source-freeze-at-start.json').relative_to(ROOT).as_posix(),ix))
            source_map=self.adapters['equality_source_freeze_map'][run_id]
            if run_id=='original-main':
                need(set(source_map)=={'candidate_sha256','test_sha256'} and
                     set(source_freeze)==set(source_map)|{'status','root003_reusable'} and
                     source_freeze['status']=='DEVELOPMENT_ONLY' and source_freeze['root003_reusable'] is False,
                     'EQUALITY_MAIN_SOURCE_FREEZE_METADATA_OR_INVENTORY')
            else:
                need(set(source_freeze)==set(source_map), 'EQUALITY_SOURCE_FREEZE_EXACT_MAP_REQUIRED')
            for name,mapped in source_map.items():
                expected_hash=source_freeze[name]
                need(expected_hash==self.hashes[mapped], 'EQUALITY_SOURCE_COPY_NOT_CURRENT')
                self.read(mapped,expected_hash)
            processes=[]; compiles=[]; kernels=[]
            for name in sorted(files):
                p=ROOT/name
                if not p.is_relative_to(directory): continue
                rel=p.relative_to(directory).as_posix()
                if re.fullmatch(r'processes/[0-9]{5}/process.json',rel):
                    row=parse(self.equality_file(name,ix)); actual=row['result']; invocation=parse(self.equality_file((p.parent/'invocation.json').relative_to(ROOT).as_posix(),ix))
                    need(all(invocation[k]==row[k] for k in ('id','label','kind','requested_argv','working_directory','requested_options')) and
                         type(actual['returncode']) is int and actual['timed_out'] is False and row['requested_argv'], 'EQUALITY_RAW_PROCESS_OR_INVOCATION')
                    for stream in ('stdout','stderr'):
                        raw=self.equality_file((p.parent/(stream+'.bin')).relative_to(ROOT).as_posix(),ix)
                        need(actual[stream]['sha256']==sha(raw) and number(actual[stream]['bytes'])==len(raw), 'EQUALITY_RAW_PROCESS_OUTPUT_HASH')
                    if row['kind']=='kernel':
                        need(actual['returncode']==0, 'EQUALITY_KERNEL_PROCESS_FAILED')
                        row['_request']=parse(self.equality_file((p.parent/'request.json').relative_to(ROOT).as_posix(),ix))
                        row['_response']=self.normalized_kernel_response(parse(self.equality_file((p.parent/'response.json').relative_to(ROOT).as_posix(),ix)))
                        tool=self.equality_file((p.parent/'VeriSlopKernel.lean').relative_to(ROOT).as_posix(),ix)
                        need(sha(tool)==self.spec['kernel_tool_hash'], 'EQUALITY_ACTUAL_KERNEL_TOOL_SOURCE_CHANGED')
                    row['_directory']=p.parent; processes.append(row)
                elif re.fullmatch(r'compiles/[0-9]{5}.json',rel):
                    row=parse(self.equality_file(name,ix)); self.compile_process(row['result']['process_evidence'])
                    need(row['source_sha256']==row['result']['process_evidence']['input']['module_source_sha256'], 'EQUALITY_COMPILER_SOURCE_BINDING')
                    compiles.append(row)
                elif re.fullmatch(r'kernels/[0-9]{5}.json',rel): kernels.append(parse(self.equality_file(name,ix)))
            need(number(report['actual_processes'])==len(processes) and number(report['actual_compiler_calls'])==len(compiles) and
                 number(report['actual_kernel_calls'])==len(kernels), 'EQUALITY_LEDGER_INVENTORY_COUNTS')
            for row in rows:
                need(row['label'] not in allcases and row['status']=='PASS', 'EQUALITY_DUPLICATE_OR_FAILED_CASE')
                allcases[row['label']]=(run_id,row)
            runs[run_id]={'directory':directory,'environment':environment,'processes':processes,'compiles':compiles,'kernels':kernels}
        need(set(allcases)==set(labels), 'EQUALITY_ORIGINAL44_NEW11_LABELS_CHANGED')
        self.equality_cache=(ix,contracts,allcases,runs,registration)
        return self.equality_cache

    def equality_witnesses(self, contract, ix):
        case=contract['witness_case']; result=parse(self.equality_file(case['result_path'],ix)); witnesses={'result':result}
        for role,entry in case['witness_paths'].items():
            raw=self.equality_file(entry['path'],ix)
            need(entry['encoding'] in ('json','raw','bytes','utf8'), 'EQUALITY_WITNESS_ENCODING_NOT_REGISTERED')
            witnesses[role]=parse(raw) if entry['encoding']=='json' else raw if entry['encoding'] in ('raw','bytes') else raw.decode('utf-8','strict')
            if 'select' in entry:
                need(entry['encoding']=='json' and type(entry['select']) is list and len(entry['select'])==len(set(entry['select'])), 'EQUALITY_SELECTED_IDENTITY_INVALID')
                witnesses[role]={key:witnesses[role][key] for key in entry['select']}
        need(set(contract['required_witness_roles']).issubset(witnesses), 'EQUALITY_MISSING_SUBSTANTIVE_WITNESS')
        return result,witnesses,case

    def receipt(self, receipt, result, witnesses, case, run, ix, label):
        need(receipt['ok'] is True and receipt['status']==self.adapters['equality_case_contracts'][label]['expected_receipt_status'], 'EQUALITY_RECEIPT_DISPOSITION')
        stripped=dict(receipt); recorded=stripped.pop('receipt_hash'); need(digest(stripped)==recorded, 'EQUALITY_RECEIPT_HASH')
        keys=('candidate_source_hash','formalization_hash','records_hash','analysis_hash','proposals_hash')
        need(receipt['binding']=={key:result[key] for key in keys}, 'EQUALITY_RECEIPT_EXACT_BINDING')
        package=ROOT/case['package_root']; need(package.is_absolute() and '..' not in package.parts and package.resolve()==package.absolute(), 'EQUALITY_PACKAGE_ROOT_NOT_CANONICAL')
        artifacts={}
        for role,entry in receipt['artifacts'].items():
            need(type(entry['path']) is str and not Path(entry['path']).is_absolute() and '..' not in Path(entry['path']).parts, 'EQUALITY_ARTIFACT_PATH')
            path=(package/entry['path']).relative_to(ROOT).as_posix(); raw=self.equality_file(path,ix)
            need(sha(raw)==entry['sha256'], 'EQUALITY_RECEIPT_ARTIFACT_HASH'); artifacts[role]=raw
        need(set(artifacts)=={'source','compiled_module','kernel_export'}, 'EQUALITY_PROOF_ARTIFACT_INVENTORY')
        if label in ('revised-private-only-safe-fallback','revised-no-equality-safe-fallback','revised-private-plus-public-reuse'):
            text=artifacts['source'].decode('utf-8','strict'); namespace=receipt['lean_symbol'].rsplit('.',1)[0]
            need(text.count('\nnamespace '+namespace+'\n')==1, 'PRIVATE_EQUALITY_PROOF_NAMESPACE_AMBIGUOUS')
            tail=text.split('\nnamespace '+namespace+'\n',1)[1]
            derivation='deriving instance _root_.DecidableEq for _root_.«PrivateEqualityRevision019».«Palette»'
            if label=='revised-private-plus-public-reuse':
                need(derivation not in tail and ' := _root_.«zzUsableEquality»' in tail, 'PRIVATE_PUBLIC_REUSE_NOT_EXACT')
            else: need(derivation in tail and 'local instance' not in tail, 'PRIVATE_OR_ABSENT_EQUALITY_NOT_SAFE_FALLBACK')
        exported=parse(artifacts['kernel_export']); policy=run['environment']['policy']; declarations,hashes=self.environment(exported,policy)
        baseline=witnesses['baseline_export']; _,basehashes=self.environment(baseline,policy)
        need(all(hashes.get(n)==h for n,h in basehashes.items()), 'EQUALITY_BASE_DECLARATION_CHANGED')
        root=receipt['lean_symbol']; row=declarations[root]
        need(row['kind']=='theorem' and row['safety']=='safe' and row['level_params']==[] and row['unresolved_constants']==[] and
             type(row['axioms']) is list and row['axioms']==receipt['axioms']==[] and
             type(receipt['refutation_sorry_dependencies']) is int and receipt['refutation_sorry_dependencies']==0 and
             hashes[root]==receipt['declaration_hash'], 'EQUALITY_ROOT_SAFE_EXACT_OR_DEPENDENCY')
        closure=self.semantic_closure(root,declarations); form=witnesses['formalization']
        forbidden={b['theorem'] for b in form['bindings'] if 'theorem' in b}
        need(not (closure&forbidden) and all(declarations[n].get('safety') not in ('unsafe','partial') and
             'sorryAx' not in [self.name(a) for a in declarations[n].get('axioms',[])] and
             not (n.startswith('_private.') and n.endswith('.hiddenEquality')) for n in closure), 'EQUALITY_FORBIDDEN_TRANSITIVE_DEPENDENCY')
        defeq=exported['defeq']; expected={'ok':True,'typechecks':True,'defeq':True}
        need(len(defeq)==1 and defeq[0]['id']=='closed_check' and defeq[0]['result']==receipt['kernel_defeq']==expected, 'EQUALITY_EXACT_DEFEQ_RESULT')
        matched=[k for k in run['kernels'] if k['response']==exported and k['request'].get('export') is True and k['request'].get('axioms') is True]
        need(matched, 'EQUALITY_EXPORT_NOT_ACTUAL_KERNEL_LEDGER')
        matched=[k for k in matched if len(k['request'].get('defeq',[]))==1 and k['request']['defeq'][0]['id']=='closed_check' and
                 self.name(k['request']['defeq'][0]['theorem'])==root and digest(k['request']['defeq'][0]['expr'])==receipt['proposition_hash']]
        actual_kernels=[p for p in run['processes'] if p.get('_response')==exported and p['kind']=='kernel' and
                       p['_request'].get('module')=='VeriSlopContract' and p['_request'].get('export') is True and p['_request'].get('axioms') is True and
                       any(p['_request'].get('defeq')==k['request']['defeq'] for k in matched)]
        need(matched and actual_kernels, 'EQUALITY_RECORDED_PROPOSITION_OR_RAW_KERNEL_PROCESS')
        sourcehash=sha(artifacts['source']); modulehash=sha(artifacts['compiled_module'])
        compilers=[c for c in run['compiles'] if c['source_sha256']==sourcehash and c['result']['ok'] is True and c['result']['process_evidence']['returncode']==0]
        need(compilers, 'EQUALITY_PROOF_SOURCE_NOT_ACTUAL_COMPILATION')
        copied=[]
        for compile_row in compilers:
            name=(run['directory']/'compiled-artifacts'/('%05d'%compile_row['id'])/Path(compile_row['result']['olean']).name).relative_to(ROOT).as_posix()
            data=self.equality_file(name,ix)
            if data==artifacts['compiled_module']: copied.append(compile_row)
        need(copied, 'EQUALITY_MODULE_NOT_ACTUAL_COPIED_COMPILATION')
        need(any(p['kind']=='compiler' and p['result']['returncode']==0 and any(
             sha(self.equality_file(name,ix))==sourcehash for name in ix['files'] if (ROOT/name).parent==p['_directory'] and name.endswith('.lean')) and
             any(c['result']['process_evidence']['launcher_argv']==p['result']['argv'] and
                 all(c['result']['process_evidence'][stream]['sha256']==p['result'][stream]['sha256'] for stream in ('stdout','stderr')) for c in copied)
             for p in run['processes']), 'EQUALITY_SOURCE_NOT_RAW_COMPILER_PROCESS')
        parts=self.module_parts(artifacts['compiled_module'])
        need(any(all(self.equality_file((p['_directory']/'stage'/name).relative_to(ROOT).as_posix(),ix)==data for name,data in parts.items())
             for p in actual_kernels), 'EQUALITY_MODULE_NOT_ACTUAL_KERNEL_STAGE')
        need(receipt['toolchain']==self.spec['toolchain'] and receipt['kernel_tool_hash']==self.spec['kernel_tool_hash'] and
             receipt['kernel_proof_hash']==digest({'module':modulehash,'declaration':receipt['declaration_hash'],'proposition':receipt['proposition_hash'],
                 'kernel_export':sha(artifacts['kernel_export']),'kernel_tool':receipt['kernel_tool_hash'],'toolchain':receipt['toolchain']}), 'EQUALITY_KERNEL_PROOF_HASH_OR_TOOLCHAIN')

    def equality_case(self, label, ix, contract, case_row, run):
        result,witnesses,case=self.equality_witnesses(contract,ix)
        mode=contract['mode']
        need(contract['predicates'] or mode in ('contract-report','grouped-binding'), 'NO_INDEPENDENT_CONTROL_PREDICATE')
        checked=self.predicates(contract['predicates'],witnesses) if contract['predicates'] else 0
        if contract['expected_status'] is not None:
            need(result['status']==contract['expected_status'], 'EQUALITY_EXACT_EXPECTED_STATUS:'+label)
        rawprocesses=[p for p in run['processes'] if p['label']==label]
        need(number(case_row['actual_processes'])==len(rawprocesses), 'EQUALITY_CASE_RAW_PROCESS_COUNT')
        if contract['require_actual_processes']: need(rawprocesses, 'EQUALITY_CASE_DID_NOT_ACTUALLY_EXECUTE')
        if result.get('artifact_kind')=='candidate_contract_refutation':
            stripped=dict(result); reporthash=stripped.pop('report_hash'); need(digest(stripped)==reporthash, 'EQUALITY_RAW_REPORT_HASH')
            source=witnesses['source']; source=source.encode('utf-8') if type(source) is str else source
            analysis=witnesses['analysis']; identity={key:analysis[key] for key in ('profile','statements','registry','defeq_requests')}
            need(identity==witnesses['analysis_identity'], 'EQUALITY_SUPPLIED_ANALYSIS_IDENTITY_NOT_RECOMPUTED')
            checker=witnesses['checker']; checker_path=self.path(checker['path']); checker_name=checker_path.relative_to(ROOT).as_posix()
            need(self.hashes[checker_name]==checker['sha256'] and checker['package_root']==str(ROOT/case['package_root']), 'EQUALITY_ACTUAL_CHECKER_OR_PACKAGE_NOT_BOUND')
            self.read(checker_path,checker['sha256'])
            hashes={'candidate_source_hash':sha(source),'formalization_hash':digest(witnesses['formalization']),'records_hash':digest(witnesses['records']),
                    'analysis_hash':digest(identity),'proposals_hash':digest(witnesses['proposals'])}
            need(all(result[k]==h for k,h in hashes.items()), 'EQUALITY_RAW_SOURCE_FORM_RECORDS_ANALYSIS_PROPOSALS_HASH')
            for receipt in result['receipts']: self.receipt(receipt,result,witnesses,case,run,ix,label)
            if contract['expected_receipt_status'] is not None: need(result['receipts'], 'EQUALITY_POSITIVE_RECEIPT_MISSING')
        if label in ('mismatched-semantic-analysis-exact-rejection','changed-source-semantics-exact-binding-rejection') or mode=='binding-rejection':
            need(result['status']=='UNKNOWN' and result['diagnostics']==[{'message':'source/form/records do not match the supplied kernel-derived analysis'}] and
                 type(result['bounded_scan']['proof_attempts']) is int and result['bounded_scan']['proof_attempts']==0 and result['receipts']==[], 'EQUALITY_BINDING_MUST_REJECT_BEFORE_ATTEMPTS')
        if label=='comment-only-source-semantic-equivalence' or mode=='comment-equivalence':
            need(witnesses['before_source']!=witnesses['after_source'], 'COMMENT_SOURCE_BYTE_HASH_NOT_CHANGED')
            need(wire(witnesses['semantic_identity_before'])==wire(witnesses['semantic_identity_after']) and
                 result['candidate_source_hash']==sha(witnesses['after_source']), 'COMMENT_KERNEL_SEMANTIC_IDENTITY_OR_EXACT_NEW_BYTES')
        if label=='changed-source-semantics-exact-binding-rejection':
            _,before=self.environment(witnesses['baseline_export'],run['environment']['policy'])
            changes=[]
            for process in rawprocesses:
                if process['kind']=='kernel' and process['_request'].get('export') is True:
                    _,after=self.environment(process['_response'],run['environment']['policy'])
                    changes.extend(name for name in before if name in after and before[name]!=after[name])
            need(changes, 'CHANGED_SOURCE_KERNEL_SEMANTICS_CONTROL_NOT_DISCRIMINATING')
        if label=='analysis-guard-mutant-discrimination':
            need(result['status']=='REFUTED' and result['receipts'] and number(result['bounded_scan']['proof_attempts'],1)>0 and
                 witnesses['checker']['sha256']==self.hashes[self.adapters['equality_guard_mutant_source']] and
                 witnesses['checker']['fixture_only_mutant'] is True, 'ACTUAL_FALSIFIABLE_MUTANT_NOT_DISCRIMINATING')
        if label=='source-analysis-wire-binding-negatives':
            for role in ('binding_result','changed_result'):
                raw=witnesses[role]
                need(raw['status']=='UNKNOWN' and raw['diagnostics']==[{'message':'source/form/records do not match the supplied kernel-derived analysis'}] and
                     type(raw['bounded_scan']['proof_attempts']) is int and raw['bounded_scan']['proof_attempts']==raw['bounded_scan']['cases_evaluated']==0 and raw['receipts']==[], 'GROUPED_BINDING_REJECTION_NOT_EXACT')
            need(witnesses['invalid_result']['status']=='UNKNOWN' and witnesses['invalid_result']['receipts']==[] and
                 sum(d.get('kind')=='INVALID_PROPOSAL' for d in witnesses['invalid_result']['diagnostics'])==4 and
                 witnesses['mutant_result']['status']=='REFUTED' and witnesses['mutant_result']['receipts'] and
                 witnesses['comment_result']['status']=='REFUTED', 'GROUPED_CONTROL_NONDISCRIMINATING')
            mutant_contract=copy.deepcopy(contract)
            basic=('result','source','formalization','records','analysis','analysis_identity','proposals','checker','base','baseline_export')
            mutant_contract['required_witness_roles']=list(basic)
            mutant_case_recipe=mutant_contract['witness_case']
            mutant_case_recipe['result_path']=contract['witness_case']['witness_paths']['mutant_result']['path']
            mutant_case_recipe['package_root']=mutant_case_recipe['package_root'].replace('/comment-source-equivalence','/grouped-analysis-guard-mutant')
            mutant_case_recipe['witness_paths']={role:copy.deepcopy(contract['witness_case']['witness_paths'][role]) for role in basic}
            for role,entry in mutant_case_recipe['witness_paths'].items():
                entry['path']=entry['path'].replace('/comment-source-equivalence','/grouped-analysis-guard-mutant')
            mutant,mutant_witnesses,mutant_case=self.equality_witnesses(mutant_contract,ix)
            need(mutant==witnesses['mutant_result'] and mutant_witnesses['checker']['fixture_only_mutant'] is True and
                 mutant_witnesses['checker']['sha256']==self.hashes[self.adapters['equality_guard_mutant_source']], 'GROUPED_MUTANT_SUPPLIED_INPUT_NOT_BOUND')
            for receipt in mutant['receipts']: self.receipt(receipt,mutant,mutant_witnesses,mutant_case,run,ix,label)
        if contract.get('required_structural_control'):
            checked+=self.structural_equality_control(contract['required_structural_control'],witnesses,run,label)
        return {'label':label,'independent_predicates':checked,'raw_actual_processes':len(rawprocesses),'receipt_count':len(result.get('receipts',[]))}

    def equality_original(self):
        ix,contracts,cases,runs,registry=self.equality_inputs(); checked=[]
        for label in registry['equality_original44']:
            run_id,row=cases[label]; checked.append(self.equality_case(label,ix,contracts[label],row,runs[run_id]))
        need(len(checked)==44, 'EQUALITY_ORIGINAL44_NOT_INDEPENDENTLY_CHECKED')
        return {'exact_original44':checked,'installed_equality_hash':ix['installed_source_sha256']}

    def equality_private(self):
        ix,contracts,cases,runs,registry=self.equality_inputs(); checked=[]
        for label in registry['equality_new11']:
            run_id,row=cases[label]; checked.append(self.equality_case(label,ix,contracts[label],row,runs[run_id]))
        need(len(checked)==11, 'EQUALITY_NEW11_NOT_INDEPENDENTLY_CHECKED')
        return {'exact_new11':checked,'guard_rejection_preserves_zero_attempts':True}

    def structural_equality_control(self, kind, witnesses, run, label):
        ledger=witnesses.get('structural_ledger',witnesses['result'])
        if kind=='ordered-carrier-prelude-ledger':
            none,all_=ledger['prelude_none'],ledger['prelude_all']
            # Exact qualified carrier suffixes are taken from the frozen source contract.
            positions=[none.index('«'+name+'»') for name in ('Token','ZLeaf','AParcel')]
            need(positions==sorted(positions) and len(set(positions))==3 and 'deriving instance' not in all_ and
                 ledger['prelude_before_stale_metadata']==ledger['prelude_after_stale_metadata']==all_, 'EQUALITY_PRELUDE_ORDER_OR_METADATA_AUTHORITY')
            before=copy.deepcopy(ledger['profile_before']); after=ledger['profile_after']
            need('decidable_eq' not in before['enums']['Token'] and 'decidable_eq' in after['enums']['Token'], 'EQUALITY_FAKE_METADATA_CONTROL_ABSENT')
            before['enums']['Token']['decidable_eq']=after['enums']['Token']['decidable_eq']
            need(before==after, 'EQUALITY_FAKE_METADATA_CHANGED_OTHER_PROFILE_FIELDS')
            return 5
        baseline=ledger['baseline_export']; declarations,hashes=self.environment(baseline,run['environment']['policy'])
        need(any(k['response']==baseline for k in run['kernels']) and any(p.get('_response')==baseline for p in run['processes']), 'EQUALITY_STRUCTURAL_BASE_NOT_ACTUAL_KERNEL_EXPORT')
        if kind=='direct-false-proof-ledger':
            need(ledger['binding']=={'fixture':'false closed proposition'} and witnesses['result']['ok'] is False and
                 witnesses['result']['reason']=='closed proof did not elaborate', 'EQUALITY_FALSE_PROOF_EXPECTED_BOUNDARY')
            namespace='VeriSlopRefutation_'+digest({'binding':ledger['binding'],'proposition':ledger['expr']}).removeprefix('sha256:')[:24]
            compiles=[c for c in run['compiles'] if c['label']==label and c['result']['ok'] is False and
                      c['result']['process_evidence']['timed_out'] is False and type(c['result']['process_evidence']['returncode']) is int and c['result']['process_evidence']['returncode']!=0]
            need(compiles, 'EQUALITY_FALSE_PROOF_NO_ACTUAL_FAILED_COMPILATION')
            processes=[p for p in run['processes'] if p['label']==label and p['kind']=='compiler' and p['result']['returncode']!=0]
            matched=False
            for process in processes:
                for name in self.equality_cache[0]['files'] if self.equality_cache is not None else []:
                    if (ROOT/name).parent==process['_directory'] and name.endswith('.lean'):
                        source=self.equality_file(name,self.equality_cache[0])
                        if ('namespace '+namespace+'\n').encode() in source and b'theorem closed_check :' in source and any(c['source_sha256']==sha(source) for c in compiles): matched=True
            need(matched and ledger['process_ids_before']!=ledger['process_ids_after'] and all(
                 not any(self.name(d['theorem'])==namespace+'.closed_check' for d in k['request'].get('defeq',[])) for k in run['kernels']), 'EQUALITY_FALSE_PROOF_SOURCE_OR_UNEXPECTED_ACCEPTED_KERNEL')
            return 5
        if kind=='collision-environment-ledger':
            namespace='VeriSlopRefutation_'+digest({'binding':ledger['binding'],'proposition':ledger['expr']}).removeprefix('sha256:')[:24]
            suffix='._vr_eq_0' if label=='generated-alias-name-collision-synthetic-env' else '.closed_check'
            name=namespace+suffix; changed=ledger['modified_declarations']
            need(ledger['generated_name']==name and set(changed)==set(declarations)|{name} and
                 all(changed[n]==row for n,row in declarations.items()) and changed[name]=={'name':[namespace,suffix[1:]]}, 'EQUALITY_COLLISION_SYNTHETIC_ENV_NOT_EXACT')
            before,after=ledger['process_ids_before'],ledger['process_ids_after']
            need(before==after and len(before)==len(set(before)) and all(type(v) is int and v in {p['id'] for p in run['processes']} for v in before), 'EQUALITY_COLLISION_EXECUTED_OR_FAKE_PROCESS_LEDGER')
            return 4
        need(kind=='stale-equality-environment-ledger', 'UNREGISTERED_STRUCTURAL_CONTROL')
        need(ledger['hashes_before']==hashes and ledger['equality_name'] in declarations, 'EQUALITY_STALE_BASE_HASHES_NOT_RECONSTRUCTED')
        after=dict(hashes); stale=ledger['stale_bytes']
        if type(stale) is str: stale=stale.encode('utf-8')
        need(type(stale) is bytes, 'EQUALITY_STALE_CONTROL_BYTES_NOT_LITERAL')
        after[ledger['equality_name']]=sha(stale)
        need(after==ledger['hashes_after'] and hashes[ledger['equality_name']]!=after[ledger['equality_name']] and
             'DecidableEq' in self.constants_in(declarations[ledger['equality_name']]['type']) and
             'RefutationEquality019.Token' in self.constants_in(declarations[ledger['equality_name']]['type']), 'EQUALITY_STALE_NOMINAL_OR_HASH_CONTROL_NOT_EXACT')
        need('deriving instance _root_.DecidableEq for _root_.«RefutationEquality019».«Token»' in ledger['prelude'], 'EQUALITY_STALE_ENV_NOT_SAFE_FALLBACK')
        return 4

    def fresh_author(self):
        author=self.index('author'); self.bound(author)
        need(author['format']=='verislop.support019-single-fresh-author-evidence/1' and type(author['spawn_count']) is int and
             author['spawn_count']==1 and author['requested_model']=='gpt-6.1-sol' and author['fork_turns']=='none' and
             author['model_identity']==author['semantic_consumption']=='UNATTESTED', 'AUTHOR_COUNT_REQUEST_OR_IDENTITY_OVERCLAIM')
        fixture,reference=self.fresh_fixture(author['fresh_fixture']); literal=self.recipe_literals()
        message=self.author_message(reference)
        need(self.fresh_ref(author['submitted_message_ref'])==self.fresh_ref(author['expected_literal_message_ref'])==message, 'ORIGINAL_PLAIN_AGENT_MESSAGE_BYTES_CHANGED')
        spawn=parse(self.fresh_ref(author['spawn_request_ref'])); response=parse(self.fresh_ref(author['spawn_result_ref']))
        need(type(response) is dict and set(response)=={'task_name'} and
             type(response['task_name']) is str and re.fullmatch(r'/root(?:/[a-z0-9_]+)+',response['task_name']) is not None and
             type(spawn['task_name']) is str and re.fullmatch(r'[a-z0-9_]+',spawn['task_name']) is not None and
             response['task_name'].rsplit('/',1)[1]==spawn['task_name'], 'ACTUAL_FRESH_AUTHOR_CANONICAL_TASK_NAME_NOT_BOUND')
        need(spawn['model']=='gpt-6.1-sol' and spawn['fork_turns']=='none' and type(spawn['message']) is str and
             spawn['message'].encode('utf-8')==message, 'ACTUAL_FRESH_AUTHOR_SPAWN_NOT_BOUND')
        requests=author['observed_author_requests']
        need(type(requests) is list and len(requests)==1 and type(requests[0]) is dict and
             set(requests[0])=={'spawn_request_ref','spawn_result_ref','agent_id'} and
             wire(requests[0]['spawn_request_ref'])==wire(author['spawn_request_ref']) and
             wire(requests[0]['spawn_result_ref'])==wire(author['spawn_result_ref']) and
             type(author['author_agent_id']) is str and author['author_agent_id']==requests[0]['agent_id']==response['task_name'],
             'AUTHOR_REQUEST_INVENTORY_NOT_EXACT_ONE')
        markers=list(dict.fromkeys(re.findall(literal['marker_pattern'],fixture['user'])))
        need(markers==literal['expected_markers'], 'FRESH_UNRELATED_MARKER_DOMAIN')
        expected={'markers':markers,'field_roots':{'/'+k:sha(fixture[k].encode('utf-8')) for k in ('system','user')},
                  'field_eof':{'/system':True,'/user':True},'field_chars':{'/'+k:len(fixture[k]) for k in ('system','user')}}
        final_raw=self.fresh_ref(author['literal_final_ref']); final=parse(final_raw)
        need(wire(final)==wire(expected) and wire(parse(self.fresh_ref(author['evaluator_expectations_ref'])))==wire(expected), 'LITERAL_FINAL_SYNTAX_MARKER_ROOT_TOTALS_EOF_MISMATCH')
        need(author['exposed_responses_refs'] and author['evaluator_expectations_sent_to_author'] is False and
             author['replacement_author_or_resampling'] is False, 'AUTHOR_CONTAMINATION_OR_HIDDEN_FAILURES')
        for entry in author['exposed_responses_refs']: self.fresh_ref(entry)
        return {'single_actual_spawn':response['task_name'],'literal_final_sha256':sha(final_raw),'independent_original_field_expectations':expected,
                'model_identity':'UNATTESTED','semantic_consumption':'UNATTESTED'}

    def source_pair(self, entry):
        left=self.ref(entry['left']); right=self.ref(entry['right'])
        if 'symbol' in entry:
            def selected(data):
                nodes=ast.parse(data.decode('utf-8','strict')).body
                matches=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==entry['symbol'] or
                         isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==entry['symbol'] for t in n.targets)]
                need(len(matches)==1, 'SOURCE_SYMBOL_BINDING_AMBIGUOUS')
                node=matches[0]
                if isinstance(node,ast.Assign): return ast.literal_eval(node.value)
                return ast.dump(node,include_attributes=False)
            left,right=selected(left),selected(right)
        need(entry['relation']=='equal' and type(left) is type(right) and left==right, 'REGISTERED_SOURCE_BYTE_OR_AST_IDENTITY_CHANGED')
        return {'left':entry['left']['path'],'right':entry['right']['path'],'symbol':entry.get('symbol')}

    def source_ast(self, data, symbol):
        nodes=ast.parse(data.decode('utf-8','strict')).body
        for part in symbol.split('.'):
            matches=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==part]
            need(len(matches)==1,'SOURCE_AST_SYMBOL_NOT_UNIQUE:'+symbol)
            node=matches[0]; nodes=getattr(node,'body',[])
        return ast.get_source_segment(data.decode('utf-8','strict'),node).encode('utf-8')

    def pure_read_expected(self, reference, view, raw, own_path):
        cap=view.get('output_cap_bytes',8192) if type(view) is dict else 0
        if type(cap) is not int or not 256<=cap<=8192: return b''
        def failure(code):
            data=wire({'format':'verislop.exact-carrier-view/0.1','status':'error','code':code,'next_char':None,'field_eof':False})+b'\n'
            return data if len(data)<=cap else b''
        reserve=view.get('metadata_reserve_bytes',2048)
        if type(reserve) is not int or not 128<=reserve<cap: return failure('INVALID_BOUNDS')
        if set(view)-{'operation','selector','start_char','output_cap_bytes','metadata_reserve_bytes'}: return failure('INVALID_VIEW_FIELDS')
        if type(reference) is not dict or set(reference)!={'path','sha256','request_sha256'} or any(type(v) is not str for v in reference.values()): return failure('INVALID_REFERENCE')
        if reference['path']!=own_path or not Path(reference['path']).is_absolute(): return failure('INDIRECT_PATH')
        if sha(raw)!=reference['sha256']: return failure('CARRIER_HASH_MISMATCH')
        if raw.startswith(b'\xef\xbb\xbf'): return failure('UNSUPPORTED_JSON')
        try:
            def pairs(values):
                out={}
                for k,v in values:
                    if k in out: raise Block('DUPLICATE_KEY')
                    out[k]=v
                return out
            def integer(value):
                n=int(value)
                if abs(n)>2**53-1: raise Block('UNSUPPORTED_INTEGER')
                return n
            def no_number(value): raise Block('UNSUPPORTED_NUMBER')
            doc=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=pairs,parse_float=no_number,parse_constant=no_number,parse_int=integer)
            if type(doc) is not dict or set(doc)!={'format','request_id','request_sha256','system','user'} or any(type(v) is not str for v in doc.values()): return failure('INVALID_CARRIER')
            for value in doc.values(): value.encode('utf-8','strict')
        except Block as error: return failure(str(error))
        except (UnicodeError,ValueError,TypeError,OverflowError,RecursionError): return failure('UNSUPPORTED_JSON_OR_TEXT')
        if doc['format']!='verislop.collaboration-carrier/0.1': return failure('INVALID_CARRIER_FORMAT')
        if doc['request_sha256']!=reference['request_sha256']: return failure('REQUEST_METADATA_MISMATCH')
        base={'format':'verislop.exact-carrier-view/0.1','status':'ok','carrier_path':own_path,'carrier_raw_bytes':len(raw),'carrier_sha256':sha(raw),
              'request_sha256':doc['request_sha256'],'request_id':doc['request_id'],'char_unit':'decoded_unicode_code_points','byte_unit':'decoded_field_utf8',
              'output_cap_bytes':cap,'metadata_reserve_bytes':reserve}
        operation=view.get('operation','field')
        if operation=='inventory':
            record={**base,'operation':'inventory','fields':[{'selector':'/'+key,'field_chars':len(doc[key]),'field_utf8_bytes':len(doc[key].encode()),'start_char':0,'end_char':len(doc[key])} for key in ('system','user')],'navigation':'complete_linear_fields_only'}
            data=wire(record)+b'\n'
            return data if len(data)<=reserve and len(data)<=cap else failure('METADATA_RESERVE_EXCEEDED')
        if operation!='field': return failure('INVALID_OPERATION')
        selector=view.get('selector','/system')
        if selector not in ('/system','/user'): return failure('INVALID_SELECTOR')
        text=doc[selector[1:]]; start=view.get('start_char',0)
        if type(start) is not int or not 0<=start<=len(text): return failure('INVALID_CURSOR')
        def candidate(end):
            content=text[start:end]
            record={**base,'operation':'field','selector':selector,'field_chars':len(text),'field_utf8_bytes':len(text.encode()),'start_char':start,'end_char':end,
                    'start_utf8_byte':len(text[:start].encode()),'end_utf8_byte':len(text[:end].encode()),'content_chars':end-start,'content_utf8_bytes':len(content.encode()),
                    'content':content,'next_char':end,'field_eof':end==len(text)}
            data=wire(record)+b'\n'; token=len(wire(content))
            return data,len(data)-token+2,token
        end=min(len(text),start+cap-reserve)
        # Independent finite reverse search over the registered maximum8192 span.
        while end>=start:
            data,metadata,token=candidate(end)
            if metadata<=reserve and token<=cap-reserve and len(data)<=cap:
                if end>start or start==len(text): return data
                break
            end-=1
        _,metadata,_=candidate(start)
        return failure('METADATA_RESERVE_EXCEEDED' if metadata>reserve else 'NO_CONTENT_CAPACITY')

    def pure_carrier_raw(self, frame):
        arguments=frame['arguments']; source=self.ref(frame['source_ref'])
        # Method source segments carry class indentation; dedent through AST
        # lookup directly against the authenticated complete source instead.
        tree=ast.parse(source.decode()); parts=frame['symbol'].split('.'); nodes=tree.body
        for part in parts:
            selected=[n for n in nodes if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==part]
            need(len(selected)==1,'PURE_CARRIER_SIGNATURE_BINDING'); function=selected[0]; nodes=function.body
        names=[a.arg for a in function.args.args]
        if names and names[0]=='self': names=names[1:]
        need('raw' in names,'PURE_CARRIER_RAW_PARAMETER_ABSENT')
        position=names.index('raw'); raw=arguments['keyword'].get('raw')
        if raw is None and len(arguments['positional'])>position: raw=arguments['positional'][position]
        return wire(frame['returned_value'][1])+b'\n' if raw is None else raw

    def pure_frame_relations(self, frame, own):
        if frame['kind']=='read' and frame['exception'] is None:
            args=frame['arguments']['positional']; reference,view=args[0],args[1]
            carriers=[f for f in own if f['kind']=='carrier' and f['exception'] is None and f['sequence']<frame['sequence']]
            need(carriers,'PURE_READ_HAS_NO_CAPTURED_OWN_CARRIER')
            selected=next((f for f in reversed(carriers) if f['returned_value'][0]['path']==reference.get('path')),carriers[-1])
            own_reference,document=selected['returned_value']; raw=self.pure_carrier_raw(selected)
            need(type(raw) is bytes and sha(raw)==own_reference['sha256'], 'PURE_OWN_CARRIER_ORIGINAL_RAW_BYTES')
            expected=self.pure_read_expected(reference,view,raw,own_reference['path'])
            need(frame['returned_value']==expected,'PURE_SERVER_RAW_DEFAULT_MALFORMED_OR_SLICE_OUTPUT_DIFFERS')
        if frame['kind']=='source_function':
            args=frame['arguments']['positional']; kwargs=frame['arguments']['keyword']; name=frame['symbol'].rsplit('.',1)[-1]
            ret=frame['returned_value']; exception=frame['exception']
            if name=='_closed_view':
                try: self.closed_view(args[0]); valid=True
                except Block: valid=False
                need((exception is None and valid and ret==args[0]) or (exception is not None and not valid),'PURE_CLOSED_VIEW_REJECTION_NOT_DISCRIMINATING')
                return
            if name=='_replace_exact_source_line':
                recipe,line,replacement=args[:3]; lines=recipe.split('\n')
                if lines.count(line)!=1: need(exception is not None,'PURE_EXACT_SOURCE_LINE_MISSING_DUPLICATE_ACCEPTED')
                else: need(exception is None and ret=='\n'.join(replacement if value==line else value for value in lines),'PURE_SOURCE_LINE_REPLACED_QUOTED_DATA')
                return
            if exception is not None:
                if name=='collector_result_key': need(args[1] not in ('AC002-001','AC002-002','AC002-003','AC002-004'),'PURE_REGISTERED_COLLECTOR_KEY_REJECTED')
                elif name=='next_collector_template':
                    case=args[2] if len(args)>2 else kwargs.get('case_id','AC002-001'); view=args[1] if len(args)>1 else kwargs.get('view')
                    need(kwargs.get('fault') is True and (case not in ('AC002-002','AC002-003') or view!={'operation':'field','selector':'/user','start_char':0,'output_cap_bytes':8192,'metadata_reserve_bytes':2048}),'PURE_VALID_COLLECTOR_FAULT_REJECTED')
                return
            if name in ('inline_source','inline_command','inline_prefix'):
                reference=args[0]; view=args[1] if len(args)>1 else kwargs.get('view')
                if view is None: view={'operation':'inventory','output_cap_bytes':8192,'metadata_reserve_bytes':2048}
                literal=self.recipe_literals(); source=literal['constants']['READER_SOURCE']+'\nREFERENCE = json.loads('+repr(json.dumps(reference,sort_keys=True,ensure_ascii=True))+')\nVIEW = json.loads('+repr(json.dumps(view,sort_keys=True,ensure_ascii=True))+')\nraise SystemExit(emit_view(REFERENCE, VIEW))\n'
                command="python -I -B - <<'VERISLOP_EXACT_CARRIER_VIEW'\n"+source+'VERISLOP_EXACT_CARRIER_VIEW\n'
                expected=source if name=='inline_source' else command if name=='inline_command' else command.partition('\nVIEW = json.loads(')[0]+'\n'
                need(ret==expected,'PURE_INLINE_COMMAND_REFERENCE_VIEW_BYTES')
            if name in ('agent_message','plain_author_message'):
                reference=args[0]; literal=self.recipe_literals(); first={'operation':'inventory','output_cap_bytes':8192,'metadata_reserve_bytes':2048}
                next_view={'operation':'field','selector':'/system','start_char':0,'output_cap_bytes':8192,'metadata_reserve_bytes':2048}
                parts=literal['message_suffix_parts']; expected=literal['agent_message_prefix']+json.dumps(reference,sort_keys=True,ensure_ascii=True)+parts[0]+self.recipe(reference,first,True).decode()+parts[1]+parts[2]+self.recipe(reference,next_view).decode()+parts[3]
                if 'previous' not in frame['role']: need(ret==expected,'PURE_LITERAL_AUTHOR_MESSAGE')
            if name=='collector_result_key':
                reference=args[0]; case=args[1]
                need(case in ('AC002-001','AC002-002','AC002-003','AC002-004') and ret=='verislop.observable-carrier-collector-result/0.1:'+json.dumps({'case_id':case,'path':reference['path'],'sha256':reference['sha256']},sort_keys=True,ensure_ascii=True,separators=(',',':')),'PURE_COLLECTOR_OWN_CASE_KEY')
            if name=='own_session_key':
                reference=args[0]; expected='verislop.exact-carrier-session/0.1:'+json.dumps({'path':reference['path'],'sha256':reference['sha256']},sort_keys=True,ensure_ascii=True,separators=(',',':'))
                need(ret==expected,'PURE_OWN_STATE_PATH_HASH_KEY_CHANGED')
            if name in ('initial_session_template','next_session_template'):
                reference=args[0]; first=name=='initial_session_template'
                view=({'operation':'inventory','output_cap_bytes':8192,'metadata_reserve_bytes':2048} if first else
                      args[1] if len(args)>1 and args[1] is not None else {'operation':'field','selector':'/system','start_char':0,'output_cap_bytes':8192,'metadata_reserve_bytes':2048})
                # Previous001 NEXT is an explicitly different baseline; current/original002 must match.
                if 'previous' not in frame['role']: need(ret.encode()==self.recipe(reference,view,first),'PURE_RENDERER_RECIPE_BYTES_CHANGED')
            if name in ('initial_collector_template','next_collector_template'):
                reference=args[0]; first=name=='initial_collector_template'
                view=({'operation':'inventory','output_cap_bytes':8192,'metadata_reserve_bytes':2048} if first else
                      args[1] if len(args)>1 and args[1] is not None else {'operation':'field','selector':'/system','start_char':0,'output_cap_bytes':8192,'metadata_reserve_bytes':2048})
                case=args[1] if first and len(args)>1 else args[2] if not first and len(args)>2 else kwargs.get('case_id','AC002-001')
                fault=kwargs.get('fault',False); outer,nested=(256,16384) if fault and case=='AC002-003' else (20000,256) if fault else (20000,16384)
                need(ret.encode()==self.collector_recipe(reference,view,case,first,outer,nested),'PURE_COLLECTOR_OBSERVER_OR_FAULT_RECIPE_CHANGED')

    def source_expression(self, node, values):
        # Finite source-data expression grammar: no imports, eval, attribute access
        # outside the listed serialization operations, or arbitrary calls.
        if isinstance(node,ast.Constant): return node.value
        if isinstance(node,ast.Name):
            need(node.id in values,'PURE_SOURCE_EXPRESSION_UNBOUND:'+node.id); return values[node.id]
        if isinstance(node,(ast.List,ast.Tuple)): return [self.source_expression(v,values) for v in node.elts]
        if isinstance(node,ast.Dict): return {self.source_expression(k,values):self.source_expression(v,values) for k,v in zip(node.keys,node.values)}
        if isinstance(node,ast.Subscript): return self.source_expression(node.value,values)[self.source_expression(node.slice,values)]
        if isinstance(node,ast.BinOp):
            left,right=self.source_expression(node.left,values),self.source_expression(node.right,values)
            if isinstance(node.op,ast.Add): return left+right
            if isinstance(node.op,ast.Mult): return left*right
        if isinstance(node,ast.BoolOp) and isinstance(node.op,ast.Or):
            for item in node.values:
                value=self.source_expression(item,values)
                if value: return value
            return value
        if isinstance(node,ast.Call):
            kwargs={k.arg:self.source_expression(k.value,values) for k in node.keywords}
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='json' and node.func.attr=='dumps':
                return json.dumps(*[self.source_expression(v,values) for v in node.args],**kwargs)
            if isinstance(node.func,ast.Attribute) and node.func.attr=='join':
                separator=self.source_expression(node.func.value,values); argument=node.args[0]
                if isinstance(argument,ast.GeneratorExp):
                    need(len(argument.generators)==1 and not argument.generators[0].ifs,'PURE_SOURCE_GENERATOR_UNREGISTERED')
                    generator=argument.generators[0]; need(isinstance(generator.target,ast.Name),'PURE_SOURCE_GENERATOR_TARGET')
                    data=[]
                    for value in self.source_expression(generator.iter,values):
                        local={**values,generator.target.id:value}; data.append(self.source_expression(argument.elt,local))
                    return separator.join(data)
                return separator.join(self.source_expression(argument,values))
        raise Block('PURE_SOURCE_EXPRESSION_OUTSIDE_FINITE_GRAMMAR')

    def pure_source_only(self, contract):
        obligations=contract['source_only_obligations']; need(obligations,'PURE_SOURCE_ONLY_OBLIGATION_ABSENT')
        count=0
        for obligation in obligations:
            raw=self.read(obligation['path'],self.hashes[obligation['path']]); kind=obligation['kind']
            if kind=='manifest_contract':
                need(sha(raw)==obligation['expected_sha256'],'PURE_IMMUTABLE_MANIFEST_CHANGED')
                manifest=parse(raw)
                for path,entry in manifest[obligation['entry_map']].items(): self.read(path,entry['sha256'])
                count+=len(manifest[obligation['entry_map']])+1
            elif kind=='json_contract':
                document=parse(raw)
                for key,value in obligation['required_values'].items(): need(wire(document[key])==wire(value),'PURE_SOURCE_ONLY_REQUIRED_VALUE:'+key)
                if 'actual_channel_cases' in document:
                    cases={c['id']:c for c in document['actual_channel_cases']}
                    need(set(cases)=={'AC002-001','AC002-002','AC002-003','AC002-004'},'PURE_PROTOCOL_FOUR_CASES')
                    fault_view={'operation':'field','selector':'/user','start_char':0,'output_cap_bytes':8192,'metadata_reserve_bytes':2048}
                    for case,outer,nested in [('AC002-002',20000,256),('AC002-003',256,16384)]:
                        need(cases[case]['registered_fault_budgets']=={'outer_max_output_tokens':outer,'nested_max_output_tokens':nested} and cases[case]['registered_fault_view']==fault_view and
                             all(text in cases[case]['retry'] for text in ('SAME selector/start','outer20000/nested16384','cap4096/reserve2048')),'PURE_PROTOCOL_FAULT_RETRY')
                    author=document['fresh_author_case']
                    need((author['exact_count'],author['model'],author['fork_turns'],author['inspection_assertions'])==(1,'gpt-6.1-sol','none','UNATTESTED'),'PURE_PROTOCOL_SINGLE_AUTHOR')
                else:
                    need(document['fresh_pure_controls']['count']==15 and document['fresh_pure_controls']['prior_controls_rerun_with_new_bindings']==10 and
                         'Exact whole LF-delimited source-line equality' in document['replacement_scope'] and
                         {c['id'] for c in document['cases']}=={'AC002-001','AC002-002','AC002-003','AC002-004','FA002-001'} and
                         set(v for k,v in document['unavailable'].items() if k!='never_fabricate_or_relabel')=={'UNAVAILABLE'} and document['unavailable']['never_fabricate_or_relabel'] is True and
                         'Observable byte availability' in document['claim_scope'] and 'no hidden outer-envelope identity or LLM consumption' in document['claim_scope'],'PURE_CAPTURE_REGISTRATION_SCOPE')
                    author=next(c for c in document['cases'] if c['id']=='FA002-001')
                    need((author['exact_count'],author['model'],author['fork_turns'])==(1,'gpt-6.1-sol','none'),'PURE_CAPTURE_SINGLE_AUTHOR')
                count+=len(obligation['required_values'])+5
            elif kind=='python_fixture_contract':
                tree=ast.parse(raw.decode('utf-8','strict')); values={}
                for node in tree.body:
                    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('ATOM','MARKERS','SYSTEM'):
                        values[node.targets[0].id]=ast.literal_eval(node.value)
                function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fixture')
                assignments=[n for n in function.body if isinstance(n,ast.Assign)]
                need(len(assignments)==1 and assignments[0].targets[0].id=='user','PURE_FIXTURE_SOURCE_STRUCTURE')
                user=self.source_expression(assignments[0].value,values); system=values['SYSTEM']; markers=list(values['MARKERS'])
                need(len(user)==429112 and len(user)>400000 and user.endswith('UNRELATED_019_002_FINAL_TAIL🙂\t ') and 'é🙂e\u0301' in user and '\x00\t\r\n\\"/' in user and
                     markers==sorted(markers,key=user.index) and all(t in system for t in ('syntactically valid JSON','strict UTF-8','complete reconstructed decoded field')) and
                     'tools.exec_command' not in ast.get_docstring(tree),'PURE_FIXTURE_LITERAL_PREDICATES')
                count+=9
            else: raise Block('PURE_UNREGISTERED_SOURCE_ONLY_OBLIGATION')
        return count

    def pure_node_relations(self, frame, own):
        # Reconstruct the exact retained helper's Node program from finite literal
        # AST expressions, then bind real child stdout to the observed return.
        source=self.ref(frame['source_ref']).decode('utf-8','strict')
        function=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==frame['symbol'])
        positional=frame['arguments']['positional']; keyword=frame['arguments']['keyword']
        values={'scripts':positional[0],'recipes':positional[0],
                'initial_state':positional[1] if len(positional)>1 else keyword.get('initial_state'),
                'simulate_rendered_truncation':keyword.get('simulate_rendered_truncation',False)}
        for node in function.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='program':
                values['program']=self.source_expression(node.value,values)
            elif isinstance(node,ast.AugAssign) and isinstance(node.target,ast.Name) and node.target.id=='program' and isinstance(node.op,ast.Add):
                values['program']+=self.source_expression(node.value,values)
        children=[f for f in own if f['kind']=='subprocess' and f['parent_sequence']==frame['sequence']]
        need(len(children)==1 and children[0]['exception'] is None,'PURE_NODE_ACTUAL_CHILD_MISSING')
        child=children[0]; ret=child['returned_value']; argv=['node','--input-type=module','-e',values['program']]
        need(child['arguments']['positional'][0]==ret['argv']==argv and ret['returncode']==0 and
             type(ret['stdout']) is str and type(ret['stderr']) is str and wire(parse(ret['stdout'].encode()))==wire(frame['returned_value']),'PURE_NODE_ACTUAL_PROGRAM_OR_OUTPUT_BINDING')
        output=frame['returned_value']; need(set(output)==set(self.pure_schema['node_return_shapes'][frame['kind']]),'PURE_NODE_RETURN_SCHEMA')
        need(len(output['errors'])==len(positional[0]) and len(output['calls'])==len(output['forwarded']) and
             all(item['same_actual'] is True for item in output['forwarded']),'PURE_ONE_FORWARD_PER_ACTUAL_CALL')
        if frame['kind']=='inert_node':
            need(len(output['resultStores'])==len(output['calls']) and all(item['same_actual'] is True for item in output['resultStores']) and
                 output['events']==['call','forward','result_store']*len(output['calls']),'PURE_ACTUAL_OBJECT_RETAINED_AFTER_FORWARD')
        return 4

    def carrier_pure(self):
        raw=self.index('pure'); self.bound(raw,False)
        need(raw['format']=='verislop.support019-carrier-pure-observations/1' and raw['status']=='OBSERVED' and
             raw['installed_source_sha256']==self.hashes['synthetic_dataset/tools/bootstrap_tier2_carrier_view.py'], 'PURE_PRODUCER_SCHEMA_OR_INSTALLED_SOURCE')
        ids=self.adapters['exact_pure_test_ids']
        need(len(ids)==len(set(ids))==30 and raw['registered_test_ids']==raw['started_ids']==ids and number(raw['tests_run'])==30 and
             raw['cases']==[{'test_id':i,'status':'PASS'} for i in ids], 'PURE_EXACT30_ACTUAL_START_OUTCOMES')
        for key in ('failures','errors','skipped','expected_failures','unexpected_successes'): need(number(raw[key])==0,'PURE_ADVERSE_COUNT:'+key)
        evidence=self.adapters['pure_evidence']; receipt_path=self.path(evidence['actual_process_receipt_path'])
        receipt=parse(self.fresh_ref({'path':str(receipt_path),**self.report['evidence'][str(receipt_path)]})); self.actual_process(receipt,evidence['process_contract'])
        witness_ref=raw['semantic_witnesses_ref']; need(witness_ref['path']==evidence['semantic_witnesses_path'],'PURE_WITNESS_OUTPUT_PATH_CHANGED')
        witnesses=parse(self.fresh_ref(witness_ref)); self.bound(witnesses,False)
        schema=self.doc(evidence['schema_path'],self.hashes[evidence['schema_path']]); self.pure_schema=schema
        need(set(witnesses)==set(schema['top_required']) and witnesses['format']==schema['sidecar_format'] and witnesses['registered_test_ids']==ids and
             witnesses['producer']['path']==evidence['producer_path'] and witnesses['producer']['sha256']==self.hashes[evidence['producer_path']] and
             witnesses['schema']['path']==evidence['schema_path'] and witnesses['schema']['sha256']==self.hashes[evidence['schema_path']] and
             witnesses['qualification_authority'] is False and witnesses['models_called']==0 and witnesses['task_inputs'] is False,'PURE_WITNESS_SCHEMA_OR_SOURCE')
        sources={entry['path']:self.ref(entry) for entry in witnesses['source_refs']}
        need(len(sources)==len(witnesses['source_refs']) and all(sha(data)==self.hashes[path] for path,data in sources.items()),'PURE_CURRENT_FROZEN_SOURCE_REFERENCES')
        def decode(value):
            if type(value) is list: return [decode(v) for v in value]
            if type(value) is dict:
                encoding=value.get('encoding')
                if encoding=='base64':
                    need(set(value)==set(schema['bytes_required']),'PURE_BYTES_SCHEMA'); data=base64.b64decode(value['data'],validate=True)
                    need(sha(data)==value['sha256'] and len(data)==number(value['byte_count']),'PURE_LOSSLESS_BYTES_HASH'); return data
                if encoding=='path':
                    need(set(value)=={'encoding','value'} and type(value['value']) is str,'PURE_PATH_ENCODING'); return value['value']
                need(encoding!='unavailable','PURE_WITNESS_VALUE_UNAVAILABLE')
                return {k:decode(v) for k,v in value.items()}
            return value
        source_checks=[]
        for pair in witnesses['source_pairs']:
            need(set(pair)==set(schema['source_pair_required']) and pair['source_ref']['path'] in sources,'PURE_SOURCE_PAIR_SCHEMA')
            data=sources[pair['source_ref']['path']]; tree=ast.parse(data.decode()) if any(f['symbol']!='FILE_BYTES' for f in pair['fragments']) else None
            for fragment in pair['fragments']:
                need(set(fragment)==set(schema['fragment_required']),'PURE_SOURCE_FRAGMENT_SCHEMA'); symbol=fragment['symbol']
                if symbol=='FILE_BYTES': expected=data
                elif fragment['kind']=='constant_bytes':
                    nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==symbol for t in n.targets)]
                    need(len(nodes)==1,'PURE_CONSTANT_NOT_UNIQUE'); expected=ast.literal_eval(nodes[0].value).encode()
                else: need(fragment['kind']=='function_ast_bytes','PURE_FRAGMENT_KIND'); expected=self.source_ast(data,symbol)
                need(decode(fragment['value'])==expected,'PURE_SOURCE_FRAGMENT_RAW_BYTES'); source_checks.append({'role':pair['role'],'symbol':symbol,'sha256':sha(expected)})
        need(source_checks,'PURE_SOURCE_FRAGMENTS_MISSING')
        fragments={(pair['role'],f['symbol']):decode(f['value']) for pair in witnesses['source_pairs'] for f in pair['fragments']}
        for left,right,symbols in [('candidate.candidate','candidate.original',('READER_SOURCE','inline_source','inline_command')),
                                   ('candidate.candidate','candidate.previous',('READER_SOURCE','inline_source','inline_command','inline_prefix','initial_session_template'))]:
            for symbol in symbols:
                need((left,symbol) in fragments and (right,symbol) in fragments and fragments[left,symbol]==fragments[right,symbol],'PURE_ORIGINAL_HELPER_BYTES_CHANGED:'+symbol)
        frames=witnesses['frames']; need(type(frames) is list and frames and [f['sequence'] for f in frames]==list(range(1,len(frames)+1)),'PURE_FRAME_SEQUENCE')
        decoded=[decode(frame) for frame in frames]
        for frame in decoded:
            need(set(frame)==set(schema['frame_required']) and type(frame['sequence']) is int and frame['case_id'] in ids and frame['kind'] in schema['frame_kinds'] and
                 set(frame['arguments'])==set(schema['argument_required']) and frame['source_ref']['path'] in sources,'PURE_FRAME_CLOSED_SCHEMA')
            self.ref(frame['source_ref']); parent=frame['parent_sequence']
            need(parent is None or type(parent) is int and 1<=parent<frame['sequence'] and decoded[parent-1]['case_id']==frame['case_id'],'PURE_FRAME_PARENT_BINDING')
        contracts=schema['case_contracts']; cases=witnesses['cases']
        need([c['case_id'] for c in contracts]==[c['case_id'] for c in cases]==ids,'PURE_EXACT_CASE_CONTRACTS')
        checked=[]
        for contract,case in zip(contracts,cases):
            case_id=contract['case_id']; own=[f for f in decoded if f['case_id']==case_id]
            need(set(case)==set(schema['case_required']) and case['source_ref']['path']==contract['source'] and
                 all(case[key]==contract[key] for key in ('exact_symbol','source_only','required_roles','independent_predicates','source_only_obligations')) and
                 decode(case['case_ast'])==self.source_ast(self.ref(case['source_ref']),contract['exact_symbol']),'PURE_EXACT_REGISTERED_CASE_AST')
            role_index={}
            for frame in own: role_index.setdefault(frame['role'],[]).append(frame['sequence'])
            need(case['frame_sequences']==[f['sequence'] for f in own] and case['role_index']==role_index and set(contract['required_roles']).issubset(role_index),'PURE_CASE_FRAME_ROLE_BINDING')
            count=self.pure_source_only(contract) if contract['source_only'] else 0
            if not contract['source_only']: need(own,'PURE_DYNAMIC_CASE_NO_OBSERVATION')
            for frame in own:
                self.pure_frame_relations(frame,own)
                if frame['exception'] is not None: continue
                kind=frame['kind']; ret=frame['returned_value']
                if kind in ('node_templates','inert_node'): count+=self.pure_node_relations(frame,own)
                elif kind=='subprocess':
                    need(set(ret)==set(schema['subprocess_return_required']) and type(ret['returncode']) is int and
                         type(ret['stdout']) is type(ret['stderr']) and type(ret['stdout']) is (str if frame['arguments']['keyword'].get('text',False) is True else bytes) and ret['argv']==frame['arguments']['positional'][0],'PURE_ACTUAL_SUBPROCESS_LOSSLESS')
                    count+=1
                elif kind=='carrier':
                    need(frame['returned_type']=='builtins.tuple' and type(ret) is list and len(ret)==2,'PURE_CARRIER_TUPLE')
                    reference,document=ret; original=self.pure_carrier_raw(frame)
                    need(set(reference)=={'path','sha256','request_sha256'} and all(type(v) is str for v in reference.values()) and
                         set(document)=={'format','request_id','request_sha256','system','user'} and all(type(v) is str for v in document.values()) and document['format']=='verislop.collaboration-carrier/0.1' and
                         reference['request_sha256']==document['request_sha256'] and type(original) is bytes and sha(original)==reference['sha256'],'PURE_CARRIER_RAW_REFERENCE_BINDING'); count+=1
                elif kind in ('read','source_function'): count+=1
            need(count>0,'PURE_INDEPENDENT_PREDICATES_ABSENT'); checked.append({'test_id':case_id,'independent_raw_predicates':count,'frame_count':len(own)})
        return {'exact30':checked,'source_fragments':source_checks,'mock_renderer_is_not_actual_channel':True}

    def authority_boundary(self):
        contract=self.adapters['authority_contract']
        source_checks=[self.source_pair(pair) for pair in contract['source_pairs']]
        need(source_checks and self.spec['strict_implementation_proof_release_unchanged'] is True and
             self.spec['inference_timeout'] is self.spec['retrieval_timeout'] is self.spec['review_timeout'] is None, 'AUTHORITY_OR_DEADLINE_CHANGED')
        before=parse(self.ref(contract['policy_before_ref'])); after=parse(self.ref(contract['policy_after_ref']))
        need(wire(before)==wire(after) and sha(self.ref(contract['policy_after_ref']))==self.spec['policy_hash'], 'STRICT_POLICY_BYTE_IDENTITY_CHANGED')
        for name,entry in contract['limit_objects'].items():
            current=parse(self.ref(entry['current_ref'])); baseline=parse(self.ref(entry['baseline_ref']))
            need(wire(current)==wire(baseline), 'EXISTING_LIMIT_OBJECT_CHANGED:'+name)
            self.predicates(entry['predicates'],{'current':current,'baseline':baseline})
        need(contract['observation_trust']=='TCB-TOOL-FORWARDING' and contract['hidden_outer_native_envelope']=='UNAVAILABLE' and
             contract['semantic_acceptance_authority'] is False and contract['activation_authority'] is False and
             contract['model_identity']==contract['semantic_consumption']=='UNATTESTED', 'AUTHORITY_BOUNDARY_OVERCLAIM')
        return {'strict_source_identities':source_checks,'policy_hash':self.spec['policy_hash'],'existing_limits_identical':sorted(contract['limit_objects']),
                'core_model_calls':0,'ancillary_author_calls':1,'only_observable_tool_trust_added':True}

    def whole_audit(self):
        required=['freeze','phases','suite','carrier','channel','unicode','ground','collection','provenance']+list(ADDITIONAL.values())[:-1]
        need(all(self.groups[g]['status']=='VERIFIED' for g in required), 'ALL27_PREREQUISITE_PREDICATES_NOT_INDEPENDENTLY_VERIFIED')
        need([p['id'] for p in self.spec['execution_phases']]==self.floor['phase_order'] and len(self.phase_receipts)==4 and
             set(self.floor['registered_test_ids']).issubset(self.suite_ids), 'WHOLE_AUDIT_PHASE_OR_SUITE_FLOOR')
        self.rehash()
        return {'original18_and_additional9_independent':True,'original_fresh_phases':self.floor['phase_order'],
                'final_test_count':len(self.suite_ids),'all_source_input_raw_receipt_output_rehashed':True,'prior_PASS_inheritance':False}

    def run(self):
        self.execute('freeze',self.freeze)
        ordered=('phases','suite','carrier','channel','unicode','ground','collection','equality_original','equality_private',
                 'carrier_pure','carrier_full','carrier_faults','carrier_empty','fresh_author','authority_boundary','provenance','whole_audit')
        for group in ordered:
            if self.groups['freeze']['status']=='VERIFIED': self.execute(group,getattr(self,group))
            else: self.groups[group]={'status':'BLOCKED','actual_predicates':{},'blocking_reasons':['CURRENT_ROOT_OR_FINALIZER_NOT_ADMITTED'],'evidence':[]}
        if self.hashes and hasattr(self,'frozen'): self.execute('final_rehash',self.rehash)
        else: self.groups['final_rehash']={'status':'BLOCKED','actual_predicates':{},'blocking_reasons':['CURRENT_ROOT_NOT_ADMITTED'],'evidence':[]}
        registration=getattr(self,'reader_registration',{})
        verifier_hash=sha(self.read(Path(__file__))); verifier_id=registration.get('verifier_id','V019-INDEPENDENT-PREDICATE-READER')
        claims=[]
        for original in self.claims:
            names=original['audit_groups']+['final_rehash']; checked=[self.groups[g] for g in names]
            state=('INFRASTRUCTURE_FAILURE' if any(g['status']=='INFRASTRUCTURE_FAILURE' for g in checked) else
                   'BLOCKED' if any(g['status']!='VERIFIED' for g in checked) else 'VERIFIED')
            paths=set().union(*(set(g['evidence']) for g in checked))
            # Shared and cached raw evidence is still listed when a later group rereads it.
            paths.update(self.report.get('claims',[{}])[len(claims)].get('evidence',[]) if self.report else [])
            rawrefs=[]
            for value in sorted(paths):
                path=self.path(value)
                if any(path.is_relative_to(ROOT/prefix) for prefix in self.spec['fresh_evidence_prefixes']):
                    row=self.evidence[str(path)]; rawrefs.append({'path':path.relative_to(ROOT).as_posix(),**row})
            required=self.spec['independent_claim_checks'][original['id']]
            if state=='VERIFIED':
                need(rawrefs and required['predicate_implementation_reviewed'] is True and required['verifier_id']==verifier_id and
                     required['verifier_path']==Path(__file__).relative_to(ROOT).as_posix() and self.hashes[required['verifier_path']]==verifier_hash,
                     'CLAIM_READER_REGISTRATION_OR_RAW_EVIDENCE_MISSING')
            claims.append({'claim_id':original['id'],'closure_id':CLOSURE,'source_root':self.source_root,'input_root':self.input_root,
                'original_statement':original['statement'],'original_pass_condition':original['pass_condition'],'registered_verifier':original['verifier'],
                'verifier_id':verifier_id,'verifier_hash':verifier_hash,'status':state,'checked_predicates':required['required_predicate_names'],
                'raw_evidence_refs':rawrefs,'actual_predicates':{g:self.groups[g]['actual_predicates'] for g in names},
                'blocking_reasons':[r for g in checked for r in g['blocking_reasons']],'trusted_dependencies':original['dependencies_trusted']})
        state=('INFRASTRUCTURE_FAILURE' if any(c['status']=='INFRASTRUCTURE_FAILURE' for c in claims) else
               'BLOCKED' if any(c['status']!='VERIFIED' for c in claims) else 'VERIFIED')
        code={'VERIFIED':0,'BLOCKED':1,'INFRASTRUCTURE_FAILURE':2}[state]
        output=Path(self.args.output)
        need(output.is_absolute() and output.parent==GATE and output.name=='independent-audit' and not output.exists(), 'OUTPUT_MUST_BE_NEW_REGISTERED_AUDIT_DIRECTORY')
        # No writes occur until all finite checks and final source/evidence rehash complete.
        report={'format':'verislop.support019-independent-predicate-report/1','closure_id':CLOSURE,'status':state,'exit_code':code,
            'source_root':self.source_root,'input_root':self.input_root,'verifier_id':verifier_id,'verifier_hash':verifier_hash,'verifier_sha256':verifier_hash,
            'claims':claims,'claim_counts':{'total':27,'passed':sum(c['status']=='VERIFIED' for c in claims),'blocked':sum(c['status']=='BLOCKED' for c in claims),
                'infrastructure_failure':sum(c['status']=='INFRASTRUCTURE_FAILURE' for c in claims)},'actual_predicate_groups':self.groups,'phase_receipts':self.phase_receipts,
            'evidence':self.evidence,'dependencies':{'trusted':[t['id'] for t in self.plan['tcb']['trusted']]+['TCB-TOOL-FORWARDING'],'undeclared':[]},
            'categories':self.plan['report_categories'],'excluded_surface':self.plan['exclusions'],
            'build_counts':{'required_outer_clean_builds':2,'passed':2 if self.groups['collection']['status']=='VERIFIED' else 0},
            'determinism':{'required':True,'status':self.groups['whole_audit']['status']},'provenance':{'status':self.groups['provenance']['status'],'public_claims':self.plan['public_claims']},
            'correspondence':{'ground_observations':16 if self.groups['ground']['status']=='VERIFIED' else 0,'unicode_exact_cases_per_round':182 if self.groups['unicode']['status']=='VERIFIED' else 0},
            'witnesses':{'required_ground_fixture_assignment_pairs':8,'admitted_current_rounds':2 if self.groups['ground']['status']=='VERIFIED' else 0},
            'scope':{'finite_qualification_only':True,'semantic_acceptance_authority':False,'activation_authority':False,'production_task_inputs':False,
                'prior_pass_inheritance':False,'llm_consumption_attested':False,'model_identity':'UNATTESTED','semantic_consumption':'UNATTESTED','hidden_outer_native_envelope':'UNAVAILABLE'},
            'decision':{'exit_code':code,'manual_override_allowed':False,'valid_states':['VERIFIED','BLOCKED','INFRASTRUCTURE_FAILURE']},
            'infrastructure_errors':[reason for g in self.groups.values() if g['status']=='INFRASTRUCTURE_FAILURE' for reason in g['blocking_reasons']],
            'interpretation':'Finite current-root 27-predicate closure only under explicit existing semantic TCB and tool-forwarding trust for observable bytes/rendering. No task correctness, consumption, activation, universal Unicode or historical PASS transfer.'}
        output.mkdir()
        with (output/'report.json').open('xb') as f: f.write(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False).encode()+b'\n')
        print(json.dumps({'status':state,'exit_code':code,'report':str(output/'report.json'),'claim_count':27},sort_keys=True))
        return code

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('qualification-root','final-report','finalizer-receipt','output','equality-index-sha256','carrier-index-sha256','author-index-sha256','pure-index-sha256'):
        parser.add_argument('--'+name,required=True)
    try: return Reader(parser.parse_args()).run()
    except (Block,KeyError,ValueError,TypeError,IndexError,AttributeError) as error:
        print(json.dumps({'status':'BLOCKED','exit_code':1,'blocking_reasons':[str(error)]},sort_keys=True)); return 1
    except Exception as error:
        print(json.dumps({'status':'INFRASTRUCTURE_FAILURE','exit_code':2,'infrastructure_errors':[type(error).__name__+':'+str(error)]},sort_keys=True)); return 2

if __name__=='__main__':
    raise SystemExit(main())
