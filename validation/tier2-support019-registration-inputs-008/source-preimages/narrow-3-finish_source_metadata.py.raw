"""Fresh exact Q007 metadata/template bindings and source seal; no qualification."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-007'
BASE='validation/tier2-support019-final-configuration-008'
PLAN='validation/tier2-support-019-qualification-plan-012'
OLDPLAN='validation/tier2-support-019-qualification-plan-011'
ADAPTER='validation/tier2-support-019-qualification-adapters-008'
def ref(name):
 raw=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_count':len(raw)}
def load(name):return json.loads((ROOT/name).read_bytes())
def write(name,value):
 with (ROOT/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def tr(name):
 return name.replace('registration-inputs-006','registration-inputs-007').replace('final-configuration-006','final-configuration-008').replace('fresh-author-carrier-literals-006','fresh-author-carrier-literals-007').replace('fresh-author-capture-literals-006','fresh-author-capture-literals-007').replace('fixture-system-source-fidelity.json','FIXTURE_SOURCE_FIDELITY.json')
def refresh(value):
 if type(value) is dict:
  if set(value)>={'path','sha256','byte_count'} and (ROOT/value['path']).is_file():value.update(ref(value['path']))
  for item in value.values():refresh(item)
 elif type(value) is list:
  for item in value:refresh(item)
def main():
 assert not (ROOT/'validation/tier2-support-019-qualification-007').exists()
 old=load(OLDPLAN+'/predicate-reader-adaptation-specification.json');adaptation=json.loads(json.dumps(old))
 paths={tr(row['path']) for row in old['source_templates']}
 paths.update(REG+'/'+n for n in ['SPECIFICATION_BEFORE_DERIVATION.json','SPECIFICATION_BEFORE_SOURCE.json','static-source-fidelity.json','FIXTURE_SOURCE_FIDELITY.json','compact-profile-source-derivation.json','fresh-author-carrier-literals-007.json','fresh-author-capture-literals-007.json','prepare_unrelated_fixture.py','assemble_current_source_handoff.py','DIAGNOSTIC_FIXTURE_SYSTEM_SPECIFICATION_BEFORE_SOURCE.json','final-installation-review-specification-before-record.json'])
 paths.add(BASE+'/prepare_configuration.py')
 package='validation/tier2-carrier-runtime-support-021-implementation-001'
 for name in load(package+'/hash-manifest.json')['files']:paths.add(name if name.startswith(('validation/','synthetic_dataset/','tests/','/')) else package+'/'+name)
 paths.update({package+'/hash-manifest.json',package+'/SEAL.sha256',ADAPTER+'/complete-hash-manifest.json',ADAPTER+'/COMPLETE_SEAL.sha256'})
 paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'validation/tier2-carrier-runtime-support-021-installation-001').iterdir() if p.is_file())
 descriptor=load('synthetic_dataset/tools/carrier_runtime020-registration.json');paths.update(v['path'] for v in descriptor['source_files'].values());paths.add('synthetic_dataset/tools/carrier_runtime020-registration.json')
 for name in paths:assert not Path(name).is_absolute() and not name.startswith(tuple(f'validation/tier2-support-019-qualification-{i:03d}/' for i in range(1,7)))
 adaptation['source_templates']=[{'path':name,'sha256':ref(name)['sha256']} for name in sorted(paths)]
 adaptation['transport_source_reviews']=old['transport_source_reviews']+[ref(package+'/SOURCE_READINESS.json')]
 adaptation_path=ROOT/PLAN/'predicate-reader-adaptation-specification.json'
 (ROOT/PLAN/'preimages/current011-adaptation.raw').write_bytes(adaptation_path.read_bytes())
 adaptation_path.write_text(json.dumps(adaptation,sort_keys=True,indent=2)+'\n')
 # Only consumed prospective version/path labels in the template change.
 name='final-config-template.json';p=ROOT/PLAN/name;before=p.read_bytes();(ROOT/PLAN/'preimages/current011-final-config-template.json.raw').write_bytes(before)
 after=before.decode().replace('qualification-plan-011','qualification-plan-012').replace('plan011','plan012');p.write_text(after)
 preserved=['claims.json','mandatory-floor.json','control-registration.json','audit_actual.py','test_admission_controls.py','materialize_registration.py','registration_lib.py','producer-contracts.json','source-inventory-registration.json']
 assert all((ROOT/PLAN/n).read_bytes()==(ROOT/OLDPLAN/n).read_bytes() for n in preserved)
 preflight=load(REG+'/preflight-007/stdout.log');assert preflight['tests_executed']==preflight['model_calls']==0 and preflight['task_inputs'] is False
 historical={'policy':'Candidate/reproducer preinstallation input maps are historical source evidence only; never recursively promoted to current source/guard/external maps or current27 PASS','prior_generator':ref('validation/tier2-carrier-runtime-support-021-installation-001/compact_protocol-preinstallation.py.raw'),'prior_registry':ref('validation/tier2-carrier-runtime-support-021-installation-001/runtime-registration-preinstallation.json.raw'),'current_generator':ref('synthetic_dataset/tools/carrier_runtime020/compact_protocol.py'),'current_registry':ref('synthetic_dataset/tools/carrier_runtime020-registration.json')}
 fidelity={'format':'verislop.support021-q007-final-source-binding-fidelity/1','status':'SOURCE_BOUND_RUNTIME_UNQUALIFIED','source_spec':ref(REG+'/SPECIFICATION_BEFORE_SOURCE.json'),'immutable_plan011':ref(OLDPLAN+'/hash-manifest.json'),'initial_copy_fidelity':ref(PLAN+'/INITIAL_COPY_FIDELITY.json'),'materializer':ref(PLAN+'/materialize_registration.py'),'materializer_byte_exact011':True,'legacy27_claims_floor_controls_audit_code_byte_exact':{n:ref(PLAN+'/'+n) for n in preserved},'authoritative_adapters_package':{'manifest':ref(ADAPTER+'/complete-hash-manifest.json'),'seal':ref(ADAPTER+'/COMPLETE_SEAL.sha256')},'independent_transport_source_readiness':adaptation['transport_source_reviews'],'current_profiles':[ref(REG+'/fresh-author-carrier-literals-007.json'),ref(REG+'/fresh-author-capture-literals-007.json')],'capture_profile_byte_exact006':(ROOT/REG/'fresh-author-capture-literals-007.json').read_bytes()==(ROOT/'validation/tier2-support019-registration-inputs-006/fresh-author-capture-literals-006.json').read_bytes(),'diagnostic_fixture_delta':ref(REG+'/FIXTURE_SOURCE_FIDELITY.json'),'diagnostic_parser':ref(package+'/diagnostic_failure_parser.py'),'historical_preinstallation_identity_roles':historical,'current_runtime_registration':ref('synthetic_dataset/tools/carrier_runtime020-registration.json'),'root_installation':ref('validation/tier2-carrier-runtime-support-021-installation-001/SOURCE_INSTALLATION.json'),'source_templates':adaptation['source_templates'],'actual_nonexecuting_preflight':ref(REG+'/preflight-007/actual-process-receipt.json'),'source_root':preflight['source_root'],'models_compiler_kernel_runtime_claims_executed':0,'qualification_authority':False}
 assert fidelity['capture_profile_byte_exact006'];write(PLAN+'/FINAL_SUPPORT021_Q007_BINDINGS_SOURCE_FIDELITY.json',fidelity)
 amendment=load('validation/tier2-support019-final-configuration-006/final-version-amendment-003-before-bindings.json')
 amendment.update({'revision':'007','closure_id':'support019-final-current-root-007','qualification_root':'validation/tier2-support-019-qualification-007','qualification_plan':PLAN,'qualification_adapters':ADAPTER,'external_carrier_profile':ref(REG+'/fresh-author-carrier-literals-007.json'),'external_capture_profile':ref(REG+'/fresh-author-capture-literals-007.json'),'current_preflight':ref(REG+'/preflight-007/stdout.log'),'capture_registration':ref(REG+'/capture003-registration.json'),'runtime020_registration':ref('synthetic_dataset/tools/carrier_runtime020-registration.json'),'diagnostic_failure_parser':ref(package+'/diagnostic_failure_parser.py'),'supersedes_paths_only':'Fresh Q007 source metadata; byte-exact legacy/capture/adapters/materializer truth conditions; no prior runtime outcome authority'})
 write(BASE+'/final-version-amendment-003-before-bindings.json',amendment)
 for n in ['required-current-bindings.json','specification-before-configuration.json','interface-amendment-before-bindings.json','source-preservation-input-amendment-before-bindings.json']:
  p=ROOT/BASE/n;value=load(BASE+'/'+n);raw=p.read_bytes();(ROOT/REG/'source-preimages'/('before-final-bindings-'+n+'.raw')).write_bytes(raw);refresh(value);p.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
 own={p.relative_to(ROOT/PLAN).as_posix():ref(p.relative_to(ROOT).as_posix()) for p in (ROOT/PLAN).rglob('*') if p.is_file() and p not in {ROOT/PLAN/'hash-manifest.json',ROOT/PLAN/'SEAL.sha256'}}
 manifest={'format':'verislop.support019-qualification-plan-source-manifest/1','files':{name:{'sha256':entry['sha256'],'byte_count':entry['byte_count']} for name,entry in sorted(own.items())},'inputs':{row['path']:ref(row['path']) for row in adaptation['source_templates']},'scope':'SOURCE_ONLY_PLAN012_SUPPORT021_NO_QUALIFICATION'}
 write(PLAN+'/hash-manifest.json',manifest)
 with (ROOT/PLAN/'SEAL.sha256').open('x') as f:f.write(ref(PLAN+'/hash-manifest.json')['sha256'][7:]+'  hash-manifest.json\n')
 print(json.dumps({'plan_manifest':ref(PLAN+'/hash-manifest.json'),'plan_seal':ref(PLAN+'/SEAL.sha256'),'fidelity':ref(PLAN+'/FINAL_SUPPORT021_Q007_BINDINGS_SOURCE_FIDELITY.json'),'current_refs':len(paths),'qualification_created':False},sort_keys=True))
if __name__=='__main__':main()
