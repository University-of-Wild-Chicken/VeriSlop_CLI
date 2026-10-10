from __future__ import annotations
import base64,copy,datetime,hashlib,itertools,json,pathlib,sys,tempfile
from unittest.mock import patch
OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'runtime'))
from verislop import canonical,leanbridge,sandbox,review_projection
from verislop.errors import Diagnostic
from verislop.evidence import EvidenceStore
from verislop.bridges.manifest import InvalidPackage
from verislop.bridges import vscore3_checker as checker
H=canonical.digest(b'fresh unrelated generic fixture binding')
rows=[]
def check(label,passed,details=None):
 rows.append({'id':label,'pass':bool(passed),'details':details})
 if not passed:raise AssertionError(label)
with tempfile.TemporaryDirectory(prefix='generic-telemetry-audit-') as tmp:
 root=pathlib.Path(tmp);tc=leanbridge.Toolchain('synthetic-pin',root/'toolchain')
 # Independent complete-result acceptance matrix. sandbox.run is always mocked.
 for index,(named,rc,timed,error,artifact) in enumerate(itertools.product((False,True),(0,3,-9),(False,True),(False,True),(False,True))):
  source=b'fresh unrelated literal source '+str(index).encode();stage=root/('case-'+str(index))
  output=(b'{"severity":"error","data":"fresh fixture error","pos":{"line":2,"column":3}}\n' if error else b'non-json output\xff\n')
  stderr=b'INTERNAL PANIC: out of memory\n' + b'x'*4100 + b'\xff\x00end'
  seen={}
  def completed(argv,cwd,**kwargs):
   seen.update(argv=list(argv),cwd=str(cwd.resolve()),kwargs=kwargs)
   if artifact:
    p=cwd/argv[argv.index('-o')+1];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture compiled bytes')
   return sandbox.SandboxResult(['fixture-launcher','--',*argv],rc,output,stderr,timed,0.03125,{'fixture':True,'read_only_paths':[]})
  with patch.object(sandbox,'run',side_effect=completed):
   if named:result,parts=leanbridge.compile_named_module(tc,stage,'Generic.Telemetry',source,{},read_only=[],timeout=11.75,memory_mb=19)
   else:result=leanbridge.compile_module(tc,source,stage,timeout=11.75,memory_mb=19);parts=None
  expected=rc==0 and not timed and not error and artifact
  check('acceptance-matrix:'+str(index),result.ok==expected,{'named':named,'rc':rc,'timed_out':timed,'parsed_error':error,'artifact':artifact,'expected_ok':expected,'actual_ok':result.ok})
  p=result.process_evidence
  check('exact-observations:'+str(index),p['returncode']==rc and p['timed_out']==timed and p['requested_argv']==seen['argv'] and p['launcher_argv']==['fixture-launcher','--',*seen['argv']] and p['working_directory']==seen['cwd'])
  check('exact-input:'+str(index),p['input']['module_source_sha256']==canonical.digest(source) and p['input']['module']==('Generic.Telemetry' if named else leanbridge.MODULE) and p['input']['setup_sha256']==(canonical.digest((stage/'setup.json').read_bytes()) if named else None))
  for channel,data in [('stdout',output),('stderr',stderr)]:
   check('full-output:'+str(index)+':'+channel,p[channel]['byte_count']==len(data) and p[channel]['sha256']==canonical.digest(data) and base64.b64decode(p[channel]['content_b64'],validate=True)==data)
  check('requested-boundaries:'+str(index),p['requested_limits']=={'lean_heap_mb':19,'sandbox_address_space_bytes':(19+leanbridge.LEAN_AS_HEADROOM_MB)*1024*1024,'sandbox_cpu_soft_seconds':16,'sandbox_cpu_hard_seconds':21,'sandbox_file_size_bytes':leanbridge.COMPILE_FILE_SIZE_MB*1024*1024,'sandbox_core_bytes':0,'wall_timeout_seconds':'11.75'} and seen['kwargs']['memory_mb']==19+leanbridge.LEAN_AS_HEADROOM_MB and seen['kwargs']['cpu_seconds']==16)
  check('no-causal-overclaim:'+str(index),p['reported_stderr_panics']==[{'kind':'out_of_memory','report':'INTERNAL PANIC: out of memory'}] and not {'peak_rss','termination_signal','host_oom','failed_boundary','resource_cause'}&set(p))
  check('canonical-roundtrip:'+str(index),canonical.loads(canonical.dumps(p))==p)
 # Actual registered evidence storage plus the downstream closed release normalizer.
 baseline={'bridge_id':'generic','edge_id':'generic-edge','plan_hash':H,'artifacts_hash':H,'semantic_edge_root':H,'template':checker.T.TEMPLATE,'proposition_hash':H,'proof_symbol':checker.T.EDGE_THEOREM,'edge_axioms':[],'inputs':{'proof_source':{'slot_id':'vscore-proof','sha256':H}},'accepted_modules':[],'obligations':['P'],'implementation_ir_hash':H,'builds':[H,H],'certificate_descriptor_hash':H,'semantic_acceptance':True,'assigns_end_to_end_verified':False}
 check('actual-producer-base-field-set',set(baseline)==review_projection.RESULT_FIELDS[checker.VERIFIER][0])
 process=leanbridge._compile_process_evidence(sandbox.SandboxResult(['fixture-launcher','lean'],0,b'fixture output',b'',False,0.125,{}),argv=['lean'],working_directory='/fixture',module=checker.T.PROOF_MODULE,source=b'fresh generic proof',timeout=12.5,memory_mb=19,cpu_seconds=17)
 inventory={'format':'verislop.vscore-compile-process-inventory/1','builds':{'A':{checker.T.PROOF_MODULE:{'availability':'available','record':process}},'B':{checker.T.PROOF_MODULE:{'availability':'available','record':copy.deepcopy(process)}}}}
 retained=[]
 for label,payload in [('legacy',baseline),('new-telemetry',{**baseline,'compile_process_evidence':inventory})]:
  store_path=OUT/'witness-publications'/label
  ev=EvidenceStore(store_path,'generic-audit').record(claim_id='GENERIC',verifier_id=checker.VERIFIER,status='PASS',scope=['Synthetic producer-format compatibility only; no semantic proof claim'],input_root=H,result=payload,invocation=['synthetic-audit-fixture'])
  try:
   fmt,normalized=review_projection.normalize(ev.record,ev.result)
   observation={'accepted':True,'format':fmt,'normalized':normalized}
  except InvalidPackage as exc:
   observation={'accepted':False,'code':exc.code,'message':str(exc)}
  retained.append({'label':label,'evidence_id':ev.id,'record':ev.record,'raw':ev.result,'normalizer':observation})
 check('legacy-normalizer-compatible',retained[0]['normalizer']['accepted'])
 check('new-telemetry-normalizer-rejected',not retained[1]['normalizer']['accepted'] and retained[1]['normalizer']['code']=='STALE_OR_UNBOUND_EVIDENCE' and retained[1]['normalizer']['message']=='unknown or missing raw result fields for verislop.vscore3-checker')
 (OUT/'normalizer-counterexample.json').write_text(json.dumps({'scope':'Actual EvidenceStore and exact release normalizer; synthetic unrelated producer payload; no kernel/native/model invocation.','observations':retained,'conclusion':'Current successful .3 producer results now contain an additive field outside the exact registered release-normalizer alternatives. Legacy format passes; new format fails before semantic projection.'},indent=2)+'\n')
 (OUT/'independent-checks.json').write_text(json.dumps({'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':rows,'counts':{'pass':sum(r['pass'] for r in rows),'fail':sum(not r['pass'] for r in rows)},'mocked':{'sandbox.run':'All compiler results; no real subprocesses or Lean invocations.'}},indent=2)+'\n')
 print(json.dumps({'pure_checks':len(rows),'result':'PASS_CHECKS_WITH_ONE_REPRODUCED_COMPATIBILITY_DEFECT','normalizer_counterexample':retained[1]['normalizer']},indent=2))
