import datetime,hashlib,json,pathlib,re
OUT=pathlib.Path(__file__).resolve().parent

def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
assert re.search(r'Ran 48 tests in .*\n\nOK\s*$',(OUT/'focused.stderr.txt').read_text())
checks=read(OUT/'checks.json');assert checks['count']==143 and checks['pass']==143
capture=read(OUT/'capture.json')
review={
 'format':'verislop.independent-compile-process-projection-followup/1',
 'decision':'PASS_BOUNDED_CORRECTED_NORMALIZER_NOT_NATIVE_QUALIFICATION',
 'reviewer':'/root/tier2_semantics_audit','completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'prior_review':{'path':'validation/tier2-compile-process-evidence-review/review-attempt-jccsmiil/review.json','sha256':'sha256:4a770e9d08d39e34bd3c883bdcac01dd48eced2509829337f4be75a14fd29f76','preserved_decision':'REVISION_REQUIRED_CONCRETE_RELEASE_NORMALIZER_COMPATIBILITY_DEFECT'},
 'prior_witness':{'sha256':'sha256:76b0828fb663df7357136ce3564e29cecb39bdc97609310d743b000f120ea0c3','exact_replay':'Both exact original records/raw hashes authenticated; original legacy and newly additive telemetry payload now normalize. Full raw result is preserved apart from the original top-level volatile wrappers.'},
 'repaired_input_hashes':capture['repaired_files'],
 'results':{'focused_tests':48,'focused_pass':48,'independent_pure_checks':143,'independent_pure_pass':143,'concrete_remaining_defects_found':0},
 'finding_resolution':{'id':'CPE-AUDIT-01','status':'RESOLVED_IN_CAPTURED_REPAIRED_CODE','evidence':['replay.json','checks.json','focused.stderr.txt','repaired-inputs/verislop/review_projection.py'],'scope':'Only the prior concrete release-normalizer format defect and explicit bounded repair requirements; no task/native outcome is revised.'},
 'inspected_invariants':[
  'Exactly four .3 producer alternatives: legacy, process inventory, readable support, or both; full nested payloads retained.',
  'The original .1 field set remains unchanged and rejects every .3-only extension; all other producer alternatives remain unchanged.',
  'Every original required producer/wrapper field is still required. An extra unknown top-level field rejects every .3 variant.',
  'Complete successful-build outputs admit exactly original fields or original fields plus readable_support. Unknown or missing required output fields reject. Removing the optional support field yields the explicit legacy variant.',
  'The normalizer registry publishes every exact producer and build-output alternative and changes its source identity. Earlier historical registry/source identities are not rewritten.',
  'Nested path, time, recorded_at and sequence keys are retained verbatim inside frozen process and support payloads; no recursive metadata filtering was introduced.',
  'Original EXCLUDED_PATHS and evidence wrappers are unchanged; elapsed execution metadata normalization remains positional.',
  'The added regression executes actual checker.outputs, EvidenceStore persistence, hash-bound raw reader and release normalizer; only semantic descriptor/schema setup is mocked and no proof/kernel success is claimed.'
 ],
 'test_runtime':capture['runtime'],
 'limitations':[
  'No native/Lean/kernel/gate/model invocations, source/doc/test edits or subagents.',
  'No retained task/cohort candidate, proof, case or outcome was inspected or rescored.',
  'Previously captured qualifying telemetry modules remain fixed in the runtime; only repaired projection and its new test are overlaid. Concurrent readable implementation changes are excluded and require their own review.',
  'Saved synthetic evidence authenticates producer-format compatibility. Passing normalize alone does not authorize current semantic evidence; normal mechanical validation and verifier-current checks remain mandatory.',
  'Readable support descriptor internals are preserved, not independently kernel-qualified by these normalizer tests. Actual payload/schema/source/module checks remain checker/closure duties.',
  'Full frozen telemetry is consumed evidence, not a fresh A/B comparison field. This review does not recommend dropping it.',
  'Independent native engineering qualification remains outstanding/parent-owned.'
 ]
}
(OUT/'review.json').write_text(json.dumps(review,indent=2)+'\n')
rows=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file() and p.name not in {'receipt-manifest.json','receipt-summary.json'}:
  b=p.read_bytes();rows.append({'path':str(p.relative_to(OUT)),'sha256':digest(b),'size':len(b)})
manifest={'format':'verislop.independent-compile-process-followup-seal/1','file_count':len(rows),'files':rows,'inventory_root':digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())}
(OUT/'receipt-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
summary={'decision':review['decision'],'review_sha256':digest((OUT/'review.json').read_bytes()),'replay_sha256':digest((OUT/'replay.json').read_bytes()),'manifest_sha256':digest((OUT/'receipt-manifest.json').read_bytes()),'inventory_root':manifest['inventory_root'],'file_count':len(rows),'focused_tests_pass':48,'independent_pure_checks_pass':143,'remaining_concrete_defects':0}
(OUT/'receipt-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
for p in OUT.rglob('*'):
 if p.is_file():p.chmod(0o444)
for p in sorted((p for p in OUT.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):p.chmod(0o555)
OUT.chmod(0o555)
