"""Independent frozen-challenge scope inspection; no kernel/native/model execution."""
from pathlib import Path
import json, hashlib, sys, re, os, datetime
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-011'
PROJECT=STAGE/'project'
RUN=STAGE/'run'
PKG=RUN/'artifacts/D21/verislop/package'
CH=PKG/'contract/challenge'
OUT=Path(__file__).parent
sys.path.insert(0,str(PROJECT))
from verislop import dsl, source_policy, fsutil
assert Path(dsl.__file__).resolve().is_relative_to(PROJECT)
checks=[]
def sha(b): return 'sha256:'+hashlib.sha256(b).hexdigest()
def put(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def ck(name,ok,detail=None):
 checks.append({'name':name,'pass':bool(ok),'detail':detail})
 if not ok: raise AssertionError(name)
snapshots=[]
def snap(path,label):
 b=path.read_bytes(); dst=OUT/'snapshots'/label; dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
 snapshots.append({'path':str(path),'snapshot':'snapshots/'+label,'sha256':sha(b),'size':len(b)})
 return b
cohort_names=['protocol.json','preregistration.json','config.json','engineering-validation.json']
for f in cohort_names: snap(RUN/f,'cohort/'+f)
for p in sorted((RUN/'requests/D21').iterdir()):
 if p.is_file(): snap(p,'cohort/requests/D21/'+p.name)
for p in sorted(CH.iterdir()):
 if p.is_file(): snap(p,'package/contract/challenge/'+p.name)
for f in ['claims.json','draft.json','interpretation.json','package.json','request/request.json','request/prompt.txt','request/source-policy.json']:
 snap(PKG/f,'package/'+f)
for f in ['verislop/dsl.py','verislop/source_policy.py','verislop/source_contract.py','verislop/fsutil.py','verislop/canonical.py','docs/bootstrap-tier2-interpretation-scope.md','docs/bootstrap-tier2-source-facets.md']:
 snap(PROJECT/f,'generic/'+f)
TC=Path('/home/augustus/.elan/toolchains/leanprover--lean4---v4.34.1/src/lean')
for f in ['Init/Data/String/Basic.lean','Init/Data/Char/Basic.lean','Init/Data/Char/Lemmas.lean','Init/Data/List/Lex.lean','Init/Data/Int/DivMod/Basic.lean']:
 snap(TC/f,'pinned-toolchain/'+f)
def load(label): return json.loads((OUT/'snapshots'/label).read_text())
challenge=load('package/contract/challenge/challenge.json')
formalization=load('package/contract/challenge/formalization.json')
claims=load('package/claims.json'); records=claims['obligations']; by_id={r['id']:r for r in records}
statements=load('package/contract/challenge/statements.json')['statements']
profile_json=load('package/contract/challenge/profile.json'); profile=dsl.Profile.from_json(profile_json)
policy=load('package/request/source-policy.json')
ck('challenge_manifest_root',fsutil.manifest_root(challenge['manifest'])==challenge['contract_input_root'])
for row in challenge['manifest']['entries']:
 b=(PKG/row['path']).read_bytes()
 ck('frozen_file:'+row['path'],sha(b)==row['sha256'] and len(b)==row['size'])
original=load('cohort/requests/D21/original-metadata.json'); original_ids={r['id'] for r in original['identities']}
ck('original_identity_set',original_ids=={'D1','A1','I1','S1',*[f'O{i}' for i in range(1,8)]})
ck('exact_frozen_obligation_set',set(by_id)==original_ids|{'A1_satisfiable'} and set(statements)==set(by_id))
for identity in original['identities']:
 r=by_id[identity['id']]
 ck('identity_kind_role_required:'+r['id'],all(r[k]==identity[k] for k in ['kind','role','required']))
 ck('active:'+r['id'],not r['blocked_by'])
revised=(OUT/'snapshots/cohort/requests/D21/revised-prompt.txt').read_bytes()
for r in records:
 for n,ref in enumerate(r['source_refs']):
  ck('source_ref:'+r['id']+':'+str(n),ref['document_hash']==sha(revised) and 0<=ref['start_byte']<ref['end_byte']<=len(revised))
ck('no_added_workflow_obligation',len(formalization['bindings'])==11 and {x['obligation'] for x in formalization['bindings']}==original_ids)
ck('derived_nonvacuity_required',by_id['A1_satisfiable']['required'] and by_id['A1_satisfiable']['kind']=='non_vacuity' and by_id['A1_satisfiable']['origin']=='derived')
ck('derived_nonvacuity_same_assumption',formalization['internal_obligations'][0]['witnesses_for']==['A1'])
ck('required_source_policy_validation',not source_policy.validate(policy))
ck('required_source_policy_from_reconstructed_statements',not source_policy.check(policy,statements,records))
ck('policy_rows',set(policy['obligations'])=={'I1','S1',*[f'O{i}' for i in range(1,8)]})
for oid,row in policy['obligations'].items():
 ck('policy_value_required:'+oid,row['value_required']==(oid not in {'I1','S1'}))
expected_fields={
 'Event':[('group','String'),('time','Int'),('value',{'option':'Int'})],
 'Input':[('events',{'list':{'record':'Event'}}),('start','Int'),('end','Int'),('width','Int'),('fill','String')],
 'Output':[('group','String'),('start','Int'),('count','Nat'),('value',{'option':'Int'})],
 'State':[('previous',{'option':'Int'}),('rows',{'list':{'record':'Output'}})],
 'Stats':[('count','Nat'),('sum','Int')]}
ck('profile_record_set',set(profile_json['records'])==set(expected_fields))
for rid,expected in expected_fields.items():
 ck('exact_ordered_fields:'+rid,[(x['name'],x['sort']) for x in profile_json['records'][rid]['fields']]==expected)
closure=statements['O1']['semantic_closure']
for sid,s in profile_json['symbols'].items(): ck('helper_closed:'+sid,closure.get(s['lean_decl'])==s['decl_hash'])
for rid,record in profile_json['records'].items():
 for item in [record,*record['fields']]:
  if 'lean_decl' in item: ck('record_closed:'+rid,closure.get(item['lean_decl'])==item['decl_hash'])
  else: ck('projection_closed:'+rid+'.'+item['name'],closure.get(item['lean_projection'])==item['projection_hash'])
# Explicit independently written AST shape checks.  These are syntax inspections,
# not an implementation candidate, proof, or task oracle.
def n(tag,**kw): return {'tag':tag,**kw}
def v(i): return n('var',index=i)
def f(r,key,i): return n('field',sort=r,field=key,value=v(i))
def b(tag,left,right): return n(tag,left=left,right=right)
def u(tag,value): return n(tag,value=value)
def integer(i): return n('int',value=str(i))
def natural(i): return n('nat',value=str(i))
def string(s): return n('string',value=s)
def rec(r,*fields): return n('record',sort=r,fields=list(fields))
def ls(s,*items): return n('list',element_sort=s,items=list(items))
def none(): return n('none',element_sort='Int')
def cond(formula,x,y): return n('ite',condition=n('decide',formula=formula),then=x,**{'else':y})
def fold(value,initial,acc_s,elem_s,body): return n('list_foldl',value=value,initial=initial,function={'accumulator_sort':acc_s,'element_sort':elem_s,'body':body})
def bucket_start(inp,idx): return b('int_add',f('Input','start',inp),b('int_mul',u('nat_to_int',v(idx)),f('Input','width',inp)))
def ands(*xs):
 result=xs[-1]
 for x in reversed(xs[:-1]): result=b('and',x,result)
 return result
R=lambda r:{'record':r}
L=lambda r:{'list':R(r)}
guard=ands(b('lt',integer(0),f('Input','width',0)),b('le',f('Input','start',0),f('Input','end',0)),b('or',b('eq',f('Input','fill',0),string('none')),b('eq',f('Input','fill',0),string('previous'))))
formula=statements['O1']['formula_package']['value']['formula']; rhs=formula['body']['right']['right']
ck('domain_exact_no_extra_preconditions',formula['tag']=='forall' and formula['sort']==R('Input') and formula['body']['tag']=='implies' and formula['body']['left']==guard)
ck('endpoint_lhs',formula['body']['right']['tag']=='eq' and formula['body']['right']['left']==n('call',symbol='solve',args=[v(0)]))
ck('nonvacuity_quantifies_same_domain',statements['A1_satisfiable']['formula_package']['formula']==n('exists',sort=R('Input'),body=guard))
# Event-fold body context: event0, stats accumulator1, bucket index2,
# bucket state3, group4, output accumulator5, input6.
eligible=ands(b('eq',f('Event','group',0),v(4)),b('le',bucket_start(6,2),f('Event','time',0)),b('lt',f('Event','time',0),b('int_add',bucket_start(6,2),f('Input','width',6))),b('lt',f('Event','time',0),f('Input','end',6)),n('holds',term=u('option_is_some',f('Event','value',0))))
event_body=cond(eligible,rec('Stats',b('add',f('Stats','count',1),natural(1)),b('int_add',f('Stats','sum',1),n('option_get_or',value=f('Event','value',0),default=integer(0)))),v(1))
events=fold(f('Input','events',4),rec('Stats',natural(0),integer(0)),R('Stats'),R('Event'),event_body)
# Singleton-state body: stats0, current state1, bucket index2,
# enclosing bucket state3, group4, output accumulator5, input6.
nonempty=b('lt',natural(0),f('Stats','count',0)); summed=u('some',f('Stats','sum',0)); previous=f('State','previous',1)
row_value=cond(nonempty,summed,cond(b('eq',f('Input','fill',6),string('previous')),previous,none()))
row=rec('Output',v(4),bucket_start(6,2),f('Stats','count',0),row_value)
state_body=rec('State',cond(nonempty,summed,previous),b('list_append',f('State','rows',1),ls(R('Output'),row)))
state_step=fold(ls(R('Stats'),events),v(1),R('State'),R('Stats'),state_body)
# Bucket-fold enclosing group context: group0, output accumulator1,input2.
ceil_term=u('int_to_nat',b('int_fdiv',b('int_sub',b('int_add',b('int_sub',f('Input','end',2),f('Input','start',2)),f('Input','width',2)),integer(1)),f('Input','width',2)))
buckets=fold(n('list_range',stop=ceil_term),rec('State',none(),ls(R('Output'))),R('State'),'Nat',state_step)
group_body=b('list_append',v(1),n('field',sort='State',field='rows',value=buckets))
groups=u('list_sort',u('list_unique',n('list_map',value=f('Input','events',0),function={'sort':R('Event'),'body':f('Event','group',0)})))
expected_rhs=fold(groups,ls(R('Output')),L('Output'),'String',group_body)
ck('entire_nested_reference_exact_ast',rhs==expected_rhs)
put('independent-reference-shape.json',expected_rhs)
for i in range(1,8):
 oid=f'O{i}';s=statements[oid];vp=s['formula_package']['value']
 ck('full_functional_formula:'+oid,vp==statements['O1']['formula_package']['value'])
 ck('hypotheses_exact_A1:'+oid,s['hypotheses']==['A1'])
 ck('typed_value_package:'+oid,dsl.check_package(vp,profile) is None)
 ck('projection_left_same_theorem:'+oid,s['formula_package']['value_projection']['projection']=='left' and s['formula_package']['value_projection']['source_theorem']=='VeriSlopAST.complete_aggregation')
for oid in ['I1','S1']:
 ck('approved_source_only:'+oid,statements[oid]['formula_package']['value'] is None and statements[oid]['hypotheses']==[])
ck('typed_nonvacuity_package',dsl.check_package(statements['A1_satisfiable']['formula_package'],profile) is None)
properties=policy['obligations']['O1']['properties']
for oid in policy['obligations']:
 sp=statements[oid]['formula_package'];facets=sp['source']
 ck('one_bound_source_facet:'+oid,len(facets)==1)
 facet=facets[0]
 ck('exact_source_constructor:'+oid,facet['requirements']==[{'tag':'entry','file':'program.vscore.json','entry':'solve','arity':1},*[{'tag':tag} for tag in properties]])
 ck('source_endpoint_same_solve:'+oid,facet['symbol']=='solve' and facet['lean_decl']=='VeriSlopAST.solve' and facet['decl_hash']==profile_json['symbols']['solve']['decl_hash'])
# Record every de Bruijn occurrence with its actual nested environment.
occurrences=[]; binders=[]
def walk(x,path,env):
 if isinstance(x,list):
  for i,y in enumerate(x): walk(y,path+'/'+str(i),env)
  return
 if not isinstance(x,dict): return
 tag=x.get('tag')
 if tag=='var':
  i=x['index'];ck('bound_var:'+path,0<=i<len(env));occurrences.append({'path':path,'index':i,'binding':env[i],'environment':env})
  return
 if tag in {'forall','exists'}:
  new=[{'name':'input','sort':x['sort']}]+env; binders.append({'path':path,'tag':tag,'environment':new}); walk(x['body'],path+'/body',new);return
 if tag=='list_foldl':
  fn=x['function']; es=fn['element_sort'];as_=fn['accumulator_sort']
  en='group' if es=='String' else 'bucket_index' if es=='Nat' else 'event' if es==R('Event') else 'stats'
  an='output_accumulator' if as_==L('Output') else 'stats_accumulator' if as_==R('Stats') else 'state_accumulator'
  new=[{'name':en,'sort':es},{'name':an,'sort':as_}]+env
  binders.append({'path':path,'tag':tag,'environment':new})
  walk(fn['body'],path+'/function/body',new);walk(x['value'],path+'/value',env);walk(x['initial'],path+'/initial',env);return
 if tag=='list_map':
  new=[{'name':'event','sort':x['function']['sort']}]+env;binders.append({'path':path,'tag':tag,'environment':new})
  walk(x['function']['body'],path+'/function/body',new);walk(x['value'],path+'/value',env);return
 for k,y in x.items():
  if isinstance(y,(list,dict)): walk(y,path+'/'+k,env)
walk(formula,'formula',[])
put('debruijn-bindings.json',{'binders':binders,'occurrences':occurrences,'maximum_context_length':max(len(x['environment']) for x in occurrences)})
ck('all_var_occurrences_typed',dsl.type_term(rhs,[R('Input')],profile)==L('Output'))
# Pure evaluation is limited to the two published examples (not hidden cases).
original_prompt=(OUT/'snapshots/cohort/requests/D21/original-prompt.txt').read_text()
examples=json.loads(original_prompt.split('Public examples (additional held-out cases will be scored):\n',1)[1])
def typed_input(data):
 evs=tuple(dsl.record_v('Event',[e['group'],e['time'],dsl.OPTION_NONE if e['value'] is None else dsl.option_some_v(e['value'])]) for e in data['events'])
 return dsl.record_v('Input',[evs,data['start'],data['end'],data['width'],data['fill']])
def output_json(row):
 vals=row[2];opt=vals[3]
 return dict(group=vals[0],start=vals[1],count=vals[2],value=None if opt==dsl.OPTION_NONE else opt[1])
example_results=[]
for i,ex in enumerate(examples):
 inp=typed_input(ex['input']);ev=dsl.Evaluator(profile,{},lambda bound,env: [],step_budget=50000,range_limit=4096)
 observed=[output_json(r) for r in ev.term(rhs,[inp])]
 ck('public_example:'+str(i),observed==ex['output'])
 example_results.append({'input':ex['input'],'expected_public_output':ex['output'],'observed_frozen_rhs_output':observed})
put('public-example-results.json',example_results)
# Small unrelated integer arithmetic grid checks bucket count against the
# literal number of increasing starts below end. It is not universal proof.
ceil_results=[]
for start in range(-3,4):
 for distance in range(10):
  end=start+distance
  for width in range(1,8):
   inp=typed_input({'events':[],'start':start,'end':end,'width':width,'fill':'none'})
   ev=dsl.Evaluator(profile,{},lambda bound,env: [],step_budget=1000,range_limit=100)
   actual=ev.term(ceil_term,['unrelated-group',(),inp])
   literal_count=len(tuple(range(start,end,width)))
   ck('ceil_grid:'+str((start,end,width)),actual==literal_count)
   ceil_results.append({'start':start,'end':end,'width':width,'ceil_term':actual,'count_of_starts':literal_count})
put('bounded-ceil-arithmetic.json',ceil_results)
ck('constructive_domain_is_nonempty',dsl.Evaluator(profile,{},lambda bound,env: []).formula(guard,[typed_input({'events':[],'start':0,'end':0,'width':1,'fill':'none'})]).value)
lean=(OUT/'snapshots/package/contract/challenge/Contract.lean').read_text()
placeholders=[{'line':i,'text':line} for i,line in enumerate(lean.splitlines(),1) if 'by sorry' in line]
ck('frozen_proof_placeholders_only_expected',len(placeholders)==3 and all(any(name in x['text'] for name in ['«complete_aggregation»','«input_inhabited»','«source_properties»']) for x in placeholders))
ck('no_explicit_new_axiom_declaration',not re.search(r'^\s*axiom\b',lean,re.M))
strict=load('package/contract/challenge/policy.json')
ck('strict_expected_axiom_policy',strict['forbid_module_axioms'] and strict['require_kernel_replay'] and strict['allowed_axioms']==['Classical.choice','Quot.sound','propext'])
put('frozen-proof-placeholders.json',placeholders)
notes=[
 {'clause':'Full domain','observation':'Input events/list/Int/String/Option shapes have no size or magnitude bounds. The sole guard is width>0, start<=end, and the two specified fill alternatives.'},
 {'clause':'Bucket count, signed endpoints and empty interval','observation':'For d=end-start>=0 and w=width>0, N=floor((d+w-1)/w)=ceil(d/w). Numerator is nonnegative; toNat changes nothing. When d=0, N=0. For k<N, start+k*w<end, and conversely. This reasoning depends only on d,w, not the signs or magnitudes of start,end.'},
 {'clause':'Groups and Unicode order','observation':'Map group over every input event, erase duplicates only in that name list, then mergeSort using decidable String<=. Pinned Lean String order is lexicographic List Char order and Char order compares scalar values. Out-of-range events still contribute group names.'},
 {'clause':'Half-open end clipping','observation':'Event guard contains group equality, bucketStart<=time, time<bucketStart+width, time<end, and isSome value. The two strict upper guards are equivalent to time<min(bucketStart+width,end).'},
 {'clause':'Counts, sums, duplicates and null','observation':'Each occurrence in the original input events list is folded separately. Only eligible Some values increment count and contribute Int sum; event list is never deduplicated. Stats starts count0/sum0.'},
 {'clause':'Causal previous and zero','observation':'Each group starts State(previous=None,rows=[]), then increasing bucket indices. count>0 updates previous to Some sum, including zero. Empty bucket retains previous. fill previous uses retained state; fill none emits None. Before-start events fail all emitted buckets\' lower guard, so cannot seed.'},
 {'clause':'Exact group-then-bucket output','observation':'A singleton output record is appended at every bucket step, bucket state rows are projected after the fold, and each group rows list is appended to outer output. No prepend/reverse/alternate order/extra output branch occurs.'},
 {'clause':'Required identities and facets','observation':'All11 original IDs retained required and active. O1-O7 bind the identical full universal functional formula conjoined with exact solve/file/arity+7 source properties. Only explicitly approved I1/S1 are source-only. Derived required A1_satisfiable quantifies the same valid domain.'},
 {'clause':'Lean body versus reconstructed statement','observation':'The named Lean helper definitions bucket_count/stats/step/group_rows/groups/solve were manually read and match the inlined primitive RHS, including all binders. Their exact hashes and record/projection dependency hashes are present in O1 semantic_closure. No author JSON was used as statement authority.'},
 {'clause':'Proof and implementation status','observation':'Frozen challenge contains three expected by-sorry placeholders. This is a scope audit of the frozen Lean/reconstructed representation, not proof acceptance, actual source refinement, raw adapter adequacy, or mechanical closure. Those remain later native workflow obligations.'}
]
put('mathematical-scope-observations.json',notes)
# Rehash every inspected exact input; snapshot and hash authentication only.
for row in snapshots: ck('read_stability:'+row['snapshot'],sha(Path(row['path']).read_bytes())==row['sha256'])
put('snapshot-manifest.json',{'schema_version':'audit-snapshots/1','entries':snapshots})
put('checks.json',checks)
availability={'accepted_contract_directory_exists':(PKG/'contract/accepted').exists(),'accepted_ir_exists':(PKG/'contract/accepted/accepted-ir.json').exists(),'implementation_directory_exists':(PKG/'implementation').exists(),'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
audit={'schema_version':'independent-scope-audit/1','phase':'fresh Stage011 D21 frozen challenge','source_root':'sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a','contract_input_root':challenge['contract_input_root'],'result':'NO_CONCRETE_SCOPE_DEFECT_FOUND_IN_BOUNDED_INSPECTION','claim_limit':'Faithful frozen mathematical representation; accepted proofs and implementation/source/bridge/mechanical discharge not audited or claimed. Natural-language correspondence remains an explicit trusted audit judgment.','inputs':len(snapshots),'checks':len(checks),'passed_checks':sum(x['pass'] for x in checks),'debruijn_occurrences':len(occurrences),'public_examples':len(examples),'ceil_arithmetic_cases':len(ceil_results),'availability_observed_only':availability,'forbidden_actions_not_performed':['native/kernel/closure/gate execution','model/provider calls','author/controller/reviewer communication','package/cohort/project/production edits','historical solutions/proofs/hidden cases'],'preceding_phase_receipts':[{'path':'initial-attempt-zb68ly_5/audit.json','sha256':'sha256:ff0f37228e42fe527d75c41d96d42f02cf10db8cc726e5bb4550363eacccf8fe'},{'path':'interpreted-attempt-w13woa1u/audit.json','sha256':'sha256:3c8c4c593c102b434d96792474c9b80802addd78c5de7a150786f5945d8223b2'}]}
put('audit.json',audit)
print(json.dumps(audit,indent=2))
