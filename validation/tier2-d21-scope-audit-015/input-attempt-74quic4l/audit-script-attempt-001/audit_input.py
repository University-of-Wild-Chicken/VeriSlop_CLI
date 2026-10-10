from pathlib import Path
import json,hashlib,sys,datetime
root=Path(__file__).resolve().parent;snap=json.loads((root/'snapshot.json').read_text());run=Path(snap['cohort']);project=Path(snap['source_project']);sys.path.insert(0,str(project))
from verislop import canonical
obj=lambda p:canonical.loads((root/'inputs'/p).read_bytes());read=lambda p:(root/'inputs'/p).read_bytes();checks=[]
def ck(n,v,d=None):
 assert v,n
 checks.append({'name':n,'result':'PASS','detail':d})
proto=obj('protocol.json');pre=obj('preregistration.json');revision=obj('requests/D21/delivery-revision.json');metadata=obj('requests/D21/original-metadata.json');sourcepolicy=obj('requests/D21/source-policy.json');original=read('requests/D21/original-prompt.txt');revised=read('requests/D21/revised-prompt.txt')
ck('exact preregistered protocol and source/input/request roots',pre['protocol_sha256']==canonical.digest(read('protocol.json')) and all(pre[k]==proto[k] for k in ('source_root','input_root','request_set_root')) and canonical.digest_json(proto['source_files'])==proto['source_root'] and canonical.digest_json(proto['input_files'])==proto['input_root'] and canonical.digest_json({t['id']:t['revised_request_sha256'] for t in proto['tasks']})==proto['request_set_root'])
for name,h in proto['input_files'].items():assert canonical.digest(read(name))==h,name
ck('every eight preregistered prepared input byte hash actual',True,len(proto['input_files']))
ck('only newD21 task request,original/revised hashes and sourcepolicy exact preregistered',len(proto['tasks'])==1 and proto['tasks'][0]['id']=='D21' and proto['tasks'][0]['original_request_sha256']==revision['original_request_sha256']==metadata['original_request_sha256']==canonical.digest(original) and proto['tasks'][0]['revised_request_sha256']==revision['revised_request_sha256']==canonical.digest(revised) and proto['tasks'][0]['source_policy_sha256']==revision['source_policy_sha256']==canonical.digest(read('requests/D21/source-policy.json')))
ids={r['id']:r for r in metadata['identities']};mapped={r['id']:r for r in revision['identity_mapping']};expected={'D1','A1','I1','S1',*[f'O{i}' for i in range(1,8)]}
ck('all exact11 original identities/roles/kinds/requiredness retained',len(metadata['identities'])==len(revision['identity_mapping'])==11 and set(ids)==set(mapped)==expected and all(r['required'] is True and (r['kind'],r['role'],r['required'])==(mapped[k]['kind'],mapped[k]['role'],mapped[k]['required']) for k,r in ids.items()))
for seg in revision['segments']:
 a=original[seg['original_start_byte']:seg['original_end_byte']];b=revised[seg['revised_start_byte']:seg['revised_end_byte']]
 if seg['kind']=='preserved':assert a==b and canonical.digest(a)==seg['sha256']
for edit in revision['edits']:
 assert original[edit['original_start_byte']:edit['original_end_byte']].decode()==edit['before'] and revised[edit['revised_start_byte']:edit['revised_end_byte']].decode()==edit['after']
ck('all preserved UTF8functional/publicexample segments identical;only three declared delivery edits',True,{'preserved_segments':sum(s['kind']=='preserved' for s in revision['segments']),'explicit_delivery_edits':len(revision['edits'])})
for ident in ids:
 for mapping in mapped[ident]['source_mappings']:
  a=original[mapping['original_start_byte']:mapping['original_end_byte']];b=revised[mapping['revised_start_byte']:mapping['revised_end_byte']]
  assert a.decode() and b.decode()
  if not mapping['delivery_revised']:assert a==b
ck('original clause offsets map exactly without functional clause replacement',True)
example=original[original.index(b'[{"input"'):].strip();newexample=revised[revised.index(b'[{"input"'):revision['segments'][-1]['revised_end_byte']].strip()
ck('both original public examples preserved exact bytes and declared example digest',example==newexample and canonical.digest(example)==revision['public_examples_sha256'],canonical.digest(example))
props=['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only'];guarantees={'I1','S1',*[f'O{i}' for i in range(1,8)]}
ck('exact closed nine mandatory source rows,complete properties/file/entry/arity',set(sourcepolicy)=={'format','schema_version','obligations'} and set(sourcepolicy['obligations'])==guarantees and all(set(row)=={'file','entry','arity','properties','value_required'} and row['file']=='program.vscore.json' and row['entry']=='solve' and type(row['arity']) is int and row['arity']==1 and row['properties']==props for row in sourcepolicy['obligations'].values()))
classification={'source_only_operational_ids':['I1','S1'],'value_required_default':True}
ck('only explicitly requested I1/S1 source-only;all O1-O7 require complete values',revision['source_policy_classification']==proto['tasks'][0]['source_policy_classification']==classification and all(row['value_required'] is (ident not in ('I1','S1')) for ident,row in sourcepolicy['obligations'].items()))
workflow=revision['workflow_context'];wbytes=workflow['text'].encode('utf-8')
ck('workflowcontext exact UTF8/hash-bound sidecar and absent from program request',set(workflow)=={'text','encoding','byte_length','sha256'} and workflow['encoding']=='utf-8' and len(wbytes)==workflow['byte_length']==1055 and canonical.digest(wbytes)==workflow['sha256'] and wbytes not in revised and b'Supervisor workflow context for this verification run:' not in revised)
request=obj('artifacts/D21/verislop/package/request/request.json')
ck('native package request/policy bytes exactly prepared public request/policy',read('artifacts/D21/verislop/package/request/prompt.txt')==revised and read('artifacts/D21/verislop/package/request/source-policy.json')==read('requests/D21/source-policy.json') and request['document_hash']==canonical.digest(revised) and request['byte_length']==len(revised) and request['request_ref']==proto['tasks'][0]['revised_request_ref'])
ck('complete unbounded domain and scalar semantics retained in revised text',b"width:positive int,fill:'none'|'previous'}, start<=end." in revised and b'There are no additional input bounds or preconditions beyond the functional specification.' in revised and b'Arithmetic uses unbounded mathematical integers without floating point.' in revised and b'Strings contain Unicode scalar values and lexicographic order compares scalar codepoints.' in revised)
ck('declared fresh isolated roles,no prior-positive arguments/oracles or runtime campaigns',proto['fresh_agent_per_request'] is True and proto['fork_turns']=='none' and proto['positive_candidate_arguments']==[] and proto['hidden_cases_loaded'] is False and proto['task_oracle_invoked'] is False and proto['python_grader_invoked'] is False and proto['runtime_campaign_requested'] is False and proto['independent_clean_builds']==2 and proto['model_identity_attested'] is False,{'requested_model':proto['requested_model'],'actual_model_identity':'UNATTESTED by protocol; no claim of attestation from labels'})
ck('exact restricted-source Tier2 boundary and honest originalPython assurance',proto['tier']==2 and proto['endpoint']=='restricted_source' and proto['target']=='vscore' and proto['backend_version']=='0.3' and proto['language']=='vscore/0.3' and proto['semantics']=='vscore-semantics/0.3' and proto['profile']=='data-pipeline/0.3' and proto['require_state']=='END_TO_END_VERIFIED' and revision['old_delivery_assurance_relabelled'] is False and metadata['previous_python_assurance']=='unchanged; no Tier 2 reinterpretation')
checkpoint=obj('composed-prelive-qualified-checkpoint.json');driver=obj('driver.json')
ck('honest composed generic readiness checkpoint predates sole native driver',checkpoint['status']=='QUALIFIED_FOR_FRESH_GENERATION' and checkpoint['fresh_all162_pass_claim'] is False and checkpoint['source_root']==proto['source_root'] and checkpoint['task_model_calls_before_qualification']==0 and checkpoint['task_cohort_prepared_before_qualification'] is False and datetime.datetime.fromisoformat(checkpoint['created_at_utc'])<datetime.datetime.fromisoformat(driver['started_at_utc']))
currency=obj('source-byte-currency.json') if (root/'inputs/source-byte-currency.json').exists() else canonical.load_file(root/'source-byte-currency.json')
execution={}
for rel,h in proto['source_files'].items():
 assert canonical.digest((project/rel).read_bytes())==currency['files'][rel]==h
 data=(run/'execution-source'/rel).read_bytes();assert canonical.digest(data)==h,rel;execution[rel]=h
(root/'execution-source-currency.json').write_bytes(canonical.dumps({'source_root':proto['source_root'],'all238_actual_native_execution_source_bytes_match':True,'files':execution}))
ck('all238 frozenproject and actual execution-source producer bytes exacte3b root',True,len(execution))
result={'format':'verislop.independent-fresh-D21-initial-scope-audit/1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'scope':'Only fresh stage015 public original/revised request,identity metadata,frozen sourcepolicy,preregistration/context/readiness and actual request bytes inspected. No interpretation/accepted/source/proof/native closure acceptance is asserted; those artifacts were pending at capture.'}
(root/'input-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
