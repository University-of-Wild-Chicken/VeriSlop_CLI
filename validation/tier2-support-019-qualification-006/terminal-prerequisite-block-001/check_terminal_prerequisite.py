"""Finite terminal author-completion gate; never execute current27 or viewers."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[3]
GATE=ROOT/'validation/tier2-support-019-qualification-006'
OUT=Path(__file__).absolute().parent
EXPECTED_SOURCE='sha256:46914cccd000e3063fc2c9e64efcceaf9e6659e4a22ad599faabdebc2a1e936e'
EXPECTED_INPUT='sha256:c02b2ca6ced98031104d3b48826ca69ecfb7aad8b41bc8cc3a6d15450bc2d459'
SUCCESS_KEYS={'markers','field_roots','field_eof','field_chars'}
def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def ref(path):
    assert path.is_file() and not path.is_symlink() and path.resolve()==path.absolute()
    raw=path.read_bytes();return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(raw),'byte_count':len(raw)}
def load(path):
    def unique(pairs):
        value={}
        for key,item in pairs:
            assert key not in value,'Duplicate JSON member';value[key]=item
        return value
    return json.loads(path.read_bytes(),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
def guard(hashes):
    actual={name:ref(ROOT/name)['sha256'] for name in hashes};assert actual==hashes,'Frozen input mutation';return actual
def main():
    registration=load(OUT/'registration-before-execution.json')
    for name,expected in registration['source_guards'].items():assert ref(ROOT/name)==expected,'Registered source/evidence mutation'
    binding=load(OUT/'evidence-interface-binding-before-source.json')
    for name,identity in binding['evidence_refs'].items():assert ref(ROOT/identity['path'])==identity
    inputs=load(GATE/'qualification-inputs.json');spec=load(GATE/'qualification-specification.json');prereg=load(GATE/'preregistration.json')
    assert inputs['source_root']==spec['source_root']==prereg['source_root']==EXPECTED_SOURCE
    assert inputs['input_root']==prereg['input_root']==EXPECTED_INPUT
    assert spec['closure_id']==prereg['closure_id']=='support019-final-current-root-006'
    frozen=inputs['source_hashes'];assert len(frozen)==6836
    assert sha(json.dumps(frozen,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())==EXPECTED_INPUT
    before=guard(frozen);write(OUT/'before-input-hashes.json',before)
    author=GATE/'fresh-author';literal_ref=ref(author/'literal-final.txt');literal=load(author/'literal-final.txt');records=load(author/'author-records.json')
    diagnostic=load(author/'diagnostic-parser-observation.json');controller=load(author/'controller-after-transport.json');native=load(author/'completion-actual-tool-observation.json');structural=load(author/'structural-admission-observation.json')
    assert type(native['exit_code']) is int and native['exit_code']==0 and 'session_id' not in native
    observed=json.loads(native['output']);assert observed==structural
    for key in ('before_ref','after_ref','author_records_ref','literal_final_ref','diagnostic_parser_observation_ref'):
        identity=observed[key];assert ref(ROOT/identity['path'])==identity
    assert records['literal_final_ref']==diagnostic['literal_final_ref']==observed['literal_final_ref']==literal_ref
    assert diagnostic['parser_ref']==ref(ROOT/'validation/tier2-support019-author-recovery-implementation-006/diagnostic_failure_parser.py')
    assert diagnostic['schema_valid'] is False and diagnostic['success_authority'] is False and diagnostic['independent_reproduction_executed'] is False
    assert diagnostic['trust']==literal['failure']['trust']=='UNATTESTED'
    assert diagnostic['error_type']=='DiagnosticSchemaError' and diagnostic['error_literal']==observed['diagnostic_parser_error']=='INVALID_OWN_CAP'
    assert observed['schema_valid'] is False and observed['gate_completion']=='UNSUCCESSFUL_LITERAL_FINAL'
    assert observed['independent_error_reproduction_executed'] is False and observed['hidden_cause']=='UNAVAILABLE'
    assert type(observed['controller_process_pid']) is int and observed['controller_process_pid']==controller['controller_process_pid']==3568677
    assert observed['frozen_inputs_unchanged']==controller['frozen_input_count']==6836
    assert controller['observed_input_hashes']==frozen and controller['input_hashes_unchanged'] is True and controller['guard_mismatches']==[]
    assert controller['binding_hashes_unchanged'] is True and controller['external_bindings']==prereg['external_bindings']
    assert records['source_root']==controller['source_root']==EXPECTED_SOURCE and records['input_root']==controller['input_root']==EXPECTED_INPUT
    assert records['spawn_count']==observed['spawn_count']==controller['actual_author_spawn_count']==1
    assert observed['followup_count']==controller['actual_author_followup_count']==0
    assert records['replacement_author_or_resampling'] is False and controller['replacement_or_resampling'] is False
    assert records['model_identity']==records['semantic_consumption']==controller['model_identity']==controller['semantic_consumption']=='UNATTESTED'
    assert len(records['observed_author_requests'])==1 and records['evaluator_expectations_sent_to_author'] is False
    for key in ('spawn_request_ref','spawn_result_ref'):
        identity=records[key];assert ref(ROOT/identity['path'])==identity
        assert records['observed_author_requests'][0][key]==identity
    for identity in records['exposed_responses_refs']:assert ref(ROOT/identity['path'])==identity
    assert records['exposed_responses_refs']==observed['exposed_response_refs']
    roots=literal['field_roots'];missing_roots=sorted({'/system','/user'}-set(roots));extra_fields=sorted(set(literal)-SUCCESS_KEYS)
    assert roots=={} and missing_roots==['/system','/user'] and literal['field_eof']['/user'] is False and extra_fields==['failure']
    assert observed['field_roots_reported']==roots and observed['field_eof_reported']==literal['field_eof'] and observed['literal_final_key_count']==len(literal)==5
    assert not (ROOT/spec['actual_author_evidence_path']).exists() and observed['author_index_created'] is False and controller['author_index_created'] is False
    absent=[spec[key] for key in ('actual_process_output_index_path','actual_author_evidence_path','actual_equality_evidence_path','actual_pure_evidence_path','actual_channel_evidence_path')]
    for phase in spec['execution_phases']+spec['additional_processes']:absent.extend(phase['outputs'].values())
    absent=sorted(set(absent));assert all(not (ROOT/name).exists() for name in absent),'Current main/core/additional output exists'
    assert not (GATE/'actual-channel/calls').exists() and not (GATE/'original-channel/capture-index.json').exists()
    generic=load(GATE/'admission-controls/actual-process-receipt.json');assert type(generic['returncode']) is int and generic['returncode']==0 and generic['before']==generic['after']
    assert generic['argv']==spec['ancillary_admission_controls']['argv'] and generic['registered_environment']==spec['ancillary_admission_controls']['environment']
    for identity in (generic['stdout'],generic['stderr']):assert ref(ROOT/identity['path'])==identity
    assert b'Ran 5 tests' in (ROOT/generic['stderr']['path']).read_bytes() and b'\nOK\n' in (ROOT/generic['stderr']['path']).read_bytes()
    baseline=load(ROOT/'validation/tier2-support-019-qualification-003/terminal-prerequisite-block-001/report.json')
    claim_ids=sorted(baseline['current27_claims']);assert claim_ids==[f'Q018-{i:02d}' for i in range(1,19)]+[f'Q019-{i:02d}' for i in range(1,10)]
    after=guard(frozen);assert before==after;write(OUT/'after-input-hashes.json',after)
    evidence={'format':'verislop.support019-terminal-prerequisite-checker-evidence/1','scope':registration['scope'],'frozen_input_count':6836,'all_frozen_inputs_unchanged':True,'before':ref(OUT/'before-input-hashes.json'),'after':ref(OUT/'after-input-hashes.json'),'literal_final':literal_ref,'author_records':ref(author/'author-records.json'),'diagnostic_parser_observation':ref(author/'diagnostic-parser-observation.json'),'diagnostic_parser':diagnostic['parser_ref'],'existing_native_process_observation':ref(author/'completion-actual-tool-observation.json'),'existing_controller_process_record':ref(author/'controller-after-transport.json'),'existing_controller_pid':observed['controller_process_pid'],'existing_native_exit_code':native['exit_code'],'separate_controller_stderr':'UNAVAILABLE_NOT_SEPARATELY_EXPOSED','absent_current_main_core_outputs':absent,'generic5_receipt':ref(GATE/'admission-controls/actual-process-receipt.json'),'opaque_fixture_gold_parsed_or_exposed':False,'current27_verifiers_run':0,'VIEW_calls':0,'model_calls':0,'Lean_calls':0,'qualification_authority':False,'activation_authority':False}
    write(OUT/'checker-evidence.json',evidence)
    report={'format':baseline['format'],'status':'BLOCKED','closure_id':spec['closure_id'],'source_root':EXPECTED_SOURCE,'input_root':EXPECTED_INPUT,'failed_prerequisite':'UNIQUE_AUTHOR_COMPLETE_LITERAL_FINAL','affected_claim_id':'Q019-07','prerequisite_decision_scope':'Only the author-completion gate; no current27 qualification decision','actual_literal_final':literal,'literal_final_sha256':literal_ref['sha256'],'concrete_counterexamples':[{'required':'field_roots has exactly /system and /user SHA256 values','observed':roots,'missing_roots':missing_roots},{'required':'explicit /user EOF true before successful reconstruction','observed':literal['field_eof']['/user']},{'required':'successful FINAL has exactly markers, field_roots, field_eof, field_chars','observed_extra_fields':extra_fields}],'all6836_frozen_inputs_unchanged':True,'checker_evidence_ref':ref(OUT/'checker-evidence.json'),'current27_claims':{cid:'UNRESOLVED_NOT_EXECUTED' for cid in claim_ids},'current27_passed':0,'current27_verifiers_run':0,'core_processes_started':0,'main_collector_invocations':0,'original_channel_invocations':0,'native019_activated':False,'current_native_calls':0,'current_task_calls':0,'Tier2_task_claim':'PENDING','independent_whole_root_admission':'NOT_EXECUTED','author_spawn_count':1,'author_followups':0,'resampling':False,'inference_timeout':None,'author_reported_diagnostic':{'trust':'UNATTESTED','stage':literal['failure']['stage'],'operation':literal['failure']['operation'],'observation':literal['failure']['observation'],'success_path_authority':False},'diagnostic_schema_observation':{'schema_valid':False,'error_type':diagnostic['error_type'],'error_literal':diagnostic['error_literal'],'evidence_ref':ref(author/'diagnostic-parser-observation.json'),'success_path_authority':False},'hidden_failure_reason':'UNAVAILABLE','historical_cause':'UNAVAILABLE','historical_actual_retry':'UNAVAILABLE','independent_error_reproduction_executed':False,'model_identity':'UNATTESTED','semantic_consumption':'UNATTESTED','finite_prerequisite_checker_processes':1,'generic_negative_controls':{'count':5,'actual_receipt':ref(GATE/'admission-controls/actual-process-receipt.json'),'current27_authority':False},'qualification_authority':False,'activation_authority':False,'task_TESTED_authority':False,'stop':baseline['stop']}
    write(OUT/'report.json',report)
    print(json.dumps({'status':'BLOCKED','report':ref(OUT/'report.json'),'evidence':ref(OUT/'checker-evidence.json'),'frozen_inputs':6836,'all_guards_unchanged':True,'current27_passed':0},sort_keys=True),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
