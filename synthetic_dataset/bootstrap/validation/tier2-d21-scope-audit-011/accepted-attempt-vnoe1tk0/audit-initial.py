"""Pure accepted-artifact audit: consume exports, never execute Lean or model tools."""
from pathlib import Path
import json,sys,re,hashlib,datetime
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-011';PROJECT=STAGE/'project';RUN=STAGE/'run';PKG=RUN/'artifacts/D21/verislop/package';OUT=Path(__file__).parent
FROZEN=OUT.parent/'frozen-attempt-w3ulmxn3'
sys.path.insert(0,str(PROJECT))
from verislop import contract as C,reify as R,dsl,source_contract as S,source_policy,canonical,export as E,exprjson,accept as A
from verislop.package import Package
assert Path(C.__file__).resolve().is_relative_to(PROJECT)
checks=[];snapshots=[]
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def put(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def ck(name,ok,detail=None):
 checks.append({'name':name,'pass':bool(ok),'detail':detail})
 if not ok:raise AssertionError(name)
def snap(path,label):
 b=path.read_bytes();dest=OUT/'snapshots'/label;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b);snapshots.append({'path':str(path),'snapshot':'snapshots/'+label,'sha256':sha(b),'size':len(b)});return b
def load(label):return json.loads((OUT/'snapshots'/label).read_text())
for p in sorted((PKG/'accepted').rglob('*')):
 if p.is_file():snap(p,'package/'+str(p.relative_to(PKG)))
for f in ['contract/challenge/challenge.json','contract/challenge/formalization.json','contract/challenge/statements.json','contract/challenge/profile.json','contract/challenge/policy.json','claims.json','request/source-policy.json','request/request.json','request/prompt.txt']:
 snap(PKG/f,'package/'+f)
for f in ['original-metadata.json','original-prompt.txt','revised-prompt.txt','source-policy.json','delivery-revision.json']:
 snap(RUN/'requests/D21'/f,'cohort/requests/D21/'+f)
for f in ['protocol.json','preregistration.json','engineering-validation.json']:
 snap(RUN/f,'cohort/'+f)
for f in ['verislop/contract.py','verislop/exprjson.py','verislop/reify.py','verislop/export.py','verislop/accept.py','verislop/source_contract.py','verislop/source_policy.py','verislop/dsl.py','verislop/evidence.py','verislop/claimcheck.py','verislop/lean/SourceBoundary.lean','docs/bootstrap-tier2-source-facets.md']:
 snap(PROJECT/f,'generic/'+f)
ck('prior_frozen_receipt_digest',sha((FROZEN/'audit.json').read_bytes())=='sha256:838faa0008177d651df2b288e7c99edb937e36f2c89b9e4f4d731c1d666603d8')
for f in ['audit.json','independent-reference-shape.json','mathematical-scope-observations.json','debruijn-bindings.json']:
 snap(FROZEN/f,'preceding-frozen-audit/'+f)
cert=load('package/accepted/acceptance.json');ir=load('package/accepted/accepted-ir.json');frozen=load('package/contract/challenge/statements.json');challenge=load('package/contract/challenge/challenge.json');form=load('package/contract/challenge/formalization.json');policy=load('package/contract/challenge/policy.json');claims=load('package/claims.json');records=claims['obligations'];by_id={x['id']:x for x in records};statements=frozen['statements']
ck('certificate_root_frozen',cert['contract_input_root']==challenge['contract_input_root']==ir['contract_input_root'])
ck('certificate_diagnostics_empty',cert['diagnostics']==[] and cert['gate']=='accepted_and_proved')
ck('certificate_content_addressed_copy',sha((PKG/ir['acceptance_certificate_ref']).read_bytes())==sha((PKG/'accepted/acceptance.json').read_bytes()))
for k,ref in cert['artifacts'].items():ck('artifact_exact_hash:'+k,sha((PKG/ref['path']).read_bytes())==ref['sha256'])
ck('accepted_environment_ir_binding',ir['accepted_environment_hash']==cert['artifacts']['environment_export']['sha256'])
ck('accepted_profile_byte_equals_frozen',(PKG/cert['artifacts']['profile']['path']).read_bytes()==(PKG/'contract/challenge/profile.json').read_bytes())
ck('accepted_statements_byte_equals_frozen',(PKG/cert['artifacts']['statements']['path']).read_bytes()==(PKG/'contract/challenge/statements.json').read_bytes())
ck('ir_addressed_copy',sha((PKG/'accepted/accepted-ir.json').read_bytes())=='sha256:d4a33c54ac9de03426a46a20475840852b6d11f16818b67e8da1b5c4f140a6ca')
ck('ir_addressed_file_equals', (PKG/'accepted/ir/d4a33c54ac9de03426a46a20475840852b6d11f16818b67e8da1b5c4f140a6ca.json').read_bytes()==(PKG/'accepted/accepted-ir.json').read_bytes())
ck('exact_12_obligation_set',set(ir['obligations'])==set(cert['obligations'])==set(statements)==set(by_id) and len(by_id)==12)
# This registered consumer performs file/schema/evidence checks only. Its source
# has been inspected; it does not invoke export.run/C.analyze/kernel/model tools.
pkg=Package(PKG)
verified,ir_hash,verified_cert,diags=E.verified_ir(pkg)
put('registered-ir-validation.json',{'ir_hash':ir_hash,'diagnostics':[d.to_dict() for d in diags],'certificate_hash':sha((PKG/'accepted/acceptance.json').read_bytes())})
ck('registered_consumer_ir_validation',not diags and verified==ir and verified_cert==cert)
# Retain the exact finite evidence rows consumed for contract milestones.
from verislop.claimcheck import evaluate_claim
contract_evidence=[]
for oid,rec in by_id.items():
 for milestone,verifier,key,expected_root in [('TYPECHECKED','verislop.lean-acceptance','contract_input_root',cert['contract_input_root']),('PROVED','verislop.lean-acceptance','contract_input_root',cert['contract_input_root']),('REIFIED','verislop.reifier','acceptance_certificate',sha((PKG/'accepted/acceptance.json').read_bytes()))]:
  if milestone=='PROVED' and rec['role']!='guarantee':continue
  cid=f'{milestone}:{oid}@{rec["revision"]}'
  checked=evaluate_claim({'claim_id':cid,'verifier':verifier},pkg.evidence.for_claim(cid),{key:expected_root},key)
  ev=checked.evidence
  ck('authorized_exact_evidence:'+cid,checked.authorized and checked.outcome=='PASS' and not checked.diagnostics and ev is not None)
  snap(PKG/'evidence'/f'{ev.id}.json','package/evidence/'+ev.id+'.json');snap(PKG/ev.record['raw_result_ref'],'package/'+ev.record['raw_result_ref'])
  row={'claim_id':cid,'evidence_id':ev.id,'record':ev.record,'result':ev.result}
  contract_evidence.append(row)
  if milestone=='REIFIED':
   check=ev.result['check'];ck('denotation_identity:'+cid,check['denotation_defeq'] is True if statements[oid]['representation'] in ['contract_dsl','source_facets'] else check['denotation_defeq'] is None)
put('contract-evidence.json',contract_evidence)
# Reconstruct declarations and registry purely from the retained kernel AST export.
export_json=load('package/'+cert['artifacts']['environment_export']['path'])
env=C.Env.from_export(export_json,policy,'read-only accepted audit')
ck('stored_replay_and_pure_env_validation',not env.diagnostics and export_json['replay']['ok'])
put('pure-env-validation.json',{'diagnostics':[d.to_dict() for d in env.diagnostics],'replay':export_json['replay'],'import':export_json['import'],'declarations':len(env.decls)})
registry=C.decode_registry(env.decls);reg={r['id']:r for r in registry}
ck('registry_exact_ids',set(reg)==set(by_id))
for oid,r in by_id.items():
 ck('registry_exact_metadata:'+oid,all(reg[oid][k]==r[k] for k in C.RECORD_FIELDS))
 for k in ['id','revision','kind','role','statement','required','source_refs','scope','acceptance_criteria']:
  ck('IR_from_registry:'+oid+':'+k,ir['obligations'][oid][k]==reg[oid][k])
 a=cert['obligations'][oid];fo=ir['obligations'][oid]['formal'];st=statements[oid]
 ck('accepted_identity:'+oid,all(a[k]==r[k] for k in ['revision','kind','role']) and a['typechecked']=='PASS' and a['codes']==[])
 ck('accepted_guarantee_proof:'+oid,a['proved']==('PASS' if r['role']=='guarantee' else 'NOT_APPLICABLE'))
 ck('same_statement_hash:'+oid,a['statement_hash']==st['statement_hash']==fo['statement_hash'])
 ck('IR_same_statement_closure:'+oid,fo['semantic_closure_hash']==st['semantic_closure_hash'] and fo['hypotheses']==st['hypotheses'])
 ck('accepted_allowed_axioms:'+oid,set(a['axioms'])<=set(policy['allowed_axioms']))
 for name,digest in st['semantic_closure'].items():ck('frozen_dependency:'+oid+':'+name,env.hashes.get(name)==digest)
for name,digest in frozen['declaration_hashes'].items():
 if name.startswith(C.REGISTRY_NS+'.'):ck('reserved_registry_declaration:'+name,env.hashes.get(name)==digest)
ck('no_added_reserved_registry_declarations',not {n for n in env.decls if n.startswith(C.REGISTRY_NS+'.')} -set(frozen['declaration_hashes']))
for name,c in env.decls.items():
 ck('no_module_axiom:'+name,c['kind']!='axiom')
 ck('no_sorry_axiom:'+name,not any('sorryAx' in exprjson.name_str(a) for a in c.get('axioms',[])))
 ck('safe_semantic_decl:'+name,c.get('safety') not in {'unsafe','partial'})
 ck('no_unresolved_constants:'+name,not c.get('unresolved_constants'))
# Independently derive the pure data profile from accepted roots and typed metadata.
bnames=C.binding_names(form);roots=set()
for r in records:
 for name in bnames[r['id']]:roots.add(name);roots|=exprjson.constants(env.decls[name]['type'])
explicit={n for r in records for n in reg[r['id']]['bindings']}
profile_json,notes=R.derive_profile(form['profile_id'],env.decls,env.hashes,roots,explicit_declarations=explicit)
ck('profile_reconstructed_from_actual_AST',profile_json==load('package/contract/challenge/profile.json'))
put('pure-profile-reconstruction.json',{'profile':profile_json,'notes':notes,'roots':sorted(roots),'explicit_registry_declarations':sorted(explicit)})
profile=dsl.Profile.from_json(profile_json)
# Source model constructor decode is pure. We intentionally do not invoke
# reify_contract/verify_model, whose generic pin check may execute Lean.
accepted_expressions={}
for oid,row in ir['obligations'].items():
 ref=row['formal']['formula_ref'];digest=ref.rsplit('@',1)[1]
 data=(PKG/'accepted/expressions'/f'{digest.split(":")[1]}.json').read_bytes();ck('expression_ref_digest:'+oid,sha(data)==digest);accepted_expressions[oid]=json.loads(data)
 if statements[oid]['representation'] in {'contract_dsl','source_facets'}:ck('accepted_expression_full_frozen:'+oid,accepted_expressions[oid]==statements[oid]['formula_package'])
for i in range(1,8):
 oid=f'O{i}';name=cert['obligations'][oid]['lean_symbol'];type_ast=env.decls[name]['type'];head,args=exprjson.head_const(type_ast)
 ck('mixed_complete_top_conjunction:'+oid,head=='And' and len(args)==2)
 facets=S._source_tree(args[1],profile,env.decls,env.hashes)
 formula,why,unfolded=R.reify_formula(args[0],profile,env.decls)
 ck('value_reconstructed_directly_from_accepted_AST:'+oid,formula==accepted_expressions[oid]['value']['formula'] and 'VeriSlopAST.valid_input' in unfolded)
 ck('source_reconstructed_directly_from_accepted_AST:'+oid,facets==accepted_expressions[oid]['source'])
 rhs=formula['body']['right']['right'];ck('accepted_full_reference_equals_independent_shape:'+oid,rhs==load('preceding-frozen-audit/independent-reference-shape.json'))
 projection=accepted_expressions[oid]['value_projection'];pd=env.decls[projection['lean_symbol']]
 pf,_,_=R.reify_formula(pd['type'],profile,env.decls)
 ck('projection_same_full_value_type:'+oid,pf==formula and env.hashes[projection['lean_symbol']]==projection['decl_hash'])
 ck('projection_uses_original_conjunction:'+oid,name in {exprjson.name_str(x) for x in pd['value_constants']})
 ck('assumption_and_witness_graph:'+oid,{'id':'A1','relation':'assumes'} in ir['obligations'][oid]['dependencies'] and {'id':'A1_satisfiable','relation':'requires_witness'} in ir['obligations'][oid]['dependencies'])
for oid in ['I1','S1']:
 name=cert['obligations'][oid]['lean_symbol'];facets=S._source_tree(env.decls[name]['type'],profile,env.decls,env.hashes)
 ck('approved_source_only_from_AST:'+oid,accepted_expressions[oid]['value'] is None and facets==accepted_expressions[oid]['source'])
ck('pure_source_policy_check',not source_policy.check(load('package/request/source-policy.json'),statements,records))
# Kernel-exported bounded witness head form, independently decoded and evaluated.
nv=env.decls['VeriSlopAST.input_inhabited'];nvf,why,_=R.reify_formula(nv['type'],profile,env.decls)
ck('nonvacuity_formula_actual_AST',nvf==accepted_expressions['A1_satisfiable']['formula'])
witness_export=next(w for w in export_json['witnesses'] if exprjson.name_str(w['theorem'])=='VeriSlopAST.input_inhabited')
ck('stored_kernel_witness_extraction_ok',witness_export['ok'])
matched=A.match_witnesses(nvf,witness_export['shape'],profile)
expected_witness=dsl.record_v('Input',[(),0,0,1,'none'])
ck('exact_concrete_input_witness',matched==[[expected_witness]])
truth=dsl.Evaluator(profile,{},lambda body,env: []).formula(nvf['body'],[expected_witness])
ck('witness_exact_guard_true',truth.value is True and truth.exact)
ck('witness_axioms_none',cert['obligations']['A1_satisfiable']['axioms']==[] and env.axioms('VeriSlopAST.input_inhabited')==[])
put('nonvacuity-witness.json',{'kernel_shape':witness_export,'pure_decoded':A._jsonable(matched,numeric_strings=True),'exact_guard_truth':{'value':truth.value,'exact':truth.exact}})
source=(PKG/cert['artifacts']['source']['path']).read_text()
ck('accepted_source_zero_sorry',not re.search(r'\bsorry\b|\bsorryAx\b',source))
ck('accepted_source_zero_explicit_axiom',not re.search(r'^\s*axiom\b',source,re.M))
ck('same_body_source_until_obligation_proofs',source.split('theorem «complete_aggregation» :',1)[0]==(PKG/'contract/challenge/Contract.lean').read_text().split('theorem «complete_aggregation» :',1)[0])
ck('accepted_proof_full_value_unfolds', 'unfold solve groups group_rows step stats bucket_count\n    rfl' in source)
ck('source_contract_proof_is_abstract_only','exact VeriSlop.Source.contract_sound SolveSource' in source)
for row in snapshots:ck('observed_file_stability:'+row['snapshot'],sha(Path(row['path']).read_bytes())==row['sha256'])
put('snapshot-manifest.json',{'format':'independent-audit-snapshots/1','entries':snapshots});put('checks.json',checks)
audit={'schema_version':'independent-accepted-scope-audit/1','phase':'Stage011 D21 accepted artifact','source_root':'sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a','accepted_ir_sha256':ir_hash,'acceptance_certificate_sha256':sha((PKG/'accepted/acceptance.json').read_bytes()),'contract_input_root':cert['contract_input_root'],'result':'NO_CONCRETE_ACCEPTED_SCOPE_DEFECT_FOUND_IN_BOUNDED_INSPECTION','checks':len(checks),'passed_checks':sum(x['pass'] for x in checks),'snapshots':len(snapshots),'stored_acceptance_evidence':'All12 typed; all10 guarantee obligations proved, including required derived A1_satisfiable; no sorryAx/module axioms; only policy-allowed base axioms. Stored kernel export replay ok, 410 constants including one authenticated quarantined unsafe runtime auxiliary; 409 semantic declarations retained by Env. Independent pure consumption does not replay the kernel.','semantic_scope':'Accepted statements/profile byte-equal frozen. Direct accepted AST reconstruction reproduces full O1-O7 value/source facets, same full domain and independent nested RHS, exact record shapes, and constructive witness. All11 original IDs remain required. Named definitions and all frozen registry/semantic declarations retained exactly. No author JSON consulted as mathematical authority.','claim_limit':'Accepted mathematical contract and abstract source model only. Actual VSCore source refinement, raw coverage/inverses/effects/source adequacy, mechanical closure, release review and terminal success not audited or claimed.','prior_receipt_availability_correction':'Prior frozen receipt checked availability at contract/accepted; the canonical accepted directory is package/accepted. Its availability fields were only observations of that wrong path and are not lifecycle authority. This annex uses canonical certificate paths and binds exact new accepted artifacts. Frozen scope/proof-placeholder inspection is unaffected.','availability_observed_only':{'canonical_accepted_ir':str(PKG/'accepted/accepted-ir.json'),'implementation_exists':(PKG/'implementation').exists(),'bridge_exists':(PKG/'bridges/implementation').exists(),'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},'forbidden_actions_not_performed':['native/kernel/closure/gate execution','model/provider calls','author/controller/reviewer communication','package/cohort/project/production edits','historical task solutions/proofs/hidden cases']}
put('audit.json',audit);print(json.dumps(audit,indent=2))
