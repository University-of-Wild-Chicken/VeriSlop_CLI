"""Offline read-only P03 evidence audit. Never imports frozen runtime code."""
from __future__ import annotations
import argparse
from pathlib import Path
import tarfile
from verislop import canonical as c, fsutil
from verislop.targets import python_target as pt
from synthetic_dataset.tools import check_data_pipeline_poc as old
from synthetic_dataset.tools.data_pipeline_oracle import wire

TASK = 'P03-unicode-labels'
# Literal expectations derived from the public request, not candidate code.
BOUNDARIES = [
    ({'labels': ['', 'e\u0301', 'é', '  ', 'é'], 'prefix': '前'},
     {'labels': ['前e\u0301', '前é', '前  ', '前é'], 'count': 4}),
    ({'labels': ['', 'e\u0301', 'é', 'é'], 'prefix': ''},
     {'labels': ['e\u0301', 'é', 'é'], 'count': 3}),
    ({'labels': ['', ''], 'prefix': '前'}, {'labels': [], 'count': 0}),
    ({'labels': [], 'prefix': ''}, {'labels': [], 'count': 0}),
    ({'labels': [' ', '\t', '😀', '\u0000'], 'prefix': 'e\u0301'},
     {'labels': ['e\u0301 ', 'e\u0301\t', 'e\u0301😀', 'e\u0301\u0000'], 'count': 4}),
]


def inside(root, name):
    fsutil.check_relpath(name)
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('path escapes evidence root')
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('symlink evidence path')
    return path


def boundaries(implementation, file='requested.py', qualname='solve'):
    inventory = pt.inventory(implementation)
    if inventory.errors:
        raise ValueError(str(inventory.errors))
    result = {'status': 'NOT_RUN', 'cases': [], 'scope': 'Independent finite observations only'}
    try:
        with_harness = pt.Harness(implementation, inventory.files, {'solve': (file, qualname)},
                                 per_call_timeout=1, memory_mb=512,
                                 require_network_isolation=True, require_filesystem_isolation=True)
        try:
            result['isolation'] = with_harness.isolation
            for data, expected in BOUNDARIES:
                response = with_harness.call('solve', [wire(data)])
                passed = c.dumps(response) == c.dumps({'op': 'result', 'id': with_harness.calls, 'value': wire(expected)})
                result['cases'].append({'input': data, 'expected': expected, 'response': response, 'passed': passed})
            result['status'] = 'PASS' if all(x['passed'] for x in result['cases']) else 'FAIL'
        finally:
            with_harness.close()
    except (pt.HarnessError, OSError) as exc:
        result.update(status='INFRASTRUCTURE_FAILURE' if getattr(exc, 'kind', 'launch') in
                      {'isolation', 'launch'} else 'FAIL', diagnostic=str(exc))
    return result


def receipt_check(receipt, package):
    """Recompute every retained response verdict; historical PASS flags are not trusted."""
    if (receipt.get('format') != 'verislop.data-pipeline-request-oracle/0.1'
            or receipt.get('native_gate_passed') is not True
            or receipt.get('input_bytes_unchanged') is not True
            or receipt.get('diagnostics') != []):
        raise ValueError('historical completion flags/diagnostics mismatch')
    isolation = receipt.get('isolation', [])
    if len(isolation) != 2 or not all(all(profile.get(key) is True for key in
            ('network_namespace', 'filesystem_read_isolation', 'filesystem_write_isolation')) for profile in isolation):
        raise ValueError('historical isolation evidence incomplete')
    prereg = old.check_preregistration()
    expected = c.load_file(old.PROTOCOL / 'withheld' / f'{TASK}.json')['cases']
    rows = receipt['cases']
    if len(rows) != 160 or len(expected) != 160:
        raise ValueError('expected exactly 160 historical cases')
    for case_index, (actual, wanted) in enumerate(zip(rows, expected)):
        if any(c.dumps(actual[k]) != c.dumps(wanted[k]) for k in ('case_id', 'input_wire', 'expected_wire')):
            raise ValueError('historical case differs from frozen oracle')
        obs = actual['observations']
        if len(obs) != 2:
            raise ValueError('missing/extra historical repeat')
        for o in obs:
            target = {'op': 'result', 'id': case_index + 1, 'value': wanted['expected_wire']}
            if c.dumps(o['response']) != c.dumps(target) or o['passed'] is not True:
                raise ValueError('historical response/verdict mismatch')
        if actual['passed'] is not True:
            raise ValueError('historical case verdict mismatch')
    for key, value in {'distinct_cases':160, 'repeats':2, 'passed_cases':160, 'failed_cases':0,
                       'incomplete_cases':0, 'observations':320, 'passed_observations':320}.items():
        if type(receipt.get(key)) is not int or receipt[key] != value:
            raise ValueError('historical counter mismatch: ' + key)
    if (receipt['observations_hash'] != c.digest_json(rows) or receipt['task'] != TASK
            or receipt['status'] != 'VERIFIED' or receipt['preregistration_root'] != prereg['root']
            or receipt['package_root'] != fsutil.manifest_root(fsutil.manifest_tree(package))):
        raise ValueError('historical receipt binding mismatch')
    return {'status': 'CONSISTENT', 'observations': 320,
            'scope': 'Retained record consistency, not evidence that execution occurred'}


def audit(root, package=None):
    root = root.resolve()
    result = {'format':'verislop.p03-offline-recheck/0.1', 'status':'INCOMPLETE',
              'historical_records':{}, 'independent_reexecution':{}, 'checks':[],
              'unverified_claims':['historical autonomous repairs and model provenance',
                'historical Lean candidate failures and accepted proof execution',
                'historical review completeness and final verification execution',
                'six historical TESTED guarantees and 320 historical execution observations',
                'ledger-0010 authenticity and external trust anchor',
                'Sol real invocation path', 'universal end-to-end implementation refinement']}
    if not root.is_dir():
        result['checks'].append({'name':'evidence_directory','status':'MISSING'})
        return result
    before = fsutil.manifest_tree(root)
    result['evidence_manifest'] = before
    def check(name, fn):
        try:
            value = fn()
            result['checks'].append({'name':name, 'status':'PASS'})
            return value
        except Exception as exc:
            result['checks'].append({'name':name, 'status':'UNVERIFIED', 'diagnostic':str(exc)})
            return None
    def binding():
        protocol = c.load_file(inside(root, 'protocol.json'))
        freeze = c.load_file(inside(root, 'FREEZE_BEFORE_INFERENCE.json'))
        if freeze['protocol_sha256'] != c.digest_file(root/'protocol.json'):
            raise ValueError('protocol freeze mismatch')
        for name, digest in protocol['run_inputs'].items():
            if c.digest_file(inside(root, name)) != digest:
                raise ValueError('input hash mismatch: '+name)
        sources = protocol['source_hashes']
        if not sources or c.digest_json(sources) != protocol['source_root']:
            raise ValueError('source root mismatch')
        archive = protocol['source_archive']
        path = inside(root, archive['path'])
        if c.digest_file(path) != archive['sha256']:
            raise ValueError('archive hash mismatch')
        found = {}
        with tarfile.open(path, 'r:gz') as tar:
            for member in tar:
                fsutil.check_relpath(member.name)
                if not member.isfile() or member.name in found:
                    raise ValueError('nonregular/duplicate archive member')
                found[member.name] = c.digest(tar.extractfile(member).read())
        if found != sources or archive['members'] != len(found):
            raise ValueError('archive inventory mismatch')
        return {'status':'CONSISTENT', 'source_root':protocol['source_root'],
                'scope':'Internal hash binding; no timestamp or authenticity attestation; external tokenizer inputs not checked'}
    result['historical_records']['source_binding'] = check('frozen_sources', binding)
    task = root/'tasks'/TASK
    recorded = check('task_result', lambda:c.load_file(inside(root, f'tasks/{TASK}/result.json')))
    if recorded:
        result['historical_records']['task_result'] = recorded
    # Explicit package selection avoids trusting archived absolute paths or guessing among repairs.
    if package is None:
        package = f'tasks/{TASK}/runs/{TASK.lower()}'
    pkg = check('package_path', lambda:inside(root, package))
    if pkg is not None and pkg.is_dir():
        def linked():
            package_obj = old.Package(pkg)
            link_record = c.load_file(pkg/'bridges/link.json')
            impl, files, entry, manifest, link = old.select_solve(package_obj, TASK, link_record['accepted_ir'])
            obj = entry['implementation_object']
            result['independent_reexecution']['unicode_boundaries'] = boundaries(impl, obj['file'], obj['qualname'])
        check('implementation_link_and_boundary_checks', linked)
        def historical_receipt():
            package_obj = old.Package(pkg)
            report_path = package_obj.path('report')
            report = c.load_file(report_path)
            result['historical_records']['native_tested_gate'] = old.native_tested_gate(report)
            if not recorded or recorded.get('report_sha256') != c.digest_file(report_path):
                raise ValueError('task result report hash mismatch')
            historical = c.load_file(inside(root, f'tasks/{TASK}/independent-check.json'))
            verdict = receipt_check(historical, pkg)
            protocol = c.load_file(root/'protocol.json')
            if historical['checker_hash'] != protocol['source_hashes']['synthetic_dataset/tools/check_data_pipeline_poc.py']:
                raise ValueError('historical checker not bound to source snapshot')
            impl, files, entry, manifest, link = old.select_solve(package_obj, TASK, historical['accepted_ir_hash'])
            if (historical['implementation_manifest'] != manifest or historical['link_hash'] != c.digest_file(link)
                    or historical['report_hash'] != c.digest_file(report_path) or historical['binding'] != entry):
                raise ValueError('receipt source/link/report mismatch')
            result['historical_records']['independent_receipt'] = verdict
        check('historical_receipt_binding', historical_receipt)
        result['independent_reexecution']['existing_oracle'] = check('existing_oracle_reexecution', lambda:old.run_check(pkg, TASK))
    else:
        result['checks'].append({'name':'historical_package','status':'MISSING'})
    result['input_bytes_unchanged'] = before == fsutil.manifest_tree(root)
    result['status'] = 'RECHECKED' if (result['input_bytes_unchanged'] and all(x['status']=='PASS' for x in result['checks'])
        and result['independent_reexecution'].get('unicode_boundaries',{}).get('status')=='PASS'
        and (result['independent_reexecution'].get('existing_oracle') or {}).get('status')=='VERIFIED') else 'INCOMPLETE'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--package', help='relative active package path within directory, if repaired')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(args.directory.resolve()):
        parser.error('--out must be outside evidence directory')
    if args.out.exists() or args.out.is_symlink():
        parser.error('--out must be new')
    try:
        result = audit(args.directory, args.package)
    except Exception as exc:
        result = {'format':'verislop.p03-offline-recheck/0.1', 'status':'INCOMPLETE',
                  'diagnostic':str(exc), 'scope':'No successful historical verification'}
    with args.out.open('xb') as stream:
        stream.write(c.dumps(result))
    return 0 if result['status']=='RECHECKED' else 2

if __name__ == '__main__':
    raise SystemExit(main())
