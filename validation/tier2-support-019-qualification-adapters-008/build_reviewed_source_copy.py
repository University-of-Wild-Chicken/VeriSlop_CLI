"""Only copy/authenticate already-reviewed source, update declared active metadata."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / 'validation/tier2-support-019-qualification-adapters-007'
INT = ROOT / 'validation/tier2-carrier-runtime-support-020-integration-001'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    raw = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(raw), 'byte_count': len(raw)}


def dump(node):
    return ast.dump(node, include_attributes=False)


def functions(raw):
    result = {}
    for node in ast.parse(raw).body:
        if isinstance(node, ast.FunctionDef):
            result[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for part in node.body:
                if isinstance(part, ast.FunctionDef):
                    result[node.name + '.' + part.name] = part
    return result


def main():
    spec = json.loads((HERE / 'SOURCE_COPY_SPECIFICATION_BEFORE_IMPLEMENTATION.json').read_bytes())
    baseline = json.loads((OLD / 'hash-manifest.json').read_bytes())
    need((OLD / 'SEAL.sha256').read_text() == sha((OLD / 'hash-manifest.json').read_bytes()).removeprefix('sha256:') + '  hash-manifest.json\n', 'BASELINE_MANIFEST_SEAL')
    copied, replacements, unchanged_python = [], [], []
    for name, ref in baseline['files'].items():
        source = ROOT / name
        raw = source.read_bytes()
        need(sha(raw) == ref['sha256'] and len(raw) == ref['byte_count'], 'BASELINE_SOURCE_HASH:' + name)
        relative = source.relative_to(OLD)
        target = HERE / relative
        need(not target.exists(), 'COPY_DESTINATION_EXISTS:' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        copied.append(identity(source))
        if len(relative.parts) == 1 and relative.suffix == '.py' and relative.name not in spec['source_replacements']:
            unchanged_python.append(relative.name)
    for name in ('hash-manifest.json', 'SEAL.sha256'):
        (HERE / ('baseline007-' + name)).write_bytes((OLD / name).read_bytes())
    for name, reviewed in spec['source_replacements'].items():
        target = HERE / name
        old = target.read_bytes()
        preimage = HERE / 'immutable007-preimages' / (name + '.raw')
        preimage.parent.mkdir(exist_ok=True)
        preimage.write_bytes(old)
        source = INT / reviewed
        target.write_bytes(source.read_bytes())
        replacements.append({'destination': identity(target), 'reviewed_source': identity(source), 'immutable_baseline': identity(preimage)})
    template_path = HERE / 'runtime-configuration-template.json'
    old_template = template_path.read_bytes()
    preimage = HERE / 'immutable007-preimages/runtime-configuration-template.json.raw'
    preimage.write_bytes(old_template)
    template = json.loads(old_template)
    for dotted, value in spec['metadata_changes']['runtime-configuration-template.json'].items():
        prefix, key = dotted.split('.')
        template[prefix][key] = value
    template_path.write_text(json.dumps(template, indent=2, sort_keys=True) + '\n')
    expected = json.loads(old_template)
    for dotted, value in spec['metadata_changes']['runtime-configuration-template.json'].items():
        prefix, key = dotted.split('.')
        expected[prefix][key] = value
    need(json.loads(template_path.read_bytes()) == expected, 'ACTIVE_TEMPLATE_METADATA_DELTA')
    need(len(unchanged_python) == 8, 'ACTUAL_UNCHANGED_PYTHON_COUNT')
    for name in unchanged_python:
        need((HERE / name).read_bytes() == (OLD / name).read_bytes(), 'UNCHANGED_PYTHON:' + name)
    projections = {}
    for name, changed, added in (('predicate_reader.py', {'Reader.recipe_literals', 'Reader.author_message'}, {'Reader.author_protocol_sources'}), ('additional_predicates.py', {'AdditionalPredicates.fresh_author'}, set())):
        old_tree = ast.parse((OLD / name).read_bytes())
        new_tree = ast.parse((HERE / name).read_bytes())
        before, after = functions((OLD / name).read_bytes()), functions((HERE / name).read_bytes())
        need(set(after) == set(before) | added, 'FUNCTION_SET:' + name)
        need({key for key in before if dump(before[key]) != dump(after[key])} == changed, 'FUNCTION_DELTAS:' + name)
        projected = copy.deepcopy(new_tree)
        for cls in projected.body:
            if isinstance(cls, ast.ClassDef):
                cls.body = [copy.deepcopy(before[cls.name + '.' + part.name]) if isinstance(part, ast.FunctionDef) and cls.name + '.' + part.name in changed else part for part in cls.body if not (isinstance(part, ast.FunctionDef) and cls.name + '.' + part.name in added)]
        need(dump(old_tree) == dump(projected), 'WHOLE_MODULE_PROJECTION:' + name)
        projections[name] = {'changed': sorted(changed), 'added': sorted(added), 'unchanged': len(before) - len(changed)}
        if name == 'additional_predicates.py':
            def tail(function):
                start = next(index for index, part in enumerate(function.body) if isinstance(part, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'request' for t in part.targets))
                return [dump(part) for part in function.body[start:]]
            need(tail(before['AdditionalPredicates.fresh_author']) == tail(after['AdditionalPredicates.fresh_author']), 'COMPLETION_TAIL')
    prefix = (OLD / 'author_protocol_reconstruction.py').read_bytes()
    need((HERE / 'author_protocol_reconstruction.py').read_bytes().startswith(prefix + b'\n\n'), 'INDEPENDENT_LEGACY_PREFIX')
    active = set(spec['source_replacements']) | {'runtime-configuration-template.json'}
    unchanged = []
    for source in copied:
        old_path = ROOT / source['path']
        relative = old_path.relative_to(OLD)
        if relative.as_posix() not in active:
            need((HERE / relative).read_bytes() == old_path.read_bytes(), 'OTHER_BASELINE_BYTES:' + str(relative))
            unchanged.append(relative.as_posix())
    status = {'format': 'verislop.support020-adapters008-current-source-status/1', 'source_revision': 'adapters008', 'status': 'SOURCE_ONLY_RUNTIME_UNQUALIFIED', 'qualification_authority': False, 'activation_authority': False, 'execution_authority': False, 'source_root': None, 'input_root': None, 'all27_current_results': None, 'historical_outcomes_reused_as_current_PASS': False, 'active_external_profiles': {key: template['adapters'][key] for key in ('predicate_reader_carrier_literals', 'predicate_reader_capture_literals')}, 'current_reconstruction_source': identity(HERE / 'author_protocol_reconstruction.py'), 'historical_classification': 'Every copied007 source-control/review/PASS record, source profile, candidate binding and schema preimage is historical source definition/evidence only. The exact declared current template and replaced reviewed sources are current; fresh Q006 evidence does not exist here.'}
    (HERE / 'CURRENT_SOURCE_STATUS_008.json').write_text(json.dumps(status, indent=2) + '\n')
    fidelity = {'format': 'verislop.support020-adapters008-source-copy-fidelity/1', 'status': 'REVIEWED_SOURCE_COPY_AND_DECLARED_METADATA_FIDELITY_COMPLETE_RUNTIME_UNQUALIFIED', 'copy_pid': os.getpid(), 'baseline_manifest': identity(OLD / 'hash-manifest.json'), 'baseline_seal': identity(OLD / 'SEAL.sha256'), 'sealed_baseline_files': len(copied), 'byte_exact_remaining_files': unchanged, 'byte_exact_remaining_file_count': len(unchanged), 'actual_unchanged_top_level_Python_files': unchanged_python, 'actual_unchanged_Python_count': len(unchanged_python), 'replacement_sources': replacements, 'function_projections': projections, 'Additional_completion_tail_exact': True, 'Reader_fresh_author_AST_exact': True, 'independent_legacy_helper_prefix_exact': True, 'all27_claim_objects_and_contracts_byte_exact': True, 'declared_metadata_delta': spec['metadata_changes'], 'qualification_authority': False, 'activation_authority': False, 'model_VIEW_runtime_current27_Lean_native_task_calls': 0}
    (HERE / 'SOURCE_FIDELITY_008.json').write_text(json.dumps(fidelity, indent=2) + '\n')
    print(json.dumps({'pid': os.getpid(), 'baseline_files': len(copied), 'unchanged_files': len(unchanged), 'unchanged_Python_files': len(unchanged_python), 'reconstruction': identity(HERE / 'author_protocol_reconstruction.py'), 'qualification_authority': False}), flush=True)


if __name__ == '__main__':
    main()
