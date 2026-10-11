"""Bind current static capture/checkpoint/install metadata, not execution outcomes."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-007'
OLD='validation/tier2-support019-registration-inputs-006'
BASE='validation/tier2-support019-final-configuration-008'
PLAN='validation/tier2-support-019-qualification-plan-012'
def ref(name):
 b=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def load(name):return json.loads((ROOT/name).read_bytes())
def write(name,value):
 with (ROOT/name).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
def transform(value):
 if isinstance(value,str):
  return value.replace(OLD,REG).replace('validation/tier2-support019-final-configuration-006',BASE).replace('qualification-plan-011','qualification-plan-012').replace('qualification-006','qualification-007').replace('support019-final-current-root-006','support019-final-current-root-007').replace('preflight-006','preflight-007').replace('fresh006 unrelated','fresh007 unrelated')
 if isinstance(value,list):return [transform(x) for x in value]
 if isinstance(value,dict):return {transform(k):transform(v) for k,v in value.items()}
 return value
def main():
 assert not (ROOT/'validation/tier2-support-019-qualification-007').exists()
 preflight=load(REG+'/preflight-007/stdout.log')
 assert preflight['tests_executed']==preflight['model_calls']==0 and preflight['task_inputs'] is False
 assert preflight['test_count']==208 and len(preflight['test_modules'])==18
 checkpoint=transform(load(OLD+'/checkpoint-control-identities.json'))
 checkpoint['preflight_path']=REG+'/preflight-007/stdout.log';checkpoint['preflight_sha256']=ref(checkpoint['preflight_path'])['sha256']
 assert len(checkpoint['ids'])==17 and set(checkpoint['ids']).issubset(preflight['test_ids'])
 write(REG+'/checkpoint-control-identities.json',checkpoint)
 capture=transform(load(OLD+'/capture003-registration.json'))
 capture['runtime020_registration']=ref('synthetic_dataset/tools/carrier_runtime020-registration.json')
 capture['current_checkpoint_controls']['path']=REG+'/checkpoint-control-identities.json'
 for case in capture['cases']:
  if case['id']=='FA002-001':case['message']='Exact current installed support021-prose compact runtime_agent_message; support020 API own pending FIRST/NEXT/CONFIRM/HASH only; no collector/expectations/oracle inputs'
 write(REG+'/capture003-registration.json',capture)
 for name in ['CAPTURE003_REGISTRATION_SPECIFICATION_BEFORE_GENERATION.json']:
  write(REG+'/'+name,transform(load(OLD+'/'+name)))
 # This historical installation is still the actual unchanged legacy carrier source observation.
 with (ROOT/REG/'source-installation-observation.json').open('xb') as f:f.write((ROOT/OLD/'source-installation-observation.json').read_bytes())
 review=transform(load(OLD+'/final-installation-review-specification-before-record.json'))
 review['runtime020_installation']=ref('validation/tier2-carrier-runtime-support-021-installation-001/SOURCE_INSTALLATION.json')
 review['runtime020_registration']=ref('synthetic_dataset/tools/carrier_runtime020-registration.json')
 review['diagnostic_failure_parser']=ref('validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py')
 review['current_adapters_manifest']=ref('validation/tier2-support-019-qualification-adapters-008/complete-hash-manifest.json')
 review['configuration_sha256']=None;review['input_root']=None
 write(REG+'/final-installation-review-specification-before-record.json',review)
 print(json.dumps({'capture':ref(REG+'/capture003-registration.json'),'checkpoint':ref(REG+'/checkpoint-control-identities.json'),'review_spec':ref(REG+'/final-installation-review-specification-before-record.json'),'actual_source_root':preflight['source_root'],'claims_qualified':0},sort_keys=True))
if __name__=='__main__':main()
