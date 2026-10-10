import json,subprocess,sys,time
from pathlib import Path
P=Path('validation/isolated-collection-bridge-20261010-gcb');pkg=P/'run-simple-ids'
commands=[
 ('11-interpret',['interpret','--package',str(pkg),'--prompt-file',str(P/'specification.json'),'--candidate',str(P/'inputs-simple-ids/draft.json'),'--ledger',str(P/'inputs-simple-ids/ledger.json'),'--mode','software','--non-interactive']),
 ('12-formalize',['formalize','--package',str(pkg),'--candidate',str(P/'inputs-simple-ids/formalization')]),
 ('13-prove',['prove','--package',str(pkg),'--candidate',str(P/'inputs-simple-ids/proofs.lean'),'--no-portfolio','--budget-seconds','0']),
 ('14-accept',['accept','--package',str(pkg)]),
 ('15-export',['export','--package',str(pkg)]),
 ('07b-source-compile',['vscore','compile','--package',str(pkg),'--source',str(P/'inputs/program.vsc'),'--out',str(P/'program.json')]),
 ('08-source-admit',['vscore','check','--package',str(pkg),'--source',str(P/'program.json'),'--out',str(P/'source-admission')]),
 ('16-actual-readable-goal',['vscore','goal','--package',str(pkg),'--source',str(P/'program.json'),'--relation',str(P/'inputs/relation.json'),'--out',str(P/'actual-goal'),'--readable-view'])]
for label,args in [x for x in commands if x[0] not in ('07b-source-compile','08-source-admit')]:
 out=P/'diagnostics'/f'{label}.stdout.json';err=P/'diagnostics'/f'{label}.stderr.txt'
 with out.open('wb') as o,err.open('wb') as e:
  r=subprocess.run([sys.executable,str(P/'invoke_cli.py'),label,*args,'--json'],stdout=o,stderr=e)
 (P/'diagnostics'/f'{label}.exit.json').write_text(json.dumps({'exit_code':r.returncode}))
 print(label,r.returncode,flush=True)
 if r.returncode:
  print(out.read_text()[-5000:],flush=True);break
