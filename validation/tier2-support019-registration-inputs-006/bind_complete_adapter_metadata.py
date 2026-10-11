"""Append source completeness metadata without changing sealed plan or ready."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-006'
BASE='validation/tier2-support019-final-configuration-006'
ADAPTER='validation/tier2-support-019-qualification-adapters-008'
def ref(name):
    b=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def load(name):return json.loads((ROOT/name).read_bytes())
def write(name,x):
    with (ROOT/name).open('x') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n')
def main():
    spec=load(REG+'/ADAPTER_COMPLETE_BINDING_BEFORE_METADATA.json')
    for identity in spec['preimages'].values():assert ref(identity['path'])==identity
    manifest=spec['new_manifest'];seal=spec['new_seal'];assert ref(manifest['path'])==manifest and ref(seal['path'])==seal
    assert (ROOT/seal['path']).read_text().split()==[manifest['sha256'][7:],'complete-hash-manifest.json']
    package=load(manifest['path']);files={}
    for field in ('files','inputs'):
        for name,value in package[field].items():
            actual=ref(name);expected=value if type(value) is str else value['sha256'];assert actual['sha256']==expected
            if type(value) is dict and 'byte_count' in value:assert actual['byte_count']==value['byte_count']
            files[name]=actual
    files.update({manifest['path']:manifest,seal['path']:seal,REG+'/ADAPTER_COMPLETE_BINDING_BEFORE_METADATA.json':ref(REG+'/ADAPTER_COMPLETE_BINDING_BEFORE_METADATA.json')})
    completion={'format':'verislop.support020-current-source-ready-completion/1','status':'SOURCE_METADATA_COMPLETE_RUNTIME_UNQUALIFIED','original_ready':spec['preimages']['ready'],'original_config_preimage':spec['preimages']['config'],'authoritative_adapter_package':{'manifest':manifest,'seal':seal,'entry_maps':['files','inputs']},'source_dependencies':files,'qualification_authority':False,'legacy_executable_predicates_changed':False}
    path=REG+'/current-source-ready-completion-002.json';write(path,completion)
    for name in ('final-config.json','static-input-bindings.json'):
        original=(ROOT/BASE/name).read_bytes();preimage=ROOT/REG/'source-preimages'/('builder-output-before-complete-'+name+'.raw');preimage.write_bytes(original)
    config=load(BASE+'/final-config.json');extra=set(files)|{path,REG+'/bind_complete_adapter_metadata.py'}
    config['current_source_ready_completion']=ref(path)
    config['authoritative_adapter_source_package']=completion['authoritative_adapter_package']
    config['verification_input_paths']=sorted(set(config['verification_input_paths'])|extra)
    config['adapters']['required_adapter_inputs']=sorted(set(config['adapters']['required_adapter_inputs'])|extra)
    (ROOT/BASE/'final-config.json').write_text(json.dumps(config,sort_keys=True,indent=2)+'\n')
    bindings=load(BASE+'/static-input-bindings.json');bindings['current_source_ready_completion']=ref(path)
    bindings['files'].update(files);bindings['files'][path]=ref(path);bindings['files'][BASE+'/final-config.json']=ref(BASE+'/final-config.json')
    (ROOT/BASE/'static-input-bindings.json').write_text(json.dumps(bindings,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'completion':ref(path),'configuration':ref(BASE+'/final-config.json'),'package_files':len(package['files']),'package_inputs':len(package['inputs']),'qualification_authority':False}))
if __name__=='__main__':main()
