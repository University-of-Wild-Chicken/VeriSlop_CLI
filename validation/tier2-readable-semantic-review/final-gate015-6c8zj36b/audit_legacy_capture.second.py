from pathlib import Path
import json,sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'runtime'))
from verislop import canonical,schemas
from verislop.package import Package
from verislop.backends import vscore3_closure as B
from verislop.bridges import vscore3_checker as C
cap=root/'legacy-capture';meta=canonical.load_file(cap/'capture.json')
checks=[]
def ck(name,value,detail=None):
 assert value,name
 checks.append({'name':name,'result':'PASS','detail':detail})
actual={p.relative_to(cap).as_posix() for p in cap.rglob('*') if p.is_file()}
ck('complete actual captured path inventory',actual=={'capture.json',*meta['files']},len(actual))
for p,h in meta['files'].items():assert canonical.digest_file(cap/p)==h,p
ck('all captured file actual hashes',True,len(meta['files']))
freeze=canonical.load_file(root/'gate-inputs/source-freeze.json')
frozen_inputs={**freeze['source_files'],**canonical.load_file(root/'gate-inputs/test-sources.json')}
ck('capture producer root hashes canonical',canonical.digest_json(meta['source_hashes'])==meta['source_root'])
ck('all capture producer bytes match final gate015 sourcefreeze',all(frozen_inputs[p]==h and canonical.digest_file(cap/'registered-sources'/p)==h for p,h in meta['source_hashes'].items()),len(meta['source_hashes']))
pkg=Package(cap/'package')
diags=B.validate_frozen(pkg)
ck('current frozen package independent read-only validator',not diags,[d.to_json() for d in diags])
result=B.mechanical_snapshot(pkg)
ck('current published execution independent pure validation',result is not None and result['mechanical_status']=='VERIFIED',result['attempt_id'])
claim_records=canonical.load_file(pkg.root/'closure/implementation-claims.json')['claims']
det=next(c for c in claim_records if c['claim_id']=='CLOSURE:determinism')
ck('frozen registered .3 determinism predicate exact',det['result_predicate']==det['pass_predicate']=='closure-determinism/0.3')
ck('all61 outcomes represented+all required PASS',len(result['claims'])==len(claim_records)==61 and all(c['outcome']=='PASS' for c in result['claims'] if c['required']),sum(c['required'] for c in result['claims']))
ck('two actual complete clean source builds A/B',len(result['builds'])==2 and [b['build'] for b in result['builds']]==['A','B'] and all(b['ok'] is True and b['errors']==[] for b in result['builds']))
ck('exact13plus1 nullable output inventories',len(B.COMPARISON_SLOTS)==14 and result['determinism']['compared']==list(B.COMPARISON_SLOTS) and all(set(b['outputs'])==set(B.COMPARISON_SLOTS) and b['outputs']['readable_support'] is None and all(b['outputs'][k] is not None for k in B.COMPARISON_SLOTS if k!='readable_support') for b in result['builds']))
ck('independently recomputed present-null comparison',B._compare_outputs(result['builds'][0]['outputs'],result['builds'][1]['outputs'])==result['determinism']['mismatches']==[])
accepted,pending,semantic_diags=C.verify_published(pkg,'implementation',rebuild=False)
ck('actual published bridge metadata portable no-rebuild validation',bool(accepted) and not pending and not semantic_diags,{'accepted':accepted,'pending':pending,'diagnostics':[d.to_json() for d in semantic_diags]})
report=canonical.load_file(pkg.root/'report.json')
ck('stored report status/current-result/determinism agreement',report['backend']=='verislop.backend.vscore/0.3' and report['mechanical_status']==result['mechanical_status'] and report['determinism']==result['determinism'] and report['builds']==result['builds'],{'mechanical_result':report['mechanical_result'],'terminal_status':report['terminal_status'],'release_status':report['release_status'],'counts':report['counts']})
for prefix in ('builds/A','builds/B'):
 build=canonical.load_file((pkg.root/result['mechanical_result_path']).parent/(prefix+'.json'))
 assert build==next(b for b in result['builds'] if b['build']==prefix[-1])
 semantic=(pkg.root/result['mechanical_result_path']).parent/prefix/'semantic'
 cert=canonical.load_file(semantic/'certificate.json')
 assert 'readable_support' not in cert
 for name in ('A','B'):
  obs=canonical.load_file(semantic/'builds'/f'{name}.json')
  assert obs['readable_support'] is None
ck('retained source build semantic copies honest legacy absence',True)
output={'format':'verislop.independent-gate015-legacy-capture-checks/1','checks':checks,'scope':'Actual frozen .3 legacy package/semantic/current execution pure validation and hash-bound portability only; no fresh native/kernel/model/build execution; final combined engineering qualification pending.'}
(root/'legacy-checks.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
