"""Frozen unrelated negative controls through actual construction/kernel calls."""
from pathlib import Path
from types import SimpleNamespace
import argparse
import copy
import importlib.util
import time
from verislop import canonical, dsl, leanbridge, policy
from verislop.targets import vscore3_replay as replay, vscore3_target as target

parser = argparse.ArgumentParser()
parser.add_argument('--run-id', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
out = root / args.run_id
out.mkdir(exist_ok=False)
load = importlib.util.spec_from_file_location('ground018_explore', root / 'explore.py')
explore = importlib.util.module_from_spec(load)
load.loader.exec_module(explore)
identity, identity_contract, _ = explore.fixture('identity')
bounded, _, _ = explore.fixture('bounded')
formula = copy.deepcopy(bounded.obligations[0].formula)
formula['body']['right']['body'] = {'tag': 'le', 'left': {'tag': 'var', 'index': 0},
                                  'right': {'tag': 'nat', 'value': '3'}}
profile = {'profile_id': 'ground018-unrelated', 'dsl': dsl.ENCODING_V2,
           'symbols': {'transform': {'lean_decl': 'VeriSlopContract.reference', 'args': ['Int'], 'result': 'Int'}}}
failure = target.build_goal(identity.source_bytes, {'bindings': [{'symbol': 'transform', 'entry': 'transform'}]},
                            profile, {'GENERIC': {'formula': formula, 'source_facets': [],
                            'lean_symbol': 'VeriSlopContract.guarantee', 'statement_hash': canonical.digest_json(formula)}})
from verislop.reify import _Denoter
exact = target.Printer().term(_Denoter(dsl.Profile.from_json(profile)).formula(formula, []))
failure_contract = ('import VSCore3\nnamespace VeriSlopContract\ndef reference (x : Int) : Int := x\n'
                    'theorem guarantee : ' + exact + ' := by\n  intro x\n  constructor\n  · rfl\n'
                    '  · intro n hlo hhi\n    exact Nat.le_of_lt hhi\nend VeriSlopContract\n')
stale = copy.deepcopy(identity)
stale.source_bytes = explore.fixture('mutant')[0].source_bytes
forged = target.enrich_readable(identity)
assert 'with_unfolding_all exact (env).1' in forged.text
forged.text = forged.text.replace('with_unfolding_all exact (env).1', 'with_unfolding_all exact (0 : Int)', 1)
base = copy.deepcopy(identity)
base.readable_selection = canonical.dumps({'mode': 'BASE', 'status': 'not_CHECKED'})
cases = {'source-stale': (stale, identity_contract), 'module-inventory': (identity, identity_contract),
         'export-count': (identity, identity_contract), 'normative-source-tamper': (identity, identity_contract),
         'forged-readable': (forged, identity_contract), 'compile-failure': (failure, failure_contract),
         'base-readable': (base, identity_contract)}
manifest = {'driver': canonical.digest_file(Path(__file__)), 'freeze': canonical.digest_file(root / 'negative-controls-007-freeze.json'),
            'replay': canonical.digest_file(Path(replay.__file__)),
            'printer': canonical.digest_file(Path('verislop/targets/vscore_source.py'))}
for name, (spec, contract) in cases.items():
    folder = out / name
    folder.mkdir()
    (folder / 'Goal.lean').write_text(spec.text)
    (folder / 'source.json').write_bytes(spec.source_bytes)
    (folder / 'Contract.lean').write_text(contract)
    for path in folder.iterdir():
        manifest[str(path.relative_to(out))] = canonical.digest_file(path)
(out / 'frozen-inputs.json').write_bytes(canonical.dumps(manifest))
tc, pol = leanbridge.resolve_toolchain(), policy.get('strict')
sources = target.library_sources()
libraries = replay._library_parts(tc, pol, time.monotonic() + pol['build_timeout_seconds'], sources)
deps = {name: leanbridge.write_module_parts(out / 'imports', name, parts) for name, parts in libraries.items()}
original_compile, original_kernel, original_sources = leanbridge.compile_named_module, leanbridge.run_kernel_tool_modules, target.library_sources
for case, (spec, contract) in cases.items():
    folder = out / case
    result, _ = original_compile(tc, folder / 'contract', target.CONTRACT_MODULE, contract.encode(), deps,
                                read_only=[out / 'imports'], timeout=pol['build_timeout_seconds'], memory_mb=pol['memory_mb'])
    (folder / 'contract-process.json').write_bytes(canonical.dumps({'ok': result.ok, 'errors': result.errors, 'process': result.process_evidence}))
    assert result.ok, result.errors
    ctx = SimpleNamespace(policy=pol, contract_module=result.olean.read_bytes())
    serial, tampered = [0], [False]
    def compile_capture(*a, **kw):
        result, parts = original_compile(*a, **kw)
        n = serial[0]
        serial[0] += 1
        (folder / ('compile-%d.lean' % n)).write_bytes(a[3])
        (folder / ('compile-%d.json' % n)).write_bytes(canonical.dumps({'module': a[2], 'ok': result.ok,
                 'errors': result.errors, 'timed_out': result.timed_out, 'process': result.process_evidence}))
        return result, parts
    def kernel_capture(*a, **kw):
        response = original_kernel(*a, **kw)
        (folder / 'kernel-response-original.json').write_bytes(canonical.dumps(response))
        (folder / 'kernel-request.json').write_bytes(canonical.dumps(a[3]))
        if case == 'module-inventory':
            response['import']['modules'].append({'name': ['UnboundControl018'], 'staged': True})
        if case == 'export-count':
            row = next(row for row in response['constants'] if row.get('module') == [target.CONTRACT_MODULE])
            response['constants'].remove(row)
        if case == 'normative-source-tamper':
            tampered[0] = True
        (folder / 'kernel-response-control.json').write_bytes(canonical.dumps(response))
        return response
    def source_provider():
        current = original_sources()
        if tampered[0]:
            name = next(iter(current))
            current[name] += b'\n'
        return current
    leanbridge.compile_named_module, leanbridge.run_kernel_tool_modules = compile_capture, kernel_capture
    target.library_sources = source_provider
    expression = replay.ground(spec, spec.obligations[0].formula, [-2])
    (folder / 'expression.json').write_bytes(canonical.dumps(expression))
    started = time.monotonic()
    try:
        observed = replay.check(tc, ctx, spec, expression, deadline=started + 30)
        outcome = {'status': 'NOT_REPRODUCED' if observed['predicate'] else 'CONFIRMED', 'observed': observed}
    except (replay.Unsupported, dsl.BudgetExceeded) as exc:
        outcome = {'status': 'UNSUPPORTED', 'observed': None, 'diagnostic': str(exc)}
    outcome['elapsed_seconds'] = str(time.monotonic() - started)
    (folder / 'result.json').write_bytes(canonical.dumps(outcome))
    if case == 'base-readable':
        assert outcome['status'] == 'NOT_REPRODUCED' and outcome['observed']['strategy_id'] == replay.STRATEGY
    else:
        assert outcome['status'] == 'UNSUPPORTED' and outcome['observed'] is None, outcome
    if case == 'compile-failure':
        attempts = canonical.loads(outcome['diagnostic'].split('; proof_attempts=', 1)[1].encode())
        assert len(attempts) == 2 and all(not row['compiler_ok'] for row in attempts), outcome
    print(case, outcome['status'], flush=True)
    target.library_sources = original_sources
    leanbridge.compile_named_module, leanbridge.run_kernel_tool_modules = original_compile, original_kernel
