#!/usr/bin/env python3
"""Fresh013 retained source and generated universal bridge goal, not proof acceptance."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from unittest.mock import patch
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-013';RUN=STAGE/'run';PROJECT=STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';S=PKG/'agents/vscore-attempts/source-3';OUT=Path(__file__).resolve().parent
checks={};snaps={};observed={}
def h(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def d(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def check(k,b,detail=None):
 checks[k]={'ok':bool(b)}
 if detail is not None:checks[k]['detail']=detail
def capture(p,label):
 p=Path(p);check('regular:'+label,p.is_file() and not p.is_symlink());b=p.read_bytes();q=OUT/'snapshots'/label;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);snaps[label]={'source':str(p),'sha256':h(b),'bytes':len(b)};observed[str(p)]=h(b);return b
def js(p,label):return json.loads(capture(p,label))
availability_start={n:(PKG/n).exists() for n in ['implementation','bridges','semantic','closure/current.json']}
protocol=js(RUN/'protocol.json','protocol.json');prereg=js(RUN/'preregistration.json','preregistration.json');check('source_protocol_authentication',protocol['source_root']==prereg['source_root']==h(d(protocol['source_files']))=='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710' and prereg['protocol_sha256']==h((RUN/'protocol.json').read_bytes()))
for f,sha in protocol['source_files'].items():check('frozen_source:'+f,h(capture(PROJECT/f,'project/'+f))==sha)
for f,sha in protocol['input_files'].items():check('prepared_input:'+f,h(capture(RUN/f,'prepared/'+f))==sha)
ir=js(PKG/'accepted/accepted-ir.json','package/accepted-ir.json');cert=js(PKG/'accepted/acceptance.json','package/acceptance.json');profile=js(PKG/cert['artifacts']['profile']['path'],'package/accepted-profile.json');capture(PKG/cert['artifacts']['source']['path'],'package/accepted-reference.lean')
for name in ['program.vscore.json','relation.json','model.json','profile.json','VeriSlopBridgeGoal.lean','checks/source.json','response.txt']:capture(S/name,'source-3/'+name)
source=(S/'program.vscore.json').read_bytes();relation_bytes=(S/'relation.json').read_bytes();goal=(S/'VeriSlopBridgeGoal.lean').read_text();preview=json.loads((S/'checks/source.json').read_bytes());check('retained_native_preview_admission',preview['passed'] is True and preview['proof_checked'] is False and preview['proof_hash'] is None and preview['source_hash']==h(source) and preview['relation_hash']==h(relation_bytes))
sys.path.insert(0,str(PROJECT))
from verislop import export,leanbridge,lifecycle,canonical
from verislop.package import Package
from verislop.targets import vscore3_target as T
from verislop.bridges.vscore3_checker import _obligation_from_package
with patch.object(leanbridge,'run_kernel_tool',side_effect=AssertionError('kernel forbidden')),patch.object(leanbridge,'compile_module',side_effect=AssertionError('compilation forbidden')):
 vi,ih,vc,diags=export.verified_ir(Package(PKG));check('pure_current_accepted_IR',not diags and vi==ir and vc==cert and ih==h((PKG/'accepted/accepted-ir.json').read_bytes()),[x.to_json() for x in diags])
 applicable=sorted(k for k,r in ir['obligations'].items() if r['required'] and r['role']=='guarantee' and lifecycle.applicability(r)['END_TO_END_VERIFIED'][0]);check('exact_nine_transfer_ids',applicable==['I1','O1','O2','O3','O4','O5','O6','O7','S1'])
 packages={};obs={}
 for k,r in ir['obligations'].items():
  sha=r['formal']['formula_ref'].rsplit('@',1)[1];p=PKG/'accepted/expressions'/f'{sha[7:]}.json';packages[k]=js(p,'package/accepted-expressions/'+k+'.json');check('exact_formula_hash:'+k,h(p.read_bytes())==sha)
  if k in applicable:obs[k]=_obligation_from_package(k,r,packages[k],profile)
 relation=T.load_relation(relation_bytes);spec=T.build_goal(source,relation,profile,obs)
 check('exact_native_renderer_reconstruction',spec.text==goal)
 check('one_canonical_bound_endpoint',relation['bindings']==[{'symbol':'solve','entry':'solve'}] and relation['source_slot']=='vscore-source' and relation['proof_slot']=='vscore-proof' and relation['template']=='vscore.reference_refinement/0.3')
 check('exact_native_model_descriptor',(S/'model.json').read_bytes()==canonical.dumps(T.model_descriptor(cert['toolchain']['pin'])))
 check('exact_native_representation_profile',(S/'profile.json').read_bytes()==canonical.dumps(T.profile_descriptor(profile,cert['artifacts']['profile']['sha256'])))
 check('full_typed_domain_refinement',spec.refinement_symbols=={'solve'} and 'def Refines_solve : Prop := (∀ (x__0 : @VeriSlopAST.Input),' in goal and '@VeriSlopBridgeGoal.source_fn_solve x__0) (@VeriSlopAST.solve x__0)' in goal)
 check('actual_compiled_run_not_ref_alias','entry_solve.run (adapter_5.to x__0, ())' in goal and 'VSCore3.findEntry checkedProgram "solve"' in goal and 'VSCore3.compileProgram profile rawProgram' in goal)
 check('raw_coverage_all_ArgsTyped','∀ args, VSCore3.ArgsTyped entry_solve args → ∃ (x__0 : @VeriSlopAST.Input), args = [adapter_5.encode x__0]' in goal and 'VSCore3.encodeEnv_decodeEnv' in goal and 'adapter_5.to_from' in goal)
 check('raw_evaluator_result_encode','VSCore3.evalEntry profile rawProgram "solve" [adapter_5.encode x__0]' in goal and '.ok (adapter_8.encode (source_fn_solve x__0))' in goal and 'rw [adapter_8.to_from]' in goal)
 check('nine_exact_adapters',len(spec.adapters)==9 and all('adapter_'+str(i)+'_decode_encode' in goal for i in range(9)) and goal.count('from_to :=')==3 and goal.count('to_from :=')==3)
 check('canonical_record_and_aggregate_raw_laws',all(x in goal for x in ['VSCore3.RecordLayout.cons','VSCore3.recordRawLaws','VSCore3.listRawLaws','VSCore3.optionRawLaws','VSCore3.intRawLaws','VSCore3.stringRawLaws']) and '.record "Input" ["events", "start", "end", "width", "fill"]' in goal and '.record "Bucket" ["group", "start", "count", "value"]' in goal)
 check('compiler_bound_source_adequacy','VSCore3.SourceFactsAdequate profile rawProgram "solve" checkedProgram entry_solve' in goal and 'VSCore3.exactSourceFacts_adequate compiled_ok find_solve' in goal)
 for k,o in obs.items():
  check('same_accepted_statement:'+k,o['statement_hash']==ir['obligations'][k]['formal']['statement_hash'] and o['lean_symbol']==ir['obligations'][k]['formal']['lean_symbol'])
  check('source_endpoint_properties:'+k,o['source_facets']==obs['O1']['source_facets'])
  check('mixed_complete_value:'+k,(o['formula'] is None)==(k in {'I1','S1'}) and (k in {'I1','S1'} or o['formula']==obs['O1']['formula']))
  check('native_transfer_definition:'+k,'Transfer_'+k in spec.expected and 'def Transfer_'+k+' : Prop :=' in goal)
  if k.startswith('O'):check('functional_transfer_requires_full_refines:'+k,'theorem transfer_'+k+' (h_solve : Refines_solve)' in goal)
 edge=goal.split('def EdgeProp : Prop :=',1)[1].split('theorem edge_of_refines',1)[0];check('closed_whole_edge_conjunction',all(n in edge for n in ['SourceParses','SourceChecks','InputsCover_solve','RawEval_solve','Refines_solve','SourceAdequate_solve']+['Transfer_'+k for k in applicable]))
 # Independent symbolic inspection of the actual current source structure, no evaluation.
 p=json.loads(source);fn={e['id']:e for e in p['helpers']+p['entries']};check('pure_function_inventory',set(fn)=={'getOrZero','isSome','aggregate','scanStep','groupRows','solve'} and len(p['entries'])==1 and p['entries'][0]['id']=='solve')
 V=lambda n:{'tag':'var','index':n};P=lambda name,n:{'tag':'project','field':name,'value':V(n)};I=lambda n:{'tag':'int','value':str(n)};N=lambda n:{'tag':'nat','value':str(n)};B=lambda tag,l,r:{'tag':tag,'left':l,'right':r};U=lambda tag,v:{'tag':tag,'value':v};Call=lambda name,args:{'tag':'call','helper':name,'args':args};Some=lambda v:U('some',v)
 check('option_getOrZero_exact',fn['getOrZero']['body']=={'tag':'match_option','scrutinee':V(0),'none':I(0),'some':V(0)})
 check('option_isSome_exact',fn['isSome']['body']=={'tag':'match_option','scrutinee':V(0),'none':{'tag':'bool','value':False},'some':{'tag':'bool','value':True}})
 solve=fn['solve']['body'];check('solve_all_groups_scalar_sorted',solve['source']=={'tag':'list_sort','value':{'tag':'list_unique','value':{'tag':'list_map','value':P('events',0),'body':P('group',0)}}} and solve['step']==B('list_append',V(1),Call('groupRows',[V(2),V(0)])) and solve['initial']=={'tag':'nil','element_type':{'record':'Bucket'}})
 agg=fn['aggregate']['body'];check('aggregate_fold_all_events',agg['tag']=='list_fold' and agg['source']==P('events',2) and agg['step']['else']==V(1))
 initial={f['id']:f['value'] for f in agg['initial']['fields']};check('aggregate_signed_start_zero_initial',initial=={'group':V(1),'start':B('add',P('start',2),B('mul',U('nat_to_int',V(0)),P('width',2))),'count':N(0),'value':Some(I(0))})
 include=B('and',B('eq',P('group',0),V(3)),B('and',Call('isSome',[P('value',0)]),B('and',B('le',P('start',1),P('time',0)),B('and',B('lt',P('time',0),B('add',P('start',1),P('width',4))),B('lt',P('time',0),P('end',4))))))
 check('exact_half_open_clipping_null_guard',agg['step']['cond']==include)
 af={f['id']:f['value'] for f in agg['step']['then']['fields']};check('duplicate_occurrences_and_signed_sum',af=={'group':P('group',1),'start':P('start',1),'count':B('add',P('count',1),N(1)),'value':Some(B('add',Call('getOrZero',[P('value',1)]),Call('getOrZero',[P('value',0)])))})
 group=fn['groupRows']['body']['value'];count=U('int_to_nat',B('int_fdiv',B('sub',B('add',B('sub',P('end',1),P('start',1)),P('width',1)),I(1)),P('width',1)));check('ceil_range_same_full_domain',group['source']==U('list_range',count))
 gi={f['id']:f['value'] for f in group['initial']['fields']};check('no_prestart_previous_seed',gi=={'previous':{'tag':'none','element_type':'int'},'rows':{'tag':'nil','element_type':{'record':'Bucket'}}})
 check('scan_call_same_order_state',group['step']==Call('scanStep',[V(3),V(1),Call('aggregate',[V(3),V(2),V(0)])]))
 gf={f['id']:f['value'] for f in fn['scanStep']['body']['fields']};prev=gf['previous'];condition=B('lt',N(0),P('count',0));check('zero_previous_and_empty_never_reset',prev=={'tag':'if','cond':condition,'then':P('value',0),'else':P('previous',1)})
 row={f['id']:f['value'] for f in gf['rows']['right']['head']['fields']};check('output_exact_metadata',row['group']==P('group',0) and row['start']==P('start',0) and row['count']==P('count',0))
 check('causal_previous_fill_only',row['value']=={'tag':'if','cond':condition,'then':P('value',0),'else':{'tag':'if','cond':B('eq',P('fill',2),{'tag':'string','value':[112,114,101,118,105,111,117,115]}),'then':P('previous',1),'else':{'tag':'none','element_type':'int'}}})
 check('stable_group_then_bucket_append',gf['rows']['tag']=='list_append' and gf['rows']['left']==P('rows',1) and gf['rows']['right']['tail']=={'tag':'nil','element_type':{'record':'Bucket'}})
 annotations=[]
 def walk(x,ctx,path):
  if not isinstance(x,dict):return
  tag=x.get('tag')
  if tag=='var':check('binder:'+path,0<=x['index']<len(ctx));annotations.append({'path':path,'index':x['index'],'context':ctx,'binder':ctx[x['index']]});return
  if tag=='list_fold':walk(x['source'],ctx,path+'/source');walk(x['initial'],ctx,path+'/initial');walk(x['step'],['item','acc']+ctx,path+'/step');return
  if tag in {'list_map','list_filter'}:walk(x['value'],ctx,path+'/value');walk(x['body'],['item']+ctx,path+'/body');return
  if tag=='match_option':walk(x['scrutinee'],ctx,path+'/scrutinee');walk(x['none'],ctx,path+'/none');walk(x['some'],['someval']+ctx,path+'/some');return
  for key,v in x.items():
   if isinstance(v,dict):walk(v,ctx,path+'/'+key)
   elif isinstance(v,list):
    for i,z in enumerate(v):walk(z,ctx,path+'/'+key+'/'+str(i))
 contexts={'getOrZero':['optional_value'],'isSome':['optional_value'],'aggregate':['bucket_index','group','input'],'scanStep':['bucket','scan','input'],'groupRows':['group','input'],'solve':['input']}
 for name,e in fn.items():walk(e['body'],contexts[name],name)
 (OUT/'binder-annotations.json').write_bytes(d(annotations));(OUT/'reconstructed-goal-statements.json').write_bytes(d(spec.expected));(OUT/'decoded-source-program.json').write_bytes(d(spec.program))
 # Exact immutable proof context and generic catalog, never sent or changed by auditor.
 request=js(RUN/'artifacts/D21/verislop/mailbox/request-0017.json','published-native-request-0017.json');ctx=json.JSONDecoder().raw_decode(request['user'].split('\n',1)[1])[0]
 check('native_pending_prover_role',request['purpose']=='generate' and request['instance']=='prover/vscore/3/1')
 check('exact_context_delivered_source_goal',ctx['source']==p and ctx['source_hash']==h(source) and ctx['relation']==relation and ctx['relation_hash']==h(relation_bytes) and ctx['generated_goal']==goal and ctx['goal_hash']==h(goal.encode()) and ctx['refinement_symbols']==['solve'])
 check('accepted_context_hash_bound',ctx['accepted_reference']['sha256']==cert['artifacts']['source']['sha256'] and ctx['accepted_reference']['path']==cert['artifacts']['source']['path'] and ctx['accepted_reference']['lean_source']==(PKG/cert['artifacts']['source']['path']).read_text() and ctx['accepted_profile']==profile and set(ctx['accepted_packages'])==set(packages) and all(ctx['accepted_packages'][k]=={'revision':ir['obligations'][k]['revision'],'statement_hash':ir['obligations'][k]['formal']['statement_hash'],'formula_ref':ir['obligations'][k]['formal']['formula_ref'],'package':v} for k,v in packages.items()))
 libs=T.library_sources();check('exact_registered_libraries_in_context',set(ctx['verifier_library'])==set(libs) and all(ctx['verifier_library'][k].encode()==v for k,v in libs.items()))
 catalog=T.proof_support_catalog();check('catalog_exact_frozen_source',ctx['proof_support']==catalog and catalog['source_hash']==h((PROJECT/'verislop/lean/VSCore3/Transport.lean').read_bytes()) and catalog['module']=='VSCore3.Transport' and catalog['global_simp_rules'] is False and len(catalog['lemmas'])==6)
 check('catalog_only_closed_universal_lemmas',all(r['signature'].startswith('∀ ') and r['name'].startswith('VSCore3.ProofSupport.') and not any(s in r['signature'] for s in ['D21','Bucket','Event','solve','aggregate','groupRows']) for r in catalog['lemmas']))

 # Published native attempt verdicts are observations, never independently promoted to certified refinement.
 proof_observations=[]
 for pf in sorted((S/'checks').glob('proof-*.json')):
  n=pf.stem.split('-')[1];ck=js(pf,'source-3/checks/'+pf.name);dg=js(S/'diagnostics'/pf.name,'source-3/diagnostics/'+pf.name);pb=capture(S/'proofs'/f'{n}.lean','source-3/proofs/'+n+'.lean');rb=capture(S/'responses'/f'proof-{n}.txt','source-3/responses/'+f'proof-{n}.txt')
  check('proof_attempt_exact_hashes:'+n,ck['source_hash']==dg['source_hash']==h(source) and ck['relation_hash']==dg['relation_hash']==h(relation_bytes) and ck['proof_hash']==dg['proof_hash']==h(pb) and dg['response_artifact']=={'path':f'agents/vscore-attempts/source-3/responses/proof-{n}.txt','sha256':h(rb)})
  check('proof_attempt_matching_verdict:'+n,isinstance(ck['passed'],bool) and ck['proof_checked'] is True and dg['passed']==ck['passed'] and ck['diagnostics']==dg['diagnostics'])
  errors=[];stderr=[]
  for diagnostic in ck['diagnostics']:
   de=diagnostic.get('details',{});check('diagnostic_goal_input_hashes:'+n,de['goal_hash']==h(goal.encode()) and de['module_source_hash']==h(pb) and de['input_hashes']=={'model':h((S/'model.json').read_bytes()),'profile':h((S/'profile.json').read_bytes()),'proof_source':h(pb),'relation':h(relation_bytes),'source':h(source)});errors+=de.get('errors',[]);stderr.append(de.get('stderr',''))
  proof_observations.append({'attempt':n,'passed':ck['passed'],'proof_hash':h(pb),'response_hash':h(rb),'reported_errors':errors,'stderr':stderr,'interpretation':'The stored native preview verdict is observed with bound inputs. No bridge acceptance or causal attribution is inferred from it alone.'})
 (OUT/'published-source3-proof-observations.json').write_bytes(d(proof_observations))

 # Current cohort's previous source2 failed attempts retain their own complete input bindings.
 oldS=PKG/'agents/vscore-attempts/source-2';old_inputs={}
 for nm in ['program.vscore.json','relation.json','model.json','profile.json','VeriSlopBridgeGoal.lean']:
  old_inputs[nm]=capture(oldS/nm,'previous-source2/'+nm)
 previous_proofs=[]
 for pf in sorted((oldS/'checks').glob('proof-*.json')):
  n=pf.stem.split('-')[1];ck=js(pf,'previous-source2/checks/'+pf.name);dg=js(oldS/'diagnostics'/pf.name,'previous-source2/diagnostics/'+pf.name);pb=capture(oldS/'proofs'/f'{n}.lean','previous-source2/proofs/'+n+'.lean');rb=capture(oldS/'responses'/f'proof-{n}.txt','previous-source2/responses/'+f'proof-{n}.txt')
  check('previous_source2_proof_hashes:'+n,ck['source_hash']==dg['source_hash']==h(old_inputs['program.vscore.json']) and ck['relation_hash']==dg['relation_hash']==h(old_inputs['relation.json']) and ck['proof_hash']==dg['proof_hash']==h(pb) and dg['response_artifact']=={'path':f'agents/vscore-attempts/source-2/responses/proof-{n}.txt','sha256':h(rb)})
  check('previous_source2_verdict_bound:'+n,ck['passed'] is False and ck['proof_checked'] is True and dg['passed']==ck['passed'] and ck['diagnostics']==dg['diagnostics'])
  for ix,diagnostic in enumerate(ck['diagnostics']):
   de=diagnostic.get('details',{});check('previous_source2_diagnostic_inputs:'+n+':'+str(ix),de['goal_hash']==h(old_inputs['VeriSlopBridgeGoal.lean']) and de['module_source_hash']==h(pb) and de['input_hashes']=={'model':h(old_inputs['model.json']),'profile':h(old_inputs['profile.json']),'proof_source':h(pb),'relation':h(old_inputs['relation.json']),'source':h(old_inputs['program.vscore.json'])})
  previous_proofs.append({'attempt':n,'native_passed':ck['passed'],'proof_hash':h(pb),'response_hash':h(rb),'diagnostics':ck['diagnostics'],'interpretation':'Recorded native rejection of this current-cohort previous candidate only; no success, causal attribution or conclusion about source3 proof feasibility.'})
 check('three_previous_source2_failed_proofs',len(previous_proofs)==3)
 (OUT/'previous-source2-rejected-proof-observations.json').write_bytes(d(previous_proofs))
 facts=(PROJECT/'verislop/lean/VSCore3/SourceFacts.lean').read_text();check('source_observation_actual_eval_laws',all(t in facts for t in ['⟨evalEntry p prog id args, args, []⟩','parameterRepresentation : ∀ t ∈ e.params, RawLaws t','resultRepresentation : RawLaws e.result','typedCoverage : TypedCoverage e','typedTotal : ∀ args, ArgsTyped e args','emptyEffectTrace : ∀ args']))
for p,sha in observed.items():check('unchanged:'+p,h(Path(p).read_bytes())==sha)
availability_end={n:(PKG/n).exists() for n in ['implementation','bridges','semantic','closure/current.json']};failed=[k for k,v in checks.items() if not v['ok']]
audit={'format':'independent-bounded-audit/0.1','phase':'admitted-source3-and-pending-generated-bridge-goal','stage':'013','task':'D21','time':datetime.now(timezone.utc).isoformat(),'source_root':protocol['source_root'],'source_hash':h(source),'relation_hash':h(relation_bytes),'goal_hash':h(goal.encode()),'accepted_IR_hash':h((PKG/'accepted/accepted-ir.json').read_bytes()),'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failed else 'AUDIT_ASSERTION_FAILURE','checks':len(checks),'failed_checks':failed,'snapshots':len(snaps),'availability_at_start':availability_start,'availability_at_end':availability_end,'observations':['Exact frozen renderer reconstructs the retained generated goal from accepted AST-derived expression packages.','Refines is universal over every typed Input without a domain guard; source_fn runs the compiled source and exact adapter inverse.','All nine complete per-ID value/source transfers, raw input coverage, raw evaluation, representation laws and compiler-bound source adequacy are in EdgeProp.','Current source binders and structural expressions preserve all groups, ceil bucket count, half-open clipped bounds, null/duplicate counting, signed sums, zero previous and empty carry/output order.','The native proof context contains exact frozen modules and the six closed universal proof-support lemmas, with no auditor injection.'],'limits':['Retained preview passed but has proof_checked=false and is authoring feedback, not registered whole-instance refinement evidence.','Published native attempt verdicts are recorded only; no accepted bridge proof or semantic certificate validated in this phase.','No source function or task input executed; no Lean/kernel/native/model/review/closure calls.','No author context or live/frozen artifact modified.','No implementation correctness or lifecycle success claimed.']}
(OUT/'checks.json').write_bytes(d(checks));(OUT/'snapshots.json').write_bytes(d(snaps));(OUT/'audit.json').write_bytes(d(audit));print(json.dumps(audit,indent=2));assert not failed,failed
