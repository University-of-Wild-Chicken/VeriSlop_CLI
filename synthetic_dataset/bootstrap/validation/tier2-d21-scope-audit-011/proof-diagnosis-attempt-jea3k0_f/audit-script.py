from pathlib import Path
from datetime import datetime, timezone
import ast, hashlib, json, os, copy

ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-011'
PROJECT=STAGE/'project'
PKG=STAGE/'run/artifacts/D21/verislop/package'
MB=PKG.parent/'mailbox'
ATT=PKG/'agents/vscore-attempts'
STD=Path('/home/augustus/.elan/toolchains/leanprover--lean4---v4.34.1/src/lean')
OUT=Path(__file__).parent
SOURCE_ROOT='sha256:b9d1ba95eae0bf4e1eb824b5d729ad26b33bf2d5bcc857899825eb446babac5a'
def sha(b): return 'sha256:'+hashlib.sha256(b).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=True,indent=2,sort_keys=True)+'\n')
inputs={}
def capture(p):
 p=Path(p).absolute()
 if p in inputs: return inputs[p]['bytes']
 b=p.read_bytes()
 if p.is_relative_to(PKG): rel=Path('package')/p.relative_to(PKG)
 elif p.is_relative_to(MB): rel=Path('mailbox')/p.relative_to(MB)
 elif p.is_relative_to(PROJECT): rel=Path('project')/p.relative_to(PROJECT)
 elif p.is_relative_to(STD): rel=Path('pinned-lean')/p.relative_to(STD)
 else: raise ValueError(str(p))
 q=OUT/'snapshots'/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 inputs[p]={'bytes':b,'snapshot':str(q.relative_to(OUT)),'sha256':sha(b)}
 return b

def read_json(p): return json.loads(capture(p))
checks=[]
def check(name,condition,details=None):
 checks.append({'name':name,'pass':bool(condition),'details':details})
 if not condition: raise AssertionError(name)

# Exact current-stage candidate/check/carrier evidence only; no historical task source.
for name in ('program.vscore.json','relation.json','VeriSlopBridgeGoal.lean','checks/source.json'):
 capture(ATT/'source-2'/name)
for i in (1,2,3):
 capture(ATT/f'source-2/proofs/{i}.lean');capture(ATT/f'source-2/checks/proof-{i}.json')
for name in ('program.vscore.json','relation.json','source-diagnostics.json','response.txt','checks/source.json'):
 capture(ATT/'source-3'/name)
for i in(14,15,16,17):
 for kind in ('request','carrier','carrier-binding','response','response-receipt'):
  capture(MB/f'{kind}-{i:04d}.json')
for name in ('accepted/accepted-ir.json','accepted/acceptance.json'):
 capture(PKG/name)
for name in ('verislop/targets/vscore3_target.py','verislop/bridges/vscore3_checker.py','verislop/targets/vscore3_source.py','verislop/lean/SourceBoundary.lean'):
 p=PROJECT/name
 if p.exists(): capture(p)
for name in ('Init/ByCases.lean','Init/SimpLemmas.lean','Init/PropLemmas.lean','Init/Data/Int/Basic.lean','Init/Data/List/Lemmas.lean'):
 capture(STD/name)

contexts={}
for i in(14,15,16):
 req=read_json(MB/f'request-{i:04d}.json');carrier=read_json(MB/f'carrier-{i:04d}.json')
 binding=read_json(MB/f'carrier-binding-{i:04d}.json');response=read_json(MB/f'response-{i:04d}.json');receipt=read_json(MB/f'response-receipt-{i:04d}.json')
 check(f'{i}.carrier request digest',carrier['request_sha256']==sha(capture(MB/f'request-{i:04d}.json')))
 check(f'{i}.binding request digest',binding['request_sha256']==carrier['request_sha256'])
 check(f'{i}.binding carrier digest',binding['carrier_sha256']==sha(capture(MB/f'carrier-{i:04d}.json')))
 check(f'{i}.carrier user/system exact',(carrier['user'],carrier['system'])==(req['user'],req['system']))
 check(f'{i}.response request digest',response['request_sha256']==carrier['request_sha256'])
 check(f'{i}.receipt request digest',receipt['request_sha256']==carrier['request_sha256'])
 check(f'{i}.receipt response digest',receipt['response_sha256']==sha(capture(MB/f'response-{i:04d}.json')))
 check(f'{i}.receipt text digest',receipt['text_sha256']==sha(response['text'].encode()))
 prefix='FIXED VSCORE PROOF CONTEXT (data):\n'
 check(f'{i}.proof context header',req['user'].startswith(prefix))
 ctx,n=json.JSONDecoder().raw_decode(req['user'][len(prefix):]);contexts[i]=ctx
 check(f'{i}.context source hash',ctx['source_hash']==sha(capture(ATT/'source-2/program.vscore.json')))
 check(f'{i}.context goal exact',ctx['generated_goal'].encode()==capture(ATT/'source-2/VeriSlopBridgeGoal.lean'))
 check(f'{i}.refinement binding exact',ctx['refinement_symbols']==['solve'])
 for module,text in ctx['verifier_library'].items():
  b=capture(PROJECT/'verislop/lean'/Path(module.replace('.','/')+'.lean'))
  check(f'{i}.library exact {module}',b==text.encode())
 ref=ctx['accepted_reference'];p=Path(ref['path']);p=p if p.is_absolute() else PKG/p
 b=capture(p)
 check(f'{i}.accepted reference bytes',b==ref['lean_source'].encode())
 check(f'{i}.accepted reference hash',sha(b)==ref['sha256'])
 if i>14:
  check(f'{i}.fixed context exact',ctx==contexts[14])

# Request 17 is the independently delivered current source 3, not a fourth proof attempt.
i=17
req=read_json(MB/f'request-{i:04d}.json');carrier=read_json(MB/f'carrier-{i:04d}.json')
binding=read_json(MB/f'carrier-binding-{i:04d}.json');response=read_json(MB/f'response-{i:04d}.json');receipt=read_json(MB/f'response-receipt-{i:04d}.json')
for name,condition in (
 ('carrier request digest',carrier['request_sha256']==sha(capture(MB/f'request-{i:04d}.json'))),
 ('binding request digest',binding['request_sha256']==carrier['request_sha256']),
 ('binding carrier digest',binding['carrier_sha256']==sha(capture(MB/f'carrier-{i:04d}.json'))),
 ('carrier user/system exact',(carrier['user'],carrier['system'])==(req['user'],req['system'])),
 ('response request digest',response['request_sha256']==carrier['request_sha256']),
 ('receipt request digest',receipt['request_sha256']==carrier['request_sha256']),
 ('receipt response digest',receipt['response_sha256']==sha(capture(MB/f'response-{i:04d}.json'))),
 ('receipt text digest',receipt['text_sha256']==sha(response['text'].encode())),
 ('source role',req['instance']=='implementer/vscore/3')):
 check(f'{i}.{name}',condition)

# Preserve complete retained diagnostic bytes and readable exact compiler-error list.
error_lists={}
for i in(1,2,3):
 x=read_json(ATT/f'source-2/checks/proof-{i}.json')
 check(f'proof{i}.failed',x['passed'] is False)
 check(f'proof{i}.host invoked proof checker',x['proof_checked'] is True)
 check(f'proof{i}.exact source hash',x['source_hash']==sha(capture(ATT/'source-2/program.vscore.json')))
 check(f'proof{i}.candidate build diagnostic',len(x['diagnostics'])==1 and x['diagnostics'][0]['code']=='CANDIDATE_BUILD_FAILURE')
 msg=x['diagnostics'][0]['message']
 errors=ast.literal_eval(msg.split(': ',1)[1]);error_lists[i]=errors
 (OUT/f'proof-{i}-retained-errors.txt').write_text('\n\n'.join(errors)+'\n')
check('proof1.transparency note retained','implicit' in error_lists[1][0] and 'Application type mismatch' in error_lists[1][0])
check('proof2.Int constructor versus cast retained','Int.ofNat k' in error_lists[2][0] and '↑k' in error_lists[2][0])
check('proof3.Int constructor versus cast retained','Int.ofNat k' in error_lists[3][0] and '↑k' in error_lists[3][0])
check('proof2.Bool decide condition retained','decide (0 < (stats x g k).count) = true' in error_lists[2][2])
check('proof3.lambda identity mismatch retained','List.map (fun g => g)' in error_lists[3][2])
proof3=capture(ATT/'source-2/proofs/3.lean').decode()
check('proof3.narrow identity-only simp present','simp only [List.map_id] at h' in proof3 and 'simpa only [List.map_id, List.map_nil] using h' in proof3)

# Exact pinned definitions and theorem inventory; this is source inspection, not kernel replay.
intsrc=capture(STD/'Init/Data/Int/Basic.lean').decode()
bycases=capture(STD/'Init/ByCases.lean').decode()
listsrc=capture(STD/'Init/Data/List/Lemmas.lean').decode()
simpsrc=capture(STD/'Init/SimpLemmas.lean').decode()
check('nat cast uses Int.ofNat','instance : NatCast Int where natCast n := Int.ofNat n' in intsrc)
check('ofNat_eq_natCast reflexive simp theorem','@[simp] theorem ofNat_eq_natCast (n : Nat) : Int.ofNat n = n := rfl' in intsrc)
check('apply_ite generic theorem exists','theorem apply_ite (f : α → β) (P : Prop) [Decidable P] (x y : α)' in bycases)
for marker in ('theorem foldl_map {','theorem foldl_hom (','theorem map_id\' (','theorem map_id_fun\' :'):
 check('pinned '+marker,marker in listsrc)
for marker in ('theorem decide_eq_true_eq','theorem decide_eq_false_iff_not'):
 check('pinned '+marker,marker in simpsrc)
transport=capture(PROJECT/'verislop/lean/VSCore3/Transport.lean').decode()
check('transport lacks dedicated foldl helper','foldl' not in transport)
check('transport lacks dedicated apply_ite helper','apply_ite' not in transport)
checker=capture(PROJECT/'verislop/bridges/vscore3_checker.py').decode()
check('diagnostics bounded to first3',"{res.errors[:3]}" in checker)

# Pure symbolic AST comparison with names for binders, not execution of the task program.
a=read_json(ATT/'source-2/program.vscore.json');b=read_json(ATT/'source-3/program.vscore.json')
aha={h['id']:h for h in a['helpers']};ahb={h['id']:h for h in b['helpers']}
for field in ('declarations','entries','language','profile'):
 check('source2/source3 exact '+field,a[field]==b[field])
check('only helper deleted',set(aha)-set(ahb)=={'bucket_start'} and not(set(ahb)-set(aha)))
for name in ('bucket_count','group_rows','groups'):
 check('source2/source3 exact helper '+name,aha[name]==ahb[name])
def named(e,env,depth=0):
 if isinstance(e,list): return [named(v,env,depth) for v in e]
 if not isinstance(e,dict): return e
 tag=e.get('tag')
 if tag=='var':
  check('named variable in range',0<=e['index']<len(env))
  return copy.deepcopy(env[e['index']])
 if tag=='call' and e['helper']=='bucket_start':
  args=[named(v,env,depth) for v in e['args']]
  return named(aha['bucket_start']['body'],list(reversed(args)),depth)
 out={}
 for k,v in e.items():
  ext=env
  if tag=='list_fold' and k=='step': ext=[{'tag':'named_var','name':f'item{depth}'},{'tag':'named_var','name':f'acc{depth}'}]+env
  elif tag=='match_option' and k=='some': ext=[{'tag':'named_var','name':f'some{depth}'}]+env
  elif tag=='let' and k=='body': ext=[{'tag':'named_var','name':f'let{depth}'}]+env
  out[k]=named(v,ext,depth+1 if ext is not env else depth)
 return out
env=[{'tag':'named_var','name':n} for n in ('index','group','input')]
n2=named(aha['stats']['body'],env);n3=named(ahb['stats']['body'],env)
check('stats fold source/initial exact',n2['source']==n3['source'] and n2['initial']==n3['initial'])
s2=n2['step'];s3=n3['step']
check('stats changed if-option versus option-if',s2['tag']=='if' and s2['then']['tag']=='match_option' and s3['tag']=='match_option' and s3['some']['tag']=='if')
check('stats exact option scrutinee',s2['then']['scrutinee']==s3['scrutinee'])
check('stats exact pure guard after inlining',s2['cond']==s3['some']['cond'])
check('stats exact nonempty update',s2['then']['some']==s3['some']['then'])
check('stats all none/false cases same accumulator',s2['then']['none']==s2['else']==s3['none']==s3['some']['else'])
stepenv=[{'tag':'named_var','name':n} for n in ('state','index','group','input')]
check('step exact after bucket_start inlining',named(aha['step']['body'],stepenv)==named(ahb['step']['body'],stepenv))
dump(OUT/'symbolic-source-comparison.json',{'method':'pure tree substitution only; no execution/refinement proof','stats2':n2,'stats3':n3,'checks':'if C then match v with none=>a|some u=>b else a; match v with none=>a|some u=>if C then b else a; C and b unchanged under exact named binders','entry_declarations_other_helpers':'identical','step':'identical after exact bucket_start syntactic substitution'})
r2=read_json(ATT/'source-2/relation.json');r3=read_json(ATT/'source-3/relation.json')
check('relation only slots differ',{k:v for k,v in r2.items() if k not in ('source_slot','proof_slot')}=={k:v for k,v in r3.items() if k not in ('source_slot','proof_slot')})
s3check=read_json(ATT/'source-3/checks/source.json')
check('source3 host rejection',s3check['passed'] is False and s3check['proof_checked'] is False and s3check['diagnostics'][0]['code']=='INVALID_CANDIDATE')
check('source3 slot diagnostic exact',s3check['diagnostics'][0]['message']=='relation slots must be vscore-source and vscore-proof for this helper')
check('source3 diagnostic binds current bytes',s3check['source_hash']==sha(capture(ATT/'source-3/program.vscore.json')))

# Source bytes read earlier must remain exact after bounded inspection.
for p,row in inputs.items(): check('observed input stable '+str(p),p.read_bytes()==row['bytes'])
manifest={'format':'verislop.independent-read-only-input-snapshot/0.1','source_root_context':SOURCE_ROOT,'files':[{'source':str(p),'snapshot':row['snapshot'],'sha256':row['sha256'],'bytes':len(row['bytes'])} for p,row in sorted(inputs.items(),key=lambda v:str(v[0]))]}
dump(OUT/'manifest.json',manifest)
dump(OUT/'pure-checks.json',checks)
shapes='''Bounded proof-search diagnosis; theorem shapes only, no new task proof.

Retained conditional residual, abstracted from proof2 and proof3:
  ((if P then t else a).count, (if P then t else a).sum, ()) =
  if P then (t.count, t.sum, ()) else (a.count, a.sum, ())
This is function application through ite, for arbitrary P, a, and t.

Pinned Init.ByCases.apply_ite:
  (f : α → β) (P : Prop) [Decidable P] (x y : α) :
  f (ite P x y) = ite P (f x) (f y)

Pinned Int.ofNat_eq_natCast, annotated [simp], existing proof rfl:
  (n : Nat) : Int.ofNat n = (n : Int)
Pinned NatCast Int definition: natCast n := Int.ofNat n.
Thus the Int.ofNat k versus ↑k printouts are not different integer semantics.
A hypothesis being used before its cast spelling is normalized can survive a
single simp pass even when the target has the same mathematical guard.
No tactic replay was run by this auditor, so the causal account is limited to
exact retained residuals and pinned source definitions.

Pinned List.foldl_map:
  {f : β₁ → β₂} {g : α → β₂ → α} {l : List β₁} {init : α} :
  (l.map f).foldl g init = l.foldl (fun x y => g x (f y)) init
Pinned List.foldl_hom:
  (f : α₁ → α₂) {g₁ : α₁ → β → α₁} {g₂ : α₂ → β → α₂}
  {l : List β} {init : α₁}
  (H : ∀ x y, g₂ (f x) y = f (g₁ x y)) :
  l.foldl g₂ (f init) = f (l.foldl g₁ init)
Pinned List.map_id uses map id; List.map_id' and List.map_id_fun'
explicitly use map (fun a => a). The failed attempt restricts simplification
to List.map_id and retains exactly that lambda spelling in its goal.

Pinned decide_eq_true_eq [Decidable p] : (decide p = true) = p
Pinned decide_eq_false_iff_not [Decidable p] : (decide p = false) ↔ ¬p
The proof2 count branches retain a Bool equation rather than the corresponding
Nat comparison; its displayed implications are vacuous under that comparison.

Generic representation-library ergonomic shape (not a new theorem or proof):
  for f : α → β, f (if P then a else b) = if P then f a else f b.
This is already apply_ite. A VSCore3 adapter alias could expose the same shape
for a.to / a.inv, but mathematical foundations are not missing.
Generic combined fold representation shape is already present as candidate
private foldl_transport and follows the pinned foldl_map / foldl_hom interfaces.
No D21-specific statement, tactic patch, or replacement proof is supplied.
'''
(OUT/'small-theorem-shapes.txt').write_text(shapes)
audit={'format':'verislop.independent-proof-search-diagnosis/0.1','observed_at_utc':datetime.now(timezone.utc).isoformat(),'task':'D21','stage':'tier2-source-facets-011','source_root_context':SOURCE_ROOT,'scope':'same-current-stage source2 proof attempts 1..3 and carriers0014..0017; source3 structural annex; pinned generic library source inspection only','source2_hash':sha(capture(ATT/'source-2/program.vscore.json')),'goal_hash':sha(capture(ATT/'source-2/VeriSlopBridgeGoal.lean')),'source3_hash':sha(capture(ATT/'source-3/program.vscore.json')),'manifest_hash':sha((OUT/'manifest.json').read_bytes()),'auditor_script_hash':sha(Path(__file__).read_bytes()),'pure_checks':len(checks),'input_files':len(inputs),'findings':[{'id':'P1','classification':'candidate tactic transparency failure, not a demonstrated kernel typing flaw','evidence':'proof1 retained error60:25 notes implicit transparency application type mismatch after broad compiler/entry unfolding. Generated entry has explicit canonical params/result and full-transparency extraction. Proof2/3 retained failures are ordinary typed expressions. No kernel invocation by auditor.'},{'id':'P2','classification':'incomplete conditional representation transport / normalization','evidence':'proof2 rawStats_eq and proof3 rawStats_eq retain packing of ite versus ite of packing. Pinned apply_ite already states the needed generic identity. Cast spellings differ in hypotheses and residual guard, but NatCast Int is defined by Int.ofNat and existing equality is rfl. This is not a signed-domain or arithmetic-semantic difference.'},{'id':'P3','classification':'incomplete Boolean-to-Proposition case normalization','evidence':'proof2 rawStep_eq retains decide(0<count)=true/false while goal has zero/positive-count implications. Existing pinned decide bridges expose those same propositions. Proof3 switches to proposition cases and no rawStep failure appears among its first3 retained errors; this is not exhaustive success evidence.'},{'id':'P4','classification':'candidate restricted simp set misses lambda identity-map spelling','evidence':'proof3 line113 simp only[List.map_id] made no progress; line128 retains List.map(fun g=>g). Pinned List.map_id\' / map_id_fun\' explicitly target lambda form. No representation/type change required by that residual.'},{'id':'S3','classification':'separate invalid metadata, no admitted third source','evidence':'current source3 relation slots implementation_source/implementation_proof violate helper-required vscore-source/vscore-proof. Its source check fails INVALID_CANDIDATE before proof checking. Static comparison finds identical declarations/entry/other three helpers; bucket_start is inlined and removed, stats pure option match moves outside unchanged guard with correctly shifted named binders, step otherwise identical.'}], 'conclusion':'No reproduced generic source/goal semantic counterexample or inconsistent type requirement in the retained diagnostics. Existing pinned generic lemmas cover the displayed normal forms; an adapter/fold helper facade would be ergonomic, not a missing mathematical axiom. Proof attempts remain failed; no refinement, implementation correctness, accepted third source, closure, or lifecycle upgrade is asserted.','limitations':['Native compiler errors are explicitly bounded to first3 entries by vscore3_checker.py. No claim that these are all remaining errors or that any unreported helper theorem is proved.','No Lean/kernel, model, mechanical closure, gate, task evaluation, or hidden/historical task artifacts used. No code/source/proof/package edits or author/controller communication.','Pure symbolic source2/source3 comparison establishes exact representation differences and binder preservation only; it is not universal refinement proof.','Existing accepted/frozen-scope audit is carried forward only as observation, not replacement proof authority.'],'pending':['accepted materialized implementation','successful universal bridge proof','mechanical closure','release/terminal state']}
dump(OUT/'audit.json',audit)
dump(OUT/'receipt.json',{'audit_hash':sha((OUT/'audit.json').read_bytes()),'manifest_hash':audit['manifest_hash'],'checks_hash':sha((OUT/'pure-checks.json').read_bytes()),'theorem_shapes_hash':sha((OUT/'small-theorem-shapes.txt').read_bytes()),'symbolic_comparison_hash':sha((OUT/'symbolic-source-comparison.json').read_bytes()),'script_hash':audit['auditor_script_hash'],'passed':all(x['pass'] for x in checks),'checks':len(checks),'input_files':len(inputs)})
print(json.dumps({'receipt':str(OUT),'audit_hash':sha((OUT/'audit.json').read_bytes()),'checks':len(checks),'input_files':len(inputs),'result':'bounded diagnosis; no semantic/type counterexample reproduced'},sort_keys=True))
