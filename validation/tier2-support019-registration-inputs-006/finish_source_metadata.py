"""Finite current source binding metadata and plan seal, no qualification."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).absolute().parents[2]
REG='validation/tier2-support019-registration-inputs-006'
BASE='validation/tier2-support019-final-configuration-006'
PLAN='validation/tier2-support-019-qualification-plan-011'
OLDPLAN='validation/tier2-support-019-qualification-plan-010'
ADAPTER='validation/tier2-support-019-qualification-adapters-008'

def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def ref(name):
    raw=(ROOT/name).read_bytes();return {'path':name,'sha256':sha(raw),'byte_count':len(raw)}
def load(name):return json.loads((ROOT/name).read_bytes())
def write(name,value):
    path=ROOT/name
    with path.open('x') as stream:json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')
def tr(name):
    return name.replace('qualification-adapters-007','qualification-adapters-008').replace('registration-inputs-005','registration-inputs-006').replace('fresh-author-carrier-literals-005','fresh-author-carrier-literals-006').replace('fresh-author-capture-literals-005','fresh-author-capture-literals-006').replace('EXTERNAL_CURRENT006_PROFILES_SOURCE_DERIVATION.json','compact-profile-source-derivation.json')

def main():
    assert not (ROOT/'validation/tier2-support-019-qualification-006').exists()
    old=load(OLDPLAN+'/predicate-reader-adaptation-specification.json')
    adaptation=json.loads(json.dumps(old))
    adaptation['adapter_revision']='008'
    adaptation['planned_sources']={key:tr(name) for key,name in old['planned_sources'].items()}
    paths={tr(row['path']) for row in old['source_templates']}
    # Current source was installed by root after both independent source reviews.
    paths.update({'synthetic_dataset/tools/bootstrap_tier2.py','synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py','synthetic_dataset/tools/carrier_runtime020-registration.json',REG+'/fixture-system-source-fidelity.json',REG+'/compact-profile-source-derivation.json',REG+'/fresh-author-carrier-literals-006.json',REG+'/fresh-author-capture-literals-006.json',REG+'/prepare_unrelated_fixture.py',REG+'/assemble_current_source_handoff.py',BASE+'/prepare_configuration.py'})
    for folder,manifest,mapping in [('validation/tier2-carrier-runtime-support-020-implementation-001','hash-manifest.json','files'),('validation/tier2-carrier-runtime-support-020-integration-001','source-manifest.json','own_files'),('validation/tier2-carrier-runtime-support-020-integration-source-review-001','hash-manifest.json','files'),('validation/tier2-carrier-runtime-support-020-review-001','hash-manifest.json','files')]:
        for name in load(folder+'/'+manifest)[mapping]:paths.add(name if name.startswith(('validation/','synthetic_dataset/','tests/','/')) else folder+'/'+name)
        paths.update({folder+'/'+manifest,folder+('/SOURCE_SEAL.sha256' if mapping=='own_files' else '/SEAL.sha256')})
    descriptor=load('synthetic_dataset/tools/carrier_runtime020-registration.json')
    paths.update(v['path'] for v in descriptor['source_files'].values())
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'validation/tier2-carrier-runtime-support-020-installation-001').iterdir() if p.is_file())
    for name in paths:assert not name.startswith(tuple('validation/tier2-support-019-qualification-'+str(i).zfill(3)+'/' for i in range(1,6)))
    adaptation['source_templates']=[{'path':name,'sha256':ref(name)['sha256']} for name in sorted(paths)]
    adaptation['runtime_transport_revision']='support020-compact-runtime/1'
    adaptation['transport_source_reviews']=[ref('validation/tier2-carrier-runtime-support-020-integration-source-review-001/REVIEW.json'),ref('validation/tier2-carrier-runtime-support-020-review-001/SOURCE_REVIEW_REPORT.json')]
    adaptation_path=ROOT/PLAN/'predicate-reader-adaptation-specification.json'
    (ROOT/PLAN/'preimages/current010-adaptation.raw').write_bytes(adaptation_path.read_bytes())
    adaptation_path.write_text(json.dumps(adaptation,sort_keys=True,indent=2)+'\n')
    # Only the prospective consumed configuration-template binding labels change.
    for name in ('final-config-template.json',):
        p=ROOT/PLAN/name;before=p.read_bytes();(ROOT/PLAN/'preimages'/('current010-'+name+'.raw')).write_bytes(before)
        text=before.decode().replace('qualification-plan-010','qualification-plan-011').replace('qualification-adapters-007','qualification-adapters-008').replace('"adapter_revision": "007"','"adapter_revision": "008"')
        p.write_text(text)
    materializer=ref(PLAN+'/materialize_registration.py')
    fidelity={'format':'verislop.support020-q006-final-source-binding-fidelity/1','status':'SOURCE_BOUND_RUNTIME_UNQUALIFIED','source_spec':ref(REG+'/SPECIFICATION_BEFORE_SOURCE.md'),'immutable_plan010':ref(OLDPLAN+'/hash-manifest.json'),'materializer':materializer,'materializer_only_adapter_revision_operand_changed':True,'EXPECTED_CARRIER':'sha256:f855de49fa8522cfc91053fe3f1f0db1ebd3c199260acbb97618d0f998c5eb4a','legacy27_claims_floor_controls_audit_byte_exact':all((ROOT/PLAN/n).read_bytes()==(ROOT/OLDPLAN/n).read_bytes() for n in ('claims.json','mandatory-floor.json','control-registration.json','audit_actual.py','test_admission_controls.py')),'adapter_source_fidelity':ref(ADAPTER+'/SOURCE_FIDELITY_008.json'),'independent_compact_source_review':adaptation['transport_source_reviews'],'current_profiles':[ref(REG+'/fresh-author-carrier-literals-006.json'),ref(REG+'/fresh-author-capture-literals-006.json')],'diagnostic_fixture_delta':ref(REG+'/fixture-system-source-fidelity.json'),'source_templates':adaptation['source_templates'],'actual_nonexecuting_preflight':ref(REG+'/preflight-006/actual-process-receipt.json'),'source_root':load(REG+'/preflight-006/stdout.log')['source_root'],'models_compiler_kernel_runtime_claims_executed':0,'qualification_authority':False}
    assert fidelity['legacy27_claims_floor_controls_audit_byte_exact']
    write(PLAN+'/FINAL_SUPPORT020_Q006_BINDINGS_SOURCE_FIDELITY.json',fidelity)
    amendment=load('validation/tier2-support019-final-configuration-005/final-version-amendment-003-before-bindings.json')
    amendment.update({'revision':'006','closure_id':'support019-final-current-root-006','qualification_root':'validation/tier2-support-019-qualification-006','qualification_plan':PLAN,'qualification_adapters':ADAPTER,'external_carrier_profile':ref(REG+'/fresh-author-carrier-literals-006.json'),'external_capture_profile':ref(REG+'/fresh-author-capture-literals-006.json'),'current_preflight':ref(REG+'/preflight-006/stdout.log'),'capture_registration':ref(REG+'/capture003-registration.json'),'runtime020_registration':ref('synthetic_dataset/tools/carrier_runtime020-registration.json'),'supersedes_paths_only':'Fresh Q006 compact transport metadata, no earlier runtime outcome inheritance; unchanged filename003 is builder role API','author_index_owner':'Registered ancillary assembler alone creates author-index after successful author/equality/PURE; author controller retains author-records only'})
    write(BASE+'/final-version-amendment-003-before-bindings.json',amendment)
    for name in ('required-current-bindings.json','specification-before-configuration.json','interface-amendment-before-bindings.json'):
        p=ROOT/BASE/name;value=json.loads(p.read_text().replace('adapters007','adapters008').replace('adapter007','adapter008'))
        def refresh(v):
            if type(v) is dict:
                if set(v)>={'path','sha256','byte_count'} and (ROOT/v['path']).is_file():v.update(ref(v['path']))
                for item in v.values():refresh(item)
            elif type(v) is list:
                for item in v:refresh(item)
        refresh(value)
        p.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
    own={str(p.relative_to(ROOT/PLAN)):ref(str(p.relative_to(ROOT))) for p in (ROOT/PLAN).rglob('*') if p.is_file() and p.name not in ('hash-manifest.json','SEAL.sha256')}
    manifest={'format':'verislop.support019-qualification-plan-source-manifest/1','files':{name:{'sha256':entry['sha256'],'byte_count':entry['byte_count']} for name,entry in sorted(own.items())},'inputs':{row['path']:ref(row['path']) for row in adaptation['source_templates']},'scope':'SOURCE_ONLY_PLAN011_SUPPORT020_NO_QUALIFICATION'}
    write(PLAN+'/hash-manifest.json',manifest)
    (ROOT/PLAN/'SEAL.sha256').write_text(ref(PLAN+'/hash-manifest.json')['sha256'][7:]+'  hash-manifest.json\n')
    print(json.dumps({'plan_manifest':ref(PLAN+'/hash-manifest.json'),'plan_seal':ref(PLAN+'/SEAL.sha256'),'fidelity':ref(PLAN+'/FINAL_SUPPORT020_Q006_BINDINGS_SOURCE_FIDELITY.json'),'current_refs':len(paths),'qualification_created':False},sort_keys=True))

if __name__=='__main__':main()
