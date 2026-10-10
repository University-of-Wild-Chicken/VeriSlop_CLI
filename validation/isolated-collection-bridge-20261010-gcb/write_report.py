import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from verislop import canonical
from verislop.exprjson import canon,name_str
P=Path('validation/isolated-collection-bridge-20261010-gcb')
def load(path):return canonical.load_file(P/path)
before=load('source-freeze-before.json')
after=[{'path':r['path'],'sha256':canonical.digest_file(Path(r['path'])),'size':Path(r['path']).stat().st_size} for r in before]
(P/'source-freeze-after.json').write_bytes(canonical.dumps(after))
changed=[r['path'] for r,s in zip(before,after) if r!=s]
print('audited generic source/spec files',len(before),'changed',changed)
actual=(P/'actual-goal/VeriSlopBridgeGoal.lean').read_bytes()
selected=load('actual-goal/support/readable/selection.json')
base=(P/'actual-goal/readable/base-goal.lean').read_bytes()
readable=load('actual-goal/readable/compiled-inventory.json')
(P/'actual-generated-artifact-identities.json').write_bytes(canonical.dumps({'source':canonical.digest_file(P/'program.json'),'specification':canonical.digest_file(P/'specification.json'),'base_goal':canonical.digest(base),'selected_goal':canonical.digest(actual),'base_proposition_hash':selected['base_proposition_hash'],'readable_selection':canonical.digest_file(P/'actual-goal/support/readable/selection.json'),'readable_compiled_inventory':readable,'adapters':'The six adapter_0 through adapter_5 declarations are in the exact checker-generated base and selected goal source; none supplied by author.'}))
source=(P/'UniversalTransport-v0.lean').read_text()
control=load('diagnostics/21-actual-transport-v1/kernel.json')
proposed=[]
for name in ('to_eq_iff','decide_to_eq','map_transport','filter_transport','foldl_transport'):
 start=source.index('theorem '+name+' ');end=source.index(' := by',start)
 c=next(c for c in control['constants'] if c['name']==['GenericUniversalControls',name])
 proposed.append({'prototype_name':'GenericUniversalControls.'+name,'signature_source':source[start:end],
  'kernel_type_hash':canonical.digest_json(canon(c['type'],[])),
  'prototype_source':'UniversalTransport-v0.lean','prototype_source_hash':canonical.digest_file(P/'UniversalTransport-v0.lean'),
  'kernel_evidence':'diagnostics/21-actual-transport-v1/kernel.json','axioms':[name_str(a) for a in c['axioms']],
  'unresolved_constants':c['unresolved_constants'],'global_simp_rule':False,
  'actual_generated_term_use':{'to_eq_iff':'ref_filter for generated adapter_2','decide_to_eq':'fixed_enum_decision for generated adapter_0 and fixed denoteDecidableEq / instDecidableEqTone','map_transport':'ref_map for generated adapter_4 and adapter_5','filter_transport':'ref_filter for generated adapter_4 and adapter_5','foldl_transport':'ref_fold for generated adapter_4, adapter_5 and adapter_1'}[name]})
(P/'proposed-universal-support-catalog.json').write_bytes(canonical.dumps({'status':'proposal only; production untouched','generic_types':'Actual current VSCore3.Adapter and Shape/Denote types, α/β : Type (current Adapter carrier universe).','prototypes':proposed}))
status={}
for label in ('12-formalize','13-prove','14-accept','15-export','08-source-admit','16-actual-readable-goal','22-current-checker-positive','23-bridge-prepare'):
 f=P/'diagnostics'/f'{label}.stdout.json'
 if f.is_file() and f.stat().st_size:
  x=json.loads(f.read_bytes());status[label]={'status':x.get('status'),'diagnostics':x.get('diagnostics'),'summary':x.get('summary')}
report={
 'format':'isolated-generic-proof-ergonomics-report/1',
 'experiment_root':str(P.resolve()),
 'specification':{'path':'specification.json','sha256':canonical.digest_file(P/'specification.json'),'persisted_before_fixture_inputs':True,'unchanged':True},
 'scope':{'fixture_only':True,'native_task_knowledge_used':False,'qualification_claim':False,'semantic_bridge_acceptance_published':False,'hard_inference_deadline':False},
 'source_freeze':{'before':'source-freeze-before.json','after':'source-freeze-after.json','changed_paths':changed,'audited_generic_files':len(before),'tests':'No test file read or written; no production/spec/test source edit performed.'},
 'actual_vs_standin':{
  'actual':['verislop.formal_frontend.compile_response generated candidate source, canonical fixed enum decisions and compiler receipt','verislop.formalize.attempt with actual frontend object performed six kernel denotation audits','current CLI interpretation/formalization/prove/accept/export on new independent packages','current vscore compile/check admitted exact canonical bytes through two clean builds','current vscore goal selected actual CHECKED readable support','actual returned compiled module parts preserved for exploratory controls','current vscore goal with complete authored proof and frozen selection','current bridge prepare freezes the new fixture bundle'],
  'author_written':['Specification and typed proposal','VSCore surface source','UniversalTransport-v0.lean universally quantified support prototypes','ActualControls-v1.lean instantiates those prototypes on generated adapter_0 through adapter_5 and existing source_eq_* theorems'],
  'standin_adapters':False,'standin_goals':False,'standin_checker_results':False,
  'lower_level_control_boundary':'compile_control.py reuses exact actual generated compiled modules for exploratory compiler/kernel checks; these are not registered bridge certificates. The complete final proof additionally goes through current checker preview.',
  'observation_boundary':'invoke_cli.py wraps original Leanbridge functions solely to save unmodified return values/diagnostics; it supplies no replacement compiler or kernel outcomes. An initial serialization-wrapper exception is separately retained under diagnostics/03-formalize and prevented that attempt from reaching any acceptance gate.'},
 'resource_policy':{'path':'resource-policy.json','policy':'verislop.policy.strict/0.1','build_timeout_seconds':300,'kernel_timeout_seconds':300,'memory_mb':8192,'address_space_headroom_mb':16384,'proof_search_orchestration_budget_seconds':0,'policy_changed':False},
 'stage_results':status,
 'universal_controls':{'existing_catalog':'actual-authoring-lemma-catalog.json','existing_catalog_lemmas':6,'proposed_support_signatures':'proposed-universal-support-catalog.json','new_universal_lemmas':5,'pure_universal_kernel_control':'diagnostics/10b-universal-controls-v0/kernel.json','actual_instantiations_kernel':'diagnostics/21-actual-transport-v1/kernel.json','all_positive_controls_compile_without_sorry':True,'all_positive_control_kernel_replays_passed':True,'no_input_bounds_or_preconditions_added':True},
 'concrete_ergonomics':[
  {'gap':'List map through nominal nested-record representation','actual_failure':'diagnostics/18-actual-rfl-baseline/compile.json','actual_positive':'ActualControls-v1.lean: ref_map','explanation':'The source maps over List.map adapter_4.to xs, then the result uses List.map adapter_4.inv. Direct definitional equality fails; map_transport discharges list fusion after a universal per-element relation, which is rfl for this fixture.'},
  {'gap':'List filter with representation predicate agreement','actual_failure':'diagnostics/18-actual-rfl-baseline/compile.json','actual_positive':'ActualControls-v1.lean: ref_filter','explanation':'The admitted source tests full intrinsic Atom product equality; the accepted DSL uses fixed enum/Nat field decisions because aggregate bool_eq is unsupported. filter_transport handles List.map inv / filter / List.map to; to_eq_iff turns actual generated adapter_2 equality into native Atom equality, then structural field equality is proved.'},
  {'gap':'Fold over a mapped representation and generalized accumulator','actual_failure':'diagnostics/18-actual-rfl-baseline/compile.json','actual_positive':'ActualControls-v1.lean: ref_fold','explanation':'The source folds encoded Box values and returns through adapter_1.inv. foldl_transport requires the step equation for every accumulator and element, then proves correspondence by list induction; the concrete step uses exhaustive enum cases only.'},
  {'gap':'Fixed enum decision across nominal enum / intrinsic subtype carriers','actual_failure':'diagnostics/20-actual-equality-rfl/compile.json','actual_positive':'ActualControls-v1.lean: fixed_enum_decision','explanation':'Current fixed denoteDecidableEq on the generated source enum subtype and the formalizer-fixed instDecidableEqTone compute on different representations. Direct rfl fails universally; decide_to_eq follows from the actual Adapter inverse law and retains the exact two decision instances.'}],
 'incidental_generic_diagnostics':[
  {'code':'UNSUPPORTED_TYPED_AGGREGATE_BOOL_EQ','evidence':'diagnostics/00-composite-equality-compiler.json','message':'bool_eq requires equal primitive scalar or bound enumeration sorts','faithful_alternative':'Fieldwise fixed enum/Nat decisions; unchanged operation specification, with full structural equality correspondence proved in ref_filter.'},
  {'code':'HYPHENATED_OBLIGATION_NAME_LOOKUP','evidence':'diagnostics/09-actual-readable-goal.stdout.json','root':'verislop/bridges/vscore3_checker.py:506-508 uses a raw transfer_<oid> lookup; name_str exports the hyphenated component quoted. Exported actual transfer_G-filter contains the accepted law_keepAtom dependency, yet lookup fails.','resolution':'New package and binding inventory use Gmap/Gfilter/Gfold; the original accepted package and all diagnostics remain preserved; specification bytes unchanged.'}],
 'input_and_harness_diagnostics':{'nat_literal_envelope':'diagnostics/01-input-generation-failure.json; exact original attempted inputs retained in inputs-attempt0 and replayed diagnostics explicitly labelled in diagnostics/00a-original-input-diagnostics-replayed.json','draft_lifecycle_envelope':'diagnostics/02-interpret.stdout.json; original draft retained, corrected candidate metadata in inputs/draft-v1.json','telemetry_serialization':'diagnostics/03-formalize.stderr.txt and invoke_cli-v0.py; observer corrected to JSON telemetry with floating-point wall seconds, no compiler resource-policy change','enum_registry_envelope':'diagnostics/07-source-compile.stdout.json; subsequent source compilation uses the actual accepted profile registry'},
 'evidence_indexes':{'commands':'commands.jsonl','generated_artifact_hashes':'actual-generated-artifact-identities.json','input_manifest':'input-manifest.json','complete_final_artifact_manifest':'artifact-manifest.json','all_diagnostics':'diagnostics/'},
 'recommendation':'Consider adding only these source-independent universal signatures to the explicit authoring catalog. This fixture demonstrates useful proof normalization; it does not establish a task qualification, success rate, completeness claim or production change.'
}
(P/'report.json').write_bytes(canonical.dumps(report))
manifest=[{'path':str(f.relative_to(P)),'sha256':canonical.digest_file(f),'size':f.stat().st_size} for f in sorted(P.rglob('*')) if f.is_file() and f.name!='artifact-manifest.json']
(P/'artifact-manifest.json').write_bytes(canonical.dumps(manifest))
print('report written; indexed artifacts',len(manifest))
