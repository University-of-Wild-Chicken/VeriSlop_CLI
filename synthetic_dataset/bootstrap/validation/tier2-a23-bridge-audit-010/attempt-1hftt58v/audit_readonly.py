from pathlib import Path
import sys,json,datetime
AUDIT=Path(__file__).resolve().parent
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-010'
PROJECT=STAGE/'project'
RUN=STAGE/'run'
PKG=RUN/'artifacts/A23/verislop/package'
BUNDLE=PKG/'bridges/implementation'
SEM=BUNDLE/'semantic/edge-6c6b7f3cad1aebbacfb2127f'
sys.path.insert(0,str(PROJECT))
from verislop import canonical,export
from verislop.package import Package
from verislop.bridges import vscore3_checker as K
from verislop.targets import vscore3_target as T
checks=[]
inputs={}
def write(name,obj): (AUDIT/name).write_bytes(canonical.dumps(obj))
def check(name,ok,detail=None):
 checks.append({'check':name,'passed':bool(ok),'details':detail})
 if not ok: raise AssertionError(name)
def capture(path):
 path=Path(path).resolve()
 rel=path.relative_to(STAGE).as_posix()
 data=path.read_bytes()
 out=AUDIT/'inputs'/rel
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_bytes(data)
 inputs[rel]={'sha256':canonical.digest(data),'size':len(data),'observed_path':str(path)}
 return data
p=Package(PKG)
ir,irhash,acc,ds=export.verified_ir(p)
check('accepted contract still exactly current',not ds,[d.as_dict() for d in ds])
ctx=K.load_context(BUNDLE,'implementation','reference-to-vscore')
spec=K.derive_goal(ctx)
accepted,pending,ds=K.verify_published(p,'implementation',rebuild=False)
check('registered stored semantic certificate validation without rebuilding',not ds and not pending and len(accepted)==1,[d.as_dict() for d in ds])
cert=canonical.loads(capture(SEM/'certificate.json'))
check('accepted contract/IR bridge identity',ctx.plan['accepted_ir']==irhash==cert['accepted_ir'] and ctx.plan['acceptance_certificate']==canonical.digest_file(PKG/ir['acceptance_certificate_ref'])==cert['acceptance_certificate'])
check('semantic evidence covers all four required implementation guarantee IDs',{x['id'] for x in cert['obligations']}=={'O1','O2','S1','S2'})
check('stored complete Goal exactly derived from accepted/frozen inputs',capture(SEM/cert['goal']['path'])==spec.text.encode())
check('fresh supervisor source preview exactly published Goal',capture(PKG/'agents/vscore-attempts/source-2/VeriSlopBridgeGoal.lean')==spec.text.encode())
source=capture(PKG/'implementation/program.vscore.json')
check('materialized source exact frozen source slot',source==ctx.inputs['source'][1])
check('materialized source exact source candidate bytes',capture(PKG/'agents/vscore-attempts/source-2/program.vscore.json')==source)
check('exact canonical source identity',canonical.digest(source)==cert['inputs']['source']['sha256']=='sha256:fc3e6141c0bead91c8e7a5561f9bc670abf833559d4ae0518fb32cb5bf437125')
program=canonical.loads(source)
v=lambda i:{'tag':'var','index':i}
f=lambda name,i:{'tag':'project','field':name,'value':v(i)}
b=lambda tag,l,r:{'tag':tag,'left':l,'right':r}
expected_body={'tag':'list_sum','value':{'tag':'list_map','value':{'tag':'list_range','value':{'tag':'int_to_nat','value':f('n',0)}},'body':b('int_fdiv',b('add',b('mul',f('a',1),{'tag':'nat_to_int','value':v(0)}),f('b',1)),f('m',1))}}
expected_program={'language':'vscore/0.3','profile':'data-pipeline/0.3','declarations':[{'tag':'record','id':'Input','fields':[{'id':name,'type':'int'} for name in ['n','m','a','b']]}],'helpers':[],'entries':[{'id':'solve','params':[{'record':'Input'}],'result':'int','body':expected_body}]}
check('complete signed floor-sum implementation syntax with exact ordered carrier',program==expected_program)
check('single canonical admitted solve entry with exact signature',len(spec.symbols)==1 and spec.symbols[0].symbol=='solve' and spec.symbols[0].entry=='solve' and spec.symbols[0].lean_decl=='VeriSlopAST.solve' and spec.signatures==[{'id':'solve','params':[('record','Input')],'result':'int'}])
ref=spec.expected['Refines_solve']['value']
check('unrestricted universal refinement over exact accepted record',ref['pi']['type']=={'const':['VeriSlopAST','Input'],'levels':[]} and ref['pi']['body']['app'][0]['const']==['Eq'] and ref['pi']['body']['app'][2]['app'][0]['const']==['VeriSlopBridgeGoal','source_fn_solve'] and ref['pi']['body']['app'][3]['app'][0]['const']==['VeriSlopAST','solve'])
def edge_leaves(x):
 if x.get('app',[{}])[0].get('const')==['And']:
  return edge_leaves(x['app'][1])+edge_leaves(x['app'][2])
 return [x['const'][-1]]
check('full EdgeProp retains every required component',edge_leaves(spec.expected['EdgeProp']['value'])==['SourceParses','SourceChecks','InputsCover_solve','RawEval_solve','Refines_solve','SourceAdequate_solve','Transfer_O1','Transfer_O2','Transfer_S1','Transfer_S2'])
check('source adequacy exact compiler entry identity',spec.expected['SourceAdequate_solve']['value']['app'][0]['const']==['VSCore3','SourceFactsAdequate'] and spec.expected['SourceAdequate_solve']['value']['app'][3]=={'lit':{'str':'solve'}})
goal=spec.text
for phrase in ['theorem compiled_ok','theorem find_solve','def source_fn_solve','entry_solve.run (adapter_1.to x__0, ())','def RawEval_solve : Prop := ∀','def InputsCover_solve : Prop := ∀ args, VSCore3.ArgsTyped entry_solve args → ∃','theorem adapter_1_decode_encode','from_to :=','to_from :=','VSCore3.RecordLayout.cons "n"','VSCore3.RecordLayout.cons "m"','VSCore3.RecordLayout.cons "a"','VSCore3.RecordLayout.cons "b"','VSCore3.encodeEnv_decodeEnv','adapter_1.to_from','VSCore3.exactSourceFacts profile rawProgram "solve"','VSCore3.exactSourceFacts_adequate compiled_ok find_solve']:
 check('exact compiler/raw transport/scaffold '+phrase,phrase in goal)
check('record adapter fields preserve all four exact signed fields',[a.sort for a in spec.adapters]==['Int',{'record':'Input'}] and all(('VeriSlopAST.Input.'+x) in spec.adapters[1].definition for x in ['n','m','a','b']))
for oid in ['O1','O2','S1','S2']:
 row=next(x for x in cert['obligations'] if x['id']==oid)
 check('per-ID exact accepted theorem/statement transfer '+oid,row['accepted_statement_hash']==ir['obligations'][oid]['formal']['statement_hash'] and row['accepted_theorem']==ir['obligations'][oid]['formal']['lean_symbol'] and row['transfer']=='VeriSlopBridgeGoal.Transfer_'+oid and row['transfer_theorem']=='VeriSlopBridgeGoal.transfer_'+oid)
 check('per-ID exact accepted source facets '+oid,ctx.obligations[oid]['source_facets'][0]['requirements']==[{'tag':'entry','file':'program.vscore.json','entry':'solve','arity':1}]+[{'tag':x} for x in ['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']])
 check('per-ID value applicability '+oid,(ctx.obligations[oid]['formula'] is not None)==(oid in ['O1','O2']))
 check('per-ID generated theorem actually applies accepted theorem '+oid,'have haccepted := @'+row['accepted_theorem'] in goal)
link=canonical.loads(capture(PKG/'bridges/link.json'))
check('linked exact original four guarantee scope',{x['id'] for x in link['covered']}=={'O1','O2','S1','S2'} and all(x['accepted_statement_hash']==ir['obligations'][x['id']]['formal']['statement_hash'] for x in link['covered']))
check('exact bound source endpoint/link carrier',link['source']=={'path':'implementation/program.vscore.json','sha256':canonical.digest(source)} and link['bindings'][0]['implementation_object']['entry']=='solve' and link['endpoint_node']=='vscore-program')
mat=canonical.loads(capture(PKG/'implementation/materialization.json'))
check('materialization source/profile/program identity',mat['source_hash']==canonical.digest(source) and mat['program']==program and mat['proposition_hash']==cert['proposition_hash'] and mat['profile_hash']==cert['inputs']['profile']['sha256'])
observations=[canonical.loads(capture(SEM/x['path'])) for x in cert['builds']]
check('stored two isolated native build observations identical',observations[0]==observations[1])
check('stored native compile results all PASS with zero sorries',all(x['ok'] and x['sorries']==0 and x['errors']==[] for obs in observations for x in obs['compiles'].values()))
check('stored kernel replay observes full staged declarations',all(obs['replayed_constants']==3113 for obs in observations))
check('proof axiom inventory exactly permitted strict policy',cert['theorem']['axioms']==['Classical.choice','Quot.sound','propext'])
check('certificate explicitly does not assign END_TO_END_VERIFIED',cert['semantic_acceptance'] is True and cert['assigns_end_to_end_verified'] is False)
proof=capture(BUNDLE/'candidate-inputs/Proof.lean').decode()
check('candidate proves exact universal EdgeProp via compiler-based refinement','theorem edge : VeriSlopBridgeGoal.EdgeProp' in proof and 'apply VeriSlopBridgeGoal.edge_of_refines' in proof and 'intro x' in proof and 'with_unfolding_all rfl' in proof and 'sorry' not in proof and 'axiom ' not in proof)
check('candidate proof unchanged from fresh proof role',capture(PKG/'agents/vscore-attempts/source-2/proofs/1.lean')==proof.encode())
for path in [PKG/'agents/vscore-attempts/source-2/checks/source.json',PKG/'agents/vscore-attempts/source-2/checks/proof-1.json',PKG/'bridges/bindings.json',BUNDLE/'plan.json',BUNDLE/'artifacts.json',BUNDLE/'preparation-certificate.json',BUNDLE/'import-receipt.json',PKG/'accepted/accepted-ir.json',PKG/ir['acceptance_certificate_ref'],RUN/'preregistration.json',RUN/'protocol.json',RUN/'requests/A23/source-policy.json',RUN/'requests/A23/revised-prompt.txt',RUN/'requests/A23/original-prompt.txt',RUN/'requests/A23/original-metadata.json']:
 capture(path)
for slot in ctx.slots.values():
 check('manifest-bound imported/candidate artifact '+slot['slot_id'],canonical.digest(capture(BUNDLE/slot['path']))==slot['sha256'])
for path in SEM.rglob('*'):
 if path.is_file():capture(path)
for module,data in T.library_sources().items():
 path=PROJECT/'verislop/lean'/(module.replace('.','/')+'.lean')
 check('exact registered normative library source '+module,capture(path)==data)
for name in ['verislop/targets/vscore3_target.py','verislop/bridges/vscore3_checker.py','verislop/targets/vscore3_source.py','verislop/source_policy.py','verislop/source_contract.py']:
 capture(PROJECT/name)
protocol=canonical.load_file(RUN/'protocol.json')
check('all frozen generic production bytes unchanged',all(canonical.digest_file(PROJECT/k)==v for k,v in protocol['source_files'].items()))
check('exact source-policy bytes copied into bridge',capture(BUNDLE/'request/source-policy.json')==capture(PKG/'request/source-policy.json')==capture(RUN/'requests/A23/source-policy.json'))
check('observed immutable input bytes stable through snapshot',all(canonical.digest_file(STAGE/k)==v['sha256'] for k,v in inputs.items()))
mechanical={'closure_current_published':(PKG/'closure/current.json').exists(),'report_published':(PKG/'report.json').exists(),'review_release_summary_published':(PKG/'reviews/release-summary.json').exists()}
if mechanical['closure_current_published']:capture(PKG/'closure/current.json')
write('checks.json',checks)
write('derived-statements.json',spec.expected)
write('input-manifest.json',{'format':'independent-readonly-audit-inputs/0.1','files':inputs})
write('stored-semantic-validation.json',{'rebuild':False,'accepted':accepted,'pending':pending,'diagnostics':[d.as_dict() for d in ds]})
write('audit.json',{'format':'independent-readonly-bridge-audit/0.1','observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':str(STAGE),'task':'A23','phase':'published semantic source bridge','source_root':protocol['source_root'],'accepted_ir_hash':irhash,'source_hash':canonical.digest(source),'goal_hash':cert['goal']['sha256'],'proposition_hash':cert['proposition_hash'],'semantic_certificate_hash':canonical.digest_file(SEM/'certificate.json'),'semantic_edge_root':cert['semantic_edge_root'],'checks_passed':len(checks),'input_files':len(inputs),'concrete_defects_found':[],'conclusion':'No concrete scope, source-expression, adapter, raw-coverage or transfer defect found in inspected exact current artifacts. Registered stored semantic certificate authenticates two native builds of full compiler-bound universal refinement and all four accepted property transfers.','scope_observations':['The sole source entry is solve(Input)->Int with n,m,a,b signed Int in exact accepted order, and its body is sum(map(Int.fdiv(a*Int.ofNat(i)+b,m), range(Int.toNat(n)))).','Refines_solve quantifies every typed accepted Input, with no extra assumptions. O1/O2 transferred propositions retain exactly 0<=n<=500 and m>0; signed a,b remain unbounded.','Adapter inverses and both raw laws are exact canonical record/product/Int laws. InputsCover covers every raw argument list with successful exact typed decoding; RawEval ties encoded inputs/output to actual evalEntry and compiled entry.run.','SourceFactsAdequate binds exact compile/find success, parameter/result representation laws, typed coverage/totality, unchanged inputs, determinism, empty effect trace, no I/O or floating point, pure result shape and the normative evaluator result.','O1/O2 and S1/S2 retain the exact required source policy and accepted theorem/statement identities; all four are explicit EdgeProp conjuncts.','Published native observations agree, report 3113 replayed constants and zero sorries, and use only the strict policy permitted axioms.'],'mechanical_observed':mechanical,'limits':['Natural-language correspondence is an independent trusted reading.','No new Lean/kernel/closure/native driver/model call was executed; existing registered stored evidence was inspected and authenticated with rebuild=False.','Source/effects claims concern the normative restricted evaluator only, not a host interpreter/compiler/machine code.','This receipt does not independently establish final mechanical closure, END_TO_END_VERIFIED or release outcome. Final sealed claim graph and reviews require a separate terminal audit.','Any precheck proof_checked flag was not treated as semantic authority; the published registered certificate and bound native observations were inspected.','This audit receipt is outside the frozen cohort and is not lifecycle authority.']})
for q in AUDIT.rglob('*'):
 if q.is_file():q.chmod(0o444)
for q in sorted(AUDIT.rglob('*'),reverse=True):
 if q.is_dir():q.chmod(0o555)
AUDIT.chmod(0o555)
print(json.dumps({'audit':str(AUDIT/'audit.json'),'audit_sha256':canonical.digest_file(AUDIT/'audit.json'),'checks':len(checks),'input_files':len(inputs),'mechanical_observed':mechanical},sort_keys=True))
