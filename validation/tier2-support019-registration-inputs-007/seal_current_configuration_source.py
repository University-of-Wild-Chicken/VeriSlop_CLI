"""Seal current source config from registered finite observations, no runtime PASS."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-007'
BASE='validation/tier2-support019-final-configuration-008'
PLAN='validation/tier2-support-019-qualification-plan-012'
def ref(name):
 b=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def load(name):return json.loads((ROOT/name).read_bytes())
def write(name,value):
 with (ROOT/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
def main():
 config=load(BASE+'/final-config.json');review=load(REG+'/final-installation-review.json');interface=load(REG+'/configuration-interface-inspection.json')
 assert not (ROOT/config['qualification_root']).exists()
 assert review['configuration']==ref(BASE+'/final-config.json') and interface['configuration']['sha256']==ref(BASE+'/final-config.json')['sha256']
 assert interface['status']=='READY' and interface['missing_literal_paths']==[]
 assert all(not Path(n).is_absolute() for n in config['verification_input_paths']+config['adapters']['required_adapter_inputs'])
 receipts={}
 paths={'static-source-preparation':'validation/tier2-support019-source-binding-processes-007/static-source-preparation001/actual-process-receipt.json','current-static-metadata':'validation/tier2-support019-source-binding-processes-007/current-static-metadata001/actual-process-receipt.json','fixture-generator':REG+'/fixture-profile-process-001/fixture-generation/actual-process-receipt.json','profile-derivation':REG+'/fixture-profile-process-001/profile-derivation/actual-process-receipt.json','plan-final-metadata':'validation/tier2-support019-source-binding-processes-007/plan-final-metadata/actual-process-receipt.json','source-ready-assembler':'validation/tier2-support019-source-binding-processes-007/source-ready-assembler/actual-process-receipt.json','configuration-builder':'validation/tier2-support019-source-binding-processes-007/configuration-builder/actual-process-receipt.json','configuration-interface':'validation/tier2-support019-source-binding-processes-007/configuration-interface/actual-process-receipt.json','configuration-source-inspector':'validation/tier2-support019-source-binding-processes-007/configuration-source-inspector/actual-process-receipt.json'}
 for role,name in paths.items():
  data=load(name);assert type(data['returncode']) is int and data['returncode']==0 and type(data['pid']) is int and data['pid']>0
  assert data['before']==data['after'] and data['timeout_seconds'] is None and data['timed_out'] is False
  assert ref(data['stdout']['path'])==data['stdout'] and ref(data['stderr']['path'])==data['stderr'];receipts[role]=ref(name)
 preflight=load(REG+'/preflight-007/stdout.log')
 assert preflight['test_count']==208 and len(preflight['test_modules'])==18 and preflight['tests_executed']==preflight['model_calls']==0
 checks={'format':'verislop.support019-configuration-source-checks/1','status':'SOURCE_STATIC_CHECKED_FROZEN_PENDING_ROOT_AUTH_RUNTIME_UNQUALIFIED','claims':27,'test_source_identities':preflight['test_count'],'modules':len(preflight['test_modules']),'actual_source_inspector_receipt':receipts['configuration-source-inspector'],'fresh_nonexecuting_preflight':ref(REG+'/preflight-007/stdout.log'),'root_authorized_finite_source_inspection':ref(REG+'/final-installation-review.json'),'authoritative_adapter_package':config['authoritative_adapter_source_package'],'binary_path_separation':'No absolute paths in repository lists; current external interpreter hashes bound independently','diagnostic_failure_parser':config['diagnostic_failure_parser'],'qualification_authority':False,'task_TESTED_authority':False,'activation_authority':False,'all27_runtime_claims':'UNRESOLVED_NOT_EXECUTED'}
 write(BASE+'/CONFIGURATION_METADATA_CHECKS.json',checks)
 with (ROOT/BASE/'HANDOFF.md').open('x') as f:f.write('Q007 source preparation only. Installed support021 message and evidence-only diagnostic parser; unchanged support020 runtime, legacy006 carrier, adapters008, plan011 materializer and 27 completion predicates. Actual fresh preflight '+config['source_root']+'. Complete adapter package selected directly, external binary refs excluded from repository-relative lists before builder output. Registered actual source builder/interface/inspector int0, interface READY. All27 runtime claims UNRESOLVED_NOT_EXECUTED. Q007 absent; root authorization required before exact materializer. Two existing Lean identity queries only at future materialization; no compiler/kernel/task authority.\n')
 files={p.relative_to(ROOT).as_posix():ref(p.relative_to(ROOT).as_posix()) for p in (ROOT/BASE).rglob('*') if p.is_file() and p not in {ROOT/BASE/'configuration-source-manifest.json',ROOT/BASE/'SEAL.sha256'}}
 write(BASE+'/configuration-source-manifest.json',{'format':'verislop.support019-configuration-source-manifest/1','status':checks['status'],'files':files,'qualification_authority':False,'activation_authority':False})
 with (ROOT/BASE/'SEAL.sha256').open('x') as f:f.write(ref(BASE+'/configuration-source-manifest.json')['sha256'][7:]+'  configuration-source-manifest.json\n')
 record={'format':'verislop.support021-q007-source-preparation-handoff/1','status':'SOURCE_READY_PENDING_ROOT_AUTH_NO_QUALIFICATION','qualification_root':config['qualification_root'],'source_root':config['source_root'],'configuration':ref(BASE+'/final-config.json'),'configuration_manifest':ref(BASE+'/configuration-source-manifest.json'),'configuration_seal':ref(BASE+'/SEAL.sha256'),'ready':ref(BASE+'/generation-inputs-ready.json'),'plan_manifest':ref(PLAN+'/hash-manifest.json'),'plan_seal':ref(PLAN+'/SEAL.sha256'),'plan_fidelity':ref(PLAN+'/FINAL_SUPPORT021_Q007_BINDINGS_SOURCE_FIDELITY.json'),'authoritative_adapters_package':config['authoritative_adapter_source_package'],'profile_derivation':ref(REG+'/compact-profile-source-derivation.json'),'carrier_profile':ref(REG+'/fresh-author-carrier-literals-007.json'),'capture_profile':ref(REG+'/fresh-author-capture-literals-007.json'),'diagnostic_parser':config['diagnostic_failure_parser'],'preflight_receipt':ref(REG+'/preflight-007/actual-process-receipt.json'),'fixture_map':ref(REG+'/fresh-fixture-input-map.json'),'interface':ref(REG+'/configuration-interface-inspection.json'),'installation_review':ref(REG+'/final-installation-review.json'),'source_process_receipts':receipts,'counts':{'claims':27,'equality':55,'PURE':30,'checkpoint':17,'test_IDs':208,'test_modules':18},'runtime_qualification_authority':False,'models':0,'VIEW':0,'Lean_compilation_kernel_task_calls':0,'qualification_created':False}
 write(REG+'/Q007_SOURCE_PREPARATION_HANDOFF.json',record)
 print(json.dumps({'handoff':ref(REG+'/Q007_SOURCE_PREPARATION_HANDOFF.json'),'configuration':record['configuration'],'configuration_manifest':record['configuration_manifest'],'configuration_seal':record['configuration_seal'],'qualification_created':False},sort_keys=True))
if __name__=='__main__':main()
