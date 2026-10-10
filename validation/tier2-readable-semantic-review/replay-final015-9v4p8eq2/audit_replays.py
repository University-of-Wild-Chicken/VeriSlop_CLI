from pathlib import Path
import json,sys,base64
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'runtime'))
from verislop import canonical,policy,leanbridge
from verislop.exprjson import decl_hash,name_str
from verislop.bridges import vscore3_checker as C,vscore3_readable_support as RS
from verislop.targets import vscore3_target as T,vscore3_readable as R
checks=[]
def ck(n,v,d=None):
 assert v,n
 checks.append({'name':n,'result':'PASS','detail':d})
read=lambda label,p:(root/label/p).read_bytes()
obj=lambda label,p:canonical.loads(read(label,p))
outer={};observations={};support={};full={};baseline={};process={}
for label in ('A','B'):
 outer[label]=obj(label,'manifest.json')
 actual={p.relative_to(root/label).as_posix() for p in (root/label).rglob('*') if p.is_file()}
 ck(label+' exact complete outer inventory',actual=={'manifest.json',*outer[label]['artifacts']},len(actual))
 for p,ref in outer[label]['artifacts'].items():
  data=read(label,p);assert ref=={'sha256':canonical.digest(data),'size':len(data)},(label,p)
 ck(label+' all actual outer bytes/hashes/sizes',True,len(outer[label]['artifacts']))
 observation=observations[label]=obj(label,'observation.json')
 ck(label+' exact deterministic observation fields',set(observation)==set(C.DETERMINISTIC))
 support[label]=RS.artifact_refs(observation['readable_support'],lambda p:read(label,p))
 ck(label+' exact closed selected support artifact refs',set(support[label])=={p for p in actual if p.startswith(('readable/','support/readable/'))},len(support[label]))
 manifest=obj(label,R.MANIFEST_PATH);selection=RS.checked_json('vscore-readable-selection',read(label,R.SELECTION_PATH))
 ck(label+' current frozen renderer/budgets/tool identity',selection['renderer']==RS.renderer() and selection['budgets']==R.BUDGETS and observation['kernel_tool_hash']==leanbridge.kernel_tool_hash())
 rows=obj(label,'readable/declarations.json');exports=obj(label,'readable/kernel-export.json')
 baseline[label]=obj(label,'readable/base-kernel-export.json');full[label]=obj(label,'full-kernel-export.json')
 ck(label+' raw baseline identity and selected projection',canonical.digest_json({n:decl_hash(c) for n,c in sorted(baseline[label].items())})==manifest['base_declaration_identity_hash'] and {n:c for n,c in full[label].items() if c.get('module')==[T.GOAL_MODULE] and n not in exports}==baseline[label],len(baseline[label]))
 axs=sorted({name_str(a) for c in baseline[label].values() for a in c['axioms']});actualaxs=sorted({a for row in rows for a in row['axioms']})
 ck(label+' actual support axioms within raw baseline/policy',set(actualaxs)<=set(axs) and canonical.digest_json(axs)==manifest['support_axiom_baseline_hash'] and actualaxs==manifest['actual_support_axioms'] and all(policy.classify_axiom(a,policy.get('strict'))=='allowed' for a in axs))
 modules={}
 for p in (root/label/'modules').iterdir():
  for suffix in sorted(leanbridge.MODULE_SUFFIXES,key=len,reverse=True):
   if p.name.endswith(suffix):modules.setdefault(p.name[:-len(suffix)],{})[suffix]=p.read_bytes();break
 ck(label+' all module parts including actual proof',set(modules)==set(observation['modules']) and T.PROOF_MODULE in modules and all(C._parts_digest(parts)==observation['modules'][m] for m,parts in modules.items()),len(modules))
 proof={n:c for n,c in full[label].items() if c.get('module')==[T.PROOF_MODULE]}
 ck(label+' actual proof declaration and exact EdgeProp type',set(proof)=={T.PROOF_MODULE+'.edge'} and proof[T.PROOF_MODULE+'.edge']['kind']=='theorem' and proof[T.PROOF_MODULE+'.edge']['type']=={'const':[T.GOAL_MODULE,'EdgeProp'],'levels':[]} and proof[T.PROOF_MODULE+'.edge']['safety']=='safe' and proof[T.PROOF_MODULE+'.edge']['unresolved_constants']==[])
 ck(label+' actual proof/support observation binding',manifest['base_proposition_hash']==manifest['replayed_proposition_hash']==observation['proposition_hash'] and observation['compiles'][T.PROOF_MODULE]=={'ok':True,'errors':[],'sorries':0,'timed_out':False})
 process[label]=obj(label,'compile-process.json')
 compiled=set(observation['compiles'])
 ck(label+' exact complete BASE/source and SELECTED/proof phases',set(process[label])=={'BASE::'+m for m in compiled if m!=T.PROOF_MODULE}|{'SELECTED::'+m for m in compiled},len(process[label]))
 for key,v in process[label].items():
  assert v['availability']=='available';r=v['record'];phase,module=key.split('::',1)
  assert r['input']['module']==module and r['returncode']==0 and r['timed_out'] is False
  if module==T.GOAL_MODULE:source=read(label,'readable/base-goal.lean' if phase=='BASE' else 'goal.lean')
  elif module==T.PROOF_MODULE:source=None
  else:source=T.library_sources()[module]
  if source is not None:assert r['input']['module_source_sha256']==canonical.digest(source)
  for stream in ('stdout','stderr'):
   data=base64.b64decode(r[stream]['content_b64'],validate=True);assert len(data)==r[stream]['byte_count'] and canonical.digest(data)==r[stream]['sha256']
 ck(label+' every compile telemetry raw hash/source/status binding',True)
 ck(label+' process telemetry outside deterministic/support maps','compile_process_evidence' not in observation and 'process_evidence' not in observation and 'compile-process.json' not in support[label])
ck('exact A/B deterministic observations',observations['A']==observations['B'])
ck('exact A/B full selected support refs+bytes',support['A']==support['B'] and all(read('A',p)==read('B',p) for p in support['A']),len(support['A']))
ck('exact A/B full raw selected and BASE exports',full['A']==full['B'] and read('A','full-kernel-export.json')==read('B','full-kernel-export.json') and baseline['A']==baseline['B'] and read('A','readable/base-kernel-export.json')==read('B','readable/base-kernel-export.json'))
pathsA=set(outer['A']['artifacts']);pathsB=set(outer['B']['artifacts'])
ck('closed A/B capture path inventories equal',pathsA==pathsB,len(pathsA))
compared=sorted(pathsA-{'compile-process.json'})
ck('exact all A/B nonprocess actual captured artifacts',all(read('A',p)==read('B',p) for p in compared),len(compared))
ck('actual process observations vary as separated volatile evidence',process['A']!=process['B'])
output={'format':'verislop.independent-gate015-matrix-replay-checks/1','checks':checks,'artifact_comparison':{'complete_support_refs':len(support['A']),'all_capture_paths':len(pathsA),'all_nonprocess_capture_paths_compared':compared,'only_excluded_capture_payload':'compile-process.json: actual elapsed/staging-path/process observations retained and checked independently'},'scope':'Actual final frozen015 A/B proof replay capture inspection only; no new Lean/kernel/native/model execution; selected registered pipeline and full gate still pending.'}
(root/'replay-checks.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
