import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from verislop import canonical,contract,formal_frontend,formalize,leanbridge,policy
from verislop.events import EventSink
P=Path('validation/isolated-collection-bridge-20261010-gcb');D=P/'diagnostics/17-typed-frontend-audit';D.mkdir()
draft=canonical.load_file(P/'inputs-simple-ids/draft.json');records=contract.interpreted_records(draft,{})
c=formal_frontend.compile_response((P/'inputs-simple-ids/typed-proposal.json').read_bytes(),records,'isolated.collection.v1',response_ref='inputs-simple-ids/typed-proposal.json')
pol=policy.get('strict');tc=leanbridge.resolve_toolchain(leanbridge.DEFAULT_TOOLCHAIN)
original=leanbridge.compile_module
def observed(*a,**kw):
 r=original(*a,**kw)
 (D/'actual-compile-process.json').write_text(json.dumps({'ok':r.ok,'messages':r.messages,'errors':r.errors,'sorries':r.sorry_positions,'raw_stderr':r.raw_stderr,'process_evidence':r.process_evidence},sort_keys=True))
 return r
leanbridge.compile_module=observed
sink=EventSink('isolated-generic-frontend',target=str(D/'events.jsonl'),quiet=True)
out=formalize.attempt(tc,pol,records,c.source,c.formalization,sink,frontend=c)
sink.close()
(D/'composed-actual-source.lean').write_bytes(out['composed'])
if out.get('export'):(D/'kernel-export.json').write_bytes(canonical.dumps(out['export']))
summary={'diagnostics':[d.to_json() for d in out['diagnostics']],**{k:out.get(k) for k in ('compile','frontend_defeq','defeq','olean_closure')}}
(D/'audit.json').write_bytes(canonical.dumps(summary))
with (P/'commands.jsonl').open('a') as f:f.write(json.dumps({'label':'17-typed-frontend-audit','argv':sys.argv,'policy':pol,'actual_api':'verislop.formalize.attempt with actual verislop.formal_frontend.compile_response result','utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
print('diagnostics',summary['diagnostics'],'frontend_defeq',summary['frontend_defeq'],flush=True)
