"""Bounded pure read-only audit of actual frozen015 selected pipeline artifacts."""
from pathlib import Path
import sys,json,hashlib,re,difflib,ast
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'runtime'));sys.path.insert(0,str(root/'runtime/tests'))
from verislop import canonical,schemas,policy,leanbridge,review_projection,review_counterexamples as CR
from verislop.package import Package
from verislop.backends import vscore3 as V,vscore3_closure as B
from verislop.bridges import vscore3_checker as C,vscore3_readable_support as RS
from verislop.targets import vscore3_target as T,vscore3_readable as R,vscore3_source as S
from verislop.exprjson import decl_hash,name_str,canon,constants
from test_vscore3_readable import context
checks=[]
def ck(n,v,d=None):
 assert v,n
 checks.append({'name':n,'result':'PASS','detail':d})
read=lambda label,p:(root/label/p).read_bytes()
obj=lambda label,p:canonical.loads(read(label,p))
cap=root/'selected-capture';meta=obj('selected-capture','capture.json')
actual={p.relative_to(cap).as_posix() for p in cap.rglob('*') if p.is_file()}
ck('exact complete selected native capture inventory',actual=={'capture.json',*meta['files']},len(actual))
for p,h in meta['files'].items():assert canonical.digest_file(cap/p)==h,p
ck('every actual selected capture file hash matches retained inventory',True,len(meta['files']))
freeze=obj('gate-inputs','source-freeze.json');originaltests=obj('gate-inputs','test-sources.json');frozen={**freeze['source_files'],**originaltests}
ck('capture exact canonical producer root',canonical.digest_json(meta['source_hashes'])==meta['source_root'])
ck('all176 native producer/test inputs equal original frozen015 source/test bytes',all(frozen[p]==h and canonical.digest_file(cap/'registered-sources'/p)==h for p,h in meta['source_hashes'].items()),len(meta['source_hashes']))
pkg=Package(cap/'package');diags=B.validate_frozen(pkg)
ck('independent current frozen package validator',not diags,[d.to_json() for d in diags])
result=B.mechanical_snapshot(pkg)
ck('independent current execution inventory and scoped roots validation',result is not None and result['mechanical_status']=='VERIFIED',result['attempt_id'])
claims=B._claims(pkg);rows=result['claims']
ck('complete61 claims and exact46 required claims all PASS',len(rows)==len(claims)==61 and sum(c['required'] for c in rows)==46 and all(c['outcome']=='PASS' for c in rows if c['required']),[{'id':c['claim_id'],'outcome':c['outcome']} for c in rows if c['required']])
ck('all applicable three generic source/value endpoints E2E PASS and witness separately PROVED',{c['claim_id'] for c in rows if c['claim_id'].startswith('END_TO_END_VERIFIED:')}=={'END_TO_END_VERIFIED:O1@1','END_TO_END_VERIFIED:O2@1','END_TO_END_VERIFIED:S1@1'} and next(c for c in rows if c['claim_id']=='PROVED:W1@1')['outcome']=='PASS')
ck('actual two complete clean builds A/B, no errors',len(result['builds'])==2 and [b['build'] for b in result['builds']]==['A','B'] and all(b['ok'] is True and b['errors']==[] for b in result['builds']))
ck('exact registered .3 complete14 output slots including CHECKED support',len(B.COMPARISON_SLOTS)==14 and result['determinism']['compared']==list(B.COMPARISON_SLOTS) and all(set(b['outputs'])==set(B.COMPARISON_SLOTS) and b['outputs']['readable_support']['descriptor']['mode']=='CHECKED' and all(v is not None for v in b['outputs'].values()) for b in result['builds']))
ck('all actual A/B outputs identical, fresh registered determinism0.3 re-evaluates',result['builds'][0]['outputs']==result['builds'][1]['outputs'] and B._compare_outputs(result['builds'][0]['outputs'],result['builds'][1]['outputs'])==result['determinism']['mismatches']==[] and next(c for c in claims if c['claim_id']=='CLOSURE:determinism')['result_predicate']=='closure-determinism/0.3')
accepted,pending,diagnostics=C.verify_published(pkg,'implementation',rebuild=False)
ck('independent retained-copy published bridge check without any build',bool(accepted) and not pending and not diagnostics,{'accepted':accepted,'pending':pending,'diagnostics':[d.to_json() for d in diagnostics]})
selection=V.selection(pkg);ctx=C.load_context(pkg.root/'bridges/implementation','implementation',selection['edge_id']);spec=C.derive_goal(ctx)
sroot=pkg.root/'bridges/implementation'/C.SEMANTIC_DIR/C.edge_key(ctx.edge['edge_id'])
relative=lambda p:(sroot/p).read_bytes();m=canonical.load_file(sroot/R.MANIFEST_PATH);cert=canonical.load_file(sroot/'certificate.json')
refs=RS.artifact_refs(cert['readable_support'],relative)
ck('exact closed selected support artifact map and actual bound refs',set(refs)=={p.relative_to(sroot).as_posix() for p in sroot.rglob('*') if p.is_file() and p.relative_to(sroot).as_posix().startswith(('readable/','support/readable/'))},len(refs))
ck('frozen selected metadata survives candidate/backend/preparation/published binding',ctx.readable_selection==read('selected-capture','candidate/support/readable/selection.json')==relative(R.SELECTION_PATH) and C.readable_candidate_metadata(ctx.readable_selection,ctx.readable_diagnostics.__getitem__)=={R.SELECTION_PATH:ctx.readable_selection} and cert['readable_support']==result['builds'][0]['outputs']['readable_support']['descriptor'])
ck('exact independently regenerated selected/base/source/typedIR/correspondence bytes',spec.text.encode()==relative('goal/VeriSlopBridgeGoal.lean')==relative('readable/selected-goal.lean') and spec.base_text.encode()==relative('readable/base-goal.lean') and spec.readable_view.block==relative('readable/source-block.lean') and spec.readable_view.typed_ir==relative('readable/typed-ir.json') and spec.readable_correspondence==relative('readable/correspondence.lean'))
baseline=canonical.load_file(sroot/'readable/base-kernel-export.json');support=canonical.load_file(sroot/'readable/kernel-export.json')
ck('actual raw68 BASE records disjoint from26 support records',len(baseline)==68 and len(support)==26 and not (set(baseline)&set(support)))
ck('all generated full original/universal/source/transfer theorem statements match raw exports',T.statement_mismatches(spec,{**baseline,**support})==[])
ck('raw baseline declaration identity independently recomputed',canonical.digest_json({n:decl_hash(c) for n,c in sorted(baseline.items())})==m['base_declaration_identity_hash'])
baseaxs=sorted({name_str(a) for c in baseline.values() for a in c['axioms']});suppaxs=sorted({name_str(a) for c in support.values() for a in c['axioms']})
ck('actual complete support axioms subset actual raw BASE and exact strict policy',suppaxs==m['actual_support_axioms']==['Classical.choice','Quot.sound','propext'] and set(suppaxs)<=set(baseaxs) and canonical.digest_json(baseaxs)==m['support_axiom_baseline_hash'] and all(policy.classify_axiom(a,ctx.policy)=='allowed' for a in baseaxs+suppaxs))
for row in m['support_declarations']:
 c=support[row['name']];th=canonical.digest_json(canon(c['type'],[]));bh=canonical.digest_json(canon(c['value'],[])) if c['kind']=='definition' else None
 assert row['type_hash']==th and row['body_hash']==bh and row['proof_identity']['regenerated_source_hash']==m['selected_goal_hash'] and row['proof_identity']['module_parts_hash']==m['support_module_parts_hash']
 if c['kind']=='theorem':assert row['proof_identity']['kind']=='MODULE_BOUND_PROOF' and row['proof_identity']['proof_body_ast']=='UNAVAILABLE' and row['proof_identity']['individual_proof_body_digest']=='UNAVAILABLE' and row['body_hash'] is None
 else:assert row['proof_identity']['kind']=='EXPORTED_DEFINITION_BODY' and row['proof_identity']['exported_body_hash']==bh
ck('all26 actual declaration identities preserve exact types/body/module binding and honest theorem limitations',True,{'definitions':sum(c['kind']=='definition' for c in support.values()),'theorems':sum(c['kind']=='theorem' for c in support.values())})
ck('two complete entry lookup/signature/universal Env equalities, no sampled/domain-bound proofs',len(m['compiled_inventory'])==2 and {r['source_id'] for r in m['compiled_inventory']}=={'shift','solve'} and all(r['role']=='entry' and r['run_equals_theorem'] in support and support[r['run_equals_theorem']]['type']=={'const':r['run_equals_theorem'].replace('runEquals_','RunEquals_').split('.'),'levels':[]} for r in m['compiled_inventory']))
proof=read('selected-capture','candidate/Proof.lean')
ck('actual accepted proof uses both readable universal rewrite routes',proof==read('selected-capture','package/bridges/implementation/candidate-inputs/Proof.lean') and b'apply VeriSlopBridgeGoal.edge_of_refines' in proof and b'rw [VeriSlopBridgeGoal.Readable.source_eq_shift]' in proof and b'rw [VeriSlopBridgeGoal.Readable.source_eq_solve]' in proof and m['checked_proof_support_dependencies']==['VeriSlopBridgeGoal.Readable.readable_fn_shift','VeriSlopBridgeGoal.Readable.readable_fn_solve','VeriSlopBridgeGoal.Readable.source_eq_shift','VeriSlopBridgeGoal.Readable.source_eq_solve'])
ck('accepted semantic certificate correctly separates semantics from E2E policy state',cert['semantic_acceptance'] is True and cert['assigns_end_to_end_verified'] is False and cert['theorem']['symbol']==T.PROOF_MODULE+'.edge' and cert['theorem']['proposition']==T.EDGE_PROP and set(cert['theorem']['axioms'])==set(suppaxs) and {o['id'] for o in cert['obligations']}=={'O1','O2','S1'})
execution=(pkg.root/result['mechanical_result_path']).parent
for build in result['builds']:
 prefix=execution/'builds'/build['build'];stored=canonical.load_file(execution/'builds'/(build['build']+'.json'));assert stored==build
 semantic=prefix/'semantic';bcert=canonical.load_file(semantic/'certificate.json')
 assert bcert['readable_support']==cert['readable_support']
 bref=RS.artifact_refs(bcert['readable_support'],lambda p:(semantic/p).read_bytes())
 assert bref==refs and all((semantic/p).read_bytes()==relative(p) for p in refs)
 assert build['outputs']['readable_support']=={'descriptor':cert['readable_support'],'artifacts':refs}
 for label in ('A','B'):
  obs=canonical.load_file(semantic/'builds'/(label+'.json'));assert obs['readable_support']==cert['readable_support']
 modules={}
 for p in (prefix/'modules').rglob('*'):
  if not p.is_file():continue
  for suffix in sorted(leanbridge.MODULE_SUFFIXES,key=len,reverse=True):
   if p.name.endswith(suffix):module=p.relative_to(prefix/'modules').as_posix()[:-len(suffix)].replace('/','.');modules.setdefault(module,{})[suffix]=p.read_bytes();break
 # Goal module parts bind universal support; Proof module is separately inventory-bound.
 assert C._parts_digest(modules[T.GOAL_MODULE])==m['support_module_parts_hash']
ck('both clean builds retained exact full43 support artifacts and actual goal module parts',True,len(refs))
report=canonical.load_file(pkg.path('report'))
ck('stored report/current execution builds/determinism/status agree exactly',report['builds']==result['builds'] and report['determinism']==result['determinism'] and report['mechanical_status']==result['mechanical_status']=='VERIFIED' and report['terminal_status']=='VERIFIED' and report['release_status']=='NOT_REQUIRED',report['counts'])
port=obj('portability','receipt.json')
ck('retained portability receipt binds exact actual completed capture/root',port['format']=='verislop.fresh-readable-portability/1' and port['capture_hash']==canonical.digest_file(cap/'capture.json') and port['closure_root']==result['closure_root'] and port['original_temporary_root_removed'] is True and port['published_check']=='PASS' and port['mechanical_status']=='VERIFIED')
projection=review_projection.build(pkg,result)
ck('complete retained deterministic review projection independently reconstructs',projection==obj('selected-capture','retained-projection.json'))
receipt=obj('selected-capture','mechanical-probe.json');replayed=CR.replay(pkg,'release',receipt['proposal'])
ck('registered current-root release mechanical probe independently reconstructs exact receipt',receipt==replayed and receipt['status']=='NOT_REPRODUCED' and receipt['expected']['outcome']==receipt['observed']['outcome']=='PASS' and receipt['expected']['root_kind']=='semantic_edge' and receipt['expected']['root']==cert['semantic_edge_root'],{'status':receipt['status'],'expected':receipt['expected'],'observed':receipt['observed'],'input_bindings':len(receipt['input_bindings'])})
ck('release probe is not promoted into an unexecuted release consensus',report['release_status']=='NOT_REQUIRED' and not (pkg.root/'reviews').exists())
# Honest BASE fallback for the two intentionally unsupported forms, actual gate015 capture.
vmeta=obj('variant','manifest.json');vpaths={p.relative_to(root/'variant').as_posix() for p in (root/'variant').rglob('*') if p.is_file()}
ck('actual variant BASE capture has complete exact payload inventory',vpaths=={'manifest.json',*vmeta['artifacts']})
for p,ref in vmeta['artifacts'].items():d=read('variant',p);assert ref=={'sha256':canonical.digest(d),'size':len(d)}
ck('actual variant BASE capture every retained byte/hash/size',True,len(vmeta['artifacts']))
vsource=read('variant','source.json');vctx=context(read('variant','modules/VeriSlopContract.olean'));vctx.inputs['source']=('vscore-source',vsource);vbase=T.build_goal(vsource,vctx.relation,vctx.accepted_profile,vctx.obligations)
vobs=obj('variant','observation.json');vselection=obj('variant',R.SELECTION_PATH)
ck('variant and matchVariant are admitted in source but preserve exact unmodified BASE goal',S.parse_source(vsource)['helpers'][0]['body'][0]=='variant' and S.parse_source(vsource)['helpers'][1]['body'][0]=='match_variant' and read('variant','goal.lean')==vbase.text.encode()==read('variant','readable/base-goal.lean')==read('variant','readable/selected-goal.lean') and vselection['selected_mode']=='BASE' and vselection['status']=='UNSUPPORTED' and vselection['reasons'][0]['code']=='UNSUPPORTED_TYPE')
vrefs=RS.artifact_refs(vobs['readable_support'],lambda p:read('variant',p))
ck('actual BASE metadata/diagnostic closed inventory passes exact host replay',set(vrefs)=={p for p in vpaths if p.startswith(('readable/','support/readable/'))} and vobs['readable_support']['mode']=='BASE' and vobs['readable_support']['support_inventory_hash'] is None and vobs['readable_support']['support_module_parts_hash'] is None,len(vrefs))
# Test-only correction and aggregate failure stay distinct.
gate=obj('gate-inputs','run-result.json');log=read('gate-inputs','gate.stderr.log').decode()
ck('original gate015 FAIL retained,162 tests,0 failures,one exact mock-only AttributeError',gate['status']=='FAIL' and gate['tests_run']==162 and gate['failures']==0 and gate['errors']==1 and gate['source_unchanged'] and gate['test_sources_unchanged'] and "AttributeError: 'types.SimpleNamespace' object has no attribute 'readable_selection'" in log and log.count('ERROR: ')==1)
original=read('runtime','tests/test_compile_process_evidence.py');corrected=(root/'corrected-test-fixture.py').read_bytes();delta='\n'.join(difflib.unified_diff(original.decode().splitlines(),corrected.decode().splitlines(),fromfile='frozen',tofile='corrected'))
(root/'fixture-delta.patch').write_text(delta+'\n')
oldtree=ast.parse(original);newtree=ast.parse(corrected)
def methods(tree):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
oldmethods=methods(oldtree);newmethods=methods(newtree)
ck('test-only correction changes only the failing fixture method',set(oldmethods)==set(newmethods) and [k for k in oldmethods if oldmethods[k]!=newmethods[k]]==['test_preview_returns_detached_optional_inventory_with_existing_info'])
ck('correction only completes actual GoalSpec None field and adds three legacy assertions',corrected==original.replace(b'spec = SimpleNamespace(symbols=[])',b'spec = SimpleNamespace(symbols=[], readable_selection=None)').replace(b'        self.assertTrue(info["proof_checked"])\n',b'        self.assertTrue(info["proof_checked"])\n        self.assertIsNone(info["readable_selection"])\n        self.assertIsNone(info["readable_source_view"])\n        self.assertEqual(info["readable_candidate_artifacts"], {})\n') and 'readable_selection: bytes | None = None' in read('runtime','verislop/targets/vscore3_target.py').decode())
fixspec=obj('gate-inputs','fixture-correction/specification.json');fixinv=obj('gate-inputs','fixture-correction/invocation.json');fix=obj('gate-inputs','fixture-correction/result.json');fixlog=read('gate-inputs','fixture-correction/unittest.log')
ck('spec-first separately frozen fixture supplement exact bindings,whole23 tests PASS',fixspec['production_change'] is False and fixspec['change_scope']==['tests/test_compile_process_evidence.py'] and fixspec['failure_record']['sha256']==canonical.digest(read('gate-inputs','run-result.json')) and fixspec['old_test_sha256']==canonical.digest(original) and fixinv['test_sha256']==fix['test_sha256']==canonical.digest(corrected) and fix['log_sha256']==canonical.digest(fixlog) and fix['tests_run']==23 and fix['status']=='PASS' and fix['original_gate_status']=='FAIL' and fix['errors']==fix['failures']==fix['skipped']==0 and len(re.findall(rb'^test_.* \.\.\. ok$',fixlog,re.MULTILINE))==23 and b'Ran 23 tests' in fixlog and fixlog.rstrip().endswith(b'OK'))
engineering=obj('gate-inputs','engineering-validation.json')
ck('parent engineering record agrees with independently validated selected closure',engineering['status']=='VERIFIED' and engineering['source_root']==freeze['source_root'] and engineering['closure_root']==result['closure_root'] and engineering['fresh_model_calls']==0 and engineering['fixture_only'] is True and engineering['model_authoring_input'] is False and len(engineering['package_files'])==491,{'package_files':len(engineering['package_files']),'closure_root':result['closure_root']})
output={'format':'verislop.independent-selected-readable-pipeline-audit/1','checks':checks,'scope':'Actual frozen015 generic selected package/support/raw BASE/refinement/probe/retained-copy and separately frozen mock-fixture supplement. Pure local artifact and registered no-rebuild validators only. Original gate remains FAIL; this is not a fresh all162-PASS claim.'}
(root/'selected-checks.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
