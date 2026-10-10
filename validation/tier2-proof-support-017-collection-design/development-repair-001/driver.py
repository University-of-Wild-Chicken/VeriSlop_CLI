from pathlib import Path
import importlib.util
import hashlib
import json
import traceback
import unittest
import sys

repository = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repository))
repair = Path(__file__).resolve().parent
fixture_path = repository / "tests/test_vscore3_collection_bridge.py"
spec = importlib.util.spec_from_file_location("generic_collection_repair_development", fixture_path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
run_root = repair / "fresh-prepared-candidate"
run_root.mkdir(exist_ok=False)
result = {"qualification": False, "scope": "fresh actual prepared_collection_candidate only; no registered closure qualification",
          "test_hash": "sha256:" + hashlib.sha256(fixture_path.read_bytes()).hexdigest()}
try:
    pkg, candidate, info = fixture.prepared_collection_candidate(run_root, unittest.TestCase())
    result.update(status="UNQUALIFIED_REAL_PREPARED_CANDIDATE_PASS", candidate=str(candidate),
                  selected_mode=fixture.canonical.loads(info["readable_selection"])["selected_mode"])
except BaseException as exc:
    result.update(status="UNQUALIFIED_ACTUAL_FAILURE", error={"type": type(exc).__name__, "message": str(exc)})
    (repair / "failure-trace.txt").write_text(traceback.format_exc())
    raise
finally:
    (repair / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
