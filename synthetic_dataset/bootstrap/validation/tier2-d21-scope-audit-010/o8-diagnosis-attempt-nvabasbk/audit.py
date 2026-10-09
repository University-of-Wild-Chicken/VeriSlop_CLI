from pathlib import Path
import sys,json,datetime,os,re,ast
ROOT=Path('/home/augustus/VeriSlop_CLI'); STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-010'; PROJECT=STAGE/'project'; RUN=STAGE/'d21-run'; PKG=RUN/'artifacts/D21/verislop/package'; MAIL=RUN/'artifacts/D21/verislop/mailbox'; OUT=Path(__file__).parent
sys.path.insert(0,str(PROJECT))
from verislop import canonical, source_policy
from synthetic_dataset.tools import bootstrap_tier2 as H
checks=[]; observations={}; snapshots={}
def ck(name,result,detail=None):
 row={'name':name,'pass':bool(result)}
 if detail is not None: row['detail']=detail
 checks.append(row)
 if not result: raise AssertionError(name)
def snap(path,key):
 data=path.read_bytes(); dest=OUT/'snapshots'/key; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
 sha=canonical.digest(data); snapshots[str(dest.relative_to(OUT))]=sha; observations[str(path)]={'sha256':sha,'snapshot':str(dest.relative_to(OUT))}; return data
before=os.environ.get('VERISLOP_CONFIG_HOME')
with H._frozen_provider_context(RUN/'config.json'): protocol=H.verify_inputs(RUN)
ck('frozen_inputs_and_project_verified_without_provider_calls',True)
ck('environment_restored',os.environ.get('VERISLOP_CONFIG_HOME')==before)
for name in ('protocol.json','preregistration.json')+tuple(protocol['input_files']): snap(RUN/name,'cohort/'+name)
for name in ('draft.json','interpretation.json','request/prompt.txt','request/request.json','request/source-policy.json'): snap(PKG/name,'package/'+name)
for name in ('response-0002.json','response-0004.json','request-0002.json','request-0004.json','carrier-0002.json','carrier-0004.json'): snap(MAIL/name,'mailbox/'+name)
codefiles=['synthetic_dataset/tools/bootstrap_tier2.py','docs/bootstrap-tier2-source-facets.md','docs/bootstrap-tier2-data.md','verislop/source_policy.py','verislop/source_contract.py','verislop/formalize.py','verislop/export.py','verislop/accept.py','verislop/draft.py','verislop/lean/SourceBoundary.lean','verislop/backends/vscore3_closure.py','verislop/bridges/import_contract.py','schemas/interpretation.schema.json']
for name in codefiles:
 snap(PROJECT/name,'generic/'+name)
 ck('frozen_generic_hash:'+name,canonical.digest_file(PROJECT/name)==protocol['source_files'][name])
orig=(RUN/'requests/D21/original-prompt.txt').read_bytes(); revised=(RUN/'requests/D21/revised-prompt.txt').read_bytes()
revision=canonical.load_file(RUN/'requests/D21/delivery-revision.json'); meta=canonical.load_file(RUN/'requests/D21/original-metadata.json'); policy=canonical.load_file(RUN/'requests/D21/source-policy.json'); draft=canonical.load_file(PKG/'draft.json'); ledger=canonical.load_file(PKG/'interpretation.json')
records=[r for value in draft.values() if isinstance(value,list) for r in value if isinstance(r,dict) and 'id' in r]
by_id={r['id']:r for r in records}; original_ids={r['id'] for r in meta['identities']}
ck('original_id_count11',len(original_ids)==11)
ck('draft_added_only_O8_and_N1',set(by_id)-original_ids=={'O8','N1'})
ck('original_ids_retained',original_ids<=set(by_id))
for r in meta['identities']: ck('original_identity_preserved:'+r['id'],all(by_id[r['id']][k]==r[k] for k in ('kind','role','required')))
o8=by_id['O8']; ck('O8_new_required_program_postcondition',(o8['role'],o8['kind'],o8['required'])==('guarantee','postcondition',True))
ck('O8_no_dependencies',o8['dependencies']==[])
ck('O8_scope_is_formalization_boundary',o8['scope']==['contract formalization and requested verification boundary'])
ck('O8_absent_original_identities', 'O8' not in original_ids)
ck('O8_absent_frozen_source_policy','O8' not in policy['obligations'])
ck('source_policy_original_guarantee_rows_only',set(policy['obligations'])=={'I1','S1'}|{'O'+str(i) for i in range(1,8)})
base_end=max(s['revised_end_byte'] for s in revision['segments']); ck('software_and_examples_end_at2283',base_end==2283)
clauses=[]
for n,ref in enumerate(o8['source_refs']):
 start,end=ref['start_byte'],ref['end_byte']; raw=revised[start:end]
 ck('O8_ref_only_appended_scaffolding:'+str(n),start>=base_end and 0<=start<end<=len(revised))
 ck('O8_ref_exact_request_hash:'+str(n),ref['document_hash']==canonical.digest(revised))
 clauses.append({**ref,'clause':raw.decode(),'clause_sha256':canonical.digest(raw),'region':'appended_delivery_identity_source-policy_scaffolding'})
ck('O8_source_ref_count15',len(clauses)==15)
workflow_clause=revised[6591:6730].decode()
ck('exact_workflow_clause',workflow_clause=='These constraints will be independently checked against kernel-reconstructed contract facets before proof, after acceptance and at closure.')
ck('O8_cites_workflow_clause',any(r['start_byte']==6591 and r['end_byte']==6730 for r in clauses))
ck('original_has_no_workflow_or_metacontract_language',all(t not in orig for t in (b'kernel-reconstructed',b'contract facets',b'required flags',b'trust boundary')))
ledger_o8=[{**r,'clause':revised[r['start_byte']:r['end_byte']].decode()} for r in ledger['clauses'] if 'O8' in r.get('refs',[])]
ck('O8_ledger_dispositions_all_guarantee_obligations',all(r['disposition']=='obligations' for r in ledger_o8))
reports=[]
for rid in ('0002','0004'):
 resp=canonical.load_file(MAIL/('response-'+rid+'.json')); req=canonical.load_file(MAIL/('request-'+rid+'.json')); carrier=canonical.load_file(MAIL/('carrier-'+rid+'.json')); report=json.loads(resp['text'])
 ck('response_request_hash:'+rid,resp['request_sha256']==canonical.digest_file(MAIL/('request-'+rid+'.json')))
 ck('response_carrier_hash:'+rid,resp['carrier_sha256']==canonical.digest_file(MAIL/('carrier-'+rid+'.json')))
 ck('carrier_exact_request_context:'+rid,carrier['request_sha256']==resp['request_sha256'] and all(carrier[k]==req[k] for k in ('system','user')))
 ck('capability_report_encoding:'+rid,report['encoding']=='verislop.formalizer-capability-gap/0.1')
 ck('capability_reports_only_O8_gap:'+rid,[r['obligation_ids'] for r in report['gaps']]==[['O8']])
 reports.append({'request_id':rid,'report':report,'authority':'Untrusted model report, not proof, impossibility, accepted contract, or source discharge.'})
# Pure negative inspection of the registered request-policy validator. Empty
# reconstructed statements deliberately fail every policy row. This does not
# author any candidate or claim satisfaction of facets.
problems=source_policy.check(policy,{},records)
pure_result=[p.to_json() for p in problems]
ck('policy_checks_exactly_existing_nine_rows',len(pure_result)==9 and {oid for p in pure_result for oid in p['obligations']}==set(policy['obligations']))
ck('policy_does_not_require_added_O8',all('O8' not in p['obligations'] for p in pure_result))
source=(PROJECT/'verislop/lean/SourceBoundary.lean').read_text()
ctor_block=source.split('inductive SourceRequirement where\n',1)[1].split('  deriving DecidableEq',1)[0]
ctors=re.findall(r'^  \| (\w+)',ctor_block,re.M)
ck('closed_source_requirements_have_no_workflow_metadata_ctor',ctors==['entry','typedTotal','deterministic','inputPreserved','noExternalIO','noFloatingPoint','pureData','restrictedRuntimeOnly'])
ledger_src=(PROJECT/'verislop/draft.py').read_text(); ck('registered_ledger_supports_context_notes','if disp == "context":' in ledger_src and 'explanatory context requires a note' in ledger_src)
enforcement=[]
patterns={
'verislop/source_policy.py':['def check(', 'for oid, required in policy["obligations"].items():','def check_package(','def check_ir('],
'verislop/formalize.py':['source_policy.check(required_source_policy, last["analysis"].statements, records)'],
'verislop/accept.py':['source_policy.check_package(pkg, analysis.statements, records)'],
'verislop/export.py':['source_policy.check_ir(pkg, ir, list(expected.values()))','source_policy.check_package(pkg, analysis.statements, records)'],
'verislop/backends/vscore3_closure.py':['if source_policy.context(pkg) is not None:', 'paths[source_policy.PATH] = "frozen-input"','if tcb != _tcb(', 'imported = import_contract(pkg.root)'],
'verislop/bridges/import_contract.py':['replay_meta["source_policy"] = source_reference','export.verified_ir('],
'synthetic_dataset/tools/bootstrap_tier2.py':['if any(actual_identities.get(oid) != value for oid, value in original_identities.items()):','Requested endpoint: Tier 2 / restricted_source','These constraints will be independently','def verify_inputs(']}
for name,needles in patterns.items():
 lines=(PROJECT/name).read_text().splitlines()
 for needle in needles:
  matches=[i for i,line in enumerate(lines,1) if needle in line]
  ck('registered_enforcement_source:'+name+':'+needle,bool(matches))
  for i in matches:
   enforcement.append({'path':name,'line':i,'pattern':needle,'snippet_start':max(1,i-2),'snippet':'\n'.join(lines[max(0,i-3):min(len(lines),i+3)])})
availability={name:(PKG/name).is_file() for name in ['contract/challenge/challenge.json','accepted/accepted-ir.json','implementation/program.vscore.json','bridges/implementation/plan.json','closure/current.json','report.json']}
unchanged={path:canonical.digest_file(Path(path))==rec['sha256'] for path,rec in observations.items()}
for path,same in unchanged.items(): ck('audited_input_unchanged_during_observation:'+path,same)
(OUT/'exact-o8-clause-evidence.json').write_bytes(canonical.dumps({'software_request_and_examples_end_byte':base_end,'O8':{k:v for k,v in o8.items() if k!='lifecycle'},'source_clauses':clauses,'ledger_clauses':ledger_o8}))
(OUT/'capability-report-observations.json').write_bytes(canonical.dumps(reports))
(OUT/'registered-enforcement-evidence.json').write_bytes(canonical.dumps({'closed_source_constructors':ctors,'source_locations':enforcement,'pure_negative_policy_check':pure_result,'check_scope':'No accepted facet satisfaction is tested; empty statements show precisely which policy rows are required by the frozen native validator.'}))
audit={'format':'verislop.independent-readonly-scope-diagnosis/0.1','task':'D21','cohort':str(RUN),'source_root':protocol['source_root'],'protocol_sha256':canonical.digest_file(RUN/'protocol.json'),'request_sha256':canonical.digest(revised),'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks_passed':len(checks),'checks_failed':0,'finding':{'classification':'Concrete request-layer scope misclassification in current interpreted draft','witness':'O8 is a new required postcondition about actual proposed contracts, metadata, verification events and configured trust boundary. All fifteen source references start after byte2509 in appended scaffolding; the revised software specification and public examples finish at byte2283. O8 is absent from the original eleven identities and all nine required source-policy rows. The interpretation ledger nevertheless assigns the scaffolding to O8 as an obligations disposition.','program_scope':'D21 requires grouped bucket aggregation plus exact solve/file/arity and the seven admitted source properties. These remain mandatory in all original policy rows, including complete value formulas and universal refinement for O1-O7.','supervisor_scope':'Preservation of identities/roles/kinds/required flags, exact policy inspection before proof/after acceptance/at closure, assurance-layer exclusions and declared TCB are binding verifier/workflow constraints. They are not an additional aggregation-program postcondition and have no matching constructor in the current closed source requirement model.','capability_limit':'The two current formalizer reports identify only this actual-artifact/workflow binding gap. They do not establish an aggregation expression gap, proof impossibility, accepted contract, or source discharge. This diagnosis does not prove that other D21 formalization/implementation obstacles are absent.','registered_enforcement':'Existing native code checks requested facets on the original policy rows against reconstructed contract statements at formalization, acceptance and export; closure includes exact policy bytes and fresh acceptance/export replay, enforces registered TCB and scoped graph/recipe; harness reconstructs original identity preservation and preregistered surface. No enforcement completion is claimed for this pending task.'},'bounded_corrective_recommendation':'For a future generic specification-first correction, explicitly separate software/domain/source-delivery clauses from supervisor/verification protocol context in the generated request and interpretation interface. Keep all original IDs, roles, requiredness, domain, source-policy rows/properties and full functional value/universal refinement requirements unchanged. Retain workflow clauses as mandatory authenticated host-policy checks and trust/report constraints, with ledger context/protocol coverage rather than a new program guarantee. Do not silently remove actual user program requirements, replace O8 by True/reflexivity, broaden the trust claim, hand-edit this live draft or regrade the run. Qualify the generic separation under a fresh source freeze and engineering gate, then use a fresh model run.','artifact_availability_observation':availability,'scope_limit':'Read-only diagnosis of public request, current interpretation, two explicit model capability reports, and registered generic enforcement sources. No accepted contract, source program, bridge, native execution, closure or terminal verification claimed.','restrictions_observed':['No production/project/cohort/package mutation','No native/kernel/closure/gate/model/provider calls','No author/critic/reviewer/controller advice or communication','No hidden cases/oracles/old task candidates or proofs read'],'observed_files':observations,'snapshot_root':canonical.digest_json(snapshots),'authority':'Independent trusted NL correspondence and exact byte/source classification audit only; this receipt is outside cohort and adds no lifecycle or accepted-IR authority.'}
(OUT/'checks.json').write_bytes(canonical.dumps(checks)); (OUT/'snapshot-manifest.json').write_bytes(canonical.dumps({'files':snapshots,'files_root':canonical.digest_json(snapshots)})); (OUT/'audit.json').write_bytes(canonical.dumps(audit))
print(json.dumps({'receipt':str(OUT/'audit.json'),'sha256':canonical.digest_file(OUT/'audit.json'),'checks':len(checks),'snapshots':len(snapshots),'availability':availability},sort_keys=True))
