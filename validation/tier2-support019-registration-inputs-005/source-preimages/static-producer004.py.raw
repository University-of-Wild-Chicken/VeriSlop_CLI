"""Prepare fresh static sources only; no qualification, model or task execution."""
from pathlib import Path
import argparse
import ast
import hashlib
import json

ROOT = Path(__file__).absolute().parents[2]
REG = 'validation/tier2-support019-registration-inputs-004'
BASE = 'validation/tier2-support019-final-configuration-004'
CANDIDATE = 'validation/tier2-support019-author-diagnostic-implementation-005'
REVIEW = 'validation/tier2-carrier005-source-review-001'
OLD_REG = 'validation/tier2-support019-registration-inputs-003'
OLD_BASE = 'validation/tier2-support019-final-configuration-003'
REPLACEMENTS = {
    OLD_REG: REG,
    OLD_BASE: BASE,
    'validation/tier2-support-019-qualification-plan-008': 'validation/tier2-support-019-qualification-plan-009',
    'validation/tier2-support-019-qualification-adapters-006': 'validation/tier2-support-019-qualification-adapters-007',
    'validation/tier2-support-019-qualification-003': 'validation/tier2-support-019-qualification-004',
    'support019-final-current-root-003': 'support019-final-current-root-004',
    'validation/tier2-carrier-context-support-019-implementation-004': CANDIDATE,
    'validation/tier2-carrier004-integration-source-review-001': REVIEW,
    'validation/tier2-support019-final-helpers-source-review-007': REVIEW,
    'fixture-current-whole-gate-003': 'fixture-current-whole-gate-004',
    'validation/tier2-support019-core-drivers-003': 'validation/tier2-support019-core-drivers-004',
}


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def raw(path):
    file = ROOT / path
    assert file.is_file() and not file.is_symlink() and file.resolve() == file.absolute(), path
    return file.read_bytes()


def write(path, data):
    file = ROOT / path
    assert file.is_relative_to(ROOT / REG) or file.is_relative_to(ROOT / BASE), path
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('xb') as out:
        out.write(data)


def transformed(text):
    for before, after in REPLACEMENTS.items():
        text = text.replace(before, after)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-candidate-sha256', required=True)
    args = parser.parse_args()
    candidate_hash = sha(raw(CANDIDATE + '/bootstrap_tier2_carrier_view.py'))
    assert candidate_hash == args.reviewed_candidate_sha256
    assert not (ROOT / 'validation/tier2-support-019-qualification-004').exists()
    old_hash = 'sha256:774081ab079b0bb9086479782d065c9e4b91c372ecce765c248b533c1c2b666a'
    created = []
    preimages = []
    for before, after in (
        (OLD_BASE + '/prepare_configuration.py', BASE + '/prepare_configuration.py'),
        (OLD_BASE + '/required-current-bindings.json', BASE + '/required-current-bindings.json'),
        (OLD_REG + '/assemble_current_source_handoff.py', REG + '/assemble_current_source_handoff.py'),
        (OLD_REG + '/prepare_unrelated_fixture.py', REG + '/prepare_unrelated_fixture.py'),
        (OLD_REG + '/run_registered_process.py', REG + '/run_registered_process.py'),
        (OLD_REG + '/preflight-004/specification.json', REG + '/preflight-004/specification.json'),
        (OLD_BASE + '/specification-before-configuration.json', BASE + '/specification-before-configuration.json'),
        (OLD_BASE + '/interface-amendment-before-bindings.json', BASE + '/interface-amendment-before-bindings.json'),
        (OLD_BASE + '/source-preservation-input-amendment-before-bindings.json', BASE + '/source-preservation-input-amendment-before-bindings.json'),
    ):
        original = raw(before)
        text = transformed(original.decode('utf-8'))
        if before.endswith('prepare_configuration.py'):
            text = text.replace(old_hash, candidate_hash)
            text = text.replace("adaptation['adapter_revision']=='006'", "adaptation['adapter_revision']=='007'")
            text = text.replace("'qualification-019-003'", "'qualification-019-004'")
            profile_expression = "ADAPTERS+'/predicate-reader-carrier-literals.json'"
            assert text.count(profile_expression) == 4
            text = text.replace(profile_expression, "REG+'/fresh-author-carrier-literals-004.json'")
            text = text.replace("'validation/tier2-support-019-qualification-002/'))",
                                "'validation/tier2-support-019-qualification-002/',"
                                "'validation/tier2-support-019-qualification-003/'))")
        elif before.endswith('assemble_current_source_handoff.py'):
            text = text.replace(old_hash, candidate_hash)
            text = text.replace('adaptation["adapter_revision"] == "006"', 'adaptation["adapter_revision"] == "007"')
            text = text.replace('"validation/tier2-support-019-qualification-002/")),',
                                '"validation/tier2-support-019-qualification-002/",\n'
                                '                                "validation/tier2-support-019-qualification-003/")),')
            # The combined new review authenticates stable current source inputs.
            text = text.replace('(\"' + REVIEW + '\", \"manifest.json\", [\"files\"]),',
                                '(\"' + REVIEW + '\", \"manifest.json\", [\"files\", \"inputs\"]),', 1)
            duplicate = '        ("' + REVIEW + '", "manifest.json", ["files", "inputs"]),\n'
            assert text.count(duplicate) == 2
            text = text.replace(duplicate, '', 1)
            text = text.replace('reviews = [review, "' + REVIEW + '/REVIEW.json",',
                                'reviews = [review,')
            review_pair = ("PLAN + \"/FINAL_BINDINGS_PHASE_ONE_SOURCE_FIDELITY.json\",\n"
                           "               PLAN + \"/FINAL_BINDINGS_PHASE_TWO_SOURCE_FIDELITY.json\"")
            assert text.count(review_pair) == 1
            text = text.replace(review_pair, "PLAN + \"/FINAL_CURRENT005_BINDINGS_SOURCE_FIDELITY.json\"")
        elif before.endswith('prepare_unrelated_fixture.py'):
            text = text.replace('UNRELATED_019_003_', 'UNRELATED_019_004_')
            text = text.replace('unrelated-carrier-context019-003-', 'unrelated-carrier-context019-004-')
            text = text.replace('"004"', '"005"')
            anchor = 'This fixture grants no semantic, proof, review or lifecycle authority.'
            addition = (' If a concrete observed protocol failure prevents completion, this SYSTEM explicitly permits '
                        'the five-key diagnostic failure branch specified in the outer author instructions: preserve '
                        'the four partial-result fields and add failure with UNATTESTED trust, exact observed error '
                        'and concrete own reproduction inputs or explicit unavailability. First criticize the '
                        'observed failure and attempt only recovery already allowed by the fixed protocol. A failed '
                        'diagnostic is never a successful response; never invent roots, EOF, markers or an error.')
            assert text.count(anchor) == 1
            text = text.replace(anchor, anchor + addition)
        output = text.encode('utf-8')
        if after.endswith('.py'):
            ast.parse(text)
        else:
            json.loads(text)
        preimage = REG + '/source-preimages/' + Path(before).name + '.raw'
        assert preimage not in preimages
        write(preimage, original)
        preimages.append(preimage)
        write(after, output)
        created.append({'path': after, 'sha256': sha(output), 'byte_count': len(output),
                        'preimage': {'path': before, 'sha256': sha(original), 'byte_count': len(original)},
                        'retained_preimage': preimage})
    metadata = {'format': 'verislop.support019-static-source-preparation/1',
                'status': 'SOURCE_PREPARED_UNSEALED_RUNTIME_UNQUALIFIED',
                'candidate_sha256': candidate_hash, 'sources': created,
                'declared_path_replacements': REPLACEMENTS,
                'scope': 'Source/path/identity preparation only; no artifacts or runtime evidence inherited',
                'qualification_authority': False, 'task_TESTED_authority': False,
                'model_calls': 0, 'Lean_calls': 0, 'qualification_root_created': False}
    write(REG + '/source-preparation-metadata.json',
          (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode())
    print(json.dumps({'status': metadata['status'], 'prepared_sources': len(created),
                      'candidate_sha256': candidate_hash, 'qualification_authority': False}))


if __name__ == '__main__':
    main()
