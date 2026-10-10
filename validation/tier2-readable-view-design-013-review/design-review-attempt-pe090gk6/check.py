from __future__ import annotations
import copy, datetime, hashlib, json, pathlib, re, shutil, sys

ROOT=pathlib.Path('/home/augustus/VeriSlop_CLI')
OUT=pathlib.Path(__file__).resolve().parent
DESIGN=ROOT/'validation/tier2-readable-view-design-013/design-v2-module-bound-20261010T034049Z-790249cc'
DELTA=ROOT/'validation/tier2-readable-view-design-013/minimal-recipe-delta-20261010T034501Z-52b56a72'
sys.path.insert(0,str(ROOT))
from verislop.jsonschema_lite import Registry

H='sha256:'+'a'*64
checks=[]
def record(label,passed,details=None):
 checks.append({'id':label,'pass':bool(passed),'details':details})
 if not passed: raise AssertionError(label)
def digest(data): return 'sha256:'+hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_bytes())

design_manifest=read(DESIGN/'manifest.json')
delta_manifest=read(DELTA/'manifest.json')
spec=read(DESIGN/'specification.json')
delta=read(DELTA/'recipe-delta.json')
record('exact-design-spec',digest((DESIGN/'specification.json').read_bytes())=='sha256:27ebcb558b1c2dc63ca97ce8b1ef5c80b8368a58d59eb857cc433f7f7257cb09')
record('exact-design-manifest',digest((DESIGN/'manifest.json').read_bytes())=='sha256:fc250de564570c0cef9005f498ece732e490f5941a562b901d04d2c293725bce')
record('exact-delta-spec',digest((DELTA/'recipe-delta.json').read_bytes())=='sha256:42a1ddd138f3beaaacdb424c7cffcdc870db2b6316bcabb444f4c7a67393ce38')
record('exact-delta-manifest',digest((DELTA/'manifest.json').read_bytes())=='sha256:6f9f9ce2848b0c00d46563f3fb80d1e2a1ad4f91635396f5b61fb103c4b22aa4')
for folder,manifest in [(DESIGN,design_manifest),(DELTA,delta_manifest)]:
 for row in manifest['artifacts']:
  raw=(folder/row['path']).read_bytes()
  record('sealed-artifact:'+folder.name+'/'+row['path'],digest(raw)==row['sha256'] and len(raw)==row['size'])
record('delta-parent-binding',delta['parent_design']==delta_manifest['parent_design'] and delta['parent_design']['specification_sha256']==digest((DESIGN/'specification.json').read_bytes()) and delta['parent_design']['manifest_sha256']==digest((DESIGN/'manifest.json').read_bytes()))

# Copy exactly named generic APIs and sealed design inputs; no task/cohort source is opened.
api_paths=[row['path'] for row in design_manifest['generic_api_observations']]+['verislop/jsonschema_lite.py']
observed=[]
for rel in api_paths:
 raw=(ROOT/rel).read_bytes(); dest=OUT/'inputs'/'generic'/rel
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
 prior=next((r['sha256'] for r in design_manifest['generic_api_observations'] if r['path']==rel),None)
 observed.append({'path':rel,'sha256':digest(raw),'size':len(raw),'design_prior_observation':prior,'equals_prior_observation':prior is None or digest(raw)==prior})
for folder in [DESIGN,DELTA]:
 for path in sorted(folder.iterdir()):
  if path.is_file():
   dest=OUT/'inputs'/'design'/folder.name/path.name
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())

syntax=(ROOT/'verislop/lean/VSCore3/Syntax.lean').read_text()
expr_block=syntax.split('inductive Expr where\n',1)[1].split('\ninductive DataDecl where',1)[0]
actual=re.findall(r'\|\s+(\w+)',expr_block)
matrix=read(DESIGN/'constructor-matrix.json')
rows=matrix['rows'] if 'rows' in matrix else matrix['constructors']
covered=[r['constructor'] for r in rows]
record('exact-current-41-expr-constructors',len(actual)==41 and len(set(actual))==41,actual)
record('matrix-39-unique-constructors',len(covered)==39 and len(set(covered))==39)
record('matrix-excludes-only-variant-branches',set(actual)-set(covered)=={'variant','matchVariant'} and set(covered)<=set(actual))
record('coverage-spec-equals-matrix',covered==spec['closed_coverage']['source_expr_constructors'])
for row in rows:
 record('matrix-fields:'+row['constructor'],all(row.get(k) for k in ['type_rule','environment','readable_body','normative_compiler_branch','correspondence_recipe','negative_mutations']))
plan=read(DESIGN/'validation-plan.json')
record('validation-plan-19-unique',len(plan['cases'])==19 and len({c['id'] for c in plan['cases']})==19)
record('proof-identity-honest-module-mode',spec['proof_identity_choice']['frozen_choice'].startswith('MODULE_BOUND_PROOF') and 'individual theorem proof-body AST' in spec['proof_identity_choice']['unavailable'])
record('delta-fixed-universal-recipe','intro env; with_unfolding_all rfl' in json.dumps(delta) and 'Frozen CHECKED replay never falls back' in json.dumps(delta))
record('delta-no-required-node-theorems','Do not require inventories for per-expression proof declarations when none are emitted' in json.dumps(delta))

# These are finite structural schema tests only. Semantic replay is explicitly unimplemented.
def exemplar(s):
 if 'const' in s: return copy.deepcopy(s['const'])
 if 'enum' in s: return copy.deepcopy(s['enum'][0])
 if 'oneOf' in s: return exemplar(s['oneOf'][0])
 t=s.get('type')
 if isinstance(t,list):t=t[0]
 if t=='object':return {k:exemplar(s['properties'][k]) for k in s.get('required',[])}
 if t=='array':return [exemplar(s.get('items',{})) for _ in range(s.get('minItems',0))]
 if t=='string':return H if 'pattern' in s and 'sha256:' in s['pattern'] else 'x'
 if t=='integer':return s.get('minimum',0)
 if t=='boolean':return False
 if t=='null':return None
 return None
reg=Registry();schemas={}
for name in ['readable-selection.schema.json','readable-view.schema.json']:
 schema=read(DESIGN/name);reg.add(schema);schemas[name]=schema
 record('schema-registers:'+name,True)

def validate_case(label,value,schema,expect):
 issues=reg.validate(value,schema['$id'])
 record(label,(not issues)==expect,[str(i) for i in issues])

sel_schema=schemas['readable-selection.schema.json'];sel=exemplar(sel_schema)
sel['selected_mode']='CHECKED';sel['status']='CHECKED';sel['reasons']=[]
validate_case('checked-selection-structure',sel,sel_schema,True)
base=copy.deepcopy(sel);base['selected_mode']='BASE';base['status']='UNSUPPORTED';base['checked_descriptor']=None
validate_case('base-selection-structure',base,sel_schema,True)
for label,mut in [
 ('checked-selection-null-descriptor',lambda x:x.update(checked_descriptor=None)),
 ('checked-selection-status-downgrade',lambda x:x.update(status='UNSUPPORTED')),
 ('checked-selection-unknown-field',lambda x:x.update(fake_authority=True)),
 ('base-selection-checked-status',lambda x:x.update(status='CHECKED')),
 ('base-selection-nonnull-descriptor',lambda x:x.update(checked_descriptor=copy.deepcopy(sel['checked_descriptor']))),
]:
 value=copy.deepcopy(base if label.startswith('base-') else sel);mut(value)
 validate_case(label,value,sel_schema,False)
for key in sel_schema['required']:
 value=copy.deepcopy(sel);del value[key]
 validate_case('selection-required:'+key,value,sel_schema,False)
for key in sel['budgets']:
 value=copy.deepcopy(sel);value['budgets'][key]+=1
 validate_case('selection-frozen-budget:'+key,value,sel_schema,False)

view_schema=schemas['readable-view.schema.json'];view=exemplar(view_schema)
view['selected_mode']='CHECKED';view['status']='CHECKED';view['reasons']=[]
view['support_inventory_hash']=H;view['support_module_parts_hash']=H
view['compiled_inventory']=[exemplar(view_schema['properties']['compiled_inventory']['items'])]
row_schema=view_schema['properties']['support_declarations']['items']
definition=exemplar(row_schema);definition['kind']='definition';definition['body_hash']=H
identity_schema=row_schema['properties']['proof_identity']['oneOf']
definition['proof_identity']=exemplar(identity_schema[1])
view['support_declarations']=[definition]
validate_case('checked-view-definition-structure',view,view_schema,True)
theorem=exemplar(row_schema);theorem['kind']='theorem';theorem['body_hash']=None;theorem['proof_identity']=exemplar(identity_schema[0])
vt=copy.deepcopy(view);vt['support_declarations']=[theorem]
validate_case('checked-view-theorem-module-structure',vt,view_schema,True)
for label,mut in [
 ('theorem-fabricated-body-hash',lambda r:r.update(body_hash=H)),
 ('theorem-fabricated-ast',lambda r:r['proof_identity'].update(proof_body_ast={})),
 ('theorem-fabricated-digest',lambda r:r['proof_identity'].update(individual_proof_body_digest=H)),
 ('theorem-definition-identity-kind',lambda r:r.update(proof_identity=copy.deepcopy(definition['proof_identity']))),
 ('theorem-unsafe',lambda r:r.update(safety='unsafe')),
 ('theorem-unknown-field',lambda r:r.update(proof_ast={})),
]:
 value=copy.deepcopy(vt);mut(value['support_declarations'][0]);validate_case(label,value,view_schema,False)
for key in row_schema['required']:
 value=copy.deepcopy(vt);del value['support_declarations'][0][key]
 validate_case('theorem-row-required:'+key,value,view_schema,False)
for label,mut in [
 ('definition-null-body-hash',lambda r:r.update(body_hash=None)),
 ('definition-theorem-identity-kind',lambda r:r.update(proof_identity=copy.deepcopy(theorem['proof_identity']))),
]:
 value=copy.deepcopy(view);mut(value['support_declarations'][0]);validate_case(label,value,view_schema,False)
for key in view_schema['required']:
 value=copy.deepcopy(vt);del value[key]
 validate_case('view-required:'+key,value,view_schema,False)
for label,mut in [
 ('checked-view-empty-function-inventory',lambda x:x.update(compiled_inventory=[])),
 ('checked-view-empty-support-inventory',lambda x:x.update(support_declarations=[])),
 ('checked-view-null-module-binding',lambda x:x.update(support_module_parts_hash=None)),
 ('checked-view-null-support-binding',lambda x:x.update(support_inventory_hash=None)),
 ('checked-view-status-downgrade',lambda x:x.update(status='REJECTED')),
 ('checked-view-unknown-field',lambda x:x.update(support_authority=True)),
]:
 value=copy.deepcopy(vt);mut(value);validate_case(label,value,view_schema,False)
base_view=copy.deepcopy(vt);base_view.update(selected_mode='BASE',status='UNSUPPORTED',support_inventory_hash=None,support_module_parts_hash=None,compiled_inventory=[],support_declarations=[],actual_support_axioms=[],checked_proof_support_dependencies=[])
validate_case('base-view-empty-support-structure',base_view,view_schema,True)
value=copy.deepcopy(base_view);value['support_declarations']=[theorem]
validate_case('base-view-cannot-expose-theorem',value,view_schema,False)

# Finite metadata checks for the exact intended binder stacks; not a Lean equality proof.
from collections import OrderedDict
binder_expectations=OrderedDict([
 ('entry_helper_body','params.reverse; index 0 is last declared parameter'),
 ('letE','value :: outer'),('some_result_payload','payload :: outer'),
 ('matchList_cons','tail :: head :: outer'),('listMap_filter','item :: outer'),
 ('listFold_step','item :: accumulator :: outer; host lambda accumulator then item'),
 ('natFold_step','accumulator :: Nat-index :: outer; host Nat.rec lambda index then accumulator')])
record('exact-all-seven-binder-descriptions',spec['explicit_function_interfaces']['source_binders']==binder_expectations)
for arity in range(65):
 values=list(range(arity));env=()
 for val in reversed(values):env=(val,env)
 extracted=[];rest=env
 while rest:extracted.append(rest[0]);rest=rest[1]
 record('declared-order-tuple-bookkeeping:'+str(arity),extracted==values and list(reversed(extracted))==values[::-1])

# Independently checked API substrings tie the reviewed prose to the current generic code.
api_anchors={
 'verislop/lean/VSCore3/Typing.lean':[
  'compileExpr (exprBudget e.body + 1) p ds hs params.reverse e.body',
  'fun args => body (envReverse params args)',
  'compileHelperPass p ds rest (hs ++ [result])',
  'let c ← castCompiled n.1 (← compileExpr f p ds hs (.list t :: t :: Γ) c)',
  'step (item, (acc, env))','step (acc, (index, env))',
  'mapped.2 (x, env)','predicate (x, env)',
  'List.get?Internal (x env) (i env)','Int.fdiv (x env) (y env)',
  'mergeSort (fun a b => decide (a ≤ b))','List.sum (run env)'],
 'verislop/lean/VeriSlopKernel.lean':[
  'v.value.getUsedConstants.qsort Name.lt','("value_constants", namesJson used)',
  'let (axs, unknown) := axiomsOf env ci.name','base.toKernelEnv.replay newConsts'],
 'verislop/exprjson.py':['Theorems contribute their type only','ident["value"] = canon(c["value"], lps)'],
 'verislop/bridges/vscore3_checker.py':['def verify_published(','def run_build(','def _audit(','DETERMINISTIC ='],
 'verislop/backends/vscore3_closure.py':['def _clean_build(','def validate_execution(','COMPARISON_SLOTS =']}
for rel,anchors in api_anchors.items():
 text=(ROOT/rel).read_text()
 for i,anchor in enumerate(anchors):record('current-api-anchor:'+rel+':'+str(i),anchor in text,anchor)

# Recheck captured generic bytes after all pure reads. Differences in earlier design observations are explicit.
for row in observed:
 record('current-generic-byte-stability:'+row['path'],digest((ROOT/row['path']).read_bytes())==row['sha256'])
(OUT/'checks.json').write_text(json.dumps({'scope':'Pure design/schema/API bookkeeping only; not an implemented readable checker or kernel qualification.','checks':checks},indent=2)+'\n')
(OUT/'observed-generic-files.json').write_text(json.dumps(observed,indent=2)+'\n')
print(json.dumps({'result':'PASS','pure_checks':len(checks),'generic_files_captured':len(observed),'design_prior_observation_differences':[r['path'] for r in observed if not r['equals_prior_observation']],'no_build_or_model_calls':True,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
