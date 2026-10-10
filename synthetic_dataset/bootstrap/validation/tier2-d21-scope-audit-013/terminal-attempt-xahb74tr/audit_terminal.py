#!/usr/bin/env python3
"""Independent pure, bounded audit of the exact sealed blocked Stage013 D21 run."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from unittest.mock import patch
import json, hashlib, subprocess

ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-013'
RUN=STAGE/'run'; PROJECT=STAGE/'project'; PKG=RUN/'artifacts/D21/verislop/package'
GATE=ROOT/'validation/tier2-native-boundary-gate-013'
OUT=Path(__file__).resolve().parent
SOURCE_ROOT='sha256:6cbf6ea1ccae9839c90d3087edb522434c5f5ff0532b817c8a67d0889fa39710'
SEAL_ROOT='sha256:ef4323ffd068445ad2b025c2e95f76fbdc57ac6a9bbd925db0e9fde37fb324f7'
checks={}; snapshots={}; observed={}
def h(b): return 'sha256:'+hashlib.sha256(b).hexdigest()
def d(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def check(k,b,detail=None):
    checks[k]={'ok':bool(b)}
    if detail is not None: checks[k]['detail']=detail
def capture(path,label):
    path=Path(path);check('regular:'+label,path.is_file() and not path.is_symlink())
    data=path.read_bytes(); dest=OUT/'snapshots'/label;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    snapshots[label]={'source':str(path),'sha256':h(data),'bytes':len(data)};observed[str(path)]=h(data);return data
def js(path,label): return json.loads(capture(path,label))
def forbidden(*args,**kwargs): raise AssertionError('Native/build/kernel/model/process execution forbidden in this audit')

seal=js(RUN/'EVIDENCE-MANIFEST.json','EVIDENCE-MANIFEST.json')
other_seal=js(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json','BOOTSTRAP-EVIDENCE-MANIFEST.json')
check('identical_exact_terminal_seals',seal==other_seal and len(seal['files'])==846 and seal['files_root']==h(d(seal['files']))==SEAL_ROOT)
inventory={}
for path in sorted(RUN.rglob('*')):
    if (path.is_file() or path.is_symlink()) and path.name not in {'EVIDENCE-MANIFEST.json','BOOTSTRAP-EVIDENCE-MANIFEST.json'} and '__pycache__' not in path.parts and not path.name.endswith(('.pyc','.lock')):
        rel=str(path.relative_to(RUN));inventory[rel]=h(capture(path,'sealed-run/'+rel))
        check('sealed-file:'+rel,seal['files'].get(rel)==inventory[rel])
check('complete_normative_sealed_inventory',inventory==seal['files'])
protocol=json.loads((RUN/'protocol.json').read_bytes()); prereg=json.loads((RUN/'preregistration.json').read_bytes())
check('protocol_prereg_seal_exact_binding',seal['source_root']==prereg['source_root']==protocol['source_root']==SOURCE_ROOT and prereg['protocol_sha256']==seal['protocol_sha256']==h((RUN/'protocol.json').read_bytes()) and h(d(protocol['source_files']))==SOURCE_ROOT)
for name,digest in protocol['source_files'].items():
    check('frozen-project:'+name,h(capture(PROJECT/name,'frozen-project/'+name))==digest and inventory['execution-source/'+name]==digest)
for name,digest in protocol['input_files'].items():check('frozen-input:'+name,inventory[name]==digest)
check('input_and_request_roots',h(d(protocol['input_files']))==protocol['input_root'] and h(d({t['id']:t['revised_request_sha256'] for t in protocol['tasks']}))==protocol['request_set_root'])
check('bootstrap_complete',json.loads((RUN/'active-arm.json').read_bytes())=={'phase':'bootstrap_complete'})

# External observations are bound read-only snapshots, never milestone authority.
for name in ['terminal-seal-verification.json','driver-result.json','driver-invocation.json','launch.json','recovery-plan.json','driver.stdout.log','driver.stderr.log','supervisor.stdout.log','supervisor.stderr.log','dispatch/infrastructure-0019.json','dispatch/recovery-0019.json']:
    capture(GATE/name,'external/'+name)
external_verify=json.loads((GATE/'terminal-seal-verification.json').read_bytes())
check('root_normal_frozen_verify_receipt',h((GATE/'terminal-seal-verification.json').read_bytes())=='sha256:516eb3fbdba80737480404d2d231aff4985f5fff63fa5ad6c2f149d16f1287c9' and external_verify['status']=='PASS' and external_verify['milestone_authority'] is False and external_verify['source_root']==SOURCE_ROOT)
driver_result=json.loads((GATE/'driver-result.json').read_bytes())
check('driver_exit_and_retained_streams',driver_result['returncode']==2 and driver_result['stdout_sha256']==h((GATE/'driver.stdout.log').read_bytes()) and driver_result['stderr_sha256']==h((GATE/'driver.stderr.log').read_bytes()))

sys.path.insert(0,str(PROJECT))
from verislop import canonical, leanbridge, export, view, report as report_module, schemas, lifecycle, source_policy, contract as C
from verislop.package import Package
from verislop.errors import Diagnostic
from verislop.evidence import EvidenceStore
from verislop.claimcheck import evaluate_claim
from verislop.backends import vscore3, vscore3_closure as CL
from verislop.bridges import vscore3_checker as checker
from synthetic_dataset.tools import bootstrap_tier2 as B

with patch.object(leanbridge,'run_kernel_tool',side_effect=forbidden),patch.object(leanbridge,'compile_module',side_effect=forbidden),patch.object(checker,'run_build',side_effect=forbidden),patch.object(subprocess,'run',side_effect=forbidden),patch.object(subprocess,'Popen',side_effect=forbidden):
    pkg=Package(PKG)
    check('pure_preregistered_inputs_validator',B.verify_inputs(RUN)==protocol)
    ir=json.loads((PKG/'accepted/accepted-ir.json').read_bytes());cert=json.loads((PKG/'accepted/acceptance.json').read_bytes())
    vi,ih,vc,vd=export.verified_ir(pkg)
    check('pure_certified_IR_reader',not vd and vi==ir and vc==cert and ih==h((PKG/'accepted/accepted-ir.json').read_bytes()),[x.to_json() for x in vd])
    check('same_accepted_contract_identity',ih=='sha256:6fb479b4861dc7ff78a04283e773858da28e088bc75649f5dd1e47dfe90377eb' and h((PKG/'accepted/acceptance.json').read_bytes())=='sha256:e6c4e0293206ceba145bae9a138adaffa61841bbda3405249cf3dc1c0f6a91cb' and cert['gate']=='accepted_and_proved' and not cert['diagnostics'])
    for key,obj in cert['artifacts'].items():check('accepted_artifact:'+key,h((PKG/obj['path']).read_bytes())==obj['sha256'])
    metadata=json.loads((RUN/protocol['tasks'][0]['metadata_path']).read_bytes())
    ids={r['id']:{k:r[k] for k in ['role','kind','required']} for r in metadata['identities']}
    check('all_eleven_original_identities',set(ids)=={'D1','A1','I1','S1',*['O'+str(i) for i in range(1,8)]} and all({k:ir['obligations'][oid][k] for k in ['role','kind','required']}==row for oid,row in ids.items()) and len(ir['obligations'])==12)
    check('original_python_history_excluded',metadata['old_positive_candidate_bytes_read'] is False and protocol['positive_candidate_arguments']==[] and protocol['runtime_campaign_requested'] is False)
    check('required_source_policy_exact',not source_policy.check_ir(pkg,ir,list(ir['obligations'].values())) and (PKG/'request/source-policy.json').read_bytes()==(RUN/protocol['tasks'][0]['source_policy_path']).read_bytes() and (PKG/'bridges/implementation/request/source-policy.json').read_bytes()==(PKG/'request/source-policy.json').read_bytes())
    policy=json.loads((PKG/'request/source-policy.json').read_bytes()); guarantee_ids=sorted(policy['obligations'])
    check('nine_source_policy_guarantees',guarantee_ids==['I1','O1','O2','O3','O4','O5','O6','O7','S1'] and all(row['value_required']==(oid not in {'I1','S1'}) for oid,row in policy['obligations'].items()))
    env_export=json.loads((PKG/cert['artifacts']['environment_export']['path']).read_bytes());env,ed=C.Env.from_export(env_export)
    check('pure_exported_environment_validation',env is not None and not ed and env_export['replay']['ok'] is True,[x.to_json() for x in ed])
    constants={'.'.join(x['name']):x for x in env_export['constants']}
    for oid,row in cert['obligations'].items():
        check('certificate_identity:'+oid,row['statement_hash']==ir['obligations'][oid]['formal']['statement_hash'] and row['typechecked']=='PASS' and not row['codes'])
        if row['role']=='guarantee':
            co=constants[row['lean_symbol']]
            check('guarantee_proof_audit:'+oid,row['proved']=='PASS' and {'.'.join(x) for x in co['axioms']}==set(row['axioms']) and set(row['axioms']).issubset(cert['policy']['allowed_axioms']) and co['safety']=='safe' and not co['unresolved_constants'])
    witness=cert['obligations']['valid_domain_witness']
    expected_witness=[[{'tuple':['record','Input',{'tuple':[{'tuple':[]},{'int':'0'},{'int':'0'},{'int':'1'},'none']}]}]]
    check('constructive_full_domain_witness',witness['kind']=='non_vacuity' and witness['axioms']==[] and witness['witnesses']==expected_witness and env_export['witnesses'][0]['ok'] is True)
    accepted_source=(PKG/cert['artifacts']['source']['path']).read_text()
    import re
    check('accepted_source_zero_holes',not re.search(r'\b(sorry|admit|axiom|native_decide)\b',accepted_source))
    # Previous current-cohort scope receipts are authenticated and exact artifact identities remain unchanged.
    prior_phases={
      'accepted':'accepted-attempt-6xbthvkm',
      'source1':'source-pending-attempt-uqq1_jis',
      'source2':'source2-pending-attempt-o5dypwdf',
      'source3':'source3-pending-attempt-tfughg1z'}
    for phase,dirname in prior_phases.items():
        pp=OUT.parent/dirname;pa=js(pp/'audit.json','prior-audits/'+phase+'/audit.json');pm=js(pp/'RECEIPT-MANIFEST.json','prior-audits/'+phase+'/RECEIPT-MANIFEST.json')
        check('prior_receipt_metadata:'+phase,pm['files']['audit.json']==h((pp/'audit.json').read_bytes()) and pm['files_root']==h(d(pm['files'])) and pa['source_root']==SOURCE_ROOT and pa['outcome']=='NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' and not pa['failed_checks'])
        for rel,digest in pm['files'].items():check('prior_receipt_sealed:'+phase+'/'+rel,h((pp/rel).read_bytes())==digest)
        if phase.startswith('source'):
            number=phase[-1];check('same_scope_audited_source:'+phase,pa['accepted_IR_hash']==ih and pa['source_hash']==h((PKG/f'agents/vscore-attempts/source-{number}/program.vscore.json').read_bytes()) and pa['goal_hash']==h((PKG/f'agents/vscore-attempts/source-{number}/VeriSlopBridgeGoal.lean').read_bytes()))
    (OUT/'scope-continuity.json').write_bytes(d({'meaning':'Prior independent current-cohort natural-language/AST and symbolic-source audits remain bounded NL correspondence judgments, not Lean implementation proofs. Terminal checks authenticate unchanged exact bytes and certified artifacts.','original_scope':'All groups including out-of-range; Unicode scalar sorting; half-open clipped buckets for signed endpoints; null exclusion; occurrence duplicates; signed sums; zero updates previous; empty carries without reset; no prestart seed; exact group-then-bucket rows; width>0,start<=end,fill none|previous; no additional magnitude/list/name/event bounds.','prior_receipts':prior_phases,'accepted_IR':ih}))

    stored_view=json.loads((PKG/'obligation-view.json').read_bytes());current_view=view.derive(pkg)
    check('full_derived_current_view',current_view==stored_view and not current_view['evidence_integrity_problems'])
    recorded_report=json.loads((PKG/'report.json').read_bytes());report_module.validate(recorded_report)
    params=json.loads((PKG/'closure/implementation-claims.json').read_bytes())['parameters']
    diagnostics=[Diagnostic.from_json(x) for group in ['blocking_reasons','infrastructure_errors','warnings'] for x in recorded_report[group]]
    reconstructed_report=report_module.build(pkg,current_view,recorded_report['terminal_status'],diagnostics,recorded_report['builds'],recorded_report['determinism'],params,recorded_report['tier']['requested_endpoint'],recorded_report['tier']['require_state'],recorded_report['roots']['closure_input_root'],recorded_report['provenance'],recorded_report['review'],recorded_report['roots']['accepted_ir'],recorded_report['bridge_preparations'])
    check('entire_report_exact_derivative',reconstructed_report==recorded_report)
    check('report_honestly_blocked',all(recorded_report[k]=='BLOCKED' for k in ['terminal_status','mechanical_status','release_status']) and recorded_report['endpoint']['established'] is None and recorded_report['builds']==[] and recorded_report['mechanical_result'] is None and recorded_report['closure_id'] is None and recorded_report['roots']['closure_input_root'] is None)
    for oid,row in current_view['obligations'].items():
        app=lifecycle.applicability(row)
        for milestone in lifecycle.MILESTONES:
            result=row['lifecycle'][milestone]['outcome']
            if not app[milestone][0]:check('normative_NA:'+oid+':'+milestone,result=='NOT_APPLICABLE')
        if oid in guarantee_ids:check('required_pending_E2E:'+oid,row['lifecycle']['END_TO_END_VERIFIED']['outcome']=='PENDING' and row['lifecycle']['TESTED']['outcome']=='PENDING' and all(row['lifecycle'][m]['outcome']=='PASS' for m in ['INTERPRETED','FORMALIZED','TYPECHECKED','PROVED','IMPLEMENTED','LINKED']))
    nv=current_view['obligations']['valid_domain_witness'];check('NV_proved_not_implementation',nv['required'] is True and nv['lifecycle']['PROVED']['outcome']=='PASS' and all(nv['lifecycle'][m]['outcome']=='NOT_APPLICABLE' for m in lifecycle.IMPLEMENTATION_MILESTONES))
    selected=vscore3.selection(pkg);checked_link,link_diags=vscore3.checked_link(pkg)
    check('pure_exact_selection_and_link',not link_diags and checked_link==json.loads((PKG/'bridges/link.json').read_bytes()) and sorted(x['id'] for x in selected['covered'])==guarantee_ids)
    check('source3_exact_materialization',(PKG/'implementation/program.vscore.json').read_bytes()==(PKG/'agents/vscore-attempts/source-3/program.vscore.json').read_bytes() and (PKG/'bridges/implementation/candidate-inputs/program.vscore.json').read_bytes()==(PKG/'implementation/program.vscore.json').read_bytes() and (PKG/'bridges/implementation/candidate-inputs/Proof.lean').read_bytes()==(PKG/'agents/vscore-attempts/source-3/proofs/3.lean').read_bytes())
    materialization=json.loads((PKG/'implementation/materialization.json').read_bytes());check('materialization_proof_not_checked',materialization['proof_checked'] is False and materialization['source_hash']==h((PKG/'implementation/program.vscore.json').read_bytes()))
    published,pending,pubdiags=checker.verify_published(pkg,'implementation',rebuild=False)
    check('no_published_semantic_acceptance',published==[] and pending==['BRIDGE:implementation:vscore-refinement'] and pubdiags==[] and not (PKG/'bridges/implementation/semantic').exists())
    check('no_current_mechanical_execution',CL.mechanical_snapshot(pkg) is None and not any((PKG/'closure'/x).exists() for x in ['current.json','plan.json','manifest.json','executions']))
    graph=CL._claims(pkg);roots=CL._roots(pkg,selected,None);pool=list(pkg.evidence.load())+list(EvidenceStore(PKG/'bridges/implementation','implementation').load())
    check('registered_complete_graph',len(graph)==115 and sum(c['required'] for c in graph)==94 and all(e.valid and e.verifier_current for e in pool))
    assessments=[]
    for claim in graph:
        assessed=evaluate_claim(claim,pool,roots,claim['root_kind'])
        assessments.append({'claim':claim,'outcome':assessed.outcome,'authorized':assessed.authorized,'reason':assessed.reason,'evidence_id':assessed.evidence.id if assessed.evidence else None,'diagnostics':[x.to_json() for x in assessed.diagnostics]})
        if claim['required'] and assessed.outcome=='PASS':check('required_PASS_authenticated:'+claim['claim_id'],assessed.authorized and assessed.evidence is not None)
    required_outcomes=Counter(x['outcome'] for x in assessments if x['claim']['required'])
    check('full_graph_honest_required_states',required_outcomes=={'PASS':80,'PENDING':14})
    expected_pending={'BRIDGE:implementation:vscore-refinement',*CL.FINAL_PREDICATES,*[f'END_TO_END_VERIFIED:{oid}@1' for oid in guarantee_ids]}
    check('complete_pending_semantic_closure_graph',{x['claim']['claim_id'] for x in assessments if x['claim']['required'] and x['outcome']!='PASS'}==expected_pending)
    for oid in guarantee_ids:
        final=next(c for c in graph if c['claim_id']==f'END_TO_END_VERIFIED:{oid}@1')
        check('full_E2E_premises:'+oid,{'BRIDGE:implementation:vscore-refinement',*CL.FINAL_PREDICATES,f'PROVED:{oid}@1','IMPLEMENTED:D1@1','LINKED:D1@1',f'IMPLEMENTED:{oid}@1',f'LINKED:{oid}@1'}.issubset(final['premises']) and final['accepted_statement_hash']==ir['obligations'][oid]['formal']['statement_hash'])
    for ev in pool:
        if ev.record['verifier_id']=='verislop.vscore3-materializer':check('materializer_admission_only:'+ev.id,ev.result.get('proof_checked') is False)
        if ev.record['verifier_id']=='verislop.vscore3-linker':check('linker_structural_only:'+ev.id,ev.result.get('semantic_acceptance') is False and ev.result.get('correspondence')=='structural')
    prep=json.loads((PKG/'bridges/implementation/preparation-certificate.json').read_bytes())
    check('preparation_explicit_pending',prep['structural_acceptance'] is True and prep['semantic_acceptance'] is False and prep['assigns_end_to_end_verified'] is False and prep['pending_semantic_claims']==pending)
    (OUT/'registered-graph-assessments.json').write_bytes(d(assessments))
    (OUT/'reconstructed-report.json').write_bytes(d(reconstructed_report))

    # Every retained proof rejection is tied to its own exact source and generated goal.
    proof_attempts=[]
    for source_number in [1,2,3]:
        attempt=PKG/f'agents/vscore-attempts/source-{source_number}'
        inputs={k:h((attempt/v).read_bytes()) for k,v in {'source':'program.vscore.json','relation':'relation.json','profile':'profile.json','model':'model.json'}.items()}
        goal_hash=h((attempt/'VeriSlopBridgeGoal.lean').read_bytes())
        check('three_proofs_for_source:'+str(source_number),len(list((attempt/'checks').glob('proof-*.json')))==3)
        for proof_number in [1,2,3]:
            name=f'proof-{proof_number}.json';ck=json.loads((attempt/'checks'/name).read_bytes());dg=json.loads((attempt/'diagnostics'/name).read_bytes());proof_hash=h((attempt/f'proofs/{proof_number}.lean').read_bytes());raw_hash=h((attempt/f'responses/proof-{proof_number}.txt').read_bytes())
            label=f'{source_number}/{proof_number}'
            check('native_rejected_proof:'+label,ck['passed'] is False and ck['proof_checked'] is True and dg['passed'] is False and ck['diagnostics']==dg['diagnostics'])
            check('proof_hash_binding:'+label,ck['proof_hash']==dg['proof_hash']==proof_hash and ck['source_hash']==dg['source_hash']==inputs['source'] and ck['relation_hash']==dg['relation_hash']==inputs['relation'] and dg['response_artifact']=={'path':f'agents/vscore-attempts/source-{source_number}/responses/proof-{proof_number}.txt','sha256':raw_hash})
            for ix,di in enumerate(ck['diagnostics']):
                de=di['details'];check('compile_diagnostic_inputs:'+label+':'+str(ix),de['goal_hash']==goal_hash and de['module_source_hash']==proof_hash and de['input_hashes']=={**inputs,'proof_source':proof_hash} and de['error_count']==len(de['errors']) and di['code']=='CANDIDATE_BUILD_FAILURE')
            proof_attempts.append({'source_attempt':source_number,'proof_attempt':proof_number,'source_hash':inputs['source'],'goal_hash':goal_hash,'proof_hash':proof_hash,'raw_response_hash':raw_hash,'passed':False,'diagnostics':ck['diagnostics'],'scope':'Stored native failure and stderr observations only; no causal attribution or source correctness proof.'})
    check('all_nine_attempts_failed',len(proof_attempts)==9)
    (OUT/'native-proof-attempts.json').write_bytes(d(proof_attempts))

    events=[json.loads(x) for x in (PKG/'events.jsonl').read_text().splitlines()]
    check('event110_is_start_not_success',events[-1]['seq']==110 and events[-1]['type']=='stage_started' and events[-1]['phase']=='verify' and not any(x.get('milestone')=='END_TO_END_VERIFIED' and x.get('outcome')=='PASS' for x in events))
    pipeline=json.loads((PKG.parent/'stdout.json').read_bytes())
    check('pipeline_no_success_claim',pipeline['status']=='BLOCKED' and pipeline['asserts_closure_verified'] is False and pipeline['summary']['stopped_at']=='bridge:accept' and pipeline['summary']['failed_stage_summary']=={'assigns_end_to_end_verified':False,'bridge_id':'implementation','pending_semantic_claims':pending,'semantic_acceptance':False,'semantic_certificates':[]})
    check('closure_attempt_failed_before_snapshot',any(x['code']=='INVALID_CANDIDATE' and 'semantic/' in x['message'] and 'certificate.json' in x['message'] for x in pipeline['diagnostics']) and any(x['code']=='INVALID_CANDIDATE' and 'closure/plan.json' in x['message'] for x in pipeline['diagnostics']))
    check('report_matches_complete_native_diagnostics',recorded_report['blocking_reasons']==pipeline['diagnostics'] and pipeline['summary']['mechanical_status']==recorded_report['mechanical_status'] and pipeline['summary']['terminal_status']==recorded_report['terminal_status'])
    # Actual formal review exists; no release campaign is invented.
    campaigns=[q for q in (PKG/'reviews').iterdir() if q.is_dir()];check('only_formal_review_campaign',len(campaigns)==1)
    campaign=campaigns[0];cons=json.loads((campaign/'consensus-certificate.json').read_bytes());ballot=json.loads((campaign/'ballots/R0_critic#1.json').read_bytes())
    check('formal_review_only_ACCEPT',cons['checkpoint']=='formal_contract' and cons['final']=='REVIEW_ACCEPTED' and cons['mechanical_veto']==[] and cons['tiers'][0]['ballots'][0]['ballot_hash']==h((campaign/'ballots/R0_critic#1.json').read_bytes()) and cons['tiers'][0]['ballots'][0]['verdict']=='ACCEPT')
    counterreceipts=[json.loads(q.read_bytes()) for q in sorted((campaign/'counterexamples/R0_critic#1').glob('*.json'))]
    check('formal_concrete_probes_not_reproduced',len(counterreceipts)==2 and all(x['status']=='NOT_REPRODUCED' and x['checkpoint']=='formal_contract' for x in counterreceipts))
    check('release_never_ACCEPTED',recorded_report['release_status']=='BLOCKED' and recorded_report['review']=={'configured':True} and not any(json.loads((q/'campaign.json').read_bytes()).get('checkpoint')=='release' for q in campaigns))

    origin=B.response_audit(RUN,protocol['tasks'][0]);native=B.native_audit(pkg,recorded_report,RUN/'config.json')
    terminal=json.loads((PKG.parent/'result.json').read_bytes());aggregate=json.loads((RUN/'BOOTSTRAP-RESULT.json').read_bytes())
    check('exact_stored_origin_audit',origin==terminal['origin_audit'] and origin['status']=='PASS' and origin['provider_calls']==origin['responses']==19 and origin['transport_errors']==0 and len(set(origin['agents']))==19 and not origin['model_identity_attested'] and not origin['milestone_authority'])
    check('exact_native_terminal_audit',native==terminal['native'] and native['status']=='PASS' and native['required_obligations']==12 and native['required_guarantees']==9 and native['all_required_guarantees']==10 and native['required_non_vacuity_witnesses']==1 and native['required_e2e_passed']==0 and native['all_required_e2e'] is False and native['mechanical_claims']==[] and native['builds']==[])
    check('row_aggregate_verify_exact_agreement',aggregate['rows']==external_verify['rows']==[terminal] and terminal['issues']==[] and terminal['status']=='BLOCKED' and terminal['successful_task'] is False and terminal['strict_cli_success'] is False and terminal['worker_exit_code']==2 and aggregate['status']=='BLOCKED' and aggregate['complete'] is True and aggregate['verified_tasks']==0 and aggregate['fresh_calls']==aggregate['fresh_agents']==19 and aggregate['transport_errors']==0)
    check('unattested_and_no_oracles',aggregate['model_identity_attested'] is False and aggregate['hidden_cases_loaded'] is False and aggregate['oracle_calls']==0 and aggregate['original_python_assurance_relabelled'] is False)
    for n in range(1,20):
        nn=f'{n:04d}';request=json.loads((PKG.parent/f'mailbox/request-{nn}.json').read_bytes());response=json.loads((PKG.parent/f'mailbox/response-{nn}.json').read_bytes());receipt=json.loads((PKG.parent/f'mailbox/response-receipt-{nn}.json').read_bytes());binding=json.loads((PKG.parent/f'mailbox/carrier-binding-{nn}.json').read_bytes())
        orig=js(GATE/f'dispatch/origin-{nn}.json','external/dispatch/'+f'origin-{nn}.json');capture(GATE/f'dispatch/envelope-{nn}.json','external/dispatch/'+f'envelope-{nn}.json');final=capture(GATE/f'dispatch/final-{nn}.txt','external/dispatch/'+f'final-{nn}.txt')
        request_hash=h((PKG.parent/f'mailbox/request-{nn}.json').read_bytes());carrier_hash=h((PKG.parent/f'mailbox/carrier-{nn}.json').read_bytes())
        check('fresh_origin_exact_binding:'+nn,orig['request_id']==nn and orig['request_sha256']==request_hash==response['request_sha256']==receipt['request_sha256']==binding['request_sha256'] and orig['carrier_sha256']==carrier_hash==response['carrier_sha256']==binding['carrier_sha256'] and orig['agent_task_id']==response['agent_task_id']==receipt['agent_task_id']==origin['agents'][n-1] and orig['text_sha256']==h(final)==h(response['text'].encode())==receipt['text_sha256'] and orig['source_root']==SOURCE_ROOT and orig['supplemental_protocol_root']==h((RUN/'protocol.json').read_bytes()) and orig['fork_turns']=='none' and orig['model_identity_attested'] is False and receipt['returned_model'] is None)
    infra=json.loads((GATE/'dispatch/infrastructure-0019.json').read_bytes());recovery=json.loads((GATE/'dispatch/recovery-0019.json').read_bytes());origin19=json.loads((GATE/'dispatch/origin-0019.json').read_bytes())
    check('transient_spawn_refusal_honest',infra['role_ran'] is False and infra['child_returned'] is False and infra['response_submitted'] is False and infra['observed_prior_fresh_call_count']==infra['observed_prior_transport_submitted_count']==18 and infra['spawn_error']=='collab spawn failed: agent thread limit reached')
    check('same_request_recovered_before_final',recovery['prior_observation_sha256']==h((GATE/'dispatch/infrastructure-0019.json').read_bytes()) and recovery['pending_binding_unchanged'] is True and recovery['child_returned'] is True and recovery['child_confirmed_running'] is True and recovery['authoritative_final_received'] is False and recovery['response_submitted'] is False and all(infra[k]==recovery[k]==origin19[k] for k in ['request_id','request_sha256','carrier_sha256','spawn_message_sha256','source_root','request_set_root','supplemental_protocol_root']) and recovery['child_canonical_identity']==origin19['agent_task_id'])
    usage=json.loads((PKG.parent/'mailbox/usage.json').read_bytes());check('native_transport_errors_not_changed_by_spawn_retry',usage['calls']==usage['responses']==19 and usage['transport_errors']==0 and usage['unknown_usage_calls']==19 and usage['token_usage_available'] is False)
    (OUT/'terminal-observations.json').write_bytes(d({'native_pipeline':pipeline['summary'],'native_audit':native,'origin_audit':origin,'external_spawn_refusal':infra,'external_spawn_recovery':recovery,'review_consensus':cons,'formal_counterexample_receipts':counterreceipts,'materialization':{k:v for k,v in materialization.items() if k not in ['program','adapters','bindings','signatures','enums']},'interpretation':'BLOCKED is exact native outcome. Host seal verification PASS authenticates the unchanged blocked evidence; it does not establish refinement, clean builds, release acceptance or E2E.'}))

for path,digest in observed.items():check('unchanged:'+path,h(Path(path).read_bytes())==digest)
failed=[k for k,v in checks.items() if not v['ok']]
audit={'format':'independent-bounded-audit/0.1','phase':'sealed-terminal','stage':'013','task':'D21','time':datetime.now(timezone.utc).isoformat(),'source_root':SOURCE_ROOT,'sealed_run_root':SEAL_ROOT,'sealed_run_files':len(inventory),'outcome':'NO_CONCRETE_DEFECT_FOUND_IN_BOUNDED_SCOPE' if not failed else 'AUDIT_ASSERTION_FAILURE','native_outcome':'BLOCKED','checks':len(checks),'failed_checks':failed,'snapshots':len(snapshots),'observations':['Exact 846-file terminal seals, frozen 230-file project/source inventory and preregistered inputs authenticated.','Accepted complete reference/strict proof policy/constructive witness remain unchanged; nine required source/value guarantees and all original eleven identities retained.','Materialized source3 and LINKED are structural admission only; all nine authored bridge proofs rejected with exact input and diagnostic bindings.','Complete registered graph has 115 claims: 94 required, with 80 authenticated PASS and 14 PENDING (semantic edge, four terminal closure claims and nine E2E guarantees).','Frozen closure started but lacked semantic certificate and closure plan; no current closure execution, semantic certificate, or two clean-build records are published.','Stored view and entire report reconstruct exactly; terminal, aggregate, native audit and root seal-verification agree on BLOCKED and zero E2E success.','Formal-contract review ACCEPT and two NOT_REPRODUCED probes do not imply release approval; release is BLOCKED with no release campaign.','All 19 fresh completed roles, exact carriers/finals and the external request0019 spawn-refusal/recovery authenticate; native transport errors remain zero and model identity/token usage remain unattested.'],'limits':['Read-only pure validators only (semantic replay rebuild=False); no Lean/kernel/build/native-driver/model/review campaign or source function execution.','Natural-language correspondence remains an explicitly trusted independent bounded judgment; previous current-cohort receipts are authenticated for unchanged bytes, not used as implementation proofs.','Stored failures and stderr are observations, without causal resource attribution.','No old task candidates, hidden cases or oracles read, no role agents contacted, and no source/cohort/package artifact modified.','BLOCKED remains BLOCKED; no strict success, release acceptance, implementation refinement or E2E correctness claimed.']}
(OUT/'checks.json').write_bytes(d(checks));(OUT/'snapshots.json').write_bytes(d(snapshots));(OUT/'audit.json').write_bytes(d(audit));print(json.dumps(audit,indent=2));assert not failed,failed
