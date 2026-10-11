from pathlib import Path
import json, os, subprocess, datetime, time, hashlib
root=Path('/home/augustus/VeriSlop_CLI')
p=root/'validation/tier2-support019-registration-inputs-003/integration-source-tests-002'
reg=json.loads((p/'registration-before-execution.json').read_text())
assert all(not(p/name).exists() for name in ['stdout.log','stderr.log','actual-process-receipt.json'])
env=os.environ.copy();env.update(reg['environment']);started=datetime.datetime.now(datetime.timezone.utc).isoformat();clock=time.monotonic()
with(p/'stdout.log').open('xb') as out,(p/'stderr.log').open('xb') as err:
 child=subprocess.Popen(reg['argv'],cwd=reg['cwd'],env=env,stdout=out,stderr=err);pid=child.pid;returncode=child.wait()
def ref(name):
 raw=(p/name).read_bytes();return {'path':str((p/name).relative_to(root)),'sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_count':len(raw)}
receipt={'format':'verislop.generic-integration-source-check-actual-receipt/1','argv':reg['argv'],'cwd':reg['cwd'],'registered_environment':reg['environment'],'pid':pid,'returncode':returncode,'started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'wall_seconds':time.monotonic()-clock,'timed_out':False,'timeout_seconds':None,'stdout':ref('stdout.log'),'stderr':ref('stderr.log'),'qualification_authority':False}
with(p/'actual-process-receipt.json').open('x')as out:json.dump(receipt,out,sort_keys=True,indent=2);out.write('\n')
if returncode==0:
 for maps in (reg['source_files'],reg['test_sources']):
  for name, expected in maps.items():assert 'sha256:'+hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
 print(json.dumps({'returncode':returncode,'pid':pid,'registered_generic_test_count':reg['test_count'],'source_and_test_guards_unchanged':True,'task_TESTED_authority':False}))
else:print(json.dumps(receipt))
raise SystemExit(returncode)
