#!/usr/bin/env python3
"""Finite independent evidence admission. No imports/execution of target verifiers."""
from pathlib import Path
import argparse
import base64
import datetime
import hashlib
import json
import re
import sys

ROOT = Path(__file__).absolute().parents[2]
HERE = Path(__file__).absolute().parent
GATE = ROOT / 'validation/tier2-support-018-qualification-002'
FINAL = GATE / 'final-reconciliation'
CLOSURE = 'support018-final-current-root-002'
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
    return sha(wire(x))

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
        self.args, self.evidence, self.groups = args, {}, {}
        self.plan = parse((HERE / 'audit-specification.json').read_bytes())
        self.claims = self.plan['claims']
        self.report = {}
        self.hashes = {}
        self.input_root = self.source_root = None
        self.processes = []
        self.runtime_representation = parse((HERE / 'runtime-representation-binding.json').read_bytes())

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
        spec=self.doc(HERE/'source-inventory-registration.json')
        names=set(spec['transport_files'])
        for directory,suffixes in spec['directory_suffixes'].items():
            names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*') if p.suffix in suffixes)
        names.update(n for n in spec['optional_root_files'] if (ROOT/n).exists())
        need(spec['required_source_file'] in names,'SOURCE_SPECIFICATION_MISSING')
        return names

    def finalizer(self):
        reg = self.doc(ROOT / 'validation/tier2-support-018-qualification-plan/final-reconciliation-002/finalizer-registration.json')
        receipt = self.doc(self.args.finalizer_receipt)
        need(receipt['argv'] == reg['invocation']['argv'] and receipt['cwd'] == str(ROOT), 'FINALIZER_COMMAND_NOT_REGISTERED')
        number(receipt['pid'], 1)
        need(number(receipt['returncode']) == 0 and receipt['timed_out'] is False, 'FINALIZER_PROCESS_NOT_COMPLETED_SUCCESSFULLY')
        need(receipt['input_root'] == self.input_root and receipt['source_root'] == self.source_root, 'FINALIZER_PROCESS_STALE')
        need(date(receipt['started_utc']) <= date(receipt['completed_utc']), 'FINALIZER_INTERVAL_INVALID')
        stdout = parse(self.ref(receipt['stdout']))
        self.ref(receipt['stderr'])
        report_path = self.path(self.args.final_report)
        need(report_path == FINAL / 'report.json' and self.path(receipt['report']['path']) == report_path and
             stdout['report'] == str(report_path), 'FINAL_REPORT_PATH_NOT_CURRENT_REGISTERED')
        self.report = self.doc(report_path, receipt['report']['sha256'])
        r = self.report
        need(stdout == {'status': r['status'], 'source_root': self.source_root, 'input_root': self.input_root,
                        'report': str(report_path), 'claim_count': 18}, 'FINALIZER_STDOUT_REPORT_DISAGREES')
        need(r['closure_id'] == CLOSURE and r['source_root'] == self.source_root and r['input_root'] == self.input_root, 'FINAL_REPORT_STALE')
        need(r['verifier_id'] == 'V018-FINAL-RECONCILIATION-002' and
             r['verifier_sha256'] == reg['verifier']['sha256'] and r['specification_sha256'] == reg['specification']['sha256'] and
             r['report_schema_sha256'] == reg['report_schema']['sha256'], 'FINALIZER_IMPLEMENTATION_UNBOUND')
        for key in ('verifier', 'specification', 'report_schema'):
            self.read(reg[key]['path'], reg[key]['sha256'])
        need([c['claim_id'] for c in r['claims']] == [c['id'] for c in self.claims], 'ORIGINAL_CLAIM_INVENTORY_CHANGED')
        for old, row in zip(self.claims, r['claims']):
            expected_groups=['guards' if g=='freeze' else g for g in old['audit_groups'] if g!='provenance']
            need(row['status']=='VERIFIED' and row['blocking_reasons']==[] and
                 row['actual_predicates']=={g:r['actual_predicate_groups'][g]['actual_predicates'] for g in expected_groups} and
                 all(r['actual_predicate_groups'][g]['status']=='VERIFIED' for g in expected_groups),
                 'ORIGINAL_CLAIM_NOT_DERIVED_FROM_CURRENT_REGISTERED_RAW_GROUPS:'+old['id'])
            need(row['original_statement'] == old['statement'] and row['original_pass_condition'] == old['pass_condition'] and
                 row['registered_verifier'] == old['verifier'] and row['trusted_dependencies'] == old['dependencies_trusted'],
                 'ORIGINAL_PREDICATE_OR_TRUST_CHANGED:' + old['id'])
        need(r['status']=='VERIFIED' and number(r['decision']['exit_code'])==receipt['returncode'] and
             r['decision']['manual_override_allowed'] is False, 'FINALIZER_DECISION_PROCESS_CONTRADICTION')
        need(r['dependencies']['trusted']==[x['id'] for x in self.plan['tcb']['trusted']] and
             r['dependencies']['undeclared']==[], 'FINALIZER_UNDECLARED_OR_CHANGED_DEPENDENCY')
        for p, row in r['evidence'].items():
            self.read(p, row['sha256'], row['byte_count'])
        need(r['scope']['finite_qualification_only'] is True and all(r['scope'][k] is False for k in
             ('llm_consumption_attested', 'semantic_acceptance_authority', 'production_task_inputs', 'prior_pass_inheritance')),
             'FINALIZER_SCOPE_LEAK')
        return {'exact_registered_process': receipt, 'raw_finalizer_evidence_count': len(r['evidence'])}

    def freeze(self):
        for p, h in self.plan['frozen_authorities'].items():
            self.read(p, h)
        representation = self.doc(HERE / 'collection-representation.json')
        for p, h in {**representation['source_bindings'],**self.runtime_representation['source_bindings']}.items():
            self.read(p, h)
        self.spec = self.doc(GATE / 'qualification-specification.json')
        self.input = self.doc(GATE / 'qualification-inputs.json')
        self.frozen = self.doc(GATE / 'source-freeze.json')
        self.prereg = self.doc(GATE / 'preregistration.json')
        self.hashes = self.input['source_hashes']
        self.input_root = self.input['input_root']
        self.source_root = self.frozen['source_root']
        need(all(isinstance(v,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in (self.input_root,self.source_root)), 'RUNTIME_REGISTERED_ROOT_INVALID')
        need(self.spec['closure_id']==CLOSURE and self.input['source_root']==self.source_root and
             self.spec['source_root']==self.source_root==self.plan['expected_source_root'], 'RUNTIME_ROOT002_CLOSURE_SOURCE_MISMATCH')
        need(self.hashes and digest(self.hashes) == self.input['input_root'] == self.input_root, 'CURRENT_INPUT_MAP_MISMATCH')
        need(self.frozen['source_files'] and digest(self.frozen['source_files']) == self.source_root, 'CURRENT_SOURCE_MAP_MISMATCH')
        need(self.spec['test_sources'] and len(self.spec['test_modules']) == 15 and
             self.spec['registered_test_count'] == 180 and self.spec['source_root'] == self.source_root, 'CURRENT_REGISTRATION_COUNT_CHANGED')
        stopped=self.doc(HERE/'root002-source-binding.json')
        for p,h in stopped['files'].items():
            need(self.hashes.get(p)==h,'STOPPED_ROOT002_SOURCE_OR_LEDGER_INPUT_NOT_REGISTERED:'+p)
            self.read(p,h)
        for p, h in self.hashes.items():
            self.read(p, h)
        need(all(self.hashes.get(p)==h for p,h in {**representation['source_bindings'],**self.runtime_representation['source_bindings']}.items()), 'COLLECTION_REPRESENTATION_SOURCE_NOT_CURRENT_ROOT')
        for source_map in (self.frozen['source_files'], self.spec['test_sources']):
            need(all(self.hashes.get(p) == h for p, h in source_map.items()), 'INCOMPLETE_SOURCE_TEST_HASH_MAP')
        need(self.inventory()==set(self.frozen['source_files']),'PRODUCTION_FILE_ADDED_OR_REMOVED')
        # Inventory only current tests; no imports, test execution, or discovery outside this root.
        test_names = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests').rglob('*.py')}
        need(test_names == set(self.spec['test_sources']), 'TEST_FILE_ADDED_OR_REMOVED')
        for k, p in [('driver_sha256','gate.py'),('spec_sha256','qualification-specification.json'),
                     ('source_freeze_sha256','source-freeze.json'),('input_manifest_sha256','qualification-inputs.json')]:
            self.read(GATE / p, self.prereg[k])
        need(self.prereg['input_root'] == self.input_root and self.prereg['source_root'] == self.source_root and
             self.prereg['generation_started'] is False and self.frozen['generation_started'] is False, 'FREEZE_NOT_PREEXECUTION')
        need(isinstance(self.spec['toolchain'],dict) and all(k in self.spec['toolchain'] for k in ('pin','version','githash','lean_binary_sha256')) and
             all(isinstance(v,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',v) for v in
                 (self.spec['toolchain']['lean_binary_sha256'],self.spec['kernel_tool_hash'],self.spec['policy_hash'])), 'RUNTIME_TOOL_OR_POLICY_BINDING_INVALID')
        need(self.spec['model_calls'] == 0 and self.spec['task_inputs'] is False and self.spec['prior_pass_inheritance'] is False,
             'PROHIBITED_AUTHORITY')
        self.finalizer()
        for g in ('guards','guards_after'):
            raw = self.report['actual_predicate_groups'][g]
            need(raw['actual_predicates']['source_root'] == self.source_root and raw['actual_predicates']['input_root'] == self.input_root and
                 raw['actual_predicates']['input_files'] == len(self.hashes) and raw['actual_predicates']['source_files'] == len(self.frozen['source_files']) and
                 raw['actual_predicates']['test_files'] == len(self.spec['test_sources']) and raw['actual_predicates']['environment']=={
                     'toolchain':self.spec['toolchain'],'kernel_tool_hash':self.spec['kernel_tool_hash'],'policy_hash':self.spec['policy_hash']}, 'FINALIZER_COMPLETE_GUARDS_ABSENT')
        need(self.report['actual_predicate_groups']['guards']['actual_predicates'] ==
             self.report['actual_predicate_groups']['guards_after']['actual_predicates'], 'FINALIZER_ENTRY_EXIT_DIFFER')
        return {'input_count':len(self.hashes), 'source_count':len(self.frozen['source_files']), 'test_count':len(self.spec['test_sources']), 'source_root': self.source_root,
                'input_root': self.input_root, 'registered_verifier_execution_authenticated': True}

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
        self.final_spec = self.doc(ROOT / 'validation/tier2-support-018-qualification-plan/final-reconciliation-002/specification.json')
        return {'exact_current_numeric_processes':4,'registered_serial_order':self.final_spec['phase_order']}

    def suite(self):
        s = self.doc(GATE / 'run-result.json'); inv = self.doc(GATE / 'invocation.json'); ids = self.spec['registered_test_ids']
        need(len(ids) == len(set(ids)) == 180 and COLLECTION in ids and
             s['registered_test_ids'] == s['started_ids'] == inv['registered_test_ids'] == ids and
             number(s['tests_run']) == s['registered_test_count'] == 180 and
             s['test_observations'] == [{'test_id':i,'status':'PASS'} for i in ids], 'EXACT_SUITE_NOT_EXECUTED')
        for k in ('failures','errors','skipped','expected_failures','unexpected_successes'):
            need(number(s[k]) == 0, 'NONZERO_SUITE_RESULT:' + k)
        need(s['source_root_before'] == s['source_root_after'] == inv['source_root'] == self.source_root and
             s['input_root'] == inv['input_root'] == self.input_root and
             s['external_bindings_before'] == s['external_bindings_after'], 'SUITE_CURRENT_BINDING_MISMATCH')
        for p,h in s['external_bindings_before'].items(): self.read(p,h)
        need(all(s[k] is True for k in ('source_unchanged','tests_unchanged','qualification_inputs_unchanged')) and
             all(any(i.startswith(m+'.') for i in ids) for m in self.spec['test_modules']), 'SUITE_INVENTORY_GUARD_MISSING')
        self.suite_ids = ids
        return {'ordered_tests':180,'modules':15,'all_exact_individual_outcomes':'PASS'}

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
        directory = GATE / 'channel-actual'; p = self.doc(directory / 'channel-case-plan.json'); ix = self.doc(directory / 'capture-index.json')
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
             'validation/tier2-support-018-qualification-plan/scripts/verify-channel-records-v2.py'] and result['raw_result']['complete_fields']==[] and
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
        d=ROOT/'validation/tier2-unicode-literal-support-018/runs/qualification-018-002';r=self.doc(d/'report.json')
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
        recipe=self.doc(ROOT/'validation/tier2-ground-replay-support-018-design/recipe-001.json',g['recipe_sha256'])
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
        marker_spec = self.doc(HERE / 'marker-specification.json')
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
        p=self.doc(FINAL/'provenance.json');need(len(p)==18 and [x['claim_id'] for x in p]==[c['id'] for c in self.claims],'PROVENANCE_CLAIM_INVENTORY')
        for row,claim in zip(p,self.claims):
            need(row['registered_verifier']==claim['verifier'] and row['trusted_dependencies']==claim['dependencies_trusted'] and
                 row['inputs']['source_root']==self.source_root and row['inputs']['input_root']==self.input_root and row['inputs']['registered_files']==self.hashes and row['evidence'],
                 'PUBLIC_CLAIM_PROVENANCE_UNBOUND:'+claim['id'])
            for e in row['evidence']:need(str(self.path(e)) in self.evidence,'PROVENANCE_EVIDENCE_NOT_ADMITTED')
        for public in self.plan['public_claims']:need(public['claims'] and all(i in {c['id'] for c in self.claims} for i in public['claims']),'ORPHAN_PUBLIC_CLAIM')
        need(self.inventory()==set(self.frozen['source_files']) and
             {p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').rglob('*.py')}==set(self.spec['test_sources']), 'ENTRY_EXIT_SOURCE_TEST_MAP_MUTATION')
        for path,row in list(self.evidence.items()):self.read(path,row['sha256'],row['byte_count'])
        return {'internal_claims':18,'public_claims':len(self.plan['public_claims']),'all_read_evidence_rehashed_on_exit':True}

    def run(self):
        registration=self.doc(HERE/'reader-registration.json')
        for p,h in registration['files'].items():self.read(p,h,base=HERE)
        self.execute('freeze',self.freeze)
        for group in ('phases','suite','carrier','channel','unicode','ground','collection','provenance'):
            if self.groups['freeze']['status']=='VERIFIED':self.execute(group,getattr(self,group))
            else:self.groups[group]={'status':'BLOCKED','actual_predicates':{},'blocking_reasons':['CURRENT_ROOT_OR_FINALIZER_NOT_ADMITTED'],'evidence':[]}
        claims=[]
        for original in self.claims:
            checked=[self.groups[g] for g in original['audit_groups']]
            state=('INFRASTRUCTURE_FAILURE' if any(g['status']=='INFRASTRUCTURE_FAILURE' for g in checked) else
                   'BLOCKED' if any(g['status']!='VERIFIED' for g in checked) else 'VERIFIED')
            claims.append({'claim_id':original['id'],'original_statement':original['statement'],'original_pass_condition':original['pass_condition'],
                           'registered_target_verifier':original['verifier'],'status':state,'actual_predicates':{g:self.groups[g]['actual_predicates'] for g in original['audit_groups']},
                           'blocking_reasons':[r for g in checked for r in g['blocking_reasons']],'trusted_dependencies':original['dependencies_trusted']})
        state=('INFRASTRUCTURE_FAILURE' if any(c['status']=='INFRASTRUCTURE_FAILURE' for c in claims) else
               'BLOCKED' if any(c['status']!='VERIFIED' for c in claims) else 'VERIFIED')
        code={'VERIFIED':0,'BLOCKED':1,'INFRASTRUCTURE_FAILURE':2}[state]
        output=Path(self.args.output).absolute();need(output.parent==HERE and not output.exists(),'OUTPUT_MUST_BE_NEW_AUDIT_CHILD');output.mkdir()
        report={'format':'verislop.support018-independent-audit-report/1','audit_id':self.plan['audit_id'],'closure_id':CLOSURE,'status':state,'exit_code':code,
                'source_root':self.source_root,'input_root':self.input_root,'verifier_id':registration['verifier_id'],'verifier_hash':sha(Path(__file__).read_bytes()),
                'specification_hash':registration['files']['audit-specification.json'],'claims':claims,'claim_counts':{'total':18,'passed':sum(c['status']=='VERIFIED' for c in claims),
                'blocked':sum(c['status']=='BLOCKED' for c in claims),'infrastructure_failure':sum(c['status']=='INFRASTRUCTURE_FAILURE' for c in claims)},
                'groups':self.groups,'evidence':self.evidence,'dependencies':self.plan['tcb'],'categories':self.plan['report_categories'],'excluded_surface':self.plan['exclusions'],
                'build_counts':{'required_outer_clean_builds':2,'passed':2 if self.groups['collection']['status']=='VERIFIED' else 0},
                'determinism':{'required':True,'status':self.groups['provenance']['status'] if all(self.groups[g]['status']=='VERIFIED' for g in ('collection','unicode','ground')) else 'BLOCKED'},
                'provenance':{'public_claims':self.plan['public_claims'],'status':self.groups['provenance']['status']},
                'correspondence':{'ground_observation_count':16 if self.groups['ground']['status']=='VERIFIED' else 0,'unicode_exact_cases_per_round':182 if self.groups['unicode']['status']=='VERIFIED' else 0},
                'witnesses':{'required_ground_fixture_assignment_pairs':8,'admitted_current_rounds':2 if self.groups['ground']['status']=='VERIFIED' else 0},
                'infrastructure_errors':[x for g in self.groups.values() if g['status']=='INFRASTRUCTURE_FAILURE' for x in g['blocking_reasons']],
                'manual_override_allowed':False,'interpretation':'VERIFIED applies only to the original frozen finite 18-predicate surface and authenticated registered verifier evidence under the unchanged explicit TCB. No task correctness, TESTED, Tier3/4, old PASS transfer, or universal Unicode claim.'}
        with (output/'report.json').open('xb') as f:f.write(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False).encode()+b'\n')
        print(json.dumps({'status':state,'exit_code':code,'report':str(output/'report.json'),'claims':18},sort_keys=True))
        return code

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--final-report',required=True);p.add_argument('--finalizer-receipt',required=True);p.add_argument('--output',required=True)
    try:return Reader(p.parse_args()).run()
    except (Block,KeyError,ValueError,TypeError) as e:
        print(json.dumps({'status':'BLOCKED','exit_code':1,'blocking_reasons':[str(e)]},sort_keys=True));return 1
    except Exception as e:
        print(json.dumps({'status':'INFRASTRUCTURE_FAILURE','exit_code':2,'infrastructure_errors':[type(e).__name__+':'+str(e)]},sort_keys=True));return 2

if __name__=='__main__':
    raise SystemExit(main())
