"""Finite registered Q006 source derivatives; no runtime or qualification."""
from pathlib import Path
import ast
import hashlib
import json
import shutil

ROOT = Path(__file__).absolute().parents[2]
REG = 'validation/tier2-support019-registration-inputs-006'
BASE = 'validation/tier2-support019-final-configuration-006'
PLAN = 'validation/tier2-support-019-qualification-plan-011'
OLDREG = REG[:-3]+'005'
OLDBASE = BASE[:-3]+'005'
OLDPLAN = PLAN[:-3]+'010'
ADAPTER = 'validation/tier2-support-019-qualification-adapters-008'
INTEGRATION = 'validation/tier2-carrier-runtime-support-020-integration-001'

def sha(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def ref(path):
    raw=(ROOT/path).read_bytes();return {'path':path,'sha256':sha(raw),'byte_count':len(raw)}
def write(path,raw):
    target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:stream.write(raw)
def transform(text):
    for old,new in ((OLDREG,REG),(OLDBASE,BASE),(OLDPLAN,PLAN),('validation/tier2-support-019-qualification-adapters-007',ADAPTER),('validation/tier2-support-019-qualification-005','validation/tier2-support-019-qualification-006'),('validation/tier2-support019-source-binding-processes-005','validation/tier2-support019-source-binding-processes-006'),('support019-final-current-root-005','support019-final-current-root-006'),('fixture-current-whole-gate-005','fixture-current-whole-gate-006'),('preflight-005','preflight-006'),('fresh-author-carrier-literals-005','fresh-author-carrier-literals-006'),('fresh-author-capture-literals-005','fresh-author-capture-literals-006'),('FINAL_CURRENT006_BINDINGS_SOURCE_FIDELITY.json','FINAL_SUPPORT020_Q006_BINDINGS_SOURCE_FIDELITY.json'),('configuration005','configuration006'),('registration-inputs005','registration-inputs006'),('plan010','plan011'),('qualification005','qualification006'),('Q005','Q006'),('qualification-019-005','qualification-019-006')):
        text=text.replace(old,new)
    return text
def replace(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)

def main():
    assert not (ROOT/'validation/tier2-support-019-qualification-006').exists()
    assert (ROOT/PLAN).is_dir()
    for p in (ROOT/OLDPLAN).rglob('*'):
        if p.is_file():assert p.read_bytes()==(ROOT/PLAN/p.relative_to(ROOT/OLDPLAN)).read_bytes()
    # The manifest/seal and predecessor outcome metadata are historical preimages.
    for name in ('hash-manifest.json','SEAL.sha256'):
        target=ROOT/PLAN/name
        (ROOT/PLAN/('preimages/current010-'+name)).write_bytes(target.read_bytes())
        target.unlink()
    created=[]
    pairs=[(OLDBASE+'/prepare_configuration.py',BASE+'/prepare_configuration.py'),(OLDBASE+'/required-current-bindings.json',BASE+'/required-current-bindings.json'),(OLDREG+'/assemble_current_source_handoff.py',REG+'/assemble_current_source_handoff.py'),(OLDREG+'/run_registered_process.py',REG+'/run_registered_process.py'),(OLDREG+'/run_nonexecuting_preflight_005.py',REG+'/run_nonexecuting_preflight_006.py'),(OLDREG+'/preflight-005/specification.json',REG+'/preflight-006/specification.json'),(OLDBASE+'/specification-before-configuration.json',BASE+'/specification-before-configuration.json'),(OLDBASE+'/interface-amendment-before-bindings.json',BASE+'/interface-amendment-before-bindings.json'),(OLDBASE+'/source-preservation-input-amendment-before-bindings.json',BASE+'/source-preservation-input-amendment-before-bindings.json'),(OLDREG+'/verify_configuration_source.py',REG+'/verify_configuration_source.py')]
    package_rows='''        ("validation/tier2-carrier-runtime-support-020-implementation-001", "hash-manifest.json", ["files"]),
        ("validation/tier2-carrier-runtime-support-020-integration-001", "source-manifest.json", ["files"]),
        ("validation/tier2-carrier-runtime-support-020-integration-source-review-001", "hash-manifest.json", ["files", "inputs"]),
        ("validation/tier2-carrier-runtime-support-020-review-001", "hash-manifest.json", ["files"]),
'''
    for before,after in pairs:
        original=(ROOT/before).read_bytes();text=transform(original.decode())
        if before.endswith('prepare_configuration.py'):
            text=text.replace("adaptation['adapter_revision']=='007'","adaptation['adapter_revision']=='008'")
            text=text.replace('PLAN010_ADAPTER007','PLAN011_ADAPTER008').replace('PLAN010_CURRENT','PLAN011_CURRENT')
            text=replace(text,"'validation/tier2-support-019-qualification-004/'))","'validation/tier2-support-019-qualification-004/','validation/tier2-support-019-qualification-005/'))")
            anchor="    config['external_runtime_files']=external\n"
            addition="    compact_descriptor=load('synthetic_dataset/tools/carrier_runtime020-registration.json')\n    for interpreter in compact_descriptor['interpreters'].values():\n        name=interpreter['path'];need(sha(raw(name))==interpreter['sha256'],'COMPACT_INTERPRETER_CHANGED:'+name);external[name]=interpreter['sha256']\n    config['compact_runtime_registration']=reference('synthetic_dataset/tools/carrier_runtime020-registration.json')\n    config['compact_runtime_trust']={'Node_and_Python':'Explicit external binary identities; source/hash/checkpoint runtime is trusted only for registered transport operations','author_index_owner':'registered ancillary assembler after completed author/equality/PURE evidence; author controller writes only author-records'}\n"
            text=replace(text,anchor,addition+anchor)
        elif before.endswith('assemble_current_source_handoff.py'):
            text=text.replace('adaptation["adapter_revision"] == "007"','adaptation["adapter_revision"] == "008"')
            text=replace(text,'"validation/tier2-support-019-qualification-004/")),','"validation/tier2-support-019-qualification-004/", "validation/tier2-support-019-qualification-005/")),')
            text=replace(text,'    for folder, manifest_name, maps in declarations:',package_rows+'    ]\n    for folder, manifest_name, maps in declarations:') if False else text
            anchor='    ]\n    for folder, manifest_name, maps in declarations:'
            text=replace(text,anchor,package_rows+anchor)
            text=replace(text,'seal_path = folder + "/SEAL.sha256"','seal_path = folder + ("/SOURCE_SEAL.sha256" if manifest_name == "source-manifest.json" else "/SEAL.sha256")')
            text=replace(text,'    paths.add(carrier)\n','    paths.add(carrier)\n    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/"validation/tier2-carrier-runtime-support-020-installation-001").iterdir() if p.is_file())\n')
            text=replace(text,'    reviews = [review,','    reviews = [review, "validation/tier2-carrier-runtime-support-020-integration-source-review-001/REVIEW.json",')
        elif before.endswith('run_registered_process.py'):
            text=replace(text,'path.relative_to(ROOT).as_posix()','path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)')
        if after.endswith('.py'):ast.parse(text)
        else:json.loads(text)
        write(REG+'/source-preimages/current005-'+Path(before).name+'.raw',original)
        write(after,text.encode());created.append({'preimage':ref(before),'successor':ref(after)})
    materializer=ROOT/PLAN/'materialize_registration.py'
    old=materializer.read_bytes();new=replace(old.decode(),'adapters["adapter_revision"] == "007"','adapters["adapter_revision"] == "008"').encode()
    (ROOT/PLAN/'preimages/current010-materialize_registration.py.raw').write_bytes(old)
    materializer.write_bytes(new)
    beforetree=ast.parse(old);aftertree=ast.parse(new)
    class Normalize(ast.NodeTransformer):
        def visit_Constant(self,node):
            if node.value in ('007','008'):return ast.Constant(value='ADAPTER_REVISION')
            return node
    assert ast.dump(Normalize().visit(beforetree),include_attributes=False)==ast.dump(Normalize().visit(aftertree),include_attributes=False)
    metadata={'format':'verislop.support020-static-source-derivation/1','scope':'SOURCE_ONLY_NO_QUALIFICATION','created_sources':created,'materializer_only_adapter_revision_operand_changed':True,'carrier_expected_hash_unchanged':True,'claims27_floor_audit_controls_byte_exact':all((ROOT/PLAN/n).read_bytes()==(ROOT/OLDPLAN/n).read_bytes() for n in ('claims.json','mandatory-floor.json','audit_actual.py','control-registration.json','test_admission_controls.py')),'runtime_qualification_authority':False}
    write(REG+'/static-source-fidelity.json',(json.dumps(metadata,sort_keys=True,indent=2)+'\n').encode())
    print(json.dumps({'created_sources':len(created),'materializer_AST_equal_excluding_only_adapter_revision':True,'qualification_created':False}))

if __name__=='__main__':main()
