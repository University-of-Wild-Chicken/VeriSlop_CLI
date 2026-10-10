from pathlib import Path
from types import SimpleNamespace
import argparse
from verislop import canonical, leanbridge, policy
from verislop.exprjson import name_str
from verislop.targets import vscore3_replay as replay, vscore3_target as target

parser = argparse.ArgumentParser()
parser.add_argument('--run-id', required=True)
args = parser.parse_args()
out = Path(__file__).resolve().parent / args.run_id
out.mkdir(exist_ok=False)
sources = {
    target.GOAL_MODULE: ('import Init\nnamespace ' + target.GOAL_MODULE + '\ntheorem «Transfer_G.filter» : True := True.intro\nend ' + target.GOAL_MODULE + '\n').encode(),
    replay.MODULE: ('import ' + target.GOAL_MODULE + '\nnamespace ' + replay.MODULE + '\ntheorem wrapper : True := ' + target.GOAL_MODULE + '.«Transfer_G.filter»\ntheorem result : True := wrapper\nend ' + replay.MODULE + '\n').encode()}
freeze = {'source_sha256': {name: canonical.digest(data) for name,data in sources.items()},
    'verifier_sha256': canonical.digest_file(Path(replay.__file__)),
    'driver_sha256': canonical.digest_file(Path(__file__)),
    'prospective_spec_sha256': canonical.digest_file(Path(__file__).with_name('name-control-001-freeze.json'))}
(out/'frozen-inputs.json').write_bytes(canonical.dumps(freeze))
tc, pol = leanbridge.resolve_toolchain(), policy.get('strict')
parts, dependencies = {}, {}
for name,source in sources.items():
    (out/(name+'.lean')).write_bytes(source)
    result,data = leanbridge.compile_named_module(tc,out/'compile',name,source,dependencies,read_only=[out/'compile'],timeout=30,memory_mb=pol['memory_mb'])
    (out/(name+'.process.json')).write_bytes(canonical.dumps({'ok':result.ok,'errors':result.errors,'process':result.process_evidence}))
    assert result.ok, result.errors
    parts[name]=data
    dependencies[name]=leanbridge.write_module_parts(out/'compile',name,data)
response=leanbridge.run_kernel_tool_modules(tc,parts,replay.MODULE,{'export':True,'export_modules':list(parts),'axioms':True},timeout=30,memory_mb=pol['memory_mb'])
(out/'kernel-response.json').write_bytes(canonical.dumps(response))
assert response['import']['ok'] and response['replay']['ok']
decls={name_str(row['name']):row for row in response['constants']}
spec=SimpleNamespace(obligations=[SimpleNamespace(lean_symbol='VeriSlopContract.guarantee')])
try:
    result={'status':'ADMITTED_ORACLE','audit':replay._proof_dependencies(spec,decls,replay.THEOREM,set(parts))}
except replay.Unsupported as exc:
    result={'status':'REJECTED_ORACLE','diagnostic':str(exc)}
(out/'result.json').write_bytes(canonical.dumps(result))
print(result['status'])
