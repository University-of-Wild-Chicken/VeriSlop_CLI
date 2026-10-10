"""Reusable current-source qualification; never imports previous PASS evidence."""
from pathlib import Path
import argparse
import importlib.util
import os
import subprocess
import sys
from verislop import canonical, leanbridge, policy
from verislop.exprjson import app, const, name_str
from verislop.targets import vscore3_replay as replay, vscore3_target as target

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path.cwd()


def load(path):
    return canonical.loads(path.read_bytes())


def relevant_paths():
    from verislop import dsl, fsutil, exprjson, reify, review_counterexamples, review
    from verislop.targets import vscore3_source, vscore_source, vscore_target
    modules = (canonical, leanbridge, policy, dsl, fsutil, exprjson, reify, replay, target,
               vscore3_source, vscore_source, vscore_target, review_counterexamples, review)
    paths = [Path(module.__file__) for module in modules]
    paths += [target.LIB_ROOT / target.module_path(module) for module in target.library_sources()]
    paths += [WORKSPACE / 'verislop/lean/VeriSlopKernel.lean',
              WORKSPACE / 'tests/test_vscore3_ground_support_018.py',
              WORKSPACE / 'tests/test_vscore3_review_replay.py']
    paths += [ROOT / name for name in ('explore.py', 'negative_controls.py', 'oracle_controls.py',
              'name_control.py', 'deadline_controls.py', 'qualification.py', 'baseline-vscore3_replay.py',
              'specification.json', 'qualification-plan.json', 'evidence-contract.json', 'activation-001.json',
              'recipe-001.json', 'export-frontier-005-freeze.json', 'frontier-evidence-006-freeze.json',
              'negative-controls-007-freeze.json', 'clean-builds-008-freeze.json', 'qualification-hook-009-freeze.json',
              'name-control-001-freeze.json', 'diagnostic-controls-003-freeze.json', 'oracle-controls-002-freeze.json')]
    return sorted(set(path.resolve() for path in paths))


def current_map(paths):
    return {str(path.relative_to(WORKSPACE)): canonical.digest_file(path) for path in paths}


def validate_fixtures(folder, expected):
    module_spec = importlib.util.spec_from_file_location('ground018_qualification_fixture', ROOT / 'explore.py')
    explore = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(explore)
    outcomes = load(folder / 'outcomes.json')
    assert len(outcomes) == 8
    projection = []
    for result in outcomes:
        name, index = result['fixture'], result['assignment']
        assert result['status'] == expected[name], result
        assignment = folder / name / ('assignment-%d' % index)
        if result['status'] == 'UNSUPPORTED':
            errors = [load(path) for path in sorted(assignment.glob('compile-*.json'))]
            attempts = [row for row in errors if row['module'] == replay.MODULE]
            assert len(attempts) == 2 and all(not row['ok'] for row in attempts)
            assert all(any('failed to synthesize' in error and 'Decidable' in error for error in row['errors']) for row in attempts)
            assert result['observed'] is None
            continue
        observed, response = result['observed'], load(assignment / 'kernel-response.json')
        expression = load(assignment / 'expression.json')
        polarity = result['status'] == 'NOT_REPRODUCED'
        exact = expression if polarity else app(const('Not'), expression)
        assert response['import']['ok'] and response['replay']['ok']
        assert response['defeq'][0]['result'] == {'ok': True, 'typechecks': True, 'defeq': True}
        rows = {name_str(row['name']): row for row in response['constants']}
        theorem = rows[replay.THEOREM]
        assert theorem['kind'] == 'theorem' and theorem['safety'] == 'safe'
        assert target.same_expr(theorem['type'], exact)
        assert observed['result_type_hash'] == canonical.digest_json(exact)
        assert observed['ground_expression_hash'] == canonical.digest_json(expression)
        assert observed['predicate'] is polarity and observed['kernel_replay'] is True
        assert sorted(name_str(name) for name in theorem['axioms']) == observed['axioms']
        assert all(policy.classify_axiom(name, policy.get('strict')) == 'allowed' for name in observed['axioms'])
        spec, _, _ = explore.fixture(name)
        goal = {key: row for key, row in rows.items() if row.get('module') == [target.GOAL_MODULE]}
        assert not target.statement_mismatches(spec, goal)
        assert canonical.dumps(target.reexport(spec, goal)['program']) == spec.source_bytes
        compilation = [load(path) for path in sorted(assignment.glob('compile-*.json'))]
        attempts = [row for row in compilation if row['module'] == replay.MODULE]
        assert 1 <= len(attempts) <= 2
        if 'proof_attempts' in observed:
            assert len(attempts) == len(observed['proof_attempts'])
            assert float(result['elapsed_seconds']) < 30
            assert all(0 < float(row['timeout_seconds']) <= 30 for row in compilation)
            assert 0 < float(load(assignment / 'kernel-options.json')['timeout_seconds']) <= 30
            assert len(canonical.dumps(observed['proof_attempts'])) <= replay.DIAGNOSTIC_WIRE_BYTES
            requested = load(assignment / 'kernel-request.json')['export_modules']
            assert requested == [target.CONTRACT_MODULE, target.GOAL_MODULE, replay.MODULE]
            replay_counts = {name_str(row['name']): row['constants'] for row in response['replay']['modules']}
            assert all(sum(row.get('module') == [module] for row in response['constants']) == replay_counts[module] for module in requested)
            actual_dependencies = replay._proof_dependencies(spec, rows, replay.THEOREM, set(requested))
            assert all(observed['proof_dependencies'][key] == value for key, value in actual_dependencies.items())
            assert observed['proof_dependencies']['precontract_library_sources'] == {
                module: canonical.digest(source) for module, source in sorted(target.library_sources().items())}
            for path in assignment.glob('compile-*.lean'):
                text = path.read_text()
                if 'namespace ' + replay.MODULE in text:
                    assert 'maxRecDepth 100000' in text and 'maxHeartbeats 2000000' in text
                    assert 'smartUnfolding false' in text and replay.PROOF in text
        projection.append({'fixture': name, 'assignment': index, 'status': result['status'],
            'ground_expression_hash': observed['ground_expression_hash'], 'result_type_hash': observed['result_type_hash'],
            'axioms': observed['axioms'], 'modules': observed['modules'], 'proof_dependencies': observed.get('proof_dependencies')})
    return projection


def verify_controls(out):
    negative = out / 'negative'
    for name in ('source-stale', 'module-inventory', 'export-count', 'normative-source-tamper', 'forged-readable', 'compile-failure'):
        result = load(negative / name / 'result.json')
        assert result['status'] == 'UNSUPPORTED' and result['observed'] is None
    assert load(negative / 'base-readable/result.json')['status'] == 'NOT_REPRODUCED'
    failed = load(negative / 'compile-failure/result.json')
    attempts = canonical.loads(failed['diagnostic'].split('; proof_attempts=', 1)[1].encode())
    assert len(attempts) == 2 and all(not row['compiler_ok'] and row['available_rows'] > 0 for row in attempts)
    assert len(canonical.dumps(attempts)) <= replay.DIAGNOSTIC_WIRE_BYTES
    for name in ('guarantee', 'refinement', 'axiom', 'weaker'):
        assert load(out / 'oracle' / name / 'result.json')['status'] == 'PASS'
    assert load(out / 'quoted-name/result.json')['status'] == 'REJECTED_ORACLE'
    for name, count in (('before-second-options', 1), ('after-kernel-replay', 2)):
        result = load(out / 'deadline' / name / 'result.json')
        assert result['status'] == 'UNSUPPORTED' and result['observed'] is None
        assert result['attempts'] == count and result['prior_failure_retained']
    controls = load(ROOT / 'qualification-plan.json')['negative_controls']
    evidence = {'N-GR-SOURCE-STALE': 'negative/source-stale/result.json',
        'N-GR-MODULE-INVENTORY': 'negative/module-inventory/result.json',
        'N-GR-FORGED-READABLE': 'negative/forged-readable/result.json',
        'N-GR-BASE-READABLE': 'negative/base-readable/result.json',
        'N-GR-INADMISSIBLE-AXIOM': 'oracle/axiom/result.json',
        'N-GR-GUARANTEE-ORACLE': 'oracle/guarantee/result.json',
        'N-GR-REFINEMENT-ORACLE': 'oracle/refinement/result.json',
        'N-GR-WEAKER-TYPE': 'oracle/weaker/result.json',
        'N-GR-COMPILE-FAILURE': 'negative/compile-failure/result.json',
        'N-GR-BUDGET': 'deadline/before-second-options/result.json'}
    return [{'id': row['id'], 'status': 'VERIFIED', 'evidence': evidence.get(row['id'], 'units.log'),
             'scope': 'S-GR-001 preselected; S-GR-002 remains unavailable' if row['id'] == 'N-GR-BASE-READABLE' else 'actual registered control'} for row in controls]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-freeze', required=True)
    parser.add_argument('--source-manifest', required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    supplied = load(Path(args.source_manifest))
    supplied = supplied.get('files', supplied)
    assert isinstance(supplied, dict) and all(isinstance(value, str) for value in supplied.values())
    relevant = current_map(relevant_paths())
    combined = {**supplied, **relevant}
    assert all(canonical.digest_file(WORKSPACE / name) == value for name, value in supplied.items())
    before = {'format': 'verislop.ground-replay-relevant-freeze/1', 'caller_source_freeze': args.source_freeze,
              'files': combined, 'file_map_hash': canonical.digest_json(combined), 'toolchain': leanbridge.resolve_toolchain().identity(),
              'kernel_tool_hash': leanbridge.kernel_tool_hash(), 'policy_hash': policy.policy_hash(policy.get('strict'))}
    (out / 'frozen-inputs.json').write_bytes(canonical.dumps(before))
    env = dict(os.environ, GROUND018_OUTPUT_ROOT=str(out), PYTHONPATH=str(WORKSPACE))
    steps = [('baseline', ['explore.py', '--run-id', 'baseline', '--baseline']),
             ('clean-001', ['explore.py', '--run-id', 'clean-001']), ('clean-002', ['explore.py', '--run-id', 'clean-002']),
             ('negative', ['negative_controls.py', '--run-id', 'negative']), ('oracle', ['oracle_controls.py', '--run-id', 'oracle']),
             ('quoted-name', ['name_control.py', '--run-id', 'quoted-name']), ('deadline', ['deadline_controls.py', '--run-id', 'deadline'])]
    report = {'format': 'verislop.ground-replay-qualification/1', 'status': 'PENDING',
              'scope': 'Finite generic replay inputs; caller source-freeze label is bound, supplied file map is checked. Parent owns unified whole-root qualification.',
              'input_root': before['file_map_hash'], 'caller_source_freeze': args.source_freeze, 'steps': [],
              'recipe': replay.PROOF, 'strategy': 'S-GR-001', 'optional_strategy': 'S-GR-002_UNAVAILABLE',
              'forbidden_task_oracles_read': False, 'native_or_model_calls': 0, 'controls': []}
    try:
        for name, command in steps:
            with (out / (name + '.log')).open('wb') as stream:
                result = subprocess.run([sys.executable, str(ROOT / command[0]), *command[1:]], env=env, stdout=stream, stderr=subprocess.STDOUT)
            report['steps'].append({'id': name, 'rc': result.returncode, 'log': name + '.log'})
            print(name, result.returncode, flush=True)
            assert result.returncode == 0, name
        for name, module in (('units', 'tests.test_vscore3_ground_support_018'), ('existing-replay', 'tests.test_vscore3_review_replay')):
            with (out / (name + '.log')).open('wb') as stream:
                result = subprocess.run([sys.executable, '-m', 'unittest', module, '-v'], env=env, stdout=stream, stderr=subprocess.STDOUT)
            report['steps'].append({'id': name, 'rc': result.returncode, 'log': name + '.log'})
            print(name, result.returncode, flush=True)
            assert result.returncode == 0, name
        expected = {'identity': 'NOT_REPRODUCED', 'mutant': 'CONFIRMED', 'bounded': 'NOT_REPRODUCED', 'listhelper': 'NOT_REPRODUCED'}
        baseline = dict(expected, bounded='UNSUPPORTED')
        validate_fixtures(out / 'baseline', baseline)
        first, second = validate_fixtures(out / 'clean-001', expected), validate_fixtures(out / 'clean-002', expected)
        assert load(out / 'clean-001/frozen-inputs.json') == load(out / 'clean-002/frozen-inputs.json')
        assert first == second, 'clean deterministic bound inventory mismatch'
        (out / 'clean-comparison.json').write_bytes(canonical.dumps({'status': 'VERIFIED', 'exact_inventory': first,
            'inventory_hash': canonical.digest_json(first), 'clean_builds': 2}))
        report['controls'] = verify_controls(out)
        report['actual_axioms'] = sorted({axiom for row in first for axiom in row['axioms']})
        report['status'] = 'VERIFIED'
        report['claims'] = [{'id': row['id'], 'status': 'VERIFIED', 'evidence': {'C-GR-001': 'baseline/bounded/assignment-0',
            'C-GR-002': 'clean-001/outcomes.json', 'C-GR-003': 'clean-001', 'C-GR-004': 'oracle',
            'C-GR-005': 'deadline', 'C-GR-006': 'negative/compile-failure/result.json',
            'C-GR-007': 'controls', 'C-GR-008': 'clean-comparison.json'}[row['id']]} for row in load(ROOT / 'specification.json')['claim_table']]
    except Exception as exc:
        report['status'] = 'BLOCKED'
        report['diagnostic'] = type(exc).__name__ + ': ' + str(exc)
        report['claims'] = [{'id': row['id'], 'status': 'BLOCKED', 'reason': 'current qualification did not complete'} for row in load(ROOT / 'specification.json')['claim_table']]
    unchanged = all(canonical.digest_file(WORKSPACE / name) == value for name, value in combined.items())
    report['inputs_unchanged'] = unchanged
    report['environment_unchanged'] = (before['toolchain'] == leanbridge.resolve_toolchain().identity() and before['kernel_tool_hash'] == leanbridge.kernel_tool_hash()
                                      and before['policy_hash'] == policy.policy_hash(policy.get('strict')))
    if not unchanged or not report['environment_unchanged']:
        report['status'] = 'BLOCKED'
        report['diagnostic'] = 'frozen relevant input/environment identity changed'
    report['evidence'] = {str(path.relative_to(out)): canonical.digest_file(path) for path in sorted(out.rglob('*')) if path.is_file()}
    (out / 'report.json').write_bytes(canonical.dumps(report))
    print(report['status'], flush=True)
    return 0 if report['status'] == 'VERIFIED' else 2


if __name__ == '__main__':
    sys.exit(main())
