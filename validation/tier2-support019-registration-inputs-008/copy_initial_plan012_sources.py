"""Copy immutable plan012 bytes only; future Q008 bindings remain unresolved."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
REG=ROOT/'validation/tier2-support019-registration-inputs-008'
OLD=ROOT/'validation/tier2-support-019-qualification-plan-012'
NEW=ROOT/'validation/tier2-support-019-qualification-plan-013'
def ref(p):
 b=p.read_bytes();return {'path':p.relative_to(ROOT).as_posix(),'sha256':'sha256:'+hashlib.sha256(b).hexdigest(),'byte_count':len(b)}
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def main():
 spec=json.loads((REG/'PLAN013_SPECIFICATION_BEFORE_INITIAL_COPY.json').read_bytes())
 assert ref(OLD/'hash-manifest.json')==spec['predecessor_manifest'] and ref(OLD/'SEAL.sha256')==spec['predecessor_seal']
 assert (OLD/'SEAL.sha256').read_text().split()==[spec['predecessor_manifest']['sha256'][7:],'hash-manifest.json']
 manifest=json.loads((OLD/'hash-manifest.json').read_bytes());assert len(manifest['files'])==spec['own_plan_source_count']==264
 assert not (ROOT/'validation/tier2-support-019-qualification-008').exists()
 pairs={};asts={}
 for name,identity in sorted(manifest['files'].items()):
  before=OLD/name;raw=before.read_bytes();actual=ref(before)
  assert actual['sha256']==identity['sha256'] and actual['byte_count']==identity['byte_count']
  after=NEW/name;after.parent.mkdir(parents=True,exist_ok=True)
  with after.open('xb') as f:f.write(raw)
  assert after.read_bytes()==raw;pairs[name]={'preimage':actual,'copy':ref(after)}
  if name.endswith('.py'):
   left=ast.dump(ast.parse(raw),include_attributes=False);right=ast.dump(ast.parse(after.read_bytes()),include_attributes=False);assert left==right
   asts[name]='sha256:'+hashlib.sha256(left.encode()).hexdigest()
 archived={}
 for name in ['hash-manifest.json','SEAL.sha256']:
  after=NEW/'preimages'/('baseline012-'+name+'.raw');after.parent.mkdir(parents=True,exist_ok=True)
  with after.open('xb') as f:f.write((OLD/name).read_bytes())
  assert after.read_bytes()==(OLD/name).read_bytes();archived[name]=ref(after)
 claims=json.loads((NEW/'claims.json').read_bytes());assert len(claims['original_claims'])==18 and len(claims['additional_claims'])==9
 assert ref(NEW/'materialize_registration.py')['sha256']==spec['materializer_byte_exact012']['sha256']
 assert not (NEW/'hash-manifest.json').exists() and not (NEW/'SEAL.sha256').exists()
 fidelity={'format':'verislop.support022-plan013-initial-copy-fidelity/1','status':'BASELINE_SOURCE_BYTES_COPIED_FUTURE_BINDINGS_UNRESOLVED','specification':ref(REG/'PLAN013_SPECIFICATION_BEFORE_INITIAL_COPY.json'),'predecessor_manifest':spec['predecessor_manifest'],'predecessor_seal':spec['predecessor_seal'],'copied_own_files':len(pairs),'all264_own_sources_byte_exact':True,'source_pairs':pairs,'all_python_ASTs_exact':asts,'archived_top_level_manifest_seal':archived,'claims':27,'materializer_byte_exact012':ref(NEW/'materialize_registration.py'),'semantic_predicate_floor_control_code_changed':False,'source_profile_root_current_metadata_bindings':'UNRESOLVED_UNSEALED_PENDING_AUTHENTICATED_ROOT_INSTALLATION','predecessor_metadata_interpretation':'Historical baseline source preimages only; no current source/profile/root/PASS inference','qualification_authority':False,'activation_authority':False,'Q008_created':False,'preflight_profile_fixture_model_VIEW_current27_native_task_calls':0}
 write(NEW/'INITIAL_PLAN012_COPY_FIDELITY.json',fidelity)
 print(json.dumps({'copied_own_sources':264,'python_ASTs':len(asts),'fidelity':ref(NEW/'INITIAL_PLAN012_COPY_FIDELITY.json'),'materializer':ref(NEW/'materialize_registration.py'),'current_bindings':'UNRESOLVED_UNSEALED','Q008_created':False},sort_keys=True))
 return 0
if __name__=='__main__':raise SystemExit(main())
