#!/usr/bin/env python3
"""Stage013 accepted-contract scope audit. Pure retained artifact checks only."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,re
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-013';RUN=STAGE/'run';PROJECT=STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';CH=PKG/'contract/challenge';OUT=Path(__file__).resolve().parent
PRIOR=ROOT/'synthetic_dataset/bootstrap/validation/tier2-d21-scope-audit-013/frozen-attempt-mcxowply'
SOURCE_ROOT='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710';CH_ROOT='sha256:006fd3741f22e86fa270f02450653297b77a0346acac6e8dc094182737f64d3c'
IR_HASH='sha256:6fb479b4861dc7ff78a04283e773858da28e088bc75649f5dd1e47dfe90377eb';CERT_HASH='sha256:e6c4e0293206ceba145bae9a138adaffa61841bbda3405249cf3dc1c0f6a91cb'
checks={};snaps={};observed={}
def h(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def d(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def check(k,b,detail=None):
 checks[k]={'ok':bool(b)}
 if detail is not None:checks[k]['detail']=detail
def capture(p,label):
 p=Path(p);check('regular:'+label,p.is_file() and not p.is_symlink());b=p.read_bytes();q=OUT/'snapshots'/label;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);snaps[label]={'source':str(p),'sha256':h(b),'bytes':len(b)};observed[str(p)]=h(b);return b
def js(p,label):return json.loads(capture(p,label))
protocol=js(RUN/'protocol.json','protocol.json');prereg=js(RUN/'preregistration.json','preregistration.json');check('source_protocol_authentication',protocol['source_root']==prereg['source_root']==SOURCE_ROOT==h(d(protocol['source_files'])) and prereg['protocol_sha256']==h((RUN/'protocol.json').read_bytes()))
for f,sha in protocol['source_files'].items():check('frozen_source:'+f,h(capture(PROJECT/f,'project/'+f))==sha)
for f,sha in protocol['input_files'].items():check('prepared_input:'+f,h(capture(RUN/f,'prepared/'+f))==sha)
metadata=json.loads((RUN/'requests/D21/original-metadata.json').read_bytes());policy=json.loads((RUN/'requests/D21/source-policy.json').read_bytes());orig={r['id'] for r in metadata['identities']}
prior=js(PRIOR/'audit.json','prior-current013-frozen/audit.json');seal=js(PRIOR/'RECEIPT-MANIFEST.json','prior-current013-frozen/RECEIPT-MANIFEST.json');reference=js(PRIOR/'reference-value-package.json','prior-current013-frozen/reference-value-package.json');guard=js(PRIOR/'exact-guard.json','prior-current013-frozen/exact-guard.json')
check('same_current_stage_scope_receipt',h((PRIOR/'audit.json').read_bytes())=='sha256:a7b7bb39c7b123b09ab7bd01fbabf8d2e617e8d7629a6db55556e3b7ccc41e58' and prior['source_root']==SOURCE_ROOT and prior['frozen_challenge_root']==CH_ROOT and prior['outcome']=='NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE')
check('prior_receipt_seal_root',h(d(seal['files']))==seal['files_root'])
for f in ['audit.json','reference-value-package.json','exact-guard.json']:check('prior_receipt_member:'+f,h((PRIOR/f).read_bytes())==seal['files'][f])
challenge=js(CH/'challenge.json','package/challenge.json');check('challenge_root',challenge['contract_input_root']==CH_ROOT==h(d(challenge['manifest'])))
for row in challenge['manifest']['entries']:
 b=capture(PKG/row['path'],'package/'+row['path']);check('frozen_member:'+row['path'],h(b)==row['sha256'] and len(b)==row['size'])
records={r['id']:r for r in json.loads((PKG/'claims.json').read_bytes())['obligations']};form=json.loads((CH/'formalization.json').read_bytes());statements=json.loads((CH/'statements.json').read_bytes());accept_policy=json.loads((CH/'policy.json').read_bytes())
ir=js(PKG/'accepted/accepted-ir.json','package/accepted-ir.json');cert=js(PKG/'accepted/acceptance.json','package/acceptance.json');check('exact_IR_and_certificate_hash',h((PKG/'accepted/accepted-ir.json').read_bytes())==IR_HASH and h((PKG/'accepted/acceptance.json').read_bytes())==CERT_HASH)
check('content_addressed_certificate_alias',capture(PKG/ir['acceptance_certificate_ref'],'package/'+ir['acceptance_certificate_ref'])==(PKG/'accepted/acceptance.json').read_bytes())
check('content_addressed_IR_alias',capture(PKG/'accepted/ir'/f'{IR_HASH[7:]}.json','package/accepted/ir/'+IR_HASH[7:]+'.json')==(PKG/'accepted/accepted-ir.json').read_bytes())
for k,a in cert['artifacts'].items():check('accepted_artifact:'+k,h(capture(PKG/a['path'],'package/'+a['path']))==a['sha256'] and a['sha256'][7:] in a['path'])
check('accepted_exact_challenge_policy',cert['contract_input_root']==ir['contract_input_root']==CH_ROOT and cert['policy']['hash']==h((CH/'policy.json').read_bytes()) and cert['policy']['allowed_axioms']==accept_policy['allowed_axioms']==['Classical.choice','Quot.sound','propext'])
check('accepted_twelve_ids_no_diagnostics',cert['gate']=='accepted_and_proved' and cert['diagnostics']==[] and set(cert['obligations'])==set(ir['obligations'])==set(records)==orig|{'valid_domain_witness'} and len(ir['obligations'])==12)
for ident in metadata['identities']:check('original_identity:'+ident['id'],all(ir['obligations'][ident['id']][k]==ident[k] for k in ['id','kind','role','required']))
source=(PKG/cert['artifacts']['source']['path']).read_text();frozen=(CH/'Contract.lean').read_text();check('zero_holes_or_candidate_axioms',not re.search(r'\b(sorry|admit|axiom)\b',source) and 'native_decide' not in source)
for theorem in ['complete_behavior','source_behavior','valid_input_inhabited']:
 def header(text):return next(l.split(':= by',1)[0].rstrip() for l in text.splitlines() if l.startswith('theorem «'+theorem+'»'))
 check('same_frozen_theorem_header:'+theorem,header(source)==header(frozen))
check('same_SourceBoundary_and_registry_prefix',source.split('namespace VeriSlopAST\n',1)[0]==frozen.split('namespace VeriSlopAST\n',1)[0] and (PROJECT/'verislop/lean/SourceBoundary.lean').read_text().replace('import Std\n','',1).strip() in source)
check('accepted_profile_statements_exact',(PKG/cert['artifacts']['profile']['path']).read_bytes()==(CH/'profile.json').read_bytes() and (PKG/cert['artifacts']['statements']['path']).read_bytes()==(CH/'statements.json').read_bytes())
profile_json=json.loads((CH/'profile.json').read_bytes());envjson=json.loads((PKG/cert['artifacts']['environment_export']['path']).read_bytes());check('environment_and_pin_binding',ir['accepted_environment_hash']==cert['artifacts']['environment_export']['sha256'] and ir['lean_toolchain']==cert['toolchain']['pin']=='leanprover/lean4:v4.34.1' and envjson['lean_githash']=='5045d0056413266e57c625dcd7c365b10e377c52' and envjson['import']['ok'] and envjson['replay']['ok'])
sys.path.insert(0,str(PROJECT))
from verislop import contract as C,exprjson,reify,dsl,export,accept,source_contract,source_policy,lifecycle,leanbridge
from verislop.package import Package
with patch.object(leanbridge,'run_kernel_tool',side_effect=AssertionError('kernel forbidden')),patch.object(leanbridge,'compile_module',side_effect=AssertionError('compilation forbidden')):
 vi,vh,vc,diags=export.verified_ir(Package(PKG));check('pure_registered_current_IR',not diags and vi==ir and vh==IR_HASH and vc==cert,[x.to_json() for x in diags])
 env=C.Env.from_export(envjson,accept_policy,'independent accepted013 stored export audit');check('accepted_export_safety_validation',not env.diagnostics,[x.to_json() for x in env.diagnostics])
 registry=C.decode_registry(env.decls);reg={r['id']:r for r in registry};check('AST_registry_exact_ids',set(reg)==set(records) and len(registry)==len(records)==12)
 for k,r in records.items():
  check('AST_registry_fields:'+k,all(reg[k][z]==r[z] for z in C.RECORD_FIELDS));check('IR_from_AST_metadata:'+k,all(ir['obligations'][k][z]==reg[k][z] for z in ['id','revision','kind','role','statement','required','source_refs','scope','acceptance_criteria']))
 for n,sha in statements['declaration_hashes'].items():check('accepted_frozen_decl:'+n,env.hashes.get(n)==sha)
 for k,st in statements['statements'].items():
  check('closure_hash:'+k,st['semantic_closure_hash']==h(d({'toolchain':cert['toolchain']['pin'],'declarations':st['semantic_closure']})))
  for n,sha in st['semantic_closure'].items():check('safe_exact_closure:'+k+':'+n,env.hashes.get(n)==sha and env.decls[n]['safety']=='safe' and env.decls[n]['unresolved_constants']==[])
 names=C.binding_names(form);roots=set()
 for k in records:
  for n in names[k]:roots.add(n);roots.update(exprjson.constants(env.decls[n]['type']))
 derived,notes=reify.derive_profile(form['profile_id'],env.decls,env.hashes,roots,explicit_declarations={n for r in registry for n in r['bindings']});check('profile_from_accepted_types',derived==profile_json,notes)
 profile=dsl.Profile.from_json(profile_json);packages={}
 for k,r in ir['obligations'].items():
  sha=r['formal']['formula_ref'].rsplit('@',1)[1];p=PKG/'accepted/expressions'/f'{sha[7:]}.json';pack=js(p,'package/accepted-expressions/'+k+'.json');packages[k]=pack;check('formula_artifact_hash:'+k,h(p.read_bytes())==sha)
  row=cert['obligations'][k];st=statements['statements'][k]
  check('statement_identity:'+k,all(row[z]==r['formal'][z]==st[z] for z in ['statement_hash','representation','lean_symbol']))
  check('type_and_proof_applicability:'+k,row['typechecked']=='PASS' and row['proved']==('PASS' if r['role']=='guarantee' else 'NOT_APPLICABLE') and row['codes']==[])
  check('only_permitted_axioms:'+k,set(row['axioms'])<=set(accept_policy['allowed_axioms']) and r['formal']['axioms']==row['axioms'])
  if r['role']=='guarantee':
   decl=env.decls[row['lean_symbol']];check('proof_dependency_axioms:'+k,row['axioms']==[exprjson.name_str(a) for a in decl['axioms']] and decl['kind']=='theorem' and decl['unresolved_constants']==[])
  if 'formula_package' in st:check('formula_exact_frozen_package:'+k,pack==st['formula_package'])
  else:check('typed_metadata_exact_AST_bindings:'+k,pack=={'encoding':'verislop.typed-metadata/0.1','semantic_profile':profile_json['profile_id'],'registry_entry':'VeriSlop.Registry.'+k,'bindings':{n:env.hashes[n] for n in st['bindings']}})
 check('all_O1_O7_whole_value_package',all(packages['O'+str(i)]==reference for i in range(1,8)))
 actual=env.decls['VeriSlopAST.complete_behavior'];head,args=exprjson.head_const(actual['type']);check('actual_complete_mixed_conjunction',head=='And' and len(args)==2)
 value,reason,unfolded=reify.reify_formula(args[0],profile,env.decls);check('value_reconstructed_from_actual_type',value==reference['value']['formula'] and reason=='reified into verislop.contract-dsl/0.2' and unfolded=={'VeriSlopAST.valid_input'})
 facet=source_contract._decode_contract(args[1],profile,env.decls,env.hashes);check('source_facet_reconstructed_from_actual_type',[facet]==reference['source'])
 check('entire_projection_type_preserved',exprjson.canon(env.decls['VeriSlopAST._vs_value_complete_behavior']['type'],[])==exprjson.canon(args[0],[]) and 'VeriSlopAST.complete_behavior' in exprjson.constants(env.decls['VeriSlopAST._vs_value_complete_behavior']['value']))
 check('source_only_same_endpoint',all(packages[k]['value'] is None and packages[k]['source']==[facet] for k in ['I1','S1']) and source_contract._decode_contract(env.decls['VeriSlopAST.source_behavior']['type'],profile,env.decls,env.hashes)==facet)
 check('full_unbounded_domain',value['tag']=='forall' and value['sort']=={'record':'Input'} and value['body']['tag']=='implies' and value['body']['left']==guard)
 wdecl=env.decls['VeriSlopAST.valid_input_inhabited'];wf,why,uw=reify.reify_formula(wdecl['type'],profile,env.decls);check('witness_exact_same_guard',wf=={'tag':'exists','sort':{'record':'Input'},'body':guard} and uw=={'VeriSlopAST.valid_input'})
 shapes=[w for w in envjson['witnesses'] if exprjson.name_str(w['theorem'])=='VeriSlopAST.valid_input_inhabited'];check('one_kernel_extracted_witness',len(shapes)==1 and shapes[0]['ok'])
 decoded=accept.match_witnesses(wf,shapes[0]['shape'],profile);check('constructive_empty_interval_witness',decoded==[[('record','Input',((),0,0,1,'none'))]] and cert['obligations']['valid_domain_witness']['axioms']==[] and cert['obligations']['valid_domain_witness']['witnesses']==[[{'tuple':['record','Input',{'tuple':[{'tuple':[]},{'int':'0'},{'int':'0'},{'int':'1'},'none']}]}]])
 nv=ir['obligations']['valid_domain_witness'];check('required_witness_proved_but_impl_NA',nv['required'] and nv['kind']=='non_vacuity' and lifecycle.applicability(nv)['PROVED'][0] and not lifecycle.applicability(nv)['END_TO_END_VERIFIED'][0])
 check('nine_transfer_applicable_not_witness',sorted(k for k,r in ir['obligations'].items() if r['required'] and lifecycle.applicability(r)['END_TO_END_VERIFIED'][0])==['I1','O1','O2','O3','O4','O5','O6','O7','S1'])
 check('source_policy_accepted_AST_enforced',not source_policy.check_ir(Package(PKG),ir,list(records.values())))
 # Reconstruct each current accepted helper body from typed lambda AST, not author JSON.
 models={}
 for name,row in profile.symbols.items():
  expr=env.decls[row['lean_decl']]['value'];sorts=[]
  while 'lam' in expr:
   lam=expr['lam'];sorts.append(lam['type']);expr=lam['body']
  rr=reify._Reifier(profile,env.decls);body=rr.term(expr,[('var',s) for s in reversed(row['args'])]);result=dsl.type_term(body,list(reversed(row['args'])),profile);check('typed_body_from_accepted_AST:'+name,len(sorts)==len(row['args']) and result==row['result']);models[name]={'args':row['args'],'result':row['result'],'body':body,'lean_decl':row['lean_decl']}
 check('current_helper_inventory',set(models)=={'aggregate','group_rows','solve'})
 (OUT/'accepted-reference-models.json').write_bytes(d(models));(OUT/'accepted-extracted-witness.json').write_bytes(d(shapes));(OUT/'accepted-registry.json').write_bytes(d(registry))
 evidence=[]
 for p in (PKG/'evidence').glob('*.json'):
  e=json.loads(p.read_bytes())
  if e['claim_id'].split(':',1)[0] in {'TYPECHECKED','PROVED','REIFIED'}:
   evidence.append(e);capture(p,'package/evidence/'+p.name);raw=js(PKG/e['raw_result_ref'],'package/'+e['raw_result_ref']);check('native_evidence_hash:'+e['evidence_id'],h((PKG/e['raw_result_ref']).read_bytes())==e['raw_result_hash']);check('native_evidence_success:'+e['evidence_id'],e['status']=='PASS' and e['input_root_hash']==CH_ROOT)
 check('complete_native_contract_evidence',{e['claim_id'] for e in evidence}=={'TYPECHECKED:'+k+'@1' for k in records}|{'PROVED:'+k+'@1' for k,r in records.items() if r['role']=='guarantee'}|{'REIFIED:'+k+'@1' for k in records})
for p,sha in observed.items():check('unchanged:'+p,h(Path(p).read_bytes())==sha)
fail=[k for k,v in checks.items() if not v['ok']];availability={'materialized_implementation':(PKG/'implementation').exists(),'bridge':(PKG/'bridges').exists(),'semantic':(PKG/'semantic').exists(),'closure':(PKG/'closure/current.json').exists()}
audit={'format':'independent-bounded-audit/0.1','phase':'accepted-contract','stage':'013','task':'D21','time':datetime.now(timezone.utc).isoformat(),'source_root':SOURCE_ROOT,'frozen_challenge_root':CH_ROOT,'accepted_IR_hash':IR_HASH,'acceptance_certificate_hash':CERT_HASH,'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not fail else 'AUDIT_ASSERTION_FAILURE','checks':len(checks),'failed_checks':fail,'snapshots':len(snaps),'availability_only':availability,'observations':['Accepted AST registry and reconstructed profile preserve all eleven original identities and separately derived required witness.','Every frozen declaration/type hash, exact formula package and semantic closure remains bound to the accepted artifacts.','Actual theorem type reconstructs the full independent reference with exact public domain and all nine mandatory endpoint/source requirements.','All applicable guarantees are proved; only propext/Classical.choice/Quot.sound appear on mixed source-contract proofs.','Constructive valid_domain_witness has no axioms and decodes to events=[], start=end=0,width=1,fill=none; it is required PROVED and implementation N/A.','All source and typed helper models were reconstructed from accepted AST; author proposal JSON supplied no semantic authority.'],'limits':['No task candidate or reference function executed.','No Lean/kernel/model/native/mechanical replay or author communication.','Source.Contract proves the abstract requirement checker; delivered source needs compiler-bound adequacy and universal refinement separately.','No implementation/refinement/lifecycle success claimed.','Natural-language mathematical correspondence remains the explicit trust boundary.']}
(OUT/'checks.json').write_bytes(d(checks));(OUT/'snapshots.json').write_bytes(d(snaps));(OUT/'audit.json').write_bytes(d(audit));print(json.dumps(audit,indent=2));assert not fail,fail
