import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from verislop import canonical,contract,formal_frontend
P=Path('validation/isolated-collection-bridge-20261010-gcb');Q=P/'inputs-simple-ids';Q.mkdir()
draft=canonical.load_file(P/'inputs/draft-v1.json');ledger=canonical.load_file(P/'inputs/ledger.json');proposal=canonical.load_file(P/'inputs/typed-proposal.json')
ids={'G-map':'Gmap','G-filter':'Gfilter','G-fold':'Gfold'}
for rec in draft['postconditions']:rec['id']=ids[rec['id']]
ledger['clauses'][0]['refs']=[ids[x] for x in ledger['clauses'][0]['refs']]
proposal['obligations']={ids[k]:v for k,v in proposal['obligations'].items()}
for n,x in [('draft.json',draft),('ledger.json',ledger),('typed-proposal.json',proposal)]: (Q/n).write_bytes(canonical.dumps(x))
c=formal_frontend.compile_response((Q/'typed-proposal.json').read_bytes(),contract.interpreted_records(draft,{}),'isolated.collection.v1',response_ref='inputs-simple-ids/typed-proposal.json')
(Q/'formalization').mkdir();(Q/'formalization/Contract.lean').write_bytes(c.source);(Q/'formalization/formalization.json').write_bytes(canonical.dumps(c.formalization));(Q/'compiler-origin.json').write_bytes(canonical.dumps(c.receipt));(Q/'proofs.lean').write_bytes(c.source.replace(b':= by sorry',b':= by intros; rfl'))
old=(P/'run_stages.py').read_text();new=old.replace("pkg=P/'run'","pkg=P/'run-simple-ids'").replace("'02b-interpret'","'11-interpret'").replace("'03b-formalize'","'12-formalize'").replace("'04-prove'","'13-prove'").replace("'05-accept'","'14-accept'").replace("'06-export'","'15-export'").replace("'09-actual-readable-goal'","'16-actual-readable-goal'")
new=new.replace("P/'inputs/draft-v1.json'","P/'inputs-simple-ids/draft.json'").replace("P/'inputs/ledger.json'","P/'inputs-simple-ids/ledger.json'").replace("P/'inputs/formalization'","P/'inputs-simple-ids/formalization'").replace("P/'inputs/proofs.lean'","P/'inputs-simple-ids/proofs.lean'")
new=new.replace('for label,args in commands[5:]:',"for label,args in [x for x in commands if x[0] not in ('07b-source-compile','08-source-admit')]:")
(P/'run_simple_ids.py').write_text(new)
