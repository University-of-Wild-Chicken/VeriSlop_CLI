"""Final read-only generic artifact audit. No native/Lean/model rerun or source mutation."""
from pathlib import Path
import datetime,json,sys,re,traceback
ROOT=Path('/home/augustus/VeriSlop_CLI');OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from verislop import canonical,contract,dsl,formal_frontend as ff,policy,reify,source_policy,review_projection,schemas
from verislop.exprjson import name_str,decl_hash,closure,constants,canon,app,const
from verislop.package import Package
from verislop.backends import vscore3,vscore3_closure
from verislop.bridges import vscore3_checker as checker
from verislop.targets import vscore3_source as source
from test_formal_frontend_enum_tier2 import SURFACE,REQUEST,PROPERTIES,RELATION
F=OUT/'fixture';P=F/'package';G=OUT/'gate';A=OUT/'retained';S=P/'bridges/implementation/semantic/edge-6c6b7f3cad1aebbacfb2127f'
rows=[]; inventories={};observations={}
def load(path):return canonical.load_file(path)
def check(name,condition,**evidence):
 q={'id':name,'ok':bool(condition),**evidence};rows.append(q)
 if not q['ok']:raise AssertionError(q)
def identity(x):
 if isinstance(x,bytes):return canonical.digest(x)
 if isinstance(x,set):x=sorted(x)
 return canonical.digest_json(x)
def equal(name,a,b):check(name,a==b,actual_hash=identity(a),expected_hash=identity(b))
def artifact(a,root,name):
 p=root/a['path'];check(name,p.is_file() and not p.is_symlink() and canonical.digest_file(p)==a['sha256'],path=str(p.relative_to(OUT)),expected=a['sha256']);return p
try:
 # Authenticate actual completed test invocation and every frozen current byte.
 freeze=load(G/'source-freeze.json');qual=load(G/'qualification-inputs.json');tests=load(G/'test-sources.json');gate=load(G/'run-result.json')
 check('gate-all131-success',gate['status']=='PASS' and gate['tests_run']==131 and gate['failures']==gate['errors']==gate['skipped']==0)
 check('gate-honest-zero-models',gate['fresh_model_calls']==0 and qual['model_calls']==0 and not qual['task_inputs'])
 check('gate-current-source-stable',gate['source_unchanged'] and gate['test_sources_unchanged'] and gate['source_root_before']==gate['source_root_after']==freeze['source_root'])
 equal('production-root-recomputed',canonical.digest_json(freeze['source_files']),freeze['source_root'])
 equal('test-root-recomputed',canonical.digest_json(tests),qual['test_root'])
 equal('qualification-production-root',qual['source_root'],freeze['source_root'])
 equal('qualification-frozen-inputs-complete',qual['source_hashes'],{**freeze['source_files'],**tests,'validation/tier2-native-boundary-gate-016/gate.py':canonical.digest_file(G/'gate.py')})
 check('qualification-frozen-production-reference',qual['engineering_freeze_hash']==canonical.digest_file(G/'source-freeze.json'))
 for name,h in qual['source_hashes'].items():
  check('current-source:'+name,canonical.digest_file(ROOT/name)==h,expected=h)
 equal('gate-actual-tested-source-map',gate['test_sources'],tests)
 stderr=(G/'gate.stderr.log').read_text();test_lines=[l for l in stderr.splitlines() if re.search(r'\.\.\. ok$',l)]
 check('gate-131-actual-ok-lines',len(test_lines)==131,observed=len(test_lines))
 # Complete capture member inventory, frozen source copies, current snapshot refs.
 cap=load(F/'capture.json');actual={str(p.relative_to(F)) for p in F.rglob('*') if p.is_file()}
 equal('capture-exact-file-inventory',actual,set(cap['files'])|{'capture.json'})
 for name,h in cap['files'].items():check('capture-member:'+name,canonical.digest_file(F/name)==h,expected=h)
 equal('capture-qualification-inputs',cap['source_hashes'],qual['source_hashes'])
 equal('capture-combined-input-root',cap['source_root'],canonical.digest_json(qual['source_hashes']))
 check('capture-does-not-inflate-early-status',cap['qualification'] is False and cap['stage_status']=='BUILT_PENDING_RETAINED')
 equal('capture-qualification-freeze-hash',cap['source_freeze_hash'],canonical.digest_file(G/'qualification-inputs.json'))
 for name,h in cap['source_hashes'].items():check('captured-registered-source:'+name,canonical.digest_file(F/'registered-sources'/name)==h,expected=h)
 package_manifest={str(p.relative_to(P)):canonical.digest_file(p) for p in sorted(P.rglob('*')) if p.is_file()};inventories['package']=package_manifest
 engineering=load(G/'engineering-validation.json')
 normalized_members={n:h for n,h in package_manifest.items() if '__pycache__' not in Path(n).parts and not Path(n).name.endswith(('.pyc','.lock'))}
 equal('package-exact-engineering-member-inventory',normalized_members,engineering['package_files'])
 check('package-normalized416-and-complete417-members',len(normalized_members)==416 and len(package_manifest)==417,normalized=len(normalized_members),complete=len(package_manifest),excluded=sorted(set(package_manifest)-set(normalized_members)))
 # Literal typed compiler origin is checked as an untrusted candidate only.
 response=(P/'formalizer-response.json').read_bytes();records=load(P/'formalizer-frozen.json');compiled=ff.compile_response(response,records,'generic.enum.packet',response_ref='formalizer-response.json')
 equal('candidate-exact-generated-source',compiled.source,(P/'contract/candidate/proposal.lean').read_bytes())
 equal('candidate-exact-generated-bindings',compiled.formalization,load(P/'contract/candidate/formalization.json'))
 check('candidate-origin-exact-regeneration',ff.reconstruct_origin(response,records,compiled.source,compiled.formalization,compiled.receipt))
 equal('literal-generic-request',REQUEST,(P/'request/prompt.txt').read_bytes())
 # Accepted declarations, semantic registry and each full dependency closure are recomputed.
 pkg=Package(P);cert=load(P/'accepted/acceptance.json');ir=load(P/'accepted/accepted-ir.json')
 for key,a in cert['artifacts'].items():artifact(a,P,'accepted-bound-artifact:'+key)
 accepted_policy=load(P/'contract/challenge/policy.json');env=contract.Env.from_export(load(P/cert['artifacts']['environment_export']['path']),accepted_policy,'independent pure retained export inspection')
 check('accepted-export-kernel-replay-observation',not env.diagnostics and env.export['import']['ok'] and env.export['replay']['ok'])
 equal('accepted-ir-environment-hash',ir['accepted_environment_hash'],canonical.digest_file(P/cert['artifacts']['environment_export']['path']))
 claimed=load(P/'claims.json')['obligations'];form=load(P/'contract/challenge/formalization.json');analysis=contract.analyze(env,claimed,form,accepted_policy,cert['toolchain']['pin'],'independent retained accepted AST inspection')
 check('accepted-ast-reconstruction-no-blockers',not any(d.severity=='blocking' for d in analysis.diagnostics),diagnostics=[d.to_json() for d in analysis.diagnostics])
 accepted_profile=load(P/cert['artifacts']['profile']['path']);equal('accepted-registry-from-real-declarations',analysis.profile,accepted_profile)
 profile=dsl.Profile.from_json(accepted_profile);enum=profile.enums['Compass'];binding=enum['decidable_eq'];instance=binding['lean_decl']
 check('accepted-enum-candidate-metadata-absent','candidate_decidable_eq' not in enum)
 equal('accepted-exact-three-constructors',enum['constructors'],['north','south','center'])
 equal('accepted-exact-instance-type',env.decls[instance]['type'],app(const('DecidableEq',[1]),const(enum['lean_decl'])))
 equal('accepted-instance-real-declaration-hash',binding['decl_hash'],decl_hash(env.decls[instance]))
 equal('accepted-instance-resolves-safe-current',reify.validate_enum_equality_binding(profile,'Compass',env.decls),instance)
 st=load(P/cert['artifacts']['statements']['path'])['statements']
 for oid,stmt in st.items():
  equal('accepted-statement-reconstruction:'+oid,analysis.statements[oid],stmt)
  for name,h in stmt['semantic_closure'].items():check('accepted-closure:'+oid+':'+name,env.hashes[name]==h,expected=h)
  equal('accepted-closure-digest:'+oid,stmt['semantic_closure_hash'],canonical.digest_json({'toolchain':cert['toolchain']['pin'],'declarations':stmt['semantic_closure']}))
  equal('accepted-ir-statement-binding:'+oid,ir['obligations'][oid]['formal']['statement_hash'],stmt['statement_hash'])
  if oid in ['O1','S1']:
   package_path=ir['obligations'][oid]['formal']['formula_ref'].split('@sha256:')[1];fp=load(P/f'accepted/expressions/{package_path}.json')
   equal('accepted-ast-expression-package:'+oid,fp,analysis.statements[oid]['formula_package'])
  check('accepted-no-sorry-or-native-axiom:'+oid,'sorryAx' not in ir['obligations'][oid]['formal'].get('axioms',[]) and not any(policy.classify_axiom(a,accepted_policy)!='allowed' for a in ir['obligations'][oid]['formal'].get('axioms',[])))
 family=closure({instance},env.decls);check('accepted-instance-helper-closure-fully-bound',family<=set(st['O1']['semantic_closure']))
 observations['accepted_equality']={'name':instance,'decl_hash':binding['decl_hash'],'helper_closure':{n:env.hashes[n] for n in sorted(family)}}
 check('actual-policy-closed-source-facet-values',not source_policy.check_package(pkg,analysis.statements,claimed))
 o1=st['O1']['formula_package'];s1=st['S1']['formula_package'];check('mixed-value-conjunction-preserved',o1['value'] is not None and s1['value'] is None and len(o1['source'])==len(s1['source'])==1)
 expected_requirements=[{'tag':'entry','file':'program.vscore.json','entry':'adjust','arity':1},*[{'tag':t} for t in PROPERTIES]]
 for oid,fp in [('O1',o1),('S1',s1)]:equal('accepted-exact-eight-source-requirements:'+oid,fp['source'][0]['requirements'],expected_requirements)
 value_formula=o1['value']['formula'];check('unbounded-universal-Packet-value',value_formula['tag']=='forall' and value_formula['sort']=={'record':'Packet'} and value_formula['body']['tag']=='eq')
 check('required-witness-Proved',any(c['id']=='W1' and c['required'] for c in claimed) and ir['obligations']['W1']['formal']['axioms']==[])
 # Current source/parser AST and exact goal regenerated by the registered host renderer.
 selection=vscore3.selection(pkg);ctx=checker.load_context(P/'bridges/implementation','implementation',selection['edge_id']);spec=checker.derive_goal(ctx)
 delivered=ctx.inputs['source'][1];equal('actual-source-surface-replay',source.compile_surface(SURFACE,{'Compass':enum['constructors']}),delivered)
 equal('actual-source-parser-roundtrip',source.source_bytes(source.parse_source(delivered)),delivered)
 equal('relation-exact-current-bindings',ctx.relation,RELATION)
 equal('actual-goal-exact-current-renderer',spec.text.encode(),(S/'goal/VeriSlopBridgeGoal.lean').read_bytes())
 accepted,pending,diagnostics=checker.verify_published(pkg,'implementation',rebuild=False)
 check('published-semantic-certificate-pure-authentication',len(accepted)==1 and not pending and not diagnostics,accepted_count=len(accepted),pending=pending,diagnostics=[d.to_json() for d in diagnostics])
 semantic=load(S/'certificate.json');check('semantic-is-real-full-edge-not-E2E-authority',semantic['semantic_acceptance'] and semantic['assigns_end_to_end_verified'] is False)
 equal('required-per-ID-transfers',[(r['id'],r['transfer']) for r in semantic['obligations']],[('O1','VeriSlopBridgeGoal.Transfer_O1'),('S1','VeriSlopBridgeGoal.Transfer_S1')])
 # Authenticate every selected readable artifact and independently recompute identities/axioms.
 refs=checker.readable_artifact_refs(semantic['readable_support'],lambda p:(S/p).read_bytes());manifest=load(S/'readable/manifest.json');support=load(S/'readable/kernel-export.json');baseline=load(S/'readable/base-kernel-export.json')
 check('selected-readable-current-checked',manifest['selected_mode']==manifest['status']=='CHECKED' and len(support)==13)
 check('readable-proof-actually-uses-support',manifest['checked_proof_support_dependencies']==['VeriSlopBridgeGoal.Readable.readable_fn_adjust','VeriSlopBridgeGoal.Readable.source_eq_adjust'])
 check('readable-support-baseline-disjoint',not(set(support)&set(baseline)))
 equal('raw-baseline-real-declaration-digest',manifest['base_declaration_identity_hash'],canonical.digest_json({n:decl_hash(c) for n,c in sorted(baseline.items())}))
 baseline_axioms=sorted({name_str(a) for c in baseline.values() for a in c['axioms']});support_axioms=sorted({name_str(a) for c in support.values() for a in c['axioms']})
 check('actual-support-axioms-contained',set(support_axioms)<=set(baseline_axioms) and all(policy.classify_axiom(a,accepted_policy)=='allowed' for a in support_axioms))
 equal('raw-baseline-axiom-digest',manifest['support_axiom_baseline_hash'],canonical.digest_json(baseline_axioms));equal('actual-support-axiom-inventory',manifest['actual_support_axioms'],support_axioms)
 check('readable-original-EdgeProp-unchanged',manifest['base_proposition_hash']==manifest['replayed_proposition_hash']==semantic['proposition_hash'])
 equal('readable-full-function-inventory',[(f['role'],f['source_id']) for f in manifest['compiled_inventory']],[('entry','adjust')])
 for row in manifest['support_declarations']:
  c=support[row['name']];equal('readable-record:'+row['name'],c,load(S/row['kernel_record']['path']))
  equal('readable-type-hash:'+row['name'],row['type_hash'],canonical.digest_json(canon(c['type'],[])))
  if c['kind']=='theorem':check('honest-module-bound-proof:'+row['name'],row['body_hash'] is None and row['proof_identity']['kind']=='MODULE_BOUND_PROOF' and row['proof_identity']['proof_body_ast']==row['proof_identity']['individual_proof_body_digest']=='UNAVAILABLE')
  else:equal('readable-definition-value-hash:'+row['name'],row['body_hash'],canonical.digest_json(canon(c['value'],[])))
  check('readable-current-module-parts:'+row['name'],row['proof_identity']['module_parts_hash']==manifest['support_module_parts_hash'] and row['proof_identity']['regenerated_source_hash']==manifest['selected_goal_hash'])
 observations['readable']={'refs_count':len(refs),'baseline_declarations':len(baseline),'support_declarations':len(support),'baseline_axioms':baseline_axioms,'support_axioms':support_axioms,'proof_dependencies':manifest['checked_proof_support_dependencies']}
 # Stored registered execution validation, complete premises, equality and honest lifecycle.
 snapshot=vscore3_closure.mechanical_snapshot(pkg);equal('actual-execution-snapshot',snapshot,load(F/'mechanical-snapshot.json'))
 equal('retained-execution-snapshot',snapshot,load(A/'retained-mechanical-snapshot.json'))
 check('stored-execution-Verified',snapshot['mechanical_status']=='VERIFIED' and not snapshot['diagnostics'])
 required=[c for c in snapshot['claims'] if c['required']];check('all38-required-claims-pass',len(required)==38 and all(c['outcome']=='PASS' for c in required),count=len(required))
 builds=snapshot['builds'];check('two-real-builds-A-B',[b['build'] for b in builds]==['A','B'] and all(b['ok'] and not b['errors'] for b in builds))
 equal('complete-registered-A-B-output-equality',builds[0]['outputs'],builds[1]['outputs'])
 check('deterministic-comparison-no-mismatches',not snapshot['determinism']['mismatches'])
 for b in builds:check('build-readable-check:'+b['build'],b['outputs']['readable_support']['descriptor']['mode']=='CHECKED')
 report=load(P/'report.json');check('full-report-current-endpoint',report['mechanical_status']=='VERIFIED' and report['tier']['requested_endpoint']=='restricted_source' and report['tier']['require_state']=='END_TO_END_VERIFIED')
 for oid in ['O1','S1']:
  check('reported-required-E2E:'+oid,report['obligations'][oid]['outcomes']['END_TO_END_VERIFIED']=='PASS')
  check('optional-TESTED-honestly-pending:'+oid,report['obligations'][oid]['outcomes']['TESTED']=='PENDING')
 check('required-witness-contract-only',report['obligations']['W1']['outcomes']['PROVED']=='PASS' and report['obligations']['W1']['outcomes']['END_TO_END_VERIFIED']=='NOT_APPLICABLE')
 equal('registered-review-projection-exact',review_projection.build(pkg,snapshot),load(F/'review-projection.json'))
 probe=load(F/'release-probe.json');retained_probe=load(A/'retained-release-probe.json');equal('retained-release-probe-exact',probe,retained_probe)
 check('concrete-release-probe-NotReproduced',probe['status']=='NOT_REPRODUCED' and probe['expected']['outcome']==probe['observed']['outcome']=='PASS' and probe['claim']['claim_id']==semantic['claim_id'] and probe['expected']['root']==semantic['semantic_edge_root'] and not probe['diagnostics'])
 for name,h in probe['input_bindings'].items():
  if name.startswith('binding:'):continue
  check('release-bound-input:'+name,(P/name).is_file() and canonical.digest_file(P/name)==h,expected=h)
 retained=load(A/'result.json');check('retained-copy-qualification-final',retained['qualification'] and retained['original_temporary_root_removed'] and retained['error'] is None and retained['model_calls']==0 and retained['registered_actual_builds']=='A,B')
 equal('retained-annex-exact-capture-reference',retained['capture_hash'],canonical.digest_file(F/'capture.json'))
 # The original temporary root is additionally extracted from volatile paths, never trusted as a live import.
 original_dirs=set()
 for p in F.rglob('*.json'):
  if p.stat().st_size>8_000_000:continue
  original_dirs.update(re.findall(r'/tmp/fresh-enum-packet-tier2-[A-Za-z0-9_-]+',p.read_text(errors='replace')))
 check('actual-original-temp-paths-absent',bool(original_dirs) and all(not Path(d).exists() for d in original_dirs),paths=sorted(original_dirs))
 observations['closure']={'closure_root':snapshot['closure_root'],'required_claims':len(required),'package_members':len(package_manifest),'build_output_keys':sorted(builds[0]['outputs']),'premise_claims':snapshot['claims'],'original_temporary_roots':sorted(original_dirs)}
 for name in ['stage-results.json','implementation-stage-results.json']:check('actual-stages-pass:'+name,all(r['status']=='PASS' for r in load(F/name)))
 status='PASS_BOUNDED_FINAL_GENERIC_QUALIFICATION_AUDIT'
except BaseException as exc:
 status='AUDIT_CHECK_FAILURE';observations['audit_error']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
finally:
 result={'format':'verislop.enum-final-independent-audit-checks/0.1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':status,'checks':rows,'checks_run':len(rows),'failures':sum(not r['ok'] for r in rows),'inventories':inventories,'observations':observations,'no_native_kernel_model_calls':True,'kernel_evidence_scope':'Stored actual generic pinned builds/replays authenticated; no fresh kernel replay by this auditor.'}
 (OUT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':status,'checks':len(rows),'failures':result['failures'],'error':observations.get('audit_error')}))
 if status=='AUDIT_CHECK_FAILURE':sys.exit(1)
