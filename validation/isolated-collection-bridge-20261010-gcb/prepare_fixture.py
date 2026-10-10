import json,subprocess,sys
from pathlib import Path
P=Path('validation/isolated-collection-bridge-20261010-gcb');pkg=P/'run-simple-ids';candidate=P/'bridge-candidate'
commands=[
 ('22-current-checker-positive',['vscore','goal','--package',str(pkg),'--source',str(P/'program.json'),'--relation',str(P/'inputs/relation.json'),'--proof',str(P/'ActualControls-v1.lean'),'--readable-selection',str(P/'actual-goal/support/readable/selection.json'),'--out',str(candidate),'--bridge-id','isolated-collection']),
 ('23-bridge-prepare',['bridge','prepare','--package',str(pkg),'--proposal',str(candidate/'proposal.json'),'--candidate-dir',str(candidate)])]
for label,args in commands:
 out=P/'diagnostics'/f'{label}.stdout.json';err=P/'diagnostics'/f'{label}.stderr.txt'
 with out.open('wb') as o,err.open('wb') as e:r=subprocess.run([sys.executable,str(P/'invoke_cli.py'),label,*args,'--json'],stdout=o,stderr=e)
 (P/'diagnostics'/f'{label}.exit.json').write_text(json.dumps({'exit_code':r.returncode}))
 print(label,r.returncode,flush=True)
 if r.returncode:
  try:
   x=json.loads(out.read_bytes());print([(d['code'],d['message']) for d in x.get('diagnostics',[])],flush=True)
  except Exception:print(out.read_text()[-5000:],flush=True)
  break
