"""Bind actual corrected interface/recursive fidelity; preserve immutable old root."""
import copy
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).absolute().parent
ROOT=HERE.parents[1]
BASE=HERE.relative_to(ROOT).as_posix()
REG='validation/tier2-support019-registration-inputs-006'
def ref(name):
    b=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def load(name):return json.loads((ROOT/name).read_bytes())
def write(name,value):
    with (HERE/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def main():
    old=load('validation/tier2-support019-final-configuration-006/final-config.json');current=load(BASE+'/final-config.json')
    restore=copy.deepcopy(current);restore['verification_input_paths']=old['verification_input_paths'];restore['adapters']['required_adapter_inputs']=old['adapters']['required_adapter_inputs'];assert restore==old
    assert old['external_runtime_files']==current['external_runtime_files'] and not (ROOT/current['qualification_root']).exists()
    interface=load(BASE+'/configuration-interface-inspection.json');identity=ref(BASE+'/final-config.json')
    assert interface['status']=='READY' and interface['missing_literal_paths']==[] and interface['configuration']['sha256']==identity['sha256']
    process='validation/tier2-support019-source-binding-processes-006/configuration-interface-repair002/actual-process-receipt.json'
    receipt=load(process);assert type(receipt['pid']) is int and type(receipt['returncode']) is int and receipt['returncode']==0 and receipt['before']==receipt['after']
    for name,reference in receipt['after'].items():assert ref(name)==reference
    assert ref(receipt['stdout']['path'])==receipt['stdout'] and ref(receipt['stderr']['path'])==receipt['stderr']
    previous=REG+'/final-installation-review.json';review=load(previous)
    review['configuration']=identity
    review['specification']=ref(BASE+'/SPECIFICATION_BEFORE_SOURCE.json')
    review['interface_inspection']=ref(BASE+'/configuration-interface-inspection.json')
    review['interface_actual_receipt_snapshot']=receipt
    review['configuration_repair_source_fidelity']=ref(BASE+'/CONFIGURATION_REPAIR_SOURCE_FIDELITY.json')
    review['historical_source_review_preimage']=ref(previous)
    review['root_review_scope']='Root-authorized exact two-member repository-path metadata repair; all unchanged source/current27 runtime predicates retained; final root authentication precedes materialization'
    review['historical_configuration_interface_metadata']='All config fields beyond the two declared list removals remain exact, including original prospective interface registration. This actual new interface/receipt is the authoritative successor observation; old registration is retained source metadata.'
    write('final-installation-review.json',review)
    checks={'format':'verislop.support020-corrected-configuration-source-checks/1','scope':'SOURCE_ONLY_NOT_QUALIFICATION','configuration':identity,'specification':ref(BASE+'/SPECIFICATION_BEFORE_SOURCE.json'),'recursive_fidelity':ref(BASE+'/CONFIGURATION_REPAIR_SOURCE_FIDELITY.json'),'interface':ref(BASE+'/configuration-interface-inspection.json'),'actual_interface_process':ref(process),'current_installation_review':ref(BASE+'/final-installation-review.json'),'absolute_paths_absent_in_repository_lists':all(not Path(n).is_absolute() for n in current['verification_input_paths']+current['adapters']['required_adapter_inputs']),'external_binary_bindings_retained':{n:current['external_runtime_files'][n] for n in ('/usr/bin/node','/usr/bin/python3.12')},'all27_runtime_claims':'UNRESOLVED_NOT_EXECUTED','qualification_authority':False}
    write('CONFIGURATION_METADATA_CHECKS.json',checks)
    (HERE/'HANDOFF.md').write_text('Corrected Q006 source configuration only. Remove exactly the Node/Python absolute paths from two repository-relative lists. All other recursive configuration values and external binary identities unchanged. BASE006/plan011/failure preserved. Actual new interface READY/int0; Q006 absent. Materializer execution requires root authentication. All27 runtime claims UNRESOLVED_NOT_EXECUTED.\n')
    files={p.relative_to(ROOT).as_posix():ref(p.relative_to(ROOT).as_posix()) for p in HERE.rglob('*') if p.is_file() and p.name not in ('configuration-source-manifest.json','SEAL.sha256')}
    write('configuration-source-manifest.json',{'format':'verislop.support019-configuration-source-manifest/1','status':'SOURCE_STATIC_CHECKED_PENDING_ROOT_AUTH_RUNTIME_UNQUALIFIED','files':files,'qualification_authority':False,'activation_authority':False})
    (HERE/'SEAL.sha256').write_text(ref(BASE+'/configuration-source-manifest.json')['sha256'][7:]+'  configuration-source-manifest.json\n')
    print(json.dumps({'configuration':identity,'manifest':ref(BASE+'/configuration-source-manifest.json'),'seal':ref(BASE+'/SEAL.sha256'),'review':ref(BASE+'/final-installation-review.json'),'interface':ref(BASE+'/configuration-interface-inspection.json'),'all_other_recursive_config_values_unchanged':True,'qualification_created':False}))
if __name__=='__main__':main()
