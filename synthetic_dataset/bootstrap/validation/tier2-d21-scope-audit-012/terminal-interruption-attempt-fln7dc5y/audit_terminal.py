#!/usr/bin/env python3
"""Authenticate the sealed interrupted Stage012 record without execution/replay."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
ROOT=Path('/home/augustus/VeriSlop_CLI');STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-012';RUN=STAGE/'run';PROJECT=STAGE/'project';PKG=RUN/'artifacts/D21/verislop/package';OUT=Path(__file__).resolve().parent
checks={};snaps={};observed={}
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def dumps(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def check(k,b,d=None):
 checks[k]={'ok':bool(b)}
 if d is not None:checks[k]['detail']=d
def snap(p,label):
 p=Path(p);check('regular:'+label,p.is_file() and not p.is_symlink());b=p.read_bytes();q=OUT/'snapshots'/label;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);snaps[label]={'source':str(p),'sha256':digest(b),'bytes':len(b)};observed[str(p)]=digest(b);return b
def js(p,label):return json.loads(snap(p,label))
seal=js(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json','run/BOOTSTRAP-EVIDENCE-MANIFEST.json');alias=js(RUN/'EVIDENCE-MANIFEST.json','run/EVIDENCE-MANIFEST.json')
check('exact_602_member_root',len(seal['files'])==602 and seal['files_root']==digest(dumps(seal['files']))=='sha256:c55f89c64965b4bc6756da8f26401a92486f765b9f34dcb9496f44b6b7a8bf58' and alias==seal)
for name,sha in seal['files'].items():check('sealed_member:'+name,digest(snap(RUN/name,'run/'+name))==sha)
actual={str(f.relative_to(RUN)) for f in RUN.rglob('*') if f.is_file()};check('closed_file_inventory',actual-set(seal['files'])=={'BOOTSTRAP-EVIDENCE-MANIFEST.json','EVIDENCE-MANIFEST.json'})
protocol=json.loads((RUN/'protocol.json').read_bytes());result=json.loads((RUN/'BOOTSTRAP-RESULT.json').read_bytes());row=json.loads((RUN/'artifacts/D21/verislop/result.json').read_bytes());worker=json.loads((RUN/'artifacts/D21/verislop/worker-result.json').read_bytes())
check('exact_source_and_protocol_binding',seal['protocol_sha256']==result['protocol_sha256']==digest((RUN/'protocol.json').read_bytes()) and seal['source_root']==result['source_root']==protocol['source_root']=='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710')
for name,sha in protocol['source_files'].items():check('frozen_project:'+name,digest(snap(PROJECT/name,'project/'+name))==sha and (RUN/'execution-source'/name).read_bytes()==(PROJECT/name).read_bytes())
check('honest_infrastructure_terminal',result['complete'] is True and result['status']==row['status']=='INFRASTRUCTURE_FAILURE' and result['verified_tasks']==0 and row['successful_task'] is False and row['strict_cli_success'] is False and row['native_terminal_status'] is None)
check('exact_row_projection',result['rows']==[row])
check('interruption_not_restart_or_task_failure',worker['status']=='CONTROLLER_INTERRUPTED' and worker['exit_code'] is None and row['worker_receipt']==worker and worker['reason']=='A partial task is never silently restarted' and row['startup_failure'] is False)
check('no_terminal_native_report',not (PKG/'pipeline').exists() and not (PKG/'terminal').exists() and row['native']['issues']==['Native terminal report is absent'] and row['native']['builds']==[] and row['native']['closure_root'] is None and row['native']['mechanical_result'] is None)
check('empty_stdout_explained', (RUN/'artifacts/D21/verislop/stdout.json').stat().st_size==0 and row['cli_status'] is None and row['cli_stages']==[])
check('no_implementation_link_or_semantic_acceptance',all(not (PKG/n).exists() for n in ['implementation','bridges','semantic']) and not (PKG/'closure/current.json').exists() and not (PKG/'closure/manifest.json').exists())
events=[json.loads(l) for l in (PKG/'events.jsonl').read_text().splitlines()];check('events_end_submitted_proof',events[-1]['type']=='candidate_proposal' and events[-1]['phase']=='generate' and events[-1]['message']=='VSCore proof proposal (source 1, proof 1)')
check('no_counterfeit_linked_e2e_events',not any(e.get('milestone') in {'LINKED','END_TO_END_VERIFIED'} or e.get('checkpoint') in {'LINKED','END_TO_END_VERIFIED'} for e in events))
cert=json.loads((PKG/'accepted/acceptance.json').read_bytes());ir=json.loads((PKG/'accepted/accepted-ir.json').read_bytes());check('accepted_contract_survives_interruption',cert['gate']=='accepted_and_proved' and cert['diagnostics']==[] and len(ir['obligations'])==12)
required={k for k,r in ir['obligations'].items() if r['required'] and r['role']=='guarantee'};check('guarantees_and_witness_not_erased',required=={'I1','S1','O1','O2','O3','O4','O5','O6','O7','A1_nonvacuity'} and all(cert['obligations'][k]['proved']=='PASS' for k in required))
evidence={}
for p in (PKG/'evidence').glob('*.json'):
 e=json.loads(p.read_bytes());evidence[e['evidence_id']]=e
 raw=PKG/e['raw_result_ref'];check('evidence_raw:'+e['evidence_id'],digest(raw.read_bytes())==e['raw_result_hash'])
check('no_registered_implementation_evidence',not any(e['claim_id'].startswith(('LINKED:','END_TO_END_VERIFIED:','BRIDGE:','IMPLEMENTATION:')) for e in evidence.values()))
source=PKG/'agents/vscore-attempts/source-1';preview=json.loads((source/'checks/source.json').read_bytes());check('source_preview_only',preview['passed'] and not preview['proof_checked'] and not (source/'checks/proof-1.json').exists())
mb=RUN/'artifacts/D21/verislop/mailbox';agents=[]
for i in range(1,11):
 id=f'{i:04d}';req=json.loads((mb/f'request-{id}.json').read_bytes());res=json.loads((mb/f'response-{id}.json').read_bytes());bind=json.loads((mb/f'carrier-binding-{id}.json').read_bytes());carrier=mb/f'carrier-{id}.json';agents.append(res['agent_task_id'])
 check('fresh_transport:'+id,res['fork_turns']=='none' and res['transport']=='collaboration' and res['relay_mode']=='file' and res['requested_model']=='gpt-6.1-sol' and res['model_override']=='gpt-6.1-sol' and res['model_identity_attested'] is False)
 check('carrier_binding:'+id,res['carrier_sha256']==bind['carrier_sha256']==digest(carrier.read_bytes()) and res['request_sha256']==bind['request_sha256']==digest((mb/f'request-{id}.json').read_bytes()) and res['request_id']==bind['request_id']==req['request_id']==id)
 check('origin_roots:'+id,res['source_root']==protocol['source_root'] and res['request_set_root']==protocol['request_set_root'] and res['supplemental_protocol_root']==digest((RUN/'protocol.json').read_bytes()))
check('ten_unique_fresh_roles',len(set(agents))==10 and agents==row['origin_audit']['agents'] and result['fresh_agents']==result['fresh_calls']==row['origin_audit']['provider_calls']==row['origin_audit']['responses']==10 and result['transport_errors']==0 and row['origin_audit']['transport_errors']==0 and row['origin_audit']['status']=='PASS')
last=json.loads((mb/'response-0010.json').read_bytes());prooftext=(source/'responses/proof-1.txt').read_text();check('last_submitted_response_exact',last['text']==prooftext and len(prooftext.encode())==6042)
check('no_hidden_oracle_or_old_assurance_upgrade',result['hidden_cases_loaded'] is False and result['oracle_calls']==0 and result['original_python_assurance_relabelled'] is False and row['python_runtime_campaign'] is False)
verified=js(ROOT/'validation/tier2-native-boundary-gate-012/interrupted-seal-verification.json','external-normal-seal-verification.json');check('stored_normal_verification_agrees',verified['status']=='PASS' and verified['milestone_authority'] is False and verified['source_root']==protocol['source_root'] and verified['protocol_sha256']==digest((RUN/'protocol.json').read_bytes()) and verified['rows']==[row])
for p,sha in observed.items():check('unchanged:'+p,digest(Path(p).read_bytes())==sha)
failed=[k for k,v in checks.items() if not v['ok']]
result={'format':'independent-bounded-audit/0.1','phase':'sealed-interrupted-terminal','stage':'012','task':'D21','time':datetime.now(timezone.utc).isoformat(),'source_root':protocol['source_root'],'sealed_files_root':seal['files_root'],'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failed else 'AUDIT_ASSERTION_FAILURE','checks':len(checks),'failed_checks':failed,'snapshots':len(snaps),'actual_terminal':'INFRASTRUCTURE_FAILURE','source_bridge':'SUBMITTED_NOT_ACCEPTED','implementation_refinement':'UNVERIFIED','closure_builds':'ABSENT','observations':['Exact 602-member seal and all retained transport/input/source/evidence hashes authenticated.','Accepted contract and all ten required guarantee proofs remain retained, including non-vacuity.','No accepted implementation, bridge certificate, LINKED/E2E evidence, closure/current execution or terminal native report exists.','Controller interruption and empty stdout are recorded without a restart or success upgrade.','Stored external frozen verification PASS authenticates the interruption record and is not a task-success milestone.'],'limits':['Pure read-only file/hash inspection only.','No native/kernel/model/mechanical replay executed.','No candidate proof validated or source function executed.','Natural-language mathematical correspondence remains an explicit trusted audit boundary.']}
(OUT/'checks.json').write_bytes(dumps(checks));(OUT/'snapshot-manifest.json').write_bytes(dumps(snaps));(OUT/'audit.json').write_bytes(dumps(result));print(json.dumps(result,indent=2));assert not failed,failed
