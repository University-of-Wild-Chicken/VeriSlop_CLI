from pathlib import Path
import sys,os,json,datetime
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-011';PROJECT=STAGE/'project';RUN=STAGE/'run';PKG=RUN/'artifacts/D21/verislop/package';MAIL=RUN/'artifacts/D21/verislop/mailbox';OUT=Path(__file__).parent
sys.path.insert(0,str(PROJECT))
from synthetic_dataset.tools import bootstrap_tier2 as H
from verislop import canonical,draft,agents
checks=[];observed={};snaps={}
def ck(name,val,detail=None):
 row={'name':name,'pass':bool(val)}
 if detail is not None:row['detail']=detail
 checks.append(row)
 if not val:raise AssertionError(name)
def snap(path,name):
 raw=path.read_bytes();t=OUT/'snapshots'/name;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(raw);sha=canonical.digest(raw);observed[str(path)]={'sha256':sha,'snapshot':str(t.relative_to(OUT))};snaps[str(t.relative_to(OUT))]=sha;return raw
before=os.environ.get('VERISLOP_CONFIG_HOME')
with H._frozen_provider_context(RUN/'config.json'):protocol=H.verify_inputs(RUN)
ck('frozen_inputs_project_retained_source_and_configuration_pass_pure_validation',True);ck('provider_context_restored',os.environ.get('VERISLOP_CONFIG_HOME')==before)
ck('frozen_source_root229',protocol['source_root']=='sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a' and len(protocol['source_files'])==229)
for name in ('protocol.json','preregistration.json')+tuple(protocol['input_files']):snap(RUN/name,'cohort/'+name)
for name in ['draft.json','interpretation.json','request/prompt.txt','request/request.json','request/source-policy.json']:snap(PKG/name,'package/'+name)
for name in ['synthetic_dataset/tools/bootstrap_tier2.py','verislop/draft.py','verislop/agents.py','verislop/source_policy.py','docs/bootstrap-tier2-interpretation-scope.md']:snap(PROJECT/name,'generic/'+name)
public=snap(ROOT/'synthetic_dataset/tasks/D21/prompt.txt','public/D21/prompt.txt');orig=(RUN/'requests/D21/original-prompt.txt').read_bytes();prompt=(RUN/'requests/D21/revised-prompt.txt').read_bytes();meta=canonical.load_file(RUN/'requests/D21/original-metadata.json');revision=canonical.load_file(RUN/'requests/D21/delivery-revision.json');policy=canonical.load_file(RUN/'requests/D21/source-policy.json');d=canonical.load_file(PKG/'draft.json');ledger=canonical.load_file(PKG/'interpretation.json');ref=protocol['tasks'][0]['revised_request_ref']
ck('original_public_scope_exact',public==orig);ck('new_exact_native_prompt',prompt==(PKG/'request/prompt.txt').read_bytes());ck('new_request_policy_exact',(PKG/'request/source-policy.json').read_bytes()==canonical.dumps(policy));new,sidecar=H.revise_prompt(orig,meta['identities'],operational_ids=('I1','S1'));ck('revision_workflow_exact_reconstruction',new==prompt and sidecar==revision)
context=revision['workflow_context'];cb=context['text'].encode('utf-8');ck('context_utf8_length_hash_binding',context['encoding']=='utf-8' and len(cb)==context['byte_length'] and canonical.digest(cb)==context['sha256'] and cb not in prompt);ck('canonical_preregistered_revision_hash',protocol['input_files']['requests/D21/delivery-revision.json']==canonical.digest_json(revision) and (RUN/'requests/D21/delivery-revision.json').read_bytes()==canonical.dumps(revision))
records=draft.obligations(d);by_id={r['id']:r for r in records};identity={r['id']:r for r in meta['identities']};ck('exact_original11_no_added_guarantees',len(records)==len(by_id)==len(identity)==11 and set(by_id)==set(identity))
for oid,row in identity.items():ck('identity_role_kind_required_retained:'+oid,all(by_id[oid][k]==row[k] for k in ('role','kind','required')) and by_id[oid]['revision']==1)
vd=draft.validate_draft(d,prompt,ref);vl,coverage=draft.validate_ledger(ledger,d,prompt,ref);ck('registered_draft_provenance_schema_dependency_validation',not vd,[x.to_json() for x in vd]);ck('registered_ledger_coverage_validation',not vl and coverage['uncovered_segments']==[],[x.to_json() for x in vl]);ck('ledger_no_new_assumption_suppliers',ledger['assumptions']==[{'discharged_at':'solve invocation through the specified typed input with width>0 and start<=end','id':'A1','supplied_by':'caller'}]);ck('no_ambiguity_or_selected_default_domain_changes',ledger['ambiguities']==[] and ledger['selected_defaults']==[] and d['ambiguities']==[])
source_evidence=[]
for rec in records:
 for n,s in enumerate(rec['source_refs']):
  start,end=s['start_byte'],s['end_byte'];raw=prompt[start:end]
  ck('exact_record_source_reference:'+rec['id']+':'+str(n),s['document_hash']==canonical.digest(prompt) and s['document_ref']==ref and 0<=start<end<=len(prompt))
  source_evidence.append({'obligation':rec['id'],**s,'quote':raw.decode(),'quote_sha256':canonical.digest(raw)})
for n,c in enumerate(ledger['clauses']):
 ck('ledger_clause_valid:'+str(n),0<=c['start_byte']<c['end_byte']<=len(prompt) and set(c['refs'])<=set(by_id))
 if c['disposition']=='context':ck('context_requires_note_no_guarantee:'+str(n),bool(c.get('note')) and c['refs']==[])
critical={(265,393):{'D1','A1'},(394,501):{'O2'},(502,561):{'O3'},(562,637):{'O3'},(638,672):{'O4'},(673,699):{'O4'},(700,759):{'O5'},(760,879):{'O5'},(880,915):{'O5'},(916,956):{'O5'},(957,1019):{'D1','O6'},(1020,1078):{'O4','O5'},(1435,1506):{'D1','O4'},(1507,1596):{'D1','O2'},(1597,1687):{'A1','O1'},(1735,2282):{'O7'},(2649,2760):{'O1','O2','O3','O4','O5','O6','O7'},(5459,5654):{'O1','O2','O3','O4','O5','O6','O7'},(5957,8118):set(policy['obligations'])}
coverage_evidence=[]
for span,needed in critical.items():
 match=[c for c in ledger['clauses'] if (c['start_byte'],c['end_byte'])==span]
 ck('functional_clause_not_hidden_as_context:'+str(span),len(match)==1 and match[0]['disposition']=='obligations' and needed<=set(match[0]['refs']))
 coverage_evidence.append({'span':list(span),'quote':prompt[span[0]:span[1]].decode(),'required_refs':sorted(needed),'actual_ledger':match[0]})
ck('A1_only_stated_guards',by_id['A1']['statement']=='The caller supplies an input in D1 with width > 0 and start <= end. No further bounds or preconditions apply.')
ck('A1_unbounded_empty_duplicate_both_fill_domain','arbitrary integer times and values, empty events, duplicate events, either fill mode and arbitrary Unicode scalar strings' in ' '.join(by_id['A1']['acceptance_criteria']))
terms={
'D1':['unbounded mathematical integers','sequences of Unicode scalar values','value:int|null','count:natural'],
'O1':['exactly one admitted typed entry solve of arity 1','every input satisfying A1','complete grouped bucket aggregation'],
'O2':['distinct group names occurring anywhere in events','sorted lexicographically by Unicode scalar codepoints','including names whose events all lie outside [start,end)'],
'O3':['b_k = start + k*width','natural k satisfying b_k < end','[b_k,min(b_k+width,end))','When start=end there are no buckets.'],
'O4':['multiset of event occurrences','e.group=g','b<=e.time<min(b+width,end)','e.value non-null','count=|M(g,b)|','empty sum zero','Each duplicate occurrence contributes separately','null and out-of-range values contribute neither count nor sum'],
'O5':['For each group independently','previous initially null','If count>0','set previous to that sum, including zero','If count=0','fill=\'none\'','fill=\'previous\'','latest earlier bucket of this same group having count>0','or null if none exists','Empty buckets preserve previous','events before start cannot seed it'],
'O6':['return exactly the list','for every group in O2 and every bucket in O3, using O4 and O5','ordered first by scalar-codepoint lexicographic group order and then increasing bucket start','No extra or missing records occur','no groups or no buckets yields an empty list','exact typed JSON input/output structure'],
'O7':['both original public example outputs exactly','complete universal specification, rather than only those examples']}
for oid,phrases in terms.items():
 for phrase in phrases:ck('interpreted_complete_scope:'+oid+':'+phrase,phrase in by_id[oid]['statement'])
props=['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only'];guarantees={'I1','S1'}|{'O'+str(i) for i in range(1,8)};ck('policy_exact_nine_original_guarantees',set(policy['obligations'])==guarantees)
for oid,row in policy['obligations'].items():
 ck('same_closed_source_policy:'+oid,row=={'file':'program.vscore.json','entry':'solve','arity':1,'properties':props,'value_required':oid not in {'I1','S1'}})
 text=by_id[oid]['statement']+' '+' '.join(by_id[oid]['acceptance_criteria'])
 ck('interpreted_source_file_solve_arity_scope:'+oid,'program.vscore.json' in text and 'solve' in text and ('arity 1' in text or 'arity-1' in text))
 if oid!='S1':ck('interpreted_all_seven_source_properties:'+oid,all(p in text for p in props))
 else:ck('S1_exact_restricted_runtime_property_text_and_criteria','executes only within the admitted restricted runtime' in text and 'including restricted_runtime_only' in text and all(p in text for p in props[:-1]))
 if oid not in {'I1','S1'}:ck('functional_value_universal_source_refinement:'+oid,any(word in text for word in ['universally','Universal implementation refinement','complete universal specification']))
ck('I1_causal_values_not_suppressed','functional behavior remains required in O4 and O5' in by_id['I1']['statement']);ck('I1_S1_only_sourceonly',['I1','S1']==revision['source_policy_classification']['source_only_operational_ids'])
ck('no_metacontract_program_requirement',all(not any(t in r['statement'] for t in ['kernel-reconstructed contract','staged checking','required flags','trust configuration','trusted boundary','contract registry']) for r in records))
ck('O6_proof_dependencies_preserve_all_functional_components',{r['id'] for r in by_id['O6']['dependencies'] if r['relation']=='uses_proof'}=={'O2','O3','O4','O5'});ck('O7_derives_complete_output',{'id':'O6','relation':'uses_proof'} in by_id['O7']['dependencies'])
# Current fresh interpreter envelope bound to exact current request/carrier;
# origin is observed metadata, not an attestation of provider/model identity.
origin=None
paths=[MAIL/('response-0001.json'),MAIL/('request-0001.json'),MAIL/('carrier-0001.json')]
if all(p.is_file() for p in paths):
 for path in paths:snap(path,'mailbox/'+path.name)
 response,request,carrier=[canonical.load_file(p) for p in paths]
 ck('fresh_response_exact_request_hash',response['request_sha256']==canonical.digest_file(paths[1]));ck('fresh_response_exact_carrier_hash',response['carrier_sha256']==canonical.digest_file(paths[2]));ck('fresh_carrier_exact_request_fields',all(carrier[k]==request[k] for k in ['system','user']) and carrier['request_sha256']==response['request_sha256']);ck('fresh_interpreter_source_root_and_request_set',response['source_root']==protocol['source_root'] and response['request_set_root']==protocol['request_set_root']);ck('fresh_role_stateless_no_identity_invention',response['fork_turns']=='none' and response['model_identity_attested'] is False)
 origin={'request_id':response['request_id'],'agent_task_id':response['agent_task_id'],'request_sha256':response['request_sha256'],'carrier_sha256':response['carrier_sha256'],'model_identity_attested':False}
availability={name:(PKG/name).is_file() for name in ['contract/challenge/challenge.json','accepted/accepted-ir.json','implementation/program.vscore.json','bridges/implementation/plan.json','closure/current.json','report.json']}
for path,row in observed.items():ck('observed_byte_hash_stable:'+path,canonical.digest_file(Path(path))==row['sha256'])
(OUT/'exact-obligation-source-quotes.json').write_bytes(canonical.dumps(source_evidence));(OUT/'functional-clause-coverage.json').write_bytes(canonical.dumps(coverage_evidence));(OUT/'registered-pure-validation.json').write_bytes(canonical.dumps({'draft_diagnostics':[x.to_json() for x in vd],'ledger_diagnostics':[x.to_json() for x in vl],'coverage':coverage,'note':'Schema/provenance/dependency/coverage validation only; no Lean or source-safety proof.'}))
audit={'format':'verislop.independent-readonly-scope-audit/0.1','task':'D21','stage':'tier2-source-facets-011','phase':'recorded_interpretation_only','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cohort':str(RUN),'frozen_project':str(PROJECT),'source_root':protocol['source_root'],'protocol_sha256':canonical.digest_file(RUN/'protocol.json'),'request_sha256':canonical.digest(prompt),'draft_sha256':canonical.digest_file(PKG/'draft.json'),'ledger_sha256':canonical.digest_file(PKG/'interpretation.json'),'conclusion':'No concrete interpreted-scope weakening or supervisor-program guarantee found in the current fresh recorded interpretation. Complete original identities/domain/functional branches/examples and exact source-policy scope are retained. This is not an accepted Lean mathematical model or implementation verification.','checks_passed':len(checks),'checks_failed':0,'required_identity_count':len(identity),'interpreted_identity_count':len(records),'source_policy_rows':9,'value_required_ids':['O'+str(i) for i in range(1,8)],'source_only_ids':['I1','S1'],'manual_correspondence_findings':['A1 adds no event/group/bucket/string/integer magnitude bounds; it explicitly permits empty/duplicate events, arbitrary signed integer times and values, either fill mode and Unicode scalar names.','O2 derives sorted unique groups from every event, including outside-range groups. O3 gives all start+k*width<end half-open clipped buckets and empty interval behavior.','O4 uses occurrence multiplicity, null exclusion, matching group and clipped in-range membership, exact sums and counts. O5 updates per-group previous only for count>0, including zero, preserves it through empties, and excludes pre-start seeding; both fill branches and before-first null are explicit.','O6 mandates the exact full group-then-bucket record list with no extra/missing records. O7 retains both public examples without restricting universal scope.','All9 source policy guarantees retain exact solve/file/arity and seven required properties. I1/S1 alone are source-only, and causal invariant value behavior remains under O4/O5.','Exactly original11 IDs were interpreted, with original roles/kinds/required flags and no added workflow guarantee. Revision identity/provenance/context paragraphs receive ledger explanatory notes; program facets and complete universal value requirements stay obligations.','Workflow_context stays separately canonical/hash-preregistered and makes no assertion of its own discharge. Registered validators have not been relaxed.'], 'interpreter_origin_observation':origin,'artifact_availability_observation':availability,'pending':['Frozen Lean function/domain/source contracts and full universal formulas; constructive nonvacuity and dependency/axiom scope','Accepted certificate and AST IR equality/provenance','Admitted actual source, universal refinement, typed/raw coverage, inverse laws and operational adequacy','Per-ID full graph, task clean builds, release/reviews, terminal/report/seals'],'trust':['Natural-language correspondence in scope inspection','Controller original identity provenance and exact copy mechanism','Host Python/hash/schema/provenance tooling'],'restrictions_observed':['No native/kernel/closure/gate/provider/model calls','No author/critic/reviewer/controller contact or supplemental guidance','No frozen/live source/project/cohort/package mutation','No historical task candidates/proofs, hidden cases or oracles read'],'observed_files':observed,'snapshot_root':canonical.digest_json(snaps),'authority':'External read-only interpreted-phase audit; no lifecycle or accepted-IR/proof authority is added.'}
(OUT/'checks.json').write_bytes(canonical.dumps(checks));(OUT/'snapshot-manifest.json').write_bytes(canonical.dumps({'files':snaps,'files_root':canonical.digest_json(snaps)}));(OUT/'audit.json').write_bytes(canonical.dumps(audit))
print(json.dumps({'receipt':str(OUT/'audit.json'),'sha256':canonical.digest_file(OUT/'audit.json'),'checks':len(checks),'snapshots':len(snaps),'availability':availability},sort_keys=True))
