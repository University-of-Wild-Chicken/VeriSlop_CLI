import copy,json,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from verislop import canonical,contract,formal_frontend,policy
P=Path('validation/isolated-collection-bridge-20261010-gcb')
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(canonical.dumps(x))
# No source write occurs in this script: its only writable root is P.
paths=sorted(p for root in ('verislop','grammar','schemas') for p in Path(root).rglob('*') if p.is_file() and p.suffix in ('.py','.lean','.json','.ebnf'))
if not (P/'source-freeze-before.json').exists():save(P/'source-freeze-before.json',[{'path':str(p),'sha256':canonical.digest_file(p),'size':p.stat().st_size} for p in paths])
save(P/'resource-policy.json',policy.get('strict'))
spec=(P/'specification.json').read_bytes();o=canonical.loads(spec)
ids={'raiseBoxes':'G-map','keepAtom':'G-filter','coldTotal':'G-fold'}
ref=str(P/'specification.json');source={'document_ref':ref,'document_hash':canonical.digest(spec),'start_byte':0,'end_byte':len(spec),'origin':'explicit','interpretation':'Independent artificial collection fixture, persisted before inputs.'}
keys=('entities','preconditions','postconditions','invariants','safety_properties','liveness_properties','resource_constraints','error_semantics','explicit_non_goals','ambiguities')
ms=('INTERPRETED','FORMALIZED','TYPECHECKED','PROVED','IMPLEMENTED','LINKED','TESTED','END_TO_END_VERIFIED')
draft={'schema_version':'0.1','artifact_kind':'draft','request_ref':ref,'category_review':{k:'Specified artificial pure collection fixture; no additional requirement.' for k in keys},**{k:[] for k in keys}}
for name,oid in ids.items():
 draft['postconditions'].append({'id':oid,'revision':1,'kind':'postcondition','role':'guarantee','statement':o['operations'][name],'required':True,'source_refs':[source],'scope':['All declared values and arbitrary finite lists; normative source semantics.'],'dependencies':[],'acceptance_criteria':['The exact universally quantified operation equation.'],'state':'INTERPRETED','lifecycle':{m:{'outcome':'PENDING','evidence_refs':[],'reason':'Independent fixture candidate.','scope':[]} for m in ms}})
ledger={'schema_version':'0.1','artifact_kind':'interpretation','request':{'document_ref':ref,'document_hash':canonical.digest(spec),'byte_length':len(spec)},'clauses':[{'start_byte':0,'end_byte':len(spec),'disposition':'obligations','refs':list(ids.values()),'note':'All operation and carrier scope clauses covered by these three fixture obligations.'}],'assumptions':[],'ambiguities':[],'selected_defaults':[]}
save(P/'inputs/draft.json',draft);save(P/'inputs/ledger.json',ledger)
def v(i):return {'tag':'var','index':i}
def field(sort,name,value):return {'tag':'field','sort':sort,'field':name,'value':value}
def atom(x):return field('Box','atom',x)
def n(x):return field('Atom','n',x)
def tone(x):return field('Atom','tone',x)
def bin(tag,x,y):return {'tag':tag,'left':x,'right':y}
box={'record':'Box'};at={'record':'Atom'};ls={'list':box}
mapbody={'tag':'list_map','value':v(0),'function':{'sort':box,'body':{'tag':'record','sort':'Box','fields':[{'tag':'record','sort':'Atom','fields':[tone(atom(v(0))),bin('add',n(atom(v(0))),{'tag':'nat','value':'1'})]},field('Box','live',v(0))]}}}
filter_composite={'tag':'list_filter','value':v(1),'function':{'sort':box,'body':bin('bool_eq',atom(v(0)),v(1))}}
filterbody=copy.deepcopy(filter_composite)
filterbody['function']['body']=bin('bool_and',bin('bool_eq',tone(atom(v(0))),tone(v(1))),bin('bool_eq',n(atom(v(0))),n(v(1))))
foldbody={'tag':'list_foldl','value':v(0),'initial':{'tag':'nat','value':'0'},'function':{'accumulator_sort':'Nat','element_sort':box,'body':{'tag':'ite','condition':bin('bool_eq',tone(atom(v(0))),{'tag':'enum','sort':'Tone','constructor':'cold'}),'then':bin('add',v(1),n(atom(v(0)))),'else':v(1)}}}
proposal={'encoding':'verislop.formalizer-ast/0.2','enums':{'Tone':{'constructors':['cold','warm']}},'records':{'Atom':{'fields':o['carriers']['Atom']},'Box':{'fields':o['carriers']['Box']}},'symbols':{},'predicates':{},'theorems':{},'obligations':{},'witness_obligations':{}}
for name,args,result,body in [('raiseBoxes',[ls],ls,mapbody),('keepAtom',[ls,at],ls,filterbody),('coldTotal',[ls],'Nat',foldbody)]:
 proposal['symbols'][name]={'args':args,'result':result,'body':body}
 theorem=bin('eq',{'tag':'call','symbol':name,'args':[v(len(args)-i-1) for i in range(len(args))]},copy.deepcopy(body))
 for s in reversed(args):theorem={'tag':'forall','sort':s,'body':theorem}
 tn='law_'+name;proposal['theorems'][tn]={'formula':theorem};proposal['obligations'][ids[name]]={'theorem':tn}
records=contract.interpreted_records(draft,{})
# Preserve a real rejected compiler attempt for aggregate equality, then use its
# equivalent fieldwise primitive decisions without changing the specification.
rejected=copy.deepcopy(proposal);rejected['symbols']['keepAtom']['body']=filter_composite
rejected['theorems']['law_keepAtom']['formula']['body']['body']['right']=copy.deepcopy(filter_composite)
save(P/'inputs/typed-proposal-composite-equality.json',rejected)
try:
 formal_frontend.compile_response(canonical.dumps(rejected),records,'isolated.collection.v1')
 result={'unexpected':'aggregate equality compiled'}
except Exception as e:
 result={'exception_type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
save(P/'diagnostics/00-composite-equality-compiler.json',result)
save(P/'inputs/typed-proposal.json',proposal)
compiled=formal_frontend.compile_response((P/'inputs/typed-proposal.json').read_bytes(),records,'isolated.collection.v1',response_ref='inputs/typed-proposal.json')
(P/'inputs/formalization').mkdir()
(P/'inputs/formalization/Contract.lean').write_bytes(compiled.source)
save(P/'inputs/formalization/formalization.json',compiled.formalization)
save(P/'inputs/compiler-origin.json',compiled.receipt)
save(P/'inputs/frontend-kernel-audit-requests.json',formal_frontend.kernel_audit_requests(compiled))
(P/'inputs/proofs.lean').write_bytes(compiled.source.replace(b':= by sorry',b':= by intros; rfl'))
surface='''program "vscore/0.3" profile "data-pipeline/0.3";
record Atom { tone: Enum(Tone); n: Nat; }
record Box { atom: Record(Atom); live: Bool; }
entry raiseBoxes(xs: List(Record(Box))) -> List(Record(Box)) {
  List.map(xs; b => record Box { atom = record Atom { tone = b.atom.tone, n = b.atom.n + 1 }, live = b.live })
}
entry keepAtom(xs: List(Record(Box)), needle: Record(Atom)) -> List(Record(Box)) {
  List.filter(xs; b => b.atom == needle)
}
entry coldTotal(xs: List(Record(Box))) -> Nat {
  List.fold(xs, 0; acc, b => if b.atom.tone == enum(Tone, cold) then acc + b.atom.n else acc)
}
'''
(P/'inputs/program.vsc').write_text(surface)
save(P/'inputs/enum-registry.json',{'enums':[['Tone',['cold','warm']]]})
from verislop.bridges import vscore3_checker as C
save(P/'inputs/relation.json',{'schema_version':'0.3','format':'verislop.vscore-relation/0.3','template':'vscore.reference_refinement/0.3','source_slot':C.SLOTS['source'],'proof_slot':C.SLOTS['proof'],'bindings':[{'symbol':s,'entry':s} for s in sorted(ids)]})
save(P/'input-manifest.json',[{'path':str(p.relative_to(P)),'sha256':canonical.digest_file(p),'size':p.stat().st_size} for p in sorted((P/'inputs').rglob('*')) if p.is_file()]+[{'path':'specification.json','sha256':canonical.digest(spec),'size':len(spec)}])
print(result['message'] if 'message' in result else result)
print('Inputs created under',P)
