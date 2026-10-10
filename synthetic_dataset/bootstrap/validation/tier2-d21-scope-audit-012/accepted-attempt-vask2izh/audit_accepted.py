#!/usr/bin/env python3
"""Accepted Stage012 contract evidence audit. No kernel/native/model reruns."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
from unittest.mock import patch
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-012'
RUN,PROJECT=STAGE/'run',STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';CH=PKG/'contract/challenge'
OUT=Path(__file__).resolve().parent;PRIOR=ROOT/'synthetic_dataset/bootstrap/validation/tier2-d21-scope-audit-012/frozen-attempt-h62jrhjz'
SOURCE_ROOT='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710'
CHALLENGE_ROOT='sha256:fa6cdd7a1dd8e85982b48c0034da5def3fab380a929a2fef3072a93ffa8f054a'
IR_HASH='sha256:a5ded856a6c82cc73c69048d8f922aabfe15d909990290752dd0c30dcc9887bb'
CERT_HASH='sha256:7ae08bb96ed1320c9d990c425957c514e36d36eb7bb2bf4ece0b17b9185a0a95'
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def dumps(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def now():return datetime.now(timezone.utc).isoformat()
checks,snapshots,observed={},{},{};started=now()
def check(name,ok,detail=None):
 checks[name]={'ok':bool(ok)}
 if detail is not None:checks[name]['detail']=detail
 return bool(ok)
def capture(path,label,stable=True):
 path=Path(path);check('regular:'+label,path.is_file() and not path.is_symlink());data=path.read_bytes()
 target=OUT/'snapshots'/label;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 snapshots[label]={'source':str(path),'sha256':digest(data),'size':len(data),'stable_phase_input':stable}
 if stable:observed[str(path)]=digest(data)
 return data
def capture_json(path,label,stable=True):return json.loads(capture(path,label,stable))
protocol=capture_json(RUN/'protocol.json','request/protocol.json');prereg=capture_json(RUN/'preregistration.json','request/preregistration.json')
check('preregistered_source',protocol['source_root']==prereg['source_root']==SOURCE_ROOT and digest(dumps(protocol['source_files']))==SOURCE_ROOT and prereg['protocol_sha256']==digest((RUN/'protocol.json').read_bytes()))
for name,sha in protocol['source_files'].items():check('frozen_source:'+name,digest(capture(PROJECT/name,'frozen-project/'+name))==sha)
for name,sha in protocol['input_files'].items():check('prepared_input:'+name,digest(capture(RUN/name,'prepared/'+name))==sha)
metadata=json.loads((RUN/'requests/D21/original-metadata.json').read_bytes());original_ids={x['id'] for x in metadata['identities']}
source_policy=json.loads((RUN/'requests/D21/source-policy.json').read_bytes())
prior=capture_json(PRIOR/'audit.json','prior-frozen-receipt/audit.json');seal=capture_json(PRIOR/'RECEIPT-MANIFEST.json','prior-frozen-receipt/RECEIPT-MANIFEST.json')
reference=capture_json(PRIOR/'reference-value-package.json','prior-frozen-receipt/reference-value-package.json');guard=capture_json(PRIOR/'exact-guard.json','prior-frozen-receipt/exact-guard.json')
check('prior_frozen_receipt_exact',digest((PRIOR/'audit.json').read_bytes())=='sha256:9bd42136f97b437de9614a45044ff514cf1f8f7b0a2c4a3b240077ad2e9ff82e' and prior['source_root']==SOURCE_ROOT and prior['frozen_challenge_root']==CHALLENGE_ROOT)
for name in ['audit.json','reference-value-package.json','exact-guard.json']:check('prior_frozen_seal:'+name,seal['files'][name]==digest((PRIOR/name).read_bytes()))
check('prior_frozen_seal_root',digest(dumps(seal['files']))==seal['files_root'])
challenge=capture_json(CH/'challenge.json','package/contract/challenge/challenge.json');check('frozen_challenge_hash',challenge['contract_input_root']==CHALLENGE_ROOT==digest(dumps(challenge['manifest'])))
for row in challenge['manifest']['entries']:
 data=capture(PKG/row['path'],'package/'+row['path']);check('frozen_member:'+row['path'],digest(data)==row['sha256'] and len(data)==row['size'])
claims=json.loads((PKG/'claims.json').read_bytes());records={x['id']:x for x in claims['obligations']}
form=json.loads((CH/'formalization.json').read_bytes());frozen=json.loads((CH/'statements.json').read_bytes());pol=json.loads((CH/'policy.json').read_bytes())
# package.json is mutable run bookkeeping; retain its observation but do not treat it as a frozen claim.
capture(PKG/'package.json','package/package.json',stable=False)
cert=capture_json(PKG/'accepted/acceptance.json','package/accepted/acceptance.json')
check('certificate_alias_hash',digest((PKG/'accepted/acceptance.json').read_bytes())==CERT_HASH)
for name,artifact in cert['artifacts'].items():
 data=capture(PKG/artifact['path'],'package/'+artifact['path']);check('accepted_content_address:'+name,digest(data)==artifact['sha256'] and artifact['sha256'].split(':')[1] in artifact['path'])
ir=capture_json(PKG/'accepted/accepted-ir.json','package/accepted/accepted-ir.json')
capture(PKG/ir['acceptance_certificate_ref'],'package/'+ir['acceptance_certificate_ref'])
check('certificate_immutable_alias', (PKG/ir['acceptance_certificate_ref']).read_bytes()==(PKG/'accepted/acceptance.json').read_bytes())
check('IR_exact_hash',digest((PKG/'accepted/accepted-ir.json').read_bytes())==IR_HASH)
capture(PKG/'accepted/ir'/f'{IR_HASH.split(":")[1]}.json','package/accepted/ir/'+IR_HASH.split(':')[1]+'.json')
check('IR_immutable_alias',(PKG/'accepted/ir'/f'{IR_HASH.split(":")[1]}.json').read_bytes()==(PKG/'accepted/accepted-ir.json').read_bytes())
check('accepted_bound_challenge_and_policy',cert['contract_input_root']==ir['contract_input_root']==CHALLENGE_ROOT and cert['policy']['hash']==digest((CH/'policy.json').read_bytes()) and cert['policy']['allowed_axioms']==pol['allowed_axioms']==['Classical.choice','Quot.sound','propext'])
check('accepted_complete_no_diagnostics',cert['gate']=='accepted_and_proved' and cert['diagnostics']==[] and set(cert['obligations'])==set(ir['obligations'])==set(records)==original_ids|{'A1_nonvacuity'})
for identity in metadata['identities']:
 id=identity['id'];r=ir['obligations'][id]
 check('accepted_original_identity:'+id,{k:r[k] for k in ('id','role','kind','required')}=={k:identity[k] for k in ('id','role','kind','required')})
accepted_source=(PKG/cert['artifacts']['source']['path']).read_text()
check('zero_source_holes_and_module_axioms',not re.search(r'\b(sorry|admit|axiom)\b',accepted_source) and 'native_decide' not in accepted_source)
for theorem in ('aggregation_contract','assumption_inhabited','source_contract'):
 def header(text):return next(line.split(':= by',1)[0].rstrip() for line in text.splitlines() if line.startswith('theorem «'+theorem+'»'))
 check('accepted_theorem_header_unchanged:'+theorem,header(accepted_source)==header((CH/'Contract.lean').read_text()))
check('accepted_registry_and_definitions_preserved',accepted_source.split('namespace VeriSlopAST\n',1)[0]==(CH/'Contract.lean').read_text().split('namespace VeriSlopAST\n',1)[0])
check('source_model_bytes_exact', (PROJECT/'verislop/lean/SourceBoundary.lean').read_text().replace('import Std\n','',1).strip() in accepted_source)
check('accepted_profile_statements_exact_frozen',(PKG/cert['artifacts']['profile']['path']).read_bytes()==(CH/'profile.json').read_bytes() and (PKG/cert['artifacts']['statements']['path']).read_bytes()==(CH/'statements.json').read_bytes())
profile_json=json.loads((PKG/cert['artifacts']['profile']['path']).read_bytes());env_export=json.loads((PKG/cert['artifacts']['environment_export']['path']).read_bytes())
check('IR_export_environment_binding',ir['accepted_environment_hash']==cert['artifacts']['environment_export']['sha256'] and ir['lean_toolchain']==cert['toolchain']['pin']=='leanprover/lean4:v4.34.1' and ir['exporter_id']=='verislop.reifier')

# Pure validators only. Explicit process-local guards reject accidental kernel/compiler calls.
sys.path.insert(0,str(PROJECT))
from verislop import contract as C,exprjson,reify,dsl,export,accept,source_contract,leanbridge
from verislop.package import Package
pkg=Package(PKG)
with patch.object(leanbridge,'run_kernel_tool',side_effect=AssertionError('Audit forbids kernel execution')),patch.object(leanbridge,'compile_module',side_effect=AssertionError('Audit forbids compilation')):
 valid_ir,valid_ir_hash,valid_cert,diags=export.verified_ir(pkg)
 check('pure_registered_IR_evidence_validation',not diags and valid_ir==ir and valid_ir_hash==IR_HASH and valid_cert==cert,[d.to_json() for d in diags])
 env=C.Env.from_export(env_export,pol,'independent stored accepted environment audit')
 check('pure_export_environment_validation',not env.diagnostics,[d.to_json() for d in env.diagnostics])
 registry=C.decode_registry(env.decls);reg={row['id']:row for row in registry}
 check('accepted_AST_registry_exact_ids',len(registry)==len(reg)==12 and set(reg)==set(records))
 for id,rec in records.items():
  check('accepted_AST_registry_fields:'+id,{k:reg[id][k] for k in C.RECORD_FIELDS}=={k:rec[k] for k in C.RECORD_FIELDS})
  check('IR_metadata_from_AST_registry:'+id,all(ir['obligations'][id][k]==reg[id][k] for k in ['id','revision','kind','role','statement','required','source_refs','scope','acceptance_criteria']))
 for name,sha in frozen['declaration_hashes'].items():check('accepted_decl_equals_frozen:'+name,env.hashes.get(name)==sha)
 profile=dsl.Profile.from_json(profile_json)
 # Derive carrier/profile metadata from accepted type ASTs without calling model replay.
 bnames=C.binding_names(form);roots=set()
 for rec in records.values():
  for name in bnames[rec['id']]:roots.add(name);roots.update(exprjson.constants(env.decls[name]['type']))
 derived_profile,profile_notes=reify.derive_profile(form['profile_id'],env.decls,env.hashes,roots,explicit_declarations={n for row in registry for n in row['bindings']})
 check('profile_reconstructed_from_accepted_AST',derived_profile==profile_json,profile_notes)
 for id,st in frozen['statements'].items():
  check('semantic_closure_hash:'+id,st['semantic_closure_hash']==digest(dumps({'toolchain':cert['toolchain']['pin'],'declarations':st['semantic_closure']})))
  for name,sha in st['semantic_closure'].items():
   check('accepted_semantic_closure:'+id+':'+name,env.hashes.get(name)==sha and env.decls[name]['safety']=='safe' and 'sorryAx' not in [exprjson.name_str(a) for a in env.decls[name].get('axioms',[])])
 expression_packages={}
 for id,row in ir['obligations'].items():
  sha=row['formal']['formula_ref'].rsplit('@',1)[1];path=PKG/'accepted/expressions'/f'{sha.split(":")[1]}.json'
  package=capture_json(path,'package/'+str(path.relative_to(PKG)));expression_packages[id]=package
  check('accepted_expression_hash:'+id,digest(path.read_bytes())==sha)
  certrow=cert['obligations'][id];st=frozen['statements'][id]
  check('accepted_statement_certificate_identity:'+id,all(row['formal'][k]==certrow[k]==st[k] for k in ['statement_hash','representation','lean_symbol']))
  check('accepted_all_typed:'+id,certrow['typechecked']=='PASS' and certrow['codes']==[])
  check('accepted_proof_applicability:'+id,certrow['proved']==('PASS' if records[id]['role']=='guarantee' else 'NOT_APPLICABLE'))
  check('accepted_only_allowed_axioms:'+id,set(certrow['axioms'])<=set(pol['allowed_axioms']))
  check('IR_axiom_certificate_binding:'+id,row['formal']['axioms']==certrow['axioms'])
  if records[id]['role']=='guarantee':
   decl=env.decls[st['lean_symbol']]
   check('accepted_proof_transitive_axioms:'+id,certrow['axioms']==[exprjson.name_str(a) for a in decl.get('axioms',[])] and decl['kind']=='theorem' and decl['unresolved_constants']==[])
  if 'formula_package' in st:check('accepted_expression_equals_frozen_package:'+id,package==st['formula_package'])
  expected_dependencies=export.mechanical_dependencies(id,st,frozen['statements'],certrow,reg[id],{x['id']:x['witnesses_for'] for x in form['internal_obligations']})
  check('IR_full_dependencies_from_AST:'+id,row['dependencies']==expected_dependencies)
 mixed_type=env.decls['VeriSlopAST.aggregation_contract']['type'];head,args=exprjson.head_const(mixed_type)
 check('accepted_actual_type_mixed_unconditional_conjunction',head=='And' and len(args)==2)
 actual_value,why,unfolded=reify.reify_formula(args[0],profile,env.decls)
 check('accepted_value_reified_from_type_AST',actual_value==reference['formula'] and why=='' and unfolded=={'VeriSlopAST.valid_input'},why)
 actual_source=source_contract._decode_contract(args[1],profile,env.decls,env.hashes)
 check('accepted_source_reified_from_constructor_AST',actual_source==expression_packages['O1']['source'][0])
 projection=env.decls['VeriSlopAST._vs_value_aggregation_contract']
 check('accepted_projection_exact_full_value_type',exprjson.canon(projection['type'],[])==exprjson.canon(args[0],[]) and ['VeriSlopAST','aggregation_contract'] in projection.get('value_constants',[]))
 source_only=source_contract._decode_contract(env.decls['VeriSlopAST.source_contract']['type'],profile,env.decls,env.hashes)
 check('accepted_sourceonly_same_endpoint_facets',source_only==actual_source and expression_packages['I1']['value'] is None and expression_packages['S1']['value'] is None)
 nv,why,unfolded=reify.reify_formula(env.decls['VeriSlopAST.assumption_inhabited']['type'],profile,env.decls)
 check('accepted_NV_type_exact_guard',nv=={'tag':'exists','sort':{'record':'Input'},'body':guard})
 witness=next(row for row in env_export['witnesses'] if row['theorem']==['VeriSlopAST','assumption_inhabited'])
 decoded=accept.match_witnesses(nv,witness['shape'],profile)
 check('accepted_witness_constructive_shape',witness['ok'] is True and decoded==[[('record','Input',((),0,0,1,'none'))]])
 json_witness=[[accept._jsonable(x,numeric_strings=True) for x in row] for row in decoded]
 check('certificate_exact_extracted_witness',json_witness==cert['obligations']['A1_nonvacuity']['witnesses'])
 check('guarantees_require_proved_witness',all({'id':'A1_nonvacuity','relation':'requires_witness'} in ir['obligations'][id]['dependencies'] for id in [f'O{i}' for i in range(1,8)]))
 # Reconstruct function bodies from their typed lambda ASTs; never evaluate task code.
 models={}
 for symbol,desc in profile.symbols.items():
  value=env.decls[desc['lean_decl']]['value'];ctx=[]
  for sort in desc['args']:
   check('accepted_model_lambda:'+symbol+':'+str(len(ctx)),'lam' in value)
   ctx=[('var',sort)]+ctx;value=value['lam']['body']
  body=reify._Reifier(profile,env.decls).term(value,ctx)
  check('accepted_model_body_typed:'+symbol,dsl.type_term(body,list(reversed(desc['args'])),profile)==desc['result'])
  models[symbol]={'args':desc['args'],'result':desc['result'],'decl_hash':env.hashes[desc['lean_decl']],'body':body}
 check('all_five_reference_definitions_reconstructed',set(models)=={'buckets','groups','stats','group_rows','solve'})
 # No kernel invocation occurs: reconstruct/analyze/reify_contract are deliberately not called because they replay models.

# Retain exact registered acceptance/export rows and all raw hashes, never author metadata as authority.
native_evidence={}
for file in sorted((PKG/'evidence').glob('*.json')):
 data=json.loads(file.read_bytes())
 if not data['claim_id'].startswith(('TYPECHECKED:','PROVED:','REIFIED:')):continue
 ev=capture_json(file,'package/evidence/'+file.name);raw=capture_json(PKG/ev['raw_result_ref'],'package/'+ev['raw_result_ref'])
 check('native_evidence_raw_hash:'+ev['claim_id'],digest((PKG/ev['raw_result_ref']).read_bytes())==ev['raw_result_hash'])
 check('native_evidence_current_success:'+ev['claim_id'],ev['status']=='PASS' and ev['exit_code']==0 and raw['milestone_outcome']=='PASS')
 if ev['claim_id'].startswith(('TYPECHECKED:','PROVED:')):check('native_acceptance_certificate_root:'+ev['claim_id'],ev['input_root_hash']==CHALLENGE_ROOT and raw['certificate_hash']==CERT_HASH)
 else:check('native_reification_exact_IR_and_certificate:'+ev['claim_id'],raw['ir_hash']==IR_HASH and raw['check']['certificate']==CERT_HASH and raw['check']['denotation_defeq'] in (None,True))
 native_evidence[ev['claim_id']]={'evidence_id':ev['evidence_id'],'verifier_id':ev['verifier_id'],'status':ev['status'],'raw_result_hash':ev['raw_result_hash']}
expected_evidence={*[f'TYPECHECKED:{id}@1' for id in records],*[f'PROVED:{id}@1' for id in records if records[id]['role']=='guarantee'],*[f'REIFIED:{id}@1' for id in records]}
check('exact_applicable_acceptance_export_evidence',set(native_evidence)==expected_evidence)
for path,sha in observed.items():check('snapshot_stable:'+str(Path(path).relative_to(ROOT)),digest(Path(path).read_bytes())==sha)
failures=[{'check':k,**v} for k,v in checks.items() if not v['ok']]
pending={name:(PKG/path).exists() for name,path in {'implementation':'implementation/program.vscore.json','bridge':'bridges/implementation','mechanical_pointer':'closure/current.json'}.items()}
report={'format':'verislop.independent-stage012-accepted-scope-audit/0.1','phase':'accepted_contract_only','auditor':'/root/tier2_semantics_audit','started_at_utc':started,'finished_at_utc':now(),'source_root':SOURCE_ROOT,'contract_input_root':CHALLENGE_ROOT,'acceptance_certificate_sha256':CERT_HASH,'accepted_IR_sha256':IR_HASH,'accepted_environment_sha256':cert['artifacts']['environment_export']['sha256'],'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failures else 'AUDIT_CHECK_FAILURE','checks_total':len(checks),'failed_checks':failures,'snapshots_count':len(snapshots),'original_required_ids':sorted(original_ids),'additional_registered_required_nonvacuity':'A1_nonvacuity','source_policy_rows':9,'value_required_ids':[f'O{i}' for i in range(1,8)],'source_only_ids':['I1','S1'],'accepted_scope_findings':prior['findings'][:-1]+[{'facet':'accepted proof and nonvacuity','finding':'All three frozen proof placeholders are replaced in the exact accepted source. Hash-bound kernel export records successful replay/import and all applicable guarantee proofs PASS under only propext/Classical.choice/Quot.sound. The exact constructive witness Input([],0,0,1,none) is extracted from the accepted proof and required by all guarded functional guarantees.'}],'reconstruction_scope':'Pure accepted type-AST value reification, closed source constructor decoding, registry decoding, declaration/semantic-closure hashes, derived carrier profile, five reference bodies, witness shape and current acceptance/export evidence authentication. No compiler or kernel invocation.','native_kernel_header':{'tool':env_export['tool'],'tool_version':env_export['tool_version'],'lean_version':env_export['lean_version'],'lean_githash':env_export['lean_githash'],'import_ok':env_export['import']['ok'],'direct_imports':env_export['import']['direct_imports'],'import_count':len(env_export['import']['modules']),'replay':env_export['replay']},'accepted_witness':json_witness,'native_evidence':native_evidence,'artifact_availability_only':pending,'limitations':['Accepted contract proof evidence is authenticated as stored; no independent Lean/kernel/native/gate/closure rebuild was performed.','Source Contract proves abstract checking rules and model inhabitance. It does not establish actual delivered-source admission, purity, observation/effect adequacy or implementation refinement.','Generated source, source certificates, bridge proof/refinement, raw coverage/adapters/transfers, two task builds, reviews and terminal closure remain outside this phase.','Natural-language correspondence, registered controller copies, pinned kernel, host tooling, hashing and OS/hardware remain explicit trust.','Pure reconstruction deliberately avoided routines that compile/replay normative models; process-local compiler/kernel guards prevented accidental calls.','No current role communication or guidance, task proof or source edits, model/provider request, historical task candidate/proof read, hidden case/oracle or task program execution occurred.','Only new outside-cohort snapshots/receipts were written.']}
for name,obj in [('audit.json',report),('checks.json',checks),('snapshot-manifest.json',snapshots),('accepted-reference-models.json',models),('accepted-registry.json',registry),('accepted-source-facet.json',actual_source),('accepted-extracted-witness.json',json_witness)]: (OUT/name).write_bytes(dumps(obj)+b'\n')
print(json.dumps({'audit':str(OUT/'audit.json'),'audit_sha256':digest((OUT/'audit.json').read_bytes()),'checks':len(checks),'failures':failures,'snapshots':len(snapshots),'pending':pending},sort_keys=True))
