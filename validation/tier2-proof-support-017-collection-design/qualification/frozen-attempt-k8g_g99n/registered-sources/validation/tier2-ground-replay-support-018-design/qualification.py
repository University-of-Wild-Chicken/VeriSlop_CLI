"""Reusable current-source qualification; never imports previous PASS evidence."""
from pathlib import Path
import argparse
import copy
import importlib.util
import os
import subprocess
import sys
from types import SimpleNamespace
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
              'name_control.py', 'deadline_controls.py', 'unit_controls.py', 'control_fixtures.py', 'qualification.py', 'baseline-vscore3_replay.py',
              'specification.json', 'qualification-plan.json', 'evidence-contract.json', 'activation-001.json',
              'recipe-001.json', 'export-frontier-005-freeze.json', 'frontier-evidence-006-freeze.json',
              'negative-controls-007-freeze.json', 'clean-builds-008-freeze.json', 'qualification-hook-009-freeze.json',
              'name-control-001-freeze.json', 'diagnostic-controls-003-freeze.json', 'oracle-controls-002-freeze.json',
              'verifier-amendment-011-freeze.json', 'output-routing-011-freeze.json', 'terminal-diagnostic-deadline-012-freeze.json',
              'qualification-registration-013.json')]
    return sorted(set(path.resolve() for path in paths))


def current_map(paths):
    return {str(path.relative_to(WORKSPACE)): canonical.digest_file(path) for path in paths}


def validate_fixtures(folder, expected, *, current=False):
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
        if current:
            assert isinstance(observed.get('proof_attempts'), list), 'current observation missing proof_attempts'
            assert isinstance(observed.get('proof_dependencies'), dict), 'current observation missing proof_dependencies'
            assert observed.get('strategy_id') == replay.STRATEGY, 'current observation missing exact strategy'
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
        if current:
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
            assert observed['proof_dependencies']['precontract_library_modules'] == {
                module: observed['modules'][module] for module in target.library_sources()}
            assert observed['proof_dependencies']['precontract_cache_key'] == canonical.digest_json({
                'toolchain': observed['toolchain'], 'sources': observed['proof_dependencies']['precontract_library_sources']})
            assert observed['proof_dependencies']['precontract_build_frontiers'] == [
                {'module': module, 'prior_normative_modules': list(target.library_sources())[:i]}
                for i, module in enumerate(target.library_sources())]
            assert {name_str(row['name']) for row in response['replay']['modules']} == set(observed['modules'])
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
    import unit_controls
    unit_result = load(out / 'units-results.json')
    expected_tests = [unit_controls.PREFIX + name for name in unit_controls.NAMES]
    assert unit_result['registry'] == expected_tests
    assert unit_result['executed'] == 15 and unit_result['success'] is True
    assert set(unit_result['results']) == set(expected_tests), 'missing exact executed unit identity'
    assert all(row['status'] == 'PASS' for row in unit_result['results'].values())
    assert all(row['status'] == 'PASS' for row in unit_result['subtests'])
    negative = out / 'negative'
    causal = {'source-stale': 'replayed artifact differs from frozen source/profile',
              'module-inventory': 'different staged dependency inventory',
              'export-count': 'omitted a requested complete declaration export',
              'normative-source-tamper': 'normative library sources changed',
              'forged-readable': 'exact source goal failed admission',
              'compile-failure': 'closed residual has no kernel-decidable result'}
    for name in ('source-stale', 'module-inventory', 'export-count', 'normative-source-tamper', 'forged-readable', 'compile-failure'):
        result = load(negative / name / 'result.json')
        assert result['status'] == 'UNSUPPORTED' and result['observed'] is None
        assert causal[name] in result['diagnostic']
    assert load(negative / 'base-readable/result.json')['status'] == 'NOT_REPRODUCED'
    failed = load(negative / 'compile-failure/result.json')
    attempts = canonical.loads(failed['diagnostic'].split('; proof_attempts=', 1)[1].encode())
    assert len(attempts) == 2 and all(not row['compiler_ok'] and row['available_rows'] > 0 for row in attempts)
    assert len(canonical.dumps(attempts)) <= replay.DIAGNOSTIC_WIRE_BYTES
    for name in ('guarantee', 'refinement', 'axiom', 'weaker'):
        assert load(out / 'oracle' / name / 'result.json')['status'] == 'PASS'
        response = load(out / 'oracle' / name / 'kernel-response.json')
        assert response['import']['ok'] and response['replay']['ok']
        rows = {name_str(row['name']): row for row in response['constants']}
        if name in ('guarantee', 'refinement'):
            spec = SimpleNamespace(obligations=[SimpleNamespace(lean_symbol='VeriSlopContract.guarantee')])
            try:
                replay._proof_dependencies(spec, rows, replay.THEOREM, {target.CONTRACT_MODULE, target.GOAL_MODULE, replay.MODULE})
            except replay.Unsupported as exc:
                assert 'guarantee oracle' in str(exc)
            else:
                raise AssertionError('actual wrapped oracle admitted')
        elif name == 'axiom':
            actual = [name_str(axiom) for axiom in rows[replay.THEOREM]['axioms']]
            assert replay.MODULE + '.fabricated' in actual
            assert policy.classify_axiom(replay.MODULE + '.fabricated', policy.get('strict')) != 'allowed'
        else:
            assert response['defeq'][0]['result'] != {'ok': True, 'typechecks': True, 'defeq': True}
    assert load(out / 'quoted-name/result.json')['status'] == 'REJECTED_ORACLE'
    quoted = load(out / 'quoted-name/kernel-response.json')
    assert quoted['import']['ok'] and quoted['replay']['ok']
    try:
        replay._proof_dependencies(SimpleNamespace(obligations=[SimpleNamespace(lean_symbol='VeriSlopContract.guarantee')]),
            {name_str(row['name']): row for row in quoted['constants']}, replay.THEOREM, {target.GOAL_MODULE, replay.MODULE})
    except replay.Unsupported as exc:
        assert 'guarantee oracle' in str(exc)
    else:
        raise AssertionError('quoted actual wrapper oracle admitted')
    for name, count in (('before-second-options', 1), ('after-kernel-replay', 2), ('terminal-second-diagnostic', 2)):
        result = load(out / 'deadline' / name / 'result.json')
        assert result['status'] == 'UNSUPPORTED' and result['observed'] is None
        assert result['attempts'] == count and result['prior_failure_retained']
        assert result['exception'] == 'BudgetExceeded' and float(result['elapsed_seconds']) >= 30
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
        'N-GR-BUDGET': 'deadline/terminal-second-diagnostic/result.json'}
    unit_map = {'N-GR-WIRE-ARITY': ['test_assignment_arity_stays_strict'],
        'N-GR-WIRE-SORT': ['test_wrong_wire_sort_rejected'], 'N-GR-WIRE-RECORD': ['test_closed_record_shape_rejected'],
        'N-GR-OPEN-RESIDUAL': ['test_unbounded_residual_is_still_rejected'],
        'N-GR-DIAGNOSTIC-TRUNCATION': ['test_utf8_row_and_whole_wire_bounds', 'test_escaped_control_rows_obey_encoded_wire_cap',
                                     'test_failed_attempt_survives_real_supervisor_receipt_path'],
        'N-GR-REVIEW-INCOMPLETE': ['test_unsupported_probe_keeps_unanimity_incomplete']}
    assert set(evidence) | set(unit_map) == {row['id'] for row in controls}
    return [{'id': row['id'], 'status': 'VERIFIED', 'evidence': evidence[row['id']] if row['id'] in evidence else 'units-results.json',
             'executed_test_ids': [unit_controls.PREFIX + name for name in unit_map.get(row['id'], [])],
             'scope': 'S-GR-001 preselected; S-GR-002 remains unavailable' if row['id'] == 'N-GR-BASE-READABLE' else 'actual registered control'} for row in controls]


def verify_verifier_guards(out, expected):
    """Actual current artifact omissions must fail the registered checker."""
    global load
    original_load = load
    outcome_path = out / 'clean-001/outcomes.json'
    outcomes = copy.deepcopy(original_load(outcome_path))
    outcomes[0]['observed'].pop('proof_attempts')
    def omit_ledger(path):
        return outcomes if path == outcome_path else original_load(path)
    load = omit_ledger
    try:
        validate_fixtures(out / 'clean-001', expected, current=True)
    except AssertionError as exc:
        assert str(exc) == 'current observation missing proof_attempts'
        ledger = str(exc)
    else:
        raise AssertionError('missing current ledger accepted')
    finally:
        load = original_load
    unit_path = out / 'units-results.json'
    units = copy.deepcopy(original_load(unit_path))
    units['results'].pop('tests.test_vscore3_ground_support_018.GroundSupportControls.test_assignment_arity_stays_strict')
    def omit_unit(path):
        return units if path == unit_path else original_load(path)
    load = omit_unit
    try:
        verify_controls(out)
    except AssertionError as exc:
        assert str(exc) == 'missing exact executed unit identity'
        unit = str(exc)
    else:
        raise AssertionError('missing executed control accepted')
    finally:
        load = original_load
    response = original_load(out / 'clean-001/identity/assignment-0/kernel-response.json')
    rows = {name_str(row['name']): row for row in response['constants']}
    removed = target.GOAL_MODULE + '.source_fn_transform'
    rows.pop(removed)
    spec = SimpleNamespace(obligations=[SimpleNamespace(lean_symbol='VeriSlopContract.guarantee')])
    try:
        replay._proof_dependencies(spec, rows, replay.THEOREM, {target.CONTRACT_MODULE, target.GOAL_MODULE, replay.MODULE})
    except replay.Unsupported as exc:
        assert 'staged declaration export' in str(exc)
        dependency = str(exc)
    else:
        raise AssertionError('missing actual staged proof dependency accepted')
    return {'status': 'VERIFIED', 'missing_current_ledger': ledger, 'missing_executed_control': unit,
            'missing_actual_staged_dependency': {'removed': removed, 'rejection': dependency},
            'fault_kind': 'Registered in-memory omission of actual current captured artifacts; no observation truth supplied.'}


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
    registration = load(ROOT / 'qualification-registration-013.json')
    assert registration['sha256'] == canonical.digest_file(Path(__file__)), 'qualification verifier differs from registration'
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
              'forbidden_task_oracles_read': False, 'native_or_model_calls': 0,
              'controls': [{'id': row['id'], 'status': 'BLOCKED', 'reason': 'required current check pending'}
                           for row in load(ROOT / 'qualification-plan.json')['negative_controls']]}
    try:
        for name, command in steps:
            with (out / (name + '.log')).open('wb') as stream:
                result = subprocess.run([sys.executable, str(ROOT / command[0]), *command[1:]], env=env, stdout=stream, stderr=subprocess.STDOUT)
            report['steps'].append({'id': name, 'rc': result.returncode, 'log': name + '.log'})
            print(name, result.returncode, flush=True)
            assert result.returncode == 0, name
        for name, command in (('units', [str(ROOT / 'unit_controls.py'), '--output', str(out / 'units-results.json')]),
                              ('existing-replay', ['-m', 'unittest', 'tests.test_vscore3_review_replay', '-v'])):
            with (out / (name + '.log')).open('wb') as stream:
                result = subprocess.run([sys.executable, *command], env=env, stdout=stream, stderr=subprocess.STDOUT)
            report['steps'].append({'id': name, 'rc': result.returncode, 'log': name + '.log'})
            print(name, result.returncode, flush=True)
            assert result.returncode == 0, name
        expected = {'identity': 'NOT_REPRODUCED', 'mutant': 'CONFIRMED', 'bounded': 'NOT_REPRODUCED', 'listhelper': 'NOT_REPRODUCED'}
        baseline = dict(expected, bounded='UNSUPPORTED')
        validate_fixtures(out / 'baseline', baseline)
        first, second = validate_fixtures(out / 'clean-001', expected, current=True), validate_fixtures(out / 'clean-002', expected, current=True)
        assert load(out / 'clean-001/frozen-inputs.json') == load(out / 'clean-002/frozen-inputs.json')
        assert first == second, 'clean deterministic bound inventory mismatch'
        (out / 'clean-comparison.json').write_bytes(canonical.dumps({'status': 'VERIFIED', 'exact_inventory': first,
            'inventory_hash': canonical.digest_json(first), 'clean_builds': 2}))
        report['controls'] = verify_controls(out)
        (out / 'verifier-guards.json').write_bytes(canonical.dumps(verify_verifier_guards(out, expected)))
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
        report['claims'] = [{'id': row['id'], 'status': 'BLOCKED', 'reason': report['diagnostic']}
                            for row in load(ROOT / 'specification.json')['claim_table']]
        report['controls'] = [{'id': row['id'], 'status': 'BLOCKED', 'reason': report['diagnostic']}
                              for row in load(ROOT / 'qualification-plan.json')['negative_controls']]
    report['evidence'] = {str(path.relative_to(out)): canonical.digest_file(path) for path in sorted(out.rglob('*')) if path.is_file()}
    (out / 'report.json').write_bytes(canonical.dumps(report))
    print(report['status'], flush=True)
    return 0 if report['status'] == 'VERIFIED' else 2


if __name__ == '__main__':
    sys.exit(main())
