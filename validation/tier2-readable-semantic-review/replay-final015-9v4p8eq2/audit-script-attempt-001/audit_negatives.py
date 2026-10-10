"""Pure replay of frozen artifacts; no Lean/compiler/provider invocation."""
from pathlib import Path
import sys,json,base64,copy
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'runtime'));sys.path.insert(0,str(root/'runtime/tests'))
from verislop import canonical,leanbridge
from verislop.bridges import vscore3_checker as C,vscore3_readable_support as RS
from verislop.targets import vscore3_target as T,vscore3_readable as R
from test_vscore3_readable import matrix_context,PROOF
outdir=root/'host-mutations';outdir.mkdir(exist_ok=True)
read=lambda label,p:(root/label/p).read_bytes()
obj=lambda label,p:canonical.loads(read(label,p))
checks=[]
def ck(name,valid,detail=None):
 assert valid,name
 checks.append({'name':name,'result':'PASS','detail':detail})
neg=root/'lowering-negative';manifest=obj('lowering-negative','manifest.json')
ck('actual negative producer format and four top-level payload refs',manifest['format']=='verislop.fresh-readable-lowering-negatives/1' and set(manifest['artifacts'])=={'dependencies.json','diagnostics.json','goal.lean','source.json'})
for p,ref in manifest['artifacts'].items():assert RS.ref(p,read('lowering-negative',p))==ref,p
ck('every actual negative top-level byte/hash/size',True,4)
dependencies=obj('lowering-negative','dependencies.json');observation=obj('A','observation.json')
ck('all thirteen dependency modules bound and identical to final positive replay',set(dependencies)==set(observation['modules'])-{T.GOAL_MODULE,T.PROOF_MODULE},len(dependencies))
for module,parts in dependencies.items():
 for suffix,h in parts.items():
  path='deps/'+leanbridge.module_relpath(module).as_posix()+suffix
  data=read('lowering-negative',path)
  assert canonical.digest(data)==h and data==read('A','modules/'+module+suffix),(module,suffix)
ck('all actual imported module-part bytes reproduced by positive replay',True,sum(map(len,dependencies.values())))
source=read('lowering-negative','source.json');goal=read('lowering-negative','goal.lean')
base=read('A','readable/base-goal.lean');correspondence=read('A','readable/correspondence.lean')
ck('same complete source bytes and exact original base goal retained',source==read('A','source.json') and goal.startswith(base+b'\n'))
ck('same original correspondence proof suffix; only readable lowering altered',goal.endswith(correspondence) and goal!=read('A','goal.lean'))
ck('exact staged failed compiler source equals retained negative goal',read('lowering-negative','compile/VeriSlopBridgeGoal.lean')==goal)
diag=obj('lowering-negative','diagnostics.json');process=diag['process_evidence']
errors=[m for m in diag['messages'] if m.get('severity')=='error'];lines=goal.decode().splitlines()
failed=[('\n'.join(lines[:m['pos']['line']]).rsplit('theorem ',1)[-1].split()[0]) for m in errors]
ck('actual compiler rejected three changed same-sort binding forms by universal rfl failures',diag['ok'] is False and diag['mutations']==['same-sort parameters','list-fold item/accumulator','nat-fold index/accumulator'] and len(errors)==8 and len(diag['errors'])==8 and all('Tactic `rfl` failed' in m['data'] for m in errors) and {'runEquals_helper_3','runEquals_helper_4','runEquals_entry_0'}.issubset(failed),{'all_failed_declarations':failed,'errors':diag['errors']})
ck('failed compiler returned claim failure, no timeout/panic, and bound exact source/setup',process['returncode']==1 and process['timed_out'] is False and process['reported_stderr_panics']==[] and process['input']['module']==T.GOAL_MODULE and process['input']['module_source_sha256']==canonical.digest(goal) and process['input']['setup_sha256']==canonical.digest(read('lowering-negative','compile/setup.json')))
for stream in ('stdout','stderr'):
 data=base64.b64decode(process[stream]['content_b64'],validate=True)
 assert len(data)==process[stream]['byte_count'] and canonical.digest(data)==process[stream]['sha256']
ck('actual failed compiler raw stdout/stderr bound by exact bytes',True)
ck('no accepted goal module exported by failed compiler',not any((neg/'compile').rglob('*.olean')))
# Reconstruct the real final generic matrix context and its exact frozen spec.
ctx=matrix_context(read('A','modules/VeriSlopContract.olean'))
spec=T.enrich_readable(T.build_goal(ctx.inputs['source'][1],ctx.relation,ctx.accepted_profile,ctx.obligations))
ctx.readable_selection=spec.readable_selection=read('A',R.SELECTION_PATH);ctx.readable_diagnostics={}
ck('host mutation context uses exact actual source/relation/profile/selected goal',ctx.inputs['source'][1]==source and canonical.dumps(ctx.relation)==read('A','relation.json') and canonical.dumps(ctx.accepted_profile)==read('A','profile.json') and spec.text.encode()==read('A','goal.lean'))
# The captured actual proof bytes are fixture-defined and hash-bound by telemetry.
proc=obj('A','compile-process.json')['SELECTED::'+T.PROOF_MODULE]['record']
ck('actual proof source telemetry agrees with frozen fixture proof bytes',proc['input']['module_source_sha256']==canonical.digest(PROOF))
modules={}
for p in (root/'A/modules').iterdir():
 for suffix in sorted(leanbridge.MODULE_SUFFIXES,key=len,reverse=True):
  if p.name.endswith(suffix):modules.setdefault(p.name[:-len(suffix)],{})[suffix]=p.read_bytes();break
actual=C.Build(copy.deepcopy(observation),obj('A','full-kernel-export.json'),modules,observation['proposition_hash'],{},observation['edge_axioms'],{},observation['readable_support'],{p:read('A',p) for p in RS.artifact_refs(observation['readable_support'],lambda p:read('A',p))})
baseline=copy.copy(actual);baseline.decls={n:c for n,c in actual.decls.items() if not n.startswith((R.NAMESPACE+'.',T.GOAL_MODULE+'.Readable.'))};baseline.observation={**actual.observation,'readable_support':None}
positive=RS.audit(ctx,spec,baseline,actual)
selection=RS.checked_json('vscore-readable-selection',ctx.readable_selection)
ck('positive host audit recomputes exact frozen CHECKED descriptor',positive['checked_descriptor']==selection['checked_descriptor'])
# These are pure mutations of actual exported records. They are NOT kernel runs.
theorem=T.GOAL_MODULE+'.Readable.runEquals_helper_0'
def saved(label,before,after):
 p=outdir/(label+'.json');p.write_bytes(canonical.dumps({'kind':'PURE_HOST_RECORD_MUTATION_NOT_KERNEL_EXECUTED','original_export_hash':canonical.digest(read('A','full-kernel-export.json')),'before':before,'after':after}))
def expect(label,code,fn):
 try:fn()
 except C.EdgeFailure as exc:
  ds=[d.to_json() for d in exc.diagnostics];assert ds[0]['code']==code,(label,ds)
  (outdir/(label+'-result.json')).write_bytes(canonical.dumps({'test_kind':'PURE_HOST_AUDIT_NOT_KERNEL_EXECUTED','expected_code':code,'observed_diagnostics':ds}))
  ck(label,True,{'code':code,'kind':'pure host mutation; no compiler replay'})
 else:raise AssertionError(label+' was accepted')
replacement=copy.copy(actual);replacement.decls=copy.deepcopy(actual.decls)
replacement.decls[theorem]['value_constants'].append(['Nat','add']);saved('changed-actual-proof-reference',actual.decls[theorem],replacement.decls[theorem])
audited=RS.audit(ctx,spec,baseline,replacement)
expect('changed-actual-proof-reference','INPUT_MUTATION',lambda:RS.attach(ctx,spec,baseline,replacement,ctx.readable_selection,audited))
unused=copy.copy(actual);unused.decls=copy.deepcopy(actual.decls);record=copy.deepcopy(unused.decls[theorem]);record['name']=[R.NAMESPACE,'unused_forbidden'];record['axioms']=[['sorryAx']];unused.decls[R.NAMESPACE+'.unused_forbidden']=record
saved('unused-forbidden-support',actual.decls[theorem],record)
expect('unused-forbidden-support','INADMISSIBLE_AXIOM',lambda:RS.audit(ctx,spec,baseline,unused))
weakened=copy.deepcopy(actual.decls);weakened[theorem]['type']={'const':['True'],'levels':[]};saved('weakened-universal-equality-type',actual.decls[theorem],weakened[theorem])
mismatches=T.statement_mismatches(spec,weakened)
(outdir/'weakened-universal-equality-type-result.json').write_bytes(canonical.dumps({'test_kind':'PURE_HOST_AUDIT_NOT_KERNEL_EXECUTED','mismatches':mismatches}))
ck('weakened-universal-equality-type',theorem in mismatches,{'actual_mismatches':mismatches,'kind':'pure host mutation; no compiler replay'})
weakenedgoal=copy.copy(actual);weakenedgoal.decls=copy.deepcopy(actual.decls);edge=T.GOAL_MODULE+'.EdgeProp';weakenedgoal.decls[edge]['value']={'const':['True'],'levels':[]};saved('weakened-original-edge-proposition',actual.decls[edge],weakenedgoal.decls[edge])
expect('weakened-original-edge-proposition','STATEMENT_MISMATCH',lambda:RS.audit(ctx,spec,baseline,weakenedgoal))
files=dict(actual.readable_artifacts);path='readable/base-kernel-export.json';old=canonical.loads(files[path]);changed=copy.deepcopy(old);next(iter(changed.values())).pop('axioms');files[path]=canonical.dumps(changed)
m=canonical.loads(files[R.MANIFEST_PATH]);next(row for row in m['artifacts'] if row['artifact']['path']==path)['artifact']=RS.ref(path,files[path]);files[R.MANIFEST_PATH]=canonical.dumps(m);desc={**actual.readable_support,'manifest':{'path':R.MANIFEST_PATH,'sha256':canonical.digest(files[R.MANIFEST_PATH])}}
saved('malformed-bound-baseline-record',next(iter(old.values())),next(iter(changed.values())))
expect('malformed-bound-baseline-record','INVALID_CANDIDATE',lambda:RS.artifact_refs(desc,files.__getitem__))
files=dict(actual.readable_artifacts);m=canonical.loads(files[R.MANIFEST_PATH]);row=next(r for r in m['support_declarations'] if r['kind']=='theorem');path=row['kernel_record']['path'];old=canonical.loads(files[path]);changed=copy.deepcopy(old);changed.pop('name');files[path]=canonical.dumps(changed);row['kernel_record']=RS.ref(path,files[path]);row['identity_hash']=canonical.digest_json({k:v for k,v in row.items() if k!='identity_hash'});next(r for r in m['artifacts'] if r['artifact']['path']==path)['artifact']=RS.ref(path,files[path]);files[R.MANIFEST_PATH]=canonical.dumps(m);desc={**actual.readable_support,'manifest':{'path':R.MANIFEST_PATH,'sha256':canonical.digest(files[R.MANIFEST_PATH])}}
saved('malformed-bound-support-record',old,changed)
expect('malformed-bound-support-record','INVALID_CANDIDATE',lambda:RS.artifact_refs(desc,files.__getitem__))
result={'format':'verislop.independent-gate015-readable-negative-checks/1','checks':checks,'scope':'Pure inspection of actual frozen015 failed lowering compilation plus pure host mutations of actual exports. Only lowering compilation is kernel-executed by captured native test. No new compiler/native/model invocation. Full selected registered pipeline and overall gate still pending.'}
(root/'negative-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
