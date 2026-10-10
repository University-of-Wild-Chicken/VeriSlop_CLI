from __future__ import annotations
import sys, os, json, hashlib, shutil, datetime
from pathlib import Path

ROOT = Path('/home/augustus/VeriSlop_CLI')
STAGE = ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-015'
RUN = STAGE/'run'
PROJECT = STAGE/'project'
PKG = RUN/'artifacts/D21/verislop/package'
OUT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(PROJECT))
from verislop import canonical, dsl, formal_frontend
from verislop.targets import python_target, vscore3_source

def sha(b): return 'sha256:' + hashlib.sha256(b).hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(canonical.dumps(obj))
checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    if not ok:
        save(OUT/'checks.json',checks)
        raise AssertionError(name)
def capture(p,rel):
    q=OUT/'snapshots'/rel; q.parent.mkdir(parents=True,exist_ok=True)
    b=p.read_bytes(); q.write_bytes(b); return sha(b)

seal=load(RUN/'EVIDENCE-MANIFEST.json')
check('exact_seal_count',len(seal['files'])==435)
check('two_seals_identical',(RUN/'EVIDENCE-MANIFEST.json').read_bytes()==(RUN/'BOOTSTRAP-EVIDENCE-MANIFEST.json').read_bytes())
for rel,h in seal['files'].items():
    p=RUN/rel
    check('sealed_file:'+rel,p.is_file() and not p.is_symlink() and sha(p.read_bytes())==h)
    capture(p,Path('cohort')/rel)
check('exact_seal_root',sha(canonical.dumps(seal['files']))==seal['files_root']=='sha256:9e27c9f11652f18eea72538d0ecf619db9ea7bfa2dc9afda0e43eb28f57c8c55')
for n in ('EVIDENCE-MANIFEST.json','BOOTSTRAP-EVIDENCE-MANIFEST.json'): capture(RUN/n,Path('cohort')/n)
protocol=load(RUN/'protocol.json'); prereg=load(RUN/'preregistration.json')
currency=[]
for rel,h in protocol['source_files'].items():
    p=PROJECT/rel; ep=RUN/'execution-source'/rel
    row={'path':rel,'expected':h,'project':sha(p.read_bytes()),'execution':sha(ep.read_bytes())}
    currency.append(row)
check('all_238_frozen_and_execution_source_bytes',len(currency)==238 and all(x['expected']==x['project']==x['execution'] for x in currency))
check('production_source_root',sha(canonical.dumps(protocol['source_files']))==protocol['source_root']==prereg['source_root']=='sha256:e3b90927196de6b17dc50fa350b1b52d7a8c15a1233a73955525e1028d32e037')
save(OUT/'source-currency.json',currency)
consulted=['verislop/agents.py','verislop/formal_frontend.py','verislop/dsl.py','verislop/reify.py','verislop/contract_refutation.py','verislop/contract_values.py','verislop/targets/python_target.py','verislop/targets/vscore3_target.py','verislop/targets/vscore3_source.py','verislop/targets/vscore3_check.py','verislop/autonomous.py','verislop/lean/VSCore3/Transport.lean','verislop/lean/VSCore3/Typed.lean','verislop/lean/VSCore3/Syntax.lean','verislop/lean/VSCore3/Decode.lean','docs/bootstrap-tier2-data.md']
source_hashes={f:capture(PROJECT/f,Path('frozen-project')/f) for f in consulted}
verify_path=ROOT/'validation/tier2-native-boundary-gate-015/terminal-seal-verification.json'
vh=capture(verify_path,Path('external/terminal-seal-verification.json')); verify=load(verify_path)
check('stored_normal_frozen_verify',verify['status']=='PASS' and verify['milestone_authority'] is False and verify['fresh_calls']==7 and verify['transport_errors']==0)

result=load(RUN/'BOOTSTRAP-RESULT.json'); row=load(RUN/'artifacts/D21/verislop/result.json'); report=load(PKG/'report.json'); meta=load(PKG/'package.json')
check('terminal_blocked_complete',result['status']=='BLOCKED' and result['complete'] and result['verified_tasks']==0 and row['status']=='BLOCKED' and row['worker_exit_code']==2 and not row['successful_task'])
check('aggregate_row_exact',result['rows']==[row])
check('native_report_agreement',all(row['native'][k]==report[k] for k in ('mechanical_status','release_status','builds','determinism')) and row['native_terminal_status']==report['terminal_status']=='BLOCKED')
check('formalization_stop',row['cli_stopped_at']=='formalize' and meta['completed_stages']==['interpret'] and [x['stage'] for x in meta['stage_history']]==['interpret','formalize'])
check('no_positive_later_artifacts',all(not (PKG/x).exists() for x in ('contract/challenge','accepted','implementation','bridges','semantic','closure/current.json','closure/manifest.json')))
check('no_build_or_mechanical_claim',report['builds']==[] and report['mechanical_result'] is None and row['native']['mechanical_claims']==[] and report['determinism']['compared']==[])
check('reviews_not_run',report['review']['checkpoints']=={'formal_contract':'REVIEW_NOT_RUN','release':'REVIEW_NOT_RUN'})
check('blocking_closed_claim_codes',set(x['code'] for x in report['blocking_reasons'])=={'ORPHAN_CLAIM','REVIEW_NOT_RUN','VERIFIER_NOT_RUN'})
ids={'D1','A1','O1','O2','O3','O4','O5','O6','O7','I1','S1'}; guarantees=ids-{'D1','A1'}
check('required_identity_states',set(report['obligations'])==ids and all(o['required'] and o['outcomes']['INTERPRETED']=='PASS' and o['outcomes']['FORMALIZED']=='FAIL' and o['outcomes']['TYPECHECKED']=='PENDING' for o in report['obligations'].values()))
check('all_nine_e2e_unproved_pending',all(report['obligations'][i]['outcomes']['END_TO_END_VERIFIED']=='PENDING' and report['obligations'][i]['outcomes']['PROVED']=='PENDING' and report['obligations'][i]['outcomes']['LINKED']=='PENDING' for i in guarantees))
check('no_unearned_domain_witness',row['native']['required_non_vacuity_witnesses']==0 and row['native']['required_guarantees']==9 and row['native']['required_e2e_passed']==0)
events=[json.loads(x) for x in (PKG/'events.jsonl').read_text().splitlines()]
check('verify_attempt_honestly_blocked',any(x.get('phase')=='verify' and x.get('type')=='stage_started' for x in events) and events[-1]['type']=='run_finished' and events[-1]['outcome']=='BLOCKED')
save(OUT/'terminal-observations.json',{'result':result,'native_report':report,'package':meta,'events':events})

mail=RUN/'artifacts/D21/verislop/mailbox'
requests=sorted(mail.glob('request-*.json')); responses=sorted(mail.glob('response-[0-9][0-9][0-9][0-9].json')); receipts=sorted(mail.glob('response-receipt-*.json'))
check('seven_literal_origin_rows',len(requests)==len(responses)==len(receipts)==7)
authors=[]; origin_rows=[]
for reqpath,respath,receiptpath in zip(requests,responses,receipts):
    req,res,rec=load(reqpath),load(respath),load(receiptpath)
    carrier=Path(res['carrier_path'])
    check('origin_binding:'+req['request_id'],res['request_id']==rec['request_id']==req['request_id'] and rec['request_sha256']==res['request_sha256']==sha(reqpath.read_bytes()) and rec['response_sha256']==sha(respath.read_bytes()) and rec['text_sha256']==sha(res['text'].encode()) and rec['output_bytes']==len(res['text'].encode()) and res['carrier_sha256']==sha(carrier.read_bytes()) and res['fork_turns']=='none' and res['model_identity_attested'] is False)
    authors.append(res['agent_task_id']);origin_rows.append({'request':req['request_id'],'purpose':req['purpose'],'instance':req['instance'],'author':res['agent_task_id'],'request_sha256':rec['request_sha256'],'response_sha256':rec['response_sha256'],'text_sha256':rec['text_sha256'],'carrier_sha256':res['carrier_sha256'],'model_identity_attested':False})
check('seven_unique_fresh_roles',len(set(authors))==7 and result['fresh_calls']==result['fresh_agents']==7 and result['transport_errors']==0 and not result['model_identity_attested'])
check('only_interpreter_formalizer_critic',[(x['purpose'],x['instance']) for x in origin_rows]==[('interpret','interpreter/1'),('formalize','formalizer/1'),('critic','critic/formalize/1/R0/group-1/critic/1'),('formalize','formalizer/2'),('critic','critic/formalize/2/R0/group-1/critic/1'),('formalize','formalizer/3'),('critic','critic/formalize/3/R0/group-1/critic/1')])
save(OUT/'origin-observations.json',origin_rows)

attempts=[]
for n in (1,2,3):
    ft=load(next((PKG/'agents/transcripts').glob(f'*-{n:04d}-formalizer_{n}.json')))
    ct=load(next((PKG/'agents/transcripts').glob(f'*-{n:04d}-critic_formalize_{n}_*.json')))
    proposal=json.loads(ft['response']); critique=json.loads(ct['response']); packet=json.loads(ct['user'])
    snap=next((PKG/'agents/memory/snapshots').glob(f'{6*n+2:08d}-*.json'))
    ss=load(snap); checked=load(PKG/ss['artifacts'][0]['blob_ref']['path'])
    check('negative_capability_only:'+str(n),proposal['encoding']=='verislop.formalizer-capability-gap/0.1' and set(proposal['obligation_ids'])==ids and set(proposal)=={'encoding','obligation_ids','gaps'})
    check('untrusted_diagnostic_only:'+str(n),len(packet['diagnostics'])==1 and packet['diagnostics'][0]['code']=='UNSUPPORTED_CAPABILITY' and packet['diagnostics'][0]['details']['untrusted_report'] is True and packet['capability_report']==proposal)
    check('diagnostic_indexed_no_actual_probe:'+str(n),critique['verdict']=='REPAIR' and critique['counterexamples']==[] and len(critique['corrections'])==1 and critique['corrections'][0]['diagnostic_index']==0 and checked['status']=='REPAIR' and checked['milestone_authority'] is False and checked['results'][0]['attempted_checks']==[] and checked['results'][0]['checked'] is None)
    attempts.append({'attempt':n,'proposal':proposal,'critic':critique,'native_critique':checked,'diagnostics':packet['diagnostics'],'registered_formalizer_language':packet['registered_formalizer_language'],'probe_interface':packet['probe_interface'],'raw_formalizer_response':packet['raw_formalizer_response']})
save(OUT/'formalization-attempts.json',attempts)
check('last_candidate_equals_last_capability',load(PKG/'contract/candidate/formalization.json')=={'capability_report':attempts[-1]['proposal']})
check('no_compile_or_bounded_refutation',load(PKG/'contract/candidate/statement-check.json')['compile'] is None and load(PKG/'contract/candidate/statement-check.json')['bounded_refutation'] is None)

draft=load(PKG/'draft.json'); records=[o for k in ('entities','preconditions','postconditions','invariants','safety_properties','liveness_properties','resource_constraints','error_semantics','explicit_non_goals') for o in draft.get(k,[]) if isinstance(o,dict) and 'id' in o]
check('eleven_interpreted_records_no_workflow_extra',len(records)==11 and {o['id'] for o in records}==ids and all(o['required'] for o in records))
save(OUT/'interpreted-scope.json',{'records':[{k:o[k] for k in ('id','role','kind','statement','scope','acceptance_criteria','dependencies','source_refs')} for o in records], 'category_review':draft['category_review']})
policy=load(PKG/'request/source-policy.json'); expected_props=['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']
check('nine_exact_policy_rows',set(policy['obligations'])==guarantees and all(v['file']=='program.vscore.json' and v['entry']=='solve' and v['arity']==1 and v['properties']==expected_props and v['value_required']==(k not in {'I1','S1'}) for k,v in policy['obligations'].items()))

# Unrelated finite host witnesses only. They are not kernel exports, task candidates,
# a D21 algorithm, a proof, or a substitute for native admission.
p=dsl.Profile.from_json({'profile_id':'AuditTone','dsl':dsl.ENCODING_V2,'enums':{'Tone':{'constructors':['amber','indigo'],'lean_decl':'Audit.Tone','lean_constructors':['Audit.Tone.amber','Audit.Tone.indigo']}},'symbols':{},'predicates':{}})
enum_sort={'enum':'Tone'}; variable={'tag':'var','index':0}; amber={'tag':'enum','sort':'Tone','constructor':'amber'}
dsl.check_sort(enum_sort,p); et=dsl.type_term(amber,[],p)
check('registered_executable_enum_sort_accepted',et==enum_sort)
values=dsl.finite_values(enum_sort,p)
wires=[python_target.encode_arg(v,enum_sort,p) for v in values]
check('enum_constructor_string_wire_roundtrip',wires==[{'str':'amber'},{'str':'indigo'}] and [python_target.decode_result(w,enum_sort,p) for w in wires]==values)
check('source_enum_value_type_accepted',vscore3_source.type_of({'Tone':['amber','indigo']},{},{},[],('enum','Tone','amber'))==('enum','Tone'))
eq={'tag':'eq','left':variable,'right':amber};dsl.type_formula(eq,[enum_sort],p)
check('enum_propositional_equality_accepted_but_not_decidable_shape',not dsl.decidable_shape(eq,[enum_sort],p))
rejections={}
for name,term in [('enum_bool_eq',{'tag':'bool_eq','left':variable,'right':amber}),('enum_decide_eq',{'tag':'decide','formula':eq})]:
    try:dsl.type_term(term,[enum_sort],p)
    except dsl.DSLError as e:rejections[name]={'exception':type(e).__name__,'message':str(e)}
    else:raise AssertionError(name+' unexpectedly admitted')
renderer=formal_frontend._Renderer(p,None)
try:renderer.sort(enum_sort)
except formal_frontend.FrontendError as e:rejections['preferred_frontend_enum_sort']={'exception':type(e).__name__,'message':str(e)}
else:raise AssertionError('frontend unexpectedly admits enum')
check('three_exact_host_rejections',len(rejections)==3)
guard={'tag':'or','left':{'tag':'eq','left':variable,'right':{'tag':'string','value':'amber'}},'right':{'tag':'eq','left':variable,'right':{'tag':'string','value':'indigo'}}}
dsl.type_formula(guard,['String'],p)
ev=dsl.Evaluator(p,{},lambda *_:[]) ; guard_out={x:ev.formula(guard,[x]).value for x in ['amber','indigo','ultraviolet','','AMBER','λ']}
check('string_carrier_exact_validity_guard',guard_out=={'amber':True,'indigo':True,'ultraviolet':False,'':False,'AMBER':False,'λ':False})
save(OUT/'generic-host-witnesses.json',{'authority':'Pure frozen-Python DSL/type/wire boundary checks only; no kernel invocation or task model/proof.','enum_profile':p.raw,'enum_sort':et,'finite_values':values,'constructor_string_wires':wires,'enum_equality_formula':eq,'host_rejections':rejections,'unrelated_exact_validity_guard':guard,'guard_observations':guard_out,'mathematical_scope':'By its expression, the valid String set is exactly equality to amber or equality to indigo; invalid carrier values remain outside that valid domain. Finite host observations above establish only the recorded evaluations.'})
save(OUT/'checks.json',checks)
print(json.dumps({'status':'CHECKS_PASS','checks':len(checks),'source_root':protocol['source_root'],'seal_root':seal['files_root'],'stored_verify_sha256':vh,'out':str(OUT)}))
