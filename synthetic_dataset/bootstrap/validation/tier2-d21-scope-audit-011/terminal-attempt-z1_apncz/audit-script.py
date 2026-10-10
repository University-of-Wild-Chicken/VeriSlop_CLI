from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json, sys
sys.dont_write_bytecode=True
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-011'
PROJECT=STAGE/'project';RUN=STAGE/'run';PKG=RUN/'artifacts/D21/verislop/package';MB=PKG.parent/'mailbox'
OUT=Path(__file__).parent
AUDITS=ROOT/'synthetic_dataset/bootstrap/validation/tier2-d21-scope-audit-011'
EXPECTED_SOURCE='sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a'
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(x):return sha(canon(x))
def load(p):return json.loads(Path(p).read_bytes())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=True,sort_keys=True,indent=2)+'\n')
checks=[]
def check(name,c,details=None):
 checks.append({'name':name,'pass':bool(c),'details':details})
 if not c:raise AssertionError(name)
inputs={}
def capture(p):
 p=Path(p).absolute();check('regular non-symlink '+str(p),p.is_file() and not p.is_symlink())
 if p in inputs:return inputs[p]['data']
 b=p.read_bytes()
 if p.is_relative_to(RUN):rel=Path('cohort')/p.relative_to(RUN)
 elif p.is_relative_to(PROJECT):rel=Path('frozen-project')/p.relative_to(PROJECT)
 elif p.is_relative_to(AUDITS):rel=Path('prior-receipts')/p.relative_to(AUDITS)
 else:raise ValueError(str(p))
 q=OUT/'snapshots'/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 inputs[p]={'data':b,'snapshot':str(q.relative_to(OUT)),'sha256':sha(b)}
 return b

def evidence_inventory():
 excluded={'EVIDENCE-MANIFEST.json','BOOTSTRAP-EVIDENCE-MANIFEST.json'}
 return {p.relative_to(RUN).as_posix():sha(p.read_bytes()) for p in sorted(RUN.rglob('*'))
         if (p.is_file() or p.is_symlink()) and p.name not in excluded and '__pycache__' not in p.parts and not p.name.endswith(('.pyc','.lock'))}

seal1=load(RUN/'EVIDENCE-MANIFEST.json');seal2=load(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json')
check('two evidence seals byte equal',(RUN/'EVIDENCE-MANIFEST.json').read_bytes()==(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json').read_bytes())
check('sealed membership exact',seal1['files']==evidence_inventory())
check('sealed files root exact',seal1['files_root']==digest(seal1['files']))
check('sealed source root',seal1['source_root']==EXPECTED_SOURCE)
for name,want in seal1['files'].items():
 check('sealed file hash '+name,sha(capture(RUN/name))==want)
for name in ('EVIDENCE-MANIFEST.json','BOOTSTRAP-EVIDENCE-MANIFEST.json'):capture(RUN/name)
protocol=load(RUN/'protocol.json');prereg=load(RUN/'preregistration.json')
check('protocol source root exact',protocol['source_root']==digest(protocol['source_files'])==EXPECTED_SOURCE)
check('protocol input root exact',protocol['input_root']==digest(protocol['input_files']))
check('seal protocol binding',seal1['protocol_sha256']==sha(capture(RUN/'protocol.json')))
check('prereg source/protocol/input/request roots',all(prereg[k]==protocol[k] for k in('source_root','input_root','request_set_root')) and prereg['protocol_sha256']==sha(capture(RUN/'protocol.json')))
check('frozen project identity',protocol['project_path']==str(PROJECT))
for rel,want in protocol['source_files'].items():
 check('frozen project bytes '+rel,sha(capture(PROJECT/rel))==want)
 check('retained execution-source bytes '+rel,sha(capture(RUN/'execution-source'/rel))==want)
check('exact retained source inventory',{p.relative_to(RUN/'execution-source').as_posix() for p in (RUN/'execution-source').rglob('*') if p.is_file()}==set(protocol['source_files']))
for rel,want in protocol['input_files'].items():check('frozen input '+rel,sha(capture(RUN/rel))==want)
check('preregistered isolated roles and endpoint',protocol['fresh_agent_per_request'] is True and protocol['fork_turns']=='none' and protocol['endpoint']=='restricted_source' and protocol['require_state']=='END_TO_END_VERIFIED')
check('no positive-candidate arguments',protocol['positive_candidate_arguments']==[])
check('no registered oracle/runtime campaign',protocol['task_oracle_invoked'] is False and protocol['python_grader_invoked'] is False and protocol['runtime_campaign_requested'] is False and protocol['hidden_cases_loaded'] is False)

# Only frozen modules are imported; these operations inspect stored bytes and reconstruct data.
# No closure.run, bridge check/build, Lean tool, bootstrap.verify/native_audit, review.gate, or model call.
sys.path.insert(0,str(PROJECT))
from verislop import canonical, view, verifiers, schemas
from verislop.package import Package
from verislop.backends import vscore3_closure
check('auditor canonical hash agrees with registered serializer',digest(protocol['source_files'])==canonical.digest_json(protocol['source_files']))
for module in (view,verifiers,schemas,vscore3_closure):check('frozen imported module '+module.__name__,Path(module.__file__).is_relative_to(PROJECT))
pkg=Package(PKG)
derived=view.derive(pkg)
check('current frozen derived view equals stored view',derived==load(PKG/'obligation-view.json'))
check('derived evidence integrity clean',derived['evidence_integrity_problems']==[])
claims=vscore3_closure._claims(pkg)
dump(OUT/'registered-claim-graph.json',claims)
check('registered complete graph count',len(claims)==115)
check('registered required graph count',sum(c['required'] for c in claims)==94)
check('no current mechanical execution',vscore3_closure.mechanical_snapshot(pkg) is None)

result=load(PKG.parent/'result.json');aggregate=load(RUN/'BOOTSTRAP-RESULT.json');report=load(PKG/'report.json');stdout=load(PKG.parent/'stdout.json');worker=load(PKG.parent/'worker-result.json')
check('report schema valid',schemas.validate('run-report-v3',report)==[])
check('worker exit2',worker['exit_code']==result['worker_exit_code']==2)
check('native/result/report terminal BLOCKED',stdout['status']==stdout['summary']['terminal_status']==report['terminal_status']==result['native_terminal_status']==result['status']=='BLOCKED')
check('mechanical/release remain blocked',all(x=='BLOCKED' for x in (report['mechanical_status'],report['release_status'],result['mechanical_status'],result['release_status'],result['native']['mechanical_status'],result['native']['release_status'])))
check('no success projection',stdout['asserts_closure_verified'] is False and result['successful_task'] is False and result['strict_cli_success'] is False)
check('blocked issues empty is inspection consistency only',result['issues']==[] and result['native']['issues']==[] and result['native']['status']=='PASS')
check('report diagnostics exactly retained result',report['blocking_reasons']==result['cli_diagnostics'])
check('stdout diagnostics exactly report',stdout['diagnostics']==report['blocking_reasons'])
check('stage histories exact',stdout['summary']['stages']==result['cli_stages']==pkg.meta()['stage_history'])
check('stopped at failed bridge',stdout['summary']['stopped_at']==result['cli_stopped_at']=='bridge:accept' and result['cli_stages'][-1]['status']=='BLOCKED')
check('aggregate sealed blocked complete',aggregate['status']=='BLOCKED' and aggregate['complete'] is True and aggregate['verified_tasks']==0 and aggregate['selected_tasks']==1)
check('aggregate row exact',aggregate['rows']==[result])
check('aggregate source/protocol/request roots',aggregate['source_root']==EXPECTED_SOURCE and aggregate['protocol_sha256']==seal1['protocol_sha256'] and aggregate['request_set_root']==protocol['request_set_root'])
check('bootstrap completed marker',load(RUN/'active-arm.json')=={'phase':'bootstrap_complete'})
check('no task clean builds',report['builds']==result['native']['builds']==[] and report['determinism']==result['native']['determinism']=={'compared':[],'mismatches':[]})
check('no task closure root/result',report['closure_id'] is None and report['mechanical_result'] is None and report['roots']['closure_input_root'] is None and result['native']['closure_root'] is None and result['native']['mechanical_result'] is None)
for rel in ('semantic/edge-6c6b7f3cad1aebbacfb2127f/certificate.json','closure/plan.json','closure/current.json'):
 check('explicit terminal artifact absent '+rel,not (PKG/rel).exists())
check('no task semantic or closure execution files',not any((PKG/'semantic').glob('**/*')) and not (PKG/'closure/executions').exists())
check('release gate unavailable',report['review']=={'configured':True} and report['endpoint']['established'] is None)
review_certificates=[load(p) for p in (PKG/'reviews').glob('*/consensus-certificate.json')]
check('only formal review accepted',len(review_certificates)==1 and review_certificates[0]['checkpoint']=='formal_contract' and review_certificates[0]['final']=='REVIEW_ACCEPTED')
cc=review_certificates[0]
for tier in cc['tiers']:
 for row in tier['ballots']:check('formal ballot hash',sha(capture(PKG/row['ballot_ref']))==row['ballot_hash'])
check('formal review has no mechanical veto',cc['mechanical_veto']==[])

# Obligation scope is retained, not weakened because proof search failed.
ir=load(PKG/'accepted/accepted-ir.json');metadata=load(RUN/'requests/D21/original-metadata.json')
required_impl={'I1','O1','O2','O3','O4','O5','O6','O7','S1'}
check('all original eleven IDs preserved',set(x['id'] for x in metadata['identities'])==set(ir['obligations'])-{'A1_satisfiable'})
for identity in metadata['identities']:
 oid=identity['id'];check('original identity exact '+oid,all(ir['obligations'][oid][k]==identity[k] for k in('role','kind','required')))
check('all12 obligations required',len(ir['obligations'])==12 and all(x['required'] is True for x in ir['obligations'].values()))
for oid,row in report['obligations'].items():
 cur=derived['obligations'][oid]
 check('report identity exact '+oid,all(row[k]==cur[k] for k in('role','kind','revision','required')))
 check('report outcomes exact '+oid,row['outcomes']=={m:x['outcome'] for m,x in cur['lifecycle'].items()})
 if oid in required_impl:
  check('required E2E pending '+oid,row['outcomes']['END_TO_END_VERIFIED']=='PENDING' and row['outcomes']['TESTED']=='PENDING')
  check('structural source milestones pass '+oid,row['outcomes']['IMPLEMENTED']==row['outcomes']['LINKED']=='PASS')
check('nonvacuity contract PROVED only',report['obligations']['A1_satisfiable']['outcomes']['PROVED']=='PASS' and all(report['obligations']['A1_satisfiable']['outcomes'][m]=='NOT_APPLICABLE' for m in('IMPLEMENTED','LINKED','TESTED','END_TO_END_VERIFIED')))
check('required count projections exact',result['native']['required_obligations']==12 and result['native']['all_required_guarantees']==10 and result['native']['required_guarantees']==9 and result['native']['required_non_vacuity_witnesses']==1 and result['native']['required_e2e_passed']==0 and result['native']['all_required_e2e'] is False)
policy=load(RUN/'requests/D21/source-policy.json')
check('policy copied bytes exactly',capture(RUN/'requests/D21/source-policy.json')==capture(PKG/'request/source-policy.json'))
check('exact nine policy IDs',set(policy['obligations'])==required_impl)
for oid,row in policy['obligations'].items():
 check('source/value policy exact '+oid,row['entry']=='solve' and row['file']=='program.vscore.json' and row['arity']==1 and row['value_required']==(oid not in {'I1','S1'}) and set(row['properties'])=={'typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only'})
byid={c['claim_id']:c for c in claims}
for oid in required_impl:
 c=byid['END_TO_END_VERIFIED:'+oid+'@1']
 check('full required graph premise '+oid,c['required'] and c['applicable'] and {'BRIDGE:implementation:vscore-refinement','CLOSURE:clean-builds','CLOSURE:determinism','CLOSURE:endpoint','CLOSURE:provenance','IMPLEMENTED:'+oid+'@1','LINKED:'+oid+'@1','PROVED:'+oid+'@1'}<=set(c['premises']))
check('required NV claim in graph',byid['PROVED:A1_satisfiable@1']['required'])
for c in claims:
 check('all graph premises declared '+c['claim_id'],set(c['premises'])<=set(byid))

# Source2 was retained after source3 metadata failed. Refinement success is absent.
source2=PKG/'agents/vscore-attempts/source-2';source3=PKG/'agents/vscore-attempts/source-3'
mat=load(PKG/'implementation/materialization.json');selection=load(PKG/'closure/selection.json');prep=load(PKG/'bridges/implementation/preparation-certificate.json');bundle=PKG/'bridges/implementation'
check('materialized exact source2',capture(PKG/'implementation/program.vscore.json')==capture(source2/'program.vscore.json') and mat['source_hash']==sha(capture(source2/'program.vscore.json')))
check('materialized proof unchecked',mat['proof_checked'] is False)
check('source2 standalone source admission passed',load(source2/'checks/source.json')['passed'] is True and load(source2/'checks/source.json')['proof_checked'] is False)
for i in(1,2,3):
 x=load(source2/f'checks/proof-{i}.json');check('source2 proof failed '+str(i),x['passed'] is False and x['proof_checked'] is True and x['source_hash']==mat['source_hash'] and x['diagnostics'][0]['code']=='CANDIDATE_BUILD_FAILURE')
check('final proof exact last failed proof',capture(bundle/'candidate-inputs/Proof.lean')==capture(source2/'proofs/3.lean'))
check('final bridge failure exact retained proof3 message',report['blocking_reasons'][0]['message']==load(source2/'checks/proof-3.json')['diagnostics'][0]['message'])
check('prepared bridge structural only',prep['structural_acceptance'] is True and prep['semantic_acceptance'] is False and prep['assigns_end_to_end_verified'] is False and prep['pending_semantic_claims']==['BRIDGE:implementation:vscore-refinement'])
check('preparation registered checker exact',prep['checker']['verifier_hash']==verifiers.verifier_hash(prep['checker']['verifier_id']))
check('all nine selected bridge obligations',{r['id'] for r in selection['covered']}==required_impl)
for name,row in selection['inputs'].items():check('selected input exact '+name,sha(capture(PKG/row['path']))==row['sha256'])
artifacts=load(bundle/'artifacts.json')
for row in artifacts['artifacts']:
 b=capture(bundle/row['path']);check('prepared artifact exact '+row['slot_id'],sha(b)==row['sha256'] and len(b)==row['size'])
s3=load(source3/'checks/source.json')
check('source3 remains rejected',s3['passed'] is False and s3['proof_checked'] is False and s3['diagnostics'][0]['code']=='INVALID_CANDIDATE' and s3['diagnostics'][0]['message']=='relation slots must be vscore-source and vscore-proof for this helper')
check('source3 never silently replaced source2',mat['source_hash']!=s3['source_hash'])

# Authenticate both top-level and preparation evidence envelopes against frozen registry.
envelopes=[]
for q in sorted(PKG.glob('**/evidence/ev-*.json')):
 e=load(q);base=q.parent.parent;rawpath=base/e['raw_result_ref'];raw=load(rawpath)
 check('evidence schema '+str(q.relative_to(PKG)),schemas.validate('evidence',e)==[])
 check('raw evidence hash '+e['evidence_id'],sha(capture(rawpath))==e['raw_result_hash'])
 check('registered verifier hash '+e['evidence_id'],e['verifier_hash']==verifiers.verifier_hash(e['verifier_id']))
 check('evidence status honest '+e['evidence_id'],e['status']=='PASS' and e['exit_code']==0)
 if e['claim_id'].startswith('LINKED:'):
  check('linked explicitly structural '+e['claim_id'],raw['correspondence']=='structural' and raw['structural_linked'] is True and raw['semantic_acceptance'] is False)
 if e['claim_id'].startswith('IMPLEMENTED:'):
  check('implemented explicitly unproved '+e['claim_id'],raw['proof_checked'] is False and raw['source_hash']==mat['source_hash'])
 envelopes.append({'path':str(q.relative_to(PKG)),'claim_id':e['claim_id'],'status':e['status'],'verifier':e['verifier_id'],'root':e['input_root_hash']})
check('no semantic or final milestone PASS envelope',not any(e['claim_id'].startswith(('END_TO_END_VERIFIED:','BRIDGE:implementation:vscore-refinement','CLOSURE:')) for e in envelopes))
dump(OUT/'evidence-summary.json',envelopes)

# All17 independently instantiated model-role origins bind exact frozen request/carrier bytes.
origins=[]
for i in range(1,18):
 ident=f'{i:04d}';req=load(MB/f'request-{ident}.json');car=load(MB/f'carrier-{ident}.json');binding=load(MB/f'carrier-binding-{ident}.json');resp=load(MB/f'response-{ident}.json');rec=load(MB/f'response-receipt-{ident}.json')
 rh=sha(capture(MB/f'request-{ident}.json'));ch=sha(capture(MB/f'carrier-{ident}.json'));replyhash=sha(capture(MB/f'response-{ident}.json'))
 check('origin'+ident+'.request/carrier digest',car['request_sha256']==binding['request_sha256']==resp['request_sha256']==rec['request_sha256']==rh and binding['carrier_sha256']==resp['carrier_sha256']==ch)
 check('origin'+ident+'.context exact',(car['system'],car['user'])==(req['system'],req['user']))
 check('origin'+ident+'.response receipt exact',rec['response_sha256']==replyhash and rec['text_sha256']==sha(resp['text'].encode()) and rec['output_bytes']==len(resp['text'].encode()))
 check('origin'+ident+'.fresh child',resp['agent_task_id']==f'/root/native_dispatch_011/native_tier2_d21_{ident}' and resp['fork_turns']=='none' and resp['relay_mode']=='file')
 check('origin'+ident+'.frozen roots',resp['source_root']==EXPECTED_SOURCE and resp['request_set_root']==protocol['request_set_root'] and resp['supplemental_protocol_root']==seal1['protocol_sha256'])
 check('origin'+ident+'.model honesty',req['requested_model']==resp['requested_model']==resp['model_override']=='gpt-6.1-sol' and rec['model_identity_attested'] is False and rec['returned_model'] is None)
 origins.append({'request_id':ident,'agent_task_id':resp['agent_task_id'],'purpose':req['purpose'],'agent':req['agent'],'instance':req['instance'],'request_hash':rh,'carrier_hash':ch,'response_hash':replyhash,'fork_turns':resp['fork_turns']})
check('all17 origin identities unique',len({o['agent_task_id'] for o in origins})==17)
check('retained exact origin identities',result['origin_audit']['agents']==[o['agent_task_id'] for o in origins])
transcripts=list(PKG.glob('**/transcripts/*.json'))
check('exact17 completed native transcript records',len(transcripts)==17)
seen=set()
for p in transcripts:
 x=load(p);native_child=x['request_id'];ident=native_child.rsplit('_',1)[-1];req=load(MB/f'request-{ident}.json');resp=load(MB/f'response-{ident}.json')
 check('transcript'+ident+'.canonical child identity',native_child==resp['agent_task_id'])
 check('transcript'+ident+'.unique',ident not in seen);seen.add(ident)
 check('transcript'+ident+'.exact native context/role',all(x[k]==req[k] for k in('system','user','purpose','agent','instance')))
 check('transcript'+ident+'.response exact',x['response']==resp['text'])
 check('transcript'+ident+'.context hashes',x['system_sha256']==sha(x['system'].encode()) and x['user_sha256']==sha(x['user'].encode()))
 check('transcript'+ident+'.model honesty',x['requested_model']=='gpt-6.1-sol' and x['returned_model'] is None and x.get('model_digest_sha256') is None and x.get('input_tokens') is None and x.get('output_tokens') is None)
check('all17 transcripts accounted',seen=={o['request_id'] for o in origins})
check('zero transport errors',not list(MB.glob('transport-error-receipt-*.json')) and result['origin_audit']['transport_errors']==aggregate['transport_errors']==0)
check('usage count exact17',result['usage']['calls']==result['usage']['responses']==aggregate['fresh_calls']==aggregate['fresh_agents']==17)
dump(OUT/'origin-summary.json',origins)

# Prior observations are immutable context, never a substitute for a successful task bridge.
prior=[]
for name in ('frozen-attempt-w3ulmxn3','accepted-attempt-vnoe1tk0','source-proposal-attempt-u3ye3yon','proof-diagnosis-attempt-jea3k0_f'):
 p=AUDITS/name;capture(p/'audit.json');mp=p/('manifest.json' if (p/'manifest.json').exists() else 'snapshot-manifest.json');manifest=load(mp);capture(mp)
 prior.append({'path':str(p/'audit.json'),'sha256':sha(capture(p/'audit.json'))})
 for row in manifest.get('files',manifest.get('entries',[])):
  original=Path(row.get('source') or row.get('path'))
  if original.is_relative_to(PKG/'accepted') or original.is_relative_to(PKG/'contract/challenge'):
   check('unchanged accepted/frozen observation '+str(original),sha(capture(original))==row['sha256'])
engineering=load(RUN/'engineering-validation.json')
check('attached engineering fixture separate',engineering['fixture_only'] is True and engineering['fresh_model_calls']==0)
engineering_builds={'count':len(engineering['builds']),'ok':[x['ok'] for x in engineering['builds']],'closure_root':engineering['closure_root'],'scope':'preregistered unrelated engineering fixture; not D21 proof or build evidence'}
# Hash all observed inputs again, including sealed inventory, after pure inspection.
for p,row in inputs.items():check('audited input stable '+str(p),p.read_bytes()==row['data'])
check('evidence seal still exact',evidence_inventory()==seal1['files'])
manifest={'format':'verislop.independent-read-only-input-snapshot/0.1','files':[{'source':str(p),'snapshot':row['snapshot'],'sha256':row['sha256'],'bytes':len(row['data'])} for p,row in sorted(inputs.items(),key=lambda x:str(x[0]))]}
dump(OUT/'manifest.json',manifest);dump(OUT/'pure-checks.json',checks)
audit={'format':'verislop.independent-blocked-terminal-audit/0.1','observed_at_utc':datetime.now(timezone.utc).isoformat(),'task':'D21','stage':'tier2-source-facets-011','source_root':EXPECTED_SOURCE,'protocol_hash':seal1['protocol_sha256'],'cohort_evidence_root':seal1['files_root'],'terminal_status':'BLOCKED','worker_exit_code':2,'proof_status':'all3 source2 candidate bridge proofs failed; no accepted semantic certificate','required_obligations':12,'required_implementation_guarantees':9,'required_implementation_e2e_passed':0,'required_nonvacuity_witnesses':1,'required_nonvacuity_status':'PROVED PASS; implementation milestones NOT_APPLICABLE','registered_graph_claims':len(claims),'registered_graph_required':sum(c['required'] for c in claims),'evidence_envelopes_inspected':len(envelopes),'native_fresh_roles':len(origins),'native_vendor_model_identity_attested':False,'task_builds':[],'task_determinism':report['determinism'],'task_closure_plan':None,'task_current_execution':None,'formal_review':'REVIEW_ACCEPTED','release_review':'ABSENT; release_status BLOCKED','engineering_fixture_builds':engineering_builds,'findings':[{'id':'T1','status':'honest blocked outcome','evidence':'CLI, worker exit2, report, task result, aggregate and sealed row agree. Native inspection status PASS denotes consistency of blocked observations; all successful_task/strict_cli_success/asserts_closure_verified flags false.'},{'id':'T2','status':'structural linkage does not promote semantics','evidence':'Every LINKED raw result says correspondence structural and semantic_acceptance false. Materialized current source2 proof_checked false; preparation semantic_acceptance false and assigns_end_to_end_verified false. All9 applicable implementation guarantees remain END_TO_END_VERIFIED PENDING.'},{'id':'T3','status':'full requirements retained','evidence':'All original11 required identities and derived required A1_satisfiable remain. Source policy has exactly9 requirements, only I1/S1 value_required false. Each required E2E claim retains the failed semantic bridge, per-ID implementation/link/proof and all clean-build/determinism/endpoint/provenance premises. Frozen/accepted observation bytes remain unchanged from independently retained current-stage scope audits.'},{'id':'T4','status':'missing later evidence explicitly bounded','evidence':'No semantic certificate, closure plan/current execution, D21 build records or release campaign. Generic engineering fixture builds are separately scoped and not used to discharge D21.'},{'id':'T5','status':'source3 rejected rather than silently admitted','evidence':'Third source has INVALID_CANDIDATE incorrect relation slots; current materialization and selected proof remain exactsource2 and failed proof3. Failure diagnostics preserved; no source3 proof/admission success.'},{'id':'T6','status':'exact current-stage origin receipts authenticated','evidence':'17 unique canonical child identities, fork_turns none, exact requests/carriers/bindings/responses/receipts and17 actual native transcripts hash-match frozen roots. Report honestly says vendor/model identity unattested. No transport errors.'}], 'blocking_reasons':report['blocking_reasons'],'conclusion':'Bounded independent read-only audit found no counterfeit semantic success or requirement downgrade in the sealed blocked run. D21 restricted_source assurance is not established; accepted reference contract proofs and constructive non-vacuity do not certify the materialized implementation.','limitations':['No Lean/kernel/native closure/gate/provider/model execution. Only frozen-project data/schema/hash/view/claim reconstruction routines used; root independently owns normal frozen verification.','Natural-language correspondence remains trusted; current-stage frozen and accepted mathematical-scope receipts are unchanged context, not new proof authority.','Prior proof-search diagnosis is engineering explanation only; retained compiler diagnostics are bounded to first3 errors. No inference that a revised tactic or third source would prove refinement.','Evidence byte integrity and recorded fresh child identity do not attest the external provider model identity, machine-code/runtime semantics or physical resources.','No historical task source, hidden cases or oracles used, no model-role communication, and no modifications to source/package/cohort/seals.'],'prior_receipts':prior,'checks':len(checks),'input_files':len(inputs),'manifest_hash':sha((OUT/'manifest.json').read_bytes()),'script_hash':sha(Path(__file__).read_bytes()),'skill':{'name':'mechanical-closure-verification','path':'/home/augustus/.codex/skills/mechanical-closure-verification/SKILL.md','mode':'read-only audit; no new closure authority'}}
dump(OUT/'audit.json',audit)
dump(OUT/'receipt.json',{'audit_hash':sha((OUT/'audit.json').read_bytes()),'manifest_hash':audit['manifest_hash'],'checks_hash':sha((OUT/'pure-checks.json').read_bytes()),'script_hash':audit['script_hash'],'checks':len(checks),'input_files':len(inputs),'all_checks_passed':True,'bounded_terminal':'BLOCKED'})
print(json.dumps({'receipt':str(OUT),'audit_hash':sha((OUT/'audit.json').read_bytes()),'checks':len(checks),'input_files':len(inputs),'terminal':'BLOCKED','claim_graph':len(claims),'required_claims':sum(c['required'] for c in claims),'roles':len(origins)},sort_keys=True))
