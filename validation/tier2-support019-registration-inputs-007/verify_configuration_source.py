"""Finite current source/configuration inspection; grants no runtime admission."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).absolute().parents[2]
REG = 'validation/tier2-support019-registration-inputs-007'
BASE = 'validation/tier2-support019-final-configuration-008'
PLAN = 'validation/tier2-support-019-qualification-plan-012'
Q = 'validation/tier2-support-019-qualification-007'


def raw(name):
    path = ROOT / name
    assert path.is_file() and not path.is_symlink() and path.resolve() == path.absolute(), name
    return path.read_bytes()


def ref(name):
    data = raw(name)
    return {'path': name, 'sha256': 'sha256:' + hashlib.sha256(data).hexdigest(), 'byte_count': len(data)}


def load(name):
    return json.loads(raw(name))


def main():
    assert not (ROOT / Q).exists()
    spec = load(REG + '/final-installation-review-specification-before-record.json')
    config = load(BASE + '/final-config.json')
    preflight = load(REG + '/preflight-007/stdout.log')
    ready = load(BASE + '/generation-inputs-ready.json')
    interface = load(REG + '/configuration-interface-inspection.json')
    builder_receipt = load('validation/tier2-support019-source-binding-processes-007/configuration-builder/actual-process-receipt.json')
    interface_receipt = load('validation/tier2-support019-source-binding-processes-007/configuration-interface/actual-process-receipt.json')
    for receipt in (builder_receipt, interface_receipt):
        assert type(receipt['returncode']) is int and receipt['returncode'] == 0
        assert type(receipt['pid']) is int and receipt['pid'] > 0
        assert receipt['before'] == receipt['after'] and receipt['before']
        assert receipt['timeout_seconds'] is None and receipt['timed_out'] is False
        for identity in receipt['after'].values():
            assert ref(identity['path']) == identity
        assert ref(receipt['stdout']['path']) == receipt['stdout']
        assert ref(receipt['stderr']['path']) == receipt['stderr']
    for name, identity in ready['source_dependencies'].items():
        assert ref(name) == identity
    for name in ('source_files', 'test_sources'):
        for path, expected in preflight[name].items():
            assert ref(path)['sha256'] == expected
    assert config['qualification_root'] == Q and config['closure_id'] == 'support019-final-current-root-007'
    assert config['source_root'] == preflight['source_root']
    assert config['registered_test_ids'] == preflight['test_ids']
    assert config['test_modules'] == preflight['test_modules']
    assert len(preflight['test_ids']) == 208 and len(preflight['test_modules']) == 18
    assert preflight['tests_executed'] == preflight['model_calls'] == 0 and preflight['task_inputs'] is False
    assert config['core_model_calls'] == 0 and config['ancillary_fresh_author_calls'] == 1
    assert config['fresh_author']['requested_model'] == 'gpt-6.1-sol' and config['fresh_author']['fork_turns'] == 'none'
    assert all(config[name] is None for name in ('inference_timeout', 'retrieval_timeout', 'review_timeout'))
    assert config['strict_implementation_proof_release_unchanged'] is True
    assert all(not Path(name).is_absolute() for name in config['verification_input_paths']+config['adapters']['required_adapter_inputs'])
    descriptor=load('synthetic_dataset/tools/carrier_runtime020-registration.json')
    for identity in descriptor['interpreters'].values():assert config['external_runtime_files'][identity['path']]==identity['sha256']
    assert config['diagnostic_failure_parser']==ref('validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py')
    assert interface['status'] == 'READY' and interface['missing_literal_paths'] == []
    assert interface['configuration']['sha256'] == ref(BASE + '/final-config.json')['sha256']
    assert interface['verifiers_executed'] == interface['model_calls'] == 0 and interface['task_inputs'] is False
    for identity in interface['sources']:
        path = Path(identity['path']).relative_to(ROOT).as_posix()
        assert ref(path)['sha256'] == identity['sha256'] and ref(path)['byte_count'] == identity['byte_count']
    claims = load(PLAN + '/claims.json')
    assert raw(PLAN + '/claims.json') == raw(PLAN + '/preimages/tier2-support-019-qualification-plan-008/claims.json')
    assert len(claims['original_claims']) == 18 and len(claims['additional_claims']) == 9
    assert len(config['independent_claim_checks']) == 27
    assert len(config['execution_phases']) == len(config['additional_processes']) == 4
    assert len(config['capture003_checkpoint_control_ids']) == 17
    assert config['capture003_checkpoint_control_ids'] == ready['checkpoint_control_ids']
    assert len(config['capture002_weird_path_control_ids']) == 5
    assert len(config['adapters']['equality_case_contracts']) == 55
    assert ref('synthetic_dataset/tools/bootstrap_tier2_carrier_view.py')['sha256'] == spec['candidate_carrier']
    assert raw('synthetic_dataset/tools/bootstrap_tier2_carrier_view.py') == raw('validation/tier2-support019-author-recovery-implementation-006/bootstrap_tier2_carrier_view.py')
    for copy in config['pre_freeze_copies']:
        assert ref(copy['source'])['sha256'] == copy['sha256']
    prior = load('validation/tier2-support019-registration-inputs-003/final-installation-review.json')
    audit = prior['oldstage018_scope_audit']
    assert ref(audit['path']) == audit and load(audit['path'])['status'] == 'BLOCKED'
    result = {
        'format': 'verislop.support019-root-final-installation-review/1', 'status': 'ROOT_REVIEWED_INSTALLED',
        'specification': ref(REG + '/final-installation-review-specification-before-record.json'),
        'qualification_root': Q, 'closure_id': config['closure_id'], 'source_root': preflight['source_root'], 'input_root': None,
        'configuration': ref(BASE + '/final-config.json'), 'candidate_hashes': {
            'carrier': spec['candidate_carrier'], 'equality': ref('verislop/contract_refutation.py')['sha256']},
        'final_capture': ref(REG + '/capture003-registration.json'),
        'final_capture_sha256': ref(REG + '/capture003-registration.json')['sha256'],
        'capture_amendment_reviewed_frozen': True,
        'capture002_weird_path_control_ids': config['capture002_weird_path_control_ids'],
        'capture003_checkpoint_control_ids': config['capture003_checkpoint_control_ids'],
        'required_new_test_ids': config['newly_registered_test_ids'],
        'oldstage018_scope_audit': audit, 'oldstage018_scope_audit_resolved': True,
        'oldstage018_scope_audit_status': 'BLOCKED',
        'oldstage018_scope_audit_resolution': prior['oldstage018_scope_audit_resolution'],
        'complete_tests': len(preflight['test_ids']), 'complete_modules': len(preflight['test_modules']),
        'source_file_count': len(preflight['source_files']), 'test_source_file_count': len(preflight['test_sources']),
        'original_claims': 18, 'additional_claims': 9, 'equality_controls': 55, 'legacy_pure_controls': 30,
        'all_original_claim_floors_preserved': True, 'registered_compiler_and_ground_limits_unchanged': True,
        'static_interface_paths_checked': sum(row['literal_paths_inspected'] for row in interface['sources']),
        'interface_inspection': ref(REG + '/configuration-interface-inspection.json'),
        'builder_actual_receipt_snapshot': builder_receipt, 'interface_actual_receipt_snapshot': interface_receipt,
        'source_reviews': ready['independent_source_reviews'],
        'root_review_scope': 'Static current installed source and registered configuration/preparation only',
        'all27_runtime_claims': 'UNRESOLVED_REQUIRES_FRESH_CHECKS_AND_INDEPENDENT_ADMISSION',
        'qualification_authority': False, 'activation_authority': False, 'task_TESTED_authority': False,
    }
    with (ROOT / REG / 'final-installation-review.json').open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'review': ref(REG + '/final-installation-review.json'), 'qualification_authority': False}))


if __name__ == '__main__':
    main()
