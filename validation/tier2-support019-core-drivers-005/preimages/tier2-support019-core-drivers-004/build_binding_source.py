"""Binding-only pure producer preparation; executes no controls or target."""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json

ROOT = Path(__file__).absolute().parents[2]
HERE = Path(__file__).absolute().parent
OLD = ROOT / 'validation/tier2-support019-core-drivers-003'
CANDIDATE = 'validation/tier2-support019-author-diagnostic-implementation-005/bootstrap_tier2_carrier_view.py'
OLD_CANDIDATE = 'validation/tier2-carrier-context-support-019-implementation-004/bootstrap_tier2_carrier_view.py'
SPEC = 'validation/tier2-support019-registration-inputs-004/PURE_PRODUCER_BINDING_AMENDMENT_BEFORE_SOURCE.md'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def ref(path):
    assert path.is_file() and not path.is_symlink() and path.resolve() == path.absolute()
    data = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(data), 'byte_count': len(data)}


def write(name, data):
    file = HERE / name
    assert file.parent == HERE
    with file.open('xb') as stream:
        stream.write(data)


def wire(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


class NormalizeBindings(ast.NodeTransformer):
    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'EXPECTED':
            node.value = ast.Constant(None)
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if node.value == CANDIDATE:
            return ast.copy_location(ast.Constant(OLD_CANDIDATE), node)
        return node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-sha256', required=True)
    args = parser.parse_args()
    candidate = ref(ROOT / CANDIDATE)
    assert candidate['sha256'] == args.candidate_sha256
    manifest = json.loads((OLD / 'manifest.json').read_bytes())
    seal = (OLD / 'SEAL.sha256').read_text().strip().split()
    assert seal[0].removeprefix('sha256:') == sha((OLD / 'manifest.json').read_bytes())[7:]
    for name, identity in manifest['files'].items():
        actual = ref(OLD / name)
        assert actual['sha256'] == identity['sha256'] and actual['byte_count'] == identity['byte_count'], name
    before = (OLD / 'verify_carrier_controls.py').read_bytes()
    old_hash = 'sha256:774081ab079b0bb9086479782d065c9e4b91c372ecce765c248b533c1c2b666a'
    text = before.decode()
    assert text.count(old_hash) == text.count(OLD_CANDIDATE) == 1
    after = text.replace(old_hash, candidate['sha256']).replace(OLD_CANDIDATE, CANDIDATE).encode()
    normalized = [ast.dump(NormalizeBindings().visit(copy.deepcopy(ast.parse(raw))), include_attributes=False)
                  for raw in (before, after)]
    assert normalized[0] == normalized[1]
    write('PREIMAGE_VERIFY_CARRIER_CONTROLS.py.txt', before)
    write('verify_carrier_controls.py', after)
    write('WITNESS_SCHEMA.json', (OLD / 'WITNESS_SCHEMA.json').read_bytes())
    write('SPECIFICATION_BEFORE_SOURCE.md', (ROOT / SPEC).read_bytes())
    fidelity = {'format': 'verislop.support019-pure-binding-source-fidelity/1',
                'status': 'SOURCE_BINDINGS_PREPARED_RUNTIME_UNQUALIFIED',
                'candidate': candidate, 'baseline': ref(OLD / 'verify_carrier_controls.py'),
                'changed_bindings': ['EXPECTED', 'current_source_candidate_path'],
                'complete_AST_equal_after_declared_binding_normalization': True,
                'WITNESS_SCHEMA_byte_exact': True, 'all30_control_definitions_unchanged': True,
                'normalization_source': ref(Path(__file__).absolute()),
                'qualification_authority': False, 'task_TESTED_authority': False}
    write('SOURCE_FIDELITY.json', wire(fidelity))
    files = {p.name: {k: v for k, v in ref(p).items() if k != 'path'}
             for p in sorted(HERE.iterdir()) if p.is_file()}
    inputs = {name: ref(ROOT / name) for name in (CANDIDATE, SPEC)}
    package = {'format': 'verislop.support019-pure-source-package/1', 'files': files,
               'inputs': inputs, 'runtime_authority': False}
    write('manifest.json', wire(package))
    write('SEAL.sha256', (sha((HERE / 'manifest.json').read_bytes())[7:] + '  manifest.json\n').encode())
    print(json.dumps({'status': fidelity['status'], 'source_files': len(files),
                      'producer': ref(HERE / 'verify_carrier_controls.py'),
                      'manifest': ref(HERE / 'manifest.json'), 'qualification_authority': False}, sort_keys=True))


if __name__ == '__main__':
    main()
