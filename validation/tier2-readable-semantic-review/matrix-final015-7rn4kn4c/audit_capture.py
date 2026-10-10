from pathlib import Path
import json,sys,collections,base64
root=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'runtime'),str(root/'runtime/tests')]
from verislop import canonical,schemas,policy,leanbridge
from verislop.exprjson import app,const,canon,decl_hash,constants,name_str
from verislop.bridges import vscore3_checker as C,vscore3_readable_support as RS
from verislop.targets import vscore3_target as T,vscore3_readable as R,vscore3_source as S
from test_vscore3_readable import matrix_context
cap=root/'capture'
read=lambda p:(cap/p).read_bytes()
obj=lambda p:canonical.loads(read(p))
checks=[]
def ck(name,value,detail=None):
 assert value,name
 checks.append({'name':name,'result':'PASS','detail':detail})
outer=obj('manifest.json')
actual={p.relative_to(cap).as_posix() for p in cap.rglob('*') if p.is_file()}
ck('complete outer capture path inventory',actual=={'manifest.json',*outer['artifacts']},len(actual))
for path,ref in outer['artifacts'].items():
 data=read(path);assert ref=={'sha256':canonical.digest(data),'size':len(data)},path
ck('all outer actual sizes/hashes',True,len(outer['artifacts']))
selection=RS.checked_json('vscore-readable-selection',read(R.SELECTION_PATH))
manifest=RS.checked_json('vscore-readable-view',read(R.MANIFEST_PATH))
observation=obj('observation.json')
refs=RS.artifact_refs(observation['readable_support'],read)
ck('closed selection and manifest and every declared actual artifact ref',set(refs)=={R.MANIFEST_PATH,*[r['artifact']['path'] for r in manifest['artifacts']]},len(refs))
ck('actual selected mode/status',selection['selected_mode']==selection['status']==manifest['selected_mode']==manifest['status']=='CHECKED')
ck('zero diagnostic fallback inputs/reasons',selection['diagnostic_inputs']==selection['reasons']==[])
ck('captured goal is exact selected goal',read('goal.lean')==read('readable/selected-goal.lean'))
ctx=matrix_context(b'')
ck('fixture source/profile/relation reproduce observed fresh inputs',ctx.inputs['source'][1]==read('source.json') and canonical.dumps(ctx.accepted_profile)==read('profile.json') and canonical.dumps(ctx.relation)==read('relation.json'))
base=T.build_goal(read('source.json'),ctx.relation,ctx.accepted_profile,ctx.obligations)
selected=T.enrich_readable(base)
ck('pure regenerated base and selected source bytes exact',base.text.encode()==read('readable/base-goal.lean') and selected.text.encode()==read('goal.lean'))
ck('selected exactly appends base',selected.text.startswith(base.text+'\n'))
ck('expected complete EdgeProp and baseline declarations preserved',all(selected.expected[n]==v for n,v in base.expected.items()) and selected.expected['EdgeProp']==base.expected['EdgeProp'],len(base.expected))
ck('typed IR/source block/correspondence pure exact',selected.readable_view.typed_ir==read('readable/typed-ir.json') and selected.readable_view.block==read('readable/source-block.lean') and selected.readable_correspondence==read('readable/correspondence.lean'))
ck('all39 exact constructor matrix',set(selected.readable_view.constructors)==set(R.CONSTRUCTORS),sorted(R.CONSTRUCTORS))
program=S.parse_source(read('source.json'))
functions=selected.readable_view.functions
inventory=obj('readable/compiled-inventory.json')
exports=obj('readable/kernel-export.json')
rows=obj('readable/declarations.json')
rowsby={r['name']:r for r in rows}
ck('source entry/helper inventory is complete incl unused',len(inventory)==len(functions)==len(program['entries'])+len(program['helpers'])==27 and {(r['role'],r['source_id']) for r in inventory}=={('entry',r['id']) for r in program['entries']}|{('helper',r['id']) for r in program['helpers']}, {'entries':len(program['entries']),'helpers':len(program['helpers'])})
ck('support declaration exported inventories exact',set(exports)==set(rowsby)=={name_str(obj(r['kernel_record']['path'])['name']) for r in rows},len(rows))
ck('full proof identities array exact',obj('readable/proof-identity.json')==[r['proof_identity'] for r in rows])
ck('full axiom/dependency/equalities inventories exact',obj('readable/axioms.json')=={r['name']:r['axioms'] for r in rows} and obj('readable/dependencies.json')=={r['name']:r['transitive_dependencies'] for r in rows} and obj('readable/equalities.json')==[{'name':n,'type_hash':canonical.digest_json(canon(c['type'],[]))} for n,c in sorted(exports.items()) if c['kind']=='theorem'])
modules={}
for p in (cap/'modules').iterdir():
 for suffix in sorted(leanbridge.MODULE_SUFFIXES,key=len,reverse=True):
  if p.name.endswith(suffix):
   modules.setdefault(p.name[:-len(suffix)],{})[suffix]=p.read_bytes();break
ck('complete captured module set and each parts digest exact',set(modules)==set(observation['modules']) and all(C._parts_digest(ps)==observation['modules'][m] for m,ps in modules.items()),{m:sorted(ps) for m,ps in modules.items()})
gh=C._parts_digest(modules[T.GOAL_MODULE])
ck('goal full parts identity binds every declaration',all(r['proof_identity']['module_parts_hash']==gh and r['proof_identity']['regenerated_source_hash']==canonical.digest(read('goal.lean')) for r in rows))
for r in rows:
 c=exports[r['name']]
 assert c==obj(r['kernel_record']['path'])
 assert r['identity_hash']==canonical.digest_json({k:v for k,v in r.items() if k!='identity_hash'})
 assert c['kind'] in ('definition','theorem') and c['safety']=='safe' and c['level_params']==[] and c['unresolved_constants']==[]
 assert all(policy.classify_axiom(a,policy.get('strict'))=='allowed' for a in r['axioms'])
 ident=r['proof_identity']
 if c['kind']=='theorem':
  assert r['body_hash'] is None and 'value' not in c and 'value_constants' in c
  assert ident['kind']=='MODULE_BOUND_PROOF' and ident['proof_body_ast']==ident['individual_proof_body_digest']=='UNAVAILABLE'
  assert ident['direct_value_constants_hash']==canonical.digest_json(sorted(name_str(n) for n in c['value_constants']))
  assert ident['axiom_inventory_hash']==canonical.digest_json(sorted(name_str(a) for a in c['axioms']))
 else:
  assert ident['kind']=='EXPORTED_DEFINITION_BODY' and ident['exported_body_hash']==r['body_hash']==canonical.digest_json(canon(c['value'],[]))
ck('honest all definition/proof identities+safety+levels+axioms',True,dict(collections.Counter(c['kind'] for c in exports.values())))
for f,inv in zip(functions,inventory):
 n=f['name'];gn=T.GOAL_MODULE+'.Readable.';rn=R.NAMESPACE+'.'+n
 assert {k:inv[k] for k in ('role','source_id','source_index','compiled_index','source_declaration_hash','compilation_context_hash')}=={k:f[k] for k in ('role','source_id','source_index','compiled_index','source_declaration_hash','compilation_context_hash')}
 expected=app(const('VSCore3.ReadableRunEquals'),const(gn+n+'_compiled'),const(rn+'_params'),const(rn+'_result'),const(rn+'_run'))
 pred=exports[gn+'RunEquals_'+n];theorem=exports[gn+'runEquals_'+n]
 assert pred['type']=={'sort':0} and canon(pred['value'],[])==canon(expected,[])
 assert theorem['kind']=='theorem' and canon(theorem['type'],[])==canon(const(gn+'RunEquals_'+n),[])
 assert inv['run_equals_type_hash']==canonical.digest_json(canon(expected,[]))
 assert inv['run_equals_theorem']==gn+'runEquals_'+n
 for need in [gn+'lookup_'+n,gn+'signature_'+n,gn+n+'_compiled',rn+'_params',rn+'_result',rn+'_body',rn+'_run',rn+'_named']:assert need in exports,need
 assert inv['params_shape_hash']==decl_hash(exports[rn+'_params']) and inv['result_shape_hash']==decl_hash(exports[rn+'_result'])
ck('all27 exact universal RunEquals applications/types/signatures/lookup inventory',True,27)
union=sorted({a for r in rows for a in r['axioms']})
baseline=obj('readable/base-kernel-export.json')
full=obj('full-kernel-export.json')
base_selected={n:c for n,c in full.items() if c.get('module')==[T.GOAL_MODULE] and n not in exports}
ck('raw retained BASE complete selected-goal projection equality',set(base_selected)==set(baseline) and all(decl_hash(base_selected[n])==decl_hash(c) for n,c in baseline.items()),len(baseline))
ck('raw BASE exact complete declaration identity hash',canonical.digest_json({n:decl_hash(c) for n,c in sorted(baseline.items())})==manifest['base_declaration_identity_hash'])
ck('raw support exact full selected export projection',{n:c for n,c in full.items() if c.get('module')==[T.GOAL_MODULE] and n not in baseline}==exports,len(full))
base_axioms=sorted({name_str(a) for c in baseline.values() for a in c['axioms']})
ck('raw BASE walks complete/safe and axioms allowed',all(c.get('safety')=='safe' and c.get('unresolved_constants')==[] and 'axioms' in c for c in baseline.values()) and all(policy.classify_axiom(a,policy.get('strict'))=='allowed' for a in base_axioms))
ck('actual support axiom inclusion recomputed from raw BASE',union==manifest['actual_support_axioms'] and canonical.digest_json(base_axioms)==manifest['support_axiom_baseline_hash'] and set(union)<=set(base_axioms),{'BASE':base_axioms,'support':union})
direct={n:set(constants(c['type']))|set(constants(c.get('value',{})))|{name_str(x) for x in c.get('value_constants',[])} for n,c in full.items()}
for row in rows:
 todo=list(row['type_constants']+row['body_constants']);seen=set()
 while todo:
  dep=todo.pop()
  if dep in seen:continue
  seen.add(dep)
  if dep in full:
   assert full[dep].get('module')!=[T.PROOF_MODULE],dep
   todo.extend(direct[dep])
 assert sorted(seen)==row['transitive_dependencies'],row['name']
ck('all274 transitive dependencies recomputed using actual full selected export',True)
ck('raw accepted BASE EdgeProp identity preserved',decl_hash(baseline[T.GOAL_MODULE+'.EdgeProp'])==decl_hash(full[T.GOAL_MODULE+'.EdgeProp']))
receipt=obj('readable/kernel-receipt.json')
ck('kernel receipt exact retained module/export/tool/import hash binding',receipt['goal_module_parts_hash']==gh==selection['checked_descriptor']['goal_module_parts_hash'] and receipt['support_export_hash']==canonical.digest(read('readable/kernel-export.json')) and receipt['kernel_tool_hash']==observation['kernel_tool_hash']==manifest['toolchain']['kernel_tool_hash'] and receipt['toolchain_olean_closure']==observation['toolchain_olean_closure']==manifest['toolchain']['import_closure_hash'])
ck('base-selected proposition claim equality',selection['base_proposition_hash']==manifest['base_proposition_hash']==manifest['replayed_proposition_hash']==observation['proposition_hash'])
process=obj('compile-process.json')
compiled=set(observation['compiles'])
ck('complete separate BASE and SELECTED process phases',set(process)=={phase+'::'+m for phase in ('BASE','SELECTED') for m in compiled},len(process))
for key,rec in process.items():
 assert rec['availability']=='available'
 rr=rec['record'];assert rr['input']['module']==key.split('::',1)[1] and rr['returncode']==0 and not rr['timed_out']
 phase,module=key.split('::',1)
 source=(base.text if phase=='BASE' else selected.text).encode() if module==T.GOAL_MODULE else T.library_sources()[module]
 assert rr['input']['module_source_sha256']==canonical.digest(source)
 for stream in ('stdout','stderr'):
  sd=base64.b64decode(rr[stream]['content_b64'],validate=True)
  assert rr[stream]['byte_count']==len(sd) and rr[stream]['sha256']==canonical.digest(sd)
 assert rr['requested_limits']['lean_heap_mb']==policy.get('strict')['memory_mb'] and rr['requested_limits']['wall_timeout_seconds']==str(policy.get('strict')['build_timeout_seconds'])
ck('actual initial process milestones all successful',True)
ck('telemetry not deterministic observation or support artifact map','process_evidence' not in observation and 'compile_process_evidence' not in observation and all('process' not in p for p in refs) and set(observation)==set(C.DETERMINISTIC))
output={'checks':checks,'initial_selection_only':True,'bounded_axiom_result':'Actual support axioms are allowed and their inclusion/BASE declaration identity are independently recomputed from retained raw BASE plus full selected exports.','no_new_kernel_native_or_model_execution':True}
(root/'capture-checks.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
