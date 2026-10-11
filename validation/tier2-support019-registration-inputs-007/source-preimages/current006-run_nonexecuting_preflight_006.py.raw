from pathlib import Path
import json, os, subprocess, datetime, time, hashlib
root=Path('/home/augustus/VeriSlop_CLI')
p=root/'validation/tier2-support019-registration-inputs-006/preflight-006'
reg=json.loads((p/'registration-before-execution.json').read_text())
def guard():
 return {name:{'path':name,'sha256':'sha256:'+hashlib.sha256((root/name).read_bytes()).hexdigest(),'byte_count':(root/name).stat().st_size} for name in reg['source_guards']}
before=guard();assert before==reg['source_guards'] and before
assert all(not(p/name).exists() for name in ['stdout.log','stderr.log','actual-process-receipt.json'])
env=os.environ.copy();env.update(reg['environment']);started=datetime.datetime.now(datetime.timezone.utc).isoformat();clock=time.monotonic()
with(p/'stdout.log').open('xb') as out,(p/'stderr.log').open('xb') as err:
 child=subprocess.Popen(reg['argv'],cwd=reg['cwd'],env=env,stdout=out,stderr=err);pid=child.pid;returncode=child.wait()
def ref(name):
 raw=(p/name).read_bytes();return {'path':str((p/name).relative_to(root)),'sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_count':len(raw)}
after=guard();assert before==after
receipt={'before':before,'after':after,'frozen_inputs_unchanged':before==after,'format':'verislop.nonexecuting-preflight-actual-receipt/1','argv':reg['argv'],'cwd':reg['cwd'],'registered_environment':reg['environment'],'pid':pid,'returncode':returncode,'started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'wall_seconds':time.monotonic()-clock,'timed_out':False,'timeout_seconds':None,'stdout':ref('stdout.log'),'stderr':ref('stderr.log'),'qualification_authority':False}
with(p/'actual-process-receipt.json').open('x')as out:json.dump(receipt,out,sort_keys=True,indent=2);out.write('\n')
if returncode==0:
 data=json.loads((p/'stdout.log').read_text());old=json.loads((root/reg['old191_ids_required_ref']).read_text());assert set(old['registered_test_ids'])<=set(data['test_ids']);assert set(old['test_modules'])<=set(data['test_modules']);assert data['tests_executed']==data['model_calls']==0 and data['task_inputs'] is False
 print(json.dumps({'returncode':returncode,'pid':pid,'test_count':data['test_count'],'test_modules':len(data['test_modules']),'source_files':len(data['source_files']),'test_sources':len(data['test_sources']),'source_root':data['source_root'],'previous191_preserved':True,'Q006created':(root/'validation/tier2-support-019-qualification-006').exists()}))
else:print(json.dumps(receipt))
raise SystemExit(returncode)
