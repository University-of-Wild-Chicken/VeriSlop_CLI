#!/usr/bin/env python3
"""Read-only Stage012 canonical interpretation audit; no formal/kernel/model calls."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-012'
RUN,PROJECT=STAGE/'run',STAGE/'project'
PKG=RUN/'artifacts/D21/verislop/package'
OUT=Path(__file__).resolve().parent
INITIAL=ROOT/'synthetic_dataset/bootstrap/validation/tier2-d21-scope-audit-012/initial-attempt-js9l3ce9'
EXPECTED_SOURCE='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710'
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def dumps(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def now():return datetime.now(timezone.utc).isoformat()
checks,snapshots,observed={},{},{}
started=now()
def check(name,ok,detail=None):
 checks[name]={'ok':bool(ok)}
 if detail is not None:checks[name]['detail']=detail
 return bool(ok)
def capture(path,label):
 path=Path(path);check('regular:'+label,path.is_file() and not path.is_symlink())
 data=path.read_bytes();target=OUT/'snapshots'/label;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 snapshots[label]={'source':str(path),'sha256':digest(data),'size':len(data)};observed[str(path)]=digest(data)
 return data
def capture_json(path,label):return json.loads(capture(path,label))
protocol=capture_json(RUN/'protocol.json','request/protocol.json')
prereg=capture_json(RUN/'preregistration.json','request/preregistration.json')
check('frozen_source_identity',protocol['source_root']==prereg['source_root']==EXPECTED_SOURCE and digest(dumps(protocol['source_files']))==EXPECTED_SOURCE)
check('prereg_protocol_identity',prereg['protocol_sha256']==digest((RUN/'protocol.json').read_bytes()))
for name,sha in protocol['source_files'].items():
 check('frozen_source:'+name,digest(capture(PROJECT/name,'frozen-project/'+name))==sha)
for name,sha in protocol['input_files'].items():
 # All prepared input bytes remain authenticated; no task response or prior proof is opened.
 check('prepared_input:'+name,digest(capture(RUN/name,'prepared/'+name))==sha)
initial=capture_json(INITIAL/'audit.json','prior-initial-receipt/audit.json')
initial_seal=capture_json(INITIAL/'RECEIPT-MANIFEST.json','prior-initial-receipt/RECEIPT-MANIFEST.json')
check('prior_initial_receipt_identity',digest((INITIAL/'audit.json').read_bytes())=='sha256:6ae58e7dc7ef4560f8d5d7aae4d48f0e253e01c86a38e7870fa10ce70eb13fd4' and initial['bounds']['source_root']==EXPECTED_SOURCE)
check('prior_initial_receipt_seal_binding',initial_seal['files']['audit.json']==digest((INITIAL/'audit.json').read_bytes()) and initial_seal['files_root']==digest(dumps(initial_seal['files'])))
metadata=json.loads((RUN/'requests/D21/original-metadata.json').read_bytes())
policy=json.loads((RUN/'requests/D21/source-policy.json').read_bytes())
revision=json.loads((RUN/'requests/D21/delivery-revision.json').read_bytes())
original=(RUN/'requests/D21/original-prompt.txt').read_bytes()
revised=(RUN/'requests/D21/revised-prompt.txt').read_bytes()
ledger=capture_json(PKG/'interpretation.json','package/interpretation.json')
draft=capture_json(PKG/'draft.json','package/draft.json')
request=capture_json(PKG/'request/request.json','package/request/request.json')
staged_prompt=capture(PKG/'request/prompt.txt','package/request/prompt.txt')
staged_policy=capture(PKG/'request/source-policy.json','package/request/source-policy.json')
capture(PKG/'request/routing.json','package/request/routing.json')
check('exact_request_staging',staged_prompt==revised and staged_policy==(RUN/'requests/D21/source-policy.json').read_bytes())
ref='tier2:tier2-source-facets-012:D21'
check('staged_request_document_binding',request['request_ref']==ref and request['document_hash']==digest(revised) and request['byte_length']==len(revised) and request['attachments']==[])
check('ledger_request_binding',ledger['request']=={'byte_length':len(revised),'document_hash':digest(revised),'document_ref':ref})
check('draft_request_ref',draft['request_ref']==ref)

# Frozen pure schema/provenance/clause validators only; never interpret.run or a verifier invocation.
sys.path.insert(0,str(PROJECT))
from verislop import draft as draftmod,fsutil
check('pure_validator_frozen',Path(draftmod.__file__).resolve()==PROJECT/'verislop/draft.py')
records=draftmod.obligations(draft);byid={row['id']:row for row in records}
identities={row['id']:row for row in metadata['identities']}
check('exact_11_original_obligations',len(records)==len(byid)==len(identities)==11 and set(byid)==set(identities))
for id,row in byid.items():
 check('identity_role_kind_required:'+id,{k:row[k] for k in ('id','role','kind','required')}=={k:identities[id][k] for k in ('id','role','kind','required')})
 check('revision_one:'+id,row['revision']==1)
 check('interpretation_only_state:'+id,row['state']=='INTERPRETED' and row['lifecycle']['INTERPRETED']['outcome']=='PASS' and all(v['outcome'] in ('PENDING','NOT_APPLICABLE') for k,v in row['lifecycle'].items() if k!='INTERPRETED'))
ddiags=draftmod.validate_draft(draft,revised,ref)
ldiags,coverage=draftmod.validate_ledger(ledger,draft,revised,ref)
blocked=draftmod.blocked_obligations(draft,ledger)
check('pure_draft_validator_no_diagnostics',not ddiags,[x.to_json() for x in ddiags])
check('pure_ledger_validator_no_diagnostics',not ldiags,[x.to_json() for x in ldiags])
check('complete_mechanical_clause_coverage',coverage['uncovered_segments']==[])
check('no_unresolved_ambiguity_or_default',blocked=={} and ledger['ambiguities']==[] and ledger['selected_defaults']==[] and draft['ambiguities']==[])
check('only_stated_caller_assumption',len(ledger['assumptions'])==1 and ledger['assumptions'][0]['id']=='A1' and ledger['assumptions'][0]['supplied_by']=='caller' and byid['A1']['role']=='assumption')
check('no_added_domain_bounds','No further input bounds or preconditions apply.' in byid['A1']['statement'] and byid['A1']['acceptance_criteria']==['width>0 and start<=end; all fields have the stated domains; no additional restrictions.'] and not draft['resource_constraints'])
check('no_program_workflow_obligation',set(byid)==set(identities) and not any(token in row['statement'].lower() for row in records for token in ('supervisor','registry maintenance','contract inspection','independently checked against kernel','workflow context','stagedchecks')))
check('no_self_added_nonvacuity',not any(x['kind']=='non_vacuity' for x in records))

source_properties=policy['obligations']['O1']['properties']
for id in [f'O{i}' for i in range(1,8)]:
 row=byid[id];text=row['statement']+' '+' '.join(row['acceptance_criteria'])
 check('full_domain_universal_intent:'+id,'universal' in text.lower() and ('every input' in text.lower() or 'every specified input' in text.lower() or 'entire stated domain' in text.lower()))
 check('canonical_entry_intent:'+id,'program.vscore.json' in text and 'solve' in text and 'arity 1' in text)
 # O1 uses equivalent prose names in its statement; other value rows spell all seven closed tags.
 if id!='O1':check('all_seven_source_properties_intent:'+id,all(p in text for p in source_properties))
check('O1_all_seven_properties_prose',all(x in byid['O1']['statement'] for x in ['typed total','deterministic','input preserving','free of external I/O and floating point','pure data','restricted-runtime-only']))
check('source_only_classification_retained',all('explicitly source-only' in byid[id]['statement'] for id in ('I1','S1')) and revision['source_policy_classification']=={'source_only_operational_ids':['I1','S1'],'value_required_default':True})
check('sourceonly_preserves_functional_causal_clauses','fully specified as required functional guarantees O4 and O5' in byid['I1']['statement'])

# Phrase anchors document human semantic inspection; these are not a semantic decision procedure.
anchors={
 'D1':['Unicode-scalar string','mathematical integer time','nullable mathematical integer value','scalar-codepoint lexicographically sorted distinct group names occurring anywhere in events','start+k*width for natural k with start+k*width<end','multiset of event occurrences','non-null value and b<=time<min(b+width,end)'],
 'O2':['every distinct event group appears once','Unicode scalar-codepoint lexicographic order','including groups whose events are all outside the requested interval or have null values'],
 'O3':['exactly one bucket for each b in B','[b,min(b+width,end))','There are no other buckets; when start=end there are none'],
 'O4':['count=n(g,b)','sum=s(g,b)','exact unbounded mathematical integers','Only non-null values','every duplicate occurrence contributes separately'],
 'O5':['if n(g,b)>0 the returned value is s(g,b)','n(g,b)=0 and fill=none the value is null','n(g,b)=0 and fill=previous','greatest earlier b\' in B with n(g,b\')>0','null if no such b\' exists','independent per group','starts absent','updated only by nonempty buckets','never reset by empty buckets','zero sums as present values','never receives values from events before start'],
 'O6':['exactly the list of records {group:g,start:b,count:n(g,b),value:v(g,b)}','where v follows O5','enumerating g through G and b through B in that order','exact specified JSON field structure and list ordering'],
 'O7':['complete universal aggregation formula for every specified input','(a,0,2,0),(a,2,0,0),(a,4,0,0)','(z,0,0,null)','Examples do not replace universal refinement'],
 'A1':['width a positive integer','start<=end','fill equal to none or previous','No further input bounds or preconditions apply.']}
for id,phrases in anchors.items():
 for index,phrase in enumerate(phrases):check('semantic_anchor:'+id+':'+str(index),phrase in byid[id]['statement'],phrase)
check('empty_inputs_retained','no events or start=end yields an empty result.' in ' '.join(byid['O6']['acceptance_criteria']))
check('nonnull_count_defines_nonempty','Nonempty means positive count of non-null contributing occurrences, including buckets whose sum is zero.' in byid['O5']['acceptance_criteria'])

source_quotes={}
for row in records:
 quotes=[]
 for index,src in enumerate(row['source_refs']):
  data=revised[src['start_byte']:src['end_byte']]
  check('citation_hash_and_span:'+row['id']+':'+str(index),src['document_ref']==ref and src['document_hash']==digest(revised) and len(data)>0)
  quotes.append({'start_byte':src['start_byte'],'end_byte':src['end_byte'],'quote':data.decode(),'interpretation':src['interpretation']})
 source_quotes[row['id']]=quotes
# The entire preserved functional paragraph is disposed as program obligations, never context/exclusion.
for clause in ledger['clauses']:
 if 265<=clause['start_byte'] and clause['end_byte']<=1078:
  check('functional_clause_disposition:'+str(clause['start_byte']),clause['disposition']=='obligations' and len(clause['refs'])>0)

manifest_entries={name:OUT/'snapshots/package'/name for name in ['request/prompt.txt','draft.json','interpretation.json','request/source-policy.json']}
interpretation_manifest=fsutil.manifest_for(manifest_entries)
interpretation_root=fsutil.manifest_root(interpretation_manifest)
evidence={}
for file in sorted((PKG/'evidence').glob('*.json')):
 data=json.loads(file.read_bytes())
 if data['claim_id']!='INTERPRETATION:request' and not data['claim_id'].startswith('INTERPRETED:'):continue
 ev=capture_json(file,'package/evidence/'+file.name)
 raw=capture_json(PKG/ev['raw_result_ref'],'package/'+ev['raw_result_ref'])
 check('evidence_raw_hash:'+ev['claim_id'],digest((PKG/ev['raw_result_ref']).read_bytes())==ev['raw_result_hash'])
 check('evidence_same_interpretation_root:'+ev['claim_id'],ev['input_root_hash']==interpretation_root)
 check('evidence_recorder_identity:'+ev['claim_id'],ev['verifier_id']=='verislop.interpretation-recorder' and ev['status']=='PASS' and ev['exit_code']==0 and ev['invocation']==['verislop','interpret'])
 check('raw_claim_identity:'+ev['claim_id'],raw['claim_id']==ev['claim_id'] and raw['milestone_outcome']=='PASS')
 if ev['claim_id']=='INTERPRETATION:request':
  check('native_coverage_matches_pure',raw['coverage']==coverage and raw['diagnostics']==[] and raw['blocked_guarantees']=={})
 else:
  id=ev['claim_id'].split(':')[1].split('@')[0]
  check('native_record_digest:'+id,raw['record_digest']==digest(dumps(byid[id])) and raw['blocked_by']==[])
 evidence[ev['claim_id']]={'evidence_id':ev['evidence_id'],'file':file.name,'raw_sha256':ev['raw_result_hash'],'status':ev['status'],'scope':ev['scope']}
check('complete_exact_native_interpretation_claims',set(evidence)=={'INTERPRETATION:request',*[f'INTERPRETED:{id}@1' for id in identities]})
for path,sha in observed.items():check('snapshot_stable:'+str(Path(path).relative_to(ROOT)),digest(Path(path).read_bytes())==sha)

pending={name:(PKG/relative).exists() for name,relative in {'frozen_challenge':'contract/challenge/challenge.json','accepted_ir':'accepted/accepted-ir.json','implementation':'bridges/implementation','mechanical_pointer':'closure/current.json'}.items()}
failures=[{'check':k,**v} for k,v in checks.items() if not v['ok']]
semantic_findings=[
 {'facet':'domain','assessment':'A1 requires only typed fields, positive width, start<=end and the two specified fill modes; no event/list/integer/Unicode bounds introduced.'},
 {'facet':'groups','assessment':'D1 and O2 sort distinct group names from all events by Unicode scalar-codepoint order, including exclusively out-of-range or null events.'},
 {'facet':'buckets','assessment':'D1 and O3 enumerate all natural k with start+k*width<end, clip the half-open upper boundary at end, and emit no buckets for start=end.'},
 {'facet':'aggregation','assessment':'D1 and O4 retain occurrence multiplicity, ignore null values in both count and sum, and use exact unbounded integer sums.'},
 {'facet':'causal_fill','assessment':'O5 selects only the greatest strictly earlier nonempty bucket in the same group, initializes absent state, never resets on emptiness, treats zero as present and excludes pre-start seeding.'},
 {'facet':'output','assessment':'O6 requires exact group-major/bucket-increasing list equality with all specified fields; empty group enumeration or empty interval yields no rows.'},
 {'facet':'examples','assessment':'O7 retains both original exact result lists and additionally requires full universal aggregation; examples are not substituted for functional correctness.'},
 {'facet':'source','assessment':'All nine required source-policy identities remain canonical program.vscore.json solve/arity1 with all seven closed properties. O1-O7 retain universal value requirements; only I1/S1 are source-only.'},
 {'facet':'workflow','assessment':'No additional program obligation about supervisor metadata, registry inspection, trust configuration or staged verification was injected. All eleven IDs match original metadata.'}]
report={'format':'verislop.independent-stage012-interpreted-scope-audit/0.1','started_at_utc':started,'finished_at_utc':now(),'auditor':'/root/tier2_semantics_audit','phase':'canonical_interpretation_only','source_root':EXPECTED_SOURCE,'interpretation_root':interpretation_root,'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failures else 'AUDIT_CHECK_FAILURE','checks_total':len(checks),'failed_checks':failures,'snapshots_count':len(snapshots),'original_ids':sorted(identities),'source_policy_rows':9,'semantic_findings':semantic_findings,'native_interpretation_evidence':evidence,'artifact_availability_only':pending,'limitations':['Interpretation is a recorded semantic assumption, not mathematical proof.','Frozen/accepted formal expressions, kernels, source implementations, bridge refinements and closure outcomes were not inspected or executed in this phase.','Pure schema/provenance/ledger coverage validation establishes structural coverage only; natural-language semantic correspondence is the auditor\'s bounded inspection.','No task author/critic/reviewer/controller contact, model request, native driver, Lean/kernel, closure verifier, task program or hidden case/oracle invocation occurred.','Only fresh Stage012 task artifacts and previously sealed initial Stage012 metadata were read; no earlier task candidate or proof was reopened.','No source, cohort or package file was edited; snapshots are outside the live cohort.']}
for name,obj in [('checks.json',checks),('snapshot-manifest.json',snapshots),('semantic-findings.json',semantic_findings),('citation-quotes.json',source_quotes),('pure-coverage.json',coverage),('interpretation-input-manifest.json',interpretation_manifest),('audit.json',report)]:
 (OUT/name).write_bytes(dumps(obj)+b'\n')
print(json.dumps({'audit':str(OUT/'audit.json'),'audit_sha256':digest((OUT/'audit.json').read_bytes()),'checks':len(checks),'failures':failures,'snapshots':len(snapshots),'interpretation_root':interpretation_root,'pending_artifacts':pending},sort_keys=True))
