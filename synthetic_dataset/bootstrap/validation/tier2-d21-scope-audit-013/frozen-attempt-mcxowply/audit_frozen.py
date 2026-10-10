#!/usr/bin/env python3
"""Fresh013 frozen mathematical scope audit; no candidate/task evaluation or kernel calls."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,hashlib,re
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-013';RUN=STAGE/'run';PROJECT=STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';CH=PKG/'contract/challenge';OUT=Path(__file__).resolve().parent
checks={};snaps={};observed={}
def h(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def d(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def check(k,b,detail=None):
 checks[k]={'ok':bool(b)}
 if detail is not None:checks[k]['detail']=detail
def capture(p,label):
 p=Path(p);check('regular:'+label,p.is_file() and not p.is_symlink());b=p.read_bytes();q=OUT/'snapshots'/label;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);snaps[label]={'source':str(p),'sha256':h(b),'bytes':len(b)};observed[str(p)]=h(b);return b
def js(p,label):return json.loads(capture(p,label))
protocol=js(RUN/'protocol.json','protocol.json');prereg=js(RUN/'preregistration.json','preregistration.json');check('protocol_prereg',prereg['protocol_sha256']==h((RUN/'protocol.json').read_bytes()) and protocol['source_root']==prereg['source_root']==h(d(protocol['source_files'])))
for f,sha in protocol['source_files'].items():check('frozen_source:'+f,h(capture(PROJECT/f,'project/'+f))==sha)
for f,sha in protocol['input_files'].items():check('frozen_input:'+f,h(capture(RUN/f,'prepared/'+f))==sha)
challenge=js(CH/'challenge.json','package/challenge.json');check('frozen_challenge_root',challenge['contract_input_root']==h(d(challenge['manifest']))=='sha256:006fd3741f22e86fa270f02450653297b77a0346acac6e8dc094182737f64d3c')
for row in challenge['manifest']['entries']:
 b=capture(PKG/row['path'],'package/'+row['path']);check('challenge_member:'+row['path'],h(b)==row['sha256'] and len(b)==row['size'])
claims=json.loads((PKG/'claims.json').read_bytes());records={r['id']:r for r in claims['obligations']};statements=json.loads((CH/'statements.json').read_bytes());profile_json=json.loads((CH/'profile.json').read_bytes());form=json.loads((CH/'formalization.json').read_bytes());policy=json.loads((RUN/'requests/D21/source-policy.json').read_bytes());metadata=json.loads((RUN/'requests/D21/original-metadata.json').read_bytes());lean=(CH/'Contract.lean').read_text()
check('all_original_plus_witness',set(records)==set(statements['statements'])=={r['id'] for r in metadata['identities']}|{'valid_domain_witness'} and len(records)==12)
for ident in metadata['identities']:
 r=records[ident['id']];check('original_identity:'+ident['id'],all(ident[k]==r[k] for k in ['id','role','kind','required']))
sys.path.insert(0,str(PROJECT))
from verislop import contract as C,dsl,source_policy,leanbridge,lifecycle
from verislop.package import Package
with patch.object(leanbridge,'run_kernel_tool',side_effect=AssertionError('kernel forbidden')),patch.object(leanbridge,'compile_module',side_effect=AssertionError('compilation forbidden')):
 frozen,diags=C.load_frozen(Package(PKG));check('registered_pure_frozen_authentication',not diags and frozen['contract_input_root']==challenge['contract_input_root'],[x.to_json() for x in diags])
 pd=source_policy.check(policy,statements['statements'],records.values());check('registered_policy_exact',not pd,[x.to_json() for x in pd])
 profile=dsl.Profile.from_json(profile_json)
 formulas={}
 for k,st in statements['statements'].items():
  check('statement_record_identity:'+k,all(st[z]==records[k][z] for z in ['id','revision','role','kind']))
  check('statement_closure_hash:'+k,st['semantic_closure_hash']==h(d({'toolchain':challenge['toolchain']['pin'],'declarations':st['semantic_closure']})))
  for name,sha in st['semantic_closure'].items():check('frozen_decl:'+k+':'+name,statements['declaration_hashes'].get(name)==sha)
  pack=st.get('formula_package')
  if pack and pack.get('encoding')=='verislop.source-contract-facets/0.1':
   facets=pack['source'];check('canonical_source:'+k,len(facets)==1 and facets[0]['symbol']=='solve' and facets[0]['lean_decl']=='VeriSlopAST.solve' and facets[0]['requirements'][0]=={'tag':'entry','file':'program.vscore.json','entry':'solve','arity':1} and [r['tag'] for r in facets[0]['requirements'][1:]]==policy['obligations'][k]['properties'])
   value=pack.get('value');check('only_I1_S1_source_only:'+k,(value is None)==(k in {'I1','S1'}))
   if value:
    formulas[k]=value['formula'];dsl.type_formula(formulas[k],[],profile);check('full_value_projection:'+k,pack['value_projection']['projection']=='left' and pack['value_projection']['lean_symbol']=='VeriSlopAST._vs_value_complete_behavior' and pack['value_projection']['source_theorem']==st['lean_symbol']=='VeriSlopAST.complete_behavior')
  if k in {'I1','S1'}:check('source_only_no_ref_body_equality:'+k,st['lean_symbol']=='VeriSlopAST.source_behavior')
  if k.startswith('O'):check('value_binds_A1:'+k,st['hypotheses']==['A1'] and records[k]['required'] is True)
 f=formulas['O1'];check('whole_universal_shared',set(formulas)=={'O1','O2','O3','O4','O5','O6','O7'} and all(x==f for x in formulas.values()) and f['tag']=='forall' and f['sort']=={'record':'Input'} and f['body']['tag']=='implies')
 V=lambda n:{'tag':'var','index':n}
 I=lambda n:{'tag':'int','value':str(n)}
 N=lambda n:{'tag':'nat','value':str(n)}
 S=lambda s:{'tag':'string','value':s}
 F=lambda sort,field,n:{'tag':'field','sort':sort,'field':field,'value':V(n)}
 B=lambda tag,l,r:{'tag':tag,'left':l,'right':r}
 U=lambda tag,v:{'tag':tag,'value':v}
 Some=lambda v:U('some',v)
 NoneInt={'tag':'none','element_sort':'Int'}
 L=lambda sort,items:{'tag':'list','element_sort':sort,'items':items}
 R=lambda sort,fields:{'tag':'record','sort':sort,'fields':fields}
 D=lambda formula:{'tag':'decide','formula':formula}
 If=lambda c,t,e:{'tag':'ite','condition':c,'then':t,'else':e}
 guard=B('and',B('lt',I(0),F('Input','width',0)),B('and',B('le',F('Input','start',0),F('Input','end',0)),B('or',B('eq',F('Input','fill',0),S('none')),B('eq',F('Input','fill',0),S('previous')))))
 check('exact_unbounded_guard',f['body']['left']==guard)
 eq=f['body']['right'];check('reference_separate_from_solve',eq['tag']=='eq' and eq['left']=={'tag':'call','symbol':'solve','args':[V(0)]})
 rhs=eq['right'];check('groups_fold',rhs['tag']=='list_foldl' and rhs['function']['element_sort']=='String' and rhs['initial']==L({'record':'Bucket'},[]) and rhs['function']['body']['tag']=='list_append' and rhs['function']['body']['left']==V(1))
 expected_groups={'tag':'list_sort','value':{'tag':'list_unique','value':{'tag':'list_map','value':F('Input','events',0),'function':{'sort':{'record':'Event'},'body':F('Event','group',0)}}}}
 check('all_event_groups_scalar_sort',rhs['value']==expected_groups)
 outer=rhs['function']['body']['right'];check('outer_group_rows',outer['tag']=='field' and outer['sort']=='Scan' and outer['field']=='rows')
 buckets=outer['value'];count=U('int_to_nat',B('int_fdiv',B('int_sub',B('int_add',B('int_sub',F('Input','end',2),F('Input','start',2)),F('Input','width',2)),I(1)),F('Input','width',2)))
 check('exact_ceiling_bucket_count',buckets['tag']=='list_foldl' and buckets['function']['element_sort']=='Nat' and buckets['value']=={'tag':'list_range','stop':count} and buckets['initial']==R('Scan',[NoneInt,L({'record':'Bucket'},[])]))
 singleton=buckets['function']['body'];check('singleton_aggregate_scan',singleton['tag']=='list_foldl' and singleton['function']['element_sort']=={'record':'Bucket'} and singleton['initial']==V(1) and singleton['value']['tag']=='list' and len(singleton['value']['items'])==1)
 agg=singleton['value']['items'][0];bstart=B('int_add',F('Input','start',4),B('int_mul',U('nat_to_int',V(0)),F('Input','width',4)))
 check('aggregate_empty_initial',agg['tag']=='list_foldl' and agg['value']==F('Input','events',4) and agg['initial']==R('Bucket',[V(2),bstart,N(0),Some(I(0))]))
 include=B('bool_and',D(B('eq',F('Event','group',0),V(4))),B('bool_and',U('option_is_some',F('Event','value',0)),D(B('and',B('le',F('Bucket','start',1),F('Event','time',0)),B('and',B('lt',F('Event','time',0),B('int_add',F('Bucket','start',1),F('Input','width',6))),B('lt',F('Event','time',0),F('Input','end',6)))))))
 get=lambda sort,field,n:{'tag':'option_get_or','value':F(sort,field,n),'default':I(0)}
 nextagg=R('Bucket',[F('Bucket','group',1),F('Bucket','start',1),B('add',F('Bucket','count',1),N(1)),Some(B('int_add',get('Bucket','value',1),get('Event','value',0)))])
 check('full_half_open_null_duplicate_sum',agg['function']['body']==If(include,nextagg,V(1)))
 nonempty=D(B('lt',N(0),F('Bucket','count',0)));prev=If(nonempty,F('Bucket','value',0),F('Scan','previous',1));out=R('Bucket',[F('Bucket','group',0),F('Bucket','start',0),F('Bucket','count',0),If(nonempty,F('Bucket','value',0),If(D(B('eq',F('Input','fill',6),S('previous'))),F('Scan','previous',1),NoneInt))])
 scan=R('Scan',[prev,B('list_append',F('Scan','rows',1),L({'record':'Bucket'},[out]))]);check('count_based_previous_empty_carry',singleton['function']['body']==scan)
 # Symbolic de Bruijn annotation for the entire reference; no execution of a task input.
 annotations=[]
 def walk(x,ctx,path):
  if isinstance(x,dict):
   if x.get('tag')=='var':check('debruijn:'+path,0<=x['index']<len(ctx));annotations.append({'path':path,'index':x['index'],'context':ctx,'binder':ctx[x['index']]});return
   tag=x.get('tag')
   if tag in {'forall','exists'}:walk(x['body'],['input']+ctx,path+'/body');return
   if tag=='list_foldl':
    walk(x['value'],ctx,path+'/value');walk(x['initial'],ctx,path+'/initial');walk(x['function']['body'],['item','acc']+ctx,path+'/function/body');return
   if tag in {'list_map','list_filter'}:walk(x['value'],ctx,path+'/value');walk(x['function']['body'],['item']+ctx,path+'/function/body');return
   for k,v in x.items():walk(v,ctx,path+'/'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):walk(v,ctx,path+'/'+str(i))
 walk(f,[],'formula')
 calls=[]
 def findcalls(x):
  if isinstance(x,dict):
   if x.get('tag')=='call':calls.append(x['symbol'])
   for v in x.values():findcalls(v)
  elif isinstance(x,list):
   for v in x:findcalls(v)
 findcalls(rhs);check('no_tautological_reference_selfcall',calls==[])
 check('exact_layout_no_added_fields',[(f['name'],f['sort']) for f in profile_json['records']['Bucket']['fields']]==[('group','String'),('start','Int'),('count','Nat'),('value',{'option':'Int'})] and [(f['name'],f['sort']) for f in profile_json['records']['Input']['fields']]==[('events',{'list':{'record':'Event'}}),('start','Int'),('end','Int'),('width','Int'),('fill','String')])
 witness=records['valid_domain_witness'];w=form['internal_obligations'];check('derived_witness_same_assumption',w==[{'description':"An input with events=[], start=0, end=0, width=1 and fill='none' satisfies valid_input.",'id':'valid_domain_witness','kind':'non_vacuity','theorem':'VeriSlopAST.valid_input_inhabited','witnesses_for':['A1']}] and witness['kind']=='non_vacuity' and witness['required'] and lifecycle.applicability(witness)['END_TO_END_VERIFIED'][0] is False)
 check('constructive_witness_full_guard_statement','theorem «valid_input_inhabited» : (∃ («_v0» : _root_.VeriSlopAST.«Input»), (_root_.VeriSlopAST.«valid_input» «_v0»))' in lean)
 check('no_axiom_declarations',not re.search(r'^\s*axiom\b',lean,re.M) and 'native_decide' not in lean)
 check('frozen_proof_holes_honest',len(re.findall(r'\bsorry\b',lean))==3)
 sc=(PROJECT/'verislop/lean/SourceBoundary.lean').read_text().replace('import Std\n','',1).strip();check('exact_registered_SourceBoundary',sc in lean)
 # Stored finalized formalization checks are observations only, not accepted proof authority.
 checkreport=js(PKG/'contract/candidate/statement-check.json','package/finalized-statement-check.json');check('stored_compile_defeq_observations',checkreport['compile']['ok'] and checkreport['diagnostics']==[] and len(checkreport['defeq'])==17 and all(r['result']=={'defeq':True,'ok':True,'typechecks':True} for r in checkreport['defeq']) and checkreport['critique']['status']=='SEARCH_COMPLETED' and checkreport['critique']['diagnostics']==[])
 for r in checkreport['frontend_defeq']:check('stored_frontend_defeq:'+r['id'],r['result']=={'defeq':True,'ok':True,'typechecks':True})
 (OUT/'reference-value-package.json').write_bytes(d(statements['statements']['O1']['formula_package']));(OUT/'exact-guard.json').write_bytes(d(guard));(OUT/'binder-annotations.json').write_bytes(d(annotations))
 for p,sha in observed.items():check('unchanged:'+p,h(Path(p).read_bytes())==sha)
 availability={'accepted_ir':(PKG/'accepted/accepted-ir.json').exists(),'source_materialized':(PKG/'implementation').exists(),'semantic_bridge':(PKG/'semantic').exists(),'closure':(PKG/'closure/current.json').exists()}
 fail=[k for k,v in checks.items() if not v['ok']];audit={'format':'independent-bounded-audit/0.1','phase':'frozen-mathematical-scope','stage':'013','task':'D21','time':datetime.now(timezone.utc).isoformat(),'source_root':protocol['source_root'],'frozen_challenge_root':challenge['contract_input_root'],'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not fail else 'AUDIT_ASSERTION_FAILURE','checks':len(checks),'failed_checks':fail,'snapshots':len(snaps),'availability_only':availability,'observations':['All original eleven identities and a separately derived required non-vacuity witness remain bound to the frozen challenge.','O1-O7 each retain the complete universal reference over exact width>0/start<=end/fill-mode guard; no extra bounds or RHS solve alias.','Deep fold binders exactly select input, group, bucket, event, aggregate and scan state.','All groups, clipped half-open buckets, null exclusion, duplicate occurrence counting, signed sums, zero previous, empty carry and group/bucket order remain explicit.','Ceiling count is (delta+width-1) fdiv width, then Int.toNat: with delta>=0,width>=1 it equals ceil(delta/width), gives zero for empty intervals, and yields exactly starts below end.','All nine canonical source-policy facets are present; only I1/S1 lack value formulas.'],'limits':['Frozen challenge contains three honest proof placeholders; this phase does not certify their replacement.','Stored compile/defeq/critic records are retained observations and not implementation evidence.','No source implementation, native/kernel/model/mechanical replay or task evaluation.','Public examples are preserved and covered by the universal reference; no example-only correctness claim.','Natural-language correspondence remains the explicit trusted audit boundary.']}
 (OUT/'checks.json').write_bytes(d(checks));(OUT/'snapshots.json').write_bytes(d(snaps));(OUT/'audit.json').write_bytes(d(audit));print(json.dumps(audit,indent=2));assert not fail,fail
