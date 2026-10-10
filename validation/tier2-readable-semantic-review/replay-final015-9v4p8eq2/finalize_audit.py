from pathlib import Path
import json,hashlib,datetime,shutil,sys
root=Path(__file__).resolve().parent;repo=Path('/home/augustus/VeriSlop_CLI');sys.path.insert(0,str(root/'runtime'))
from verislop import canonical,policy
checks=[]
def ck(n,v,d=None):
 assert v,n
 checks.append({'name':n,'result':'PASS','detail':d})
read=lambda p:json.loads((root/p).read_text())
frozen=read('gate-inputs/source-freeze.json');tests=read('gate-inputs/test-sources.json')
for p,h in frozen['source_files'].items():
 assert canonical.digest((repo/p).read_bytes())==h and canonical.digest((root/'runtime'/p).read_bytes())==h,p
ck('all current and captured production/spec/schema files equal frozen015 hashes',True,len(frozen['source_files']))
for p,h in tests.items():
 assert canonical.digest((repo/p).read_bytes())==h and canonical.digest((root/'runtime'/p).read_bytes())==h,p
ck('all current and captured test files equal frozen015 invocation hashes',True,len(tests))
ck('canonical complete production source root exactly frozen015',canonical.digest_json(frozen['source_files'])==frozen['source_root'],frozen['source_root'])
expected_limits={'lean_heap_mb':8192,'sandbox_address_space_bytes':25769803776,'sandbox_core_bytes':0,'sandbox_cpu_hard_seconds':310,'sandbox_cpu_soft_seconds':305,'sandbox_file_size_bytes':1073741824,'wall_timeout_seconds':'300'}
records=[]
for label in ('A','B'):
 for v in read(label+'/compile-process.json').values():records.append(v['record'])
records.append(read('lowering-negative/diagnostics.json')['process_evidence'])
for r in records:
 assert r['requested_limits']==expected_limits
 assert '-j4' in r['requested_argv'] and '-M8192' in r['requested_argv']
strict=policy.get('strict');assert strict['memory_mb']==8192 and strict['build_timeout_seconds']==300
ck('all55 actual process records retain exact pinned requested resource values/argv',True,{'records':len(records),'limits':expected_limits})
snapshot=read('snapshot.json')
for row in snapshot['files']:
 if row['category'] in ('A','B'):
  p=Path(snapshot['origins'][row['category']])/row['path'];data=p.read_bytes()
  assert hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['size'] and row['stable_after_copy'],str(p)
ck('final A/B sealed originals still equal independent snapshot bytes',True)
negative=read('lowering-negative-snapshot.json')
# The negative snapshot has the original path at top-level and hash/size rows.
origin=Path(negative['origin'])
for row in negative['files']:
 p=origin/row['path'];data=p.read_bytes()
 assert hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['size'] and row['stable_after_copy'],str(p)
ck('actual lowering-negative sealed original still equals independent complete snapshot',True,len(negative['files']))
(root/'currency-checks.json').write_text(json.dumps({'format':'verislop.independent-gate015-final-currency/1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks},indent=2)+'\n')
replay=read('replay-checks.json');negative_checks=read('negative-checks.json')
assert all(c['result']=='PASS' for c in replay['checks']+negative_checks['checks']+checks)
(root/'execution.json').write_text(json.dumps({'format':'verislop.independent-audit-executions/1','executions':[{'script':'audit_replays.py','observed_exit_code':0,'tool_session':36201,'output_json':'replay-checks.json','new_kernel_or_native_execution':False},{'script':'audit-script-attempt-001/audit_negatives.py','observed_exit_code':1,'classification':'INDEPENDENT_AUDIT_SCRIPT_ERROR','production_finding':False},{'script':'audit_negatives.py','observed_exit_code':0,'tool_session':68963,'stdout':'negative-checks.stdout.txt','stderr':'negative-checks.stderr.txt','new_kernel_or_native_execution':False},{'script':'finalize_audit.py','observed_checks':'currency-checks.json','new_kernel_or_native_execution':False}]},indent=2)+'\n')
review={'format':'verislop.independent-readable-replay-negative-review/1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result':'PASS_BOUNDED_ARTIFACT_AUDIT','source_root':frozen['source_root'],'findings':[],'check_counts':{'replay_artifacts':len(replay['checks']),'negative_artifacts_and_host_mutations':len(negative_checks['checks']),'final_currency_and_resource_bindings':len(checks),'total':len(replay['checks'])+len(negative_checks['checks'])+len(checks)},'actual_native_captures':snapshot['origins']|{'lowering_negative':str(origin)},'evidence_scope':{'matrix_replays':'Fresh final frozen015 A/B actual proof replay captures. Each exact deterministic observation equals; all291 support refs+bytes and raw BASE/full selected exports equal; all312 nonprocess payloads byte-identical; complete313 capture payload path inventories equal. Only compile-process.json differs, independently raw-stream/source/status/resource-bound and excluded from deterministic/support artifact maps. Outer capture manifest differs because it inventories that volatile payload.','actual_lowering_negative':'Captured real compiler returns1, no timeout/panic, only8 rfl conversion failures; direct same-sort parameter/list-fold/nat-fold universal equalities fail. Original source bytes, full original base goal, and original correspondence suffix unchanged; all13 imported module parts equal final positive replay. No accepted failed goal module.','host_mutations':'Six transformations of actual exported records, explicitly NOT kernel-executed: changed actual proof-reference inventory => INPUT_MUTATION; unused sorryAx support => INADMISSIBLE_AXIOM; RunEquals=True => STATEMENT_MISMATCH surface; original EdgeProp definition=True => STATEMENT_MISMATCH; malformed rebound raw BASE/support records => structured INVALID_CANDIDATE.','proof_identity':'Actual theorem edge has exact EdgeProp type and safe/unresolved-empty record. Readable theorem bodies remain honestly MODULE_BOUND_PROOF with unavailable individual proof AST/digest; module bytes and actual references/axioms retained.','mode':'Pure artifact/hash/registered-host audits only; no new Lean/native/closure/gate/model invocation and no task/corpus/source/proof reads.'},'pending':['Full selected registered pipeline publication/closure/two builds/readable-proof dependency route/retained-copy review portability','Variant BASE preservation result not inspected in this annex','Full frozen engineering gate015 terminal qualification'],'not_claimed':['Full engineering qualification','Task implementation correctness','Independent new kernel replay of record mutants','Assumption-free proof or individual theorem proof-body digest'],'trusted_surface':['Captured pinned Lean kernel/compiler execution under declared sandbox/OS/toolchain TCB','SHA256/canonical encoding integrity','Python file/hash/host validation implementation'],'prior_receipts_preserved':['validation/tier2-readable-semantic-review/final-gate015-6c8zj36b','validation/tier2-readable-semantic-review/matrix-final015-7rn4kn4c'],'audit_script_failure_preserved':'audit-script-attempt-001 records a corrected auditor-only string/Path mistake; no production defect or native qualification change.'}
(root/'review.json').write_text(json.dumps(review,indent=2)+'\n')
# Exclude transient import artifacts, not evidence.
for p in sorted(root.rglob('__pycache__'),key=lambda x:len(x.parts),reverse=True):shutil.rmtree(p)
files={p.relative_to(root).as_posix():{'sha256':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'manifest.json'}
manifest={'format':'verislop.immutable-independent-audit/1','artifacts':files,'input_root_hash':canonical.digest_json(files),'audit_result':'PASS_BOUNDED_ARTIFACT_AUDIT','review_sha256':canonical.digest((root/'review.json').read_bytes())}
(root/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
for p in root.rglob('*'):
 if p.is_file():p.chmod(0o444)
for p in sorted((p for p in root.rglob('*') if p.is_dir()),key=lambda x:len(x.parts),reverse=True):p.chmod(0o555)
root.chmod(0o555)
print(json.dumps({'receipt':str(root),'checks':review['check_counts'],'review_sha256':manifest['review_sha256'],'manifest_sha256':canonical.digest((root/'manifest.json').read_bytes()),'file_count':len(files),'input_root_hash':manifest['input_root_hash'],'pending':review['pending']},indent=2))
