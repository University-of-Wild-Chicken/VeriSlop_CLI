"""Independent authored boundary fixtures; no native/kernel/provider evidence."""
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import patch
import json, os, sys, hashlib

ROOT = Path('/home/augustus/VeriSlop_CLI')
sys.path.insert(0, str(ROOT))
from synthetic_dataset.tools import bootstrap_tier2 as H
from synthetic_dataset.tools import bootstrap_tier2_transport as TR
from verislop import canonical, lifecycle as L, schemas, view, review
from verislop.backends import vscore3_closure as C
from verislop.providers.broker import Broker
from verislop.errors import Diagnostic

OUT = Path(__file__).parent
FIX = OUT / 'authored-fixtures'
FIX.mkdir(exist_ok=True)
observations = []

def record(name, passed, **details):
    observations.append({'name': name, 'passed': bool(passed), **details})
    if not passed:
        raise AssertionError(name + ': ' + repr(details))

def freeze_inputs(directory, input_bytes=None):
    directory.mkdir(parents=True, exist_ok=True)
    data = input_bytes or {
        'config.json': canonical.dumps(TR.configuration()),
        H.PROFILES_INPUT: canonical.dumps(TR.endpoint_profiles()),
        'unrelated-preregistered-input.txt': b'generic exact input fixture\n',
    }
    for rel, value in data.items():
        p = directory / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value)
    files = {name: canonical.digest(value) for name, value in data.items()}
    protocol = {'format': H.FORMAT, 'source_root': 'sha256:'+'1'*64,
        'input_root': canonical.digest_json(files), 'request_set_root': 'sha256:'+'2'*64,
        'input_files': files, 'endpoint_profiles_path': H.PROFILES_INPUT,
        'endpoint_profiles_sha256': files[H.PROFILES_INPUT]}
    prereg = {k: protocol[k] for k in ['format', 'source_root', 'input_root', 'request_set_root']}
    prereg['protocol_sha256'] = canonical.digest_json(protocol)
    (directory/'protocol.json').write_bytes(canonical.dumps(protocol))
    (directory/'preregistration.json').write_bytes(canonical.dumps(prereg))
    return directory/'config.json'

def rewrite_protocol(directory, change):
    p = canonical.load_file(directory/'protocol.json')
    change(p)
    r = {k: p[k] for k in ['format', 'source_root', 'input_root', 'request_set_root']}
    r['protocol_sha256'] = canonical.digest_json(p)
    (directory/'protocol.json').write_bytes(canonical.dumps(p))
    (directory/'preregistration.json').write_bytes(canonical.dumps(r))

config = freeze_inputs(FIX/'baseline')
pkgroot = FIX/'package'
(pkgroot/'closure').mkdir(parents=True, exist_ok=True)
(pkgroot/'closure/review-config.json').write_bytes(config.read_bytes())
pkg = SimpleNamespace(root=pkgroot, path=lambda key: pkgroot/key)

def item(kind, role='guarantee', required=True):
    skeleton = {'kind': kind, 'role': role, 'revision': 1, 'required': required}
    app = L.applicability({**skeleton, 'id': 'fixture'})
    outcomes = {m: ('PASS' if app[m][0] else 'NOT_APPLICABLE') for m in L.MILESTONES}
    if app['TESTED'][0]: outcomes['TESTED']='PENDING'
    return {**skeleton, 'outcomes': outcomes}

base_obligations = {'G': item('postcondition'), 'W': item('non_vacuity'),
    'D': item('entity', 'declaration'), 'A': item('precondition', 'assumption'),
    'N': item('explicit_non_goal', 'exclusion')}
base_gate = {'configured': True,
    'checkpoints': {'formal_contract': 'REVIEW_ACCEPTED', 'release': 'REVIEW_ACCEPTED'},
    'diagnostics': [], 'projection_reuse': {'release': {'target': 'generic-fixture'}},
    'review_target': 'sha256:'+'3'*64}
base_snapshot = {'mechanical_status':'VERIFIED','closure_id':'authored-generic',
    'mechanical_result_path':'closure/executions/authored/mechanical-result.json',
    'closure_root':'sha256:'+'4'*64,'builds':[{'build':'A','ok':True},{'build':'B','ok':True}],
    'determinism':{'mismatches':[]},'claims':[]}
for oid, rec in base_obligations.items():
    app = L.applicability({**rec,'id':oid})
    for m in L.CONTRACT_MILESTONES:
        if app[m][0]: base_snapshot['claims'].append({'claim_id':L.claim_id(m,oid,1),'required':True,'outcome':'PASS'})
    if app['END_TO_END_VERIFIED'][0]:
        base_snapshot['claims'].append({'claim_id':L.claim_id('END_TO_END_VERIFIED',oid,1),'required':True,'outcome':'PASS'})
base_snapshot['claims'].append({'claim_id':'UNRELATED:required-graph-check','required':True,'outcome':'PASS'})
base_report = {'terminal_status':'VERIFIED','mechanical_status':'VERIFIED','release_status':'ACCEPTED',
    'tier':{'requested':2,'target':'vscore','endpoint':'restricted_source','requested_endpoint':'restricted_source','require_state':'END_TO_END_VERIFIED'},
    'language':'vscore/0.3','semantics':'vscore-semantics/0.3','backend':'verislop.backend.vscore/0.3',
    'freshness':'current execution revalidated','endpoint':{'established':'restricted_source'},
    'obligations':deepcopy(base_obligations),'closure_id':base_snapshot['closure_id'],
    'mechanical_result':base_snapshot['mechanical_result_path'],
    'roots':{'closure_input_root':base_snapshot['closure_root']},
    'builds':deepcopy(base_snapshot['builds']),'determinism':deepcopy(base_snapshot['determinism']),
    'review':deepcopy(base_gate),'review_target':base_gate['review_target'],
    'review_projection':{'reuse':deepcopy(base_gate['projection_reuse'])}}

def audit_case(name, mutate=None, expected='BLOCK', fail_view=False, fail_gate=False):
    state = {'report':deepcopy(base_report),'current':deepcopy(base_obligations),
        'snapshot':deepcopy(base_snapshot),'gate':deepcopy(base_gate)}
    if mutate: mutate(state)
    overlay = {'obligations':{oid:{**{k:v for k,v in r.items() if k!='outcomes'},
        'lifecycle':{m:{'outcome':v} for m,v in r['outcomes'].items()}}
        for oid,r in state['current'].items()}}
    def fake_gate(p, c):
        assert os.environ['VERISLOP_CONFIG_HOME'] == str(config.parent/'provider-home')
        if fail_gate: raise RuntimeError('authored gate error')
        return state['gate']
    with ExitStack() as stack:
        stack.enter_context(patch.object(schemas,'validate',return_value=[]))
        stack.enter_context(patch.object(view,'derive',side_effect=RuntimeError('authored view error') if fail_view else None,return_value=overlay))
        stack.enter_context(patch.object(C,'mechanical_snapshot',return_value=state['snapshot']))
        stack.enter_context(patch.object(review,'gate',side_effect=fake_gate))
        stack.enter_context(patch.object(Broker,'call',side_effect=AssertionError('provider call forbidden')))
        stack.enter_context(patch.dict(os.environ,{'VERISLOP_CONFIG_HOME':'unrelated-ambient','VERISLOP_COLLABORATION_UNUSED':'unchanged'}))
        actual=H.native_audit(pkg,state['report'],config)
        restored=(os.environ['VERISLOP_CONFIG_HOME']=='unrelated-ambient' and os.environ['VERISLOP_COLLABORATION_UNUSED']=='unchanged')
    record(name,actual['status']==expected and restored,status=actual['status'],issues=actual['issues'],
        restored=restored,counts={k:actual[k] for k in ['required_guarantees','all_required_guarantees','required_non_vacuity_witnesses','required_e2e_passed','all_required_e2e']})
    return actual

a=audit_case('baseline authored applicable guarantee plus required contract witness',expected='PASS')
record('baseline separates all guarantees, applicable guarantees and witness count',
    (a['all_required_guarantees'],a['required_guarantees'],a['required_non_vacuity_witnesses'],a['required_e2e_passed'])==(2,1,1,1))
def both_outcome(s,oid,m,value):
    s['report']['obligations'][oid]['outcomes'][m]=value
    s['current'][oid]['outcomes'][m]=value
for value in ['PENDING','FAIL','STALE','UNSUPPORTED','NOT_APPLICABLE']:
    audit_case('applicable e2e rejects '+value,lambda s,v=value:both_outcome(s,'G','END_TO_END_VERIFIED',v))
for value in ['PENDING','FAIL','STALE','UNSUPPORTED','NOT_APPLICABLE']:
    audit_case('required witness PROVED rejects '+value,lambda s,v=value:both_outcome(s,'W','PROVED',v))
for field in ['kind','role','revision','required']:
    audit_case('missing report '+field,lambda s,k=field:s['report']['obligations']['G'].pop(k))
for field in ['kind','role','revision','required']:
    def missing_both(s,k=field):
        s['report']['obligations']['G'].pop(k);s['current']['G'].pop(k)
    audit_case('missing reconstructed '+field,missing_both)
for field,value in [('revision',True),('revision',0),('required',1),('kind',''),('role','foreign')]:
    def invalid_both(s,k=field,v=value):
        s['report']['obligations']['G'][k]=v;s['current']['G'][k]=v
    audit_case('invalid reconstructed '+field+' '+repr(value),invalid_both)
for change in ['missing','extra','invalid']:
    def alter_outcomes(s,kind=change):
        for r in [s['report']['obligations']['G'],s['current']['G']]:
            if kind=='missing':r['outcomes'].pop('END_TO_END_VERIFIED')
            elif kind=='extra':r['outcomes']['AUTHORED_EXTRA']='PASS'
            else:r['outcomes']['END_TO_END_VERIFIED']='BLOCK'
    audit_case('invalid lifecycle map '+change,alter_outcomes)
audit_case('ordinary guarantee unknown kind cannot hide behind authored N/A',lambda s:(s['report']['obligations']['G'].update(kind='unregistered_kind'),s['current']['G'].update(kind='unregistered_kind'),both_outcome(s,'G','END_TO_END_VERIFIED','NOT_APPLICABLE')))
audit_case('report relabels ordinary guarantee as nonvacuity',lambda s:s['report']['obligations']['G'].update(kind='non_vacuity'))
audit_case('report drops original guarantee',lambda s:s['report']['obligations'].pop('G'))
audit_case('report adds an extra guarantee',lambda s:s['report']['obligations'].update(H=item('postcondition')))
audit_case('view reconstruction failure',fail_view=True)
audit_case('empty applicable set cannot establish endpoint',lambda s:(s['report']['obligations'].pop('G'),s['current'].pop('G')))
for oid,m in [('W','PROVED'),('G','FORMALIZED'),('G','END_TO_END_VERIFIED')]:
    cid=L.claim_id(m,oid,1)
    audit_case('missing current required graph '+cid,lambda s,c=cid:s['snapshot'].update(claims=[x for x in s['snapshot']['claims'] if x['claim_id']!=c]))
    audit_case('optional current graph cannot discharge '+cid,lambda s,c=cid:[x.update(required=False) for x in s['snapshot']['claims'] if x['claim_id']==c])
audit_case('unrelated required graph failure is preserved',lambda s:s['snapshot']['claims'][-1].update(outcome='FAIL'))
audit_case('absent current mechanics cannot use report flags',lambda s:s.update(snapshot=None))
for key,value in [('checkpoints',{'formal_contract':'REVIEW_ACCEPTED'}),('configured',False),('review_target','different'),('projection_reuse',{}),('diagnostics',[Diagnostic('REVIEW_NOT_RUN','authored stale observation')])]:
    audit_case('gate differs at '+key,lambda s,k=key,v=value:s['gate'].update({k:v}))
audit_case('report extra review field is rejected',lambda s:s['report']['review'].update(author_flag=True))
audit_case('report target differs from current gate',lambda s:s['report'].update(review_target='different'))
audit_case('report reuse projection differs',lambda s:s['report']['review_projection'].update(reuse={}))
audit_case('gate exception restores context and blocks',fail_gate=True)

for prior in [None,'','authored-ambient']:
    key='VERISLOP_CONFIG_HOME'; before=os.environ.get(key)
    try:
        if prior is None:os.environ.pop(key,None)
        else:os.environ[key]=prior
        try:
            with H._frozen_provider_context(config):
                assert os.environ[key]==str(config.parent/'provider-home')
                raise RuntimeError('authored body failure')
        except RuntimeError:pass
        record('context restores prior '+repr(prior),os.environ.get(key)==prior)
    finally:
        if before is None:os.environ.pop(key,None)
        else:os.environ[key]=before

provider_mutations = {
    'changed frozen profile bytes':lambda d:(d/H.PROFILES_INPUT).write_bytes((d/H.PROFILES_INPUT).read_bytes()+b' '),
    'changed frozen config bytes':lambda d:(d/'config.json').write_bytes((d/'config.json').read_bytes()+b' '),
    'missing frozen inventory member':lambda d:(d/'unrelated-preregistered-input.txt').unlink(),
    'preregistration changed source root':lambda d:(d/'preregistration.json').write_bytes(canonical.dumps({**canonical.load_file(d/'preregistration.json'),'source_root':'sha256:'+'5'*64})),
    'wrong endpoint profile path':lambda d:rewrite_protocol(d,lambda p:p.update(endpoint_profiles_path='foreign.json')),
    'wrong endpoint profile digest':lambda d:rewrite_protocol(d,lambda p:p.update(endpoint_profiles_sha256='sha256:'+'6'*64)),
    'missing config inventory binding':lambda d:rewrite_protocol(d,lambda p:(p['input_files'].pop('config.json'),p.update(input_root=canonical.digest_json(p['input_files'])))),
}
for name,mutate in provider_mutations.items():
    d=FIX/('provider-negative-'+str(len(observations))); c=freeze_inputs(d);mutate(d)
    with patch.dict(os.environ,{'VERISLOP_CONFIG_HOME':'authored-prior'}):
        entered=False;error=None
        try:
            with H._frozen_provider_context(c): entered=True
        except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)}
        record(name,not entered and error is not None and os.environ['VERISLOP_CONFIG_HOME']=='authored-prior',entered=entered,error=error)

class FakeReader:
    def __init__(self, directory):pass
    def json(self, name):return {'closure_root':'authored','execution_inventory':[],
        'claims':[{'claim_id':'X'},{'claim_id':'X'}]},None
    def close(self):pass
with patch.object(C,'PackageReader',FakeReader),patch.object(C.schemas,'validate',return_value=[]),patch.object(C.fsutil,'list_files',return_value=['mechanical-result.json']):
    error=None
    try:C.validate_execution(FIX/'unused')
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)}
    record('registered execution rejects duplicate claim IDs before graph deduplication',error is not None and 'unique and sorted' in error['message'],error=error)

(OUT/'checks.json').write_bytes(canonical.dumps({'scope':'Pure and mocked boundary tests only, no native proof evidence. Real schema/view/snapshot/review semantic qualification is left to the separate fresh native fixture.',
    'observations':observations,'count':len(observations),'passed':sum(o['passed'] for o in observations)}))
print(json.dumps({'checks':str(OUT/'checks.json'),'count':len(observations),'passed':sum(o['passed'] for o in observations),'failures':[o for o in observations if not o['passed']]},indent=2))
