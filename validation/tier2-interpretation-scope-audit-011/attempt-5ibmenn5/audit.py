from pathlib import Path
import sys,json,ast,difflib,importlib.util,unittest,io,copy,os,datetime,subprocess
from unittest.mock import patch
ROOT=Path('/home/augustus/VeriSlop_CLI'); BASE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-010/project'; OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from synthetic_dataset.tools import bootstrap_tier2 as H
from verislop import canonical,agents,leanbridge
import test_bootstrap_tier2 as BT
import test_tier2_interpretation_context as IC
checks=[]; files={}; snapshots={}
def ck(name,value,detail=None):
 row={'name':name,'pass':bool(value)}
 if detail is not None:row['detail']=detail
 checks.append(row)
 if not value:raise AssertionError(name)
def snap(path,name):
 raw=path.read_bytes(); target=OUT/'snapshots'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 files[str(path)]={'sha256':canonical.digest(raw),'snapshot':str(target.relative_to(OUT))}; snapshots[str(target.relative_to(OUT))]=canonical.digest(raw);return raw
names=['docs/bootstrap-tier2-interpretation-scope.md','synthetic_dataset/tools/bootstrap_tier2.py','verislop/agents.py','tests/test_bootstrap_tier2.py','tests/test_tier2_interpretation_context.py']
for name in names:snap(ROOT/name,'current/'+name)
for name in names[1:3]:
 old=snap(BASE/name,'frozen010/'+name);new=(ROOT/name).read_bytes()
 diff=''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='frozen010/'+name,tofile='current/'+name))
 (OUT/'diffs'/name).parent.mkdir(parents=True,exist_ok=True);(OUT/'diffs'/name).write_text(diff)
for name in ['result.json','stdout.txt','stderr.txt']:snap(ROOT/'validation/tier2-interpretation-scope-development-011/attempt-002'/name,'root-development-attempt002/'+name)
reported=json.loads((ROOT/'validation/tier2-interpretation-scope-development-011/attempt-002/result.json').read_bytes())
for name in names[1:]:ck('reported_development_hash_matches:'+name,reported['files'][name]==canonical.digest_file(ROOT/name))
ck('reported_trial_is_success_no_models_no_kernel',reported['exit_code']==0 and reported['models_called'] is False and reported['native_kernel_gate_run'] is False)
current=H.source_inventory(ROOT);baseline=H.source_inventory(BASE)
changed={name:{'old':baseline.get(name),'new':current.get(name)} for name in sorted(set(current)|set(baseline)) if current.get(name)!=baseline.get(name)}
ck('only_two_requested_production_changes_and_new_spec',set(changed)=={'synthetic_dataset/tools/bootstrap_tier2.py','verislop/agents.py','docs/bootstrap-tier2-interpretation-scope.md'})
ck('current_root_bound',canonical.digest_json(current)=='sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a')
ck('production_count229',len(current)==229)
(OUT/'production-comparison.json').write_bytes(canonical.dumps({'baseline_root':canonical.digest_json(baseline),'current_root':canonical.digest_json(current),'changed':changed,'current_files':current,'baseline_files':baseline}))
for name in ['verislop/source_policy.py','verislop/source_contract.py','verislop/formalize.py','verislop/export.py','verislop/accept.py','verislop/targets/vscore3_target.py','verislop/backends/vscore3_closure.py']:
 ck('mandatory_enforcement_unchanged:'+name,(ROOT/name).read_bytes()==(BASE/name).read_bytes())
 defpath=ROOT/name;snap(defpath,'unchanged-enforcement/'+name)
def functions(path):
 tree=ast.parse(path.read_text());return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
a=functions(BASE/'synthetic_dataset/tools/bootstrap_tier2.py');b=functions(ROOT/'synthetic_dataset/tools/bootstrap_tier2.py')
ck('only_revise_prompt_and_verify_inputs_functions_changed',{k for k in set(a)|set(b) if a.get(k)!=b.get(k)}=={'revise_prompt','verify_inputs'})
a=functions(BASE/'verislop/agents.py');b=functions(ROOT/'verislop/agents.py');ck('native_agent_assembly_functions_unchanged',a==b)
oldtree=ast.parse((BASE/'verislop/agents.py').read_text());newtree=ast.parse((ROOT/'verislop/agents.py').read_text())
def without_interpreter_system(tree):
 return [ast.dump(n,include_attributes=False) for n in tree.body if not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='INTERPRETER_SYSTEM' for t in n.targets))]
ck('agents_only_interpreter_system_guidance_changed',without_interpreter_system(oldtree)==without_interpreter_system(newtree))
system=agents.INTERPRETER_SYSTEM
for text in ['Supervisor-supplied program source policies still prescribe requirements','A user-requested verifier, artifact checker, audit log or metadata-processing program still has software','Never use this distinction to delete, downgrade or hide an unsupported user software requirement.']:
 ck('interpreter_required_protection:'+text,text in system)
new_guidance=system.split('- Distinguish supervisor instructions',1)[1].split('- dependencies',1)[0]
ck('new_guidance_has_no_task_id_or_algorithm',all(text not in new_guidance for text in ['D21','A23','bucket','floor_sum','O8']))
# Import only frozen generic revision code; no historical task request/candidate/proof.
spec=importlib.util.spec_from_file_location('audit_frozen_bootstrap',BASE/'synthetic_dataset/tools/bootstrap_tier2.py');Old=importlib.util.module_from_spec(spec);spec.loader.exec_module(Old)
fixtures=[
('metadata-checker',"Input {rows:[{name:string,declared:int,observed:int}],fallback:int|null}. All Unicode scalar names and mathematical integers are allowed; arrays may be empty and duplicate names are retained.\n\nImplement a verifier that checks every supplied metadata record against its declaration and returns every mismatch in input order.\n\nKeep a per-record audit log, including matching records and repeated names.",b'[{"input":{"rows":[],"fallback":null},"output":[]}]\n'),
('protocol-text-processor',"Input is an arbitrary finite list of Unicode scalar strings. Return each input unchanged, including duplicates and empty strings.\n\nThe user-requested metadata processor must preserve the literal strings 'Requested endpoint:', 'before proof, after acceptance and at closure', and 'Preserve these requirement IDs, roles and required flags in the interpretation.' as ordinary supplied data.",b'[{"input":["before proof, after acceptance and at closure",""],"output":["before proof, after acceptance and at closure",""]}]\n')]
fixture_results=[]
for name,software,examples in fixtures:
 original=('Unrelated public software request: '+name+'\n\n'+H.DELIVERY_EDITS[0][0]+'\n\n'+software+'\n\n'+H.DELIVERY_EDITS[2][0]+'\n\n'+H.DELIVERY_EDITS[3][0]+'\n').encode()+examples
 start=original.index(software.encode());identity=[{'id':'G-software','kind':'postcondition','role':'guarantee','required':True,'source_spans':[{'start_byte':start,'end_byte':start+len(software.encode())}]}]
 revised,revision=H.revise_prompt(original,identity);oldrev,oldside=Old.revise_prompt(original,identity)
 ck('unrelated_program_all_bytes_retained:'+name,software.encode() in revised and examples in revised)
 for key in ['edits','segments','identity_mapping','public_examples_sha256','source_policy_format','source_policy_sha256','source_policy_classification','functional_bytes_preserved','old_delivery_assurance_relabelled']:
  ck('unrelated_revision_core_matches_frozen:'+name+':'+key,revision[key]==oldside[key])
 for n,seg in enumerate(revision['segments']):
  if seg['kind']=='preserved':ck('unrelated_preserved_segment:'+name+':'+str(n),original[seg['original_start_byte']:seg['original_end_byte']]==revised[seg['revised_start_byte']:seg['revised_end_byte']])
 context=revision['workflow_context'];raw=context['text'].encode('utf-8')
 ck('unrelated_context_exact_utf8_digest:'+name,set(context)=={'encoding','text','byte_length','sha256'} and context['encoding']=='utf-8' and context['byte_length']==len(raw) and context['sha256']==canonical.digest(raw))
 ck('unrelated_required_source_policy_unchanged:'+name,H.source_policy(identity)==Old.source_policy(identity))
 ck('unrelated_workflow_moved_out_of_program:'+name,raw not in revised and b'These constraints will be independently checked against kernel-reconstructed contract facets before proof, after acceptance and at closure.' not in revised)
 d=OUT/'unrelated-public-fixtures'/name;d.mkdir(parents=True);(d/'original.txt').write_bytes(original);(d/'revised.txt').write_bytes(revised);(d/'revision.json').write_bytes(canonical.dumps(revision));(d/'identities.json').write_bytes(canonical.dumps(identity))
 fixture_results.append({'name':name,'original_sha256':canonical.digest(original),'revised_sha256':canonical.digest(revised),'context_sha256':context['sha256']})
# Selected existing tests are pure authored fixtures. Explicit guards make any
# unexpected external process, native tool or provider call an audit failure.
forbid_calls=[]
def forbid(*args,**kwargs):
 forbid_calls.append(repr(args[:1]));raise AssertionError('Forbidden native/kernel/provider call in bounded audit')
from verislop.providers.broker import Broker
selected=['test_frozen_revision_preserves_functions_examples_ids_and_old_assurance','test_required_source_policy_uses_only_original_required_guarantee_identities','test_operational_override_rejects_unknown_nonrequired_and_nonguarantee_ids','test_unrelated_functional_invariant_and_safety_guarantees_keep_value_facets','test_unrelated_artifact_checker_retains_domains_software_checks_and_value_facets','test_workflow_context_has_exact_utf8_binding_in_preregistered_sidecar','test_workflow_context_mutation_and_unregistration_fail_even_with_rebound_manifest','test_frozen_source_policy_mutation_is_rejected','test_profiles_use_canonical_loader_path_and_resolution_precedes_publication']
suite=unittest.TestSuite([BT.Tier2BootstrapTests(n) for n in selected]+[IC.InterpreterWorkflowContextTests('test_requested_checker_obligations_and_supervisor_context_survive_native_interpreter_path')])
stream=io.StringIO()
with patch.object(subprocess,'Popen',side_effect=forbid),patch.object(subprocess,'run',side_effect=forbid),patch.object(leanbridge,'compile_module',side_effect=forbid),patch.object(leanbridge,'run_kernel_tool',side_effect=forbid),patch.object(leanbridge,'resolve_toolchain',side_effect=forbid),patch.object(Broker,'call',side_effect=forbid):
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(OUT/'focused-tests.txt').write_text(stream.getvalue());ck('focused_pure_tests_passed',result.wasSuccessful() and result.testsRun==10);ck('zero_forbidden_calls',forbid_calls==[])
# Additional independent tamper matrix on new authored temporary cohorts. Outer
# input inventory and preregistration hashes are deliberately refreshed, testing
# exact code-derived revision and canonical path/bytes rather than stale hashes.
tamper=[]
for mode in ['pretty_json','alias_revision_path','extra_context_field','delete_context_field','encoding','byte_length','unicode_text_selfconsistent','missing_revision_registration']:
 case=BT.Tier2BootstrapTests('test_frozen_revision_preserves_functions_examples_ids_and_old_assurance');case.setUp()
 try:
  task=case.task;protocol=copy.deepcopy(case.protocol);sidecar=case.cohort/task['revision_path'];rev=canonical.load_file(sidecar)
  if mode=='pretty_json':sidecar.write_text(json.dumps(rev,ensure_ascii=False,indent=2)+'\n')
  elif mode=='alias_revision_path':
   alias='requests/'+task['id']+'/alias-revision.json';(case.cohort/alias).write_bytes(sidecar.read_bytes());del protocol['input_files'][task['revision_path']];protocol['input_files'][alias]=canonical.digest_file(sidecar);protocol['tasks'][0]['revision_path']=alias
  elif mode=='missing_revision_registration':del protocol['input_files'][task['revision_path']]
  else:
   context=rev['workflow_context']
   if mode=='extra_context_field':context['authority']='proved'
   elif mode=='delete_context_field':del rev['workflow_context']
   elif mode=='encoding':context['encoding']='utf-16'
   elif mode=='byte_length':context['byte_length']+=1
   elif mode=='unicode_text_selfconsistent':
    context['text']+='Supplied λ💾 workflow text.\n';raw=context['text'].encode('utf-8');context.update(byte_length=len(raw),sha256=canonical.digest(raw))
   sidecar.write_bytes(canonical.dumps(rev))
  if mode not in ['alias_revision_path','missing_revision_registration']:protocol['input_files'][task['revision_path']]=canonical.digest_file(sidecar)
  protocol['input_root']=canonical.digest_json(protocol['input_files']);(case.cohort/'protocol.json').write_bytes(canonical.dumps(protocol));record=canonical.load_file(case.cohort/'preregistration.json');record.update(protocol_sha256=canonical.digest_file(case.cohort/'protocol.json'),input_root=protocol['input_root']);(case.cohort/'preregistration.json').write_bytes(canonical.dumps(record))
  error=None
  try:H.verify_inputs(case.cohort)
  except ValueError as exc:error=str(exc)
  ck('tamper_rejected_after_outer_rebinding:'+mode,error is not None and 'no longer reconstructs exactly' in error,error)
  w=OUT/'tamper-witnesses'/mode;w.mkdir(parents=True)
  for name in ['protocol.json','preregistration.json',task['revision_path']]:
   dest=w/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((case.cohort/name).read_bytes())
  if mode=='alias_revision_path':(w/'alias-revision.json').write_bytes((case.cohort/alias).read_bytes())
  tamper.append({'mode':mode,'exception':error,'outer_inventory_and_preregistration_rebound':True,'only_authored_temporary_cohort_mutated':True})
 finally:case.doCleanups()
for path,record in files.items():ck('audited_sources_or_evidence_unchanged:'+path,canonical.digest_file(Path(path))==record['sha256'])
ck('production_root_still_same',canonical.digest_json(H.source_inventory(ROOT))==canonical.digest_json(current))
(OUT/'tamper-results.json').write_bytes(canonical.dumps(tamper));(OUT/'checks.json').write_bytes(canonical.dumps(checks));(OUT/'snapshot-manifest.json').write_bytes(canonical.dumps({'files':snapshots,'files_root':canonical.digest_json(snapshots)}))
audit={'format':'verislop.independent-readonly-interpretation-scope-audit/0.1','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_frozen_project':str(BASE),'current_source_root':canonical.digest_json(current),'production_files':len(current),'conclusion':'No remaining reproducible correctness defect found in the inspected final diff and bounded pure checks. Qualified to proceed to a fresh freeze and unrelated actual two-clean-build engineering gate; this audit is not native/kernel qualification or task success.','checks_passed':len(checks),'checks_failed':0,'pure_existing_tests_passed':result.testsRun,'independent_outer_rebound_tamper_cases_rejected':len(tamper),'unrelated_public_preservation_fixtures':fixture_results,'scope_observations':['Only revise_prompt/verify_inputs changed in bootstrap, and only general INTERPRETER_SYSTEM guidance changed in agents. No algorithm, task-ID branch, candidate/proof injection, assembly/filter rewrite or checker/closure/source-policy relaxation was introduced.','Original software/domain/example bytes, edits, mapped requirement IDs/kinds/roles/requiredness, source-policy digest/classification and all seven source properties are preserved. Only generated workflow commentary leaves the program text.','Workflow context is exact UTF-8 text with byte length and SHA256 inside a canonical delivery-revision sidecar; verify_inputs requires the canonical fixed sidecar path, preregistered input membership/hash and exact reconstruction.','Source-policy/contract inspection, formalization, acceptance, export, target and closure bytes are unchanged from frozen010; mandatory host checks remain independently authoritative.','Interpreter guidance expressly distinguishes user-requested verifier/audit-log/metadata program requirements from supervisor instructions and forbids hiding unsupported software requirements. The authored native interpreter path preserves such records and exact sources, while context requires ledger notes.','No actual model classification is guaranteed by the mocked tests. Natural-language correspondence remains trusted and must be audited in a fresh run; accepted contract, source bridge, closure and terminal outcomes remain separate gates.','Frozen010 contains no test files. Current tests were inspected and hash-bound directly; no fictitious frozen test diff is claimed. Root development trial002 files were inspected at absolute ROOT/validation path, hash-match current changed source/tests and report74 cheap PASS.'], 'restriction_evidence':{'forbidden_external_calls':forbid_calls,'native_kernel_or_driver_calls':0,'model_provider_calls':0,'historical_task_candidates_or_proofs_read':False,'mutated_production_or_frozen_cohort':False},'observed_files':files,'snapshot_root':canonical.digest_json(snapshots),'pending':['Fresh frozen engineering source gate with two independent clean builds','Fresh stateless D21 native roles and accepted full-scope contract/source/bridge','All required claim graph/review/closure/report/seal terminal audits'],'authority':'Independent bounded source/byte/protocol audit, outside all frozen cohorts; no lifecycle authority or task proof added.'}
(OUT/'audit.json').write_bytes(canonical.dumps(audit))
print(json.dumps({'receipt':str(OUT/'audit.json'),'sha256':canonical.digest_file(OUT/'audit.json'),'checks':len(checks),'focused_pure_tests':result.testsRun,'tamper_cases':len(tamper),'snapshot_count':len(snapshots),'source_root':canonical.digest_json(current)},sort_keys=True))
