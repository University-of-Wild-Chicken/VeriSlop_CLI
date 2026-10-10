"""Run the frozen generic pre-live gate; this script contains no task inputs."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = Path(__file__).resolve().parent
if Path.cwd() != ROOT:
    raise RuntimeError("The engineering gate must run in the exact workspace root")
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical

MODULES = [
    "tests.test_bootstrap_tier2",
    "tests.test_tier2_interpretation_context",
    "tests.test_vscore3_source_pipeline",
    "tests.test_vscore3_proof_support",
    "tests.test_compile_process_evidence",
    "tests.test_compile_process_persistence",
    "tests.test_compile_process_projection",
    "tests.test_vscore3_readable_integration",
    "tests.test_vscore3_readable_cli",
    "tests.test_vscore3_workflow_unit",
    "tests.test_vscore_workflow_unit",
    "tests.test_vscore3_readable",
]
freeze = bootstrap.freeze_engineering(GATE / "source-freeze.json")
test_paths = sorted({"tests/" + name.rsplit(".", 1)[-1] + ".py" for name in MODULES}
                    | {"tests/helpers.py"})
test_hashes = {name: canonical.digest_file(ROOT / name) for name in test_paths}
bootstrap.write_once(GATE / "test-sources.json", test_hashes)
bootstrap.write_once(GATE / "invocation.json", {
    "format": "verislop.tier2-native-engineering-invocation/0.1",
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
    "source_root": freeze["source_root"], "test_modules": MODULES,
    "fresh_task_model_calls": 0, "task_inputs_supplied": False,
    "driver_script_sha256": canonical.digest_file(Path(__file__)),
})
started = time.monotonic()
suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
result = unittest.TextTestRunner(verbosity=2).run(suite)
after = bootstrap.source_inventory()
tests_after = {name: canonical.digest_file(ROOT / name) for name in test_paths}
unchanged = after == freeze["source_files"] and tests_after == test_hashes
passed = result.wasSuccessful() and not result.skipped and unchanged
bootstrap.write_once(GATE / "run-result.json", {
    "format": "verislop.tier2-native-engineering-gate/0.1",
    "status": "PASS" if passed else "FAIL",
    "tests_run": result.testsRun, "errors": len(result.errors),
    "failures": len(result.failures), "skipped": len(result.skipped),
    "duration_seconds": str(time.monotonic() - started),
    "test_modules": MODULES, "test_sources": test_hashes,
    "source_root_before": freeze["source_root"],
    "source_root_after": canonical.digest_json(after),
    "source_unchanged": after == freeze["source_files"],
    "test_sources_unchanged": tests_after == test_hashes,
    "fresh_model_calls": 0,
    "scope": "generic current source, universal readable correspondence, exact metadata transport, two-build closure and negative regressions; no task answer transfer",
})
sys.exit(0 if passed else 2)
