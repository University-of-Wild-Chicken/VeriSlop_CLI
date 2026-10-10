#!/usr/bin/env python3
"""Frozen mathematical scope inspection. No Lean, model, native or closure execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-012'
RUN,PROJECT=STAGE/'run',STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';CH=PKG/'contract/challenge'
OUT=Path(__file__).resolve().parent
EXPECTED_SOURCE='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710'
EXPECTED_CHALLENGE='sha256:fa6cdd7a1dd8e85982b48c0034da5def3fab380a929a2fef3072a93ffa8f054a'
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def dumps(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def now():return datetime.now(timezone.utc).isoformat()
checks,snapshots,observed={},{},{};started=now()
def check(name,ok,detail=None):
 checks[name]={'ok':bool(ok)}
 if detail is not None:checks[name]['detail']=detail
 return bool(ok)
def capture(path,label):
 path=Path(path);check('regular:'+label,path.is_file() and not path.is_symlink());data=path.read_bytes()
 target=OUT/'snapshots'/label;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 snapshots[label]={'source':str(path),'sha256':digest(data),'size':len(data)};observed[str(path)]=digest(data);return data
def capture_json(path,label):return json.loads(capture(path,label))
protocol=capture_json(RUN/'protocol.json','request/protocol.json')
prereg=capture_json(RUN/'preregistration.json','request/preregistration.json')
check('exact_source_root',protocol['source_root']==prereg['source_root']==EXPECTED_SOURCE and digest(dumps(protocol['source_files']))==EXPECTED_SOURCE)
check('exact_protocol_prereg',digest((RUN/'protocol.json').read_bytes())==prereg['protocol_sha256'])
for name,sha in protocol['source_files'].items():check('frozen_source:'+name,digest(capture(PROJECT/name,'frozen-project/'+name))==sha)
for name,sha in protocol['input_files'].items():check('prepared_input:'+name,digest(capture(RUN/name,'prepared/'+name))==sha)
original=(RUN/'requests/D21/original-prompt.txt').read_bytes();revised=(RUN/'requests/D21/revised-prompt.txt').read_bytes()
metadata=json.loads((RUN/'requests/D21/original-metadata.json').read_bytes());source_policy=json.loads((RUN/'requests/D21/source-policy.json').read_bytes())
prior=ROOT/'synthetic_dataset/bootstrap/validation/tier2-d21-scope-audit-012/interpreted-attempt-3olbs4kt'
prior_audit=capture_json(prior/'audit.json','prior-interpreted-receipt/audit.json')
prior_seal=capture_json(prior/'RECEIPT-MANIFEST.json','prior-interpreted-receipt/RECEIPT-MANIFEST.json')
check('prior_interpreted_receipt_identity',digest((prior/'audit.json').read_bytes())=='sha256:c54527916de5d28f83da4381f3c26247da6ae76fccd59422c691a7e0a2b15db7' and prior_audit['source_root']==EXPECTED_SOURCE and prior_audit['interpretation_root']=='sha256:923ada9ceee40f9fc44c1e7dafbb90516048a0b2fb4378ce9b16c271b039ab72')
check('prior_interpreted_seal',prior_seal['files']['audit.json']==digest((prior/'audit.json').read_bytes()) and digest(dumps(prior_seal['files']))==prior_seal['files_root'])
challenge=capture_json(CH/'challenge.json','package/contract/challenge/challenge.json')
check('challenge_root',challenge['contract_input_root']==EXPECTED_CHALLENGE and digest(dumps(challenge['manifest']))==EXPECTED_CHALLENGE)
for row in challenge['manifest']['entries']:
 data=capture(PKG/row['path'],'package/'+row['path']);check('challenge_member:'+row['path'],digest(data)==row['sha256'] and len(data)==row['size'])
formalization=json.loads((CH/'formalization.json').read_bytes());statements=json.loads((CH/'statements.json').read_bytes());profile_json=json.loads((CH/'profile.json').read_bytes());policy=json.loads((CH/'policy.json').read_bytes());claims=json.loads((PKG/'claims.json').read_bytes())
lean=(CH/'Contract.lean').read_text();ast=lean.split('namespace VeriSlopAST\n',1)[1].rsplit('end VeriSlopAST',1)[0]
(OUT/'frozen-AST-section.lean').write_text('namespace VeriSlopAST\n'+ast+'end VeriSlopAST\n')
check('strict_pinned_policy',policy['allowed_axioms']==['Classical.choice','Quot.sound','propext'] and policy['forbid_module_axioms'] is True and policy['require_kernel_replay'] is True and policy['require_witnesses'] is True and challenge['toolchain']['pin']=='leanprover/lean4:v4.34.1')
check('frozen_placeholder_status_honest',len(re.findall(r'\bby sorry\b',ast))==3 and not re.search(r'^\s*axiom\s',lean,re.MULTILINE))
expected_ids={x['id'] for x in metadata['identities']};obligations={x['id']:x for x in claims['obligations']};statement_rows=statements['statements'];bindings={x['obligation']:x for x in formalization['bindings']}
check('original_identity_plus_registered_nv',set(obligations)==set(statement_rows)==expected_ids|{'A1_nonvacuity'} and set(bindings)==expected_ids)
check('frozen_claim_request_identity',claims['bound_to']['interpretation_root']==prior_audit['interpretation_root'] and claims['bound_to']['request']==digest(revised))
for identity in metadata['identities']:
 id=identity['id'];row=obligations[id];st=statement_rows[id]
 check('original_required_identity:'+id,{k:row[k] for k in ('id','role','kind','required')}=={k:identity[k] for k in ('id','role','kind','required')} and st['role']==identity['role'] and st['kind']==identity['kind'])
check('required_constructive_nonvacuity',obligations['A1_nonvacuity']['required'] is True and obligations['A1_nonvacuity']['kind']=='non_vacuity' and statement_rows['A1_nonvacuity']['hypotheses']==[] and formalization['internal_obligations']==[{'description':'An input with empty events, start and end zero, width one and fill none satisfies the exact caller precondition.','id':'A1_nonvacuity','kind':'non_vacuity','theorem':'VeriSlopAST.assumption_inhabited','witnesses_for':['A1']}])
check('only_original_assumption',all(statement_rows[id]['hypotheses']==['A1'] for id in [f'O{i}' for i in range(1,8)]) and all(statement_rows[id]['hypotheses']==[] for id in ('D1','A1','I1','S1','A1_nonvacuity')))

# Pure typed DSL validators only; no evaluator or kernel is invoked.
sys.path.insert(0,str(PROJECT))
from verislop import dsl
check('pure_dsl_from_frozen_project',Path(dsl.__file__).resolve()==PROJECT/'verislop/dsl.py')
profile=dsl.Profile.from_json(profile_json)
facets=statement_rows['O1']['formula_package'];value=facets['value'];formula=value['formula']
dsl.check_package(value,profile);check('pure_full_value_formula_typed',True)
dsl.check_package(statement_rows['A1_nonvacuity']['formula_package'],profile);check('pure_nv_formula_typed',True)
for id in [f'O{i}' for i in range(1,8)]:
 st=statement_rows[id];f=st['formula_package'];binding=bindings[id]
 check('full_shared_value_and_source:'+id,st['representation']=='source_facets' and f==facets and binding['theorem']=='VeriSlopAST.aggregation_contract' and binding['value_projection']=='VeriSlopAST._vs_value_aggregation_contract' and binding['source_requirements']==['VeriSlopAST.SolveSource'])
 check('guard_unfolding:'+id,st['unfolded_predicates']==['VeriSlopAST.valid_input'])
for id in ('I1','S1'):
 f=statement_rows[id]['formula_package'];check('source_only_exact:'+id,f['source']==facets['source'] and f['value'] is None and f['value_projection'] is None and bindings[id]['source_requirements']==['VeriSlopAST.SolveSource'] and bindings[id]['theorem']=='VeriSlopAST.source_contract')
expected_requirements=[{'tag':'entry','file':'program.vscore.json','entry':'solve','arity':1}]+[{'tag':p} for p in source_policy['obligations']['O1']['properties']]
check('canonical_source_facets_closed',len(facets['source'])==1 and facets['source'][0]['symbol']=='solve' and facets['source'][0]['lean_decl']=='VeriSlopAST.solve' and facets['source'][0]['requirements']==expected_requirements and facets['source'][0]['decl_hash']==profile_json['symbols']['solve']['decl_hash'])
check('source_definition_endpoint_lean', 'def «SolveSource» : _root_.VeriSlop.Source.SourceDefinition (_root_.VeriSlopAST.«Input» → (_root_.List _root_.VeriSlopAST.«Output»)) := ⟨_root_.VeriSlopAST.«solve»' in ast and 'SourceRequirement.entry "program.vscore.json" "solve" 1' in ast)
check('model_rules_are_not_actual_implementation_claim', 'def Contract {τ : Type} (d : SourceDefinition τ) : Prop :=\n  Transfer d.requirements ∧ AdmissionInhabited d.requirements' in (PROJECT/'verislop/lean/SourceBoundary.lean').read_text())
check('accepted_projection_keeps_whole_value_conjunction',facets['value_projection']['projection']=='left' and facets['value_projection']['source_theorem']=='VeriSlopAST.aggregation_contract' and 'theorem «_vs_value_aggregation_contract»' in ast and ':= by exact _root_.VeriSlopAST.«aggregation_contract».1' in ast)

# Exact anchors through the reconstructed formula, including all de Bruijn indices.
def var(i):return {'tag':'var','index':i}
def integer(n):return {'tag':'int','value':str(n)}
def natural(n):return {'tag':'nat','value':str(n)}
def string(s):return {'tag':'string','value':s}
def field(sort,name,index):return {'tag':'field','sort':sort,'field':name,'value':var(index)}
def binop(tag,left,right):return {'tag':tag,'left':left,'right':right}
def record(sort,*fields):return {'tag':'record','sort':sort,'fields':list(fields)}
def empty(sort):return {'tag':'list','element_sort':sort,'items':[]}
def none(sort):return {'tag':'none','element_sort':sort}
def some(value):return {'tag':'some','value':value}
def decide(formula):return {'tag':'decide','formula':formula}
def ite(condition,then,otherwise):return {'tag':'ite','condition':condition,'then':then,'else':otherwise}
def singleton(sort,value):return {'tag':'list','element_sort':sort,'items':[value]}
expected_guard=binop('and',binop('lt',integer(0),field('Input','width',0)),binop('and',binop('le',field('Input','start',0),field('Input','end',0)),binop('or',binop('eq',field('Input','fill',0),string('none')),binop('eq',field('Input','fill',0),string('previous')))))
check('value_full_universal_and_examples',formula['tag']=='and' and formula['left']['tag']=='forall' and formula['left']['sort']=={'record':'Input'} and formula['right']['tag']=='and')
universal=formula['left'];guard=universal['body']['left'];equality=universal['body']['right'];reference=equality['right']
check('exact_unbounded_guard',universal['body']['tag']=='implies' and guard==expected_guard)
check('source_reference_lhs',equality['tag']=='eq' and equality['left']=={'tag':'call','symbol':'solve','args':[var(0)]})
check('independent_reference_rhs_not_solve_call','solve' not in dsl.calls(reference) and reference['tag']=='list_foldl')
check('group_major_accumulation',reference['initial']==empty({'record':'Output'}) and reference['function']['element_sort']=='String' and reference['function']['accumulator_sort']=={'list':{'record':'Output'}} and reference['function']['body']['tag']=='list_append' and reference['function']['body']['left']==var(1))
groups=reference['value'];check('all_groups_sort_unique_all_events',groups=={'tag':'list_sort','value':{'tag':'list_unique','value':{'tag':'list_map','value':field('Input','events',0),'function':{'sort':{'record':'Event'},'body':field('Event','group',0)}}}})
rows_projection=reference['function']['body']['right'];bucket_fold=rows_projection['value']
check('per_group_initial_absent_state',rows_projection['tag']=='field' and rows_projection['sort']=='State' and rows_projection['field']=='rows' and bucket_fold['tag']=='list_foldl' and bucket_fold['initial']==record('State',empty({'record':'Output'}),none('Int')))
check('increasing_bucket_fold_sorts',bucket_fold['function']['element_sort']=='Int' and bucket_fold['function']['accumulator_sort']=={'record':'State'})
buckets=bucket_fold['value'];candidate_starts=buckets['value'];range_node=candidate_starts['value']
check('signed_distance_candidate_range',range_node=={'tag':'list_range','stop':{'tag':'int_to_nat','value':binop('int_sub',field('Input','end',2),field('Input','start',2))}})
check('candidate_start_exact_affine',candidate_starts['tag']=='list_map' and candidate_starts['function']=={'sort':'Nat','body':binop('int_add',field('Input','start',3),binop('int_mul',{'tag':'nat_to_int','value':var(0)},field('Input','width',3)))})
check('strict_end_bucket_filter',buckets['tag']=='list_filter' and buckets['function']=={'sort':'Int','body':decide(binop('lt',var(0),field('Input','end',3)))})
inner=bucket_fold['function']['body'];stats_fold=inner['value']['items'][0]
check('singleton_stats_evaluation_preserves_outer_state',inner['tag']=='list_foldl' and inner['initial']==var(1) and inner['value']['tag']=='list' and inner['value']['element_sort']=={'record':'Stats'} and len(inner['value']['items'])==1 and inner['function']['element_sort']=={'record':'Stats'} and inner['function']['accumulator_sort']=={'record':'State'})
check('stats_fold_all_event_occurrences',stats_fold['tag']=='list_foldl' and stats_fold['value']==field('Input','events',4) and stats_fold['initial']==record('Stats',natural(0),integer(0)) and stats_fold['function']['element_sort']=={'record':'Event'} and stats_fold['function']['accumulator_sort']=={'record':'Stats'})
selected=stats_fold['function']['body'];expected_selection=binop('bool_and',{'tag':'option_is_some','value':field('Event','value',0)},decide(binop('and',binop('eq',field('Event','group',0),var(4)),binop('and',binop('le',var(2),field('Event','time',0)),binop('and',binop('lt',field('Event','time',0),binop('int_add',var(2),field('Input','width',6))),binop('lt',field('Event','time',0),field('Input','end',6)))))))
check('exact_halfopen_nonnull_membership',selected['tag']=='ite' and selected['condition']==expected_selection and selected['else']==var(1))
expected_increment=record('Stats',binop('add',field('Stats','count',1),natural(1)),binop('int_add',field('Stats','sum',1),{'tag':'option_get_or','value':field('Event','value',0),'default':integer(0)}))
check('duplicates_count_and_exact_signed_sum',selected['then']==expected_increment)
state_body=inner['function']['body'];count_positive=decide(binop('lt',natural(0),field('Stats','count',0)));new_sum=some(field('Stats','sum',0));previous=field('State','previous',3)
expected_value=ite(count_positive,new_sum,ite(decide(binop('eq',field('Input','fill',6),string('previous'))),previous,none('Int')))
expected_out=record('Output',var(4),var(2),field('Stats','count',0),expected_value)
expected_state=record('State',binop('list_append',field('State','rows',3),singleton({'record':'Output'},expected_out)),ite(count_positive,new_sum,previous))
check('exact_causal_fill_and_state_transition',state_body==expected_state)
check('zero_sum_is_some_not_absence',state_body['fields'][1]['condition']==count_positive and state_body['fields'][1]['then']==new_sum)

# Public example equality ASTs are compared to original literal JSON without executing solve.
def event_literal(data):return record('Event',string(data['group']),integer(data['time']),none('Int') if data['value'] is None else some(integer(data['value'])))
def input_literal(data):return record('Input',{'tag':'list','element_sort':{'record':'Event'},'items':[event_literal(x) for x in data['events']]},integer(data['start']),integer(data['end']),integer(data['width']),string(data['fill']))
def output_literal(data):return record('Output',string(data['group']),integer(data['start']),natural(data['count']),none('Int') if data['value'] is None else some(integer(data['value'])))
examples=json.loads(original.split(b'Public examples (additional held-out cases will be scored):\n',1)[1])
for index,key in enumerate(('left','right')):
 example=examples[index];expected_example=binop('eq',{'tag':'call','symbol':'solve','args':[input_literal(example['input'])]},{'tag':'list','element_sort':{'record':'Output'},'items':[output_literal(x) for x in example['output']]})
 check('exact_public_example_ast:'+str(index),formula['right'][key]==expected_example)
nv_formula=statement_rows['A1_nonvacuity']['formula_package']['formula']
check('nonvacuity_same_unweakened_guard',nv_formula=={'tag':'exists','sort':{'record':'Input'},'body':expected_guard})

expected_fields={'Event':[('group','String'),('time','Int'),('value',{'option':'Int'})],'Input':[('events',{'list':{'record':'Event'}}),('start','Int'),('end','Int'),('width','Int'),('fill','String')],'Output':[('group','String'),('start','Int'),('count','Nat'),('value',{'option':'Int'})],'Stats':[('count','Nat'),('sum','Int')],'State':[('rows',{'list':{'record':'Output'}}),('previous',{'option':'Int'})]}
for sort,fields in expected_fields.items():check('exact_record_fields:'+sort,[(x['name'],x['sort']) for x in profile_json['records'][sort]['fields']]==fields)
check('solve_exact_signature',profile_json['symbols']['solve']['args']==[{'record':'Input'}] and profile_json['symbols']['solve']['result']=={'list':{'record':'Output'}})
check('no_domain_bounds_in_lean_guard','@[reducible] def «valid_input»' in ast and '_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width»' in ast)
check('reference_lean_uses_exact_data_primitives',all(token in ast for token in ['@_root_.List.foldl','@_root_.List.mergeSort _root_.String','@_root_.List.eraseDups _root_.String','_root_.List.range (_root_.Int.toNat','_root_.Int.ofNat','@_root_.Option.getD _root_.Int']))

binding_annotations=[
 {'location':'outer group fold body','innermost_first':['group','output accumulator','input']},
 {'location':'bucket map/filter body','innermost_first':['candidate k or bucket start','group','output accumulator','input']},
 {'location':'bucket fold body','innermost_first':['bucket start','group state','group','output accumulator','input']},
 {'location':'event stats fold body','innermost_first':['event','stats accumulator','bucket start','group state','group','output accumulator','input']},
 {'location':'singleton stats fold body','innermost_first':['stats result','singleton-fold accumulator','bucket start','group state','group','output accumulator','input'],'note':'Outer state index3 equals singleton-fold initial state; using it is correct because this fold has exactly one Stats item.'}]
findings=[
 {'facet':'unbounded domain','finding':'Universal Input binder guarded only by width>0, start<=end and fill none/previous. Event times/values, start/end, list lengths and Unicode scalar strings are unbounded.'},
 {'facet':'candidate bucket enumeration','finding':'Reference enumerates natural k<toNat(end-start), maps start+k*width, then filters starts<end. Under the exact guard, Delta=end-start>=0 and integer width>=1. Any required k satisfies k<=k*width<Delta, hence appears in the candidate range; filtering removes exactly starts>=end. Empty interval gives range0. Signed endpoints are preserved.'},
 {'facet':'all groups and sort','finding':'Groups are mapped from all events before eraseDups/mergeSort; no range/null filter removes a name. Comparator is String<= with Unicode scalar semantics, and each sorted group is processed once.'},
 {'facet':'half-open membership and multiplicity','finding':'Per bucket, fold scans every event occurrence. Predicate requires nonnull, exact group equality, bucket<=time, time<bucket+width and time<end; the two upper comparisons equal clipping at min(bucket+width,end). Each included duplicate increments count and sum once.'},
 {'facet':'causal filling','finding':'Each group initializes State([],none), folds increasing bucket starts, appends one row, emits some(sum) iff count>0, otherwise previous only in previous mode, and updates previous only for count>0. Zero stays some(0), empty never resets, and no prestart event can pass bucket<=time.'},
 {'facet':'output and examples','finding':'Outer sorted-group fold appends the complete bucket rows, preserving group-major then bucket order and exact fields. Both public example equalities match original literal JSON exactly.'},
 {'facet':'per-ID completeness','finding':'O1-O7 each bind the same complete universal solve=independently expanded aggregation reference conjunction with both exact public examples and the canonical Source Contract. RHS is not a solve self-call. Shared theorem does not omit any required value facet.'},
 {'facet':'source requirements','finding':'All nine rows use SolveSource whose endpoint is the exact frozen-reference solve symbol, canonical file/name/arity and all seven closed properties. I1/S1 have no value projection; O1-O7 retain the complete value projection. Abstract Source Contract encodes model rules and model inhabitance, not facts about a delivered source.'},
 {'facet':'nonvacuity and proof boundary','finding':'A1_nonvacuity is required, registered separately and states exists Input satisfying the identical guard, with constructive empty/0/0/1/none description. Frozen challenge still has exactly three sorry proof placeholders; no proof acceptance, actual source admission/refinement or source effects are claimed here.'}]

native_evidence={}
for file in sorted((PKG/'evidence').glob('*.json')):
 data=json.loads(file.read_bytes())
 if not data['claim_id'].startswith('FORMALIZED:'):continue
 ev=capture_json(file,'package/evidence/'+file.name);raw=capture_json(PKG/ev['raw_result_ref'],'package/'+ev['raw_result_ref']);id=ev['claim_id'].split(':')[1].split('@')[0]
 check('native_formalized_root:'+id,ev['input_root_hash']==EXPECTED_CHALLENGE and ev['status']=='PASS' and ev['exit_code']==0 and raw['milestone_outcome']=='PASS')
 check('native_formalized_raw_hash:'+id,digest((PKG/ev['raw_result_ref']).read_bytes())==ev['raw_result_hash'])
 check('native_formalized_statement_identity:'+id,raw['statement_hash']==statement_rows[id]['statement_hash'] and raw['representation']==statement_rows[id]['representation'] and raw['lean_symbol']==statement_rows[id]['lean_symbol'])
 native_evidence[id]={'evidence_id':ev['evidence_id'],'verifier_id':ev['verifier_id'],'status':ev['status'],'statement_hash':raw['statement_hash']}
check('all12_formalized_evidence',set(native_evidence)==set(statement_rows))
for path,sha in observed.items():check('snapshot_stable:'+str(Path(path).relative_to(ROOT)),digest(Path(path).read_bytes())==sha)
failures=[{'check':k,**v} for k,v in checks.items() if not v['ok']]
pending={name:(PKG/path).exists() for name,path in {'accepted_ir':'accepted/accepted-ir.json','implementation':'bridges/implementation','mechanical_pointer':'closure/current.json'}.items()}
report={'format':'verislop.independent-stage012-frozen-scope-audit/0.1','auditor':'/root/tier2_semantics_audit','phase':'frozen_challenge_before_acceptance','started_at_utc':started,'finished_at_utc':now(),'source_root':EXPECTED_SOURCE,'frozen_challenge_root':EXPECTED_CHALLENGE,'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failures else 'AUDIT_CHECK_FAILURE','checks_total':len(checks),'failed_checks':failures,'snapshots_count':len(snapshots),'findings':findings,'binding_annotations':binding_annotations,'native_formalized_evidence':native_evidence,'still_unproved_in_frozen_source':['aggregation_contract','assumption_inhabited','source_contract'],'artifact_availability_only':pending,'limitations':['Frozen statement representation and exact Lean source were inspected; no kernel or acceptance service was executed.','Pure DSL typing and exact reconstructed AST comparisons establish bounded representation checks, not an independent theorem proof.','Mathematical correspondence to public D21 text remains explicitly trusted auditor reasoning; hash validation does not prove natural-language meaning.','Frozen source has three honest proof placeholders. Accepted proof artifacts, generated implementation, universal refinement, raw adapters/coverage/effects and final closure are not audited or claimed in this phase.','No task role communication, author guidance, model request, task implementation/proof edit, native/gate/closure/kernel invocation, hidden case/oracle or historical task candidate/proof access occurred.','Only outside-cohort audit records were written; all audited frozen/live inputs remained byte-identical during inspection.']}
for name,obj in [('audit.json',report),('checks.json',checks),('snapshot-manifest.json',snapshots),('semantic-findings.json',findings),('binding-annotations.json',binding_annotations),('reference-value-package.json',value),('exact-guard.json',expected_guard)]: (OUT/name).write_bytes(dumps(obj)+b'\n')
(OUT/'formula-display.txt').write_text(dsl.render(formula)+'\n')
print(json.dumps({'audit':str(OUT/'audit.json'),'audit_sha256':digest((OUT/'audit.json').read_bytes()),'checks':len(checks),'failures':failures,'snapshots':len(snapshots),'artifact_availability':pending},sort_keys=True))
