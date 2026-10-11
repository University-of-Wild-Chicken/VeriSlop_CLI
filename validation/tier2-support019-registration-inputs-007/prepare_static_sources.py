"""Registered minimal Q007 static helper successors; no qualification execution."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-007'
BASE='validation/tier2-support019-final-configuration-008'
PLAN='validation/tier2-support-019-qualification-plan-012'
OLDREG='validation/tier2-support019-registration-inputs-006'
OLDBASE='validation/tier2-support019-final-configuration-006'
OLDPLAN='validation/tier2-support-019-qualification-plan-011'
PAIRS=[
 (OLDBASE+'/prepare_configuration.py',BASE+'/prepare_configuration.py'),
 (OLDBASE+'/required-current-bindings.json',BASE+'/required-current-bindings.json'),
 (OLDBASE+'/specification-before-configuration.json',BASE+'/specification-before-configuration.json'),
 (OLDBASE+'/interface-amendment-before-bindings.json',BASE+'/interface-amendment-before-bindings.json'),
 (OLDBASE+'/source-preservation-input-amendment-before-bindings.json',BASE+'/source-preservation-input-amendment-before-bindings.json'),
 (OLDREG+'/assemble_current_source_handoff.py',REG+'/assemble_current_source_handoff.py'),
 (OLDREG+'/run_registered_process.py',REG+'/run_registered_process.py'),
 (OLDREG+'/run_nonexecuting_preflight_006.py',REG+'/run_nonexecuting_preflight_007.py'),
 (OLDREG+'/preflight-006/specification.json',REG+'/preflight-007/specification.json'),
 (OLDREG+'/verify_configuration_source.py',REG+'/verify_configuration_source.py'),
 (OLDREG+'/seal_configuration_source.py',REG+'/seal_configuration_source.py'),
]

def ref(name):
 raw=(ROOT/name).read_bytes();return {'path':name,'sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'byte_count':len(raw)}
def write(name,raw):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(raw)
def replace(text,old,new):
 assert text.count(old)==1,(old,text.count(old));return text.replace(old,new)
def transform(text):
 for old,new in [(OLDREG,REG),(OLDBASE,BASE),('validation/tier2-support019-final-configuration-007',BASE),(OLDPLAN,PLAN),('validation/tier2-support-019-qualification-006','validation/tier2-support-019-qualification-007'),('validation/tier2-support019-source-binding-processes-006','validation/tier2-support019-source-binding-processes-007'),('support019-final-current-root-006','support019-final-current-root-007'),('fixture-current-whole-gate-006','fixture-current-whole-gate-007'),('preflight-006','preflight-007'),('fresh-author-carrier-literals-006','fresh-author-carrier-literals-007'),('fresh-author-capture-literals-006','fresh-author-capture-literals-007'),('FINAL_SUPPORT020_Q006_BINDINGS_SOURCE_FIDELITY.json','FINAL_SUPPORT021_Q007_BINDINGS_SOURCE_FIDELITY.json'),('plan011','plan012'),('PLAN011','PLAN012'),('configuration006','configuration008'),('registration-inputs006','registration-inputs007'),('qualification006','qualification007'),('Q006','Q007')]:text=text.replace(old,new)
 return text

def main():
 assert not (ROOT/'validation/tier2-support-019-qualification-007').exists()
 installation=json.loads((ROOT/'validation/tier2-carrier-runtime-support-021-installation-001/SOURCE_INSTALLATION.json').read_bytes())
 for key in ('source','registry','parser_metadata_source'):
  identity=installation[key];assert ref(identity['path'])==identity
 deltas=[]
 for before,after in PAIRS:
  raw=(ROOT/before).read_bytes();text=transform(raw.decode());declared=[]
  if before.endswith('/prepare_configuration.py'):
   text=replace(text,"ADAPTERS+'/hash-manifest.json'","ADAPTERS+'/complete-hash-manifest.json'")
   text=replace(text,"'validation/tier2-support-019-qualification-005/'))","'validation/tier2-support-019-qualification-005/','validation/tier2-support-019-qualification-006/'))")
   # Source inventories carry only repository paths; all binaries stay independently pinned.
   text=replace(text,"    config['required_verifier_paths']=sorted(required_verifiers)\n","    verification={name for name in verification if not Path(name).is_absolute()}\n    assert all(not Path(name).is_absolute() for name in verification)\n    config['authoritative_adapter_source_package']={'manifest':reference(ADAPTERS+'/complete-hash-manifest.json'),'seal':reference(ADAPTERS+'/COMPLETE_SEAL.sha256'),'entry_maps':['files','inputs']}\n    config['diagnostic_failure_parser']=reference('validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py')\n    config['required_verifier_paths']=sorted(required_verifiers)\n")
   declared=['complete adapter manifest selection','Q006 previous runtime prefix rejected','absolute external paths excluded from repository lists before output','actual complete package/evidence-parser metadata']
  elif before.endswith('/assemble_current_source_handoff.py'):
   text=replace(text,'"validation/tier2-support-019-qualification-005/")),','"validation/tier2-support-019-qualification-005/", "validation/tier2-support-019-qualification-006/")),')
   text=replace(text,'(ADAPTER, "hash-manifest.json", ["files"]),','(ADAPTER, "complete-hash-manifest.json", ["files", "inputs"]),')
   text=replace(text,'    ]\n    for folder, manifest_name, maps in declarations:','        ("validation/tier2-carrier-runtime-support-021-implementation-001", "hash-manifest.json", ["files"]),\n    ]\n    for folder, manifest_name, maps in declarations:')
   text=replace(text,'seal_path = folder + ("/SOURCE_SEAL.sha256" if manifest_name == "source-manifest.json" else "/SEAL.sha256")','seal_path = folder + ("/COMPLETE_SEAL.sha256" if manifest_name == "complete-hash-manifest.json" else "/SOURCE_SEAL.sha256" if manifest_name == "source-manifest.json" else "/SEAL.sha256")')
   text=replace(text,'    paths.add(carrier)\n','    paths.add(carrier)\n    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/"validation/tier2-carrier-runtime-support-021-installation-001").iterdir() if p.is_file())\n')
   text=replace(text,'    reviews = [review,','    reviews = [review, "validation/tier2-carrier-runtime-support-021-implementation-001/SOURCE_READINESS.json",')
   declared=['complete adapters008 own/input maps and seal','actual support021 own manifest/source readiness/installation','Q006 runtime prefix rejected']
  elif before.endswith('/verify_configuration_source.py'):
   text=replace(text,"    assert config['strict_implementation_proof_release_unchanged'] is True\n","    assert config['strict_implementation_proof_release_unchanged'] is True\n    assert all(not Path(name).is_absolute() for name in config['verification_input_paths']+config['adapters']['required_adapter_inputs'])\n    descriptor=load('synthetic_dataset/tools/carrier_runtime020-registration.json')\n    for identity in descriptor['interpreters'].values():assert config['external_runtime_files'][identity['path']]==identity['sha256']\n    assert config['diagnostic_failure_parser']==ref('validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py')\n")
   declared=['source-only exact binary separation and current evidence parser metadata checks']
  if after.endswith('.py'):ast.parse(text)
  else:json.loads(text)
  write(REG+'/source-preimages/current006-'+Path(before).name+'.raw',raw)
  write(after,text.encode());deltas.append({'preimage':ref(before),'successor':ref(after),'declared_extra_deltas':declared})
 assert (ROOT/REG/'run_registered_process.py').read_bytes()==(ROOT/OLDREG/'run_registered_process.py').read_bytes()
 fidelity={'format':'verislop.support021-static-helper-source-fidelity/1','scope':'SOURCE_ONLY','specification':ref(REG+'/SPECIFICATION_BEFORE_SOURCE.json'),'source_pairs':deltas,'path_label_replacements':True,'materializer_and_adapter_code_changed':False,'external_binary_path_separation_at_builder':True,'runtime_predicate_changes':0,'qualification_authority':False}
 write(REG+'/static-source-fidelity.json',(json.dumps(fidelity,sort_keys=True,indent=2)+'\n').encode())
 print(json.dumps({'created':len(deltas),'fidelity':ref(REG+'/static-source-fidelity.json'),'Q007_created':False},sort_keys=True))

if __name__=='__main__':main()
