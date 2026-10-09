from pathlib import Path
import json,sys,hashlib,datetime
AUDIT=Path(__file__).resolve().parent
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-010'
PROJECT=STAGE/'project'
RUN=STAGE/'run'
PKG=RUN/'artifacts/A23/verislop/package'
sys.path.insert(0,str(PROJECT))
from verislop import canonical,contract as C,export,source_policy
from verislop.package import Package

def write(name,obj):
 (AUDIT/name).write_bytes(canonical.dumps(obj))
def diagnostics(ds): return [d.as_dict() for d in ds]
checks=[]
def check(label,result,details=None):
 checks.append({'check':label,'passed':bool(result),'details':details})
 if not result: raise AssertionError(label)
inputs={}
def capture(p):
 p=Path(p).resolve()
 rel=p.relative_to(STAGE).as_posix()
 data=p.read_bytes()
 dest=AUDIT/'inputs'/rel
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_bytes(data)
 inputs[rel]={'sha256':canonical.digest(data),'size':len(data),'observed_path':str(p)}
 return data
p=Package(PKG)
ir,ih,cert,diags=export.verified_ir(p)
check('registered acceptance, IR and source-policy evidence integrity',not diags,diagnostics(diags))
cert_hash=canonical.digest_file(PKG/ir['acceptance_certificate_ref'])
pol=C.frozen_json(p,'policy.json')
form=C.frozen_json(p,'formalization.json')
claims=canonical.load_file(p.path('claims'))['obligations']
env_json=canonical.load_file(PKG/cert['artifacts']['environment_export']['path'])
env=C.Env.from_export(env_json,pol,'independent accepted audit')
check('accepted export import/replay safety and axiom policy',not env.diagnostics,diagnostics(env.diagnostics))
a=C.analyze(env,claims,form,pol,cert['toolchain']['pin'],'independent accepted audit')
check('pure reconstruction from kernel-replayed registry and declarations',not a.diagnostics,diagnostics(a.diagnostics))
check('independent exact source-policy package inspection',not source_policy.check_package(p,a.statements,claims))
check('reconstructed complete statement artifact exact',canonical.dumps(a.statements)==capture(PKG/cert['artifacts']['statements']['path']))
check('reconstructed complete carrier profile exact',canonical.dumps(a.profile)==capture(PKG/cert['artifacts']['profile']['path']))
reg={r['id']:r for r in a.registry}
check('exact frozen registry ID coverage',set(reg)==set(ir['obligations'])=={r['id'] for r in claims})
meta=canonical.loads(capture(RUN/'requests/A23/original-metadata.json'))
for original in meta['identities']:
 oid=original['id']
 check('original identity preserved '+oid,all(ir['obligations'][oid][k]==original[k] and reg[oid][k]==original[k] for k in ['id','kind','role','required']))
check('all nine frozen obligations remain required',len(reg)==9 and all(r['required'] for r in reg.values()))
for oid,r in ir['obligations'].items():
 st=a.statements[oid]
 check('statement/closure/certificate identity '+oid,all(r['formal'][k]==st[k] for k in ['statement_hash','semantic_closure_hash','lean_symbol','representation','hypotheses']))
 check('mechanical dependencies reconstructed '+oid,r['dependencies']==export.mechanical_dependencies(oid,st,a.statements,cert['obligations'][oid],reg[oid],{x['id']:x['witnesses_for'] for x in form['internal_obligations']}))
 check('kernel TYPECHECKED obligation '+oid,cert['obligations'][oid]['typechecked']=='PASS')
 check('proof outcome applicability '+oid,cert['obligations'][oid]['proved']==('PASS' if r['role']=='guarantee' else 'NOT_APPLICABLE'))
 expected=st.get('formula_package')
 if expected is None:
  expected={'encoding':'verislop.typed-metadata/0.1','semantic_profile':a.profile['profile_id'],'registry_entry':C.REGISTRY_NS+'.'+oid,'bindings':{n:env.hashes[n] for n in st['bindings']}}
 exprpath=PKG/'accepted/expressions'/(r['formal']['formula_ref'].rsplit(':',1)[1]+'.json')
 check('exact kernel-derived expression '+oid,canonical.dumps(expected)==capture(exprpath))
allowed=set(pol['allowed_axioms'])
check('no custom module axioms',not [n for n,c in env.decls.items() if c['kind']=='axiom'])
check('no sorryAx in any replayed declaration',not [n for n,c in env.decls.items() if any('sorryAx' in C.name_str(x) for x in c.get('axioms',[]))])
check('only policy-permitted imported axioms',all(set(row['axioms'])<=allowed for row in cert['obligations'].values()),sorted(allowed))
check('all claimed semantic closures safe',all(env.decls[n]['safety']=='safe' for st in a.statements.values() for n in st['semantic_closure']))
check('quarantined runtime companion excluded from all semantic roots',all('VeriSlop.Source.witnessEntries._unsafe_rec' not in st['semantic_closure'] for st in a.statements.values()))
prof=a.profile
check('full signed exact input/result carrier',[(f['name'],f['sort']) for f in prof['records']['Input']['fields']]==[('n','Int'),('m','Int'),('a','Int'),('b','Int')] and prof['symbols']['solve']['args']==[{'record':'Input'}] and prof['symbols']['solve']['result']=='Int')
def var(i): return {'index':i,'tag':'var'}
def field(n,i): return {'field':n,'sort':'Input','tag':'field','value':var(i)}
def integer(n): return {'tag':'int','value':str(n)}
def binary(t,l,r): return {'tag':t,'left':l,'right':r}
guard=binary('and',binary('le',integer(0),field('n',0)),binary('and',binary('le',field('n',0),integer(500)),binary('lt',integer(0),field('m',0))))
floor_body=binary('int_fdiv',binary('int_add',binary('int_mul',field('a',1),{'tag':'nat_to_int','value':var(0)}),field('b',1)),field('m',1))
expected_floor={'tag':'list_sum','value':{'tag':'list_map','function':{'sort':'Nat','body':floor_body},'value':{'tag':'list_range','stop':{'tag':'int_to_nat','value':field('n',0)}}}}
expected_value={'tag':'forall','sort':{'record':'Input'},'body':binary('implies',guard,binary('eq',{'tag':'call','symbol':'solve','args':[var(0)]},expected_floor))}
policy=canonical.loads(capture(RUN/'requests/A23/source-policy.json'))
check('exact four original delivery/value IDs',set(policy['obligations'])=={'O1','O2','S1','S2'})
for oid in ['O1','O2','S1','S2']:
 pkg=a.statements[oid]['formula_package']
 requirements=[{'tag':'entry','file':'program.vscore.json','entry':'solve','arity':1}]+[{'tag':x} for x in ['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']]
 check('exact canonical file/entry/seven closed facets '+oid,len(pkg['source'])==1 and pkg['source'][0]['lean_decl']=='VeriSlopAST.solve' and pkg['source'][0]['symbol']=='solve' and pkg['source'][0]['requirements']==requirements)
 check('value/source-only policy classification '+oid,policy['obligations'][oid]['value_required']==(oid in ['O1','O2']))
 if oid in ['O1','O2']:
  check('full-domain signed floor sum retained '+oid,pkg['value']['formula']==expected_value and a.statements[oid]['hypotheses']==['A1'])
 else:
  check('approved operational source-only proposition '+oid,pkg['value'] is None and a.statements[oid]['hypotheses']==[])
check('constructive existential states same complete A1 guard',a.statements['A1_nonvacuity']['formula_package']['formula']=={'tag':'exists','sort':{'record':'Input'},'body':guard})
check('constructive witness uses no hypotheses or axioms',not a.statements['A1_nonvacuity']['hypotheses'] and cert['obligations']['A1_nonvacuity']['axioms']==[])
w=env_json['witnesses']
check('kernel-extracted concrete non-vacuity witness',len(w)==1 and w[0]['ok'] and w[0]['theorem']==['VeriSlopAST','valid_input_inhabited'] and [x['app'][1]['lit']['nat'] for x in w[0]['shape']['exists']['witness']['app'][1:]]==['0','1','0','0'])
source=capture(PKG/cert['artifacts']['source']['path']).decode()
check('accepted source includes exact model guard and constructor witness','@[reducible] def «valid_input»' in source and '«a» : _root_.Int' in source and '«b» : _root_.Int' in source and '«n» := 0, «m» := 1, «a» := 0, «b» := 0' in source)
check('accepted source model explicit floor/map/range/sum definition',all(x in source for x in ['_root_.List.sum','_root_.List.map','_root_.List.range','_root_.Int.toNat','_root_.Int.fdiv','_root_.Int.ofNat']))
# Evidence is inspected only; no tool/replay/closure invocation is performed.
evrows=[]
for oid,r in ir['obligations'].items():
 for milestone in ['TYPECHECKED','REIFIED']+(['PROVED'] if r['role']=='guarantee' else []):
  cid=milestone+':'+oid+'@'+str(r['revision'])
  matches=[e for e in p.evidence.for_claim(cid) if e.valid and e.status=='PASS' and (e.result.get('certificate_hash')==cert_hash if milestone!='REIFIED' else e.result.get('ir_hash')==ih)]
  check('exact registered PASS evidence '+cid,bool(matches))
  e=matches[-1]
  capture(PKG/'evidence'/(e.id+'.json'))
  capture(PKG/e.record['raw_result_ref'])
  if milestone=='REIFIED' and r['role']=='guarantee':
   check('retained native denotation check '+oid,e.result['check']['denotation_defeq']=={'defeq':True,'ok':True,'typechecks':True})
  evrows.append({'claim_id':cid,'evidence_id':e.id,'verifier_id':e.record['verifier_id'],'verifier_hash':e.record['verifier_hash'],'result':e.result})
for art in cert['artifacts'].values(): capture(PKG/art['path'])
capture(PKG/ir['acceptance_certificate_ref'])
capture(p.path('accepted_ir'))
capture(p.path('claims'))
capture(PKG/'request/source-policy.json')
for path in C.challenge_dir(p).rglob('*'):
 if path.is_file(): capture(path)
protocol=canonical.loads(capture(RUN/'protocol.json'))
prereg=canonical.loads(capture(RUN/'preregistration.json'))
check('fresh frozen project source root',prereg['source_root']==protocol['source_root']=='sha256:f72db4961eda28039e8e55ed5e7817ef194e0d8da50d8471aebcc7b33bf9f13f')
check('preregistration protocol byte binding',prereg['protocol_sha256']==canonical.digest_file(RUN/'protocol.json'))
check('generic production byte inventory unchanged',all(canonical.digest_file(PROJECT/name)==digest for name,digest in protocol['source_files'].items()))
for name,digest in protocol['input_files'].items(): check('preregistered input byte identity '+name,canonical.digest(capture(RUN/name))==digest)
check('registered claim provenance revised current request only',all(ref['document_hash']==canonical.digest_file(RUN/'requests/A23/revised-prompt.txt') for r in reg.values() for ref in r['source_refs']))
check('exact bytes stable through snapshot',all(canonical.digest_file(STAGE/rel)==row['sha256'] for rel,row in inputs.items()))
pending={name:(PKG/name).exists() for name in ['implementation/program.vscore.json','bridges/implementation/semantic/edge-6c6b7f3cad1aebbacfb2127f/certificate.json','report.json']}
write('checks.json',checks)
write('evidence-inspection.json',evrows)
write('input-manifest.json',{'format':'independent-readonly-audit-inputs/0.1','files':inputs})
write('audit.json',{'format':'independent-readonly-scope-audit/0.1','observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':str(STAGE),'task':'A23','phase':'accepted contract','source_root':protocol['source_root'],'protocol_hash':canonical.digest_file(RUN/'protocol.json'),'accepted_ir_hash':ih,'acceptance_certificate_hash':cert_hash,'contract_root':cert['contract_input_root'],'checked_obligations':list(ir['obligations']),'checks_passed':len(checks),'input_files':len(inputs),'concrete_defects_found':[],'conclusion':'No concrete scope mismatch found in the inspected accepted contract. O1/O2 preserve complete valid-domain floor-sum value propositions; all four delivery IDs bind the exact canonical solve and seven source facets. Constructive non-vacuity is kernel-extracted and axiom-free.','domain':'Input.n,m,a,b are arbitrary-precision signed Lean Int; only 0 <= n <= 500 and m > 0 guard the value theorem; a,b have no guards. List.range(Int.toNat n), exact Int.fdiv and List.sum give the full negative-floor sum and empty sum zero on that domain.','policy_axioms_used':{oid:row['axioms'] for oid,row in cert['obligations'].items()},'kernel_export_replay':env_json['replay'],'implementation_observed':pending,'limits':['Natural-language correspondence is a trusted independent reading, not a kernel theorem.','No new kernel replay, native closure, driver or model call was executed by this audit. Existing registered replay/denotation evidence was inspected and authenticated.','The accepted Source.Contract proves abstract requirement-model transfer and admission inhabitation; it does not establish facts about a delivered implementation.','Source implementation/refinement/raw adapter coverage/effect adequacy/per-ID transfers/two-build mechanical closure and release outcome remain unaudited until their accepted artifacts are published.','This audit receipt is outside the frozen cohort and is not lifecycle authority.'],'snapshot_rechecked':True})
for q in AUDIT.rglob('*'):
 if q.is_file(): q.chmod(0o444)
for q in sorted(AUDIT.rglob('*'),reverse=True):
 if q.is_dir(): q.chmod(0o555)
AUDIT.chmod(0o555)
print(json.dumps({'audit':str(AUDIT/'audit.json'),'audit_sha256':canonical.digest_file(AUDIT/'audit.json'),'checks':len(checks),'input_files':len(inputs),'pending':pending},sort_keys=True))
