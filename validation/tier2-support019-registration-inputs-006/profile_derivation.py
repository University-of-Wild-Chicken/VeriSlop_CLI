"""Derive compact multi-source author profile and unchanged legacy capture profile."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
HERE=Path(__file__).absolute().parent
ADAPTER='validation/tier2-support-019-qualification-adapters-008'
INTEGRATION='validation/tier2-carrier-runtime-support-020-integration-001'

def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def ref(name):
    raw=(ROOT/name).read_bytes();return {'path':name,'sha256':sha(raw),'byte_count':len(raw)}
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out
def write(name,value):
    with (HERE/name).open('x') as stream:json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')

def main():
    reconstruction=ADAPTER+'/author_protocol_reconstruction.py'
    assert (ROOT/reconstruction).read_bytes()==(ROOT/INTEGRATION/'compact_author_protocol_reconstruction.py').read_bytes()
    helper=module('registered_independent_compact_reconstruction',reconstruction)
    tools=module('registered_source_profile_tools',INTEGRATION+'/profile_tools.py')
    descriptor_path='synthetic_dataset/tools/carrier_runtime020-registration.json'
    descriptor=json.loads((ROOT/descriptor_path).read_bytes())
    sources={role:(ROOT/value['path']).read_bytes() for role,value in descriptor['source_files'].items()}
    sources['descriptor']=(ROOT/descriptor_path).read_bytes()
    references={role:{'path':value['path'],'sha256':ref(value['path'])['sha256']} for role,value in descriptor['source_files'].items()}
    references['descriptor']={'path':descriptor_path,'sha256':ref(descriptor_path)['sha256']}
    for role in descriptor['source_files']:assert references[role]['sha256']==descriptor['source_files'][role]['sha256']
    for value in descriptor['interpreters'].values():assert ref(value['path'])['sha256']==value['sha256']
    code={'runtime_path':str(ROOT/descriptor['source_files']['runtime']['path']),'runtime_sha256':descriptor['source_files']['runtime']['sha256'],'reader_path':str(ROOT/descriptor['source_files']['reader']['path']),'reader_sha256':descriptor['source_files']['reader']['sha256'],'node_path':descriptor['interpreters']['node']['path'],'python_path':descriptor['interpreters']['python']['path'],'session_directory':str(HERE/'fixture-current-whole-gate-006/runtime020-own-sessions')}
    assert Path(code['session_directory']).is_dir()
    legacy_source=(ROOT/'synthetic_dataset/tools/bootstrap_tier2_carrier_view.py').read_bytes()
    legacy=json.loads((ROOT/'validation/tier2-support019-registration-inputs-005/fresh-author-carrier-literals-005.json').read_bytes())
    marker_prefix='UNRELATED_019_006_'
    profile=tools.build_profile(helper,legacy_source,legacy,references,sources,code,{'path':reconstruction,'sha256':ref(reconstruction)['sha256']},marker_pattern=r'UNRELATED_019_006_[A-Z_]+',expected_markers=[marker_prefix+suffix for suffix in ('START','MIDDLE_A','MIDDLE_B','FINAL_TAIL')])
    reference=json.loads((HERE/'fixture-current-whole-gate-006/reference.json').read_bytes())
    actual_message=(HERE/'fixture-current-whole-gate-006/fresh-author-exact-message.txt').read_bytes()
    rebuilt=helper.author_message(profile,reference,sources)
    assert rebuilt==actual_message
    write('fresh-author-carrier-literals-006.json',profile)
    capture=json.loads((ROOT/'validation/tier2-support019-registration-inputs-005/fresh-author-capture-literals-005.json').read_bytes())
    capture_source=(ROOT/capture['source']['path']).read_bytes();assert sha(capture_source)==capture['source']['sha256']
    tree=ast.parse(capture_source)
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in capture['constants']}
    assert json.loads(json.dumps(constants))==capture['constants']
    hashes={n.name:sha(ast.dump(n,include_attributes=False).encode()) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in capture['function_ast_hashes']}
    assert hashes==capture['function_ast_hashes']
    write('fresh-author-capture-literals-006.json',capture)
    inventory=json.loads((ROOT/'validation/tier2-support-019-qualification-plan-010/source-inventory-registration.json').read_bytes())
    inventory=tools.inventory_registration(inventory,descriptor,descriptor_path,'synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py')
    with (ROOT/'validation/tier2-support-019-qualification-plan-011/source-inventory-registration.json').open('w') as stream:json.dump(inventory,stream,sort_keys=True,indent=2);stream.write('\n')
    evidence={'format':'verislop.support020-current-compact-source-profile-derivation/1','status':'SOURCE_DERIVED_RUNTIME_UNQUALIFIED','source_refs':references,'reconstructor':ref(reconstruction),'carrier_profile':ref(str((HERE/'fresh-author-carrier-literals-006.json').relative_to(ROOT))),'capture_profile':ref(str((HERE/'fresh-author-capture-literals-006.json').relative_to(ROOT))),'independent_full_message_byte_equal':True,'message_bytes':len(rebuilt),'capture_constants':len(constants),'capture_ASTs':len(hashes),'runtime_interpreter':'/usr/bin/python3.12','VIEW_model_reader_runtime_qualification_calls':0,'legacy_truth_conditions_unchanged':True}
    write('compact-profile-source-derivation.json',evidence)
    print(json.dumps(evidence,sort_keys=True))

if __name__=='__main__':main()
