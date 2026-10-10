#!/usr/bin/env python3
"""Reproduce the captured production comparison from immutable saved bytes only.

The live production capture was executed at the timestamps in the annex. This
validator never rereads subsequently edited production or invokes any verifier.
"""
from pathlib import Path
import json, hashlib
P=Path(__file__).resolve().parent
def h(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def d(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
annex=json.loads((P/'current-production-at-capture.json').read_bytes())
protocol=json.loads((P/'snapshots/sealed-run/protocol.json').read_bytes())
observed={};checks={}
for name,rec in annex['files'].items():
    saved=(P/rec['snapshot']).read_bytes()
    frozen=(P/'snapshots/frozen-project'/name).read_bytes()
    executed=(P/'snapshots/sealed-run/execution-source'/name).read_bytes()
    observed[name]=h(saved)
    checks[name]=observed[name]==rec['sha256']==protocol['source_files'][name] and saved==frozen==executed and annex['checks'][name] is True
result={'format':'independent-saved-annex-validation/0.1','checks':len(checks)+2,'all_checks_pass':all(checks.values()) and set(observed)==set(protocol['source_files']) and h(d(observed))==protocol['source_root']==annex['observed_current_source_root'],'captured_comparison_sha256':h((P/'current-production-at-capture.json').read_bytes()),'captured_source_root':h(d(observed)),'uses_live_production':False,'uses_kernel_native_models':False}
print(json.dumps(result,indent=2))
assert result['all_checks_pass']
