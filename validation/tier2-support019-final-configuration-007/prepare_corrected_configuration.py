"""Exactly two list-member omissions; preserve all recursive config values."""
import copy
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).absolute().parent
ROOT=HERE.parents[1]
def ref(name):
    b=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def write(name,value):
    with (HERE/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def main():
    spec=json.loads((HERE/'SPECIFICATION_BEFORE_SOURCE.json').read_bytes());oldref=spec['preimage_configuration'];assert ref(oldref['path'])==oldref
    raw=(ROOT/oldref['path']).read_bytes();old=json.loads(raw);new=copy.deepcopy(old);binary={'/usr/bin/node','/usr/bin/python3.12'}
    assert not (ROOT/old['qualification_root']).exists()
    for target in (new['verification_input_paths'],new['adapters']['required_adapter_inputs']):
        assert binary<=set(target) and all(target.count(p)==1 for p in binary)
        target[:]=[p for p in target if p not in binary]
        assert not any(Path(p).is_absolute() for p in target)
    comparison=copy.deepcopy(new)
    comparison['verification_input_paths']=old['verification_input_paths']
    comparison['adapters']['required_adapter_inputs']=old['adapters']['required_adapter_inputs']
    assert comparison==old and new['external_runtime_files']==old['external_runtime_files']
    for p in binary:assert ref(p)['sha256']==new['external_runtime_files'][p]
    (HERE/'BASE006-final-config.preimage.raw').write_bytes(raw)
    write('final-config.json',new)
    identity=ref(spec['new_configuration'])
    fidelity={'format':'verislop.support020-repository-path-only-config-fidelity/1','scope':'SOURCE_ONLY_RUNTIME_UNQUALIFIED','specification':ref(str((HERE/'SPECIFICATION_BEFORE_SOURCE.json').relative_to(ROOT))),'preimage':ref(str((HERE/'BASE006-final-config.preimage.raw').relative_to(ROOT))),'corrected_configuration':identity,'removed_from_verification_input_paths':sorted(binary),'removed_from_adapters_required_adapter_inputs':sorted(binary),'all_other_recursive_fields_values_unchanged':True,'external_runtime_files_byte_value_exact':True,'binary_bindings':{p:ref(p) for p in sorted(binary)},'model_VIEW_runtime_Lean_compilation_kernel_task_calls':0,'qualification_created':False}
    write('CONFIGURATION_REPAIR_SOURCE_FIDELITY.json',fidelity)
    print(json.dumps({'configuration':identity,'fidelity':ref(str((HERE/'CONFIGURATION_REPAIR_SOURCE_FIDELITY.json').relative_to(ROOT))),'all_other_recursive_fields_unchanged':True,'qualification_created':False}))
if __name__=='__main__':main()
