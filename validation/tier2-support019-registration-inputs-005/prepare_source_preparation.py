"""Prepare fresh static sources only; no qualification, model or task execution."""
from pathlib import Path
import argparse
import ast
import hashlib
import json

ROOT = Path(__file__).absolute().parents[2]
REG = 'validation/tier2-support019-registration-inputs-005'
BASE = 'validation/tier2-support019-final-configuration-005'
CANDIDATE = 'validation/tier2-support019-author-recovery-implementation-006'
REVIEW = 'validation/tier2-carrier006-source-review-001'
OLD_REG = 'validation/tier2-support019-registration-inputs-004'
OLD_BASE = 'validation/tier2-support019-final-configuration-004'
REPLACEMENTS = {'fixture-current-whole-gate-004': 'fixture-current-whole-gate-005', 'support019-final-current-root-004': 'support019-final-current-root-005', 'validation/tier2-carrier005-source-review-001': 'validation/tier2-carrier006-source-review-001', 'validation/tier2-support-019-qualification-004': 'validation/tier2-support-019-qualification-005', 'validation/tier2-support-019-qualification-plan-009': 'validation/tier2-support-019-qualification-plan-010', 'validation/tier2-support019-author-diagnostic-implementation-005': 'validation/tier2-support019-author-recovery-implementation-006', 'validation/tier2-support019-core-drivers-004': 'validation/tier2-support019-core-drivers-005', 'validation/tier2-support019-final-configuration-004': 'validation/tier2-support019-final-configuration-005', 'validation/tier2-support019-registration-inputs-004': 'validation/tier2-support019-registration-inputs-005'}

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
    assert sha(raw('synthetic_dataset/tools/bootstrap_tier2_carrier_view.py')) == candidate_hash
    assert not (ROOT / 'validation/tier2-support-019-qualification-005').exists()
    old_hash = 'sha256:a56590eb051ebac28312031b157195caab0d747aa20ebc4557d70ff5b1b2921f'
    created = []
    for before, after in (
        (OLD_BASE + '/prepare_configuration.py', BASE + '/prepare_configuration.py'),
        (OLD_BASE + '/required-current-bindings.json', BASE + '/required-current-bindings.json'),
        (OLD_REG + '/assemble_current_source_handoff.py', REG + '/assemble_current_source_handoff.py'),
        (OLD_REG + '/prepare_unrelated_fixture.py', REG + '/prepare_unrelated_fixture.py'),
        (OLD_REG + '/run_registered_process.py', REG + '/run_registered_process.py'),
        (OLD_REG + '/run_nonexecuting_preflight_004.py', REG + '/run_nonexecuting_preflight_005.py'),
        (OLD_REG + '/preflight-004/specification.json', REG + '/preflight-005/specification.json'),
        (OLD_BASE + '/specification-before-configuration.json', BASE + '/specification-before-configuration.json'),
        (OLD_BASE + '/interface-amendment-before-bindings.json', BASE + '/interface-amendment-before-bindings.json'),
        (OLD_BASE + '/source-preservation-input-amendment-before-bindings.json', BASE + '/source-preservation-input-amendment-before-bindings.json'),
    ):
        original = raw(before)
        text = transformed(original.decode('utf-8'))
        text = text.replace('preflight-004', 'preflight-005').replace('configuration004', 'configuration005')
        text = text.replace('registration-inputs004', 'registration-inputs005').replace('plan009', 'plan010')
        text = text.replace('pure004', 'pure005').replace('carrier005', 'carrier006').replace('candidate005', 'candidate006')
        text = text.replace('qualification004', 'qualification005').replace('Q004', 'Q005')
        text = text.replace('FINAL_CURRENT005_BINDINGS_SOURCE_FIDELITY.json', 'FINAL_CURRENT006_BINDINGS_SOURCE_FIDELITY.json')
        text = text.replace('fresh-author-carrier-literals-004.json','fresh-author-carrier-literals-005.json')
        text = text.replace(old_hash,candidate_hash)
        if before.endswith('prepare_configuration.py'):
            text = text.replace("'qualification-019-004'", "'qualification-019-005'")
            text = text.replace('CURRENT004_NOT_BYTE_EXACT_INSTALLED','CURRENT006_NOT_BYTE_EXACT_INSTALLED')
            text = text.replace('PLAN008_CURRENT_CARRIER','PLAN010_CURRENT_CARRIER').replace('PLAN008_ADAPTER006','PLAN010_ADAPTER007')
            capture="ADAPTERS+'/predicate-reader-capture-literals.json'"
            assert text.count(capture)==1
            text=text.replace(capture,"REG+'/fresh-author-capture-literals-005.json'")
            anchor="ADAPTERS+'/author_protocol_reconstruction.py',REG+'/fresh-author-carrier-literals-005.json',"
            assert text.count(anchor)==1
            text=text.replace(anchor,anchor+"REG+'/fresh-author-capture-literals-005.json',")
            old_reject="'validation/tier2-support-019-qualification-003/'))"
            assert text.count(old_reject)==1
            text=text.replace(old_reject,"'validation/tier2-support-019-qualification-003/','validation/tier2-support-019-qualification-004/'))")
        elif before.endswith('assemble_current_source_handoff.py'):
            anchor='"validation/tier2-support-019-qualification-003/")),'
            assert text.count(anchor)==1
            text=text.replace(anchor,'"validation/tier2-support-019-qualification-003/",\n                                "validation/tier2-support-019-qualification-004/")),')
            text=text.replace('Carrier004 review own files','Carrier006 review own files').replace('preflight004','preflight005')
            anchor='    paths.add(carrier)\n'
            assert text.count(anchor)==1
            installation='validation/tier2-carrier006-installation-001'
            text=text.replace(anchor,anchor+'    paths.update({'+repr(installation+'/SPECIFICATION_BEFORE_INSTALLATION.json')+','+repr(installation+'/production005-preinstallation.raw')+','+repr(installation+'/ROOT_REVIEW_AUTHENTICATION.json')+','+repr(installation+'/SOURCE_INSTALLATION_OBSERVATION.json')+'})\n')
        elif before.endswith('prepare_unrelated_fixture.py'):
            text=text.replace('UNRELATED_019_004_','UNRELATED_019_005_').replace('unrelated-carrier-context019-004-','unrelated-carrier-context019-005-')
            text=text.replace('"005"','"006"')
        elif before.endswith('run_nonexecuting_preflight_004.py'):
            anchor="reg=json.loads((p/'registration-before-execution.json').read_text())\n"
            assert text.count(anchor)==1
            extra="def guard():\n return {name:{'path':name,'sha256':'sha256:'+hashlib.sha256((root/name).read_bytes()).hexdigest(),'byte_count':(root/name).stat().st_size} for name in reg['source_guards']}\nbefore=guard();assert before==reg['source_guards'] and before\n"
            text=text.replace(anchor,anchor+extra)
            text=text.replace("receipt={'format':", "after=guard();assert before==after\nreceipt={'before':before,'after':after,'frozen_inputs_unchanged':before==after,'format':",1)
        output=text.encode()
        if after.endswith('.py'):ast.parse(output)
        else:json.loads(output)
        preimage=REG+'/source-preimages/'+Path(before).name+'.raw'
        write(preimage,original);write(after,output)
        created.append({'path':after,'sha256':sha(output),'byte_count':len(output),'preimage':{'path':before,'sha256':sha(original),'byte_count':len(original)},'retained_preimage':preimage})
    metadata={'format':'verislop.support019-static-source-preparation/1','status':'SOURCE_PREPARED_UNSEALED_RUNTIME_UNQUALIFIED',
              'candidate_sha256':candidate_hash,'sources':created,'declared_path_replacements':REPLACEMENTS,
              'scope':'Source/path/identity preparation only; no artifacts or runtime evidence inherited',
              'qualification_authority':False,'task_TESTED_authority':False,'model_calls':0,'Lean_calls':0,'qualification_root_created':False}
    write(REG+'/source-preparation-metadata.json',(json.dumps(metadata,indent=2,sort_keys=True)+'\n').encode())
    print(json.dumps({'status':metadata['status'],'prepared_sources':len(created),'candidate_sha256':candidate_hash,'qualification_authority':False}))


if __name__ == '__main__':
    main()
