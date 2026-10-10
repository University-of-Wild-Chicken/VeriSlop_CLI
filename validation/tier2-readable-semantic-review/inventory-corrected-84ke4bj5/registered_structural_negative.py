from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
from verislop.bridges import check
rows=[]
for case in ('selection-size','diagnostic-size','no-selection-plan-only'):
 root=Path(__file__).parent/('generic-prepared-bundle-'+case)
 result=check.validate_package(root,Path('plan.json'),Path('artifacts.json'))
 row={'case':case,'result':result.to_json()}
 assert result.status=='BLOCKED'
 if case=='no-selection-plan-only':
  assert any('manifest does not exactly cover declared artifact slots' in d.message for d in result.diagnostics)
 else:
  assert any(d.code=='INPUT_MUTATION' and 'size/hash does not match actual bytes' in d.message for d in result.diagnostics)
 rows.append(row)
output={'actual_registered_structural_validator':rows,'scope':'Pure structural validation, no accepted-contract/kernel/semantic replay; failure occurs before accepted-contract checks.'}
(Path(__file__).parent/'registered-structural-negative.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
