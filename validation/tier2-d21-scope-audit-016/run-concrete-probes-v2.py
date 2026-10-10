"""Audit-only bounded public-spec vectors and generic source AST interpreter.

This is no task implementation and carries no normative Lean execution claim.
Expected outputs are explicit public-spec examples, not a solve/reference oracle.
"""
import copy
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path('/home/augustus/VeriSlop_CLI')
OUT = ROOT / 'validation/tier2-d21-scope-audit-016'
STAGE = ROOT / 'synthetic_dataset/bootstrap/stages/tier2-source-facets-016'
PROJECT = STAGE / 'project'
PACKAGE = STAGE / 'run/artifacts/D21/verislop/package'
sys.path.insert(0, str(PROJECT))
from verislop.targets import vscore3_source as frontend


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def write_once(name, value):
    data = (json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    with (OUT/name).open('xb') as stream:
        stream.write(data)
    return digest(data)


def event(group, time, value):
    return {'group':group,'time':time,'value':value}


def row(group, start, count, value):
    return {'group':group,'start':start,'count':count,'value':value}


vectors=[]
def case(name, events, start, end, width, fill, expected, clauses):
    vectors.append({'id':name,'input':{'events':events,'start':start,'end':end,'width':width,'fill':fill},'expected':expected,'public_clause_ids':clauses})


plan=json.loads((OUT/'frozen-plan.json').read_text())
for n, item in enumerate(plan['public_examples'],1):
    vectors.append({'id':f'public-example-{n}','input':item['input'],'expected':item['output'],'public_clause_ids':['F11']})
for fill in ['none','previous']:
    case(f'empty-events-{fill}',[], -3, 4, 2, fill, [], ['F01','F02'])
    case(f'zero-range-{fill}',[event('z',0,8),event('',0,None)],0,0,1,fill,[],['F01','F03'])
    case(f'width-exceeds-range-{fill}',[event('a',-3,100),event('a',-2,1),event('a',0,None),event('a',2,4),event('a',3,200)],-2,3,9,fill,[row('a',-2,2,5)],['F03','F04','F08'])
    case(f'half-open-boundaries-{fill}',[event('a',-1,99),event('a',0,1),event('a',1,2),event('a',2,4),event('a',3,8),event('a',4,16),event('a',5,100)],0,5,2,fill,[row('a',0,2,3),row('a',2,2,12),row('a',4,1,16)],['F03','F04','F08'])
    case(f'null-and-duplicates-{fill}',[event('a',0,None),event('a',0,3),event('a',0,3),event('a',1,None)],0,2,2,fill,[row('a',0,2,6)],['F04','F09'])
    case(f'all-null-{fill}',[event('a',0,None),event('a',2,None)],0,3,1,fill,[row('a',0,0,None),row('a',1,0,None),row('a',2,0,None)],['F04','F06','F07'])
    tail=0 if fill=='previous' else None
    case(f'zero-cancellation-{fill}',[event('a',0,10),event('a',1,-10)],0,5,2,fill,[row('a',0,2,0),row('a',2,0,tail),row('a',4,0,tail)],['F04','F05','F06','F07','F09'])
    gap=7 if fill=='previous' else None
    tail=-2 if fill=='previous' else None
    case(f'persistent-group-local-history-{fill}',[event('a',-1,999),event('a',1,7),event('a',3,-2),event('a',2,None),event('b',-1,8)],0,5,1,fill,[row('a',0,0,None),row('a',1,1,7),row('a',2,0,gap),row('a',3,1,-2),row('a',4,0,tail),row('b',0,0,None),row('b',1,0,None),row('b',2,0,None),row('b',3,0,None),row('b',4,0,None)],['F02','F05','F06','F07','F08','F10'])
    case(f'unsorted-time-occurrences-{fill}',[event('b',2,8),event('a',3,5),event('a',0,2),event('b',0,-1),event('a',1,1),event('a',2,4)],0,4,2,fill,[row('a',0,2,3),row('a',2,2,9),row('b',0,1,-1),row('b',2,1,8)],['F02','F03','F04','F10'])
names=['\U00010000','é','e\u0301','', '\U0001f600','\uffff','a']
case('unicode-codepoint-order',[event(g,0,1) for g in names],0,1,1,'none',[row(g,0,1,1) for g in ['', 'a', 'e\u0301','é','\uffff','\U00010000','\U0001f600']],['F02','F10','F13'])
case('out-of-range-group-order',[event('z',100,None),event('a',-1,100),event('m',0,1)],0,2,1,'previous',[row('a',0,0,None),row('a',1,0,None),row('m',0,1,1),row('m',1,0,1),row('z',0,0,None),row('z',1,0,None)],['F02','F07','F08','F10'])
large=10**100
case('large-integer-offset-and-cancellation',[event('a',-large,large),event('a',-large+1,-large),event('a',-large+4,large+1),event('a',-large+5,999)],-large,-large+5,2,'previous',[row('a',-large,2,0),row('a',-large+2,0,0),row('a',-large+4,1,large+1)],['F03','F04','F07','F08','F09','F13'])
case('large-positive-offset',[event('a',large,large),event('a',large+2,1)],large,large+3,1,'none',[row('a',large,1,large),row('a',large+1,0,None),row('a',large+2,1,1)],['F03','F04','F06','F13'])
case('large-width',[event('a',0,2),event('a',1,-1)],0,2,large,'previous',[row('a',0,2,1)],['F03','F04','F13'])
case('repeated-identical-occurrences',[event('a',0,-2)]*4,0,1,1,'previous',[row('a',0,4,-8)],['F04','F09'])
case('zero-nonempty-then-null-only',[event('a',0,0),event('a',1,None),event('a',3,None)],0,4,1,'previous',[row('a',0,1,0),row('a',1,0,0),row('a',2,0,0),row('a',3,0,0)],['F04','F05','F07','F09'])
for v in vectors:
    i=v['input']; assert i['width']>0 and i['start']<=i['end'] and i['fill'] in ['none','previous']
frozen_bytes=(OUT/'frozen-concrete-probes.json').read_bytes()
assert json.loads(frozen_bytes)['cases']==vectors
vector_hash=digest(frozen_bytes)


class Nat(int):
    pass


@dataclass(frozen=True)
class Some:
    value: object


class Interpreter:
    """Generic expression semantics for the observed 0.3 syntax subset."""
    def __init__(self, raw):
        self.raw=raw
        self.functions={f['id']:f for f in raw['helpers']+raw['entries']}
        self.records={d['id']:d for d in raw['declarations'] if d['tag']=='record'}
        self.steps=0
    def decode(self, ty, value):
        if ty=='nat': return Nat(value)
        if isinstance(ty,str): return value
        tag=next(iter(ty)); item=ty[tag]
        if tag=='option': return None if value is None else Some(self.decode(item,value))
        if tag=='list': return [self.decode(item,v) for v in value]
        if tag=='enum': return value
        if tag=='record': return {f['id']:self.decode(f['type'],value[f['id']]) for f in self.records[item]['fields']}
        raise ValueError('unsupported wire type: '+repr(ty))
    def encode(self, ty, value):
        if isinstance(ty,str): return int(value) if ty=='nat' else value
        tag=next(iter(ty)); item=ty[tag]
        if tag=='option': return None if value is None else self.encode(item,value.value)
        if tag=='list': return [self.encode(item,v) for v in value]
        if tag=='enum': return value
        if tag=='record': return {f['id']:self.encode(f['type'],value[f['id']]) for f in self.records[item]['fields']}
        raise ValueError('unsupported wire type: '+repr(ty))
    def call(self, name, values):
        return self.expr(self.functions[name]['body'],list(reversed(values)))
    def expr(self, e, env):
        self.steps+=1
        if self.steps>2000000: raise ValueError('bounded audit interpreter step limit')
        tag=e['tag']
        if tag=='var': return env[e['index']]
        if tag=='nat': return Nat(e['value'])
        if tag=='int': return int(e['value'])
        if tag=='bool': return e['value']
        if tag=='enum': return e['ctor']
        if tag=='none': return None
        if tag=='nil': return []
        if tag=='some': return Some(self.expr(e['value'],env))
        if tag=='record': return {f['id']:self.expr(f['value'],env) for f in e['fields']}
        if tag=='project': return self.expr(e['value'],env)[e['field']]
        if tag=='let': return self.expr(e['body'],[self.expr(e['value'],env)]+env)
        if tag=='if': return self.expr(e['then'] if self.expr(e['cond'],env) else e['else'],env)
        if tag=='match_option':
            value=self.expr(e['scrutinee'],env)
            return self.expr(e['none'],env) if value is None else self.expr(e['some'],[value.value]+env)
        if tag=='call': return self.call(e['helper'],[self.expr(v,env) for v in e['args']])
        if tag=='list_fold':
            value=self.expr(e['initial'],env)
            for item in self.expr(e['source'],env): value=self.expr(e['step'],[item,value]+env)
            return value
        if tag in ['list_map','list_filter']:
            values=self.expr(e['value'],env)
            if tag=='list_map': return [self.expr(e['body'],[v]+env) for v in values]
            return [v for v in values if self.expr(e['body'],[v]+env)]
        if tag in ['list_length','list_range','list_sort','list_unique','list_sum','nat_to_int','int_to_nat']:
            value=self.expr(e['value'],env)
            if tag=='list_length': return Nat(len(value))
            if tag=='list_range': return [Nat(i) for i in range(value)]
            if tag=='list_sort': return sorted(value)
            if tag=='list_unique':
                seen=[]
                for v in value:
                    if v not in seen: seen.append(v)
                return seen
            if tag=='list_sum': return sum(value)
            if tag=='nat_to_int': return int(value)
            if tag=='int_to_nat': return Nat(max(0,value))
        if tag=='cons': return [self.expr(e['head'],env)]+self.expr(e['tail'],env)
        if tag in ['add','sub','mul','lt','le','eq','and','or','int_fdiv','list_append']:
            a=self.expr(e['left'],env); b=self.expr(e['right'],env)
            if tag=='add': return Nat(a+b) if isinstance(a,Nat) and isinstance(b,Nat) else a+b
            if tag=='sub': return Nat(max(0,a-b)) if isinstance(a,Nat) and isinstance(b,Nat) else a-b
            if tag=='mul': return Nat(a*b) if isinstance(a,Nat) and isinstance(b,Nat) else a*b
            if tag=='lt': return a<b
            if tag=='le': return a<=b
            if tag=='eq': return a==b
            if tag=='and': return a and b
            if tag=='or': return a or b
            if tag=='int_fdiv': return 0 if b==0 else a//b
            if tag=='list_append': return a+b
        raise ValueError('unsupported expression: '+tag)
    def entry(self, name, wire):
        f=self.functions[name]; self.steps=0
        assert len(f['params'])==1
        return self.encode(f['result'],self.call(name,[self.decode(f['params'][0],copy.deepcopy(wire))]))


candidates=[('source-1',PACKAGE/'agents/vscore-attempts/source-1/program.vscore.json'),('source-2',PACKAGE/'agents/vscore-attempts/source-2/program.vscore.json'),('materialized-source-3',PACKAGE/'implementation/program.vscore.json')]
results=[]
for name,path in candidates:
    data=path.read_bytes()
    rec={'candidate':name,'path':str(path.relative_to(ROOT)),'sha256':digest(data),'admission_kind':'host parse/type proposal only','results':[]}
    try:
        parsed=frontend.parse_source(data)
        signatures=frontend.check_program({'Fill':['none','previous']},parsed)
        rec['host_admission']='PASS'; rec['signatures']=signatures
        raw=json.loads(data); interpreter=Interpreter(raw)
        for v in vectors:
            before=copy.deepcopy(v['input'])
            try:
                actual=interpreter.entry('solve',v['input'])
                deterministic=actual==interpreter.entry('solve',v['input'])
                rec['results'].append({'case_id':v['id'],'actual':actual,'expected':v['expected'],'pass':actual==v['expected'],'input_preserved':v['input']==before,'deterministic_repeat':deterministic,'steps':interpreter.steps})
            except Exception as exc:
                rec['results'].append({'case_id':v['id'],'pass':False,'execution_error':type(exc).__name__+': '+str(exc),'expected':v['expected']})
    except Exception as exc:
        rec['host_admission']='REJECTED'; rec['admission_error']=type(exc).__name__+': '+str(exc)
    rec['passed']=sum(r['pass'] for r in rec['results']); rec['failed']=sum(not r['pass'] for r in rec['results'])
    results.append(rec)
report={'schema_version':'verislop.independent-concrete-probe-results/0.1','audit_id':plan['audit_id'],'classification':'TESTED_HOST_BOUNDED_ONLY','probe_input_sha256':vector_hash,'interpreter_sha256':digest(Path(__file__).read_bytes()),'frontend_sha256':digest((PROJECT/'verislop/targets/vscore3_source.py').read_bytes()),'semantics_reference_sha256':digest((PROJECT/'verislop/lean/VSCore3/Typing.lean').read_bytes()),'execution_environment':{'python':platform.python_version(),'os':platform.platform()},'cases':len(vectors),'results':results,'optional_TESTED_rescored':False,'boundary':'Finite host AST interpretation and public expected JSON values only. No trusted correspondence to normative Lean execution and no universal refinement or task closure claim. Candidate files were not modified.'}
report['supersedes_invalid_harness_run']={'path':'validation/tier2-d21-scope-audit-016/concrete-probe-results.json','sha256':digest((OUT/'concrete-probe-results.json').read_bytes()),'reason':'v1 audit interpreter treated named record field wrappers as expressions, causing KeyError: tag. Those harness errors are not candidate counterexamples; v1 bytes and script remain unchanged.'}
result_hash=write_once('concrete-probe-results-v2.json',report)
print(json.dumps({'cases':len(vectors),'probe_sha256':vector_hash,'results_sha256':result_hash,'candidates':[{'candidate':r['candidate'],'host_admission':r['host_admission'],'passed':r['passed'],'failed':r['failed'],'admission_error':r.get('admission_error')} for r in results]},sort_keys=True))
