"""Actual finite shared-deadline exits after genuine compiler/kernel executions."""
import os
from pathlib import Path
from types import SimpleNamespace
import argparse
import importlib.util
import time
from verislop import canonical, dsl, leanbridge, policy
from verislop.targets import vscore3_replay as replay, vscore3_target as target

parser=argparse.ArgumentParser()
parser.add_argument('--run-id', required=True)
parser.add_argument('--case', choices=('before-second-options', 'after-kernel-replay', 'terminal-second-diagnostic'))
args=parser.parse_args()
root=Path(__file__).resolve().parent
out=Path(os.environ.get("GROUND018_OUTPUT_ROOT",str(root)))/args.run_id
out.mkdir(exist_ok=False)
module_spec=importlib.util.spec_from_file_location('ground018_explore',root/'explore.py')
explore=importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(explore)
spec,contract,_=explore.fixture('identity')
from control_fixtures import construction_failure
failure_spec,failure_contract=construction_failure(explore)
if args.case == 'terminal-second-diagnostic':
    spec,contract=failure_spec,failure_contract
freeze={'fixture_source':canonical.digest(spec.source_bytes),'formula':canonical.digest_json(spec.obligations[0].formula),
        'contract':canonical.digest(contract.encode()),'driver':canonical.digest_file(Path(__file__)),
        'replay':canonical.digest_file(Path(replay.__file__)),
        'control_helper':canonical.digest_file(root/'control_fixtures.py'),
        'terminal_control':{'goal':canonical.digest(failure_spec.text.encode()),'source':canonical.digest(failure_spec.source_bytes),
                            'formula':canonical.digest_json(failure_spec.obligations[0].formula),'contract':canonical.digest(failure_contract.encode())},
        'prospective_spec':canonical.digest_file(root/'diagnostic-controls-003-freeze.json'),
        'limits':{'deadline_seconds':30,'max_polarity_compilations':2,'maxRecDepth':100000,'maxHeartbeats':2000000}}
(out/'frozen-inputs.json').write_bytes(canonical.dumps(freeze))
tc,pol=leanbridge.resolve_toolchain(),policy.get('strict')
libraries=replay._library_parts(tc,pol,time.monotonic()+pol['build_timeout_seconds'],target.library_sources())
deps={m:leanbridge.write_module_parts(out/'imports',m,p) for m,p in libraries.items()}
cr,_=leanbridge.compile_named_module(tc,out/'contract',target.CONTRACT_MODULE,contract.encode(),deps,read_only=[out/'imports'],timeout=pol['build_timeout_seconds'],memory_mb=pol['memory_mb'])
assert cr.ok,cr.errors
ctx=SimpleNamespace(policy=pol,contract_module=cr.olean.read_bytes())
expression=replay.ground(spec,spec.obligations[0].formula,[-2])
original_compile,original_kernel,original_attempt=leanbridge.compile_named_module,leanbridge.run_kernel_tool_modules,replay._attempt
for case in ([args.case] if args.case else ('before-second-options','after-kernel-replay','terminal-second-diagnostic')):
    folder=out/case
    folder.mkdir()
    deadline=time.monotonic()+30
    if case=='terminal-second-diagnostic' and args.case is None:
        spec,contract=failure_spec,failure_contract
        cr,_=original_compile(tc,folder/'contract',target.CONTRACT_MODULE,contract.encode(),deps,read_only=[out/'imports'],timeout=pol['build_timeout_seconds'],memory_mb=pol['memory_mb'])
        assert cr.ok,cr.errors
        ctx=SimpleNamespace(policy=pol,contract_module=cr.olean.read_bytes())
        expression=replay.ground(spec,spec.obligations[0].formula,[-2])
        deadline=time.monotonic()+30
    (folder/'Goal.lean').write_text(spec.text)
    (folder/'Contract.lean').write_text(contract)
    (folder/'expression.json').write_bytes(canonical.dumps(expression))
    serial=[0]
    def compile_capture(*a,**kw):
        result,parts=original_compile(*a,**kw)
        index=serial[0]
        serial[0]+=1
        (folder/('compile-%d.lean'%index)).write_bytes(a[3])
        (folder/('compile-%d.json'%index)).write_bytes(canonical.dumps({'module':a[2],'ok':result.ok,'errors':result.errors,'process':result.process_evidence}))
        if case=='before-second-options' and a[2]==replay.MODULE and not result.ok:
            time.sleep(max(0,deadline-time.monotonic())+0.03)
        return result,parts
    def kernel_capture(*a,**kw):
        response=original_kernel(*a,**kw)
        (folder/'kernel-response.json').write_bytes(canonical.dumps(response))
        if case=='after-kernel-replay':
            time.sleep(max(0,deadline-time.monotonic())+0.03)
        return response
    def attempt_capture(*a,**kw):
        result=original_attempt(*a,**kw)
        if case=='terminal-second-diagnostic' and a[3]==2:
            time.sleep(max(0,deadline-time.monotonic())+0.03)
        return result
    leanbridge.compile_named_module,leanbridge.run_kernel_tool_modules=compile_capture,kernel_capture
    replay._attempt=attempt_capture
    started=time.monotonic()
    try:
        replay.check(tc,ctx,spec,expression,deadline=deadline)
        result={'status':'UNEXPECTED_OBSERVATION'}
    except (dsl.BudgetExceeded,replay.Unsupported) as exc:
        text=str(exc)
        attempts=canonical.loads(text.split('; proof_attempts=',1)[1].encode())
        result={'status':'UNSUPPORTED','exception':type(exc).__name__,'observed':None,'diagnostic':text,
                'attempts':len(attempts),'prior_failure_retained':not attempts[0]['compiler_ok'],
                'elapsed_seconds':str(time.monotonic()-started)}
        assert result['prior_failure_retained']
        assert len(attempts)==(1 if case=='before-second-options' else 2)
    (folder/'result.json').write_bytes(canonical.dumps(result))
    assert result['status']=='UNSUPPORTED'
    assert result['exception']=='BudgetExceeded',result
    print(case,result['status'],result['attempts'],flush=True)
leanbridge.compile_named_module,leanbridge.run_kernel_tool_modules=original_compile,original_kernel
replay._attempt=original_attempt
