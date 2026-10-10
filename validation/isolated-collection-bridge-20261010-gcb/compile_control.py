import dataclasses,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from verislop import canonical,leanbridge,policy
from verislop.targets import vscore3_target as T
P=Path('validation/isolated-collection-bridge-20261010-gcb').resolve();label=sys.argv[1];path=Path(sys.argv[2]);D=P/'diagnostics'/label;D.mkdir(parents=True,exist_ok=False)
pol=policy.get('strict');tc=leanbridge.resolve_toolchain(leanbridge.DEFAULT_TOOLCHAIN)
parts_root=P/'source-admission/accepted';modules={m:leanbridge.module_parts(parts_root,m) for m in T.LIB_MODULES}
roots=[parts_root]
extra=P/'actual-module-parts'
if extra.is_dir():
 for m in (T.CONTRACT_MODULE,T.GOAL_MODULE):modules[m]=leanbridge.module_parts(extra,m)
 roots.append(extra)
deps={m:{s:str((parts_root if m in T.LIB_MODULES else extra)/(leanbridge.module_relpath(m)+s)) for s in ps} for m,ps in modules.items()}
opts={'timeout':pol['build_timeout_seconds'],'memory_mb':pol['memory_mb'],'require_network_isolation':pol['require_network_isolation'],'require_filesystem_isolation':pol['require_filesystem_isolation']}
with (P/'commands.jsonl').open('a') as f:f.write(json.dumps({'label':label,'argv':sys.argv,'cwd':str(Path.cwd()),'source_hash':canonical.digest_file(path),'dependencies':{m:{s:canonical.digest(v) for s,v in ps.items()} for m,ps in modules.items()},'policy':pol,'utc_start':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
try:
 result,parts=leanbridge.compile_named_module(tc,D/'build','GenericUniversalControls',path.read_bytes(),deps,read_only=roots,**opts)
 data=dataclasses.asdict(result);data['olean']=str(data['olean']) if data['olean'] else None
 (D/'compile.json').write_text(json.dumps(data,sort_keys=True))
 print(label,'compile_ok',result.ok,'errors',result.errors,'sorries',result.sorry_positions,flush=True)
 if result.ok and not result.sorry_positions:
  modules['GenericUniversalControls']=parts
  replay=leanbridge.run_kernel_tool_modules(tc,modules,'GenericUniversalControls',{'export':True,'axioms':True},**{**opts,'timeout':pol['kernel_timeout_seconds']})
  (D/'kernel.json').write_bytes(canonical.dumps(replay))
  print(label,'kernel replay returned',flush=True)
except BaseException as e:
 (D/'exception.json').write_text(json.dumps({'exception_type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}))
 raise
