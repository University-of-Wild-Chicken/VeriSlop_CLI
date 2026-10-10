from pathlib import Path
import sys,json,hashlib
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
sys.path.insert(0,str(Path(__file__).parent/'runtime/tests'))
from test_vscore3_readable_cli import ReadableCLITests
from test_vscore3_readable_integration import ProductionReadableMetadata
from verislop import cli
from verislop.errors import UsageError
from verislop.bridges import vscore3_checker as checker

def inv(root):
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
rows=[]
for field in ['support/readable/selection.json','support/readable/diagnostic.json','readable/ReadableSource.lean']:
 a=ReadableCLITests();a.setUp()
 try:
  a.args.readable_view=True;out=Path(a.args.out);out.mkdir(parents=True);(out/'VeriSlopBridgeGoal.lean').write_bytes(b'prior untouched goal')
  (out/field).mkdir(parents=True)
  before=inv(out);caught=None
  with patch.object(checker,'preview',return_value=(a.spec,None,a.info)):
   try:cli.cmd_vscore(a.args)
   except UsageError as exc:caught=str(exc)
  after=inv(out)
  assert caught and before==after
  rows.append({'case':'directory at emitted artifact','path':field,'outcome':'REJECTED_BEFORE_WRITE','message':caught,'files_before':before,'files_after':after})
 finally:a.doCleanups()
a=ReadableCLITests();a.setUp();b=ProductionReadableMetadata();b.setUp()
try:
 metadata={checker.READABLE_SELECTION_PATH:b.selection,**b.ctx.readable_diagnostics}
 selected={**a.info,'readable_selection':b.selection,'readable_candidate_artifacts':metadata,'readable_artifacts':dict(b.build.readable_artifacts)}
 a.args.readable_view=True
 with patch.object(checker,'preview',return_value=(a.spec,None,selected)):
  assert cli.cmd_vscore(a.args).status=='PASS'
 out=Path(a.args.out);before=inv(out);a.args.readable_view=False
 legacy={k:v for k,v in a.info.items() if not k.startswith('readable_')}
 legacy.update(readable_selection=None,readable_candidate_artifacts={},readable_artifacts={},readable_source_view=None)
 caught=None
 with patch.object(checker,'preview',return_value=(a.spec,None,legacy)):
  try:cli.cmd_vscore(a.args)
  except UsageError as exc:caught=str(exc)
 after=inv(out);assert caught and before==after
 rows.append({'case':'original selected to no-flag BASE out reuse','outcome':'REJECTED_BEFORE_WRITE','message':caught,'files_before':before,'files_after':after})
finally:a.doCleanups();b.doCleanups()
result={'cases':rows,'all_rejected_before_any_write':True,'scope':'generic consumer mock preview + real closed BASE metadata; no Lean/native/models/task inputs'}
print(json.dumps(result,indent=2));(Path(__file__).parent/'independent-replay.json').write_text(json.dumps(result,indent=2)+'\n')
