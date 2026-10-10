"""Pure read-only D21 source proposal/bridge goal inspection; no proof execution."""
from pathlib import Path
import json,sys,hashlib,datetime,re
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-011';PROJECT=STAGE/'project';RUN=STAGE/'run';PKG=RUN/'artifacts/D21/verislop/package';ATT=PKG/'agents/vscore-attempts/source-2';MB=PKG.parent/'mailbox';OUT=Path(__file__).parent;PREV=OUT.parent/'accepted-attempt-vnoe1tk0'
sys.path.insert(0,str(PROJECT))
from verislop.targets import vscore3_source as S,vscore3_target as T
from verislop import canonical,exprjson,reify,source_contract,dsl
checks=[];snapshots=[]
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def put(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def ck(name,ok,detail=None):
 checks.append({'name':name,'pass':bool(ok),'detail':detail})
 if not ok:raise AssertionError(name)
def snap(path,label):
 b=path.read_bytes();p=OUT/'snapshots'/label;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);snapshots.append({'path':str(path),'snapshot':'snapshots/'+label,'sha256':sha(b),'size':len(b)});return b
def load(label):return json.loads((OUT/'snapshots'/label).read_text())
for f in ['program.vscore.json','relation.json','VeriSlopBridgeGoal.lean','model.json','profile.json','checks/source.json','proofs/1.lean']:snap(ATT/f,'proposal/'+f)
for f in ['request-0014.json','carrier-0014.json','carrier-binding-0014.json','response-0014.json']:snap(MB/f,'mailbox/'+f)
for f in ['accepted/accepted-ir.json','accepted/acceptance.json','request/source-policy.json','claims.json'] :snap(PKG/f,'package/'+f)
for f in ['original-prompt.txt','revised-prompt.txt','source-policy.json','delivery-revision.json']:snap(RUN/'requests/D21'/f,'cohort/requests/D21/'+f)
for f in ['verislop/targets/vscore3_source.py','verislop/targets/vscore3_target.py','verislop/targets/vscore_target.py','verislop/bridges/vscore3_checker.py','verislop/source_contract.py','verislop/reify.py']:snap(PROJECT/f,'generic/'+f)
for module,b in T.library_sources().items():
 p=T.LIB_ROOT/T.module_path(module);snap(p,'generic/verislop/lean/'+str(T.module_path(module)))
ck('prior_accepted_receipt_digest',sha((PREV/'audit.json').read_bytes())=='sha256:fb3fad850af492e8cac4bd01375107cb8de3ddbca2dfc3f67db669e78b807321')
snap(PREV/'audit.json','preceding-accepted-audit.json')
cert=load('package/accepted/acceptance.json');ir=load('package/accepted/accepted-ir.json')
profile_bytes=snap(PKG/cert['artifacts']['profile']['path'],'package/'+cert['artifacts']['profile']['path']);profile_json=json.loads(profile_bytes);profile=dsl.Profile.from_json(profile_json)
reference=snap(PKG/cert['artifacts']['source']['path'],'package/'+cert['artifacts']['source']['path'])
packages={}
for oid,row in ir['obligations'].items():
 digest=row['formal']['formula_ref'].rsplit('@',1)[1];f='accepted/expressions/'+digest.split(':')[1]+'.json';data=snap(PKG/f,'package/'+f);ck('accepted_expression_digest:'+oid,sha(data)==digest);packages[oid]=json.loads(data)
source=(OUT/'snapshots/proposal/program.vscore.json').read_bytes();wire=json.loads(source);program=S.parse_source(source);signatures=S.check_program({},program)
ck('canonical_source_roundtrip',S.source_bytes(program)==source)
ck('closed_language_profile',wire['language']=='vscore/0.3' and wire['profile']=='data-pipeline/0.3')
ck('only_exact_solve_entry',signatures==[{'id':'solve','params':[('record','Input')],'result':('list',('record','Output'))}])
relation=T.load_relation((OUT/'snapshots/proposal/relation.json').read_bytes());ck('exact_binding',relation['bindings']==[{'entry':'solve','symbol':'solve'}])
ck('canonical_model_descriptor',canonical.dumps(T.model_descriptor(ir['lean_toolchain']))==(OUT/'snapshots/proposal/model.json').read_bytes())
ck('canonical_profile_descriptor',canonical.dumps(T.profile_descriptor(profile_json,sha(profile_bytes)))==(OUT/'snapshots/proposal/profile.json').read_bytes())
obligations={}
for oid,row in ir['obligations'].items():
 p=packages[oid]
 if p['encoding']==source_contract.ENCODING:
  vp=source_contract.value_package(p);obligations[oid]={'lean_symbol':row['formal']['lean_symbol'],'statement_hash':row['formal']['statement_hash'],'formula':vp['formula'] if vp else None,'source_facets':source_contract.source_facets(p)}
ck('all_nine_original_impl_guarantees',set(obligations)=={'I1','S1',*[f'O{i}' for i in range(1,8)]})
spec=T.build_goal(source,relation,profile_json,obligations)
ck('entire_goal_reconstructs_from_accepted_packages',spec.text==(OUT/'snapshots/proposal/VeriSlopBridgeGoal.lean').read_text())
ck('mixed_refinement_required',spec.refinement_symbols=={'solve'})
ck('same_exact_entry_symbol',len(spec.symbols)==1 and spec.symbols[0].symbol=='solve' and spec.symbols[0].entry=='solve' and spec.symbols[0].lean_decl=='VeriSlopAST.solve')
# Verify binder preservation independently as replacement of one global constant
# in an otherwise identical accepted DSL denotation AST.
def replace(expr):
 if isinstance(expr,list):return [replace(x) for x in expr]
 if not isinstance(expr,dict):return expr
 if expr.get('const')==exprjson.parse_name('VeriSlopAST.solve'):return {**expr,'const':exprjson.parse_name('VeriSlopBridgeGoal.source_fn_solve')}
 return {k:replace(v) for k,v in expr.items()}
by_symbol={s.symbol:s for s in spec.symbols};transfer_artifacts={}
for ob in spec.obligations:
 if ob.formula is not None:
  before=reify.denote_formula(ob.formula,profile);after=T.transfer_expr(ob.formula,profile,by_symbol)
  ck('full_binder_and_guard_preserving_transfer:'+ob.oid,after==replace(before))
  ck('transfer_same_universal_input:'+ob.oid,ob.formula['tag']=='forall' and ob.formula['sort']=={'record':'Input'})
  transfer_artifacts[ob.oid]={'accepted_denotation':before,'source_function_denotation':after}
put('pure-transfer-binder-check.json',transfer_artifacts)
# Carrier request authenticates the same fixed source, goal and accepted artifacts.
request=load('mailbox/request-0014.json');carrier=load('mailbox/carrier-0014.json');payload=request['user'].split('\n',1)[1];context,n=json.JSONDecoder().raw_decode(payload)
ck('carrier_exact_request_sha',carrier['request_sha256']==sha((MB/'request-0014.json').read_bytes()))
ck('carrier_exact_messages',carrier['system']==request['system'] and carrier['user']==request['user'])
ck('carrier_exact_source',context['source']==wire and context['source_hash']==sha(source))
ck('carrier_exact_goal',context['generated_goal']==spec.text)
ck('carrier_exact_relation',context['relation']==relation)
ck('carrier_exact_accepted_reference',context['accepted_reference']['sha256']==sha(reference) and context['accepted_reference']['lean_source']==reference.decode())
ck('carrier_exact_accepted_profile',context['accepted_profile']==profile_json)
for oid,p in packages.items():ck('carrier_accepted_package:'+oid,context['accepted_packages'][oid]['package']==p and context['accepted_packages'][oid]['statement_hash']==ir['obligations'][oid]['formal']['statement_hash'])
for name,b in T.library_sources().items():ck('carrier_exact_library:'+name,context['verifier_library'][name]==b.decode())
ck('carrier_only_solve_refinement',context['refinement_symbols']==['solve'])
# Exact record field names/order/type and nominal carriers are preserved.
expected_records=profile_json['records'];decls={d['id']:d for d in wire['declarations']}
ck('nominal_record_set',set(decls)==set(expected_records))
for rid,r in expected_records.items():
 expected=[{'id':f['name'],'type':S.ty_json(T.sort_ty(f['sort']))} for f in r['fields']]
 ck('nominal_fields_exact:'+rid,decls[rid]['fields']==expected)
helpers={h['id']:h for h in wire['helpers']};ck('exact_helper_inventory',set(helpers)=={'bucket_count','bucket_start','stats','step','group_rows','groups'})
# De Bruijn table records every occurrence in each independent helper scope.
parameters={'bucket_count':['input'],'bucket_start':['input','bucket_index'],'stats':['input','group','bucket_index'],'step':['input','group','bucket_index','state'],'group_rows':['input','group'],'groups':['input'],'solve':['input']}
occ=[];binders=[]
def walk(e,path,env,current):
 if isinstance(e,list):
  for i,x in enumerate(e):walk(x,path+'/'+str(i),env,current)
  return
 if not isinstance(e,dict):return
 tag=e.get('tag')
 if tag=='var':
  i=e['index'];ck('source_var_bound:'+path,0<=i<len(env));occ.append({'path':path,'index':i,'binding':env[i],'environment':env});return
 if tag=='list_fold':
  elem,acc={'solve':('group','output_accumulator'),'stats':('event','stats_accumulator'),'group_rows':('bucket_index','state_accumulator')}[current]
  new=[elem,acc]+env;binders.append({'path':path,'tag':tag,'environment':new});walk(e['step'],path+'/step',new,current);walk(e['source'],path+'/source',env,current);walk(e['initial'],path+'/initial',env,current);return
 if tag=='list_map':
  new=['event']+env;binders.append({'path':path,'tag':tag,'environment':new});walk(e['body'],path+'/body',new,current);walk(e['value'],path+'/value',env,current);return
 if tag=='let':
  new=['stats']+env;binders.append({'path':path,'tag':tag,'environment':new});walk(e['value'],path+'/value',env,current);walk(e['body'],path+'/body',new,current);return
 if tag=='match_option':
  new=['some_value']+env;binders.append({'path':path,'tag':tag,'environment':new});walk(e['some'],path+'/some',new,current);walk(e['none'],path+'/none',env,current);walk(e['scrutinee'],path+'/scrutinee',env,current);return
 for k,x in e.items():
  if isinstance(x,(dict,list)):walk(x,path+'/'+k,env,current)
for fn in [*wire['helpers'],*wire['entries']]:walk(fn['body'],fn['id']+'/body',list(reversed(parameters[fn['id']])),fn['id'])
put('source-debruijn-bindings.json',{'binders':binders,'occurrences':occ})
# Check critical equivalent option-match/let cases by exact source structure.
stats=helpers['stats']['body'];match=stats['step']['then'];ck('stats_occurrence_fold',stats['tag']=='list_fold' and stats['source']=={'tag':'project','field':'events','value':{'tag':'var','index':2}})
ck('null_match_preserves_accumulator',match['tag']=='match_option' and match['none']=={'tag':'var','index':1})
some_fields={f['id']:f['value'] for f in match['some']['fields']};ck('some_count_shifted_accumulator',some_fields['count']['left']=={'tag':'project','field':'count','value':{'tag':'var','index':2}} and some_fields['count']['right']=={'tag':'nat','value':'1'})
ck('some_sum_shifted_accumulator_and_value',some_fields['sum']['left']=={'tag':'project','field':'sum','value':{'tag':'var','index':2}} and some_fields['sum']['right']=={'tag':'var','index':0})
step=helpers['step']['body'];ck('step_stats_argument_bindings',step['value']=={'tag':'call','helper':'stats','args':[{'tag':'var','index':3},{'tag':'var','index':2},{'tag':'var','index':1}]})
stepfields={f['id']:f['value'] for f in step['body']['fields']};prev=stepfields['previous'];ck('nonempty_zero_still_previous',prev['cond']=={'tag':'lt','left':{'tag':'nat','value':'0'},'right':{'tag':'project','field':'count','value':{'tag':'var','index':0}}} and prev['then']=={'tag':'some','value':{'tag':'project','field':'sum','value':{'tag':'var','index':0}}} and prev['else']=={'tag':'project','field':'previous','value':{'tag':'var','index':1}})
# Source shape and laws remain explicit in the proposed exact goal.
goal=spec.text
for marker in ['compileProgram profile rawProgram = .ok checkedProgram','findEntry checkedProgram "solve" = some entry_solve','adapter_8.inv (entry_solve.run (adapter_5.to x__0, ()))','∀ args, VSCore3.ArgsTyped entry_solve args → ∃ (x__0 : @VeriSlopAST.Input), args = [adapter_5.encode x__0]','VSCore3.encodeEnv_decodeEnv','adapter_5_decode_encode','adapter_8.to_from','VSCore3.SourceFactsAdequate profile rawProgram "solve" checkedProgram entry_solve','VSCore3.exactSourceFacts_adequate compiled_ok find_solve','adapter_8_raw','VSCore3.exactSourceFacts profile rawProgram "solve"']:
 ck('goal_required_marker:'+marker,marker in goal)
edge_names=exprjson.constants(spec.expected['EdgeProp']['value'])
expected_names={'VeriSlopBridgeGoal.SourceParses','VeriSlopBridgeGoal.SourceChecks','VeriSlopBridgeGoal.InputsCover_solve','VeriSlopBridgeGoal.RawEval_solve','VeriSlopBridgeGoal.Refines_solve','VeriSlopBridgeGoal.SourceAdequate_solve',*[f'VeriSlopBridgeGoal.Transfer_{oid}' for oid in obligations]}
ck('edge_all_scope_parts',expected_names<=edge_names)
ck('goal_no_sorry_axiom',not re.search(r'\bsorry\b|\bsorryAx\b|^\s*axiom\b',goal,re.M))
proof=(OUT/'snapshots/proposal/proofs/1.lean').read_text();ck('submitted_proof_exact_edge','theorem edge : VeriSlopBridgeGoal.EdgeProp' in proof and 'apply VeriSlopBridgeGoal.edge_of_refines' in proof)
ck('submitted_proof_no_admissions',not re.search(r'\bsorry\b|\bsorryAx\b|^\s*axiom\b|\bnative_decide\b|\bextern\b|\bimplemented_by\b',proof,re.M))
check=load('proposal/checks/source.json');ck('host_check_marker_bound_source',check['source_hash']==sha(source) and check['passed'] is True)
host_proof_attempts=[]
for f in sorted((ATT/'checks').glob('proof-*.json')):
 data=snap(f,'proposal/checks/'+f.name); row=json.loads(data);ck('proof_marker_source_binding:'+f.name,row['source_hash']==sha(source));host_proof_attempts.append({'file':f.name,'passed':row['passed'],'proof_checked':row['proof_checked'],'diagnostic_codes':[d['code'] for d in row.get('diagnostics',[])]})
for f in sorted((ATT/'proofs').glob('*.lean')):
 if f.name!='1.lean':snap(f,'proposal/proofs/'+f.name)
put('observed-proof-attempt-status.json',host_proof_attempts)
for row in snapshots:ck('read_stability:'+row['snapshot'],sha(Path(row['path']).read_bytes())==row['sha256'])
put('checks.json',checks);put('snapshot-manifest.json',{'format':'independent-audit-snapshots/1','entries':snapshots})
notes=[{'scope':'Source mathematical potential','observation':'Manual full source inspection finds bucket_count/starts, all-event sorted unique groups, original-occurrence event folds, exact clipped intervals, null option matching, count/sum, let-bound state, causal zero-preserving previous and output order equivalent to accepted helpers. All logged helper binders point to the intended parameter/accumulator/event/payload. This is a bounded source correspondence judgment, not a universal proof.'},{'scope':'Exact adapters/raw input universe','observation':'Goal constructs scalar/list/option adapters and canonical Event/Input/Output products with both typed inverse laws; raw laws use exact RecordLayout. InputsCover quantifies all ArgsTyped and derives encode-after-decode; RawEval binds actual compiled evaluator output through result inverse. No arbitrary malformed Shape or input magnitude/size guard is introduced.'},{'scope':'Observation/effects','observation':'Goal retains SourceFactsAdequate tied exact compile and entry find plus parameter/result RawLaws, typedCoverage/typedTotal, deterministic, unchanged arguments, no externalIO/floatingPoint, pure data and normative evaluator identity, emptyEffectTrace. The mapped fact flags are accompanied by this kernel adequacy interface; they are not candidate metadata authority.'},{'scope':'Transfer','observation':'All nine original implementation guarantees are present. O1-O7 transfers contain the complete accepted forall/guard/RHS with only solve global constant replaced under every binder. I1/S1 remain exact approved operational requirements. Refines is unguarded universal equality for all typed Input, stronger than requested valid-input value restriction.'},{'scope':'Pending proof/materialization','observation':'Current proof module requests exact EdgeProp and has no textual admissions, but has not been independently replayed in this audit. Host check marker explicitly distinguishes proof_checked. Actual materialization/certificate and native acceptance remain separate subsequent evidence.'}]
put('scope-observations.json',notes)
audit={'schema_version':'independent-source-proposal-audit/1','phase':'Stage011 D21 source-2 and proposed bridge goal/proof1','source_root':'sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a','source_sha256':sha(source),'goal_sha256':sha(goal.encode()),'accepted_ir_sha256':sha((PKG/'accepted/accepted-ir.json').read_bytes()),'result':'NO_CONCRETE_PROPOSAL_SCOPE_DEFECT_FOUND_IN_BOUNDED_INSPECTION','checks':len(checks),'passed_checks':sum(x['pass'] for x in checks),'snapshots':len(snapshots),'source_var_occurrences':len(occ),'source_binders':len(binders),'host_check_marker':check,'observed_host_proof_attempts':host_proof_attempts,'availability_observed_only':{'materialized_implementation_exists':(PKG/'implementation').exists(),'materialized_bridge_exists':(PKG/'bridges/implementation').exists(),'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},'claim_limit':'Proposed source/goal correspondence only. Proof and source operational/refinement/raw adequacy acceptance are not claimed; no mechanical closure/release/terminal assertion. This pending receipt is an immutable snapshot to be followed by a separate accepted-materialization annex.','forbidden_actions_not_performed':['native/kernel/closure/gate execution','model/provider calls','author/controller/reviewer communication','package/cohort/project/production edits','historical task solutions/proofs/hidden cases']}
put('audit.json',audit);print(json.dumps(audit,indent=2))
