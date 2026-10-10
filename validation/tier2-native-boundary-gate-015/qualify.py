"""Compose unchanged production checks and a separately frozen unit correction."""
from pathlib import Path
from datetime import datetime,timezone
import re
from synthetic_dataset.tools import bootstrap_tier2 as b
from verislop import canonical
root=Path.cwd();g=root/'validation/tier2-native-boundary-gate-015'
freeze=b.load(g/'source-freeze.json');source=b.source_inventory()
assert source==freeze['source_files']
project=root/'synthetic_dataset/bootstrap/stages/tier2-source-facets-015/project'
assert {k:canonical.digest_file(project/k) for k in source}==source
assert b.load(project/'TIER2-SNAPSHOT.json')['source_root']==freeze['source_root']
assert not (project.parent/'run').exists()
e=b.load(g/'engineering-validation.json');b.verify_engineering_record(e)
r=b.load(g/'run-result.json');c=b.load(g/'fixture-correction/result.json')
assert (r['status'],r['tests_run'],r['errors'],r['failures'],r['skipped'])==('FAIL',162,1,0,0)
assert r['source_unchanged'] and r['test_sources_unchanged'] and r['fresh_model_calls']==0
assert (c['status'],c['tests_run'],c['errors'],c['failures'],c['skipped'])==('PASS',23,0,0,0)
assert c['source_unchanged'] and c['production_root']==freeze['source_root'] and c['task_model_calls']==0
rows=lambda text:dict(re.findall(r'^(test_\S+ \([^\n]+\)) \.\.\. (ok|ERROR)$',text,re.M))
old=rows((g/'gate.stderr.log').read_text());new=rows((g/'fixture-correction/unittest.log').read_text())
assert len(old)==162 and list(old.values()).count('ok')==161 and list(old.values()).count('ERROR')==1
assert {k for k in old if '(tests.test_compile_process_evidence.' in k}==set(new)
assert len(new)==23 and set(new.values())=={'ok'}
for name,sha in r['test_sources'].items():
 if name!='tests/test_compile_process_evidence.py':assert canonical.digest_file(root/name)==sha
oldfile=root/'validation/tier2-compile-process-evidence/compile-process-attempt-ea_69slk/inputs/tests/test_compile_process_evidence.py'
assert canonical.digest_file(oldfile)==r['test_sources']['tests/test_compile_process_evidence.py']
expected=oldfile.read_text().replace('spec = SimpleNamespace(symbols=[])','spec = SimpleNamespace(symbols=[], readable_selection=None)').replace('        self.assertTrue(info["proof_checked"])\n','        self.assertTrue(info["proof_checked"])\n        self.assertIsNone(info["readable_selection"])\n        self.assertIsNone(info["readable_source_view"])\n        self.assertEqual(info["readable_candidate_artifacts"], {})\n')
assert expected==(root/'tests/test_compile_process_evidence.py').read_text()
assert canonical.digest_file(root/'tests/test_compile_process_evidence.py')==c['test_sha256']
assert canonical.digest_file(g/'fixture-correction/unittest.log')==c['log_sha256']
a=root/'validation/tier2-readable-semantic-review/selected-final015-togsb7ww';ar=b.load(a/'review.json');am=b.load(a/'manifest.json')
assert ar['result']=='PASS_BOUNDED_ARTIFACT_AUDIT' and not ar['findings'] and ar['check_counts']['total']==43
assert canonical.digest_file(a/'review.json')==am['review_sha256']
for name,ref in am['artifacts'].items():
 p=a/name;assert p.stat().st_size==ref['size'] and canonical.digest_file(p)==ref['sha256']
f=root/'validation/tier2-native-boundary-gate-015-fixture-review/review-attempt-8cmfopsd/review.json';fr=b.load(f)
assert fr['review_status']=='CHECKED_CONSISTENT' and not fr['findings']
refs=[g/'source-freeze.json',g/'engineering-validation.json',g/'run-result.json',g/'gate.py',g/'gate.stdout.log',g/'gate.stderr.log',g/'test-sources.json',g/'driver.py',g/'qualify.py',g/'prelive-qualification-specification.json',g/'fixture-correction/specification.json',g/'fixture-correction/invocation.json',g/'fixture-correction/result.json',g/'fixture-correction/unittest.log',a/'review.json',a/'manifest.json',f,project/'TIER2-SNAPSHOT.json']
for rel in ['matrix-final015-7rn4kn4c','replay-final015-9v4p8eq2']:
 refs.append(root/'validation/tier2-readable-semantic-review'/rel/'review.json')
checkpoint={'format':'verislop.composed-prelive-qualification/1','status':'QUALIFIED_FOR_FRESH_GENERATION','created_at_utc':datetime.now(timezone.utc).isoformat(),'source_root':freeze['source_root'],'source_files':len(source),'qualified_endpoint':'restricted_source','tier':2,'engineering_closure':{'status':e['status'],'closure_root':e['closure_root'],'required_claims':len(e['required_claim_observations']),'builds':[x['build'] for x in e['builds']],'mismatches':e['determinism']['mismatches']},'original_gate':{'status':'FAIL','executed_tests':162,'ok_rows':161,'errors':1,'rescored':False},'separate_fixture_correction':{'status':'PASS','executed_tests':23,'same_method_names':True,'production_changed':False},'fresh_all162_pass_claim':False,'task_model_calls_before_qualification':0,'task_cohort_prepared_before_qualification':False,'audit_result':ar['result'],'bound_records':{str(p.relative_to(root)):canonical.digest_file(p) for p in refs},'test_source_after_correction':c['test_sha256'],'scope':'Exact current generic engineering readiness only; fresh task obligations are not discharged by this checkpoint.'}
assert b.source_inventory()==source
b.write_once(g/'prelive-qualified-checkpoint.json',checkpoint)
print({'status':checkpoint['status'],'sha256':canonical.digest_file(g/'prelive-qualified-checkpoint.json'),'source_root':freeze['source_root']})
