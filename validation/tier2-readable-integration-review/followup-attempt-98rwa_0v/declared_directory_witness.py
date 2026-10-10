from pathlib import Path
import sys,json
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
sys.path.insert(0,str(Path(__file__).parent/'runtime/tests'))
from test_vscore3_readable_cli import ReadableCLITests
from verislop import cli
from verislop.bridges import vscore3_checker as checker

a=ReadableCLITests();a.setUp()
try:
 a.args.readable_view=True
 out=Path(a.args.out);(out/checker.READABLE_SELECTION_PATH).mkdir(parents=True)
 caught=None
 with patch.object(checker,'preview',return_value=(a.spec,None,a.info)):
  try:cli.cmd_vscore(a.args)
  except Exception as exc:caught={'type':type(exc).__name__,'message':str(exc)}
 result={'exception':caught,'goal_written':(out/'VeriSlopBridgeGoal.lean').exists(),'model_written':(out/checker.FILES['model']).exists(),'profile_written':(out/checker.FILES['profile']).exists(),'existing_declared_artifact_remains_directory':(out/checker.READABLE_SELECTION_PATH).is_dir(),'scope':'CLI writer only; preview boundary mocked; no Lean/native/models'}
 assert caught and caught['type']=='IsADirectoryError'
 assert result['goal_written'] and result['model_written'] and result['profile_written']
 print(json.dumps(result,indent=2));(Path(__file__).parent/'declared-directory-witness.json').write_text(json.dumps(result,indent=2)+'\n')
finally:a.doCleanups()
