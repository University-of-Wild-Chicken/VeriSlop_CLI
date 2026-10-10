"""Read-only diagnosis; never imports the project or invokes any verifier/model."""
import collections
import datetime
import hashlib
import json
import pathlib

ROOT = pathlib.Path('/home/augustus/VeriSlop_CLI')
OUT = ROOT / 'validation/tier2-native-live-driver-018/postmortem'
DRIVER = ROOT / 'validation/tier2-native-live-driver-018'
RUN = ROOT / 'synthetic_dataset/bootstrap/stages/tier2-source-facets-018/run'
ART = RUN / 'artifacts/D21/verislop'
ledger = {}

def raw(path):
    path = pathlib.Path(path)
    if not path.is_absolute():
        path = ROOT / path
    data = path.read_bytes()
    ref = {'path': str(path), 'sha256': 'sha256:' + hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    if str(path) in ledger:
        assert ledger[str(path)] == ref, 'artifact changed during diagnosis'
    ledger[str(path)] = ref
    return data

def load(path):
    return json.loads(raw(path))

def ref(path, pointer=None):
    raw(path)
    out = dict(ledger[str(pathlib.Path(path).resolve())])
    if pointer is not None:
        out['json_pointer'] = pointer
    return out

spec = load(OUT / 'specification-before-inspection-001.json')
authorization = load(spec['authorization']['path'])
assert authorization['controller_status'] == 'STOP'
assert authorization['all_native_authors_final_delivered_and_stopped'] is True
assert authorization['actual_driver_returncode'] == 2
terminal = load(ART / 'result.json')
stdout = load(ART / 'stdout.json')
driver = load(DRIVER / 'driver-result.json')
bootstrap = load(RUN / 'BOOTSTRAP-RESULT.json')
recovery = load(ART / 'package/recovery.json')
requests = []
transcripts = {}
packages = []
for pkg in sorted(ART.glob('package*')):
    report = load(pkg / 'report.json')
    events = [json.loads(line) for line in raw(pkg / 'events.jsonl').decode().splitlines()]
    for path in sorted((pkg / 'agents/transcripts').glob('*.json')):
        t = load(path)
        transcripts[t['request_id']] = (path, t)
    packages.append({'package': pkg.name, 'report': ref(pkg / 'report.json'),
                     'terminal_status': report['terminal_status'], 'milestones': report['counts']['milestones'],
                     'review': report['review'],
                     'stage_events': [{k: e[k] for k in ('seq', 'time', 'type', 'phase', 'message') if k in e}
                                      for e in events if e.get('type') in ('stage_started', 'run_finished')]})
for path in sorted((DRIVER / 'relay').glob('*/pending.json')):
    pending = load(path)
    final_path = path.parent / 'literal-final.json'
    text = load(final_path)['text']
    envelope = load(path.parent / 'response-envelope.json')
    assert envelope['text'] == text
    tid = envelope['agent_task_id']
    tpath, transcript = transcripts[tid]
    assert transcript['response'] == text
    carrier_path = pathlib.Path(pending['carrier_path'])
    carrier = load(carrier_path)
    assert ledger[str(carrier_path)]['sha256'] == pending['carrier_sha256']
    assert carrier['request_sha256'] == pending['request_sha256']
    row = {'request_id': pending['request_id'], 'role': pending['role'], 'agent': tid,
           'requested_model': envelope['requested_model'], 'model_identity_attested': envelope['model_identity_attested'],
           'fork_turns': pending['fork_turns'], 'literal_final': ref(final_path, '/text'),
           'response_envelope': ref(path.parent / 'response-envelope.json'), 'native_transcript': ref(tpath),
           'own_carrier': ref(carrier_path), 'user_characters': len(carrier['user']),
           'user_utf8_bytes': len(carrier['user'].encode()), 'final_characters': len(text)}
    try:
        value = json.loads(text)
        row['literal_json_status'] = 'VALID'
        row['protocol_encoding'] = value.get('encoding')
        row['verdict'] = value.get('verdict')
        row['proposed_counterexamples'] = len(value.get('counterexamples', []))
        if pending['role'].startswith('formalizer/'):
            used = {r['theorem'] for r in value['obligations'].values() if 'theorem' in r}
            used |= {r['theorem'] for r in value['witness_obligations'].values()}
            row['supplied_theorems'] = sorted(value['theorems'])
            row['unbound_theorems'] = sorted(set(value['theorems']) - used)
    except json.JSONDecodeError as error:
        row['literal_json_status'] = 'INVALID'
        row['parse_witness'] = {'message': error.msg, 'position': error.pos, 'line': error.lineno,
                                'column': error.colno, 'context': text[max(0, error.pos - 100):error.pos + 100]}
        if text.startswith('Inspection incomplete'):
            row['incomplete_inspection_literal'] = text
    requests.append(row)

initial_snap = ART / 'package/agents/memory/snapshots/00000011-23bb074789abe546042751830c9a2f95fcefd93e6016a41ed81ed5a2ae71d275.json'
snap = load(initial_snap)
payload_ref = next(x['blob_ref'] for x in snap['artifacts'] if x['source_ref'] == 'payload.json')
initial_payload_path = ART / 'package' / payload_ref['path']
initial_payload = load(initial_payload_path)
assert ref(initial_payload_path)['sha256'] == payload_ref['sha256']
check_path = ART / 'package-repair-01/contract/candidate/statement-check.json'
check = load(check_path)
checked = check['critique']['results'][0]['checked']
attempts_path = ART / 'package-repair-01/contract/proofs/attempts.jsonl'
proof_attempts = [json.loads(line) for line in raw(attempts_path).decode().splitlines()]
acceptance_path = ART / 'package-repair-01/accepted/acceptance.json'
acceptance = load(acceptance_path)
source_paths = {name: ROOT / ('verislop/' + name + '.py') for name in ('agents', 'formal_frontend', 'contract_refutation', 'prove')}
source_refs = {name: ref(path) for name, path in source_paths.items()}
for name, path in source_paths.items():
    assert raw(path) == raw(RUN / 'execution-source/verislop' / path.name), 'source differs from stage frozen execution source'

findings = [
 {'id': 'F01', 'priority': 1, 'class': 'TRANSPORT_INSPECTION_FAILURE',
  'conclusion': 'Four critics returned non-protocol incomplete-inspection finals; the initial typechecked formalization was sent back for contract repair, and the later proof critic prevented every model prover call.',
  'requests': ['0003', '0004', '0013', '0014'],
  'exact_initial_blocking_diagnostics': initial_payload['diagnostics'],
  'evidence': [ref(initial_snap), ref(initial_payload_path, '/diagnostics'), ref(ART / 'package-repair-02/recovery-context.json', '/autonomous_critique')],
  'causal_source': {'reference': source_refs['prove'], 'lines': [378, 389],
                    'witness': 'if previous_critique["status"] == "INCOMPLETE": break occurs before proposal = agent(...)'},
  'limit': 'Authors self-report tool truncation; native records do not contain their internal tool-call trace. Exact truncation layer or batching cause is unconfirmed. Complete carrier availability is not demonstrated consumption.'},
 {'id': 'F02', 'priority': 2, 'class': 'MODEL_JSON_SYNTAX_FAILURE',
  'conclusion': 'Five of eight formalizer finals are invalid JSON independently of the CLI parser. Four fail near nested record/fold delimiters; one has an unmatched outer object at EOF.',
  'requests': ['0005', '0007', '0009', '0015', '0017'],
  'limit': 'Raw finals, envelopes and native transcript responses match byte-for-byte as strings. No output-length truncation or provider error is evidenced; these are model content failures.'},
 {'id': 'F03', 'priority': 3, 'class': 'MODEL_BINDING_SCHEMA_FAILURE',
  'conclusion': 'Final request0019 is valid JSON but supplies public_examples without binding that theorem to a frozen obligation or witness. Native critic0020 identifies the same specific defect. The parser correctly rejects it.',
  'requests': ['0019', '0020'],
  'evidence': [ref(ART / 'package-repair-02/contract/candidate/statement-check.json', '/diagnostics')],
  'causal_source': {'reference': source_refs['formal_frontend'], 'lines': [644, 645],
                    'witness': 'if set(maps["theorems"]) != used_theorems: raise FrontendError(...)'}},
 {'id': 'F04', 'priority': 4, 'class': 'CONCRETE_GENERIC_HARNESS_DEFECT',
  'conclusion': 'Candidate refutation re-derives DecidableEq for enums whose frontend-generated Lean already derived it. Actual critic0012 replay records a duplicate enum-generated declaration; it cannot certify the proposed closed check.',
  'exact_kernel_witness': checked['diagnostics'][2]['errors'][0],
  'source_witnesses': [{'reference': source_refs['formal_frontend'], 'line': 665,
                        'text': 'source.append("  deriving _root_.DecidableEq")'},
                       {'reference': source_refs['contract_refutation'], 'lines': [367, 396],
                        'text': 'names = [e["lean_decl"] for e in profile.enums.values()]; emits deriving instance DecidableEq for every name'}],
  'evidence': [ref(check_path, '/critique/results/0/checked/diagnostics/2')],
  'limit': 'The same compilation also reports decide reduction getting stuck. That separate reduction limitation remains after the duplicate-declaration defect and is not shown to be resolved. No Lean build or fresh reproduction was performed in this diagnosis.'},
 {'id': 'F05', 'priority': 5, 'class': 'PROOF_UNRESOLVED',
  'conclusion': 'Only one built-in proof attempt ran. It elaborated but retained two sorry declarations, leaving all nine original implementation guarantees dependent on sorryAx. No model prover, implementation, link, tests, release review or source closure was reached.',
  'evidence': [ref(attempts_path), ref(acceptance_path, '/obligations')],
  'actual_proof_attempts': proof_attempts,
  'original_guarantee_outcomes': {oid: {'lean_symbol': row['lean_symbol'], 'proved': row['proved'], 'axioms': row['axioms']}
                                  for oid, row in acceptance['obligations'].items() if oid in ('O1','O2','O3','O4','O5','O6','O7','I1','S1')},
  'limit': 'Unresolved proofs do not disprove the functional requirements. A future complete critic/prover run can still fail mathematically.'}
]

repro_spec = {'format': 'verislop.unrelated-refutation-regression-specification/1', 'status': 'PROSPECTIVE_NOT_EXECUTED',
 'scope': 'Generic enum/record DecidableEq closed-check support; no D21/A23 candidate, formula, example, proof or oracle.',
 'fixture': {'enum': 'Two fresh unrelated alternatives, e.g. Mode.keep/Mode.drop',
             'carrier': 'A small nonrecursive record containing that enum; optionally list/option wrappers',
             'body': 'A typed pure identity or constant function with no source-facet task semantics',
             'ground_proposition': 'Equality of one concrete output with itself, checked through the exact registered candidate refutation kernel route'},
 'required_before_fix_observation': 'Frontend compilation creates enum equality machinery; appending current _derivations attempts to create that machinery again and triggers the actual duplicate declaration class.',
 'required_after_fix_observations': ['No duplicate enum-generated declaration', 'Actual kernel proof of exact closed proposition with checked statement and allowed axioms',
                                   'Existing candidate environment declaration hashes remain unchanged', 'A false equation is never accepted; unsupported reductions stay explicitly UNKNOWN',
                                   'Enum-only and nested record/list/option cases use unrelated fixtures'],
 'implementation_constraint': 'Reuse only actual checked safe equality instances, or construct independent kernel-checked equality support without repeating generated declarations. Do not trust profile instance metadata alone or promote host evaluator equality.',
 'not_executed_in_this_report': True}

report = {'format': 'verislop.native-terminal-diagnosis/1', 'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'stage': bootstrap['stage'], 'mode': 'READ_ONLY', 'terminal_status_unchanged': terminal['status'],
 'milestone_authority': False, 'not_correctness_or_lifecycle_evidence': True,
 'specification': ref(OUT / 'specification-before-inspection-001.json'), 'authorization': ref(spec['authorization']['path']),
 'source_root': terminal['source_root'], 'request_set_root': terminal['request_set_root'], 'protocol_sha256': bootstrap['protocol_sha256'],
 'actual_driver_returncode': driver['returncode'], 'active_terminal_package': terminal['package'],
 'final_stopped_at': terminal['cli_stopped_at'], 'final_diagnostic': terminal['cli_diagnostics'][0],
 'counts': {'native_requests': len(requests), 'unique_native_authors': len({x['agent'] for x in requests}),
            'roles': dict(collections.Counter(x['role'].split('/')[0] for x in requests)),
            'recovery_rounds': stdout['summary']['recovery']['consumed_rounds'], 'max_recovery_rounds': recovery['max_repair_rounds'],
            'packages': len(packages), 'formalizer_invalid_json': 5, 'formalizer_valid_json': 3,
            'critic_non_protocol_incomplete_inspection': 4, 'critic_protocol_REPAIR': 6, 'critic_protocol_ACCEPT': 1,
            'model_prover_requests': 0, 'builtin_proof_attempts': len(proof_attempts), 'implementation_requests': 0,
            'certified_counterexamples': len(checked['receipts']), 'live_model_identity_attested': False},
 'actual_native_proposed_probe_result': {'request': '0012', 'model_verdict': 'ACCEPT', 'native_status': check['critique']['status'],
                                       'checked_status': checked['status'], 'certified_receipts': len(checked['receipts']),
                                       'bounded_scan': checked['bounded_scan'], 'not_functional_acceptance': True,
                                       'evidence': ref(check_path, '/critique/results/0/checked')},
 'findings': findings, 'requests': requests, 'packages': packages,
 'generic_next_steps_only': ['Qualify complete large-carrier inspection with a reusable exact reader and one bounded outer-tool view; preserve full carrier checks, literal finals and native review gates.',
                           'Improve generic invalid-JSON diagnostics with precise parser offset/context; preserve literal response and prohibit guessed brace repair or silent syntax rewriting.',
                           'Allow generic response-shape validation before literal submission under an explicitly revised reader/author protocol, without task-specific hints or trusted author validation.',
                           'Fix enum equality re-derivation and qualify unrelated actual kernel fixtures before a fresh frozen-source run.'],
 'unrelated_reproduction_specification': repro_spec,
 'changes_performed': ['Created diagnostic specification, read-only extraction script, diagnostic report and hashed read ledger only'],
 'actions_not_performed': spec['prohibitions'],
 'evidence': [ref(ART / 'result.json'), ref(ART / 'stdout.json'), ref(RUN / 'BOOTSTRAP-RESULT.json'), ref(DRIVER / 'driver-result.json'), ref(ART / 'package/recovery.json')]}
for path, expected in list(ledger.items()):
    assert raw(path) == pathlib.Path(path).read_bytes()
    assert ledger[path] == expected
(OUT / 'diagnostic-report-001.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(OUT / 'read-ledger-001.json').write_text(json.dumps({'format':'verislop.read-only-diagnostic-ledger/1', 'unchanged_at_completion':True, 'files':list(ledger.values())}, indent=2)+'\n')
manifest = {'format':'verislop.read-only-diagnostic-manifest/1', 'milestone_authority':False,
            'files':[{'path':str(p), 'sha256':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in [OUT/'specification-before-inspection-001.json', OUT/'diagnose-001.py', OUT/'diagnostic-report-001.json', OUT/'read-ledger-001.json']]}
(OUT / 'manifest-001.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'status':'READ_ONLY_DIAGNOSIS_COMPLETE','report':str(OUT/'diagnostic-report-001.json'),'files_read':len(ledger),'counts':report['counts']}))
