"""Bounded generic host-seam checks; no Lean, model, task artifact or acceptance authority."""
from pathlib import Path
import copy, datetime, hashlib, io, json, sys, unittest
ROOT=Path('/home/augustus/VeriSlop_CLI'); OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from verislop import canonical, dsl, formal_frontend as ff, reify, schemas
from verislop.exprjson import app, const, parse_name, decl_hash, closure, constants
from test_formal_frontend_enums import EnumFrontendValidationTests, empty_proposal
from test_enum_equality_core import EnumEqualityTypingTests
from test_enum_authoring_workflow_unit import EnumAuthoringWorkflowUnits

log=io.StringIO(); suite=unittest.TestSuite()
for cls in (EnumFrontendValidationTests,EnumEqualityTypingTests,EnumAuthoringWorkflowUnits):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(OUT/'unit.stdout.txt').write_text(log.getvalue())
rows=[]
def check(name, actual, expected=True, **detail):
    ok=actual==expected
    rows.append({'id':name,'ok':ok,'actual':actual,'expected':expected,**detail})
    if not ok: raise AssertionError(rows[-1])
def rejected(name, fn, exception, fragment=None):
    try: fn()
    except exception as e:
        msg=str(e);check(name, fragment is None or fragment in msg, diagnostic=msg)
    else: check(name,False)

# Host compiler fidelity inventory, exact closed version and source replay, no proof claim.
obj=empty_proposal(); obj['enums']={'LeftChoice':{'constructors':['on','off']},'RightChoice':{'constructors':['on','off']}}
var=lambda i:{'tag':'var','index':i}
obj['symbols']={'same':{'args':[{'enum':'LeftChoice'},{'enum':'LeftChoice'}],'result':'Bool','body':{'tag':'bool_eq','left':var(1),'right':var(0)}}}
g=ff.compile_response(canonical.dumps(obj),[],'audit.generic')
check('candidate-fields-only',all('candidate_decidable_eq' in v and 'decidable_eq' not in v for v in g.profile.enums.values()))
check('nominal-type-separation',g.profile.enums['LeftChoice']['lean_decl']!=g.profile.enums['RightChoice']['lean_decl'])
requests=ff.kernel_audit_requests(g)
refs=set().union(*(constants(x['expr']) for x in requests))
check('mandatory-independent-denotation-targets-exact-instance','VeriSlopAST.instDecidableEqLeftChoice' in refs,request_count=len(requests))
check('origin-byte-replay',ff.reconstruct_origin(canonical.dumps(obj),[],g.source,g.formalization,g.receipt))
check('source-byte-tamper-rejected',ff.reconstruct_origin(canonical.dumps(obj),[],g.source+b'\n',g.formalization,g.receipt),False)
mut=copy.deepcopy(obj);mut['enums']['LeftChoice']['constructors'].reverse()
check('constructor-order-origin-tamper-rejected',ff.reconstruct_origin(canonical.dumps(mut),[],g.source,g.formalization,g.receipt),False)
check('compiler-emits-no-proof-status',not any(x in g.receipt for x in ['PROVED','TESTED','END_TO_END_VERIFIED','accepted']))
rejected('candidate-profile-default-parser-rejected',lambda:dsl.Profile.from_json(g.profile.raw),dsl.DSLError,'candidate-only')

# Deliberately synthetic ExprJSON rows exercise host guards only. They are not kernel exports.
E='Synthetic.Choice'; I='Synthetic.eqChoice'; H='Synthetic.helper'
def row(name,kind,ty,value=None,**fields):
    z={'name':parse_name(name),'kind':kind,'type':ty,'safety':'safe','level_params':[],'axioms':[],**fields}
    if value is not None:z['value']=value
    return z
D={E:row(E,'inductive',{'sort':1},inductive={'all':[parse_name(E)],'ctors':[parse_name(E+'.on'),parse_name(E+'.off')],'num_params':0,'num_indices':0,'is_rec':False}),
   E+'.on':row(E+'.on','constructor',const(E),constructor={'induct':parse_name(E)}),
   E+'.off':row(E+'.off','constructor',const(E),constructor={'induct':parse_name(E)}),
   H:row(H,'definition',const('Nat'),{'lit':{'nat':'0'}}),
   I:row(I,'definition',app(const('DecidableEq',[1]),const(E)),const(H))}
hashes={n:decl_hash(c) for n,c in D.items()}
check('synthetic-host-exact-instance-identity',reify._enum_equality_declaration(I,E,D,hashes),hashes[I])
raw={'profile_id':'synthetic-seam','dsl':dsl.ENCODING_V2,'enums':{'Choice':{'lean_decl':E,'constructors':['on','off'],'lean_constructors':[E+'.on',E+'.off'],'decidable_eq':{'lean_decl':I,'decl_hash':hashes[I]}}},'records':{},'symbols':{},'predicates':{}}
p=dsl.Profile.from_json(raw)
check('synthetic-host-bound-name',reify.validate_enum_equality_binding(p,'Choice',D),I)
for label,change in [('unknown',{'lean_decl':'Synthetic.missing'}),('stale',{'decl_hash':canonical.digest(b'wrong')})]:
    x=copy.deepcopy(raw);x['enums']['Choice']['decidable_eq'].update(change)
    rejected('synthetic-'+label+'-binding-rejected',lambda x=x:reify.validate_enum_equality_binding(dsl.Profile.from_json(x),'Choice',D),reify.Unsupported)
for label,change in [('unsafe',{'safety':'unsafe'}),('opaque',{'kind':'opaque'}),('axiom-choice',{'axioms':[parse_name('Classical.choice')]}),('unresolved',{'unresolved_constants':['Synthetic.absent']}),('foreign-nominal',{'type':app(const('DecidableEq',[1]),const('Synthetic.Other'))}),('polymorphic',{'level_params':[parse_name('u')]})]:
    x=copy.deepcopy(D);x[I].update(change)
    rejected('synthetic-'+label+'-instance-rejected',lambda x=x:reify.validate_enum_equality_binding(p,'Choice',x),reify.Unsupported)
for label,change in [('unsafe',{'safety':'unsafe'}),('choice-axiom',{'axioms':[parse_name('Classical.choice')]}),('native-reference',{'value':const('Synthetic.native_decide')}),('choice-reference',{'value':const('Classical.someChoice')})]:
    x=copy.deepcopy(D);x[H].update(change)
    rejected('synthetic-helper-'+label+'-rejected',lambda x=x:reify._enum_equality_declaration(I,E,x),reify.Unsupported)
x=copy.deepcopy(D);x[H]['value']={'lit':{'nat':'1'}}
check('top-declaration-identity-not-transitive',decl_hash(x[I]),decl_hash(D[I]))
fam=closure({I},D)
a={n:decl_hash(D[n]) for n in sorted(fam)};b={n:decl_hash(x[n]) for n in sorted(fam)}
check('full-semantic-closure-detects-helper-change',canonical.digest_json(a)!=canonical.digest_json(b),before=canonical.digest_json(a),after=canonical.digest_json(b))
rejected('stale-helper-supplied-hash-rejected',lambda:reify._enum_equality_declaration(I,E,x,hashes),reify.Unsupported,'stale semantic identity')
old=copy.deepcopy(raw);old['enums']['Choice'].pop('decidable_eq'); op=dsl.Profile.from_json(old)
on={'tag':'enum','sort':'Choice','constructor':'on'}; off={'tag':'enum','sort':'Choice','constructor':'off'}
dsl.type_formula({'tag':'eq','left':on,'right':off},[],op)
check('legacy-propositional-enum-equality-preserved',True)
rejected('legacy-Boolean-enum-equality-missing-binding-rejected',lambda:dsl.type_term({'tag':'bool_eq','left':on,'right':off},[],op),dsl.DSLError,'no bound computable')
rejected('legacy-enum-decide-missing-binding-rejected',lambda:dsl.type_term({'tag':'decide','formula':{'tag':'eq','left':on,'right':off}},[],op),dsl.DSLError,'no bound computable')

before=json.loads((OUT/'source-before.json').read_text());after=[]
for rec in before['files']:
    data=(ROOT/rec['path']).read_bytes();after.append({'path':rec['path'],'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
changed=[rec['path'] for rec,new in zip(before['files'],after) if rec!=new]
(OUT/'source-after.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':after,'changes_during_checks':changed},indent=2)+'\n')
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unit':{'tests_run':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'skipped':len(r.skipped),'successful':r.wasSuccessful()},'independent_host_checks':rows,'count':len(rows),'source_changes_during_checks':changed,'authority':'HOST_SEAM_ONLY; synthetic declaration rows were not kernel executed or accepted','no_native_lean_model_task_calls':True}
(OUT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'units':result['unit'],'host_checks':len(rows),'host_failures':sum(not q['ok'] for q in rows),'source_changes':changed}))
if not r.wasSuccessful():sys.exit(1)
