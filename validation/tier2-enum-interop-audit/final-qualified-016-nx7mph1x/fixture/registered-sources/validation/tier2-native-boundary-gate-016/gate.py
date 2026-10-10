"""Frozen generic enum qualification; no task input or model call."""
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = Path(__file__).resolve().parent
if Path.cwd() != ROOT:
    raise RuntimeError("Run this qualification in the exact workspace root")
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical

MODULES = [
    "tests.test_data_contract_core",
    "tests.test_formal_frontend",
    "tests.test_formal_frontend_enums",
    "tests.test_enum_equality_core",
    "tests.test_enum_authoring_workflow_unit",
    "tests.test_formal_frontend_workflow",
    "tests.test_formalizer_rejection_diagnostics",
    "tests.test_autonomous_correction",
    "tests.test_autonomous_probe_signal",
    "tests.test_bootstrap_tier2",
    "tests.test_formal_frontend_enum_tier2",
]
freeze = bootstrap.freeze_engineering(GATE / "source-freeze.json")
test_hashes = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
               for p in sorted((ROOT / "tests").rglob("*.py"))}
bootstrap.write_once(GATE / "test-sources.json", test_hashes)
all_hashes = {**freeze["source_files"], **test_hashes,
              Path(__file__).relative_to(ROOT).as_posix(): canonical.digest_file(Path(__file__))}
qualification = {"format": "verislop.enum-qualification-input-freeze/1",
                 "source_hashes": all_hashes, "source_root": freeze["source_root"],
                 "test_root": canonical.digest_json(test_hashes),
                 "engineering_freeze_hash": canonical.digest_file(GATE / "source-freeze.json"),
                 "task_inputs": False, "model_calls": 0}
bootstrap.write_once(GATE / "qualification-inputs.json", qualification)
os.environ["VERISLOP_ENUM_QUALIFICATION_FREEZE"] = str(GATE / "qualification-inputs.json")
bootstrap.write_once(GATE / "invocation.json", {
    "format": "verislop.tier2-native-engineering-invocation/0.1",
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
    "source_root": freeze["source_root"], "test_modules": MODULES,
    "fresh_task_model_calls": 0, "task_inputs_supplied": False,
    "qualification_inputs_hash": canonical.digest_file(GATE / "qualification-inputs.json"),
    "driver_script_sha256": canonical.digest_file(Path(__file__)),
})
started = time.monotonic()
suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
result = unittest.TextTestRunner(verbosity=2).run(suite)
after = bootstrap.source_inventory()
tests_after = {name: canonical.digest_file(ROOT / name) for name in test_hashes}
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
    "scope": "generic enum accepted AST, guards, universal source refinement, registered two-build closure and retained release probe; no task answer transfer",
})
sys.exit(0 if passed else 2)
