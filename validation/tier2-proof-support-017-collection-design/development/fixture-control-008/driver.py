from pathlib import Path
from types import SimpleNamespace
import traceback
from verislop import canonical,export,leanbridge,policy
from verislop.package import Package
from verislop.lifecycle import applicability
from verislop.bridges import vscore3_checker as checker
from verislop.targets import vscore3_target as target
from verislop.exprjson import closure
from tests import test_vscore3_collection_bridge as fixture
root=Path(__file__).resolve().parent
original=root.parent/"fixture-attempt-002"
pkg=Package(original/"package")
result={"qualification":False,"control_boundary":"Exact actual CHECKED goal/module parts reused for development only; no registered bridge/closure acceptance", "status":"UNQUALIFIED_STARTED"}
try:
 ir,ih,cert,diags=export.verified_ir(pkg)
 assert not diags and ir is not None
 profile=canonical.load_file(pkg.root/cert['artifacts']['profile']['path'])
 obs={}
 for oid,rec in ir['obligations'].items():
  if rec['role']=='guarantee' and rec['required'] and applicability(rec)['END_TO_END_VERIFIED'][0]:
   digest=rec['formal']['formula_ref'].rsplit('@',1)[-1]
   package=canonical.load_file(pkg.path('accepted')/'expressions'/(digest[7:]+'.json'))
   obs[oid]=checker._obligation_from_package(oid,rec,package,profile)
 delivered=(original/'program.vscore.json').read_bytes()
 spec=target.enrich_readable(target.build_goal(delivered,fixture.RELATION,profile,obs))
 selection=canonical.load_file(original/'previews/selected/support/readable/selection.json')
 assert canonical.digest(spec.text.encode())==selection['checked_descriptor']['selected_goal_hash']
 (root/'regenerated-goal.lean').write_text(spec.text)
 modules={}
 saved=original/'previews/selected/modules'
 for module in (*target.LIB_MODULES,target.CONTRACT_MODULE,target.GOAL_MODULE):
  modules[module]={s:(saved/(module+s)).read_bytes() for s in leanbridge.MODULE_SUFFIXES if (saved/(module+s)).is_file()}
 dependencies={m:leanbridge.write_module_parts(root/'deps',m,ps) for m,ps in modules.items()}
 tc=leanbridge.resolve_toolchain(cert['toolchain']['pin'])
 pol=next(p for p in policy.POLICIES.values() if p['id']==cert['policy']['id'])
 for label,baseline in [('baseline',True),('positive',False)]:
  proof=fixture.bridge_proof(spec,baseline=baseline)
  (root/(label+'.lean')).write_bytes(proof)
  compiled,parts=leanbridge.compile_named_module(tc,root/label,target.PROOF_MODULE,proof,dependencies,
      read_only=[root/'deps'],timeout=pol['build_timeout_seconds'],memory_mb=pol['memory_mb'],
      require_network_isolation=pol['require_network_isolation'],require_filesystem_isolation=pol['require_filesystem_isolation'])
  record={"qualification":False,"ok":compiled.ok,"errors":compiled.errors,"messages":compiled.messages,
          "raw_stderr":compiled.raw_stderr,"sorry_positions":compiled.sorry_positions,
          "process_evidence":leanbridge.compile_process_details(compiled)}
  (root/(label+'-compile.json')).write_bytes(canonical.dumps(record))
  print(label,compiled.ok,compiled.errors,flush=True)
  if baseline:
   assert not compiled.ok
   continue
  assert compiled.ok,compiled.errors
  audited_modules={**modules,target.PROOF_MODULE:parts}
  kernel=leanbridge.run_kernel_tool_modules(tc,audited_modules,target.PROOF_MODULE,{'export':True,'axioms':True},
      timeout=pol['kernel_timeout_seconds'],memory_mb=pol['memory_mb'],require_network_isolation=True,require_filesystem_isolation=True)
  (root/'positive-kernel.json').write_bytes(canonical.dumps(kernel))
  audit=checker._audit(tc,SimpleNamespace(claim={'claim_id':'UNQUALIFIED_DEVELOPMENT'},policy=pol,acceptance=cert),spec,kernel,audited_modules,{},compiled.isolation,True)
  assert fixture.SUPPORT_NAMES <= fixture.proof_dependencies({target.EDGE_THEOREM},audit.decls)
  (root/'positive-audit.json').write_bytes(canonical.dumps(audit.observation))
 result['status']='UNQUALIFIED_REAL_CONTROL_PASS'
except BaseException as exc:
 result.update(status='UNQUALIFIED_CONTROL_FAILED',error={'type':type(exc).__name__,'message':str(exc)})
 (root/'exception.txt').write_text(traceback.format_exc())
 raise
finally:
 (root/'development-result.json').write_bytes(canonical.dumps(result))
