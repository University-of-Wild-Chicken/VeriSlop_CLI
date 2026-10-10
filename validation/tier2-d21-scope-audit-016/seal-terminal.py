"""Read-only independent scope/provenance audit of actual NEW stage016."""
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/home/augustus/VeriSlop_CLI')
OUT=ROOT/'validation/tier2-d21-scope-audit-016'
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-016'
PROJECT=STAGE/'project'
RUN=STAGE/'run'
PACKAGE=RUN/'artifacts/D21/verislop/package'
BOUNDARY=ROOT/'validation/tier2-native-boundary-gate-016'
sys.path.insert(0,str(PROJECT))
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical


def digest(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


read_inventory={}
def load(path):
    assert path.is_file() and not path.is_symlink()
    data=path.read_bytes()
    read_inventory[str(path.relative_to(ROOT))]={'byte_length':len(data),'sha256':digest(data)}
    return json.loads(data)


def file_record(path):
    assert path.is_file() and not path.is_symlink()
    data=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'byte_length':len(data),'sha256':digest(data)}


def write_once(path,value):
    data=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
    return digest(data)


for stem in ['plan-seal','input-receipt-seal']:
    data=(OUT/(stem+'.json')).read_bytes()
    assert digest(data)==(OUT/(stem+'.sha256')).read_text().strip()
    s=load(OUT/(stem+'.json'))
    for f in s['files']: assert file_record(ROOT/f['path'])==f
plan=load(OUT/'frozen-plan.json')
input_receipt=load(OUT/'input-receipt.json')
protocol=bootstrap.verify_inputs(RUN)
for k in ['source_root','input_root','request_set_root']: assert protocol[k]==input_receipt[k]
assert file_record(RUN/'protocol.json')==input_receipt['protocol']
for check in input_receipt['public_byte_comparisons']: assert file_record(ROOT/check['current']['path'])==check['current']
seal=load(RUN/'EVIDENCE-MANIFEST.json')
other_seal=load(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json')
actual_files=bootstrap.evidence_files(RUN)
assert seal==other_seal
assert seal['files']==actual_files and seal['files_root']==canonical.digest_json(actual_files)
assert seal['source_root']==protocol['source_root'] and seal['protocol_sha256']==file_record(RUN/'protocol.json')['sha256']
assert len(actual_files)==904
origin=bootstrap.response_audit(RUN,protocol['tasks'][0])
result=load(RUN/'artifacts/D21/verislop/result.json')
aggregate=load(RUN/'BOOTSTRAP-RESULT.json')
assert origin==result['origin_audit']
assert origin['status']=='PASS' and not origin['issues'] and origin['provider_calls']==origin['responses']==15
assert origin['transport_errors']==0 and len(origin['agents'])==len(set(origin['agents']))==15
assert aggregate['rows']==[result] and aggregate['status']==result['status']=='BLOCKED'
driver=load(BOUNDARY/'driver-result.json')
controller=load(BOUNDARY/'native-controller-terminal.json')
assert driver['returncode']==result['worker_exit_code']==controller['driver_returncode']==2
assert controller['driver_result_sha256']==file_record(BOUNDARY/'driver-result.json')['sha256']
assert controller['author_task_ids']==origin['agents'] and controller['literal_final_submissions']==15 and controller['outstanding_authors']==0
assert controller['source_root']==protocol['source_root'] and controller['supplemental_protocol_root']==seal['protocol_sha256']
verify_invocation=load(BOUNDARY/'terminal-verify-invocation.json')
verify_result=load(BOUNDARY/'terminal-verify-result.json')
verify_stdout=load(BOUNDARY/'terminal-verify.stdout.log')
assert verify_result['returncode']==0 and verify_stdout['status']=='PASS'
assert verify_result['stdout_sha256']==file_record(BOUNDARY/'terminal-verify.stdout.log')['sha256']
assert verify_result['argv']==verify_invocation['argv'] and verify_result['cwd']==str(PROJECT)
assert verify_stdout['source_root']==protocol['source_root'] and verify_stdout['rows']==[result]
assert verify_stdout['milestone_authority'] is False
ir=load(PACKAGE/'accepted/accepted-ir.json')
acceptance=load(PACKAGE/'accepted/acceptance.json')
proposal=load(PACKAGE/'contract/candidate/typed-proposal.json')
formalization=load(PACKAGE/'contract/candidate/formalization.json')
statement_check=load(PACKAGE/'contract/candidate/statement-check.json')
report=load(PACKAGE/'report.json')
assert acceptance['gate']=='accepted_and_proved' and acceptance['diagnostics']==[]
for name,rec in acceptance['artifacts'].items(): assert digest((PACKAGE/rec['path']).read_bytes())==rec['sha256']
assert ir['contract_input_root']==acceptance['contract_input_root']==report['roots']['contract_input_root']
assert digest((PACKAGE/'accepted/accepted-ir.json').read_bytes())==report['roots']['accepted_ir']
assert statement_check['diagnostics']==[] and statement_check['compile']['ok'] is True
assert all(x['result']=={'defeq':True,'ok':True,'typechecks':True} for x in statement_check['defeq']+statement_check['frontend_defeq'])
ids={x['id']:x for x in plan['identity_metadata']}
assert set(ir['obligations'])==set(ids)|{'A1_nonvacuity'}
for oid,frozen in ids.items():
    rec=ir['obligations'][oid]
    assert all(rec[k]==frozen[k] for k in ['id','kind','role','required'])
    assert acceptance['obligations'][oid]['typechecked']=='PASS'
    if frozen['role']=='guarantee': assert acceptance['obligations'][oid]['proved']=='PASS'
facets={}
policy=load(RUN/'requests/D21/source-policy.json')
for oid in list(policy['obligations']):
    ref=ir['obligations'][oid]['formal']['formula_ref'].split('@sha256:')[-1]
    path=PACKAGE/'accepted/expressions'/f'{ref}.json'
    assert file_record(path)['sha256']=='sha256:'+ref
    expression=load(path)
    row=expression['source'][0]
    assert len(expression['source'])==1
    assert row['symbol']=='solve' and row['lean_decl']=='VeriSlopAST.solve'
    want=policy['obligations'][oid]
    assert row['requirements'][0]=={'tag':'entry','arity':want['arity'],'entry':want['entry'],'file':want['file']}
    assert sorted(x['tag'] for x in row['requirements'][1:])==sorted(want['properties'])
    assert (expression['value'] is not None)==want['value_required']
    facets[oid]={'classification':'MIXED' if expression['value'] is not None else 'SOURCE_ONLY','expression_sha256':file_record(path)['sha256'],'source_requirements':row['requirements'],'value_projection':expression['value_projection']}
mixed=load(PACKAGE/'accepted/expressions/b28c3cbd14c47859f9fb88199d28470ecfba6ecd3429fc31e80c40d0a9d296b9.json')
formula=mixed['value']['formula']
assert formula['tag']=='forall' and formula['sort']=={'record':'Input'}
assert formula['body']['tag']=='implies'
expected_validity={'tag':'and','left':{'tag':'lt','left':{'tag':'int','value':'0'},'right':{'tag':'field','sort':'Input','field':'width','value':{'tag':'var','index':0}}},'right':{'tag':'le','left':{'tag':'field','sort':'Input','field':'start','value':{'tag':'var','index':0}},'right':{'tag':'field','sort':'Input','field':'end','value':{'tag':'var','index':0}}}}
assert formula['body']['left']==expected_validity
assert proposal['predicates']['valid_input']['formula']==expected_validity
assert proposal['enums']['Fill']['constructors']==['none','previous']
assert proposal['records']['Input']['fields']==[{'name':'events','sort':{'list':{'record':'Event'}}},{'name':'start','sort':'Int'},{'name':'end','sort':'Int'},{'name':'width','sort':'Int'},{'name':'fill','sort':{'enum':'Fill'}}]
assert proposal['records']['Event']['fields']==[{'name':'group','sort':'String'},{'name':'time','sort':'Int'},{'name':'value','sort':{'option':'Int'}}]
nv=acceptance['obligations']['A1_nonvacuity']
assert nv['proved']==nv['typechecked']=='PASS' and nv['witnesses']
assert formalization['internal_obligations']==[{'description':'An Input with no events, start and end zero, width one and fill none satisfies exactly the caller validity predicate.','id':'A1_nonvacuity','kind':'non_vacuity','theorem':'VeriSlopAST.valid_input_inhabited','witnesses_for':['A1']}]
bridge=load(PACKAGE/'bridges/implementation/plan.json')
materialization=load(PACKAGE/'implementation/materialization.json')
selection=load(PACKAGE/'bridges/implementation/candidate-inputs/support/readable/selection.json')
structural_evidence=load(PACKAGE/'bridges/implementation/evidence/ev-02057dbfc185af1764c4f843d2c647be.json')
native_stdout=load(RUN/'artifacts/D21/verislop/stdout.json')
failed=[x for x in result['cli_diagnostics'] if x['code']=='CANDIDATE_BUILD_FAILURE'][0]
assert failed['details']['error_count']==3 and failed['details']['timed_out'] is False and failed['details']['sorry_positions']==[]
for key,name in [('source','program.vscore.json'),('proof_source','Proof.lean'),('model','model.json'),('profile','profile.json'),('relation','relation.json')]:
    assert failed['details']['input_hashes'][key]==file_record(PACKAGE/'bridges/implementation/candidate-inputs'/name)['sha256']
current_source_hash=file_record(PACKAGE/'implementation/program.vscore.json')['sha256']
assert current_source_hash==materialization['source_hash']==failed['details']['input_hashes']['source']==selection['inputs']['source']
assert materialization['proof_checked'] is False
assert structural_evidence['claim_id']=='BRIDGE:structure:implementation' and structural_evidence['status']=='PASS'
assert set(x['id'] for x in bridge['obligations'])==set(policy['obligations'])
assert report['builds']==[] and report['mechanical_result'] is None and report['release_status']=='BLOCKED'
assert not (PACKAGE/'closure/plan.json').exists()
assert not (PACKAGE/'bridges/implementation/semantic').exists()
probes=load(OUT/'concrete-probe-results-v2.json')
assert probes['cases']==27 and probes['optional_TESTED_rescored'] is False
assert all(x['passed']==27 and x['failed']==0 and all(y['input_preserved'] and y['deterministic_repeat'] for y in x['results']) for x in probes['results'] if x['host_admission']=='PASS')
assert probes['interpreter_sha256']==file_record(OUT/'run-concrete-probes-v2.py')['sha256']
events_data=(PACKAGE/'events.jsonl').read_bytes()
events=[json.loads(x) for x in events_data.decode().splitlines()]
read_inventory[str((PACKAGE/'events.jsonl').relative_to(ROOT))]={'byte_length':len(events_data),'sha256':digest(events_data)}
nv_events=[x for x in events if x.get('obligation_id')=='A1_nonvacuity']
assert min(x['seq'] for x in nv_events)>min(x['seq'] for x in events if x.get('phase')=='formalize' and x['type']=='candidate_proposal')
helper_execution={'verifier':'frozen bootstrap.verify_inputs/evidence_files/response_audit','helper':file_record(PROJECT/'synthetic_dataset/tools/bootstrap_tier2.py'),'environment':{'os':platform.platform(),'python':platform.python_version()},'result':'PASS','source_files':len(protocol['source_files']),'sealed_run_files':len(actual_files),'files_root':seal['files_root'],'origin':origin,'input_mutation_detected':False}
write_once(OUT/'terminal-mechanical-observations.json',helper_execution)
clauses=[
    {'id':x['id'],'status':'CHECKED','statement':x['statement'],'evidence':'Current public bytes; current typed AST definitions and kernel-reconstructed MIXED contract expression; accepted reference Lean source; trusted natural-language correspondence.'}
    for x in plan['functional_clauses']
]
checks=[
    {'id':'AUDIT-SCOPE','outcome':'PASS','classification':'CHECKED','detail':'Current five public files match sealed input receipt; all original 11 ID/kind/role/required triples preserved; public examples unchanged.'},
    {'id':'AUDIT-DOMAIN','outcome':'PASS','classification':'CHECKED','detail':'Unbounded Int/String/List/Option carrier and exactly width>0 AND start<=end guard; complete Fill enum none/previous. No original valid input excluded. Broader Int width carrier is guarded exactly.'},
    {'id':'AUDIT-FACETS','outcome':'PASS','classification':'CHECKED','detail':'Kernel-reconstructed O1-O7 each have nonempty source requirements and full quantified value package; I1/S1 source-only. Exact file/solve/arity1 plus all seven closed requirements. Delivery conformance of actual source remains pending the bridge.'},
    {'id':'AUDIT-NONVACUITY','outcome':'PASS','classification':'PROVED','detail':'Only new derived ID is A1_nonvacuity; registered formalization rule after actual native proposal. Accepted concrete witness events=[],start=end=0,width=1,fill=none. No source-policy row substitutes for NV.'},
    {'id':'AUDIT-REFINEMENT','outcome':'BLOCK','classification':'NOT_ESTABLISHED','detail':'Current candidate proof has three elaboration errors. BRIDGE:implementation:vscore-refinement pending; no semantic certificate or accepted source refinement/transfer.'},
    {'id':'AUDIT-CLOSURE','outcome':'BLOCK','classification':'NOT_ESTABLISHED','detail':'closure/plan.json absent, semantic certificate absent, closure root null, builds=[], determinism.compared=[], provenance=[], release_status=BLOCKED; no task clean builds A/B or release probes.'},
    {'id':'AUDIT-ORIGIN','outcome':'PASS','classification':'CHECKED_MECHANICAL','detail':'904-file equal manifests exactly match current run inventory/root; frozen source/input helper and actual response/origin replay pass. Fifteen unique fresh author IDs and exact final receipts. Controller stopped with zero outstanding authors; no identity attestation.'},
    {'id':'AUDIT-PROBES','outcome':'PASS','classification':'TESTED_HOST_BOUNDED_ONLY','detail':'Source-1 rejected for duplicate type IDs; both executable source-2 and materialized source-3 pass all 27 frozen public-only vectors with unchanged inputs and repeated equal output. No counterexample in this finite set; no normative execution/refinement claim and optional TESTED untouched.'},
]
terminal={
    'schema_version':'verislop.independent-terminal-scope-audit/0.1','audit_id':plan['audit_id'],'created_utc':datetime.now(timezone.utc).isoformat(),'status':'BLOCKED','task_status':'BLOCKED','audit_integrity_status':'PASS','closure_id':'package','input_root_hash':protocol['source_root'],'supplemental_input_root':protocol['input_root'],'protocol_sha256':seal['protocol_sha256'],'request_set_root':protocol['request_set_root'],'run_evidence_root':seal['files_root'],
    'claims':{'total':8,'passed':6,'blocked':2,'unresolved':0},'checks':checks,'functional_clause_review':clauses,
    'exact_reached_stages':result['cli_stages'],'additional_observed_start_events':[x for x in events if x['type']=='stage_started' and x['phase']=='verify'],
    'stopping_point':'CLI terminal bridge:accept BLOCKED (CANDIDATE_BUILD_FAILURE); later verify start event exists, but no semantic certificate/closure plan/clean task build records were produced.',
    'formal_contract':{'accepted':True,'accepted_ir':file_record(PACKAGE/'accepted/accepted-ir.json'),'acceptance':file_record(PACKAGE/'accepted/acceptance.json'),'contract_input_root':ir['contract_input_root'],'original_required_ids':sorted(ids),'derived_required_ids':['A1_nonvacuity'],'facets':facets,'value_formula_scope':'forall Input, width>0 and start<=end implies exact complete aggregation; all scalar strings, arbitrary finite occurrence lists, nullable unbounded integer values, both Fill alternatives. Shared complete_behavior covers all functional clauses.','natural_language_correspondence':'CHECKED review under explicitly trusted correspondence, not sole mechanical authority.','witnesses':nv['witnesses'],'actual_source_refinement_accepted':False},
    'correspondence':{'required_objects':9,'mapped_objects':9,'unmapped_objects':0,'ambiguous_objects':0,'status':'STRUCTURAL_MAPPING_PRESENT_SEMANTIC_EDGE_UNACCEPTED'},
    'witnesses':{'required':1,'valid':1,'invalid':0},'builds':{'required':2,'passed':0,'records':[]},'determinism':{'required':True,'status':'NOT_REACHED','compared':[]},'provenance':{'current_native_origin':'PASS','closure_public_claims':9,'fully_bound_end_to_end':0,'closure_evidence_status':'NOT_REACHED'},
    'dependencies':{'verified':['accepted contract kernel-check/reconstruction records','current source/input/run-seal and response/origin bindings'],'trusted':protocol['trust'],'undeclared':[]},
    'current_bridge':{'source_sha256':current_source_hash,'selected_readable_status':selection['status'],'structural_preparation_evidence':file_record(PACKAGE/'bridges/implementation/evidence/ev-02057dbfc185af1764c4f843d2c647be.json'),'semantic_claim':'BRIDGE:implementation:vscore-refinement','semantic_acceptance':False,'semantic_certificates':[],'error_count':failed['details']['error_count'],'exact_errors':failed['details']['errors'],'timed_out':False,'proof_source_sha256':failed['details']['input_hashes']['proof_source'],'goal_hash':failed['details']['goal_hash']},
    'blocking_reasons':[{'code':'CANDIDATE_BUILD_FAILURE','claim':'AUDIT-REFINEMENT','evidence':'synthetic_dataset/bootstrap/stages/tier2-source-facets-016/run/artifacts/D21/verislop/result.json','detail':'Current module VeriSlopBridgeProof failed elaboration: three reported errors at 47:26,91:2,112:44; not timeout, no sorry positions.'},{'code':'VERIFIER_NOT_RUN','claim':'AUDIT-CLOSURE','evidence':'synthetic_dataset/bootstrap/stages/tier2-source-facets-016/run/artifacts/D21/verislop/package/report.json','detail':'Required task clean builds, accepted semantic edge, determinism/provenance completion and release probes have no records; absent semantic certificate and closure plan.'}],
    'infrastructure_errors':[],
    'bounded_probe_evidence':file_record(OUT/'concrete-probe-results-v2.json'),'probe_count':27,'concrete_semantic_counterexamples':[],'probe_harness_history':'First audit-only interpreter run had named record-field wrapper decoding errors; its original script/results are immutable and explicitly superseded by v2. Those errors are not candidate counterexamples.',
    'frozen_terminal_verify':{'result':file_record(BOUNDARY/'terminal-verify-result.json'),'stdout':file_record(BOUNDARY/'terminal-verify.stdout.log'),'returncode':0,'status':'PASS','milestone_authority':False,'meaning':'Current retained BLOCKED terminal and seals reconstruct correctly; this PASS is not task closure success.'},
    'closure_boundary':{'verified_surface':['current registered accepted-contract checks','current frozen input and 904-file run integrity/origin checks'],'trusted_surface':protocol['trust'],'excluded_surface':protocol['excluded']+['host probe interpreter to normative Lean correspondence','future revisions'],'interpretation':'Task remains BLOCKED. Bounded host agreement does not establish universal source refinement, clean task closure, END_TO_END_VERIFIED or release. Accepted reference-contract proofs and current integrity evidence remain distinct from implementation assurance.'},
    'optional_TESTED_rescored':False,'model_identity_attested':False,'old_stages_modified':False,'production_task_candidate_files_modified':False,'decision':{'valid_states':['VERIFIED','BLOCKED','INFRASTRUCTURE_FAILURE'],'manual_override_allowed':False},'stop_rule':'Finite frozen checks complete; no candidate patches, further tests, agents or builds.'
}
read_manifest={'schema_version':'verislop.audit-read-manifest/0.1','audit_id':plan['audit_id'],'files':dict(sorted(read_inventory.items())),'generic_source_inventory_binding':protocol['source_root'],'current_run_inventory_binding':seal['files_root'],'restrictions':'Actual new stage016 artifacts and exact root-supplied stage016 driver/controller/verify receipts only; no old candidates/proofs/hidden cases/oracles or generic engineering fixture solutions read.'}
write_once(OUT/'terminal-read-manifest.json',read_manifest)
report_hash=write_once(OUT/'terminal-audit.json',terminal)
audit_files={p.name:file_record(p)['sha256'] for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ['terminal-audit-seal.json','terminal-audit-seal.sha256']}
audit_seal={'schema_version':'verislop.scope-audit-seal/0.1','audit_id':plan['audit_id'],'phase':'TERMINAL_AUDIT_COMPLETE','status':'BLOCKED','files':audit_files,'files_root':canonical.digest_json(audit_files),'native_run_evidence_root':seal['files_root'],'source_root':protocol['source_root']}
seal_hash=write_once(OUT/'terminal-audit-seal.json',audit_seal)
with (OUT/'terminal-audit-seal.sha256').open('x') as stream: stream.write(seal_hash+'\n')
assert bootstrap.evidence_files(RUN)==actual_files
assert bootstrap.source_inventory()==protocol['source_files']
print(json.dumps({'status':'BLOCKED','audit_integrity_status':'PASS','terminal_audit_sha256':report_hash,'terminal_audit_seal_sha256':seal_hash,'audit_files':len(audit_files),'run_files':len(actual_files),'probe_cases':27,'source_root':protocol['source_root']},sort_keys=True))
