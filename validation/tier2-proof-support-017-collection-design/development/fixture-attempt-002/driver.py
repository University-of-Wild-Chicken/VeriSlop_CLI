from pathlib import Path
import traceback,unittest
from verislop import canonical
from tests.test_vscore3_collection_bridge import prepared_collection_candidate
root=Path(__file__).resolve().parent
result={"qualification":False,"status":"UNQUALIFIED_DEVELOPMENT_STARTED","registered_closure_run":False}
(root/"development-result.json").write_bytes(canonical.dumps(result))
try:
 pkg,candidate,info=prepared_collection_candidate(root,unittest.TestCase())
 result.update(status="UNQUALIFIED_PREVIEWS_PASS",package=str(pkg.root),candidate=str(candidate))
except BaseException as exc:
 result.update(status="UNQUALIFIED_DEVELOPMENT_FAILED",error={"type":type(exc).__name__,"message":str(exc)})
 (root/"exception.txt").write_text(traceback.format_exc())
 raise
finally:
 (root/"development-result.json").write_bytes(canonical.dumps(result))
