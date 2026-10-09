#!/usr/bin/env python3
"""Unattended, independent recorded-evidence audit and documentation renderer.

No model calls, candidate execution, or writes to benchmark authority files.
Default monitor sleeps at most 30 seconds and has no wall-clock deadline.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

DEFAULT_REPO = Path(__file__).resolve().parents[2]
RUN_NAME = 'qwen-local-002'
EXPECTED_TASKS = 100

class AuditFailure(Exception):
    pass

def require(condition, detail):
    if not condition:
        raise AuditFailure(detail)

def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')

def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def load(path):
    return json.loads(path.read_bytes())

def optional_object(path):
    try:
        value = load(path)
    except (OSError, ValueError, UnicodeError):
        return {}
    require(isinstance(value, dict), 'Expected recorded JSON object: ' + str(path))
    return value

def inspect_artifact(root):
    """Independently inspect the grader's Python source/entry boundary; never import it."""
    if not root.is_dir():
        return {}, None, None
    hashes, entries = {}, []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            return {}, None, 'artifact contains a symlink'
        if path.is_file() and path.suffix == '.py':
            source = path.read_bytes()
            if len(source) > 1 << 20:
                return {}, None, 'artifact source exceeds 1 MiB'
            relative = path.relative_to(root).as_posix()
            hashes[relative] = sha(source)
            try:
                tree = ast.parse(source)
                entries.extend(relative for node in tree.body
                               if isinstance(node, ast.FunctionDef) and node.name == 'solve')
            except (SyntaxError, UnicodeError):
                pass
    return hashes, entries[0] if len(entries) == 1 else None, None

def exact(a, b):
    return canonical(a) == canonical(b)

def inside(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            'Invalid relative evidence path: ' + repr(relative))
    resolved = (root / relative).resolve()
    require(resolved.is_relative_to(root.resolve()), 'Path escapes evidence root: ' + relative)
    require(not (root / relative).is_symlink(), 'Evidence path is a symlink: ' + relative)
    return resolved

def hash_inventory(root, inventory, label):
    require(isinstance(inventory, dict), label + ' inventory is not an object')
    for relative, expected in inventory.items():
        path = inside(root, relative)
        require(path.is_file(), label + ' file missing: ' + relative)
        require(sha(path.read_bytes()) == expected, label + ' hash mismatch: ' + relative)
    return len(inventory)

def atomic_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def recompute(records):
    arms = {}
    for arm in ('raw', 'verislop'):
        rows = [r for r in records if r['arm'] == arm]
        arms[arm] = {
            'attempted_tasks': len(rows),
            'successful_tasks': sum(r['successful_task'] for r in rows),
            'artifacts': sum(r['artifact_present'] for r in rows),
            'held_out_passed': sum(r['hidden_passed'] for r in rows),
            'held_out_total': sum(r['hidden_total'] for r in rows),
            'public_passed': sum(r['public_passed'] for r in rows),
            'public_total': sum(r['public_total'] for r in rows),
            'generation_seconds': round(sum(r['generation_seconds'] for r in rows), 3),
            'model_calls': sum(r['usage'].get('calls', 0) for r in rows),
            'input_tokens': sum(r['usage'].get('input_tokens', 0) for r in rows),
            'output_tokens': sum(r['usage'].get('output_tokens', 0) for r in rows),
            'unknown_usage_calls': sum(r['usage'].get('unknown_usage_calls', 0) for r in rows),
            'last_model_purposes': dict(Counter(r.get('last_model_purpose') or 'none' for r in rows)),
            'statuses': dict(Counter(r['workflow_status'] for r in rows)),
        }
    tasks = defaultdict(dict)
    for record in records:
        tasks[record['task_id']][record['arm']] = record
    paired = {'both_success': 0, 'raw_only': 0, 'verislop_only': 0, 'neither_success': 0}
    for task in tasks.values():
        require(set(task) == {'raw', 'verislop'}, 'Unpaired final task')
        a, b = task['raw']['successful_task'], task['verislop']['successful_task']
        paired['both_success' if a and b else 'raw_only' if a else 'verislop_only' if b else 'neither_success'] += 1
    categories = {}
    for category in sorted({r['category'] for r in records}):
        categories[category] = {}
        for arm in arms:
            rows = [r for r in records if r['category'] == category and r['arm'] == arm]
            categories[category][arm] = {
                'tasks': len(rows), 'successes': sum(r['successful_task'] for r in rows),
                'passed': sum(r['hidden_passed'] for r in rows), 'total': sum(r['hidden_total'] for r in rows)}
    return arms, paired, categories

def audit(repo, expected_tasks=EXPECTED_TASKS):
    data = repo / 'synthetic_dataset'
    run = data / 'runs' / RUN_NAME
    evidence_path = run / 'run-manifest.json'
    require(evidence_path.is_file(), 'Final run-manifest.json does not exist')
    evidence_bytes = evidence_path.read_bytes()
    evidence = json.loads(evidence_bytes)
    protocol = load(run / 'protocol.json')
    summary = load(run / 'summary.json')
    dataset = load(data / 'manifest.json')
    require(evidence.get('format') == 'verislop.synthetic-benchmark-evidence/0.1', 'Unknown evidence format')
    require(evidence.get('complete') is True and evidence.get('valid') is True, 'Final evidence is incomplete or invalid')
    require(summary.get('complete') is True and summary.get('valid') is True, 'Final summary is incomplete or invalid')
    require(summary.get('source_mutations') == [], 'Final summary reports source mutations or omits the mutation check')
    require(summary.get('model_digest_after') == protocol['model_digest'], 'Model digest changed or final digest check missing')
    require(summary.get('finished_at_utc'), 'Final completion timestamp is missing')
    require(protocol.get('arm_seconds') is None and protocol.get('global_seconds') is None,
            'Run002 does not have the requested disabled generation/admission deadlines')
    require(exact(summary.get('protocol'), protocol), 'Summary protocol differs from frozen protocol')
    require(sha(canonical(protocol)) == evidence['protocol_hash'], 'Evidence protocol hash mismatch')
    require(dataset['tasks'] == expected_tasks and summary['dataset_tasks'] == expected_tasks, 'Wrong final task inventory')
    dataset_root = sha(canonical({k: v for k, v in dataset.items() if k != 'dataset_root'}))
    require(dataset_root == dataset['dataset_root'] == evidence['dataset_root'] == protocol['dataset_root'] == summary['dataset_root'],
            'Dataset root mismatch')
    dataset_files = hash_inventory(data, {**dataset['files'], **dataset['generator_hashes']}, 'Frozen dataset')
    source_files = hash_inventory(repo, protocol['source_hashes'], 'Current execution source')
    hash_inventory(run / 'execution-source', protocol['source_hashes'], 'Captured execution source')
    evidence_files = hash_inventory(run, evidence['files'], 'Final run evidence')
    actual_inventory = {p.relative_to(run).as_posix() for p in run.rglob('*') if p.is_file() and p.name != 'run-manifest.json'}
    require(actual_inventory == set(evidence['files']), 'Final evidence inventory omits or adds files')
    config = load(run / 'config.json')
    require(sha(canonical(config)) == protocol['config_hash'], 'Config hash mismatch')
    require(all(p['request_timeout_seconds'] is None for p in config['providers'].values()), 'Provider request deadline is enabled')
    require(config['review']['budgets']['max_wall_seconds_per_tier'] == 0, 'Review tier deadline is enabled')
    task_rows = [json.loads(line) for line in (data / 'tasks.jsonl').read_bytes().splitlines() if line]
    require(len(task_rows) == expected_tasks and len({t['id'] for t in task_rows}) == expected_tasks, 'Dataset task rows are incomplete/duplicated')
    metadata = {t['id']: t for t in task_rows}
    order = protocol['task_order']
    require(len(order) == expected_tasks and set(order) == set(metadata), 'Protocol task order is incomplete/duplicated')
    cases_by_task = {}
    all_cases = []
    for task in task_rows:
        cases = load(inside(data, task['cases_path']))
        require(len(cases) >= 10 and len({c['id'] for c in cases}) == len(cases), 'Invalid task case inventory: ' + task['id'])
        require(sum(c['visibility'] == 'public' for c in cases) == 2, 'Wrong public example count: ' + task['id'])
        require(len({canonical(c['input']) for c in cases}) == len(cases), 'Duplicate task inputs: ' + task['id'])
        cases_by_task[task['id']] = cases
        all_cases.extend(cases)
    require(len(all_cases) == dataset['cases'] and len({c['id'] for c in all_cases}) == len(all_cases), 'Dataset case count/identity mismatch')
    records = [json.loads(line) for line in (run / 'results.jsonl').read_bytes().splitlines() if line]
    require(len(records) == 2 * expected_tasks, 'Expected %d final arm records, received %d' % (2 * expected_tasks, len(records)))
    seen = set()
    native_responses = 0
    for position, record in enumerate(records):
        task_id, arm = record['task_id'], record['arm']
        require(task_id in metadata and arm in ('raw', 'verislop'), 'Unknown task/arm in results')
        key = (task_id, arm)
        require(key not in seen, 'Duplicate arm record: ' + str(key)); seen.add(key)
        pair_index = position // 2
        expected_arm = ('raw', 'verislop')[position % 2] if pair_index % 2 == 0 else ('verislop', 'raw')[position % 2]
        require(record['pair_index'] == pair_index and task_id == order[pair_index] and arm == expected_arm, 'Execution order mismatch: ' + str(key))
        require(record.get('timed_out') is False and record.get('workflow_status') != 'TIMEOUT', 'Generation timeout recorded despite disabled deadline: ' + str(key))
        require(record['title'] == metadata[task_id]['title'] and record['category'] == metadata[task_id]['category'], 'Task metadata mismatch: ' + str(key))
        directory = inside(run, record['artifact_path'])
        require(directory == run / 'artifacts' / task_id / arm, 'Artifact directory mismatch: ' + str(key))
        require(exact(record, load(directory / 'score.json')), 'Result and per-arm score differ: ' + str(key))
        cases = cases_by_task[task_id]
        statuses = []
        for visibility, field, prefix in [('hidden', 'held_out_results', 'hidden'), ('public', 'public_results', 'public')]:
            expected_cases = [c for c in cases if c['visibility'] == visibility]
            observed_cases = record[field]
            require([c['id'] for c in observed_cases] == [c['id'] for c in expected_cases], 'Case identity/order mismatch: ' + str(key))
            passed_count = 0
            for expected, observed in zip(expected_cases, observed_cases):
                passed = 'observed' in observed and 'error' not in observed and exact(observed['observed'], expected['expected'])
                require(observed['status'] == ('PASS' if passed else 'FAIL'), 'Incorrect per-case score: ' + expected['id'])
                if 'expected' in observed:
                    require(exact(observed['expected'], expected['expected']), 'Stored expectation mismatch: ' + expected['id'])
                passed_count += passed; statuses.append(passed)
            require(record[prefix + '_total'] == len(expected_cases) and record[prefix + '_passed'] == passed_count,
                    'Per-arm denominator/count mismatch: ' + str(key))
        source_root = directory / ('artifact' if arm == 'raw' else 'package/implementation')
        actual_hashes, actual_entry, artifact_error = inspect_artifact(source_root)
        require(exact(actual_hashes, record['source_hashes']), 'Artifact source inventory/hash mismatch: ' + str(key))
        require(record.get('entry_file') == actual_entry, 'Artifact solve entry is not unique or does not match: ' + str(key))
        require(record.get('artifact_error') == artifact_error, 'Artifact inspection error mismatch: ' + str(key))
        require(type(record['artifact_present']) is bool and record['artifact_present'] == bool(actual_hashes),
                'Artifact-present flag mismatch: ' + str(key))
        require(actual_entry is not None or not any(statuses), 'Case passed without a unique solve entry: ' + str(key))
        pipeline = optional_object(directory / 'stdout.txt')
        cli_report = optional_object(directory / 'package/report.json') if arm == 'verislop' else {}
        meta = optional_object(directory / 'package/package.json') if arm == 'verislop' else {}
        actual_status = (pipeline.get('status') or cli_report.get('terminal_status') or 'ERROR') if arm == 'verislop' else ('ARTIFACT' if actual_entry else 'ERROR')
        require(record['workflow_status'] == actual_status, 'Recorded workflow status differs from actual outputs: ' + str(key))
        actual_history = pipeline.get('summary', {}).get('stages', meta.get('stage_history', []))
        require(exact(record['cli_stages'], actual_history), 'Actual CLI stage history mismatch: ' + task_id)
        success = bool(record['held_out_results']) and all(statuses) and not record['timed_out'] and (arm == 'raw' or actual_status == 'PASS')
        require(type(record['successful_task']) is bool and record['successful_task'] == success, 'Incorrect task success: ' + str(key))
        worker = optional_object(directory / 'worker-result.json')
        known_exit = worker.get('exit_code') if worker.get('status') == 'CLI_RETURNED' else 0 if worker.get('status') == 'ARTIFACT' else 2 if worker.get('status') == 'WORKER_ERROR' else None
        require(type(record.get('worker_exit_code')) is int, 'Invalid worker process exit code: ' + str(key))
        if known_exit is not None:
            require(type(known_exit) is int and record['worker_exit_code'] == known_exit, 'Worker exit code disagrees with worker-result: ' + str(key))
        usage = record['usage']
        actual_usage = optional_object(directory / 'usage.json')
        actual_usage['unknown_usage_calls'] = max(actual_usage.get('unknown_usage_calls', 0), actual_usage.get('calls', 0) - actual_usage.get('responses', 0))
        require(exact(usage, actual_usage), 'Recorded usage differs from saved worker usage: ' + str(key))
        for field in ('calls', 'responses', 'input_tokens', 'output_tokens', 'reserved_output_tokens', 'unknown_usage_calls'):
            require(type(usage.get(field, 0)) is int and usage.get(field, 0) >= 0, 'Invalid usage counter ' + field + ': ' + str(key))
        require(0 <= usage.get('calls', 0) <= (1 if arm == 'raw' else protocol['harness_calls']), 'Logical call budget exceeded: ' + str(key))
        require(0 <= usage.get('output_tokens', 0) <= protocol['output_token_budget'], 'Generated token budget exceeded: ' + str(key))
        requests = [optional_object(path) for path in sorted(directory.glob('request-*.json'))]
        require(len(requests) == usage.get('calls', 0), 'Saved request/logical call count mismatch: ' + str(key))
        require(record.get('last_model_purpose') == (requests[-1].get('purpose') if requests else None), 'Last model purpose differs from saved request: ' + str(key))
        require(usage.get('responses', 0) <= usage.get('calls', 0), 'Received more responses than logical calls: ' + str(key))
        require(max(0, usage.get('calls', 0) - usage.get('responses', 0)) <= usage.get('unknown_usage_calls', 0) <= usage.get('calls', 0),
                'Unknown-usage count disagrees with logical calls/responses: ' + str(key))
        require(usage.get('output_tokens', 0) <= usage.get('reserved_output_tokens', 0) <= protocol['output_token_budget'],
                'Output reservation exceeds the budget or is below observed output: ' + str(key))
        responses = [load(path) for path in sorted(directory.glob('native-response-*.json'))]
        native_responses += len(responses)
        require(len(responses) == usage.get('responses', 0), 'Native response count mismatch: ' + str(key))
        require(sum(b.get('eval_count', 0) or 0 for b in responses) == usage.get('output_tokens', 0), 'Native generated token sum mismatch: ' + str(key))
        require(sum(b.get('prompt_eval_count', 0) or 0 for b in responses) == usage.get('input_tokens', 0), 'Native input token sum mismatch: ' + str(key))
        for body in responses:
            input_count = body.get('prompt_eval_count')
            require(input_count is None or type(input_count) is int and input_count >= 0, 'Invalid native prompt token count: ' + str(key))
            require(body.get('model') == protocol['model'], 'Native model identity mismatch: ' + str(key))
            count = body.get('eval_count')
            require(count is None or type(count) is int and 0 <= count <= protocol['per_call_output_tokens'],
                    'Native per-call generated-token ceiling exceeded: ' + str(key))
        for path in directory.rglob('transcripts/*.json'):
            log = load(path)
            if log.get('requested_model') is not None:
                require(log['requested_model'] == protocol['model'], 'Transcript requested model mismatch: ' + str(key))
            if log.get('error') is None:
                require(log.get('model_digest_sha256') == protocol['model_digest'], 'Successful transcript has absent/wrong model digest: ' + str(key))
                require(log.get('requested_model') == log.get('returned_model') == protocol['model'],
                        'Successful transcript requested/returned model differs from pin: ' + str(key))
            elif log.get('model_digest_sha256') is not None:
                require(log['model_digest_sha256'] == protocol['model_digest'], 'Transcript digest mismatch: ' + str(key))
                require(log.get('requested_model') == protocol['model'], 'Transcript requested model mismatch: ' + str(key))
        if arm == 'verislop':
            invocation_record = optional_object(directory / 'cli-invocation.json')
            if invocation_record:
                invocation = invocation_record['argv']
                def option(name): return invocation[invocation.index(name) + 1]
                require(option('--policy') == 'strict' and option('--tier') == '0' and option('--target') == 'python'
                        and option('--require-state') == 'TESTED' and option('--budget-seconds') == '0', 'Actual full CLI gate/deadline mismatch: ' + task_id)
                require('--require-tests' in invocation, 'Actual CLI does not require tests: ' + task_id)
                require(Path(option('--runs-dir')) / option('--run-id') == directory / 'package', 'CLI package output location mismatch: ' + task_id)
                require(Path(option('--config')) == run / 'config.json', 'Actual CLI configuration differs: ' + task_id)
                require(Path(option('--prompt-file')) == data / metadata[task_id]['prompt_path'], 'Actual CLI prompt differs: ' + task_id)
            else:
                require(actual_status == 'ERROR' and not actual_hashes and not actual_history,
                        'CLI invocation absent for a reached/successful pipeline: ' + task_id)
            if record['cli_report']:
                require(inside(run, record['cli_report']).is_file(), 'CLI report missing: ' + task_id)
    arms, paired, categories = recompute(records)
    require(exact(arms, summary['arms']), 'Final arm totals differ from independent recomputation')
    require(exact(paired, summary['paired']), 'Final paired outcome totals differ')
    require(exact(categories, summary['categories']), 'Final category totals differ')
    require(sum(paired.values()) == summary['complete_pairs'] == expected_tasks, 'Final complete-pair total differs')
    hidden_per_arm = sum(c['visibility'] == 'hidden' for c in all_cases)
    public_per_arm = sum(c['visibility'] == 'public' for c in all_cases)
    require(all(a['held_out_total'] == hidden_per_arm and a['public_total'] == public_per_arm for a in arms.values()), 'Final test denominator omits tasks/cases')
    require(evidence_path.read_bytes() == evidence_bytes, 'Evidence manifest changed during audit')
    return {'summary': summary, 'results': records, 'cases': all_cases,
            'checks': {'evidence_files': evidence_files, 'dataset_files': dataset_files, 'execution_sources': source_files,
                       'native_responses': native_responses, 'tasks': expected_tasks, 'records': len(records),
                       'cases': len(all_cases), 'hidden_per_arm': hidden_per_arm, 'public_per_arm': public_per_arm,
                       'manifest_hash': sha(evidence_bytes)}}

def render_viewer(html, checked):
    payload = json.dumps({k: checked[k] for k in ('summary', 'results', 'cases')}, sort_keys=True,
                         ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    pattern = r'(<script\b[^>]*\bid=["\']benchmark-data["\'][^>]*>)[\s\S]*?(</script\s*>)'
    require(len(re.findall(pattern, html)) == 1, 'Viewer has no unique benchmark-data JSON block')
    rendered = re.sub(pattern, lambda m: m.group(1) + payload + m.group(2), html, count=1)
    # Existing viewer understands individual cases.json files. Add the same input
    # path for an optional embedded case array without changing score rendering.
    old = 'acceptRecords(document.results);return;'
    new = 'acceptRecords(document.results);if(Array.isArray(document.cases))acceptDocument(document.cases,name);return;'
    if old in rendered:
        require(rendered.count(old) == 1, 'Ambiguous viewer embedded-case adapter')
        rendered = rendered.replace(old, new)
    else:
        require(new in rendered, 'Viewer embedded-data adapter changed unexpectedly')
    rendered = rendered.replace('<!-- Root may replace this JSON after the run finishes; no synthetic results are embedded. -->',
                                '<!-- Independently audited final run002 summary, observations, and frozen case inputs. -->')
    rendered = rendered.replace('runs/qwen-local-001/summary.json', 'runs/qwen-local-002/summary.json')
    rendered = rendered.replace('runs/qwen-local-001/results.jsonl', 'runs/qwen-local-002/results.jsonl')
    require(exact(json.loads(re.search(pattern, rendered).group(0).split('>', 1)[1].rsplit('</script', 1)[0]),
                  {k: checked[k] for k in ('summary', 'results', 'cases')}), 'Viewer payload changed during embedding')
    return rendered

def final_audit_markdown(checked):
    summary, checks = checked['summary'], checked['checks']
    p = summary['protocol']; rows = ['# Final independent audit of the local Qwen benchmark', '',
        '**Audit passed.** Run `qwen-local-002` completed all 100 paired tasks and 200 arm records. '
        'Its final `complete` and `valid` flags are true, source mutations are empty, and the final model digest matches the frozen pin.', '',
        'Finished: ' + summary['finished_at_utc'] + '. Audit: ' + datetime.now(timezone.utc).isoformat() + '.', '',
        'Model: `' + p['model'] + '`; digest `' + p['model_digest'] + '`.', '']
    for arm, label in [('raw', 'Raw Qwen'), ('verislop', 'Full VeriSlop CLI')]:
        a = summary['arms'][arm]
        rows.append('- **' + label + ':** %d/100 successful tasks; %d/%d held-out cases passed; %d/%d public examples passed; %d artifacts; %d model-call attempts; %.3f recorded generation seconds.' %
                    (a['successful_tasks'], a['held_out_passed'], a['held_out_total'], a['public_passed'], a['public_total'],
                     a['artifacts'], a['model_calls'], a['generation_seconds']))
    pairs = summary['paired']
    rows += ['', 'Paired outcomes: both succeed %d; raw only %d; CLI only %d; neither succeeds %d.' %
             (pairs['both_success'], pairs['raw_only'], pairs['verislop_only'], pairs['neither_success']), '',
             '## What was checked', '',
             'The audit independently recomputed every case status from recorded observations and frozen expected outputs, '
             'every public/hidden denominator, task-success decision, arm/category total, and paired outcome. '
             'Successful tasks pass both public and hidden tests; the full CLI also returns `PASS`. '
             'Missing artifacts and blocked workflows keep their full failed-case denominators.', '',
             '%d final evidence files, %d frozen dataset/generator files, and %d execution-source files were hash-checked. '
             'Both captured execution sources and current files agree with the protocol. '
             'Every artifact source hash, score/results correspondence, native response identity, received-response token sum, '
             'recorded transcript digest, actual CLI invocation, and stage history was checked. '
             'The manifest was stable across the audit.' %
             (checks['evidence_files'], checks['dataset_files'], checks['execution_sources']), '',
             'Generation deadlines are disabled. Finite model-call/token bounds, mechanical verifier limits, '
             'and the evaluator case/resource limits remain. No generation `TIMEOUT` flag was recorded.', '',
             '## Scope and trust', '',
             'This is a finite audit of recorded benchmark evidence, not a universal software-correctness proof. '
             'It does not rerun the model or each candidate, prove dataset oracles, authenticate provider hardware, '
             'or establish a causal benefit from verification. It trusts the frozen task expectations, recorded native service metadata, '
             'the benchmark grader and sandbox, and the host execution environment. '
             'Difficulty is author-assigned; this is one local model and one synthetic run. '
             'VeriSlop workflow passage and test passage retain their recorded formal scope. '
             'The viewer preserves exact decimal integer tokens, including values outside the browser numeric range.', '',
             '## Sources', '',
             '- [Final report](runs/qwen-local-002/REPORT.md), [summary](runs/qwen-local-002/summary.json), and [arm records](runs/qwen-local-002/results.jsonl).',
             '- [Frozen protocol](runs/qwen-local-002/protocol.json), [evidence manifest](runs/qwen-local-002/run-manifest.json), and [captured sources](runs/qwen-local-002/execution-source/).',
             '- [Dataset manifest](manifest.json), [task inventory](tasks.jsonl), and [interactive artifact comparison](viewer.html).',
             '- [Concrete recorded counterexamples](COUNTEREXAMPLES.md).', '',
             'Auditor: [finalize_qwen_002.py](tools/finalize_qwen_002.py); source hash `' + sha(Path(__file__).read_bytes()) + '`.',
             'Audited evidence-manifest hash: `' + checks['manifest_hash'] + '`.', '']
    return '\n'.join(rows)

def final_status_markdown(checked):
    s = checked['summary']; p = s['protocol']
    return '\n'.join(['# Local Qwen benchmark run status', '',
        '**Run `qwen-local-002` is completed and its independent recorded-evidence audit passed.** '
        'All 100 task pairs and 200 arm records are present. Final `complete` and `valid` flags are true; '
        'source mutations are empty and the model digest is unchanged.', '',
        'Finished: ' + s['finished_at_utc'] + '.', '',
        '- [Final benchmark report](runs/qwen-local-002/REPORT.md).',
        '- [Independent final audit and measured totals](FINAL_AUDIT.md).',
        '- [Interactive artifact comparison](viewer.html), with embedded final scores and all frozen case inputs.',
        '- [Summary](runs/qwen-local-002/summary.json), [arm records](runs/qwen-local-002/results.jsonl), '
        '[protocol](runs/qwen-local-002/protocol.json), and [evidence manifest](runs/qwen-local-002/run-manifest.json).', '',
        'Model: `' + p['model'] + '`; digest `' + p['model_digest'] + '`.', '',
        'The experiment used the actual strict Tier 0 CLI, with tests and configured adversarial review. '
        'Generation/provider/proof/review/global wall deadlines were disabled, while model-call/token ceilings '
        'and mechanical verifier/evaluator resource limits remained. Blocked workflows count as unsuccessful.', '',
        'The separate [earlier timed run](runs/qwen-local-001/REPORT.md) remains preserved with '
        '`SUPERSEDED_BY_USER` termination; its observations are excluded from this completed experiment.', ''])

def failure_document(data, error):
    atomic_text(data / 'FINAL_AUDIT.md', '# Final benchmark audit did not pass\n\n'
                '**No completed, valid benchmark result is certified by this audit.**\n\n'
                'Run: `qwen-local-002`. Audit time: ' + datetime.now(timezone.utc).isoformat() + '.\n\n'
                'Concrete audit failure: `' + str(error).replace('`', "'").replace('\n', ' ') + '`.\n\n'
                'Authority score and evidence files were not changed. The completed dashboard/status renderer '
                'was not published. Inspect [the recorded run](runs/qwen-local-002/) and its final manifest/summary.\n')

def process_identity(pid):
    """Return Linux process state/starttime without signaling or altering it."""
    try:
        stat = Path('/proc') / str(pid) / 'stat'
        text = stat.read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    # comm is parenthesized and may contain spaces or closing parentheses.
    fields = text.rsplit(')', 1)[1].split()
    require(len(fields) > 19 and fields[19].isdigit(), 'Cannot parse supervisor /proc starttime')
    return fields[0], fields[19]

def wait_for_manifest(run, poll_seconds, supervisor_pid=None):
    """Wait without a deadline; an exited pinned supervisor gets one poll of grace."""
    manifest = run / 'run-manifest.json'
    initial = process_identity(supervisor_pid) if supervisor_pid is not None and not manifest.is_file() else None
    starttime = initial[1] if initial is not None else None
    while not manifest.is_file():
        if supervisor_pid is not None:
            current = process_identity(supervisor_pid)
            alive = (current is not None and current[0] not in ('Z', 'X')
                     and starttime is not None and current[1] == starttime)
            if not alive:
                # The benchmark writes its manifest immediately before returning.
                # One additional poll covers the exit/atomic-manifest publication race.
                time.sleep(poll_seconds)
                require(manifest.is_file(), 'Pinned benchmark supervisor %d (starttime %s) exited before publishing a final manifest' %
                        (supervisor_pid, starttime if starttime is not None else 'unavailable'))
                break
        time.sleep(poll_seconds)
    return starttime

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    parser.add_argument('--poll-seconds', type=float, default=30)
    parser.add_argument('--supervisor-pid', type=int, help='Observe this benchmark PID and pin its /proc starttime; if it exits without a final manifest, report failure after one extra poll. Never signals or cancels the process')
    parser.add_argument('--check-only', '--check-now', dest='check_only', action='store_true', help='Do not wait or alter documentation; validate an existing final manifest or report that it is absent')
    args = parser.parse_args()
    require(0 < args.poll_seconds <= 30, 'Poll interval must be greater than zero and at most 30 seconds')
    require(args.supervisor_pid is None or args.supervisor_pid > 0, 'Supervisor PID must be positive')
    repo = args.repo.resolve(); data = repo / 'synthetic_dataset'; run = data / 'runs' / RUN_NAME
    try:
        if not args.check_only:
            wait_for_manifest(run, args.poll_seconds, args.supervisor_pid)
        checked = audit(repo)
        if not args.check_only:
            viewer = render_viewer((data / 'viewer.html').read_text(), checked)
            audit_doc = final_audit_markdown(checked)
            status_doc = final_status_markdown(checked)
            atomic_text(data / 'viewer.html', viewer)
            atomic_text(data / 'RUN_STATUS.md', status_doc)
            atomic_text(data / 'FINAL_AUDIT.md', audit_doc)
        print(json.dumps({'status': 'PASS', 'checks': checked['checks'], 'arms': checked['summary']['arms'],
                          'paired': checked['summary']['paired'], 'rendered': not args.check_only}, sort_keys=True), flush=True)
        return 0
    except Exception as error:
        if not args.check_only:
            failure_document(data, error)
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__, 'error': str(error)}, sort_keys=True), flush=True)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
