#!/usr/bin/env python3
"""Read-only Stage012 retained source/goal inspection; no kernel or task execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,re
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path('/home/augustus/VeriSlop_CLI'); STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-012'
RUN=STAGE/'run'; PROJECT=STAGE/'project'; PKG=RUN/'artifacts/D21/verislop/package'; S=PKG/'agents/vscore-attempts/source-1'; OUT=Path(__file__).resolve().parent
SOURCE_ROOT='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710'
checks={}; snaps={}; observed={}
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def dumps(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def check(k,b,d=None):
 checks[k]={'ok':bool(b)}
 if d is not None:checks[k]['detail']=d
def snap(p,label):
 p=Path(p);check('regular:'+label,p.is_file() and not p.is_symlink());b=p.read_bytes();q=OUT/'snapshots'/label;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);snaps[label]={'source':str(p),'sha256':digest(b),'bytes':len(b)};observed[str(p)]=digest(b);return b
def js(p,label):return json.loads(snap(p,label))
protocol=js(RUN/'protocol.json','protocol.json');check('source_root',protocol['source_root']==SOURCE_ROOT and digest(dumps(protocol['source_files']))==SOURCE_ROOT)
for f,sha in protocol['source_files'].items():check('frozen_project:'+f,digest(snap(PROJECT/f,'project/'+f))==sha)
for f,sha in protocol['input_files'].items():check('input:'+f,digest(snap(RUN/f,'run/'+f))==sha)
ir=js(PKG/'accepted/accepted-ir.json','package/accepted-ir.json');cert=js(PKG/'accepted/acceptance.json','package/acceptance.json');profile=js(PKG/cert['artifacts']['profile']['path'],'package/accepted-profile.json')
check('accepted_pair',ir['acceptance_certificate_ref'].endswith(digest((PKG/'accepted/acceptance.json').read_bytes()).split(':')[1]+'.json') and cert['gate']=='accepted_and_proved')
for f in S.rglob('*'):
 if f.is_file():snap(f,'source-1/'+str(f.relative_to(S)))
source=(S/'program.vscore.json').read_bytes();rel=(S/'relation.json').read_bytes();goal=(S/'VeriSlopBridgeGoal.lean').read_text();report=json.loads((S/'checks/source.json').read_bytes())
check('retained_preview_pass_not_proof',report['passed'] is True and report['proof_checked'] is False and report['proof_hash'] is None and report['source_hash']==digest(source) and report['relation_hash']==digest(rel))
sys.path.insert(0,str(PROJECT))
from verislop import leanbridge,canonical,lifecycle,export
from verislop.targets import vscore3_source as src,vscore3_target as T
from verislop.bridges.vscore3_checker import _obligation_from_package
from verislop.package import Package
with patch.object(leanbridge,'run_kernel_tool',side_effect=AssertionError('kernel forbidden')),patch.object(leanbridge,'compile_module',side_effect=AssertionError('compilation forbidden')):
 validated,ih,cc,diags=export.verified_ir(Package(PKG));check('pure_current_IR',not diags and validated==ir and cc==cert,[d.to_json() for d in diags])
 required=sorted(k for k,r in ir['obligations'].items() if r['required'] and r['role']=='guarantee' and lifecycle.applicability(r)['END_TO_END_VERIFIED'][0])
 check('nine_applicable_ids',required==['I1','O1','O2','O3','O4','O5','O6','O7','S1'])
 obligations={}
 for k in required:
  r=ir['obligations'][k];sha=r['formal']['formula_ref'].rsplit('@',1)[1];pack=js(PKG/'accepted/expressions'/f'{sha[7:]}.json','package/expressions/'+k+'.json');check('accepted_expression_hash:'+k,digest(dumps(pack))==sha);obligations[k]=_obligation_from_package(k,r,pack,profile)
 relation=T.load_relation(rel);spec=T.build_goal(source,relation,profile,obligations)
 check('exact_renderer_goal',spec.text==goal)
 check('exact_model',(S/'model.json').read_bytes()==canonical.dumps(T.model_descriptor(cert['toolchain']['pin'])))
 check('exact_profile',(S/'profile.json').read_bytes()==canonical.dumps(T.profile_descriptor(profile,cert['artifacts']['profile']['sha256'])))
 check('canonical_exact_binding',relation['bindings']==[{'entry':'solve','symbol':'solve'}] and relation['template']=='vscore.reference_refinement/0.3' and relation['source_slot']=='vscore-source' and relation['proof_slot']=='vscore-proof')
 check('full_domain_refinement',spec.refinement_symbols=={'solve'} and 'def Refines_solve : Prop := (∀ (x__0 : @VeriSlopAST.Input),' in goal and 'source_fn_solve x__0) (@VeriSlopAST.solve x__0)' in goal)
 for k,o in obligations.items():
  check('facet_exact_entry:'+k,o['source_facets'][0]['requirements'][0]=={'tag':'entry','file':'program.vscore.json','entry':'solve','arity':1})
  check('mixed_value_presence:'+k,(o['formula'] is not None)==(k not in {'I1','S1'}))
  check('exact_expected_transfer:'+k,'Transfer_'+k in spec.expected and 'def Transfer_'+k+' : Prop :=' in goal)
  if k.startswith('O'):
   check('whole_formula_retained:'+k,o['formula']==obligations['O1']['formula'] and 'theorem transfer_'+k+' (h_solve : Refines_solve)' in goal)
 check('whole_edge_closed',all(n in goal.split('def EdgeProp : Prop :=',1)[1].split('theorem edge_of_refines',1)[0] for n in ['SourceParses','SourceChecks','InputsCover_solve','RawEval_solve','Refines_solve','SourceAdequate_solve']+['Transfer_'+k for k in required]))
 check('compiler_run_not_reference_alias','entry_solve.run (adapter_5.to x__0, ())' in goal and 'VSCore3.findEntry checkedProgram "solve"' in goal and 'VSCore3.compileProgram profile rawProgram' in goal)
 check('actual_raw_eval_and_coverage','VSCore3.evalEntry profile rawProgram "solve" [adapter_5.encode x__0]' in goal and '∀ args, VSCore3.ArgsTyped entry_solve args → ∃ (x__0 : @VeriSlopAST.Input)' in goal and 'VSCore3.encodeEnv_decodeEnv' in goal)
 check('adapter_inverse_and_raw_laws',len(spec.adapters)==9 and all('adapter_'+str(i)+'_decode_encode' in goal for i in range(9)) and goal.count('from_to :=')==3 and goal.count('to_from :=')==3 and all(s in goal for s in ['VSCore3.RecordLayout.cons','VSCore3.recordRawLaws','VSCore3.listRawLaws','VSCore3.optionRawLaws']))
 check('source_adequacy_not_flags_alone','VSCore3.SourceFactsAdequate profile rawProgram "solve" checkedProgram entry_solve' in goal and 'VSCore3.exactSourceFacts_adequate compiled_ok find_solve' in goal)
 p=json.loads(source);functions={x['id']:x for x in p['helpers']+p['entries']}
 check('function_inventory',set(functions)=={'buckets','stats','group_rows','groups','solve'} and len(p['entries'])==1 and p['entries'][0]['id']=='solve')
 # Symbolic binder inventory only: never evaluate a task input or candidate function.
 annotations=[]
 def walk(x,ctx,path):
  if not isinstance(x,dict):return
  tag=x.get('tag')
  if tag=='var':check('binder:'+path,0<=x['index']<len(ctx));annotations.append({'path':path,'index':x['index'],'binder':ctx[x['index']],'context':ctx});return
  if tag=='list_fold':
   walk(x['source'],ctx,path+'/source');walk(x['initial'],ctx,path+'/initial');walk(x['step'],['item','acc']+ctx,path+'/step');return
  if tag in {'list_map','list_filter'}:walk(x['value'],ctx,path+'/value');walk(x['body'],['item']+ctx,path+'/body');return
  if tag=='let':walk(x['value'],ctx,path+'/value');walk(x['body'],['letval']+ctx,path+'/body');return
  if tag=='match_option':walk(x['scrutinee'],ctx,path+'/scrutinee');walk(x['none'],ctx,path+'/none');walk(x['some'],['someval']+ctx,path+'/some');return
  for k,v in x.items():
   if isinstance(v,dict):walk(v,ctx,path+'/'+k)
   elif isinstance(v,list):
    for i,z in enumerate(v):walk(z,ctx,path+'/'+k+'/'+str(i))
 contexts={'buckets':['input'],'groups':['input'],'stats':['bucket','group','input'],'group_rows':['group','input'],'solve':['input']}
 for k,f in functions.items():walk(f['body'],contexts[k],k)
 (OUT/'binder-annotations.json').write_bytes(dumps(annotations))
 g=functions['groups']['body'];check('all_groups_scalar_sort',g['tag']=='list_sort' and g['value']['tag']=='list_unique' and g['value']['value']['tag']=='list_map' and g['value']['value']['value']=={'field':'events','tag':'project','value':{'index':0,'tag':'var'}})
 b=functions['buckets']['body'];check('bucket_range_signed_empty',b['tag']=='list_filter' and b['value']['tag']=='list_map' and b['value']['value']['tag']=='list_range' and b['value']['value']['value']['tag']=='int_to_nat' and b['body']=={'left':{'index':0,'tag':'var'},'right':{'field':'end','tag':'project','value':{'index':1,'tag':'var'}},'tag':'lt'})
 st=functions['stats']['body'];check('stats_all_occurrences_fold',st['tag']=='list_fold' and st['source']=={'field':'events','tag':'project','value':{'index':2,'tag':'var'}} and st['step']['else']=={'index':1,'tag':'var'} and st['step']['cond']['left']['tag']=='match_option')
 gr=functions['group_rows']['body']['value'];step=gr['step'];check('stats_call_exact_context',step['tag']=='let' and step['value']=={'args':[{'index':3,'tag':'var'},{'index':2,'tag':'var'},{'index':0,'tag':'var'}],'helper':'stats','tag':'call'})
 fields={f['id']:f['value'] for f in step['body']['fields']};prev=fields['previous'];row={f['id']:f['value'] for f in fields['rows']['right']['head']['fields']}
 check('previous_updates_on_count_not_sum',prev['cond']=={'left':{'tag':'nat','value':'0'},'right':{'field':'count','tag':'project','value':{'index':0,'tag':'var'}},'tag':'lt'} and prev['then']=={'tag':'some','value':{'field':'sum','tag':'project','value':{'index':0,'tag':'var'}}} and prev['else']=={'field':'previous','tag':'project','value':{'index':2,'tag':'var'}})
 check('row_group_bucket_context',row['group']=={'index':3,'tag':'var'} and row['start']=={'index':1,'tag':'var'} and row['value']['cond']==prev['cond'] and row['value']['then']==prev['then'] and row['value']['else']['then']==prev['else'])
 check('group_then_bucket_append',functions['solve']['body']['step']=={'left':{'index':1,'tag':'var'},'right':{'args':[{'index':2,'tag':'var'},{'index':0,'tag':'var'}],'helper':'group_rows','tag':'call'},'tag':'list_append'} and fields['rows']['left']=={'field':'rows','tag':'project','value':{'index':2,'tag':'var'}})
 (OUT/'reconstructed-expected-statements.json').write_bytes(dumps(spec.expected))
 (OUT/'source-program-decoded.json').write_bytes(dumps(spec.program))
facts=(PROJECT/'verislop/lean/VSCore3/SourceFacts.lean').read_text();check('facts_actual_observation_and_totality',all(t in facts for t in ['⟨evalEntry p prog id args, args, []⟩','typedCoverage : TypedCoverage e','parameterRepresentation : ∀ t ∈ e.params, RawLaws t','resultRepresentation : RawLaws e.result','emptyEffectTrace : ∀ args','typedTotal : ∀ args, ArgsTyped e args']))
check('no_materialized_or_semantic_certificate',not (PKG/'implementation').exists() and not (PKG/'bridges').exists() and not (PKG/'semantic').exists() and not (S/'checks/proof-1.json').exists())
check('submitted_proof_not_accepted',(S/'proofs/1.lean').is_file() and (S/'responses/proof-1.txt').is_file())
for p,sha in observed.items():check('unchanged:'+p,digest(Path(p).read_bytes())==sha)
failed=[k for k,v in checks.items() if not v['ok']]
result={'format':'independent-bounded-audit/0.1','phase':'retained-source-and-unaccepted-bridge-goal','task':'D21','stage':'012','source_root':SOURCE_ROOT,'time':datetime.now(timezone.utc).isoformat(),'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failed else 'AUDIT_ASSERTION_FAILURE','checks':len(checks),'failed_checks':failed,'snapshots':len(snaps),'semantic_bridge_status':'NOT_ACCEPTED_CONTROLLER_INTERRUPTED','claims':['Exact frozen renderer reconstructs the retained goal from accepted AST-derived expression packages.','Universal Refines covers every typed Input without an additional guard.','Raw coverage, inverse laws, admitted-entry source adequacy and all nine complete transfers occur in the goal.','Source binding inspection preserves groups, signed bucket construction, null/duplicate handling, count-based previous state and output order.'],'limits':['No candidate function executed.','No Lean/native/kernel/model calls.','Preview check is retained authoring feedback, not registered refinement evidence.','Submitted candidate proof was not validated before interruption.','No implementation correctness or lifecycle success claimed.']}
(OUT/'checks.json').write_bytes(dumps(checks));(OUT/'snapshot-manifest.json').write_bytes(dumps(snaps));(OUT/'audit.json').write_bytes(dumps(result));print(json.dumps(result,indent=2));assert not failed,failed
