"""Concrete public-input binding only; no task execution or assurance assignment."""
import hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/home/augustus/VeriSlop_CLI')
OUT=ROOT/'validation/tier2-d21-scope-audit-017'
PROJECT=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-017/project'
RUN=PROJECT.parent/'run'
READS={}
OBS=[]
def sha(b): return 'sha256:'+hashlib.sha256(b).hexdigest()
def raw(p,scope):
 p=Path(p); b=p.read_bytes(); r={'path':str(p),'sha256':sha(b),'bytes':len(b),'read_scopes':[]}
 if str(p) in READS: r=READS[str(p)]
 if scope not in r['read_scopes']:r['read_scopes'].append(scope)
 READS[str(p)]=r
 return b
def data(p,scope='public prepared/qualification metadata only'):return json.loads(raw(p,scope))
def jcs(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def digest(x):return sha(jcs(x))
def save(name,x):
 p=OUT/name
 with p.open('xb') as f:f.write((json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode())
 return {'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}
def check(name,ok,claims,details=None):
 OBS.append({'check':name,'matches':bool(ok),'affected_frozen_checks':claims,'details':details})
 if not ok:raise AssertionError(name)
expected={
'FREEZE-MANIFEST.json':'96efcd682e3e9509c9539039ff556ea2f5d7b197eda4e3482cce12e4cc54e047',
'preregistration.json':'ef8c9f090cf58ec836842fd98fd29141ac46982caad64ec0a0249cdf2c3752ae',
'planned-evidence-checks.json':'4aeab1b561c79f056af94c0e37504b2b5501df34eba27236f978d40e78007a41',
'public-probes.json':'c1d4c00fb1148445acfa12415ba393913e39e72c86578c13f8399943d944bace'}
for name,h in expected.items():check('Immutable '+name,sha(raw(OUT/name,'immutable original stage017 preregistration'))=='sha256:'+h,['AUD-02'])
freeze=data(OUT/'FREEZE-MANIFEST.json','immutable preregistration file inventory')
for r in freeze['files']:check('Original frozen file '+r['path'],sha(raw(OUT/r['path'],'immutable preregistration file inventory replay'))=='sha256:'+r['sha256'],['AUD-02'])
prereg=data(OUT/'preregistration.json'); claims=data(OUT/'planned-evidence-checks.json'); probes=data(OUT/'public-probes.json'); originals=data(OUT/'original-public-requirements.json')
check('Exactly immutable24 checks and9 probes',len(claims['checks'])==24 and len(probes['probes'])==9,['AUD-02'])
protocol=data(RUN/'protocol.json')
check('Exact prepared protocol',sha(raw(RUN/'protocol.json','exact prepared protocol identity'))=='sha256:64b91ccc1f1724877a7b158468dabd7f2ce22953ac7fa7e1a3d1d431dccac754',['AUD-02','AUD-03'])
check('Generation and excluded tool calls absent',protocol['generation_started'] is False and protocol['hidden_cases_loaded'] is False and protocol['python_grader_invoked'] is False and protocol['task_oracle_invoked'] is False,['AUD-01','AUD-02'])
check('Only D21 and exact requested boundary',protocol['task_order']==['D21'] and protocol['pair_order']==[{'arm':'verislop','pair_index':0,'task':'D21'}] and protocol['tier']==2 and protocol['endpoint']=='restricted_source' and protocol['target']=='vscore' and protocol['language']=='vscore/0.3' and protocol['profile']=='data-pipeline/0.3' and protocol['semantics']=='vscore-semantics/0.3' and protocol['require_state']=='END_TO_END_VERIFIED',['AUD-04','AUD-23'])
check('Exact new project location',protocol['project_path']==str(PROJECT),['AUD-03'])
check('Strict native independent two-build and optional TESTED policy',protocol['policy']=='strict' and protocol['native_cli_required'] is True and protocol['independent_clean_builds']==2 and protocol['runtime_campaign_requested'] is False,['AUD-17','AUD-23'])
check('Identity and token availability boundary',protocol['transport']=='collaboration-agent-simulation' and protocol['model_identity_attested'] is False and protocol['input_tokens'] is None and protocol['output_tokens'] is None and protocol['fresh_agent_per_request'] is True and protocol['fork_turns']=='none' and protocol['positive_candidate_arguments']==[],['AUD-19','AUD-23'])
check('No added inference deadline',all(protocol[k] is None for k in ['model_generation_deadline','proof_search_deadline','review_tier_deadline']),['AUD-06','AUD-23'])
input_hashes={}
for p,h in protocol['input_files'].items():
 b=raw(RUN/p,'exact frozen public prepared input bytes; engineering record restricted metadata only')
 input_hashes[p]=sha(b)
check('All prepared public input files match',input_hashes==protocol['input_files'],['AUD-02','AUD-03'])
check('Exact input root',digest(input_hashes)==protocol['input_root']=='sha256:c4c5fe017e95962b7f4d04af51fa55826c9cf044a25edd541147af01eb14b8e4',['AUD-02','AUD-03'])
check('Exact request root',digest({t['id']:t['revised_request_sha256'] for t in protocol['tasks']})==protocol['request_set_root']=='sha256:846461144ed0dcaec457d5a20f414910ab82a3409562919b612261adc8ac910c',['AUD-02','AUD-04'])
cohort_prereg=data(RUN/'preregistration.json')
check('Cohort prereg agrees before generation',cohort_prereg['generation_started'] is False and cohort_prereg['protocol_sha256']==sha(raw(RUN/'protocol.json','exact protocol binding')) and all(cohort_prereg[k]==protocol[k] for k in ['source_root','input_root','request_set_root']),['AUD-02','AUD-03'])
configuration=data(RUN/'config.json'); endpoint_profile=data(RUN/'provider-home/endpoint-profiles.json')
check('Configured required formal/release concrete reviews',configuration['bridge_tier']==2 and configuration['endpoint']=='restricted_source' and configuration['review']['checkpoints']==['formal_contract','release'] and all(configuration['release'][k] is True for k in ['require_all_review_tiers','require_mechanical_pass','require_requested_bridge_tier']) and configuration['review']['review_tiers'][0]['consensus']=={'blocking_findings_veto':True,'max_abstentions':0,'max_soft_rejects':0,'mode':'unanimous','require_all_responses':True},['AUD-19','AUD-23'])
check('Frozen simulation endpoint-profile identity',configuration['providers']['simulation']['endpoint_profile']=='collaboration-simulation' and 'collaboration-simulation' in endpoint_profile['profiles'] and protocol['endpoint_profiles_sha256']==input_hashes['provider-home/endpoint-profiles.json'],['AUD-19'])
original=raw(RUN/'requests/D21/original-prompt.txt','original public specification copied into new request')
revised=raw(RUN/'requests/D21/revised-prompt.txt','fresh revised public request only')
meta=data(RUN/'requests/D21/original-metadata.json'); rev=data(RUN/'requests/D21/delivery-revision.json'); policy=data(RUN/'requests/D21/source-policy.json')
check('Original public request identity retained',sha(original)=='sha256:'+originals['request_sha256']==meta['original_request_sha256']==rev['original_request_sha256'],['AUD-04'])
def original_identity(r):return {'id':r['id'],'kind':r['kind'],'role':r['role'],'required':r['required'],'source_spans':[{'start_byte':s['start_byte'],'end_byte':s['end_byte']} for s in r['source_refs']]}
expected_ids={r['id']:original_identity(r) for r in originals['records']}
actual_ids={r['id']:r for r in meta['identities']}
check('All exact11 original identity kinds roles requiredness/spans',len(meta['identities'])==11 and digest(actual_ids)==digest(expected_ids) and all(r['required'] is True for r in meta['identities']),['AUD-05'])
check('Original metadata hashes match public-only provenance',meta['metadata_hashes']=={'artifacts/D21/verislop/package/draft.json':'sha256:c9d3cfe8ecefca6645b0b575e1cacaba85afd6c9636ccaa4ed22484554d8f245','artifacts/D21/verislop/package/interpretation.json':'sha256:5dd0f68878f29eab07a066d39a025bfe7b64b654757f10570a52d64741161326'} and meta['old_positive_candidate_bytes_read'] is False,['AUD-02','AUD-05'])
check('Exact delivery revision input identities',rev['revised_request_sha256']==sha(revised) and rev['source_policy_sha256']==sha(raw(RUN/'requests/D21/source-policy.json','exact source policy hash')) and rev['functional_bytes_preserved'] is True and rev['old_delivery_assurance_relabelled'] is False,['AUD-04','AUD-07'])
cursor=0;revised_cursor=0
for segment in rev['segments']:
 check('Contiguous delivery segment '+str(cursor),segment['original_start_byte']==cursor and segment['revised_start_byte']==revised_cursor,['AUD-04'])
 a=original[segment['original_start_byte']:segment['original_end_byte']];b=revised[segment['revised_start_byte']:segment['revised_end_byte']]
 if segment['kind']=='preserved':check('Exact preserved functional bytes '+str(cursor),a==b and sha(a)==segment['sha256'],['AUD-04','AUD-06','AUD-07'])
 else:
  matches=[e for e in rev['edits'] if e['original_start_byte']==segment['original_start_byte'] and e['original_end_byte']==segment['original_end_byte']]
  check('Explicit recorded delivery edit '+str(cursor),len(matches)==1 and matches[0]['before'].encode()==a and matches[0]['after'].encode()==b,['AUD-04'])
 cursor=segment['original_end_byte'];revised_cursor=segment['revised_end_byte']
check('All original bytes covered by three explicit delivery edits only',cursor==len(original) and len(rev['edits'])==3 and rev['edits'][0]['original_start_byte']==79 and rev['edits'][0]['original_end_byte']==237 and rev['edits'][1]['original_start_byte']==1053 and rev['edits'][1]['original_end_byte']==1317 and rev['edits'][2]['original_start_byte']==1319 and rev['edits'][2]['original_end_byte']==1378,['AUD-04'])
example_bytes=original.split(b'Public examples (additional held-out cases will be scored):\n',1)[1]
check('Both public examples retained verbatim',sha(example_bytes)==rev['public_examples_sha256'] and revised[:revised_cursor].endswith(example_bytes),['AUD-04','AUD-09'])
check('Full unbounded valid domain explicitly preserved',original[238:366] in revised and b'There are no additional input bounds or preconditions beyond the functional specification.' in revised and b'unbounded mathematical integers' in revised and b'Unicode scalar values' in revised,['AUD-06'])
props=['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']
expected_policy={'format':'verislop.required-source-facets/0.1','schema_version':'0.1','obligations':{i:{'arity':1,'entry':'solve','file':'program.vscore.json','properties':props,'value_required':i not in ['I1','S1']} for i in prereg['required_guarantee_ids']}}
check('Exact nine required source rows and seven Mixed/two source-only classes',digest(policy)==digest(expected_policy) and rev['source_policy_classification']==protocol['tasks'][0]['source_policy_classification']=={'source_only_operational_ids':['I1','S1'],'value_required_default':True},['AUD-07'])
mappings={r['id']:r for r in rev['identity_mapping']}
check('Every original identity carried into delivery revision',len(rev['identity_mapping'])==11 and set(mappings)==set(expected_ids) and all(all(mappings[i][k]==expected_ids[i][k] for k in ['kind','role','required']) for i in mappings),['AUD-04','AUD-05'])
for i,r in mappings.items():
 check('Exact original mappings for '+i,[{'start_byte':s['original_start_byte'],'end_byte':s['original_end_byte']} for s in r['source_mappings']]==expected_ids[i]['source_spans'],['AUD-04','AUD-05'])
 for s in r['source_mappings']:
  if s['delivery_revised'] is False:check('Exact unchanged functional mapped span '+i+':'+str(s['original_start_byte']),original[s['original_start_byte']:s['original_end_byte']]==revised[s['revised_start_byte']:s['revised_end_byte']],['AUD-04','AUD-07'])
check('I1 causal bytes remain in full Mixed functional scope despite source-only row',all(original[s['start_byte']:s['end_byte']] in revised for s in expected_ids['I1']['source_spans']) and policy['obligations']['O5']['value_required'] is True and policy['obligations']['I1']['value_required'] is False and 'Original I1 causal behavior remains mandatory' in prereg['functional_preservation'],['AUD-07','AUD-09'])
workflow=rev['workflow_context']['text'].encode()
check('Supervisor context exact separate hash and no task evidence authority',len(workflow)==rev['workflow_context']['byte_length'] and sha(workflow)==rev['workflow_context']['sha256'] and workflow not in revised and b'does not establish their satisfaction' in workflow,['AUD-04','AUD-23'])
source_files=protocol['source_files']; check('Exactly241 source metadata entries and current c022 root',len(source_files)==241 and digest(source_files)==protocol['source_root']=='sha256:c0225d21274f4c4819800e3f136f49e68c9762eb0322860438e57d43e179db49',['AUD-03'])
snapshot=data(PROJECT/'TIER2-SNAPSHOT.json'); sourcefreeze=data(ROOT/'validation/tier2-native-boundary-gate-019/source-freeze.json')
check('Project snapshot and qualified source freeze exact241 identities',snapshot['source_files']==sourcefreeze['source_files']==source_files and snapshot['source_root']==sourcefreeze['source_root']==protocol['source_root'] and snapshot['cases_or_oracles_copied'] is False and snapshot['historical_snapshots_modified'] is False,['AUD-03'])
for location,label in [(ROOT,'current production'),(PROJECT,'fresh project'),(RUN/'execution-source','execution snapshot')]:
 observed={p:sha(raw(location/p,label+' generic public framework/source metadata hash only; no task artifact')) for p in source_files}
 check('All241 '+label+' byte hashes exact',observed==source_files,['AUD-03'])
 directories={'verislop':('.py','.lean'),'formal':('.lean',),'grammar':('.ebnf',),'schemas':('.json',),'policies':('.json',),'docs':('.md',)}
 observed_names=set()
 for directory,suffixes in directories.items():
  observed_names.update(p.relative_to(location).as_posix() for p in (location/directory).rglob('*') if p.suffix in suffixes and p.is_file())
 observed_names.update(p for p in source_files if p.split('/')[0] not in directories)
 for n in ('pyproject.toml','lean-toolchain','lakefile.lean','lake-manifest.json'):
  if (location/n).exists():observed_names.add(n)
 check('Exact full '+label+' production source name set',observed_names==set(source_files),['AUD-03'])
checkpoint_path=ROOT/'validation/tier2-native-boundary-gate-019/prelive-qualification-checkpoint.json';checkpoint=data(checkpoint_path)
audit_path=ROOT/'validation/tier2-collection-proof-support-audit-017/final-gate019-audit-report-attempt-003.json';audit=data(audit_path,'generic independent audit authority summary; no fixture source/proof read')
auditreceipt_path=ROOT/'validation/tier2-collection-proof-support-audit-017/final-gate019-audit-actual-process-receipt.json';auditreceipt=data(auditreceipt_path)
receipt_path=ROOT/'validation/tier2-native-boundary-gate-019/actual-process-receipt.json';receipt=data(receipt_path)
result_path=ROOT/'validation/tier2-native-boundary-gate-019/run-result.json';result=data(result_path,'generic qualification status/count/root metadata only; no test or fixture implementation')
engineering=data(RUN/'engineering-validation.json','generic engineering authority metadata only; no fixture source/proof read')
check('Exact completed gate019 authority hashes',sha(raw(checkpoint_path,'exact checkpoint hash'))=='sha256:73f62534da24e618c4872ab3c0563130864810463f81a4eb82b45426830cdda5' and sha(raw(audit_path,'exact independent audit report hash'))=='sha256:8cbd6725d78e4cc63a7e396491c73efeebfb080ff977af75b09c3f3f6b8e9d6a' and sha(raw(auditreceipt_path,'exact independent audit process receipt hash'))=='sha256:0f1c165c1ea356da9e83e1ab315dd96cb212a3f539460cb13b6d51b41f8ab291',['AUD-03'])
check('Completed independent7-claim generic audit actual rc0',audit['qualification_attempt']==auditreceipt['qualification_attempt']=='gate019' and audit['status']==auditreceipt['decision']=='VERIFIED' and auditreceipt['observed_exit_code']==0 and auditreceipt['claims_evaluated']==auditreceipt['claims_pass']==7 and auditreceipt['unresolved_required_findings']==0 and len(audit['claims'])==7 and all(c['status']=='PASS' for c in audit['claims']) and audit['concrete_unresolved_required_findings']==[],['AUD-03'])
check('Actual98-of98 rc0 gate019 and unchanged415/241/127 metadata',receipt['actual_returncode']==0 and result['qualification_attempt']=='gate019' and result['status']=='PASS' and result['tests_run']==result['registered_test_count']==result['expected_test_count']==result['unique_test_count']==98 and all(result[k]==0 for k in ['errors','failures','skipped','expected_failures','unexpected_successes']) and result['source_unchanged'] is True and result['test_inputs_unchanged'] is True and result['qualification_inputs_unchanged'] is True and result['source_root_before']==result['source_root_after']==protocol['source_root'] and result['test_source_count_before']==result['test_source_count_after']==127 and result['prior_pass_inheritance'] is False and receipt['model_calls']==result['fresh_model_calls']==0 and audit['current_full415_input_root']==auditreceipt['current_full415_input_root']=='sha256:87a2ec2b72dc3ab24e653c80a3886142f6541a72b659b4e19b32e532e01ad40d',['AUD-03'])
check('Checkpoint binds actual audit/process/result/engineering without task authority',checkpoint['status']=='VERIFIED' and checkpoint['generation_started'] is False and checkpoint['task_authority'] is False and checkpoint['source_hold_continues'] is True and checkpoint['source_root']==protocol['source_root'] and checkpoint['engineering_record_sha256']==input_hashes['engineering-validation.json'] and checkpoint['actual_process_receipt_sha256']==sha(raw(receipt_path,'exact completed gate receipt binding')) and checkpoint['run_result_sha256']==sha(raw(result_path,'exact completed gate result binding')) and checkpoint['independent_audit_sha256']==sha(raw(audit_path,'exact completed independent audit binding')) and checkpoint['independent_audit_receipt_sha256']==sha(raw(auditreceipt_path,'exact completed independent process binding')),['AUD-03'])
check('Engineering record exact current generic boundary only',engineering['status']=='VERIFIED' and engineering['fixture_only'] is True and engineering['model_authoring_input'] is False and engineering['fresh_model_calls']==0 and engineering['source_root']==protocol['source_root'] and engineering['source_freeze']==str(ROOT/'validation/tier2-native-boundary-gate-019/source-freeze.json') and engineering['source_freeze_sha256']==sha(raw(ROOT/'validation/tier2-native-boundary-gate-019/source-freeze.json','exact engineering source freeze binding')),['AUD-03','AUD-23'])
check('Prior failed qualifications never authority',all(x['qualification_authority'] is False for x in audit['prior_failed_attempts']) and {x['attempt'] for x in audit['prior_failed_attempts']}=={'gate017','gate018'},['AUD-03'])
driver_path=ROOT/'validation/tier2-native-live-driver-017/driver.py';spec_path=driver_path.with_name('orchestration-specification.json');spec=data(spec_path)
check('Exact preregistered new native driver and specification',sha(raw(driver_path,'native orchestration source metadata hash only; no execution'))=='sha256:68c731ecba93ea12e8a84c0013441a679f9d4374bf5220c97f2b61e2f702252d' and sha(raw(spec_path,'exact new orchestration specification hash'))=='sha256:d2ae65b5a21944b77586721a748e7846daf43226d502dff164c7b34620402a30' and spec['driver_executed'] is False and spec['driver_execution_authorized_by_preparation'] is False and spec['qualification_authority'] is False and spec['model_calls']==0 and spec['future_project']==str(PROJECT.relative_to(ROOT)) and spec['future_cohort']==str(RUN.relative_to(ROOT)),['AUD-02','AUD-03'])
prepare_path=driver_path.with_name('prepare-process-receipt.json');prepare=data(prepare_path)
check('Actual fresh snapshot/prepare rc0 and no generation',sha(raw(prepare_path,'exact actual preparation receipt binding'))=='sha256:f5518d4efcadfb7b6effce6f90b9aacdece1e352baf7685851337df36e9e644d' and prepare['actual_prepare_returncode']==prepare['actual_snapshot_returncode']==0 and prepare['fresh_model_calls']==0 and prepare['generation_started'] is False and prepare['project']==str(PROJECT) and prepare['cohort']==str(RUN) and all(prepare[k]==protocol[k] for k in ['source_root','input_root','request_set_root']) and prepare['protocol_sha256']==sha(raw(RUN/'protocol.json','actual preparation protocol binding')),['AUD-02','AUD-03'])
sys.path.insert(0,str(PROJECT))
from verislop import verifiers,canonical,__version__
check('Actual registry imported from exact fresh project',Path(verifiers.__file__).resolve()==PROJECT/'verislop/verifiers.py',['AUD-03'])
registry=verifiers.registry_snapshot();registry_inputs={}
for vid,entry in sorted(registry.items()):
 specv=verifiers.VERIFIERS[vid];rows=[]
 for rel in sorted(set(verifiers.CORE+specv['sources'])):
  p='verislop/'+rel
  check('Registered source exists and is frozen '+vid+':'+p,p in source_files,['AUD-03'])
  rows.append({'path':p,'sha256':source_files[p]});registry_inputs[p]=source_files[p]
 for n in sorted(specv['schemas']):
  p='schemas/'+n
  check('Registered schema exists and is frozen '+vid+':'+p,p in source_files,['AUD-03'])
  rows.append({'path':p,'sha256':source_files[p]});registry_inputs[p]=source_files[p]
 check('Exact independently recomputed registered verifier root '+vid,digest({'verifier':vid,'version':__version__,'files':rows})==entry['hash'],['AUD-03'])
check('Required current source/bridge/closure/review registries present',all(v in registry for v in ['verislop.vscore3-source-checker','verislop.vscore3-checker','verislop.vscore3-materializer','verislop.vscore3-linker','verislop.closure','verislop.review-consensus','verislop.review-counterexample']),['AUD-03'])
# Directory listings are metadata only. No actor inventory or task artifact is opened.
directory_paths=[PROJECT,RUN,ROOT/'validation/tier2-native-live-driver-017',RUN/'requests',RUN/'requests/D21',ROOT/'validation/tier2-native-boundary-gate-019',ROOT/'validation/tier2-collection-proof-support-audit-017']
listings=[]
for p in directory_paths:
 entries=sorted([{'name':e.name,'kind':'directory' if e.is_dir(follow_symlinks=False) else 'symlink' if e.is_symlink() else 'file'} for e in os.scandir(p)],key=lambda e:e['name'])
 listings.append({'path':str(p),'scope':'nonrecursive name/type metadata only','entries':entries,'listing_sha256':digest(entries)})
check('Prepared run still has only prepared inputs before calls',{e['name'] for e in listings[1]['entries']}=={'config.json','engineering-validation.json','execution-source','preregistration.json','protocol.json','provider-home','requests'},['AUD-01','AUD-02'])
check('Final generation flag/source/protocol/prereg bytes unchanged',data(RUN/'protocol.json')['generation_started'] is False and sha(raw(RUN/'protocol.json','final no-generation protocol recheck'))=='sha256:64b91ccc1f1724877a7b158468dabd7f2ce22953ac7fa7e1a3d1d431dccac754' and all(sha(raw(OUT/n,'final immutable preregistration recheck'))=='sha256:'+h for n,h in expected.items()),['AUD-01','AUD-02','AUD-03'])
registry_record=save('registered-verifier-snapshot-001.json',{'format':'scope-audit-registered-verifier-binding/1','audit_id':'tier2-d21-scope-audit-017','source_root':protocol['source_root'],'producer':str(PROJECT/'verislop/verifiers.py'),'producer_sha256':source_files['verislop/verifiers.py'],'version':__version__,'registry':registry,'registered_input_files':registry_inputs,'status':'current generic registered identity only; no task evidence or assigned task claim minted'})
# Record prior interactive metadata reads also; their exact current bytes were hashed above.
for p in [ROOT/'validation/tier2-collection-proof-support-audit-017/final-gate019-audit-attempt-003.py']:
 raw(p,'generic independent auditor implementation identity hash only; no code/fixture implementation inspected')
raw(PROJECT/'synthetic_dataset/tools/bootstrap_tier2.py','targeted generic public root/source inventory and request preservation checker excerpts; no task output')
raw(PROJECT/'verislop/verifiers.py','targeted generic registered verifier identity excerpts')
raw(PROJECT/'verislop/canonical.py','generic canonical hash/serialization source excerpts')
raw(Path(__file__),'exact binding verifier implementation')
read_record=save('pre-generation-read-ledger-001.json',{'format':'scope-audit-binding-read-ledger/1','audit_id':'tier2-d21-scope-audit-017','files':sorted(READS.values(),key=lambda x:x['path']),'directory_listings':listings,'not_read':['task candidates','task proofs','current or old task outputs','hidden tests/oracle/grader','generic fixture source or proof answers','model contexts','actor or collaboration inventory'],'import_trust':'Only fresh frozen generic registry modules were imported; CPython/toolchain/OS reads are explicit TCB, not task semantic evidence.'})
binding={'format':'scope-audit-pre-generation-binding/1','audit_id':'tier2-d21-scope-audit-017','created_at_utc':datetime.now(timezone.utc).isoformat(),'status':'BOUND_PENDING_NATIVE_EXECUTION','terminal_audit_status':None,'pre_generation_binding_gaps':0,'checks_executed':len(OBS),'checks_pass':sum(o['matches'] for o in OBS),'observations':OBS,'preregistration_unchanged':expected,'project':str(PROJECT),'run':str(RUN),'protocol_sha256':sha(raw(RUN/'protocol.json','bound protocol')),'source_root':protocol['source_root'],'source_files':241,'request_set_root':protocol['request_set_root'],'input_root':protocol['input_root'],'input_files':input_hashes,'generation_started':False,'model_calls_observed':0,'model_call_observation_basis':'Prepared protocol false generation flags and exact prepared-only run directory; parent confirms no calls/candidates. No actor inventory inspected.','qualification_authority':{'attempt':'gate019','support_milestone_label':'017','resolution':'The immutable preregistration term gate017 denotes support milestone017. The sole completed generic qualification authority is gate019; failed qualification017/018 supply no PASS or task evidence.','checkpoint':{'path':str(checkpoint_path),'sha256':sha(raw(checkpoint_path,'bound checkpoint'))},'actual_gate_receipt':{'path':str(receipt_path),'sha256':sha(raw(receipt_path,'bound actual gate receipt')),'actual_returncode':0,'tests_passed':98,'tests_expected':98},'independent_audit':{'path':str(audit_path),'sha256':sha(raw(audit_path,'bound generic audit')),'claims_pass':7,'task_authority':False},'independent_audit_receipt':{'path':str(auditreceipt_path),'sha256':sha(raw(auditreceipt_path,'bound actual independent audit receipt')),'observed_exit_code':0},'engineering_record':{'path':str(RUN/'engineering-validation.json'),'sha256':input_hashes['engineering-validation.json'],'task_authoring_input':False}},'native_driver':{'path':str(driver_path),'sha256':sha(raw(driver_path,'bound driver hash')),'specification_path':str(spec_path),'specification_sha256':sha(raw(spec_path,'bound driver specification hash')),'execution_granted_by_this_binding':False},'scope':{'original_ids':prereg['original_required_ids'],'guarantee_ids':prereg['required_guarantee_ids'],'mixed_ids':['O1','O2','O3','O4','O5','O6','O7'],'source_only_ids':['I1','S1'],'causal_functional_preservation':'All original I1 causal clauses stay mandatory in full Mixed functional scope including O5 and linked clauses; source-only I1 classification grants no omission.','full_domain':prereg['input_domain'],'endpoint':'restricted_source','tier':2,'identity_status':'UNATTESTED','token_metrics':None,'optional_TESTED':'No campaign requested; PENDING remains permissible and never rescored','assurance_assignment':'No task proof/lifecycle/closure state assigned; native END_TO_END_VERIFIED eligible only at exact restricted_source after complete current evidence.'},'registered_verifier_snapshot':registry_record,'read_ledger':read_record,'terminal_audit_preconditions':['Root confirms ALL native authors and controller stopped','Unique fresh sealed run and actual matching registered verifier supplied','Complete native/bootstrap manifests and seals supplied','All frozen24 checks evaluated against sealed fresh evidence'],'frozen_checks':24,'frozen_public_probes':9,'future_task_artifacts_inspected':False,'stop':'Binding complete. STOP awaiting sealed terminal run and all-actors-stopped confirmation.'}
binding['prepare_receipt']={'path':str(prepare_path),'sha256':sha(raw(prepare_path,'bound actual preparation receipt')),'actual_prepare_returncode':0,'actual_snapshot_returncode':0,'fresh_model_calls':0}
binding_record=save('pre-generation-binding-001.json',binding)
script_hash=sha(raw(Path(__file__),'exact binding verifier implementation'))
manifest_record=save('PRE-GENERATION-BINDING-MANIFEST-001.json',{'format':'scope-audit-binding-manifest/1','audit_id':'tier2-d21-scope-audit-017','preregistration_freeze_sha256':'sha256:'+expected['FREEZE-MANIFEST.json'],'binding_verifier':{'path':str(Path(__file__)),'sha256':script_hash},'files':[binding_record,registry_record,read_record],'binding_only':True,'terminal_audit_status':None})
print(json.dumps({'status':'BOUND_PENDING_NATIVE_EXECUTION','binding_gaps':0,'checks_pass':len(OBS),'binding':binding_record,'registry':registry_record,'read_ledger':read_record,'manifest':manifest_record,'verifier_sha256':script_hash,'source_root':protocol['source_root'],'protocol_sha256':sha((RUN/'protocol.json').read_bytes()),'generation_started':False,'terminal_audit_status':None},sort_keys=True))
