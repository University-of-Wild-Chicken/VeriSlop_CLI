#!/usr/bin/env python3
"""Fresh013 finalized interpretation audit; pure validation and byte inspection only."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-013';RUN=STAGE/'run';PROJECT=STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';OUT=Path(__file__).resolve().parent
checks={};snaps={};observed={}
def h(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def d(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def check(k,b,detail=None):
 checks[k]={'ok':bool(b)}
 if detail is not None:checks[k]['detail']=detail
def capture(p,label):
 p=Path(p);check('regular:'+label,p.is_file() and not p.is_symlink());b=p.read_bytes();q=OUT/'snapshots'/label;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);snaps[label]={'source':str(p),'sha256':h(b),'bytes':len(b)};observed[str(p)]=h(b);return b
def js(p,label):return json.loads(capture(p,label))
protocol=js(RUN/'protocol.json','protocol.json');prereg=js(RUN/'preregistration.json','preregistration.json');check('protocol_prereg',prereg['protocol_sha256']==h((RUN/'protocol.json').read_bytes())=='sha256:3b7ed1f7943fe79d62c7da8d928e9a72b73a6b57fbedfe3ebe1d1b57e6288042' and protocol['source_root']==prereg['source_root']==h(d(protocol['source_files'])))
for f,sha in protocol['source_files'].items():check('frozen_source:'+f,h(capture(PROJECT/f,'project/'+f))==sha)
for f,sha in protocol['input_files'].items():check('frozen_input:'+f,h(capture(RUN/f,'prepared/'+f))==sha)
metadata=json.loads((RUN/'requests/D21/original-metadata.json').read_bytes());policy=json.loads((RUN/'requests/D21/source-policy.json').read_bytes());revision=json.loads((RUN/'requests/D21/delivery-revision.json').read_bytes());prompt=(RUN/'requests/D21/revised-prompt.txt').read_bytes()
ledger=js(PKG/'interpretation.json','package/interpretation.json');draft=js(PKG/'draft.json','package/draft.json')
sys.path.insert(0,str(PROJECT))
from verislop import draft as D,lifecycle
from verislop.package import Package
diags=D.validate_draft(draft,prompt,'tier2:tier2-source-facets-013:D21');ld,coverage=D.validate_ledger(ledger,draft,prompt,'tier2:tier2-source-facets-013:D21');blocked=D.blocked_obligations(draft,ledger)
check('registered_pure_draft_validation',not diags,[x.to_json() for x in diags]);check('registered_pure_ledger_validation',not ld,[x.to_json() for x in ld]);check('no_unresolved_interpretation',blocked=={} and ledger['ambiguities']==[] and draft['ambiguities']==[])
records={r['id']:r for category in ['entities','invariants','postconditions','preconditions','safety_properties','liveness_properties','resource_constraints','error_semantics','explicit_non_goals'] for r in draft[category]}
check('exact_original_11_ids',set(records)=={r['id'] for r in metadata['identities']}=={'D1','A1','I1','S1','O1','O2','O3','O4','O5','O6','O7'})
for identity in metadata['identities']:
 k=identity['id'];r=records[k];check('original_identity:'+k,all(r[z]==identity[z] for z in ['id','role','kind','required']))
 for i,ref in enumerate(r['source_refs']):check('exact_citation:'+k+':'+str(i),ref['document_hash']==h(prompt) and ref['document_ref']=='tier2:tier2-source-facets-013:D21' and 0<=ref['start_byte']<ref['end_byte']<=len(prompt))
 check('interpreted_only_lifecycle:'+k,r['lifecycle']['INTERPRETED']['outcome']=='PASS' and all(r['lifecycle'][z]['outcome']==('PENDING' if lifecycle.applicability(r)[z][0] else 'NOT_APPLICABLE') for z in ['FORMALIZED','TYPECHECKED','PROVED','IMPLEMENTED','LINKED','END_TO_END_VERIFIED','TESTED']))
check('only_caller_assumption',ledger['assumptions']==[{'discharged_at':'solve invocation, by supplying the specified typed input with width>0 and start<=end','id':'A1','supplied_by':'caller'}])
functional=[('input',"Input {events:[{group:string,time:int,value:int|null}],start:int,end:int,width:positive int,fill:'none'|'previous'}, start<=end.",{'A1','D1'}),('groups','Groups are all unique event group names sorted lexicographically, including groups with no in-range events.',{'O2'}),('bucket','For each group, emit buckets starting start,start+width,... strictly below end, each covering [bucketStart,min(bucketStart+width,end)).',{'O3'}),('sumcount','Sum only non-null in-range values; count counts these values.',{'O4'}),('nonempty','A nonempty bucket has value=sum and becomes previous value.',{'O5'}),('empty','Empty bucket value is null for fill none, or latest previous nonempty bucket sum for fill previous (null before first); empty buckets never reset previous.',{'O5'}),('prestart','Events before start never seed previous.',{'O5'}),('order','Return [{group,start,count,value}] in group then bucket order.',{'O6'}),('zero_duplicates','Zero sum is a real previous value, duplicates are counted.',{'O4','O5'})]
annotations=[]
for name,text,want in functional:
 start=prompt.find(text.encode());end=start+len(text.encode());rows=[x for x in ledger['clauses'] if x['disposition']=='obligations' and max(start,x['start_byte'])<min(end,x['end_byte'])];refs=set().union(*(set(r['refs']) for r in rows));covered={i for r in rows for i in range(max(start,r['start_byte']),min(end,r['end_byte']))}
 check('functional_clause:'+name,start>=0 and want<=refs and all(i in covered or prompt[i] in b' \t\r\n' for i in range(start,end)),{'refs':sorted(refs),'start':start,'end':end});annotations.append({'facet':name,'text':text,'rows':rows})
check('no_extra_workflow_obligation',set(records)=={r['id'] for r in metadata['identities']} and revision['workflow_context']['text'].encode() not in prompt)
check('source_policy_all_nine',set(policy['obligations'])=={'I1','S1','O1','O2','O3','O4','O5','O6','O7'})
check('functional_statements_complete',all(records[k]['statement'] for k in policy['obligations']) and all(k in {'I1','S1'} or policy['obligations'][k]['value_required'] for k in policy['obligations']))
pkg=Package(PKG);root=pkg.interpretation_root();evidence=[]
for f in (PKG/'evidence').glob('*.json'):
 e=json.loads(f.read_bytes())
 if e['claim_id'] in {'INTERPRETATION:request'}|{'INTERPRETED:'+k+'@1' for k in records}:
  evidence.append(e);capture(f,'package/evidence/'+f.name);raw=PKG/e['raw_result_ref'];check('raw_evidence:'+e['evidence_id'],h(capture(raw,'package/'+e['raw_result_ref']))==e['raw_result_hash']);check('interpretation_evidence_bound:'+e['evidence_id'],e['status']=='PASS' and e['input_root_hash']==root)
check('native_interpretation_ids',len(evidence)==12 and {e['claim_id'] for e in evidence}=={'INTERPRETATION:request'}|{'INTERPRETED:'+k+'@1' for k in records})
for p,sha in observed.items():check('unchanged:'+p,h(Path(p).read_bytes())==sha)
fail=[k for k,v in checks.items() if not v['ok']];audit={'format':'independent-bounded-audit/0.1','phase':'finalized-interpretation','stage':'013','task':'D21','time':datetime.now(timezone.utc).isoformat(),'source_root':protocol['source_root'],'interpretation_root':root,'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not fail else 'AUDIT_ASSERTION_FAILURE','checks':len(checks),'failed_checks':fail,'snapshots':len(snaps),'observations':['All eleven original identities, requiredness and typed roles remain exact.','Every original mathematical clause is accounted for by an obligation clause with the appropriate original IDs.','The only caller assumption is the full public typed domain; supervisor workflow remains separate context.','All nine closed source-policy rows remain retained with O1-O7 functional values required.'],'limits':['Finalized interpretation is a proposal, not a mathematical proof.','No formal proof/source/refinement inspected in this separate phase.','No model/native/kernel/verifier execution or candidate evaluation.']}
(OUT/'scope-annotations.json').write_bytes(d(annotations));(OUT/'checks.json').write_bytes(d(checks));(OUT/'snapshots.json').write_bytes(d(snaps));(OUT/'audit.json').write_bytes(d(audit));print(json.dumps(audit,indent=2));assert not fail,fail
