#!/usr/bin/env python3
"""Bounded Stage012 prepared-input audit. No verifier, Lean, provider or task execution."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil

ROOT = Path('/home/augustus/VeriSlop_CLI')
STAGE = ROOT / 'synthetic_dataset/bootstrap/stages/tier2-source-facets-012'
RUN, PROJECT = STAGE / 'run', STAGE / 'project'
GATE = ROOT / 'validation/tier2-native-boundary-gate-012'
OUT = Path(__file__).resolve().parent
EXPECTED = {
 'source_root':'sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710',
 'protocol_sha256':'sha256:c5fcfa3f53c1d0b89f1fa7bff8b43390e27b31ec68fa69c354c48e8b46f11ecd',
 'input_root':'sha256:ca65b795d33b64d0766d29d03514dfe8d29ea6549f807060c0420abca7246b2a',
 'request_set_root':'sha256:846461144ed0dcaec457d5a20f414910ab82a3409562919b612261adc8ac910c',
 'checkpoint_sha256':'sha256:078e4fc835d4a1847b390785fd57b313661aeab28b8e57719c94d5168fffb5e7'
}
def digest(data): return 'sha256:' + hashlib.sha256(data).hexdigest()
def dumps(obj): return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def jsonroot(obj): return digest(dumps(obj))
def load(path): return json.loads(path.read_bytes())
def now(): return datetime.now(timezone.utc).isoformat()
checks, snapshots, captured = [], {}, {}
started = now()
def check(name, ok, detail=None):
 row={'check':name,'ok':bool(ok)}
 if detail is not None: row['detail']=detail
 checks.append(row)
 return bool(ok)
def capture(path, label):
 path=Path(path)
 check('regular_non_symlink:'+label,path.is_file() and not path.is_symlink())
 data=path.read_bytes()
 target=OUT/'snapshots'/label
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(data)
 snapshots[label]={'source':str(path),'sha256':digest(data),'size_bytes':len(data)}
 captured[str(path)]=digest(data)
 return data

def capture_json(path,label): return json.loads(capture(path,label))
protocol=capture_json(RUN/'protocol.json','cohort/protocol.json')
prereg=capture_json(RUN/'preregistration.json','cohort/preregistration.json')
check('protocol_hash',digest((RUN/'protocol.json').read_bytes())==EXPECTED['protocol_sha256'])
# Protocol file bytes, not a reserialized JSON value, are preregistered.
check('prereg_protocol_binding',prereg['protocol_sha256']==EXPECTED['protocol_sha256'])
for key in ('source_root','input_root','request_set_root'):
 check('expected_'+key,protocol[key]==EXPECTED[key] and prereg[key]==EXPECTED[key])
check('source_root_recomputed',jsonroot(protocol['source_files'])==protocol['source_root'])
check('source_member_count',len(protocol['source_files'])==230)
check('input_root_recomputed',jsonroot(protocol['input_files'])==protocol['input_root'])
check('request_root_recomputed',jsonroot({x['id']:x['revised_request_sha256'] for x in protocol['tasks']})==protocol['request_set_root'])
check('fresh_task_selection',protocol['task_order']==['D21'] and len(protocol['tasks'])==1)
check('frozen_project',protocol['project_path']==str(PROJECT))
check('explicit_boundary',all(protocol[k]==v for k,v in {'backend_version':'0.3','target':'vscore','tier':2,'endpoint':'restricted_source','require_state':'END_TO_END_VERIFIED','language':'vscore/0.3','semantics':'vscore-semantics/0.3','profile':'data-pipeline/0.3','policy':'strict'}.items()))
check('no_positive_candidate_arguments',protocol['positive_candidate_arguments']==[])
check('no_hidden_or_oracle_or_runtime_campaign',all(protocol[k] is False for k in ('hidden_cases_loaded','task_oracle_invoked','python_grader_invoked','runtime_campaign_requested')))
check('fresh_isolated_roles',protocol['fork_turns']=='none' and protocol['fresh_agent_per_request'] is True and protocol['native_cli_required'] is True)
check('two_engineering_builds_requested',protocol['independent_clean_builds']==2)
check('prereg_before_generation',prereg['generation_started'] is False)
for name,sha in protocol['input_files'].items():
 data=capture(RUN/name,'cohort/'+name)
 check('input_binding:'+name,digest(data)==sha)
for name,sha in protocol['source_files'].items():
 for base,label in ((PROJECT,'frozen-project'),(RUN/'execution-source','execution-source')):
  data=capture(base/name,label+'/'+name)
  check('source_binding:'+label+'/'+name,digest(data)==sha)

metadata=load(RUN/'requests/D21/original-metadata.json')
policy=load(RUN/'requests/D21/source-policy.json')
revision=load(RUN/'requests/D21/delivery-revision.json')
original=(RUN/'requests/D21/original-prompt.txt').read_bytes()
revised=(RUN/'requests/D21/revised-prompt.txt').read_bytes()
public=capture(ROOT/'synthetic_dataset/tasks/D21/prompt.txt','public-task/prompt.txt')
check('public_prompt_exact',public==original)
identities=metadata['identities']
expected_ids=['D1','I1','O1','O2','O3','O4','O5','O6','O7','A1','S1']
check('all_11_original_identities',len(identities)==11 and [x['id'] for x in identities]==expected_ids and all(x['required'] is True for x in identities))
check('original_identity_role_kinds',[(x['id'],x['role'],x['kind']) for x in identities]==[('D1','declaration','entity'),('I1','guarantee','invariant')]+[(f'O{i}','guarantee','postcondition') for i in range(1,8)]+[('A1','assumption','precondition'),('S1','guarantee','safety_property')])
check('original_provenance_binding',metadata['original_request_sha256']==digest(original) and metadata['old_positive_candidate_bytes_read'] is False and metadata['previous_python_assurance']=='unchanged; no Tier 2 reinterpretation')
for row in identities:
 for i,span in enumerate(row['source_spans']):
  check('original_span:'+row['id']+':'+str(i),type(span['start_byte']) is int and type(span['end_byte']) is int and 0<=span['start_byte']<span['end_byte']<=len(original))
check('identity_mapping_exact_metadata', [{k:x[k] for k in ('id','role','kind','required')} for x in revision['identity_mapping']]==[{k:x[k] for k in ('id','role','kind','required')} for x in identities])
check('revision_hash_bindings',revision['original_request_sha256']==digest(original) and revision['revised_request_sha256']==digest(revised) and revision['source_policy_sha256']==digest((RUN/'requests/D21/source-policy.json').read_bytes()))
check('delivery_only_revision_count',len(revision['edits'])==3)
for i,edit in enumerate(revision['edits']):
 check('before_edit_exact:'+str(i),original[edit['original_start_byte']:edit['original_end_byte']]==edit['before'].encode())
 check('after_edit_exact:'+str(i),revised[edit['revised_start_byte']:edit['revised_end_byte']]==edit['after'].encode())
for i,seg in enumerate(revision['segments']):
 if seg['kind']=='preserved':
  old=original[seg['original_start_byte']:seg['original_end_byte']]
  new=revised[seg['revised_start_byte']:seg['revised_end_byte']]
  check('functional_preserved_segment:'+str(i),old==new and digest(old)==seg['sha256'])
check('complete_original_segment_partition',revision['segments'][0]['original_start_byte']==0 and revision['segments'][-1]['original_end_byte']==len(original) and all(x['original_end_byte']==y['original_start_byte'] for x,y in zip(revision['segments'],revision['segments'][1:])))
marker=b'Public examples (additional held-out cases will be scored):\n'
examples=original.split(marker,1)[1]
check('public_examples_preserved',examples in revised and digest(examples)==revision['public_examples_sha256'] and len(json.loads(examples))==2)
check('explicit_no_added_bounds',b'There are no additional input bounds or preconditions beyond the functional specification.' in revised)
check('explicit_unbounded_integer_unicode_order',b'Arithmetic uses unbounded mathematical integers without floating point.' in revised and b'Strings contain Unicode scalar values and lexicographic order compares scalar codepoints.' in revised)
check('sourcepolicy_exact_nine_ids',set(policy['obligations'])=={'I1','S1',*[f'O{i}' for i in range(1,8)]})
properties=['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']
for id,row in policy['obligations'].items():
 check('source_policy_closed_row:'+id,row=={'file':'program.vscore.json','entry':'solve','arity':1,'properties':properties,'value_required':id not in ('I1','S1')})
classification={'source_only_operational_ids':['I1','S1'],'value_required_default':True}
check('source_policy_classification',revision['source_policy_classification']==classification and protocol['tasks'][0]['source_policy_classification']==classification)
workflow=revision['workflow_context']; workflow_bytes=workflow['text'].encode('utf-8')
(OUT/'workflow-context.utf8.txt').write_bytes(workflow_bytes)
check('workflow_exact_utf8_hash',workflow['encoding']=='utf-8' and workflow['byte_length']==len(workflow_bytes)==1055 and workflow['sha256']==digest(workflow_bytes))
check('workflow_separate_from_program_prompt',workflow_bytes not in revised and b'Supervisor workflow context for this verification run:' not in revised)
check('workflow_prereg_bound',protocol['input_files']['requests/D21/delivery-revision.json']==digest((RUN/'requests/D21/delivery-revision.json').read_bytes()))

# Only these pure input-transformation functions are called from the frozen source.
sys.path.insert(0,str(PROJECT))
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
check('pure_reconstruction_module_is_frozen',Path(bootstrap.__file__).resolve()==PROJECT/'synthetic_dataset/tools/bootstrap_tier2.py')
reconstructed_prompt,reconstructed_revision=bootstrap.revise_prompt(original,identities,operational_ids=('I1','S1'))
check('pure_revision_reconstruction',reconstructed_prompt==revised and reconstructed_revision==revision)
check('pure_source_policy_reconstruction',bootstrap.source_policy(identities,operational_ids=('I1','S1'))==policy)

scope_clauses=[
 ('input_domain','Input {events:[{group:string,time:int,value:int|null}],start:int,end:int,width:positive int,fill:\'none\'|\'previous\'}, start<=end.'),
 ('all_groups_scalar_sort','Groups are all unique event group names sorted lexicographically, including groups with no in-range events.'),
 ('half_open_clipped_buckets','For each group, emit buckets starting start,start+width,... strictly below end, each covering [bucketStart,min(bucketStart+width,end)).'),
 ('nonnull_sum_count','Sum only non-null in-range values; count counts these values.'),
 ('nonempty_sum_previous','A nonempty bucket has value=sum and becomes previous value.'),
 ('causal_empty_fill_no_reset','Empty bucket value is null for fill none, or latest previous nonempty bucket sum for fill previous (null before first); empty buckets never reset previous.'),
 ('no_prestart_seed','Events before start never seed previous.'),
 ('layout_group_then_bucket_order','Return [{group,start,count,value}] in group then bucket order.'),
 ('zero_previous_duplicates','Zero sum is a real previous value, duplicates are counted.')]
scope=[]
for name,clause in scope_clauses:
 data=clause.encode(); start=original.find(data)
 check('public_semantic_clause_preserved:'+name,start>=0 and revised.count(data)==original.count(data)==1)
 scope.append({'facet':name,'original_start_byte':start,'original_end_byte':start+len(data),'exact_public_clause':clause,'revised_start_byte':revised.find(data),'stage':'prepared_request_only'})
(OUT/'scope-checklist.json').write_bytes(dumps(scope)+b'\n')

checkpoint=capture_json(GATE/'prelive-qualified-checkpoint.json','qualification/prelive-qualified-checkpoint.json')
check('qualification_checkpoint_hash',digest((GATE/'prelive-qualified-checkpoint.json').read_bytes())==EXPECTED['checkpoint_sha256'])
for name,sha in checkpoint['evidence'].items():
 data=capture(ROOT/name,'qualification/evidence/'+name)
 check('qualified_evidence_binding:'+name,digest(data)==sha)
freeze=load(GATE/'source-freeze.json')
engineering=load(GATE/'engineering-record.json')
results=load(GATE/'run-result.json')
test_sources=load(GATE/'test-sources.json')
capture(GATE/'invocation.json','qualification/invocation.json')
if (GATE/'driver-invocation.json').is_file(): capture(GATE/'driver-invocation.json','qualification/driver-invocation.json')
check('qualification_same_frozen_source',freeze['source_root']==protocol['source_root']==checkpoint['source_root']==engineering['source_root']==results['source_root_before']==results['source_root_after'] and freeze['source_files']==protocol['source_files'])
check('qualification_record_prereg_input_exact',(RUN/'engineering-validation.json').read_bytes()==(GATE/'engineering-record.json').read_bytes())
check('qualification_before_task_models',checkpoint['fresh_task_model_calls']==0 and checkpoint['task_outcome_claim'] is False and checkpoint['status']=='QUALIFIED' and checkpoint['native_fixture_status']=='PASS' and freeze['generation_started'] is False)
check('qualification_unrelated_fixture_only',engineering['fixture_only'] is True and engineering['model_authoring_input'] is False and engineering['fresh_model_calls']==0 and engineering['scope']=='current generic complete restricted-source engineering closure; no benchmark answer transfer')
check('qualified_54_tests',results['status']=='PASS' and results['tests_run']==54 and results['failures']==results['errors']==results['skipped']==0 and results['fresh_model_calls']==0 and results['source_unchanged'] is True and results['test_sources_unchanged'] is True)
check('qualification_test_sources_exact',results['test_sources']==test_sources['files'])
for name,sha in test_sources['files'].items():
 data=capture(ROOT/name,'qualification/tests/'+name)
 check('qualification_retained_test_hash:'+name,digest(data)==sha)
fixture=Path(engineering['package'])
check('unrelated_fixture_package_path','tier2-source-pipeline-pass/verislop-data-source-tier2-fixture-' in str(fixture) and '/stages/' not in str(fixture))
check('fixture_inventory_root',jsonroot(engineering['package_files'])==engineering['package_files_root'] and len(engineering['package_files'])==361)
for name,sha in engineering['package_files'].items():
 data=capture(fixture/name,'qualification/opaque-fixture/'+name)
 check('opaque_fixture_member:'+name,digest(data)==sha)
mech=load(fixture/engineering['mechanical_result'])
check('engineering_mechanical_result_hash',digest((fixture/engineering['mechanical_result']).read_bytes())==engineering['mechanical_result_sha256'])
check('engineering_mechanical_snapshot_identity',engineering['closure_id']==mech['closure_id'] and engineering['closure_root']==mech['closure_root'] and engineering['builds']==mech['builds'] and engineering['determinism']==mech['determinism'] and mech['mechanical_status']=='VERIFIED')
check('engineering_two_builds_exact',{b['build'] for b in mech['builds']}=={'A','B'} and all(b['ok'] is True for b in mech['builds']))
check('engineering_required_46_claims',len(engineering['required_claim_observations'])==46 and engineering['required_claim_observations']==[c for c in mech['claims'] if c['required']] and all(c['outcome']=='PASS' for c in engineering['required_claim_observations']))
check('engineering_determinism_no_mismatch',mech['determinism']['mismatches']==[])
check('engineering_freeze_hash',digest(Path(engineering['source_freeze']).read_bytes())==engineering['source_freeze_sha256'])
for slot,row in engineering['selected_inputs'].items():
 check('engineering_selected_input_hash:'+slot,engineering['package_files'].get(row['path'])==row['sha256'])
for row in mech['execution_inventory']:
 # Inventory is scoped to its execution directory; fixture member map includes that prefix.
 p=fixture/'closure/executions'/mech['attempt_id']/row['path']
 check('engineering_execution_inventory:'+row['path'],p.is_file() and digest(p.read_bytes())==row['sha256'] and p.stat().st_size==row['size'])

outer=capture_json(RUN/'artifacts/D21/verislop/invocation.json','native-origin/invocation.json')
cli=capture_json(RUN/'artifacts/D21/verislop/cli-invocation.json','native-origin/cli-invocation.json')
carrier=capture_json(RUN/'artifacts/D21/verislop/mailbox/request-0001.json','native-origin/request-0001.json')
check('native_no_candidate_transfer',outer['candidate_inputs']==[] and cli['positive_candidate_arguments']==[] and cli['python_runtime_campaign'] is False)
check('native_frozen_cwd',outer['cwd']==str(PROJECT))
args=cli['argv']
for flag,value in [('--prompt-file',str(RUN/'requests/D21/revised-prompt.txt')),('--source-policy',str(RUN/'requests/D21/source-policy.json')),('--request-ref','tier2:tier2-source-facets-012:D21'),('--endpoint','restricted_source'),('--require-state','END_TO_END_VERIFIED'),('--backend-version','0.3'),('--target','vscore')]:
 check('actual_cli_binding:'+flag,flag in args and args[args.index(flag)+1]==value)
check('initial_fresh_role',carrier['purpose']=='interpret' and carrier['instance']=='interpreter/1')
check('initial_carrier_exact_revised_request',revised.decode() in carrier['user'])
check('initial_carrier_no_previous_cohort_or_fixture_inputs',all(token not in carrier['user'] for token in ('tier2-source-facets-011','tier2-source-facets-010','tier2-source-pipeline-pass',*[x['sha256'] for x in engineering['selected_inputs'].values()])))
# Prior source/proof bytes are not opened. Opaque generic fixture qualification bytes cannot become task proof.
for path,sha in captured.items():
 check('captured_input_unchanged:'+str(Path(path).relative_to(ROOT)),digest(Path(path).read_bytes())==sha)

pending={name:(RUN/relative).exists() for name,relative in {
 'canonical_interpretation_available':'artifacts/D21/verislop/package/interpretation.json',
 'frozen_challenge_available':'artifacts/D21/verislop/package/contract/challenge/challenge.json',
 'accepted_ir_available':'artifacts/D21/verislop/package/accepted/accepted-ir.json',
 'implementation_available':'artifacts/D21/verislop/package/bridges/implementation',
 'mechanical_pointer_available':'artifacts/D21/verislop/package/closure/current.json',
 'terminal_native_result_available':'artifacts/D21/verislop/result.json',
 'bootstrap_terminal_available':'BOOTSTRAP-RESULT.json'
}.items()}
failures=[x for x in checks if not x['ok']]
summary={
 'format':'verislop.independent-stage012-prepared-scope-audit/0.1',
 'started_at_utc':started,'finished_at_utc':now(),'auditor_task':'/root/tier2_semantics_audit',
 'authority':'Exact fresh prepared request and immutable frozen project; stored unrelated qualification bytes only.',
 'phase':'initial_prepared_request','outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failures else 'AUDIT_CHECK_FAILURE',
 'bounds':EXPECTED,'checks_total':len(checks),'failed_checks':failures,'snapshots_count':len(snapshots),
 'semantic_scope':scope,'original_identity_count':len(identities),'source_policy_rows':len(policy['obligations']),
 'functional_value_required_ids':[f'O{i}' for i in range(1,8)],'source_only_ids':['I1','S1'],
 'qualification':{'status':checkpoint['status'],'tests':54,'two_clean_builds_recorded':all(b['ok'] for b in mech['builds']),'required_claims':46,'fresh_task_model_calls_before_live':0,'is_D21_implementation_evidence':False},
 'artifact_availability_only':pending,
 'limitations':[
  'No formalized or accepted D21 formula, proof, implementation or bridge was inspected in this initial phase.',
  'Presence of later task artifacts is availability only and does not establish their validity or completeness.',
  'Original identity provenance is authenticated through the prepared metadata and its preregistered input hash; historical task packages were not reopened.',
  'Qualification is an unrelated engineering fixture; its proofs and source are not D21 assurance.',
  'Natural-language correspondence, controller copies, pinned kernel, host tooling, hashing and OS/hardware remain explicit trust.',
  'No model, native CLI, Lean/kernel, mechanical closure, runtime campaign, task reference, hidden case or oracle was invoked.',
  'No live cohort, frozen project or production file was edited.'
 ]}
(OUT/'checks.json').write_bytes(dumps(checks)+b'\n')
(OUT/'snapshots.json').write_bytes(dumps(snapshots)+b'\n')
(OUT/'audit.json').write_bytes(dumps(summary)+b'\n')
print(json.dumps({'receipt':str(OUT/'audit.json'),'audit_sha256':digest((OUT/'audit.json').read_bytes()),'checks':len(checks),'failures':failures,'snapshots':len(snapshots),'pending_availability':pending},sort_keys=True))
