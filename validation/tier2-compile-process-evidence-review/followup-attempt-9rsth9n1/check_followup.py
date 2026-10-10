import copy,hashlib,json,pathlib,sys,datetime
OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(OUT/'runtime'))
from verislop import canonical,review_projection as p
from verislop.bridges.manifest import InvalidPackage
witness=json.loads((OUT/'prior-bound-inputs/normalizer-counterexample.json').read_bytes())
assert canonical.digest((OUT/'prior-bound-inputs/normalizer-counterexample.json').read_bytes())=='sha256:76b0828fb663df7357136ce3564e29cecb39bdc97609310d743b000f120ea0c3'
checks=[];outputs=[]
def check(label,passed,details=None):
 checks.append({'id':label,'pass':bool(passed),'details':details})
 if not passed:raise AssertionError(label)
def reject(label,record,raw):
 try:p.normalize(record,raw)
 except InvalidPackage as e:check(label,e.code=='STALE_OR_UNBOUND_EVIDENCE',{'code':e.code,'message':str(e)})
 else:check(label,False)
for obs in witness['observations']:
 record=obs['record'];raw=obs['raw'];body={k:v for k,v in record.items() if k!='evidence_id'}
 check('exact-original-evidence-id:'+obs['label'],'ev-'+canonical.sha256_hex(canonical.dumps(body))[:32]==record['evidence_id'])
 check('exact-original-raw-hash:'+obs['label'],canonical.digest(canonical.dumps(raw))==record['raw_result_hash'])
 fmt,norm=p.normalize(record,raw)
 check('frozen-witness-now-normalizes:'+obs['label'],fmt=='verislop.vscore3-checker.result-adapter/0.1')
 expected=copy.deepcopy(raw)
 for key in ('sequence','recorded_at'):expected.pop(key)
 check('frozen-entire-raw-preserved:'+obs['label'],norm['raw']==expected)
 outputs.append({'label':obs['label'],'original_normalizer':obs['normalizer']['accepted'],'repaired_normalizer':True,'format':fmt,'normalized':norm})
legacy=witness['observations'][0];tele=witness['observations'][1]
record=legacy['record'];base=legacy['raw'];process=tele['raw']['compile_process_evidence']
support={'descriptor':{'path':'frozen/support','recorded_at':'nested semantic metadata','sequence':17,'time':'must remain'},'artifacts':{'readable/source.lean':'sha256:'+'b'*64}}
variants=[{}, {'compile_process_evidence':process}, {'readable_support':support}, {'compile_process_evidence':process,'readable_support':support}]
base_fields=set(base)-p.WRAPPER
check('exact-four-.3-registered-alternatives',p.RESULT_FIELDS['verislop.vscore3-checker']==[base_fields|set(v) for v in variants])
check('exact-one-.1-legacy-alternative',p.RESULT_FIELDS['verislop.vscore-checker']==[base_fields])
for i,extra in enumerate(variants):
 raw={**base,**copy.deepcopy(extra)};fmt,norm=p.normalize(record,raw)
 expected={k:v for k,v in raw.items() if k not in {'sequence','recorded_at'}}
 check('variant-entire-payload-preserved:'+str(i),norm['raw']==expected)
 reject('variant-extra-top-key:'+str(i),record,{**raw,'unregistered_process_key':{'status':'PASS'}})
 for key in base:
  narrowed=copy.deepcopy(raw);del narrowed[key]
  reject('variant-missing-base-field:'+str(i)+':'+key,record,narrowed)
 old_record={**record,'verifier_id':'verislop.vscore-checker'}
 if not extra:
  _,old=p.normalize(old_record,raw);check('.1-legacy-still-normalizes',old['raw']==expected)
 else:reject('.1-extension-rejected:'+str(i),old_record,raw)
# Check exact complete build-output alternatives and preservation, including misleading nested names.
check('exact-build-output-alternatives',p.OUTPUT_ALTERNATIVES==[p.OUTPUT_FIELDS,p.OUTPUT_FIELDS|{'readable_support'}])
for i,extra in enumerate([{}, {'readable_support':support}]):
 out={name:None for name in p.OUTPUT_FIELDS};out.update(copy.deepcopy(extra))
 build={'build':'A','ok':True,'errors':[],'closure_root':'fixture-root','producer':{},'outputs':out,'execution':{'wall_ms':23}}
 metadata=[];norm=p._builds([build],metadata)[0]
 check('build-payload-preserved:'+str(i),norm=={k:v for k,v in build.items() if k!='execution'} and metadata==[{'source_path':'/raw/builds/0/execution/wall_ms','value':23}])
 for key in out:
  narrowed=copy.deepcopy(build);del narrowed['outputs'][key]
  try:p._builds([narrowed],[])
  except InvalidPackage:check('build-missing-field:'+str(i)+':'+key,True)
  else:
   # Removing the optional field is exactly the registered legacy alternative.
   check('build-missing-field:'+str(i)+':'+key,key=='readable_support')
 unknown=copy.deepcopy(build);unknown['outputs']['unregistered_field']=0
 try:p._builds([unknown],[])
 except InvalidPackage:check('build-unknown-output-rejected:'+str(i),True)
 else:check('build-unknown-output-rejected:'+str(i),False)
reg=p.normalizer_registry()
check('registry-publishes-exact-producer-alternatives',reg['formats']['verislop.vscore3-checker']['closed_alternatives']==[sorted(fields) for fields in p.RESULT_FIELDS['verislop.vscore3-checker']])
check('registry-publishes-exact-output-alternatives',reg['output_alternatives']==[sorted(fields) for fields in p.OUTPUT_ALTERNATIVES])
old_path=OUT.parent/'review-attempt-jccsmiil/runtime/verislop/review_projection.py'
import importlib.util
oldspec=importlib.util.spec_from_file_location('verislop._audit_original_projection',old_path)
old=importlib.util.module_from_spec(oldspec);oldspec.loader.exec_module(old)
check('all-original-exclusions-unchanged',p.EXCLUDED_PATHS==old.EXCLUDED_PATHS and p.WRAPPER==old.WRAPPER)
check('all-original-.1-producer-alternatives-unchanged',p.RESULT_FIELDS['verislop.vscore-checker']==old.RESULT_FIELDS['verislop.vscore-checker'])
check('other-producer-alternatives-unchanged',all(p.RESULT_FIELDS[k]==v for k,v in old.RESULT_FIELDS.items() if k!='verislop.vscore3-checker'))
check('normalizer-registry-hash-changed',reg['implementation_hash']!=old.normalizer_registry()['implementation_hash'])
# Confirm the repaired-only inputs remain exactly the captured bytes.
for row in json.loads((OUT/'capture.json').read_bytes())['repaired_files']:
 raw=(pathlib.Path('/home/augustus/VeriSlop_CLI')/row['path']).read_bytes()
 check('repaired-input-stability:'+row['path'],canonical.digest(raw)==row['sha256'])
(OUT/'replay.json').write_text(json.dumps({'scope':'Exact previously frozen generic counterexample replay; full raw and module/process payload retained; no current semantic acceptance claim.','replays':outputs},indent=2)+'\n')
(OUT/'checks.json').write_text(json.dumps({'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'count':len(checks),'pass':sum(x['pass'] for x in checks),'checks':checks},indent=2)+'\n')
print(json.dumps({'result':'PASS_BOUNDED_CORRECTED_NORMALIZER','pure_checks':len(checks),'original_defect_reproduced_prior':True,'original_new_telemetry_witness_now_passes':True},indent=2))
