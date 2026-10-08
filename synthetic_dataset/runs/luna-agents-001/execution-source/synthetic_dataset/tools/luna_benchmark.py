"""Frozen paired benchmark driven by fresh collaboration-agent model responses.

Start this driver, then service its file mailboxes with the collaboration runtime.
No native API is called and no model identity or token usage is fabricated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

from synthetic_dataset.benchmark import artifact_files, grade, load, load_bytes, verify_dataset, write
from synthetic_dataset.build_dataset import ROOT, digest, encode
from synthetic_dataset.tools.luna_worker import (
    MODEL, MAX_RESPONSE_BYTES, atomic_json, configuration, endpoint_profiles, validate_response,
)

REPO = ROOT.parent


def agent_message(request):
    return ('Handle exactly one model request. Return only the response text required by the '
            'SYSTEM and USER below. Do not use tools, read files, inspect the workspace, '
            'delegate, or access other agents. Do not include commentary.\n\n'
            'SYSTEM:\n' + request['system'] + '\n\nUSER:\n' + request['user'])


def source_inventory():
    paths = [*ROOT.glob('*.py'), *REPO.joinpath('verislop').rglob('*.py'),
             *REPO.joinpath('verislop/lean').rglob('*.lean'), *REPO.joinpath('schemas').glob('*.json'),
             Path(__file__).resolve(), REPO / 'synthetic_dataset/tools/luna_worker.py']
    return {p.relative_to(REPO).as_posix(): digest(p.read_bytes()) for p in sorted(set(paths))}


def pending_request(out):
    state = load(out / 'active-arm.json', {})
    if state.get('phase') != 'generation':
        return None
    directory = out / state['artifact_path']
    for path in sorted(directory.glob('request-*.json')):
        request = load(path)
        if not request:
            raise ValueError(f'invalid published request: {path}')
        if not (directory / f"response-{request['request_id']}.json").exists():
            message = agent_message(request)
            return {'request_path': str(path.resolve()), 'request_sha256': digest(path.read_bytes()),
                    'task_id': state['task_id'], 'arm': state['arm'], 'request': request,
                    'agent_message': message, 'spawn_message_sha256': digest(message.encode('utf-8'))}
    return None


def publish_response(out, envelope):
    pending = pending_request(out)
    if pending is None:
        raise ValueError('no pending request; refuse unsolicited response')
    request = pending['request']
    text, agent_id = validate_response(envelope, request['request_id'], pending['request_sha256'])
    if envelope.get('model_override') != MODEL or envelope.get('fork_turns') != 'none':
        raise ValueError('controller must record the actual fresh model override and context policy')
    if envelope.get('spawn_message_sha256') != pending['spawn_message_sha256']:
        raise ValueError('controller must bind the exact supplied generator message')
    # Reject cross-arm/task reuse before any response is delivered to the CLI.
    for receipt in out.joinpath('artifacts').rglob('response-receipt-*.json'):
        if load(receipt, {}).get('agent_task_id') == agent_id:
            raise ValueError('collaboration agent task was already used in this experiment')
    destination = Path(pending['request_path']).with_name(f"response-{request['request_id']}.json")
    if destination.exists():
        raise ValueError('response already exists')
    atomic_json(destination, envelope)
    return {'published': str(destination), 'agent_task_id': agent_id, 'output_bytes': len(text.encode('utf-8'))}


def summarize(records, manifest, protocol):
    selected = protocol['task_order']
    if len(selected) != len(set(selected)):
        raise ValueError('duplicate selected task ID')
    for row in records:
        if row['task_id'] not in selected or row['arm'] not in ('raw', 'verislop'):
            raise ValueError('score contains an unselected task or unknown arm')
    arms = {}
    for arm in ('raw', 'verislop'):
        rows = [r for r in records if r['arm'] == arm]
        arms[arm] = {
            'attempted_tasks': len(rows), 'successful_tasks': sum(r['successful_task'] for r in rows),
            'artifacts': sum(r['artifact_present'] for r in rows),
            'held_out_passed': sum(r['hidden_passed'] for r in rows),
            'held_out_total': sum(r['hidden_total'] for r in rows),
            'public_passed': sum(r['public_passed'] for r in rows), 'public_total': sum(r['public_total'] for r in rows),
            'model_calls': sum(r['usage'].get('calls', 0) for r in rows),
            'responses': sum(r['usage'].get('responses', 0) for r in rows),
            'output_bytes': sum(r['usage'].get('output_bytes', 0) for r in rows),
            'input_tokens': None, 'output_tokens': None, 'token_usage_available': False,
            'unknown_usage_calls': sum(r['usage'].get('calls', 0) for r in rows),
            'generation_seconds': round(sum(r['generation_seconds'] for r in rows), 3),
            'statuses': dict(Counter(r['workflow_status'] for r in rows)),
            'last_model_purposes': dict(Counter(r['last_model_purpose'] or 'none' for r in rows)),
        }
    by_id = {}
    for r in records:
        pair = by_id.setdefault(r['task_id'], {})
        if r['arm'] in pair:
            raise ValueError('duplicate task/arm score')
        pair[r['arm']] = r
    paired = dict.fromkeys(('both_success', 'raw_only', 'verislop_only', 'neither_success'), 0)
    for pair in by_id.values():
        if set(pair) == {'raw', 'verislop'}:
            a, b = pair['raw']['successful_task'], pair['verislop']['successful_task']
            paired['both_success' if a and b else 'raw_only' if a else 'verislop_only' if b else 'neither_success'] += 1
    categories = {}
    for category in sorted({r['category'] for r in records}):
        categories[category] = {}
        for arm in arms:
            rows = [r for r in records if r['category'] == category and r['arm'] == arm]
            categories[category][arm] = {'tasks': len(rows), 'successes': sum(r['successful_task'] for r in rows),
                                        'passed': sum(r['hidden_passed'] for r in rows), 'total': sum(r['hidden_total'] for r in rows)}
    count = len(protocol['task_order'])
    return {'format': 'verislop.collaboration-benchmark-summary/0.1', 'dataset_root': manifest['dataset_root'],
            'dataset_tasks': manifest['tasks'], 'selected_tasks': count, 'protocol': protocol,
            'arms': arms, 'paired': paired, 'categories': categories, 'complete_pairs': sum(paired.values()),
            'complete': sum(paired.values()) == count, 'valid': None, 'status': 'RUNNING'}


def run_arm(task, arm, index, out, args):
    directory = out / 'artifacts' / task['id'] / arm
    directory.mkdir(parents=True, exist_ok=False)
    write(out / 'active-arm.json', {'task_id': task['id'], 'arm': arm, 'pair_index': index,
                                   'phase': 'generation', 'artifact_path': directory.relative_to(out).as_posix()})
    command = [sys.executable, '-m', 'synthetic_dataset.tools.luna_worker', '--arm', arm,
               '--task', str(ROOT / task['prompt_path']), '--out', str(directory),
               '--config', str(out / 'config.json'), '--calls', '1' if arm == 'raw' else str(args.harness_calls)]
    env = dict(os.environ, VERISLOP_CONFIG_HOME=str(out / 'provider-home'))
    start = time.monotonic()
    proc = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Deliberately no generation deadline. Finite call/byte and candidate limits remain.
    stdout, stderr = proc.communicate()
    elapsed = time.monotonic() - start
    (directory / 'stdout.txt').write_bytes(stdout)
    (directory / 'stderr.txt').write_bytes(stderr)
    write(out / 'active-arm.json', {'task_id': task['id'], 'arm': arm, 'pair_index': index,
                                   'phase': 'grading', 'artifact_path': directory.relative_to(out).as_posix()})
    pipeline = load_bytes(stdout) or {}
    cli_report = load(directory / 'package/report.json', {}) if arm == 'verislop' else {}
    meta = load(directory / 'package/package.json', {}) if arm == 'verislop' else {}
    usage = load(directory / 'usage.json', {})
    cases = load(ROOT / task['cases_path'])
    artifact_error = None
    try:
        files, entry = artifact_files(arm, directory)
    except ValueError as exc:
        files, entry, artifact_error = {}, None, str(exc)
    all_scores, isolation = grade(files, entry, cases, args.case_seconds)
    hidden = [s for s, c in zip(all_scores, cases) if c['visibility'] == 'hidden']
    public = [s for s, c in zip(all_scores, cases) if c['visibility'] == 'public']
    status = (pipeline.get('status') or cli_report.get('terminal_status') or 'ERROR') if arm == 'verislop' else ('ARTIFACT' if entry else 'ERROR')
    # Full CLI PASS is essential even if a blocked package happens to contain passing code.
    success = bool(hidden) and all(s['status'] == 'PASS' for s in all_scores) and proc.returncode == 0 and (arm == 'raw' or status == 'PASS')
    requests = [load(p, {}) for p in sorted(directory.glob('request-*.json'))]
    record = {'task_id': task['id'], 'title': task['title'], 'category': task['category'], 'arm': arm,
              'pair_index': index, 'workflow_status': status, 'successful_task': success,
              'artifact_present': bool(files), 'entry_file': entry, 'artifact_error': artifact_error,
              'source_hashes': {k: digest(v) for k, v in files.items()}, 'generation_seconds': round(elapsed, 3),
              'worker_exit_code': proc.returncode, 'timed_out': False, 'usage': usage,
              'hidden_passed': sum(s['status'] == 'PASS' for s in hidden), 'hidden_total': len(hidden),
              'public_passed': sum(s['status'] == 'PASS' for s in public), 'public_total': len(public),
              'held_out_results': hidden, 'public_results': public, 'grader_isolation': isolation,
              'cli_stages': pipeline.get('summary', {}).get('stages', meta.get('stage_history', [])),
              'last_model_purpose': requests[-1].get('purpose') if requests else None,
              'cli_diagnostics': pipeline.get('diagnostics', cli_report.get('blocking_reasons', []) + cli_report.get('infrastructure_errors', [])),
              'cli_report': str((directory / 'package/report.json').relative_to(out)) if cli_report else None,
              'artifact_path': str(directory.relative_to(out))}
    write(directory / 'score.json', record)
    return record


def score_integrity_errors(row, out):
    errors = []
    tasks = {t['id']: t for t in (json.loads(line) for line in (ROOT / 'tasks.jsonl').read_text().splitlines())}
    task = tasks.get(row.get('task_id'))
    if task is None:
        return ['unknown scored task']
    cases = load(ROOT / task['cases_path'])
    directory = out / row['artifact_path']
    if row['artifact_path'] != f"artifacts/{row['task_id']}/{row['arm']}":
        errors.append('score artifact path differs from selected task/arm')
    if encode(load(directory / 'score.json')) != encode(row):
        errors.append('stored score differs from results row')
    passed = {}
    for visibility, key, prefix in (('hidden', 'held_out_results', 'hidden'), ('public', 'public_results', 'public')):
        expected_cases = [c for c in cases if c['visibility'] == visibility]
        scores = row.get(key, [])
        if [s.get('id') for s in scores] != [c['id'] for c in expected_cases]:
            errors.append(f'{visibility} case IDs differ from frozen cases')
        count = 0
        for score, case in zip(scores, expected_cases):
            status = 'PASS' if ('error' not in score and 'observed' in score and encode(score['observed']) == encode(case['expected'])) else 'FAIL'
            if score.get('status') != status:
                errors.append(f"{case['id']}: recorded status differs from exact observation")
            if 'expected' in score and encode(score['expected']) != encode(case['expected']):
                errors.append(f"{case['id']}: expected output differs from frozen case")
            count += status == 'PASS'
        if (row.get(prefix + '_passed'), row.get(prefix + '_total')) != (count, len(expected_cases)):
            errors.append(f'{visibility} counters differ from case evidence')
        passed[visibility] = count == len(expected_cases) and bool(expected_cases)
    try:
        files, entry = artifact_files(row['arm'], directory)
    except ValueError:
        files, entry = {}, None
    if (row.get('entry_file'), row.get('artifact_present'), row.get('source_hashes')) != (entry, bool(files), {k: digest(v) for k, v in files.items()}):
        errors.append('artifact selection or source hashes differ from generated files')
    success = (all(passed.values()) and bool(entry) and row.get('worker_exit_code') == 0
               and not row.get('timed_out') and (row['arm'] == 'raw' or row.get('workflow_status') == 'PASS'))
    if row.get('successful_task') != success:
        errors.append('successful task differs from exact cases and workflow gate')
    if row['arm'] == 'verislop':
        invocation = load(directory / 'cli-invocation.json', {}).get('argv', [])
        from synthetic_dataset.tools.luna_worker import cli_argv
        if invocation != cli_argv(ROOT / task['prompt_path'], directory, out / 'config.json'):
            errors.append('full CLI invocation differs from strict tested workflow')
        pipeline = load_bytes((directory / 'stdout.txt').read_bytes()) or {}
        cli_report = load(directory / 'package/report.json', {})
        status = pipeline.get('status') or cli_report.get('terminal_status') or 'ERROR'
        if row.get('workflow_status') != status:
            errors.append('workflow status differs from actual CLI output')
    return [f"{row['task_id']}/{row['arm']}: {e}" for e in errors]


def audit(out, manifest, protocol, records):
    """Check immutable bytes and response binding; not native provider attestation."""
    summarize(records, manifest, protocol)
    changes = []
    for rel, expected in protocol['source_hashes'].items():
        if not (REPO / rel).is_file() or digest((REPO / rel).read_bytes()) != expected:
            changes.append(rel)
        if digest((out / 'execution-source' / rel).read_bytes()) != expected:
            changes.append('execution-source/' + rel)
    errors, agents = [], set()
    if encode(load(out / 'protocol.json')) != encode(protocol):
        errors.append('protocol file changed')
    for row in records:
        errors.extend(score_integrity_errors(row, out))
        directory = out / row['artifact_path']
        requests = sorted(directory.glob('request-*.json'))
        receipts = sorted(directory.glob('response-receipt-*.json'))
        if len(requests) != row['usage'].get('calls') or len(receipts) != row['usage'].get('responses'):
            errors.append(f"{row['task_id']}/{row['arm']}: inconsistent call counts")
        limit = 1 if row['arm'] == 'raw' else protocol['harness_calls']
        if not 0 <= len(receipts) <= len(requests) <= limit:
            errors.append(f"{row['task_id']}/{row['arm']}: call limit exceeded")
        total_bytes = 0
        for path in receipts:
            receipt = load(path, {})
            rid = receipt.get('request_id')
            request_path, response_path = directory / f'request-{rid}.json', directory / f'response-{rid}.json'
            if not request_path.is_file() or not response_path.is_file():
                errors.append(f'{path}: missing bound request/response')
                continue
            request_bytes, response_bytes = request_path.read_bytes(), response_path.read_bytes()
            response = load(response_path, {})
            try:
                text, agent_id = validate_response(response, rid, digest(request_bytes))
                if (response.get('model_override'), response.get('fork_turns')) != (MODEL, 'none'):
                    raise ValueError('unrecorded model/context selection')
                if response.get('spawn_message_sha256') != digest(agent_message(load(request_path)).encode('utf-8')):
                    raise ValueError('unbound generator message')
                if agent_id in agents:
                    raise ValueError('agent reused across model requests')
                agents.add(agent_id)
                count = len(text.encode('utf-8'))
                if any(receipt.get(k) != v for k, v in {
                    'request_sha256': digest(request_bytes), 'response_sha256': digest(response_bytes),
                    'text_sha256': digest(text.encode('utf-8')), 'output_bytes': count,
                    'agent_task_id': agent_id, 'requested_model': MODEL, 'returned_model': None,
                    'input_tokens': None, 'output_tokens': None, 'model_identity_attested': False,
                }.items()):
                    raise ValueError('receipt does not match exact response bytes')
                total_bytes += count
            except Exception as exc:
                errors.append(f'{path.relative_to(out)}: {exc}')
        if row['usage'].get('input_tokens') is not None or row['usage'].get('output_tokens') is not None:
            errors.append(f"{row['task_id']}/{row['arm']}: invented token usage")
        if total_bytes != row['usage'].get('output_bytes', 0):
            errors.append(f"{row['task_id']}/{row['arm']}: inconsistent output bytes")
        if row['usage'].get('unknown_usage_calls') != len(requests):
            errors.append(f"{row['task_id']}/{row['arm']}: inconsistent unknown token accounting")
    if digest(encode(load(out / 'config.json'))) != protocol['config_hash']:
        errors.append('configuration changed')
    if digest((out / 'provider-home/endpoint-profiles.json').read_bytes()) != protocol['endpoint_profiles_hash']:
        errors.append('endpoint profiles changed')
    if verify_dataset()['dataset_root'] != manifest['dataset_root']:
        errors.append('dataset root changed')
    return {'source_mutations': changes, 'response_integrity_errors': errors, 'fresh_agents': len(agents),
            'valid': not changes and not errors, 'provider_model_identity_attested': False}


def report(out, summary, records):
    lines = ['# GPT-6 Luna collaboration-agent experiment', '',
             f"Status: **{summary['status']}**; {summary['complete_pairs']}/{summary['selected_tasks']} complete pairs.", '',
             f"Frozen dataset: `{summary['dataset_root']}`.", '',
             'Each call requests a fresh `gpt-6-luna` collaboration agent with `fork_turns=none`. This is an agent simulation, not a native API benchmark. Token usage, returned model snapshot, sampling settings and tool disabling cannot be independently attested by this transport.', '',
             'Direct generation uses one coding call. The other arm runs the actual strict Tier 0 VeriSlop CLI with TESTED required, its existing Lean gates and counterexample review checkpoints. All public and hidden cases must pass; a blocked CLI task is unsuccessful.', '']
    for arm, label in (('raw', 'Direct Luna'), ('verislop', 'Full VeriSlop with Luna')):
        r = summary['arms'][arm]
        lines.append(f"- **{label}:** {r['successful_tasks']}/{r['attempted_tasks']} successful tasks; {r['held_out_passed']}/{r['held_out_total']} hidden cases and {r['public_passed']}/{r['public_total']} public cases passed; {r['model_calls']} model calls. Tokens unavailable.")
    lines += ['', 'Raw: one call; full CLI: at most 32 calls. Each response is limited to 1 MiB UTF-8. There are no model generation, proof search, review or overall experiment deadlines. Candidate execution retains the same one-second case and 512 MiB memory limits as Qwen.', '',
              'The task shuffle and alternating arm order use seed 20261007. Model agents see only the exact system/user request; hidden cases and reference code are excluded. The no-tools instruction is a controller policy, not an enforced model sandbox. Candidate code is graded in the existing filesystem/network sandbox.', '',
              'The collaboration transport uses provider-alias review identity, because no immutable provider snapshot is exposed. The Qwen experiment pins an Ollama digest and enforces sampling/token controls unavailable here. Qwen runs concurrently, so timing also includes local resource contention. These separate single-run experiments do not establish a causal benefit of verification or universal implementation correctness.', '',
              'Authoritative live scores: `summary.json`, `results.jsonl`; frozen protocol: `protocol.json`. `execution-source/` captures measured sources. Each artifact directory retains exact prompts, captured agent finals, hash-bound receipts, transcripts, CLI diagnostics, generated code and case observations. The final `run-manifest.json` binds final evidence bytes.', '']
    failures = [r for r in records if r['arm'] == 'verislop' and r['cli_diagnostics']]
    if failures:
        lines += ['## Recorded workflow failures', '']
        for r in failures[:5]:
            d = r['cli_diagnostics'][0]
            lines.append(f"- {r['task_id']}: `{d.get('code')}` — {str(d.get('message', ''))[:500]}. See `{r['artifact_path']}/score.json`.")
    counterexamples = [(r, c) for r in records for c in r['held_out_results'] if c['status'] == 'FAIL' and 'observed' in c]
    if counterexamples:
        lines += ['', '## Concrete candidate counterexamples', '']
        for r, c in counterexamples[:5]:
            lines.append(f"- {r['task_id']}/{r['arm']}, case `{c['id']}`: expected `{json.dumps(c['expected'], ensure_ascii=False)[:350]}`, observed `{json.dumps(c['observed'], ensure_ascii=False)[:350]}`. Full input/output in frozen cases and `{r['artifact_path']}/score.json`.")
    if summary.get('response_integrity_errors'):
        lines += ['', 'Integrity errors: ' + json.dumps(summary['response_integrity_errors'])]
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--harness-calls', type=int, default=32)
    parser.add_argument('--case-seconds', type=float, default=1)
    parser.add_argument('--pending', action='store_true', help='Print the next mailbox request, without generating a response')
    parser.add_argument('--publish-file', type=Path, help='Atomically publish a captured fresh-agent response envelope')
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if args.pending:
        print(json.dumps(pending_request(out), ensure_ascii=False))
        return 0
    if args.publish_file:
        print(json.dumps(publish_response(out, load(args.publish_file)), ensure_ascii=False))
        return 0
    if not (1 <= args.limit <= 100 and 1 <= args.harness_calls <= 32 and args.case_seconds == 1):
        parser.error('invalid fixed experiment limits')
    manifest = verify_dataset()
    tasks = [json.loads(line) for line in (ROOT / 'tasks.jsonl').read_text().splitlines()]
    random.Random(20261007).shuffle(tasks)
    tasks = tasks[:args.limit]
    out.mkdir(parents=True, exist_ok=False)
    write(out / 'provider-home/endpoint-profiles.json', endpoint_profiles())
    cfg = configuration()
    write(out / 'config.json', cfg)
    from verislop.verifiers import host_environment, registry_snapshot
    protocol = {
        'format': 'verislop.collaboration-benchmark-protocol/0.1', 'model': MODEL,
        'returned_model': None, 'model_digest': None, 'model_identity_attested': False,
        'transport': 'collaboration-agent-simulation', 'fork_turns': 'none', 'fresh_agent_per_call': True,
        'dataset_root': manifest['dataset_root'], 'task_order': [t['id'] for t in tasks], 'seed': 20261007,
        'arm_order': 'raw first for even pair indices; VeriSlop first for odd indices',
        'raw_calls': 1, 'harness_calls': args.harness_calls, 'max_response_bytes': MAX_RESPONSE_BYTES,
        'per_call_output_tokens': None, 'output_token_budget': None, 'token_usage_available': False,
        'temperature': None, 'thinking': None, 'native_json_mode': None,
        'sampling_controls_available': False, 'output_token_limit_enforced': False,
        'schema_max_output_tokens_hint': 8192, 'require_fixed_model_snapshot': False,
        'case_seconds': args.case_seconds, 'candidate_memory_mb': 512,
        'arm_seconds': None, 'global_seconds': None,
        'generation_deadline_policy': 'disabled; no generation, proof-search or review wall deadline',
        'agent_tool_policy': 'no tools, filesystem access or delegation requested; instruction-based only',
        'host_environment': host_environment(), 'verifier_registry': registry_snapshot(),
        'config_hash': digest(encode(cfg)), 'source_hashes': source_inventory(),
        'endpoint_profiles_hash': digest((out / 'provider-home/endpoint-profiles.json').read_bytes()),
        'user_selected_mode': 'full strict CLI; blocked stages count as unsuccessful tasks',
        'concurrent_experiment': 'qwen-local-002; timing can include shared-host contention',
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    write(out / 'protocol.json', protocol)
    for rel in protocol['source_hashes']:
        destination = out / 'execution-source' / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, destination)
    records, start = [], time.monotonic()
    summary = summarize(records, manifest, protocol)
    write(out / 'summary.json', summary)
    report(out, summary, records)
    try:
        for index, task in enumerate(tasks):
            verify_dataset()
            for arm in (('raw', 'verislop') if index % 2 == 0 else ('verislop', 'raw')):
                row = run_arm(task, arm, index, out, args)
                records.append(row)
                with (out / 'results.jsonl').open('ab') as stream:
                    stream.write(encode(row))
                summary = summarize(records, manifest, protocol)
                write(out / 'summary.json', summary)
                report(out, summary, records)
                print(json.dumps({'pair': index + 1, 'task': task['id'], 'arm': arm,
                                  'status': row['workflow_status'], 'complete_pairs': summary['complete_pairs'],
                                  'hidden_passed': row['hidden_passed'], 'hidden_total': row['hidden_total']}), flush=True)
        checks = audit(out, manifest, protocol, records)
        summary = summarize(records, manifest, protocol)
        summary.update(checks, status='COMPLETE' if checks['valid'] else 'INVALID',
                       wall_seconds=round(time.monotonic() - start, 3), finished_at_utc=datetime.now(timezone.utc).isoformat())
        write(out / 'summary.json', summary)
        report(out, summary, records)
        write(out / 'active-arm.json', {'phase': 'finished', 'status': summary['status']})
        files = {p.relative_to(out).as_posix(): digest(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'run-manifest.json'}
        write(out / 'run-manifest.json', {'format': 'verislop.collaboration-benchmark-evidence/0.1',
                                        'dataset_root': manifest['dataset_root'], 'protocol_hash': digest(encode(protocol)),
                                        'files': files, 'complete': summary['complete'], 'valid': summary['valid']})
        return 0 if summary['complete'] and summary['valid'] else 2
    except BaseException as exc:
        write(out / 'active-arm.json', {'phase': 'infrastructure_failure', 'error': type(exc).__name__, 'message': str(exc)})
        write(out / 'driver-error.json', {'error': type(exc).__name__, 'message': str(exc), 'completed_arm_records': len(records)})
        raise


if __name__ == '__main__':
    sys.exit(main())
