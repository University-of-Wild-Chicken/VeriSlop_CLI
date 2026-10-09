from pathlib import Path
import sys,json,datetime,os
from collections import Counter
AUDIT=Path(__file__).resolve().parent
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-010'
PROJECT=STAGE/'project'
RUN=STAGE/'run'
DIR=RUN/'artifacts/A23/verislop'
PKG=DIR/'package'
sys.path.insert(0,str(PROJECT))
from verislop import canonical,export,view,lifecycle,review,review_counterexamples as RC,schemas,agents
from verislop.package import Package
from verislop.backends import vscore3_closure as V
from verislop.bridges import vscore3_checker as K
from verislop.verifiers import verifier_hash
from verislop.claimcheck import evaluate_claim
from synthetic_dataset.tools import bootstrap_tier2 as H
checks=[];inputs={};receipts_summary=[]
def write(name,obj): (AUDIT/name).write_bytes(canonical.dumps(obj))
def check(name,result,detail=None):
 checks.append({'check':name,'passed':bool(result),'details':detail})
 if not result:raise AssertionError(name)
def capture(path):
 path=Path(path).resolve();rel=path.relative_to(STAGE).as_posix();data=path.read_bytes()
 q=AUDIT/'inputs'/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
 inputs[rel]={'sha256':canonical.digest(data),'size':len(data),'observed_path':str(path)}
 return data
p=Package(PKG)
protocol=canonical.load_file(RUN/'protocol.json');prereg=canonical.load_file(RUN/'preregistration.json')
aggregate=canonical.load_file(RUN/'BOOTSTRAP-RESULT.json');retained=canonical.load_file(DIR/'result.json');report=canonical.load_file(PKG/'report.json');stdout=canonical.load_file(DIR/'stdout.json');worker=canonical.load_file(DIR/'worker-result.json')
check('both sealed manifests are byte-identical',(RUN/'EVIDENCE-MANIFEST.json').read_bytes()==(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json').read_bytes())
seal=canonical.load_file(RUN/'EVIDENCE-MANIFEST.json');files=H.evidence_files(RUN)
check('exact sealed physical file membership/hash root',seal['files']==files and seal['files_root']==canonical.digest_json(files))
check('seal/protocol/preregistration frozen identities',seal['source_root']==prereg['source_root']==protocol['source_root']=='sha256:f72db4961eda28039e8e55ed5e7817ef194e0d8da50d8471aebcc7b33bf9f13f' and seal['protocol_sha256']==prereg['protocol_sha256']==canonical.digest_file(RUN/'protocol.json'))
check('single selected task and exact retained terminal row',protocol['task_order']==['A23'] and aggregate['rows']==[retained] and aggregate['selected_tasks']==aggregate['verified_tasks']==1)
check('sealed native strict terminal gate status',aggregate['status']==retained['status']==report['terminal_status']=='VERIFIED' and aggregate['complete'] is True and retained['successful_task'] is True and retained['strict_cli_success'] is True and retained['issues']==[])
check('actual CLI exit/result/request endpoint',worker['exit_code']==retained['worker_exit_code']==0 and worker['status']=='CLI_RETURNED' and stdout['command']=='run' and stdout['status']=='PASS' and stdout['diagnostics']==[] and stdout['summary']['terminal_status']=='VERIFIED' and stdout['summary']['active_package']==str(PKG))
check('sole completed driver phase',canonical.load_file(RUN/'active-arm.json')=={'phase':'bootstrap_complete'})
check('native requested strict tier2 restricted source endpoint',report['tier']=={'endpoint':'restricted_source','requested':2,'requested_endpoint':'restricted_source','require_state':'END_TO_END_VERIFIED','target':'vscore','tier_default_applied':False} and report['backend']=='verislop.backend.vscore/0.3' and report['language']=='vscore/0.3' and report['semantics']=='vscore-semantics/0.3' and report['endpoint']['established']=='restricted_source')
check('honest excluded runtime/model identity boundaries',aggregate['hidden_cases_loaded'] is False and aggregate['oracle_calls']==0 and aggregate['model_identity_attested'] is False and aggregate['original_python_assurance_relabelled'] is False and retained['python_runtime_campaign'] is False)
ir,irhash,acc,diags=export.verified_ir(p)
check('accepted contract evidence remains current',not diags,[d.as_dict() for d in diags])
accepted,pending,diags=K.verify_published(p,'implementation',rebuild=False)
check('published source semantic evidence remains current without replay',not pending and not diags and len(accepted)==1,[d.as_dict() for d in diags])
snapshot=V.mechanical_snapshot(p)
check('exact frozen execution current publication authenticates VERIFIED',snapshot is not None and snapshot['mechanical_status']=='VERIFIED' and snapshot['diagnostics']==[])
claims=V._claims(p);selection=V._selection(p);roots=V._roots(p,selection,snapshot['closure_root']);byclaim={x['claim_id']:x for x in claims};rows={x['claim_id']:x for x in snapshot['claims']}
check('complete 88-claim frozen graph preserved',len(claims)==88 and len(rows)==88 and set(rows)==set(byclaim))
check('all 62 required applicable graph claims PASS',sum(x['required'] for x in snapshot['claims'])==62 and all(x['outcome']=='PASS' for x in snapshot['claims'] if x['required']))
selected=V._selected_evidence(p,selection,claims,roots)
nonfinal,diags=V._nonfinal(p,selection,claims,roots,selected)
check('nonfinal evidence recomputes exact observed rows/prerequisites',not diags and nonfinal==[x for x in snapshot['claims'] if not V._terminal(byclaim[x['claim_id']])],[d.as_dict() for d in diags])
check('all PASS required premise edges terminate in PASS',all(all(rows[cid]['outcome']=='PASS' for cid in row['premises']) for row in rows.values() if row['required']))
check('exact stored two clean builds and deterministic projection',len(snapshot['builds'])==2 and [b['build'] for b in snapshot['builds']]==['A','B'] and all(b['ok'] and b['errors']==[] for b in snapshot['builds']) and snapshot['builds'][0]['outputs']==snapshot['builds'][1]['outputs'] and snapshot['determinism']['mismatches']==[] and snapshot['determinism']['compared']==list(V.COMPARISON_SLOTS))
check('exact complete report mechanically authenticated record',report['builds']==snapshot['builds'] and report['determinism']==snapshot['determinism'] and report['mechanical_status']==snapshot['mechanical_status'] and report['mechanical_result']==snapshot['mechanical_result_path'] and report['closure_id']==snapshot['closure_id'] and report['roots']['closure_input_root']==snapshot['closure_root'])
check('bootstrap stored native snapshot exact full graph/build outputs',retained['native']['mechanical_claims']==snapshot['claims'] and retained['native']['builds']==snapshot['builds'] and retained['native']['determinism']==snapshot['determinism'] and retained['native']['mechanical_result']==snapshot['mechanical_result_path'] and retained['native']['closure_root']==snapshot['closure_root'] and retained['native']['status']=='PASS' and retained['native']['issues']==[])
overlay=view.derive(p)
current={oid:{'role':r['role'],'kind':r['kind'],'revision':r['revision'],'required':r['required'],'outcomes':{m:v['outcome'] for m,v in r['lifecycle'].items()}} for oid,r in overlay['obligations'].items()}
check('current registered lifecycle agrees with full report',current=={oid:{k:r[k] for k in ['role','kind','revision','required','outcomes']} for oid,r in report['obligations'].items()})
check('bootstrap per-ID current lifecycle agreement',retained['native']['per_obligation_outcomes']=={oid:r['outcomes'] for oid,r in current.items()})
impl=[oid for oid,r in current.items() if r['required'] and r['role']=='guarantee' and lifecycle.applicability({'id':oid,**r})['END_TO_END_VERIFIED'][0]]
check('exact four original applicable implementation guarantee IDs',set(impl)=={'O1','O2','S1','S2'})
for oid,r in current.items():
 app=lifecycle.applicability({'id':oid,**r})
 for milestone in lifecycle.CONTRACT_MILESTONES:
  if r['required'] and app[milestone][0]:
   cid=lifecycle.claim_id(milestone,oid,r['revision'])
   check('required contract graph milestone '+cid,r['outcomes'][milestone]=='PASS' and rows[cid]['required'] and rows[cid]['outcome']=='PASS')
 if oid in impl:
  check('actual per-ID E2E transported guarantee '+oid,r['outcomes']['END_TO_END_VERIFIED']=='PASS' and rows[lifecycle.claim_id('END_TO_END_VERIFIED',oid,r['revision'])]['required'])
  check('optional testing remains PENDING '+oid,r['outcomes']['TESTED']=='PENDING' and rows[lifecycle.claim_id('TESTED',oid,r['revision'])]['outcome']=='PENDING' and rows[lifecycle.claim_id('TESTED',oid,r['revision'])]['required'] is False)
check('constructive witness required PROVED with no implementation applicability',current['A1_nonvacuity']['outcomes']['PROVED']=='PASS' and rows['PROVED:A1_nonvacuity@1']['required'] and all(current['A1_nonvacuity']['outcomes'][m]=='NOT_APPLICABLE' for m in lifecycle.IMPLEMENTATION_MILESTONES))
check('accurate native obligation counters',retained['native']['required_obligations']==9 and retained['native']['required_guarantees']==retained['native']['required_e2e_passed']==4 and retained['native']['all_required_guarantees']==5 and retained['native']['required_non_vacuity_witnesses']==1 and retained['native']['all_required_e2e'] is True)
counts={m:dict(Counter(r['outcomes'][m] for r in current.values())) for m in lifecycle.MILESTONES}
check('exact report milestone counts',report['counts']=={'milestones':counts,'obligations':9,'required_obligations':9})
conf=canonical.load_file(RUN/'config.json')
oldhome=os.environ.get('VERISLOP_CONFIG_HOME')
with H._frozen_provider_context(RUN/'config.json'):
 validated_protocol=H.verify_inputs(RUN)
 origin=H.response_audit(RUN,validated_protocol['tasks'][0])
 check('all exact role/artifact origins independently reconstruct',origin==retained['origin_audit'] and origin['status']=='PASS' and origin['issues']==[])
 check('11 unique fresh origin roles, no transport errors',origin['provider_calls']==origin['responses']==len(set(origin['agents']))==11 and origin['transport_errors']==0 and aggregate['fresh_calls']==aggregate['fresh_agents']==11)
 release_folder=PKG/'reviews/rc-0002-20261009T212455Z-637892'
 release=canonical.load_file(release_folder/'consensus-certificate.json')
 reuse=review._release_reuse_context(p,release,conf)
 check('exact release original/current execution projection binding',reuse.original==reuse.current and reuse.previous_projection==reuse.current_projection)
 for folder in sorted((PKG/'reviews').glob('rc-*')):
  cert=canonical.load_file(folder/'consensus-certificate.json');campaign=canonical.load_file(folder/'campaign.json');packet=canonical.load_file(folder/'packet.json')
  check('consensus schema/identity '+cert['checkpoint'],not schemas.validate('consensus-certificate',cert) and cert['final']=='REVIEW_ACCEPTED' and cert['mechanical_veto']==[] and cert['campaign_id']==folder.name and cert['checkpoint']==campaign['checkpoint'] and cert['review_target_root']==campaign['review_target_root'] and cert['target_components']==campaign['target_components'])
  if cert['checkpoint']=='formal_contract':
   check('formal-contract candidate/packet current binding',cert['target_components']['candidate_root']==review.candidate_root(p,'formal_contract') and cert['target_components']['packet']==canonical.digest_json(packet))
  for tier in cert['tiers']:
   tier_conf=next(t for t in campaign['config']['review']['review_tiers'] if t['id']==tier['tier_id']);ballots={}
   check('configured review membership/policy preserved '+cert['checkpoint'],tier['membership']==[f"{tier_conf['id']}/{g['agent']}#{i+1}" for g in tier_conf['reviewers'] for i in range(g['count'])] and tier['policy']==tier_conf['consensus'] and tier['execution_failures']==[])
   for ref in tier['ballots']:
    bp=PKG/ref['ballot_ref'];b=canonical.load_file(bp)
    check('hash-bound constructive ballot '+cert['checkpoint'],canonical.digest_file(bp)==ref['ballot_hash'] and not schemas.validate('review-ballot-v2',b) and b['campaign_id']==cert['campaign_id'] and b['checkpoint']==cert['checkpoint'] and b['review_target_root']==cert['review_target_root'] and b['verdict']==ref['verdict']=='ACCEPT')
    check('hash-bound fresh reviewer transcript '+cert['checkpoint'],canonical.digest_file(PKG/b['transcript_ref'])==b['transcript_hash'])
    parsed,err=review.parse_ballot(agents.extract_json((PKG/b['transcript_ref']).read_text()),packet['scope'],packet['counterexample_policy'])
    check('raw reported ballot/search exact '+cert['checkpoint'],not err and parsed['reported_verdict']==b['reported_verdict'] and parsed['search']==b['search'])
    saved=[]
    check('one hash-bound receipt per concrete probe '+cert['checkpoint'],len(parsed['search']['probes'])==len(b['counterexample_receipts']))
    for probe,rr in zip(parsed['search']['probes'],b['counterexample_receipts']):
     rc=canonical.load_file(PKG/rr['receipt_ref'])
     check('exact proposal/receipt/checker identity '+rr['receipt_ref'],canonical.digest_file(PKG/rr['receipt_ref'])==rr['receipt_hash'] and not schemas.validate('review-counterexample-receipt',rc) and rc['proposal']==probe and rc['proposal_hash']==rr['probe_hash']==canonical.digest_json(probe) and rc['status']==rr['status']=='NOT_REPRODUCED' and rc['diagnostics']==[] and rc['checkpoint']==cert['checkpoint'] and rc['checker']=={'id':RC.VERIFIER,'sha256':verifier_hash(RC.VERIFIER)})
     for binding,digest in rc['input_bindings'].items():
      if binding=='binding:roots':actual=canonical.digest_json(RC.bound_roots(p,cert['checkpoint']))
      elif binding.startswith(('evidence:','evidence-result:')):
       ev=p.evidence.by_id(binding.split(':',1)[1]);check('receipt evidence valid/current '+binding,ev is not None and ev.valid and ev.verifier_current)
       actual=canonical.digest_json(ev.result if binding.startswith('evidence-result:') else ev.record)
      else:actual=canonical.digest_file(PKG/binding)
      check('receipt exact input binding '+rr['receipt_ref']+' '+binding,actual==digest)
     if probe['kind']=='mechanical_failure':
      cid=probe['claim_id'];definition=byclaim[cid]
      check('mechanical probe exact registered root/predicate/observed PASS '+cid,rc['claim']['result_predicate']==definition['result_predicate'] and rc['expected']=={'outcome':'PASS','root':roots[definition['root_kind']],'root_kind':definition['root_kind']} and rc['observed']['outcome']=='PASS' and rows[cid]['outcome']=='PASS')
      if cert['checkpoint']=='release':
       obs=review._mechanical_receipt_observation(p,rc,reuse.current,reuse.current_projection)
       check('closed authenticated mechanical receipt observation '+cid,obs['format']=='verislop.review-mechanical-observation/0.1' and obs['execution']['projection_hash']==reuse.current_projection['projection_hash'])
     else:
      check('functional probe accepted formula/IR/actual kernel result binding',rc['claim']['accepted_statement_hash']==ir['obligations'][probe['obligation_id']]['formal']['statement_hash'] and rc['expected']['accepted_ir_hash']==irhash and rc['expected']['assignment']==probe['assignment'] and rc['expected']['predicate'] is True and rc['expected']['semantics']=='vscore-semantics/0.3' and rc['observed']['predicate'] is True and rc['observed']['kernel_replay'] is True and rc['observed']['ground_expression_hash']==rc['observed']['result_type_hash'])
     saved.append(rc);receipts_summary.append({'checkpoint':cert['checkpoint'],'proposal':probe,'status':rc['status'],'receipt_hash':rr['receipt_hash'],'claim':rc['claim'],'expected':rc['expected'],'observed_outcome':rc['observed'].get('outcome'),'observed_predicate':rc['observed'].get('predicate')})
    review._apply_replay_results(parsed,saved,packet['scope'])
    expected_effective={'verdict':parsed['verdict'],'reviewed_obligations':parsed['reviewed_obligations'],'finding_refs':[b['slot_id']+':'+f['id'] for f in parsed['findings']],'unresolved_blocking_findings':[b['slot_id']+':'+f for f in parsed['blocking']],'limitations':parsed['limitations'],'rationale':parsed['rationale']}
    check('effective ballot exactly derives from stored concrete receipts '+cert['checkpoint'],all(b[k]==v for k,v in expected_effective.items()))
    ballots[b['slot_id']]=b
   tally=review.tally_tier(tier_conf,tier['membership'],ballots,cert['mechanical_veto'])
   check('exact pure consensus retally '+cert['checkpoint'],tally==tier['tally'] and tally['result']==tier['result']=='TIER_ACCEPTED')
 reuse_row={'original_raw_inventory_hash':reuse.previous_projection['raw_inventory_hash'],'current_raw_inventory_hash':reuse.current_projection['raw_inventory_hash'],'projection_hash':reuse.current_projection['projection_hash'],'target':release['review_target_root']}
 expected_gate={'configured':True,'checkpoints':{'formal_contract':'REVIEW_ACCEPTED','release':'REVIEW_ACCEPTED'},'diagnostics':[],'projection_reuse':{'release':reuse_row},'review_target':release['review_target_root']}
 check('full stored report gate record exactly reconstructed',report['review']==expected_gate and report['review_target']==expected_gate['review_target'] and report['review_projection']['reuse']==expected_gate['projection_reuse'])
 check('report projection normalization/raw inventory binding',report['review_projection']['hash']==reuse.current_projection['projection_hash'] and report['review_projection']['current_raw_inventory_hash']==reuse.current_projection['raw_inventory_hash'] and report['review_projection']['normalizer_registry_hash']==reuse.current_projection['normalizer_registry_hash'])
check('frozen provider environment restored',os.environ.get('VERISLOP_CONFIG_HOME')==oldhome)
check('final CLI/report/bootstrap mechanical/release agreement',stdout['summary']['mechanical_status']==report['mechanical_status']==retained['mechanical_status']=='VERIFIED' and stdout['summary']['release_status']==report['release_status']==retained['release_status']=='ACCEPTED' and stdout['summary']['closure_root']==snapshot['closure_root'] and stdout['summary']['mechanical_result']==snapshot['mechanical_result_path'])
check('all 8 concrete review probes independently bound',len(receipts_summary)==8 and sum(x['proposal']['kind']=='target_case' for x in receipts_summary)==3)
for name,digest in seal['files'].items():check('sealed snapshot exact '+name,canonical.digest(capture(RUN/name))==digest)
for name in ['EVIDENCE-MANIFEST.json','BOOTSTRAP-EVIDENCE-MANIFEST.json']:capture(RUN/name)
check('exact cohort membership/bytes unchanged after audit',H.evidence_files(RUN)==files)
check('all captured input bytes unchanged',all(canonical.digest_file(STAGE/name)==row['sha256'] for name,row in inputs.items()))
write('checks.json',checks);write('counterexample-inspection.json',receipts_summary);write('input-manifest.json',{'format':'independent-readonly-audit-inputs/0.1','files':inputs})
write('audit.json',{'format':'independent-readonly-terminal-audit/0.1','observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':str(STAGE),'task':'A23','source_root':protocol['source_root'],'protocol_hash':canonical.digest_file(RUN/'protocol.json'),'accepted_ir_hash':irhash,'closure_root':snapshot['closure_root'],'current_execution':snapshot['mechanical_result_path'],'seal_files_root':seal['files_root'],'checks_passed':len(checks),'input_files':len(inputs),'concrete_defects_found':[],'conclusion':'No concrete terminal scope, evidence, applicability, report or seal discrepancy found in inspected current stored artifacts. The sole native driver result is exit0/PASS; sealed aggregate and current full report agree on VERIFIED restricted-source terminal, VERIFIED mechanics and ACCEPTED release.','required_claims':62,'total_claims':88,'required_applicable_implementation_guarantees':impl,'non_vacuity':{'id':'A1_nonvacuity','required':True,'PROVED':'PASS','implementation_milestones':'NOT_APPLICABLE'},'optional_TESTED':{oid:current[oid]['outcomes']['TESTED'] for oid in impl},'fresh_origins':{'calls':11,'unique_agents':11,'transport_errors':0,'exact_artifact_reconstruction':'PASS','model_identity_attested':False},'stored_reviews':{'formal_contract':'REVIEW_ACCEPTED','release':'REVIEW_ACCEPTED','concrete_receipts':len(receipts_summary),'statuses':['NOT_REPRODUCED']},'two_clean_builds':'exact complete compared outputs equal; all retained bytes/inventories authenticated','limits':['Natural-language scope correspondence remains a trusted reading; accepted-phase and source-bridge scope were audited independently on current stage010 artifacts.','No new kernel/native/closure execution or model call was performed. Stored accepted evidence, complete execution inventories and scoped roots were authenticated with pure validators and rebuild=False.','Concrete probe receipts were authenticated and their effective ballot/tally was reconstructed; this audit did not execute their kernel probes or rerun review.gate. Parent separately runs normal frozen seal verification.','Assurance applies to normative restricted VSCore source semantics, not Python or host compiler/runtime/machine-code behavior.','Optional TESTED remains PENDING; it was never relabelled PASS or used to supply E2E evidence.','Requested model identity is honestly unattested. Fresh exact origin bindings do not attest an external provider model.','This receipt is outside the frozen cohort, adds no lifecycle authority, and does not rewrite any sealed artifact.'],'snapshot_rechecked':True})
for q in AUDIT.rglob('*'):
 if q.is_file():q.chmod(0o444)
for q in sorted(AUDIT.rglob('*'),reverse=True):
 if q.is_dir():q.chmod(0o555)
AUDIT.chmod(0o555)
print(json.dumps({'audit':str(AUDIT/'audit.json'),'audit_sha256':canonical.digest_file(AUDIT/'audit.json'),'checks':len(checks),'input_files':len(inputs),'required_claims':62,'all_claims':88},sort_keys=True))
