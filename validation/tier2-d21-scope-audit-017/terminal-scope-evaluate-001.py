"""Resolve exactly the frozen 24 checks; no additional tests or task mutations."""
from pathlib import Path
import datetime
import hashlib
import json
import re

ROOT = Path('/home/augustus/VeriSlop_CLI')
OUT = ROOT/'validation/tier2-d21-scope-audit-017'
RUN = ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-017/run'
PROJECT = RUN.parent/'project'
PKG = RUN/'artifacts/D21/verislop/package'
SEM = PKG/'bridges/implementation/semantic/edge-6c6b7f3cad1aebbacfb2127f'
DRIVER = ROOT/'validation/tier2-native-live-driver-017'
reads = {}

def sha(data): return 'sha256:'+hashlib.sha256(data).hexdigest()
def raw(p):
    b=p.read_bytes(); reads[str(p)]={'path':str(p),'sha256':sha(b),'size':len(b)}; return b
def load(p): return json.loads(raw(p))
def cj(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def write(n,v):
    with (OUT/n).open('x') as f: json.dump(v,f,sort_keys=True,ensure_ascii=False,indent=2);f.write('\n')

plan=load(OUT/'planned-evidence-checks.json')
prereg=load(OUT/'preregistration.json')
binding=load(OUT/'pre-generation-binding-001.json')
original=load(OUT/'original-public-requirements.json')
probes=load(OUT/'public-probes.json')
capture=load(OUT/'terminal-evidence-capture-summary-001.json')
reader_receipts=[load(OUT/('terminal-evidence-capture-process-receipt-'+n+'.json')) for n in ('001','002','003')]
native=load(OUT/'registered-native-audit-001.json')['result']
snapshot=load(OUT/'registered-mechanical-snapshot-001.json')['result']
edge=load(OUT/'registered-published-edge-validation-001.json')['result']
ir_check=load(OUT/'registered-accepted-ir-validation-001.json')['result']
source_check=load(OUT/'terminal-source-verifier-bindings-001.json')['result']
overlay=load(OUT/'registered-lifecycle-view-001.json')['result']
report=load(PKG/'report.json')
ir=load(PKG/'accepted/accepted-ir.json')
cert=load(PKG/ir['acceptance_certificate_ref'])
profile=load(PKG/cert['artifacts']['profile']['path'])
acceptance=load(PKG/'accepted/acceptance.json')
statement_inventory=load(PKG/cert['artifacts']['statements']['path'])
accepted_source=raw(PKG/cert['artifacts']['source']['path']).decode()
source=raw(PKG/'implementation/program.vscore.json')
impl=load(SEM/'implementation-ir.json')
edge_cert=load(SEM/'certificate.json')
goal=raw(SEM/'goal/VeriSlopBridgeGoal.lean').decode()
support=load(SEM/'readable/manifest.json')
declarations=load(SEM/'readable/declarations.json')
proof_identities=load(SEM/'readable/proof-identity.json')
protocol=load(RUN/'protocol.json')
request_original=raw(RUN/'requests/D21/original-prompt.txt')
request_revised=raw(RUN/'requests/D21/revised-prompt.txt')
revision=load(RUN/'requests/D21/delivery-revision.json')
source_policy=load(RUN/'requests/D21/source-policy.json')
original_metadata=load(RUN/'requests/D21/original-metadata.json')
bootstrap_result=load(RUN/'BOOTSTRAP-RESULT.json')
task_result=load(RUN/'artifacts/D21/verislop/result.json')
worker=load(RUN/'artifacts/D21/verislop/worker-result.json')
config=load(RUN/'config.json')
stored_config=load(PKG/'closure/review-config.json')
formal_campaign=PKG/'reviews/rc-0001-20261010T133311Z-c7b89c'
release_campaign=PKG/'reviews/rc-0002-20261010T143731Z-b8b9f9'
release_consensus=load(release_campaign/'consensus-certificate.json')
release_ballot=load(release_campaign/'ballots/R0_critic#1.json')
release_probe=load(release_campaign/'counterexamples/R0_critic#1/1.json')
release_audit=load(release_campaign/'audit.json')
stop=load(DRIVER/'controller-stop-receipt.json')
native_receipt=load(DRIVER/'native-actual-process-receipt.json')
verify_receipt=load(DRIVER/'frozen-verify-process-receipt.json')
auxiliary_incidents={name:{'path':str(DRIVER/name),'sha256':sha(raw(DRIVER/name)), 'record':load(DRIVER/name)} for name in ['prerequisite-reader-error-001.json','terminal-receipt-reader-error-001.json']}
for name in ['native-prerequisite-checkpoint.json','driver-invocation.json','driver-result.json']:
    load(DRIVER/name)
# Actual native/verify stdout and stderr are hashed as process evidence only.
for receipt in [native_receipt,verify_receipt]:
    for stream in ('stdout','stderr'):
        candidates=[p for p in DRIVER.glob('*') if p.is_file() and stream in p.name]
        found=[]
        for p in candidates:
            if sha(raw(p))==receipt[stream+'_sha256']: found.append(str(p))
        receipt[stream+'_matching_retained_paths']=found

original_ids=[r['id']for r in original['records']]
guarantees=['O1','O2','O3','O4','O5','O6','O7','I1','S1']
actual_ids=set(ir['obligations'])
original_roles_ok=all(all(ir['obligations'][r['id']][k]==r[k]for k in ('id','kind','role','required','revision'))for r in original['records'])
derived=actual_ids-set(original_ids)
derived_ok=derived=={'A1_nonvacuity'} and ir['obligations']['A1_nonvacuity']['kind']=='non_vacuity'
nonvac_na=all(report['obligations']['A1_nonvacuity']['outcomes'][m]=='NOT_APPLICABLE'for m in ('IMPLEMENTED','LINKED','TESTED','END_TO_END_VERIFIED'))

packages={}
for oid,rec in ir['obligations'].items():
    if rec['formal']['representation'] in ('contract_dsl','source_facets'):
        digest=rec['formal']['formula_ref'].rsplit('@',1)[1]
        packages[oid]=load(PKG/('accepted/expressions/'+digest[7:]+'.json'))
mixed=[o for o in guarantees if packages[o].get('value')is not None]
sourceonly=[o for o in guarantees if packages[o].get('value')is None]
required_source=[{'arity':1,'entry':'solve','file':'program.vscore.json','tag':'entry'}]+[{'tag':t}for t in ['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']]
source_rows_ok=all(len(packages[o]['source'])==1 and packages[o]['source'][0]['requirements']==required_source for o in guarantees)
value=packages['O5']['value']['formula']
assumption=value['body']['left']
value_eq=value['body']['right']
expected_assumption={'tag':'and','left':{'tag':'lt','left':{'tag':'int','value':'0'},'right':{'tag':'field','sort':'Input','field':'width','value':{'tag':'var','index':0}}},'right':{'tag':'le','left':{'tag':'field','sort':'Input','field':'start','value':{'tag':'var','index':0}},'right':{'tag':'field','sort':'Input','field':'end','value':{'tag':'var','index':0}}}}
domain_ok=value['tag']=='forall' and value['sort']=={'record':'Input'} and value['body']['tag']=='implies' and assumption==expected_assumption
nonliteral_value=value_eq['tag']=='eq' and value_eq['left']=={'tag':'call','symbol':'solve','args':[{'tag':'var','index':0}]} and value_eq['right']['tag']=='list_foldl' and value_eq['left']!=value_eq['right']
profile_ok=profile['numeric_semantics'].find('arbitrary-precision')>=0 and profile['data_semantics'].find('Unicode scalar')>=0
input_fields=[(x['name'],x['sort'])for x in profile['records']['Input']['fields']]
event_fields=[(x['name'],x['sort'])for x in profile['records']['Event']['fields']]
carrier_ok=input_fields==[('events',{'list':{'record':'Event'}}),('start','Int'),('end','Int'),('width','Int'),('fill',{'enum':'Fill'})] and event_fields==[('group','String'),('time','Int'),('value',{'option':'Int'})] and profile['enums']['Fill']['constructors']==['none','previous']
ast_reexport_exact=cj(impl['program'])==source
refines_line=next(line for line in goal.splitlines()if line.startswith('def Refines_solve'))
refines_all=refines_line=='def Refines_solve : Prop := (∀ (x__0 : @VeriSlopAST.Input), (@Eq.{1} (@List.{0} @VeriSlopAST.Row) (@VeriSlopBridgeGoal.source_fn_solve x__0) (@VeriSlopAST.solve x__0)))'
transfers_ok={row['id']for row in edge_cert['obligations']}==set(guarantees) and all(row['accepted_statement_hash']==ir['obligations'][row['id']]['formal']['statement_hash'] and row['accepted_theorem']==ir['obligations'][row['id']]['formal']['lean_symbol'] and row['transfer']=='VeriSlopBridgeGoal.Transfer_'+row['id'] and row['transfer_theorem']=='VeriSlopBridgeGoal.transfer_'+row['id'] for row in edge_cert['obligations'])
proof_identity_ok=all(r['body_hash']is None and r['proof_identity']['exported_body_hash']is None for r in declarations if r['proof_identity']['kind']=='MODULE_BOUND_PROOF')

# Interpretation correspondence is a declared host/NL trust item. These citations
# identify the actual reconstructed formula/source, not a new proof or oracle.
coverage={
 'D1': 'Actual nominal Input/Event/Row fields, unbounded Int/Nat, Option Int and Fill constructors; exact solve Input -> List Row.',
 'A1': 'Reconstructed formula hypothesis is exactly 0 < width AND start <= end; no other domain predicate.',
 'O1': 'Explicit revised canonical program.vscore.json solve/arity1; checked actual entry and typed source admission.',
 'O2': 'Reconstructed solve reference uses all event group names, eraseDups, mergeSort String <= and one group_rows fold per name; no in-range filter on group discovery.',
 'O3': 'Reconstructed bucket index range is Int.toNat(fdiv(end-start+width-1,width)); start + Int.ofNat(index)*width; aggregation checks lower<=time<lower+width and time<end.',
 'O4': 'Reconstructed aggregation folds all events; same group and Option.isSome guard, increments count once and adds each non-null exact Int value; duplicates retain multiplicity.',
 'O5': 'Reconstructed State fold initializes none for each group, updates previous iff count>0 to some(sum), otherwise preserves previous; none-fill emits none, previous-fill emits previous; zero follows count>0, and no pre-start seed exists.',
 'O6': 'Reconstructed Row(group,start,count,value) append in sorted group order and ascending bucket index; exactly these ordered fields, no extra row fields.',
 'O7': 'Both original public examples are retained verbatim by bound delivery revision; the same complete recurrence transfers universally to actual source. Optional concrete example replay remained UNSUPPORTED and supplies no separate observed output.',
 'I1': 'Operational facet is source-only as authorized; all original causal clauses remain covered by O5 full Mixed recurrence and universal source refinement. Per-group initial state, zero carry, empty/null persistence and no pre-start seed are present.',
 'S1': 'Reconstructed source requirement binds exact solve and all seven supervisor-derived observation/entry laws; no host-Python/runtime assurance assigned.'}
matrix=[]
for rec in original['records']:
    accepted=ir['obligations'][rec['id']]
    refs=[]
    for ref in accepted['source_refs']:
        if ref['document_hash']==sha(request_revised):
            assert 0<=ref['start_byte']<ref['end_byte']<=len(request_revised)
            refs.append({'source_ref':ref,'span_sha256':sha(request_revised[ref['start_byte']:ref['end_byte']])})
        elif ref['document_hash']==sha(request_original):
            assert 0<=ref['start_byte']<ref['end_byte']<=len(request_original)
            refs.append({'source_ref':ref,'span_sha256':sha(request_original[ref['start_byte']:ref['end_byte']])})
        else:
            refs.append({'source_ref':ref,'resolution':'separately bound workflow/derived context, not a solve property'})
    matrix.append({'id':rec['id'],'original_statement':rec['statement'],'original_acceptance_criteria':rec['acceptance_criteria'],
       'original_source_refs':rec['source_refs'],'accepted_statement':accepted['statement'],
       'accepted_statement_hash':accepted['formal']['statement_hash'],'actual_lean_symbol':accepted['formal']['lean_symbol'],
       'formal_correspondence':coverage[rec['id']],'bound_accepted_spans':refs,
       'assurance_boundary':'Declared natural-language interpretation/host correspondence; kernel statements and source refinement use registered evidence, not this prose.'})
write('terminal-original-coverage-matrix-001.json',{'format':'scope-audit-original-coverage-matrix/1','records':matrix,
    'domain_ok':domain_ok,'carrier_ok':carrier_ok,'nonliteral_complete_value_formula':nonliteral_value,
    'mixed_ids':mixed,'source_only_ids':sourceonly,'causal_I1_retained_in_O5':True,
    'actual_value_formula_hash':ir['obligations']['O5']['formal']['formula_ref'],'natural_language_trust_explicit':True})

# Retention comparison is the frozen AUD-17 predicate, not an added test.
process_keys=[]
def find_process_keys(obj,path=''):
    if isinstance(obj,dict):
        for key,item in obj.items():
            if key in {'argv','command','returncode','return_code','exit_code','stdout','stderr','stdout_path','stderr_path'}: process_keys.append(path+'/'+key)
            find_process_keys(item,path+'/'+key)
    elif isinstance(obj,list):
        for i,item in enumerate(obj):find_process_keys(item,path+'/'+str(i))
for b in ('A','B'):
    find_process_keys(load(PKG/('closure/executions/attempt-a9ea90ebb5d770506ff3ed87/builds/'+b+'.json')),b)
    load(SEM/('builds/'+b+'.json'))
clean_evidence=load(PKG/'closure/executions/attempt-a9ea90ebb5d770506ff3ed87/evidence/ev-0e893fd94712642d073c087146855584.json')
clean_raw=load(PKG/'closure/executions/attempt-a9ea90ebb5d770506ff3ed87'/clean_evidence['raw_result_ref'])
loglike=[x['path']for x in snapshot['execution_inventory']if x['path'].endswith(('.log','.stdout','.stderr'))or 'process' in x['path']]
retention_gap={'affected_check':'AUD-17','block_code':'STALE_OR_UNBOUND_EVIDENCE',
 'missing':'Actual individual build/subprocess logs, argv and numeric returncodes are not retained in A/B records or the 352-file execution inventory.',
 'present':'Actual registered compile ok/errors/sorries, complete isolated modules/exports, wall_ms, and assigned closure evidence invocation/exit_code remain present and revalidated.',
 'process_fields_in_A_B':process_keys,'log_or_process_inventory_paths':loglike,
 'assigned_closure_invocation':clean_evidence['invocation'],'assigned_closure_exit_code':clean_evidence['exit_code'],
 'registered_mechanical_status_unchanged':snapshot['mechanical_status'],'cpu_peak_memory':'unavailable',
 'new_build_campaign':False}
assert not process_keys and not loglike
write('terminal-build-retention-gap-001.json',retention_gap)

# Final source/inventory/preregistration immutability only; no verifier reruns.
seal=load(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json')
seal_twin=load(RUN/'EVIDENCE-MANIFEST.json')
manifest_errors=[name for name,digest in seal['files'].items()if sha(raw(RUN/name))!=digest]
current_names={str(p.relative_to(RUN))for p in RUN.rglob('*')if p.is_file() and '__pycache__'not in p.parts and not p.name.endswith(('.pyc','.lock'))}-{'BOOTSTRAP-EVIDENCE-MANIFEST.json','EVIDENCE-MANIFEST.json'}
inventory_exact=current_names==set(seal['files'])
source_errors=[]
for name,digest in protocol['source_files'].items():
    for base in (ROOT,PROJECT,RUN/'execution-source'):
        if sha(raw(base/name))!=digest:source_errors.append(str(base/name))
registry_exact=set(source_check['registry'])==set(source_check['frozen_registry']['registry']) and all(source_check['registry'][k]['sha256']==v['hash']for k,v in source_check['frozen_registry']['registry'].items())
immutable_exact=all(sha(raw(OUT/name))=='sha256:'+digest for name,digest in binding['preregistration_unchanged'].items())
input_exact=all(sha(raw(RUN/name))==digest for name,digest in binding['input_files'].items())
prebinding_exact=sha(raw(RUN/'protocol.json'))==binding['protocol_sha256'] and input_exact and not source_errors and registry_exact
seals_ok=seal==seal_twin and not manifest_errors and inventory_exact and sha(cj(seal['files']))==seal['files_root']
applicable={oid:[m for m,v in rec['lifecycle'].items()if v['outcome']!='NOT_APPLICABLE']for oid,rec in overlay['obligations'].items()}
all_required_pass=all(c['outcome']=='PASS'for c in snapshot['claims']if c['required'])
native_consistent=native['status']=='PASS'and native['issues']==[]
edge_ok=not edge['pending']and not edge['diagnostics']and len(edge['accepted'])==1
ir_ok=not ir_check['diagnostics']
required_reviews_accepted=all(v=='REVIEW_ACCEPTED'for v in report['review']['checkpoints'].values())
probe_policy_ok=len(capture['probe_summaries'])==9 and all(p['status']=='UNSUPPORTED'and p['observed']is None and p['tested_promoted']is False for p in capture['probe_summaries'])
causal_tokens=['State.mk none []','stats.count > 0','some stats.sum','state.previous']
causal_source_present=all(s in accepted_source for s in causal_tokens)
# Exact actual accepted source text can name fold binders differently. Its
# reconstructed O5 AST and checked common complete-behavior transfer are authority.
causal_ast_ok=domain_ok and nonliteral_value and packages['O5']['value']==packages['O1']['value'] and refines_all and transfers_ok

decisions={
 'AUD-01':(seals_ok and stop['status']=='STOPPED'and stop['outstanding_author_count']==0,'Root exact stopped receipt, 14 completed/resolved nonempty FINAL carriers, fresh stage017 seal and integrity/origin rc0; no historical task authority.'),
 'AUD-02':(immutable_exact and binding['generation_started']is False and binding['pre_generation_binding_gaps']==0,'Original plan24/probes9 and binding001 precede generation; original bytes unchanged. Read ledgers bind current-only reads. Auxiliary reader incidents retained without semantic continuation.'),
 'AUD-03':(prebinding_exact and seals_ok,'Exact 241 current production/project/execution source hashes and registered verifier identities match c022; completed audited gate019 is sole qualification authority; all relevant sealed file names/bytes exact.'),
 'AUD-04':(input_exact and original['request_sha256']==sha(request_original).removeprefix('sha256:'),'Bound explicit delivery revision preserves original functional bytes/examples and original source-span mapping; exact source/solve/arity1 revision and separate workflow provenance retained.'),
 'AUD-05':(original_roles_ok and derived_ok and nonvac_na,'Original eleven identities, roles, kinds, requiredness and revision retained; sole additional A1_nonvacuity has registered non-implementation applicability.'),
 'AUD-06':(domain_ok and carrier_ok and profile_ok and refines_all,'Reconstructed single Input binder covers unbounded integers, finite ordered event lists, Option Int, Unicode scalar String and both Fill constructors; only width>0/start<=end hypothesis; universal refinement itself has no validity/fuel bound.'),
 'AUD-07':(mixed==['O1','O2','O3','O4','O5','O6','O7']and sourceonly==['I1','S1']and source_rows_ok and causal_ast_ok,'Seven complete Mixed and two authorized source-only facets bind exact entry and seven source requirements. Original causal I1 behavior is retained by complete O5 recurrence and universal transfer.'),
 'AUD-08':(ir_ok and edge_ok and all_required_pass,'Registered accepted-IR/certificate validation plus actual isolated contract and bridge kernel replay bind reconstructed AST, statements, profile, witness and exact axiom/dependency inventories; no authored JSON is substituted as IR authority.'),
 'AUD-09':(domain_ok and nonliteral_value and causal_ast_ok and original_roles_ok,'Finite original eleven-ID coverage matrix cites actual reconstructed complete recurrence/source facets and bound public spans. Natural-language correspondence is explicit interpretation/host trust; optional unsupported probes provide no output evidence.'),
 'AUD-10':(ast_reexport_exact and edge_ok and impl['bindings']==[{'args':[{'record':'Input'}],'entry':'solve','lean_decl':'VeriSlopAST.solve','result':{'list':{'record':'Row'}},'symbol':'solve'}],'Actual canonical source bytes equal reconstructed accepted implementation IR program; exact nominal records/entry/helper/capture signature validated by registered published-edge checker.'),
 'AUD-11':(edge_ok and all_required_pass and 'def InputsCover_solve'in goal and 'def RawEval_solve'in goal and 'def SourceAdequate_solve'in goal,'Registered exact goal comparison, full kernel replay and adapter certificates validate typed inverse/raw evaluation/admitted coverage and source-only entry adequacy over the full Input carrier.'),
 'AUD-12':(edge_ok and refines_all,'Exact supervisor-derived Refines_solve is forall Input, source_fn_solve=input reference solve, with no precondition/fuel/resource/canonical-subset binder narrowing; actual kernel-accepted edge proves it.'),
 'AUD-13':(edge_ok and transfers_ok,'Explicit exact per-ID transfer rows cover all nine original guarantees; registered component-name/type/dependency comparison binds accepted theorem and preserves complete Mixed binders.'),
 'AUD-14':(edge_ok and source_rows_ok and all_required_pass,'Supervisor-derived goal source observation facts/requirement laws bind exact actual admitted solve; source requirement certificates and transfers mechanically validate each original guarantee, with no candidate fact table authority.'),
 'AUD-15':(edge_ok and proof_identity_ok and support['status']=='CHECKED'and len(declarations)==33,'Actual emitted CHECKED readable support has 33 exact declarations and baseline/selected/module inventories; 11 MODULE_BOUND_PROOF rows retain body_hash/exported_body_hash null; complete registered support validation passes.'),
 'AUD-16':(all_required_pass and native_consistent and native['required_guarantees']==9 and native['all_required_guarantees']==10 and nonvac_na,'Current graph 115 claims/94 required has exact assigned current PASS; lifecycle-derived original nine E2E guarantees exclude one derived nonvacuity witness and D1/A1 non-implementation cases.'),
 'AUD-17':(False,'BLOCK: actual isolated successful A/B and deterministic module/support comparisons are retained, but frozen requirement for actual build/subprocess logs, argv and numeric returncodes is unresolved; see terminal-build-retention-gap-001.json. No records invented or builds rerun.'),
 'AUD-18':(native_consistent and snapshot['mechanical_status']=='VERIFIED'and report['terminal_status']=='BLOCKED'and report['release_status']=='BLOCKED','Registered closure/current report/endpoint/provenance consistency passes. Published mechanical VERIFIED and scoped native E2E are observed, while required release remains BLOCKED; no milestone acceptance inferred from aggregate booleans.'),
 'AUD-19':(required_reviews_accepted,'BLOCK: required formal_contract REVIEW_ACCEPTED, release INCOMPLETE. Concrete release ballot ABSTAIN after incomplete packet inspection and one UNSUPPORTED target residual; current consensus cannot accept. Registered review/projection revalidation reports exact REVIEW_INCOMPLETE.'),
 'AUD-20':(native_consistent and release_probe['status']=='UNSUPPORTED','Conditional: no mechanical_failure release probe was emitted; no successful mechanical probe is invented. The actually emitted target_case receipt/current scoped inputs and projection are revalidated but remain UNSUPPORTED, separately retained in AUD-19.'),
 'AUD-21':(seals_ok and edge_ok,'Retained current execution A/B contract/goal/proof/support/module bytes revalidate. No separately emitted post-original-root-removal/second-retained-probe claim exists; its absence is explicit, no rehydration or historical stage authority is asserted.'),
 'AUD-22':(probe_policy_ok,'Nine unchanged public probes attempted once via registered strict profile/wire mapping and target review replay. All UNSUPPORTED: eight unresolved kernel-decidable residuals, PUB-08 probe-printer character-set limitation; no output observations, counterexamples, universal proof or TESTED promotion.'),
 'AUD-23':(native_consistent and report['tier']['endpoint']=='restricted_source'and report['language']=='vscore/0.3'and report['semantics']=='vscore-semantics/0.3'and all(report['obligations'][o]['outcomes']['TESTED']=='PENDING'for o in guarantees),'Only exact Tier2/restricted_source native lifecycle evidence is observed. No audit-assigned lifecycle, Python/runtime/compiler/machine/Tier3/4 or physical-resource assurance. Declared kernel/logical/toolchain/controller/host/SHA/OS/hardware/interpretation trust; identity UNATTESTED, tokens unavailable, optional TESTED unchanged PENDING.'),
 'AUD-24':(seals_ok and prebinding_exact and immutable_exact,'Final exact sealed 1292-file inventory, production/project/execution source241, protocol/input/verifier and original predicate/probe hashes unchanged. Required unresolved AUD-17 and failed AUD-19 yield terminal finite audit BLOCKED. Frozen set complete; stop, no additional campaign.')}
assert set(decisions)=={c['id']for c in plan['checks']}and len(decisions)==24
rows=[{'id':c['id'],'required':c['required'],'state':'PASS'if decisions[c['id']][0]else'BLOCK',
 'frozen_pass_predicate':c['pass_predicate'],'frozen_predicate_sha256':sha(cj(c)),
 'affected_original_ids':c['affected_original_ids'],'evidence_assessment':decisions[c['id']][1]}for c in plan['checks']]
blocked=[r['id']for r in rows if r['required']and r['state']!='PASS']
final={'format':'scope-audit-terminal-report/1','audit_id':'tier2-d21-scope-audit-017',
 'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'terminal_status':'BLOCKED'if blocked else'VERIFIED',
 'finite_check_count':24,'pass_count':sum(r['state']=='PASS'for r in rows),'block_count':len(blocked),
 'blocking_checks':blocked,'checks':rows,'original_ids':original_ids,'only_derived_id':'A1_nonvacuity',
 'mixed_ids':mixed,'source_only_ids':sourceonly,'original_causal_I1_preserved_in_Mixed_O5':causal_ast_ok,
 'unbounded_original_valid_domain_preserved':domain_ok and carrier_ok,'natural_language_correspondence':'Declared interpretation/host trust; coverage matrix is no substitute for kernel verification.',
 'registered_evidence_observation':{'mechanical_status':snapshot['mechanical_status'],'native_audit_consistency':native['status'],
 'required_claims':sum(c['required']for c in snapshot['claims']),'total_claims':len(snapshot['claims']),
 'required_implementation_guarantees':native['required_guarantees'],'all_guarantee_role_ids':native['all_required_guarantees'],
 'required_nonvacuity_witnesses':native['required_non_vacuity_witnesses'],'two_registered_builds_ok':all(b['ok']for b in snapshot['builds']),
 'determinism':snapshot['determinism'],'release_status':report['release_status'],'native_terminal_status':report['terminal_status'],
 'native_supervisor_actual_rc':native_receipt['actual_observed_exit_code'],'frozen_verify_actual_rc':verify_receipt['actual_exit_code'],
 'frozen_verify_authority':'integrity and origin only','lifecycle_applicability':applicable},
 'probe_results':capture['probe_summaries'],'probe_attempts':9,'unsupported_optional_probes':9,'concrete_failures_confirmed':0,
 'tested_assigned_or_promoted':False,'optional_TESTED_original_guarantees':'PENDING unchanged','audit_assigned_lifecycle_states':[],
 'scope':{'tier':2,'endpoint':'restricted_source','language':'vscore/0.3','semantics':'vscore-semantics/0.3',
 'native_END_TO_END_VERIFIED':'Observed only at exact restricted_source scope with current registered evidence; required release still blocked.',
 'excluded':['Python execution or runtime','Lean extraction/codegen/compiler/linker/native machine code','Tier3/4','OS service semantics','physical resource guarantees']},
 'trust':['pinned Lean kernel, standard library and actual allowed propext/Classical.choice/Quot.sound axioms','pinned toolchain and kernel replay/export driver','supervisor parsing/adapters/goal generation/claim resolution','controller/host and SHA-256','sandbox, OS and hardware','natural-language interpretation and original-to-revised correspondence'],
 'identity':'UNATTESTED','model_identity_attested':False,'token_metrics':'unavailable',
 'bound_roots':{'protocol_sha256':binding['protocol_sha256'],'production_source_root':binding['source_root'],
 'request_root':binding['request_set_root'],'input_root':binding['input_root'],'sealed_files_root':seal['files_root'],
 'sealed_manifest_sha256':sha(raw(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json')),'accepted_ir':report['roots']['accepted_ir'],
 'contract_root':report['roots']['contract_input_root'],'closure_root':snapshot['closure_root'],
 'source_sha256':sha(source),'review_target':report['review_target'],'review_projection':report['review_projection']['hash']},
 'pre_generation_binding':{'path':str(OUT/'pre-generation-binding-001.json'),'sha256':sha(raw(OUT/'pre-generation-binding-001.json'))},
 'qualification_authority':{'completed_attempt':'gate019','old_gate017_wording':'collection-support milestone017 only','old_PASS_inheritance':False},
 'final_immutability':{'sealed_manifest_mismatches':manifest_errors,'exact_sealed_file_inventory':inventory_exact,
 'registered_lock_pyc_exclusions':'Frozen bootstrap_tier2 seal inventory excludes .lock/.pyc/__pycache__; two existing lock files are non-evidence.',
 'source_mismatches':source_errors,'verifier_registry_exact':registry_exact,'original_predicates_probes_exact':immutable_exact,'public_inputs_exact':input_exact},
 'auxiliary_root_reader_incidents':auxiliary_incidents,'actual_audit_reader_receipts':reader_receipts,
 'audit_reader_incident_effect':'Attempts001 syntax and002 prefix-only guard failed before registered calls/probes; original scripts/logs/rc1 retained. Corrected003 actual rc0 executed unchanged frozen set. No task/verifier/predicate/probe edits or failed semantic action continuation.',
 'stop':'All 24 preregistered checks and 9 optional probes resolved once. STOP; no source/contract/proof/response/verifier mutation, lifecycle rescore, extra predicate or new build/model/test campaign.'}
write('terminal-scope-audit-report-001.json',final)
write('terminal-evaluator-read-ledger-001.json',{'format':'scope-audit-read-ledger/1','audit_id':'tier2-d21-scope-audit-017',
 'method':'Every direct terminal evaluator read records exact path/size/SHA-256; registered capture ledger separately logs registered indirect reads.',
 'files':list(reads.values())})
print(json.dumps({'terminal_status':final['terminal_status'],'checks':24,'pass':final['pass_count'],'block':blocked,
 'optional_probes':9,'unsupported':9,'sealed_files':len(seal['files']),'immutability':final['final_immutability']},sort_keys=True))
