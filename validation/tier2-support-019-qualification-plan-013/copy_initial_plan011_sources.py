"""Registered initial byte-exact source copy, with no current metadata adaptation."""
from pathlib import Path
import ast
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'validation/tier2-support-019-qualification-plan-011'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(raw), 'byte_count': len(raw)}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    specification = json.loads((HERE / 'SPECIFICATION_BEFORE_INITIAL_COPY.json').read_bytes())
    raw_manifest = (OLD / 'hash-manifest.json').read_bytes()
    need(sha(raw_manifest) == specification['immutable_baseline']['sha256'], 'BASELINE_MANIFEST_HASH')
    need((OLD / 'SEAL.sha256').read_text() == sha(raw_manifest).removeprefix('sha256:') + '  hash-manifest.json\n', 'EXACT_BASELINE_SEAL')
    manifest = json.loads(raw_manifest)
    need(len(manifest['files']) == 241, 'BASELINE_OWN_SOURCE_COUNT')
    copied = {}
    python_ast = {}
    for name, reference in manifest['files'].items():
        path = OLD / name
        need(path.is_file() and path.resolve() == path and not path.is_symlink(), 'BASELINE_SOURCE_NOT_REGULAR:' + name)
        raw = path.read_bytes()
        need(sha(raw) == reference['sha256'] and len(raw) == reference['byte_count'], 'BASELINE_SOURCE_IDENTITY:' + name)
        target = HERE / name
        if target.exists():
            need(target.is_file() and not target.is_symlink() and target.resolve() == target and target.read_bytes() == raw, 'EXISTING_PARTIAL_COPY_NOT_EXACT:' + name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        need(target.read_bytes() == raw, 'COPY_BYTE_MISMATCH:' + name)
        copied[name] = {'baseline': identity(path), 'copy': identity(target), 'byte_exact': True}
        if path.suffix == '.py':
            original_ast = ast.dump(ast.parse(raw), include_attributes=False).encode()
            current_ast = ast.dump(ast.parse(target.read_bytes()), include_attributes=False).encode()
            need(original_ast == current_ast, 'PYTHON_AST_MISMATCH:' + name)
            python_ast[name] = {'baseline_ast_sha256': sha(original_ast), 'copy_ast_sha256': sha(current_ast), 'exact': True}
    (HERE / 'baseline011-hash-manifest.json').write_bytes(raw_manifest)
    (HERE / 'baseline011-SEAL.sha256').write_bytes((OLD / 'SEAL.sha256').read_bytes())
    need((HERE / 'baseline011-hash-manifest.json').read_bytes() == raw_manifest, 'MANIFEST_PREIMAGE_BYTES')
    need((HERE / 'baseline011-SEAL.sha256').read_bytes() == (OLD / 'SEAL.sha256').read_bytes(), 'SEAL_PREIMAGE_BYTES')
    claims = json.loads((OLD / 'claims.json').read_bytes())
    need(type(claims) is dict and type(claims['original_claims']) is list and type(claims['additional_claims']) is list and len(claims['original_claims']) == 18 and len(claims['additional_claims']) == 9 and type(claims['total_count']) is int and claims['total_count'] == 27, 'CLOSED_ACTUAL_CLAIMS_SCHEMA')
    claim_list = claims['original_claims'] + claims['additional_claims']
    need(len(claim_list) == 27, 'CLAIM_OBJECT_COUNT')
    protected = {name: copied[name] for name in ('claims.json', 'mandatory-floor.json', 'control-registration.json', 'audit-evidence-contract.json', 'producer-contracts.json', 'registration-template.json', 'independent-audit-specification.json', 'materialize_registration.py', 'audit_actual.py', 'registration_lib.py', 'test_admission_controls.py')}
    fidelity = {'format': 'verislop.support021-plan012-initial-copy-fidelity/1', 'status': 'INITIAL_SOURCE_COPY_COMPLETE_CURRENT_METADATA_UNRESOLVED_UNSEALED', 'actual_copy_pid': os.getpid(), 'specification': identity(HERE / 'SPECIFICATION_BEFORE_INITIAL_COPY.json'), 'baseline_manifest': identity(OLD / 'hash-manifest.json'), 'baseline_seal': identity(OLD / 'SEAL.sha256'), 'manifest_preimage': identity(HERE / 'baseline011-hash-manifest.json'), 'seal_preimage': identity(HERE / 'baseline011-SEAL.sha256'), 'source_files_copied': len(copied), 'all_copied_source_bytes_exact': True, 'source_identity_pairs': copied, 'Python_AST_pairs': python_ast, 'Python_AST_count': len(python_ast), 'all_Python_AST_exact': True, 'protected_source_definitions': protected, 'claim_count': len(claim_list), 'semantic_source_deltas': [], 'metadata_deltas_executed': [], 'copied_metadata_role': 'Historical plan011 source metadata only. Collector must bind actual current REG007/BASE008/profiles/preflight/templates before sealing; no old outcome is current PASS.', 'external_baseline_input_map': 'Preserved byte-exact as source metadata; no qualification or admission evaluation of these inputs.', 'collector_owns_next_bindings_and_seal': True, 'source_root': None, 'input_root': None, 'qualification_authority': False, 'activation_authority': False, 'model_VIEW_current27_qualification_task_Lean_native_calls': 0}
    (HERE / 'INITIAL_COPY_FIDELITY.json').write_text(json.dumps(fidelity, indent=2) + '\n')
    print(json.dumps({'pid': os.getpid(), 'files_copied': len(copied), 'python_ast_count': len(python_ast), 'claims': len(claim_list), 'materializer': identity(HERE / 'materialize_registration.py'), 'status': fidelity['status']}), flush=True)


if __name__ == '__main__':
    main()
