import os
from pathlib import Path
from types import SimpleNamespace
import argparse
from verislop import canonical, leanbridge, policy
from verislop.exprjson import name_str, const
from verislop.targets import vscore3_replay as replay, vscore3_target as target

parser=argparse.ArgumentParser()
parser.add_argument('--run-id',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parent
out=Path(os.environ.get("GROUND018_OUTPUT_ROOT",str(root)))/args.run_id
out.mkdir(exist_ok=False)
contract=b'import Init\nnamespace VeriSlopContract\ntheorem guarantee : True := True.intro\nend VeriSlopContract\n'
goal=('import VeriSlopContract\nnamespace '+target.GOAL_MODULE+'\ntheorem «Refines_G-keep» : True := True.intro\nend '+target.GOAL_MODULE+'\n').encode()
cases={'guarantee': 'theorem wrapper : True := VeriSlopContract.guarantee\ntheorem result : True := wrapper',
       'refinement': 'theorem wrapper : True := '+target.GOAL_MODULE+'.«Refines_G-keep»\ntheorem result : True := wrapper',
       'axiom': 'axiom fabricated : True\ntheorem result : True := fabricated',
       'weaker': 'theorem result : True := True.intro'}
freeze={'source_hashes':{'contract':canonical.digest(contract),'goal':canonical.digest(goal),**{key:canonical.digest(value.encode()) for key,value in cases.items()}},
        'replay_hash':canonical.digest_file(Path(replay.__file__)),'driver_hash':canonical.digest_file(Path(__file__)),
        'spec_hash':canonical.digest_file(root/'oracle-controls-002-freeze.json'),'policy_hash':policy.policy_hash(policy.get('strict'))}
(out/'frozen-inputs.json').write_bytes(canonical.dumps(freeze))
tc,pol=leanbridge.resolve_toolchain(),policy.get('strict')
modules,dependencies={},{}
for name,source in ((target.CONTRACT_MODULE,contract),(target.GOAL_MODULE,goal)):
    result,parts=leanbridge.compile_named_module(tc,out/'base-build',name,source,dependencies,read_only=[out/'imports'] if dependencies else [],timeout=30,memory_mb=pol['memory_mb'])
    (out/(name+'.json')).write_bytes(canonical.dumps({'ok':result.ok,'errors':result.errors,'process':result.process_evidence}))
    assert result.ok,result.errors
    modules[name]=parts
    dependencies[name]=leanbridge.write_module_parts(out/'imports',name,parts)
for case,body in cases.items():
    folder=out/case
    folder.mkdir()
    source=('import '+target.GOAL_MODULE+'\nnamespace '+replay.MODULE+'\n'+body+'\nend '+replay.MODULE+'\n').encode()
    (folder/'Probe.lean').write_bytes(source)
    result,parts=leanbridge.compile_named_module(tc,folder/'build',replay.MODULE,source,dependencies,read_only=[out/'imports'],timeout=30,memory_mb=pol['memory_mb'])
    (folder/'process.json').write_bytes(canonical.dumps({'ok':result.ok,'errors':result.errors,'process':result.process_evidence}))
    assert result.ok,result.errors
    request={'export':True,'export_modules':[target.CONTRACT_MODULE,target.GOAL_MODULE,replay.MODULE],'axioms':True}
    if case=='weaker':
        request['defeq']=[{'id':'ground-result','theorem':[replay.MODULE,'result'],'expr':const('False')}]
    response=leanbridge.run_kernel_tool_modules(tc,{**modules,replay.MODULE:parts},replay.MODULE,request,timeout=30,memory_mb=pol['memory_mb'])
    (folder/'kernel-response.json').write_bytes(canonical.dumps(response))
    assert response['import']['ok'] and response['replay']['ok']
    rows={name_str(row['name']):row for row in response['constants']}
    if case in ('guarantee','refinement'):
        spec=SimpleNamespace(obligations=[SimpleNamespace(lean_symbol='VeriSlopContract.guarantee')])
        try:
            replay._proof_dependencies(spec,rows,replay.THEOREM,set(modules)|{replay.MODULE})
            observed={'status':'FAIL','reason':'oracle admitted'}
        except replay.Unsupported as exc:
            observed={'status':'PASS','diagnostic':str(exc)}
    elif case=='axiom':
        axioms=[name_str(name) for name in rows[replay.THEOREM]['axioms']]
        classifications={name:policy.classify_axiom(name,pol) for name in axioms}
        observed={'status':'PASS' if any(value!='allowed' for value in classifications.values()) else 'FAIL',
                  'actual_axioms':classifications}
    else:
        check=response['defeq'][0]['result']
        observed={'status':'PASS' if check!={'ok':True,'typechecks':True,'defeq':True} else 'FAIL','actual_exact_type_check':check}
    (folder/'result.json').write_bytes(canonical.dumps(observed))
    assert observed['status']=='PASS',observed
    print(case,observed['status'],flush=True)
