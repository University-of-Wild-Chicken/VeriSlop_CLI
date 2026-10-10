"""Read-only execution of stage017's frozen finite evidence predicates/probes."""
import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path('/home/augustus/VeriSlop_CLI')
OUT = ROOT / 'validation/tier2-d21-scope-audit-017'
PROJECT = ROOT / 'synthetic_dataset/bootstrap/stages/tier2-source-facets-017/project'
RUN = PROJECT.parent / 'run'
PKG = RUN / 'artifacts/D21/verislop/package'
DRIVER = ROOT / 'validation/tier2-native-live-driver-017'
READS = {}
DIRECTORIES = {}
guard = False

def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def audit_hook(event, args):
    global guard
    if guard:
        return
    guard = True
    try:
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).absolute()
            mode = args[1]
            flags = args[2]
            reading = (isinstance(mode, str) and 'r' in mode) or (mode is None and not flags & (os.O_WRONLY | os.O_RDWR))
            if not reading or not p.is_file():
                return
            name = str(p)
            # No historical task stages or generic fixture answers are authorized.
            if '/synthetic_dataset/bootstrap/stages/' in name and not (p.is_relative_to(PROJECT) or p.is_relative_to(RUN)):
                raise RuntimeError('forbidden historical-stage read: ' + name)
            if '/tests/fixtures/' in name:
                raise RuntimeError('forbidden fixture-answer read: ' + name)
            digest = sha(p.read_bytes())
            READS.setdefault(name, set()).add(digest)
        elif event in ('os.listdir', 'os.scandir') and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).absolute()
            if p.is_dir():
                DIRECTORIES.setdefault(str(p), set()).add(sha(canonical_bytes(sorted(os.listdir(p)))))
    finally:
        guard = False

sys.addaudithook(audit_hook)

def read(p):
    return json.loads(p.read_bytes())

def write(n, obj):
    with (OUT / n).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n')

def seal_check():
    manifest = read(RUN / 'BOOTSTRAP-EVIDENCE-MANIFEST.json')
    twin = read(RUN / 'EVIDENCE-MANIFEST.json')
    errors = []
    for name, expected in manifest['files'].items():
        p = RUN / name
        if not p.is_file() or sha(p.read_bytes()) != expected:
            errors.append(name)
    actual = {str(p.relative_to(RUN)) for p in RUN.rglob('*') if p.is_file()}
    extras = sorted(actual - set(manifest['files']) - {'BOOTSTRAP-EVIDENCE-MANIFEST.json', 'EVIDENCE-MANIFEST.json'})
    return {'manifest_sha256': sha((RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json').read_bytes()),
            'twins_equal': twin == manifest,
            'files': len(manifest['files']), 'file_mismatches': errors, 'unlisted_files': extras,
            'files_root': sha(canonical_bytes(manifest['files'])),
            'root_matches': sha(canonical_bytes(manifest['files'])) == manifest['files_root'],
            'protocol_sha256': manifest['protocol_sha256'], 'source_root': manifest['source_root']}

def safe(n, fn):
    started = time.monotonic()
    try:
        result = fn()
        item = {'actual_call_completed': True, 'exception': None, 'result': result}
    except Exception as exc:
        item = {'actual_call_completed': False, 'exception': type(exc).__name__ + ': ' + str(exc),
                'traceback': traceback.format_exc(), 'result': None}
    item['wall_ms'] = round((time.monotonic()-started)*1000)
    write(n + '.json', item)
    print(n, 'completed' if item['actual_call_completed'] else item['exception'], flush=True)
    return item

started = datetime.datetime.now(datetime.timezone.utc).isoformat()
before = seal_check()
binding = read(OUT / 'pre-generation-binding-001.json')
checks = read(OUT / 'planned-evidence-checks.json')
probes = read(OUT / 'public-probes.json')
original = read(OUT / 'original-public-requirements.json')
freeze = read(OUT / 'FREEZE-MANIFEST.json')
receipts = {}
expected_receipts = {
 'controller-stop-receipt.json': '54cc1510a6418f8d9a0039fa581a4e4caa011bee7e5c8da2d683e2d77a9e9a93',
 'native-actual-process-receipt.json': '70a7eaa599a828cebdf6d77e5ae1f691f17ef83f322a77c6d6bdcdc0b98fc9e2',
 'frozen-verify-process-receipt.json': 'c3c8b3d5ea5f1de96f6fa01f41a5e7e278ddd334c4ae98700e9f418a2c230dba',
 'native-prerequisite-checkpoint.json': '62a2c5cb3845759a9512ea315223487d3cfda9b77e5b4a3a27b2c879b7e48f92',
 'prerequisite-reader-error-001.json': '458e7592cd5aabf52e14c280704081f8d94ad422898d81ef064c8a7819d8679e',
 'terminal-receipt-reader-error-001.json': '5abe72f7a24c2d91c1248f5800f4c13f7c80fd0191eab6871a3a2b1ae32f606f',
}
for name, expected in expected_receipts.items():
    p = DRIVER / name
    assert sha(p.read_bytes()) == 'sha256:'+expected, name
    receipts[name] = read(p)
stop = receipts['controller-stop-receipt.json']
assert stop['status'] == 'STOPPED' and stop['outstanding_author_count'] == 0
assert stop['authors_completed'] == stop['authors_spawned'] == 14
assert len(set(stop['author_ids'])) == 14
assert all(s['author_completed'] and s['submission_resolved'] and s['submit_rc'] == 0 and s['literal_bytes'] > 0 for s in stop['submissions'])
assert len(stop['submissions']) == 14
assert receipts['native-actual-process-receipt.json']['actual_observed_exit_code'] == 2
assert receipts['frozen-verify-process-receipt.json']['actual_exit_code'] == 0
assert len(checks['checks']) == 24 and len(probes['probes']) == 9
assert all(sha((OUT / name).read_bytes()) == digest for name, digest in binding['preregistration_unchanged'].items())

sys.path.insert(0, str(PROJECT))
from verislop.package import Package
from verislop import export, view, lifecycle, dsl
from verislop.backends import vscore3_closure
from verislop.bridges import vscore3_checker
from verislop import review_counterexamples
from verislop.targets import python_target
from synthetic_dataset.tools import bootstrap_tier2
from verislop import verifiers
assert Path(verifiers.__file__).is_relative_to(PROJECT)
pkg = Package(PKG)
report = read(PKG / 'report.json')

def ir_check():
    ir, digest, cert, diags = export.verified_ir(pkg)
    return {'accepted_ir_hash': digest, 'certificate_ref': ir.get('acceptance_certificate_ref') if ir else None,
            'diagnostics': [d.to_json() for d in diags],
            'obligations': {k:{'kind':v['kind'],'role':v['role'],'required':v['required'], 'formal':v['formal']} for k,v in ir['obligations'].items()}} if ir else {'diagnostics':[d.to_json() for d in diags]}

ir_result = safe('registered-accepted-ir-validation-001', ir_check)
mechanical = safe('registered-mechanical-snapshot-001', lambda: vscore3_closure.mechanical_snapshot(pkg))

def edge_check():
    accepted, pending, diags = vscore3_checker.verify_published(pkg, 'implementation', rebuild=False)
    return {'accepted':accepted, 'pending':pending, 'diagnostics':[d.to_json() for d in diags]}

edge = safe('registered-published-edge-validation-001', edge_check)
native = safe('registered-native-audit-001', lambda: bootstrap_tier2.native_audit(pkg,report,configuration=RUN/'config.json'))
overlay = safe('registered-lifecycle-view-001', lambda: view.derive(pkg))

def exact_sources():
    protocol = read(RUN/'protocol.json')
    # Bind current frozen source inventory to preparation rather than guessing a source root.
    source_map = protocol['source_files']
    errors = []
    for name, expected in source_map.items():
        for base in (ROOT, PROJECT, RUN/'execution-source'):
            p = base/name
            if not p.is_file() or sha(p.read_bytes()) != expected:
                errors.append(str(p))
    frozen_registry = read(OUT/'registered-verifier-snapshot-001.json')
    registry = {k: {'id':k, 'sha256':verifiers.verifier_hash(k)} for k in verifiers.VERIFIERS}
    return {'source_files': len(source_map), 'source_map_root':sha(canonical_bytes(source_map)),
            'source_mismatches':errors, 'protocol_sha256':sha((RUN/'protocol.json').read_bytes()),
            'registry':registry,'frozen_registry':frozen_registry}

sources = safe('terminal-source-verifier-bindings-001',exact_sources)

# The nine frozen JSON inputs become nominal immutable DSL values solely by the
# registered profile's ordered fields and its registered strict wire encoder.
profile_ref = read(PKG/'accepted/acceptance.json')['artifacts']['profile']
profile = dsl.Profile.from_json(read(PKG/profile_ref['path']))
def nominal(value, sort):
    if sort in ('Nat','Int','String','Bool'):
        return value
    if 'list' in sort:
        return tuple(nominal(v,sort['list']) for v in value)
    if 'option' in sort:
        return dsl.OPTION_NONE if value is None else dsl.option_some_v(nominal(value,sort['option']))
    if 'enum' in sort:
        return ('enum',sort['enum'],value)
    if 'record' in sort:
        name = sort['record']
        return ('record',name,tuple(nominal(value[f['name']],f['sort']) for f in profile.records[name]['fields']))
    raise ValueError('probe sort is not admitted by frozen registered profile')

probe_summaries=[]
for probe in probes['probes']:
    value = nominal(probe['input'], {'record':'Input'})
    wire = python_target.encode_arg(value,{'record':'Input'},profile)
    decoded = python_target.decode_result(wire,{'record':'Input'},profile)
    assert decoded == value
    proposal = {'kind':'target_case','obligation_id':'O5' if probe['id']=='PUB-04' else 'O7' if probe['id'] in ('PUB-01','PUB-02') else 'O6','assignment':[wire]}
    write('public-probe-'+probe['id']+'-binding-001.json', {'frozen_probe_file': 'public-probes.json',
          'frozen_probe_file_sha256':sha((OUT/'public-probes.json').read_bytes()),
          'probe_id':probe['id'], 'affected_original_ids':probe['affected_original_ids'],
          'registered_wire_encoder':'verislop.targets.python_target.encode_arg',
          'registered_profile_sha256':profile_ref['sha256'], 'proposal':proposal,
          'wire_roundtrip_exact':True,'expected_output':probe['expected_output'],
          'meaning':'This target_case probes the grounded accepted functional predicate. It does not independently observe or assert source output bytes.'})
    result = safe('public-probe-'+probe['id']+'-receipt-001', lambda proposal=proposal: review_counterexamples.replay_probe(pkg,'release',proposal))
    receipt = result['result'] or {}
    probe_summaries.append({'id':probe['id'],'status':receipt.get('status','INFRASTRUCTURE_FAILURE'),
         'diagnostics':receipt.get('diagnostics',[]),'observed':receipt.get('observed'),
         'receipt_path':'public-probe-'+probe['id']+'-receipt-001.json',
         'tested_promoted':False,'universal_proof':False})
    print('probe-status',probe['id'],probe_summaries[-1]['status'],flush=True)

after = seal_check()
write('terminal-evidence-capture-summary-001.json',{
 'format':'scope-audit-terminal-evidence-capture/1','audit_id':'tier2-d21-scope-audit-017',
 'started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'registered_call_count':6,'frozen_probe_attempt_count':len(probe_summaries),
 'stop_and_process_receipts':{n:sha((DRIVER/n).read_bytes()) for n in expected_receipts},
 'seal_before':before,'seal_after':after,'sealed_bytes_unchanged':before==after,
 'probe_summaries':probe_summaries,'new_lifecycle_assurance_assigned':False,
 'native_status_metadata':{k:report.get(k) for k in ('mechanical_status','release_status','terminal_status')},
 'audit_scope':'exact unchanged 24 preregistered checks and 9 optional public probes',
 'qualification_authority':'completed audited gate019 ONLY; support-milestone017 label is not failed qualification017/018',
 'identity':'UNATTESTED','token_metrics':'unavailable'})
guard=True
write('terminal-capture-read-ledger-001.json',{
 'format':'scope-audit-read-ledger/1','audit_id':'tier2-d21-scope-audit-017',
 'capture_method':'Python audit-hook read/open and directory events; every file hashed at read entry',
 'files':[{'path':p,'sha256_identities':sorted(h),'scope':'sealed current task' if p.startswith(str(RUN)) else 'matching frozen generic framework' if p.startswith(str(PROJECT)) else 'audit or receipt/provenance' if p.startswith(str(ROOT/'validation')) else 'current root production or toolchain/host import'} for p,h in sorted(READS.items())],
 'directory_reads':[{'path':p,'sorted_names_sha256_identities':sorted(h)} for p,h in sorted(DIRECTORIES.items())]})
print('terminal-capture-complete', 'sealed-unchanged', before==after, 'probes',len(probe_summaries),flush=True)
